# LinkUp Commerce Engine — Engineering Standards, Performance & Scalability

**Document type:** Implementation Quality Contract / Engineering Standards  
**Version:** v1.0  
**Date:** 2026-09-08  
**Product:** LinkUp Commerce Engine  
**Stack:** FastAPI + PostgreSQL + SQLAlchemy 2.x Core async + Alembic + Redis + Async Workers  
**Architecture:** Modular Monolith  
**Applies to:** Codex, backend engineers, reviewers, DevOps, QA

---

## 1. Purpose

This document defines the implementation quality bar for LinkUp Commerce.

The architecture/business/API documents define **what the system must do**. This
document defines **how it must be engineered** so the implementation remains:

- fast;
- database-efficient;
- safe under concurrency;
- horizontally scalable;
- observable;
- resilient under load;
- maintainable;
- predictable for frontend clients.

This is not a premature-optimization checklist. It exists to prevent common
production failures such as N+1 queries, long transactions, deep OFFSET pagination,
connection-pool exhaustion, cache stampedes, retry storms, blocking I/O in async
paths, unbounded workers, missing indexes, huge synchronous exports and provider
calls inside database locks.

---

## 1.1 Persistence Standard

> **Persistence standard:** LinkUp Commerce uses PostgreSQL with SQLAlchemy 2.x Core async as the default database-access architecture. Declarative ORM models, relationship-driven persistence, lazy loading and ORM identity-map behavior are not part of the default implementation model. Database interaction should be explicit, measurable and optimized through Core statements, dedicated repositories/query services and controlled transaction boundaries.

```text
FastAPI
    ↓
Application / Domain
    ↓
Repositories + Query Services
    ↓
SQLAlchemy 2.x Core async
    ↓
PostgreSQL
```

The primary building blocks are `AsyncEngine`, `AsyncConnection`, `MetaData`,
`Table`, `select()`, `insert()`, `update()`, `delete()` and `RETURNING`.

SQLAlchemy itself remains approved. Any deliberate introduction of SQLAlchemy ORM
for an isolated use case requires explicit architectural justification and must not
become an implicit project-wide dependency.

---

## 2. Non-Negotiable Engineering Principles

1. Correctness before performance.
2. PostgreSQL is canonical commerce truth.
3. Redis is an optimization, never hidden financial/inventory truth.
4. Preserve ACID properties for critical business transactions.
5. Keep DB transactions short.
6. Never perform provider HTTP while holding critical DB locks.
7. Avoid N+1 queries by design.
8. Every growing collection API must be bounded.
9. Use cursor/keyset pagination for large datasets.
10. Every hot query must have a known index strategy.
11. Never share one transactional `AsyncConnection` across independent concurrent units of work; each operation must acquire its own connection/transaction scope from the `AsyncEngine` pool.
12. Async request paths must not perform blocking I/O.
13. Retry only when an operation is safely retryable.
14. Idempotency and reconciliation are mandatory for retry-prone side effects.
15. Worker concurrency must be bounded.
16. Observe P50/P95/P99, not only averages.
17. Performance regressions are defects.
18. Scalability must never weaken money, inventory, authorization or audit rules.
19. Do not introduce microservices before a measured operational reason exists.
20. Optimize from evidence: traces, query counts, `EXPLAIN`, load tests and metrics.

---

## 3. Initial Performance Budgets

These are starting engineering goals and must be validated against real infrastructure.

| Path | Initial P95 target |
|---|---:|
| Cached storefront read | < 250 ms |
| Product detail | < 400 ms |
| Product listing | < 500 ms |
| Cart mutation | < 600 ms |
| Checkout local mutation | < 800 ms |
| Checkout completion local DB work | < 1000 ms |
| Typical admin list | < 800 ms |
| Typical admin detail | < 600 ms |

External provider latency is measured separately.

A latency target must never be achieved by weakening correctness.

---

## 4. ACID Requirements

### Atomicity

A critical business transaction either completes fully or not at all.

Example:

```text
Order
+ Order Items
+ Address/Tax/Discount Snapshots
+ Reservation Consumption
+ Redemption
+ Status History
+ Outbox
= one atomic transaction
```

### Consistency

Every commit must preserve invariants such as:

```text
reserved + damaged <= on_hand
fulfilled <= ordered
refund <= refundable amount
one checkout <= one order
one provider event <= one financial effect
```

### Isolation

Concurrency correctness must use PostgreSQL primitives:

- unique constraints;
- row locks;
- atomic conditional SQL;
- deterministic lock ordering;
- appropriate isolation;
- bounded deadlock/serialization retry.

Python read-then-write checks are not isolation.

### Durability

After commit, commerce truth must survive:

- API crash;
- worker crash;
- Redis loss;
- process restart.

---

## 5. Transaction Standards

Default PostgreSQL `READ COMMITTED` is acceptable for most operations when combined
with explicit locking/constraints.

Do not globally use `SERIALIZABLE` as a substitute for sound domain design.

Critical operations needing deliberate locking include:

- inventory reserve/release/consume;
- checkout completion;
- refund claim;
- discount last-use;
- fulfillment quantity allocation;
- return receipt;
- transfer receipt;
- refresh-token rotation.

Never place these inside a transaction:

```text
Razorpay / Stripe HTTP
Shiprocket / Delhivery HTTP
Email / SMS / WhatsApp
Object-storage upload
Outbound webhook
ERP / CRM call
```

Pattern:

```text
persist local intent
COMMIT
call provider
persist verified result or reconciliation state
```

---

## 6. Repositories and Unit of Work

The application use case owns the transaction.

Repositories may execute explicit `SELECT`, `INSERT`, `UPDATE` and `DELETE`
statements; acquire row locks; use `RETURNING`; perform bounded batch operations;
and map database rows into typed domain/application DTOs or projections.

Repositories must not independently `commit()`, hide unrelated cross-module
mutations, open arbitrary nested transactions unless explicitly designed, return
SQLAlchemy ORM objects, depend on ORM flushing, or expose database
`Row`/`RowMapping` objects outside the infrastructure/application boundary when a
typed projection or domain value is expected.

One command should have one clear transaction owner.

---

## 7. SQLAlchemy Core Async Standards

Use SQLAlchemy 2.x Core async APIs with an application-managed `AsyncEngine`.
Connections are acquired from the engine pool and used only within an explicit,
scoped connection or transaction context.

Never create a global shared connection or share one transactional connection across
independent concurrent tasks.

Correct:

```text
Task A → AsyncConnection/transaction A
Task B → AsyncConnection/transaction B
Task C → AsyncConnection/transaction C
```

Wrong:

```text
10 concurrent tasks → one transactional connection
```

Repositories and query services receive, or operate within, the explicit transaction
scope owned by the application use case. Use parameterized Core statements only;
never construct raw SQL with string concatenation. Raw SQL via `text()` is allowed
only when Core cannot express an important optimized PostgreSQL query cleanly, and
it must remain parameterized and receive focused review.

There is no hidden relationship loading. All required data access must be visible
in explicit statements or dedicated query services.

---

## 8. N+1 Query Prevention

An N+1 query pattern is a production defect on important endpoints.

Bad:

```text
1 query loads 50 orders
50 queries load customers
50 queries load payment summaries
50 queries load fulfillment summaries
```

Use explicit joins, explicit column selection, aggregate/subquery projections, CTEs
where justified, batch queries and dedicated query services. Avoid query-per-row
loops and fetching complete relational graphs when a summary projection is enough.

---

## 9. Query Services

Complex reads should use dedicated optimized query services instead of loading full
domain aggregates.

Examples:

```text
AdminOrderListQuery
StorefrontProductCardQuery
InventoryAdminListQuery
```

Command-side repositories preserve domain ownership.

Read-side projections may use optimized SQL without introducing distributed CQRS.
They select only required columns, use explicit joins/subqueries/aggregates, use
cursor/keyset pagination for growing data, and have query-count and latency
expectations. PostgreSQL-specific features are appropriate when they materially
improve correctness or performance.

---

## 10. Query Count Budgets

Important endpoints should have approximate query-count budgets.

Suggested starting budgets:

| Endpoint class | Suggested max |
|---|---:|
| Product detail | 5 |
| Product list | 4 |
| Admin order list | 5 |
| Order detail | 8 |
| Cart read | 5 |

These can change when justified, but large regressions require review.

Add query-count regression tests for high-traffic endpoints where useful.

---

## 11. Indexing Standards

Index according to real API and query-service access patterns, not ORM
relationships.

Review indexes for:

- frequently joined foreign keys;
- `store_id`;
- status + timestamp worker scans;
- cursor pagination;
- unique business references;
- provider IDs;
- order/customer lookups;
- active reservations;
- pending outbox events.

PostgreSQL does not automatically index referencing FK columns.

Do not index every column blindly.

Indexes increase:

- write cost;
- storage;
- vacuum work;
- migration time.

---

## 12. Composite Index Design

Index order must match common filtering and sorting.

Example:

```sql
(store_id, status, created_at DESC, order_id DESC)
```

supports:

```text
WHERE store_id = ?
AND status = ?
ORDER BY created_at DESC, order_id DESC
```

Do not assume differently ordered composite indexes are equivalent.

---

## 13. Cursor Pagination

Large datasets must use cursor/keyset pagination.

Preferred:

```text
ORDER BY created_at DESC, id DESC
```

Cursor:

```text
(created_at, id)
```

Next page:

```text
WHERE (created_at, id) < (:created_at, :id)
```

Avoid deep:

```text
OFFSET 100000 LIMIT 25
```

for growing product/order/customer/event tables.

Ordering must be deterministic.

---

## 14. Partial Indexes

Use partial indexes for hot subsets where justified.

Examples:

```text
ACTIVE inventory reservations
PENDING outbox events
unprocessed provider events
ACTIVE discounts
```

Example:

```sql
CREATE INDEX ...
ON outbox_events (available_at, created_at)
WHERE status = 'PENDING';
```

---

## 15. JSONB Standards

JSONB is for genuinely flexible data:

- provider payloads;
- low-risk metadata;
- configurable rule payloads;
- custom properties.

Do not move core relational truth into JSONB for convenience.

Do not add a GIN index to every JSONB column.

Index JSONB only when an actual production query requires it.

---

## 16. PostgreSQL-first Query Efficiency and Review

Select only needed columns rather than using unnecessary wide `SELECT *` queries.
Use `RETURNING` when it removes a safe extra round trip. Prefer set-based SQL over
Python loops, bounded bulk inserts/updates for safe batches, and PostgreSQL `COPY`
for very large controlled imports. Avoid query-per-row writes, minimize round trips,
measure query counts, and review execution plans on hot paths.

The persistence layer may intentionally use PostgreSQL capabilities when they
materially improve correctness or performance: `RETURNING`, partial and expression
indexes, `FOR UPDATE`, `FOR UPDATE SKIP LOCKED`, tuple/keyset comparison, CTEs,
appropriate JSONB operators, `ON CONFLICT`, `COPY`, generated/functional indexes,
and justified advisory locks. Do not force database-agnostic abstractions that
degrade correctness, performance or clarity; PostgreSQL is the approved canonical
database.

For high-volume queries use:

```text
EXPLAIN
EXPLAIN ANALYZE
BUFFERS
```

in safe environments with representative data.

Look for:

- sequential scans on large tables;
- index usage and rows removed by filter;
- nested-loop explosion;
- sort/hash spills;
- buffer reads;
- missing indexes;
- cardinality misestimation;
- lock behavior; and
- query duration.

---

## 17. Connection Pooling

`AsyncEngine` pool capacity is finite. Connections are acquired and returned by
explicit Core connection/transaction contexts.

Monitor:

- pool size;
- checked-out connections;
- wait time;
- pool timeout;
- overflow.

Do not blindly increase pool size.

Total connection demand:

```text
API replicas × API pool
+
workers × worker pool
+
operational headroom
<
safe PostgreSQL capacity
```

Leave connections for migrations, observability and emergency admin access.

Introduce PgBouncer only when measured connection pressure justifies it.

---

## 18. Database Locking

Lock the minimum required rows.

Never hold locks during provider/network work.

For multiple locks use deterministic ordering:

```text
sort stable IDs
→ lock in the same order
```

This reduces deadlock probability.

On deadlock/serialization conflict:

- rollback;
- retry only if safe/idempotent;
- use bounded retries;
- add jitter;
- emit metric/log.

Never infinite-retry.

---

## 19. Optimistic Concurrency

Use versioning for mutable editor-style resources such as:

- products;
- product variants;
- store settings;
- carts;
- checkout sessions;
- pages;
- blog posts.

Pattern:

```sql
UPDATE ...
SET version = version + 1
WHERE id = :id
AND version = :expected
RETURNING id, version;
```

Zero updated rows => `VERSION_CONFLICT`.

Do not use generic optimistic PATCH as a substitute for domain commands on:

- inventory;
- payment;
- refund;
- order lifecycle;
- fulfillment lifecycle.

---

## 20. Bulk Operations

Large imports/exports must be asynchronous.

Do not:

```text
read 50,000 rows
issue one SQL statement per row in a Python loop
commit 50,000 times
```

Prefer:

- bounded chunks;
- bulk insert/update where safe;
- PostgreSQL COPY where appropriate;
- streaming reads;
- checkpoints;
- per-row error evidence.

Domain invariants still apply.

---

## 20.1 Generic CRUD Abstraction Rule

**Generic CRUD repositories/services are not allowed as the default commerce
architecture.** Do not introduce abstractions such as `BaseCRUDRepository`,
`GenericRepository[T]`, `CRUDService` or `BaseModelService` when they hide SQL
behavior, transactions, domain rules or concurrency semantics.

Simple resource-management endpoints may share small utilities. Domain-critical
operations remain explicit business-specific methods/use cases, for example:

```text
create_product() / publish_product() / archive_product()
reserve_inventory() / release_reservation() / consume_reservation()
complete_checkout() / create_payment_intent() / capture_payment()
request_refund() / approve_return() / receive_return()
```

---

## 21. Redis Standards

Good Redis uses:

- cache;
- rate limiting;
- short-lived derived data;
- ephemeral coordination;
- shared non-authoritative session/cache support where designed.

Redis must not be the sole truth for:

- cart;
- inventory;
- order;
- payment;
- refund.

Use cache-aside:

```text
cache read
→ miss
→ PostgreSQL
→ cache with TTL
```

Writes:

```text
PostgreSQL write
COMMIT
→ cache invalidate/update
```

If cache invalidation fails, PostgreSQL remains correct.

---

## 22. Cache Keys and TTL

Namespace cache keys.

Example:

```text
commerce:{store_id}:product:{product_id}:v{version}
commerce:{store_id}:cart:{cart_id}
```

Every mutable cache needs:

- TTL;
- invalidation policy;
- recovery behavior.

Do not use indefinite TTL for mutable commerce data.

---

## 23. Cache Stampede Protection

For expensive hot keys consider:

- single-flight;
- short refresh locks;
- stale-while-revalidate;
- TTL jitter.

Do not let mass cache expiry send thousands of identical queries to PostgreSQL.

---

## 24. API Payload Design

Use purpose-specific DTOs.

Examples:

```text
StorefrontProductCard
StorefrontProductDetail
AdminProductSummary
AdminProductDetail
```

Do not return giant resource graphs.

Do not expose persistence rows or database-shaped records directly as API responses.
Map infrastructure/database rows into purpose-specific response or domain DTOs.

List endpoints should select only required columns where practical.

---

## 25. Money Serialization

Never turn `Decimal` into floating point at JSON boundary.

Return monetary values consistently as decimal strings.

Example:

```json
{
  "amount": "1999.0000",
  "currency": "INR"
}
```

---

## 26. Request Limits

Suggested baseline:

```text
JSON body <= 1 MB
normal inline arrays <= 100 items
search query <= 200 chars
pagination max <= 100
```

Large media uploads use signed object-storage URLs.

Large data operations use bulk jobs.

---

## 27. Async I/O

Do not run blocking I/O in the FastAPI event loop.

Avoid direct async-route use of blocking:

- `requests`;
- filesystem-heavy work;
- sync provider SDKs;
- image transforms;
- large CSV processing;
- PDF generation.

Move to:

- async HTTP;
- worker;
- threadpool;
- process pool;

depending workload.

---

## 28. HTTP Client Pooling

Provider adapters should reuse managed async HTTP clients.

Configure:

- connection pooling;
- keep-alive;
- connect timeout;
- read timeout;
- write timeout;
- pool timeout.

Do not create a fresh network client for every provider call.

---

## 29. External Provider Rules

Every external request has explicit timeout.

Provider retry policy must distinguish:

### Retryable

- temporary network failure;
- 5xx;
- 429 with retry guidance;
- transient connection reset.

### Non-retryable

- invalid signature;
- permission/auth configuration failure;
- malformed request;
- permanent validation 4xx;
- illegal local state.

Provider timeout does not automatically mean provider action failed.

Use reconciliation before new side effect where required.

---

## 30. Circuit Breakers and Provider Concurrency

Provider adapters may use bounded concurrency and circuit breakers.

Respect provider quotas.

A provider outage must not exhaust API threads, DB connections or workers.

Circuit breaker fallback must never invent:

- payment success;
- stock;
- refund success.

---

## 31. Rate Limiting

Protect:

- merchant login;
- customer login;
- checkout mutations;
- payment-session creation;
- coupon probing;
- public search;
- admin writes.

Rate-limit keys should use suitable combinations such as:

```text
store
identity/token
IP
operation
```

Do not use only IP because NAT/shared offices exist.

---

## 32. Backpressure

When saturated, reject/defer work instead of spawning unlimited work.

Use appropriately:

```text
429 rate limited
503 capacity unavailable
202 accepted async work
```

---

## 33. Worker Concurrency

Worker concurrency must be bounded according to:

- PostgreSQL pool;
- provider limits;
- CPU;
- RAM;
- network.

Never assume async means unlimited concurrency is safe.

Workers should claim bounded batches.

Use `FOR UPDATE SKIP LOCKED` where appropriate.

Claims must remain recoverable with leases and idempotency.

---

## 34. Retry Backoff

Use bounded exponential backoff with jitter.

Never synchronize retry storms.

Never retry indefinitely.

---

## 35. Idempotency Performance

Idempotency records must be indexed by canonical key:

```text
(store_id, operation, idempotency_key)
```

Lookup must be constant/index-driven.

Retention must prevent indefinite uncontrolled growth.

---

## 36. Transactional Outbox Performance

Worker query must match indexes.

Typical hot query:

```text
status = PENDING
available_at <= now
ORDER BY available_at, created_at
LIMIT N
```

Do not repeatedly scan historical `PUBLISHED` rows.

---

## 37. Provider Event Inbox

Webhook intake should be fast:

```text
raw signature verification
→ trusted store/integration resolution
→ durable dedupe insert
→ commit
→ ACK
```

Heavy processing runs asynchronously/idempotently.

Provider event dedupe remains DB-enforced.

---

## 38. Audit Log Performance

Audit logs grow continuously.

Do not load full audit history inside normal entity detail endpoints.

Expose dedicated cursor-paginated history endpoints.

Partition/archive only when measured volume warrants it.

---

## 39. Inventory Hot-Row Performance

Hot SKUs may create contention.

Correctness remains first.

Use:

- short transactions;
- atomic conditional updates;
- deterministic locks;
- minimal work under lock;
- no provider calls;
- proper indexes.

Do not shard inventory before measurement proves need.

---

## 40. Pricing and Discount Query Efficiency

One pricing pipeline must not become N queries per cart line.

Batch-load:

- product variants;
- price context;
- applicable discounts;
- tax context where possible.

Bad:

```text
for each cart line:
    query price
    query discounts
    query inventory
```

Prefer bounded batched queries/projections.

---

## 41. Checkout Performance

Checkout should persist/reuse bounded session snapshots such as:

- priced lines;
- selected shipping rate;
- expiry;
- version;
- pricing/context hash where useful.

Critical values are still revalidated at completion.

Do not call providers repeatedly when valid persisted quote/session data already exists.

---

## 42. Order Completion Performance

Keep completion transaction bounded.

For multi-line orders:

- deterministic inventory locking;
- bounded batch inserts;
- no network I/O;
- one transaction owner.

Do not split atomic order creation merely to improve benchmark numbers.

---

## 43. Webhook Burst Handling

Load-test provider event bursts including duplicates.

Measure:

- intake latency;
- dedupe;
- backlog;
- worker drain rate;
- DB connection use.

Correctness assertion:

```text
one provider event
→ one logical financial effect
```

even under duplicates.

---

## 44. File and Export Handling

Media:

```text
client
→ signed storage upload
```

not through FastAPI memory.

Exports:

```text
async job
→ streaming DB read
→ object storage result
→ signed download
```

Do not build huge exports fully in API memory.

---

## 45. Memory Safety

Avoid:

```text
query all million rows
full-table list()
giant JSON payload
whole CSV in RAM
all audit history
all provider events
```

Use streaming and chunks.

---

## 46. Logging Standards

Structured logs must be concise.

Do not log:

- passwords;
- access tokens;
- refresh tokens;
- payment secrets;
- full provider payloads by default;
- giant request bodies;
- full PII.

Expected business conflicts such as `OUT_OF_STOCK` are not application ERRORs.

---

## 47. Request/Trace IDs

Every request has one opaque request ID.

Propagate across:

- API logs;
- audit;
- outbox;
- provider operations;
- worker follow-up where useful.

Do not use request IDs as high-cardinality metric labels.

---

## 48. Observability

P0 operations should expose:

```text
duration
result
conflict type
DB time
provider time
retries
request_id in logs/traces
```

Monitor at minimum:

### API
- request rate;
- P50/P95/P99;
- 4xx/5xx.

### PostgreSQL
- connections;
- lock waits;
- deadlocks;
- long transactions;
- slow queries;
- cache hit ratio;
- bloat/autovacuum.

### Redis
- latency;
- hit/miss;
- memory;
- evictions;
- errors.

### Workers
- queue depth;
- processing duration;
- retry rate;
- dead state/backlog.

### Providers
- latency;
- timeout;
- 4xx/5xx;
- reconciliation backlog.

---

## 49. Slow Query Visibility

Enable safe slow-query visibility.

Capture query fingerprints rather than sensitive raw customer values.

A high-traffic endpoint with a sequential scan over a growing table must be investigated.

---

## 50. Load Testing

Required scenarios:

- catalog browse;
- product detail;
- cart mutations;
- checkout creation;
- hot SKU reservation;
- payment webhook burst;
- admin order list;
- outbox backlog.

Use representative data, not an empty database.

---

## 51. Hot SKU Load Test

Example:

```text
stock = 100
1000 concurrent reserve attempts
```

Expected:

```text
success <= 100
available never negative
no duplicate stock effect
```

Performance is measured after correctness passes.

---

## 52. Representative Dataset Testing

Performance staging should eventually include realistic sizes such as:

```text
10k+ products
100k+ variants
100k+ customers
500k+ orders
millions of order items/events/movements
```

Adjust based on client reality.

---

## 53. Stateless API Scaling

API instances should not depend on process-local canonical state.

Safe local state:

- immutable config;
- correctness-independent small caches.

Unsafe:

- sole cart;
- sole session registry;
- sole checkout lock;
- payment state.

Horizontal scaling becomes safe because canonical state is externalized to PostgreSQL/Redis.

---

## 54. Read Replicas

Do not introduce read replicas until measured need exists.

Never use potentially lagging replica for decisions requiring current truth:

- stock reserve;
- payment state before checkout completion;
- refund balance;
- immediate authorization change.

---

## 55. Partitioning

Do not partition core tables prematurely.

Later candidates may include:

- audit logs;
- outbox history;
- provider events;
- shipment events;
- notification deliveries.

Only after measured volume demonstrates need.

---

## 56. Migration Performance

Large production migrations should prefer expand/backfill/contract patterns.

Example:

```text
add nullable column
→ deploy compatible code
→ bounded backfill
→ validate
→ enforce constraint
```

Avoid one enormous backfill transaction.

For large indexes consider non-blocking/concurrent strategies when supported by migration policy.

---

## 57. Startup Standards

Application startup must not:

- run migrations automatically in every replica;
- scan entire database;
- load whole catalog;
- call every external provider;
- create per-request global clients.

Migrations are an explicit deployment step.

---

## 58. Dependency Lifetimes

Long-lived safely shared:

- SQLAlchemy engine/pool;
- Redis pool;
- async HTTP clients.

Request-scoped:

- Core connection/transaction scope;
- UoW;
- actor/store context.

Workers create their own Core connection/transaction scopes.

Never pass request connections or transactions into background worker jobs.

---

## 59. FastAPI BackgroundTasks

Do not use process-local FastAPI background tasks for durable critical work such as:

- payment reconciliation;
- outbox delivery;
- critical notifications;
- shipment creation;
- financial workflows.

Use durable workers/outbox.

---

## 60. Purposeful Denormalization

Canonical truth stays normalized.

Derived projections are allowed for performance, e.g.:

- customer order count;
- customer total spent;
- order payment summary;
- order fulfillment summary.

Every derived projection must be reconstructable from canonical records.

Do not make a convenience counter the only financial truth.

---

## 61. Avoid Race-Prone Counters

Bad:

```text
read counter
counter = counter + 1
write
```

Use atomic SQL or derive from ledger/history where required.

---

## 62. Search

Use PostgreSQL-based search initially where sufficient.

Potential tools:

- normalized indexed columns;
- trigram;
- PostgreSQL full text.

Do not introduce Elasticsearch/OpenSearch until actual search scale or quality requires it.

---

## 63. API Smoothness Standard

A smooth API means:

- predictable P95/P99;
- stable DTOs;
- bounded payloads;
- clear errors;
- safe retry behavior;
- no unnecessary synchronous provider dependency;
- no random N+1 spikes;
- no deep-page query collapse.

Requests-per-second alone does not define quality.

---

## 64. Security Cannot Be Optimized Away

Never remove/skip:

- password hashing strength;
- webhook signatures;
- RBAC;
- IDOR checks;
- store ownership;
- audit evidence;

for performance.

Optimize query strategy instead.

---

## 65. Architecture Scaling Stages

### Stage 1 — Initial clients

```text
FastAPI modular monolith
PostgreSQL
Redis
bounded workers
```

### Stage 2 — Higher traffic

```text
multiple stateless API replicas
CDN
stronger caching
worker scaling
PgBouncer if measured need
```

### Stage 3 — High volume

Potential after evidence:

```text
safe read replicas
selected table partitioning
specialized search
analytics pipeline
```

### Stage 4 — Service extraction

Extract a module only when justified by:

- independent scale profile;
- operational ownership;
- failure isolation;
- independent deployment needs.

Do not split because “microservices scale better.”

---

## 66. Forbidden Performance Anti-Patterns

### API

- unbounded list endpoints;
- deep OFFSET on growing tables;
- giant DTO graphs;
- synchronous heavy exports;
- provider HTTP inside DB transaction.

### Database

- FLOAT money;
- missing FK/index strategy;
- read-then-write stock;
- long idle transactions;
- giant all-or-nothing backfills;
- core relational truth hidden in JSONB.

### SQLAlchemy ORM (not the default architecture)

- relationship-driven persistence;
- hidden relationship loading;
- `SELECT *` for narrow list projections;
- one SQL statement per imported row.

### Redis

- Redis as sole stock/payment/order truth;
- `KEYS *` in production path;
- cache without TTL/invalidation.

### Workers

- unlimited concurrency;
- no claim lease;
- retry every exception;
- no max retries;
- no idempotency;
- giant unbounded batches.

### Providers

- no timeout;
- new HTTP client per call;
- blind retry after unknown timeout;
- provider-specific status leaking into domain model.

---

## 67. Database Definition of Done

For DB/repository work:

- [ ] valid PK/FK relationships;
- [ ] FK indexes reviewed;
- [ ] business uniqueness DB-backed;
- [ ] simple bounds protected by CHECK;
- [ ] money uses NUMERIC;
- [ ] migration tested;
- [ ] hot queries indexed;
- [ ] real PostgreSQL integration test;
- [ ] concurrency behavior verified where critical;
- [ ] no unnecessary JSONB.

---

## 68. API Definition of Done

For significant API endpoints:

- [ ] explicit DTO;
- [ ] authentication;
- [ ] authorization/ownership;
- [ ] bounded request;
- [ ] bounded response;
- [ ] stable error codes;
- [ ] cursor pagination when growing;
- [ ] idempotency when retry-prone;
- [ ] no N+1;
- [ ] transaction boundary known;
- [ ] outbound timeouts configured;
- [ ] query/index strategy reviewed.

---

## 69. Performance Definition of Done

For production-critical implementation:

- [ ] query count reviewed;
- [ ] indexes reviewed;
- [ ] all required data access is explicit in Core statements/query services;
- [ ] no blocking I/O in async path;
- [ ] DB transaction short;
- [ ] pool usage bounded;
- [ ] cache role explicit;
- [ ] worker concurrency bounded;
- [ ] metrics/logging present;
- [ ] relevant load/concurrency test passes;
- [ ] optimization did not weaken business invariants.

---

## 70. Codex Pre-Implementation Checklist

Before implementing a task, Codex must identify:

```text
transaction owner
expected DB queries
required constraints
required indexes
N+1 risk
cache role
external I/O boundary
concurrency risk
retry/idempotency rule
required performance/integration tests
```

If any P0 point is unclear, stop and report the documentation conflict instead of inventing behavior.

---

## 71. Codex Completion Evidence

For significant DB/API work, report:

```text
files changed
migration
tests
query patterns
indexes introduced/used
query-count evidence where relevant
concurrency evidence
provider timeout behavior
known performance risks
```

“Tests pass” alone is not enough evidence for a P0 commerce slice.

---

## 72. Production Performance Gate

Before the first production client:

- [ ] no known N+1 on P0 routes;
- [ ] critical query indexes reviewed;
- [ ] representative-data benchmark run;
- [ ] hot SKU load/race test passes;
- [ ] webhook burst test passes;
- [ ] DB pool saturation behavior observed;
- [ ] Redis outage behavior verified;
- [ ] provider timeout/reconciliation tested;
- [ ] API P95 baseline recorded;
- [ ] slow-query monitoring available;
- [ ] worker backlog metrics available.

---

## 73. Optimization Workflow

When an endpoint is slow:

```text
1. reproduce
2. measure trace
3. count DB queries
4. inspect EXPLAIN
5. identify DB/CPU/network/cache bottleneck
6. make smallest safe optimization
7. rerun correctness tests
8. benchmark again
9. add regression protection
```

Do not optimize from guesswork.

---

## 74. Final Engineering Freeze

Unless superseded by an accepted ADR:

```text
NO N+1 on production-critical endpoints
NO unbounded growing lists
NO deep OFFSET as default large-data pagination
NO provider HTTP under DB locks
NO shared transactional connection across concurrent operations
NO FLOAT money
NO Redis as canonical commerce truth
NO retry without idempotency/reconciliation
NO huge synchronous imports/exports
NO unlimited worker concurrency
NO outbound call without timeout
NO performance optimization that weakens commerce correctness
```

---

## 75. Final Goal

The LinkUp Commerce implementation should feel:

```text
fast to the customer
predictable to the frontend
safe to the merchant
boring to operate
easy to profile
easy to scale
hard to corrupt
```

The goal is not maximum architectural complexity.

The goal is the **minimum complexity required to remain fast, safe, scalable and understandable**.
