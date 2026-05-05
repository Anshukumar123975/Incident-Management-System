# Incident Management System (IMS)

A production-grade Incident Management System designed to handle high-volume infrastructure signals with strong guarantees around scalability, consistency, and observability.

Repository:  
https://github.com/Anshukumar123975/Incident-Management-System

---

## 1. Problem Statement

Modern distributed systems generate large volumes of signals (logs, alerts, metrics).  
Without proper handling, this leads to:

- Duplicate alerts flooding the system
- Blocking I/O reducing throughput
- Poor incident lifecycle management
- Lack of observability during failures

This project addresses these issues by building a system that is:
- Asynchronous
- Fault-tolerant
- Observable
- Extensible

---

## 2. System Overview

The Incident Management System (IMS) processes infrastructure signals end-to-end:

1. Signals are ingested via an HTTP API
2. Buffered in an async queue (non-blocking)
3. Deduplicated using Redis (debouncer)
4. Processed by worker pool
5. Persisted across multiple storage systems
6. Exposed via APIs and real-time dashboard
7. Managed through a strict incident lifecycle

A simulation script generates 230 signals and demonstrates the full lifecycle in under 20 seconds.

---

## 3. Key Features

### 3.1 High-Throughput Ingestion
- Accepts large volumes of incoming signals
- Uses async FastAPI endpoints
- Returns immediately (non-blocking ingestion)

### 3.2 Backpressure Handling
- Implemented using `asyncio.Queue` (capacity ~50k)
- Prevents API thread from blocking under load
- Workers consume at controlled pace

### 3.3 Signal Deduplication
- Redis-based debouncer using `INCR + TTL`
- Example:
  - 100 signals in 10 seconds → 1 work item
- Achieves ~99% reduction in redundant writes

### 3.4 Incident Lifecycle Management
Managed through a strict state machine:

OPEN → INVESTIGATING → RESOLVED → CLOSED

- Invalid transitions are rejected
- CLOSED requires valid RCA submission
- Thread-safe transitions using locks

### 3.5 Real-Time Updates
- WebSocket endpoint (`/ws/feed`)
- Uses Redis Pub/Sub
- Dashboard updates instantly

---

## 4. System Architecture

| Layer            | Technology                     | Responsibility |
|-----------------|-------------------------------|---------------|
| API Gateway     | FastAPI + Uvicorn             | Signal ingestion, REST APIs, WebSockets |
| Buffer          | asyncio.Queue                 | Handles backpressure |
| Workers         | Async coroutines              | Process signals and persist data |
| Debouncer       | Redis                         | Deduplicates incoming signals |
| State Machine   | Python                        | Controls incident lifecycle |
| Circuit Breaker | Custom async implementation   | Prevents cascading failures |
| Primary DB      | PostgreSQL + TimescaleDB      | Stores work items and metrics |
| Audit Log       | MongoDB                       | Stores raw signals and DLQ |
| Cache / PubSub  | Redis                         | Caching and real-time messaging |
| Frontend        | React + Vite + Tailwind       | User interface |
| Proxy           | Nginx                         | Routing and static serving |

---

## 5. Design Decisions

### 5.1 Why asyncio.Queue instead of Kafka?
- Lower operational complexity
- Sufficient for in-memory buffering
- No external dependency overhead

### 5.2 Why Redis for Debouncing?
- Atomic operations (`INCR`)
- TTL support for time-window aggregation
- High performance for real-time systems

### 5.3 Why PostgreSQL + TimescaleDB?
- Strong consistency for core data
- Efficient time-series queries (MTTR, trends)

### 5.4 Why MongoDB?
- Flexible schema for raw signals
- Ideal for audit logs and DLQ storage

### 5.5 Why Redis (again)?
- Cache layer for read-heavy endpoints
- Pub/Sub for WebSocket broadcasting
- Rate limiting

---

## 6. Concurrency Model

- 8 async workers process signals concurrently
- Each worker:
  - Reads from queue
  - Applies debouncing
  - Writes to storage

### Synchronization
- `asyncio.Lock` ensures:
  - No race conditions during state transitions
  - Consistent updates per work item

---

## 7. Resilience

### 7.1 Circuit Breaker (Per Database)

States:
- CLOSED → normal operation
- OPEN → fail fast after repeated failures
- HALF-OPEN → probe recovery

Behavior:
- Trips after 5 failures
- Retry after 30 seconds
- Prevents blocking on failing services

### 7.2 Retry Mechanism
- Exponential backoff for database writes

### 7.3 Dead Letter Queue
- Failed signals stored in MongoDB
- Enables post-failure analysis

---

## 8. Security

- API Key authentication (X-API-Key header)
- Rate limiting using Redis
- Input validation via Pydantic
- Restricted CORS configuration
- Security headers:
  - X-Content-Type-Options
  - X-Frame-Options
- Environment-based secret management

---

## 9. Performance Optimizations

- Fully async I/O (non-blocking)
- Connection pooling (SQLAlchemy async)
- Batch writes (MongoDB)
- Redis caching (2-second TTL)
- GZip compression
- Time-series indexing with TimescaleDB

---

## 10. Observability

### Metrics
Available at `/metrics` (Prometheus format):
- ims_signals_ingested_total
- ims_queue_depth
- ims_work_items_active
- ims_circuit_breaker_state

### Logging
- Structured JSON logs
- Includes:
  - correlation_id
  - work_item_id
  - latency
  - queue depth

### Monitoring
- Health endpoint (`/health`)
- Real-time throughput logs

---

## 11. API Reference

| Method | Endpoint | Description |
|--------|---------|-------------|
| POST   | /signals | Ingest signal |
| GET    | /incidents | List incidents |
| GET    | /incidents/{id} | Incident details |
| PATCH  | /incidents/{id} | Update state |
| POST   | /rca | Submit RCA |
| GET    | /incidents/{id}/timeline | Timeline |
| GET    | /analytics/mttr | MTTR metrics |
| GET    | /health | Health check |
| GET    | /metrics | Prometheus metrics |
| WS     | /ws/feed | Real-time stream |

---

## 12. Local Setup

```bash
git clone https://github.com/Anshukumar123975/Incident-Management-System.git
cd Incident-Management-System
cp .env.example .env
docker compose up --build