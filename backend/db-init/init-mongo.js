// ─────────────────────────────────────────────────────────────────────────
// IMS — MongoDB initialization
// Runs once when the container is first created.
// Creates collections and indexes for the signals audit log.
// ─────────────────────────────────────────────────────────────────────────

db = db.getSiblingDB("ims_db");

// ── Signals collection ────────────────────────────────────────────────────
// Every raw signal payload is stored here immutably.
// This is the audit log — nothing is ever deleted.
db.createCollection("signals");

// Look up all signals for a Work Item (used by incident detail endpoint)
db.signals.createIndex({ work_item_id: 1 });

// Look up signals by component (used by analytics)
db.signals.createIndex({ component_id: 1 });

// Time-range queries on the audit log
db.signals.createIndex({ received_at: -1 });

// Compound: component + time (most common dashboard query)
db.signals.createIndex({ component_id: 1, received_at: -1 });

// ── Dead Letter Queue collection ──────────────────────────────────────────
// Signals that failed to persist after all retries land here.
// An operator can inspect and replay these after DB recovery.
db.createCollection("dead_letter");

db.dead_letter.createIndex({ received_at: -1 });
db.dead_letter.createIndex({ component_id: 1 });
// TTL index: auto-delete dead letter entries after 7 days
db.dead_letter.createIndex(
    { received_at: 1 },
    { expireAfterSeconds: 604800, name: "ttl_dead_letter_7d" }
);

print("MongoDB initialization complete.");
print("Collections created: signals, dead_letter");
print("Indexes created on signals: work_item_id, component_id, received_at, compound");
print("Indexes created on dead_letter: received_at (TTL 7d), component_id");