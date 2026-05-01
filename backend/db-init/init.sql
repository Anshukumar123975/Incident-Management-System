-- ─────────────────────────────────────────────────────────────────────────
-- IMS — PostgreSQL + TimescaleDB initialization
-- This script runs once when the container is first created.
-- It is idempotent: safe to re-run without data loss.
-- ─────────────────────────────────────────────────────────────────────────

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Work Items ────────────────────────────────────────────────────────────
-- The source of truth for every incident.
-- Each Work Item maps to one deduplicated incident (after debouncing).
CREATE TABLE IF NOT EXISTS work_items (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    component_id      TEXT        NOT NULL,
    component_type    TEXT        NOT NULL,   -- RDBMS | API | MCP_HOST | ASYNC_QUEUE | CACHE | NOSQL
    severity          TEXT        NOT NULL,   -- P0 | P1 | P2
    status            TEXT        NOT NULL DEFAULT 'OPEN',
    signal_count      INTEGER     NOT NULL DEFAULT 1,
    is_anomaly        BOOLEAN     NOT NULL DEFAULT FALSE,
    start_time        TIMESTAMPTZ NOT NULL,
    end_time          TIMESTAMPTZ,
    mttr_seconds      FLOAT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for dashboard queries: active incidents sorted by severity + time
CREATE INDEX IF NOT EXISTS idx_work_items_status_severity
    ON work_items (status, severity, created_at DESC);

-- Index for debouncer lookups by component
CREATE INDEX IF NOT EXISTS idx_work_items_component_status
    ON work_items (component_id, status);

-- ── RCA Records ───────────────────────────────────────────────────────────
-- Mandatory before a Work Item can be CLOSED.
-- Transitions to CLOSED are transactional: RCA insert + status update
-- happen in the same DB transaction.
CREATE TABLE IF NOT EXISTS rca_records (
    id                     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id           UUID        NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    root_cause_category    TEXT        NOT NULL,   -- INFRA | CODE | CONFIG | DEPENDENCY | UNKNOWN
    fix_applied            TEXT        NOT NULL,
    prevention_steps       TEXT        NOT NULL,
    incident_start         TIMESTAMPTZ NOT NULL,
    incident_end           TIMESTAMPTZ NOT NULL,
    submitted_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_rca_work_item UNIQUE (work_item_id)  -- one RCA per Work Item
);

CREATE INDEX IF NOT EXISTS idx_rca_work_item_id
    ON rca_records (work_item_id);

-- ── Work Item Events ──────────────────────────────────────────────────────
-- Audit trail for every state transition and notable event.
-- Powers the /incidents/{id}/timeline endpoint.
CREATE TABLE IF NOT EXISTS work_item_events (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id  UUID        NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    event_type    TEXT        NOT NULL,   -- STATUS_CHANGED | RCA_SUBMITTED | ESCALATED | ANOMALY_DETECTED
    old_value     TEXT,
    new_value     TEXT,
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_work_item_time
    ON work_item_events (work_item_id, created_at ASC);

-- ── Signal Metrics (TimescaleDB hypertable) ───────────────────────────────
-- Aggregated signal counts for time-series queries.
-- The worker flushes a batch here every 5 seconds.
-- TimescaleDB automatically partitions this by time.
CREATE TABLE IF NOT EXISTS signal_metrics (
    time            TIMESTAMPTZ NOT NULL,
    component_id    TEXT        NOT NULL,
    component_type  TEXT        NOT NULL,
    severity        TEXT        NOT NULL,
    signal_count    INTEGER     NOT NULL DEFAULT 1
);

-- Convert to hypertable (partitioned by time, 1-hour chunks)
-- The DO block makes this idempotent — won't fail if already a hypertable
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'signal_metrics'
    ) THEN
        PERFORM create_hypertable('signal_metrics', 'time', chunk_time_interval => INTERVAL '1 hour');
    END IF;
END$$;

-- Index for per-component time-series queries
CREATE INDEX IF NOT EXISTS idx_signal_metrics_component_time
    ON signal_metrics (component_id, time DESC);

-- ── Auto-update updated_at on work_items ─────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_work_items_updated_at ON work_items;
CREATE TRIGGER trg_work_items_updated_at
    BEFORE UPDATE ON work_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();