# LinkUp Commerce Engine — Repository & Runtime Architecture

**Document type:** Repository Architecture / Engineering Design / Codex Implementation Contract  
**Version:** v1.0  
**Date:** 2026-09-08  
**Target stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x async, PostgreSQL, Redis, Alembic, async workers  
**Deployment model:** One client store per VPS/database initially; one reusable LinkUp Commerce codebase; store-scoped design retained for future multi-store/SaaS evolution.  
**Architecture style:** Modular Monolith + layered domain modules + explicit Unit of Work + ports/adapters + transactional outbox.  
**Structural inspiration:** FYNEURA-X repository conventions, adapted and simplified for a dedicated e-commerce engine.

**Companion specifications**

- `docs/DB_SCHEMA.md` — physical/domain data architecture.
- `docs/API_ARCHITECTURE.md` — HTTP contracts, permissions, request/response behavior.
- `docs/BUSINESS_LOGIC.md` — domain invariants, pre/post conditions, state machines, failure behavior.
- `docs/TESTING_STRATEGY.md` — testing layers, gates, and required evidence.
- `AGENTS.md` — repository operating contract.
- `docs/implementation/IMPLEMENTATION_PLAN.md` — controlled execution sequence.

---

## 1. Purpose

This file defines **where code belongs, which module owns which behavior, how modules may communicate, who owns transactions, where database/provider code is allowed, and what architectural patterns Codex/developers must preserve**.

This document deliberately does **not** repeat the complete database schema, API catalogue or domain business rules.

Think of the documentation stack as:

```text
DB_SCHEMA.md
    = What data exists?

BUSINESS_LOGIC.md
    = How is the commerce system allowed to behave?

API_ARCHITECTURE.md
    = How do external/internal callers interact with it?

ARCHITECTURE.md
    = Where does each implementation responsibility live?

TESTING_STRATEGY.md
    = How do we prove that the implementation is correct?

AGENTS.md
    = What must Codex obey every time it works in this repository?
```

---

# 2. Architecture Decision

LinkUp Commerce SHALL begin as a **modular monolith**, not a microservice system.

```text
                    ┌────────────────────────┐
                    │     FastAPI Process     │
                    │   API / Composition     │
                    └───────────┬────────────┘
                                │
       ┌────────────────────────┼────────────────────────┐
       │                        │                        │
       ▼                        ▼                        ▼
   Catalog                  Checkout                Payments
   Inventory                Orders                  Fulfillment
   Customers                Promotions              Returns
       │                        │                        │
       └────────────────────────┼────────────────────────┘
                                │
                   Explicit in-process contracts
                                │
                    ┌───────────▼────────────┐
                    │ PostgreSQL / Redis      │
                    │ Workers / Providers     │
                    └─────────────────────────┘
```

### Why modular monolith first?

- LinkUp controls the backend and normally also builds the custom storefront.
- One client initially gets one deployment/database.
- Checkout/order/payment/inventory need strong transactional consistency.
- Operational complexity stays low.
- Codex can understand and modify the repository more reliably.
- Modules can later be extracted only when an actual scale/operational boundary exists.

### Do not create microservices because:

- a domain “looks important”;
- Shopify has distributed infrastructure;
- a queue already exists;
- a module has many tables.

A service extraction requires a documented ADR explaining the operational need, ownership, consistency model, failure mode, observability and migration path.

---

# 3. FYNEURA-X Pattern We Are Adopting

The clean pattern retained is:

```text
modules/<domain>/
├── presentation/
├── application/
├── domain/
└── infrastructure/
```

For LinkUp Commerce the meaning is:

| Layer | Responsibility | Framework dependency |
|---|---|---|
| `presentation` | HTTP routing, Pydantic request/response schemas, auth/dependencies, HTTP error mapping | FastAPI/Pydantic allowed |
| `application` | Commands, queries, use cases, orchestration, transaction ownership, application ports | Framework-light |
| `domain` | Pure business rules, entities/value objects, policies, transitions, domain exceptions/events | **No FastAPI/SQLAlchemy/Redis/provider imports** |
| `infrastructure` | SQLAlchemy models, repositories, UoW implementation, Redis, provider adapters, query services | Infrastructure libraries allowed |

## Important LinkUp adaptation

Avoid large generic files such as:

```text
commands.py
queries.py
repositories.py
schemas.py
```

growing indefinitely.

Prefer:

```text
application/
├── commands/
│   ├── create_product.py
│   ├── publish_product.py
│   └── archive_product.py
├── queries/
│   ├── get_product.py
│   └── list_products.py
└── ports/
    ├── product_repository.py
    └── media_storage.py
```

This is intentionally optimized for:

- Codex task scoping;
- smaller diffs;
- code review;
- ownership clarity;
- test discoverability;
- avoiding “god files”.

---

# 4. Proposed Repository Structure

```text
linkup-commerce/
│
├── AGENTS.md                         # Codex operating contract
├── ARCHITECTURE.md                   # this document
├── README.md
├── Makefile
├── pyproject.toml
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .dockerignore
│
├── app/                              # process/bootstrap/composition layer
│   ├── __init__.py
│   ├── main.py                       # create FastAPI app
│   ├── bootstrap.py                  # dependency/provider wiring
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py                 # mounts all API surfaces
│   │   ├── errors.py                 # global HTTP error envelope
│   │   └── v1/
│   │       ├── storefront.py         # aggregate storefront module routers
│   │       ├── admin.py              # aggregate admin module routers
│   │       ├── auth.py
│   │       ├── webhooks.py
│   │       └── internal.py
│   │
│   ├── core/
│   │   ├── config.py                 # pydantic-settings
│   │   ├── security.py
│   │   ├── request_context.py
│   │   ├── correlation.py
│   │   ├── logging.py
│   │   ├── errors.py
│   │   ├── pagination.py
│   │   ├── idempotency.py            # shared command infrastructure contract
│   │   ├── rate_limit.py
│   │   └── constants.py
│   │
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   ├── metadata.py               # imports module ORM metadata
│   │   └── types.py                  # shared DB types only
│   │
│   ├── cache/
│   │   ├── redis.py
│   │   ├── keys.py
│   │   └── serialization.py
│   │
│   ├── events/
│   │   ├── envelope.py
│   │   ├── registry.py
│   │   └── dispatcher.py
│   │
│   ├── workers/
│   │   ├── app.py
│   │   ├── outbox.py
│   │   ├── checkout_expiry.py
│   │   ├── notifications.py
│   │   ├── webhooks.py
│   │   ├── bulk_jobs.py
│   │   └── reconciliation.py
│   │
│   └── observability/
│       ├── metrics.py
│       ├── tracing.py
│       └── health.py
│
├── modules/
│   ├── __init__.py
│   ├── store/
│   ├── iam/
│   ├── customers/
│   ├── catalog/
│   ├── pricing/
│   ├── promotions/
│   ├── inventory/
│   ├── cart/
│   ├── checkout/
│   ├── orders/
│   ├── payments/
│   ├── fulfillment/
│   ├── returns/
│   ├── cms/
│   ├── notifications/
│   ├── integrations/
│   ├── audit/
│   └── bulk/
│
├── shared/                            # tiny framework-free shared primitives
│   ├── __init__.py
│   ├── domain/
│   │   ├── money.py
│   │   ├── ids.py
│   │   ├── clock.py
│   │   ├── result.py
│   │   └── exceptions.py
│   └── application/
│       ├── command.py
│       ├── query.py
│       └── unit_of_work.py
│
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── tests/
│   ├── unit/
│   │   └── modules/
│   ├── integration/
│   │   └── modules/
│   ├── contract/
│   ├── concurrency/
│   ├── providers/
│   ├── e2e/
│   ├── factories/
│   ├── fixtures/
│   └── conftest.py
│
├── docs/
│   ├── DB_SCHEMA.md
│   ├── API_ARCHITECTURE.md
│   ├── BUSINESS_LOGIC.md
│   ├── TESTING_STRATEGY.md
│   ├── SECURITY.md
│   ├── STATUS.md
│   │
│   ├── adr/
│   │   └── ADR-*.md
│   │
│   └── implementation/
│       ├── IMPLEMENTATION_PLAN.md
│       └── phases/
│
├── scripts/
│   ├── seed.py
│   ├── create_admin.py
│   ├── healthcheck.py
│   └── validate_openapi.py
│
└── deploy/
    ├── nginx/
    ├── docker/
    ├── systemd/                       # optional if worker/process manager uses it
    └── monitoring/
```

---

# 5. Canonical Module Template

Every normal business module should start with this shape:

```text
modules/<domain>/
│
├── __init__.py
│
├── presentation/
│   └── http/
│       ├── __init__.py
│       ├── router.py
│       ├── deps.py
│       ├── errors.py
│       │
│       ├── schemas/
│       │   ├── requests.py
│       │   ├── responses.py
│       │   └── common.py
│       │
│       └── routes/
│           ├── storefront.py
│           ├── admin.py
│           ├── webhooks.py            # only when this domain receives them
│           └── internal.py            # only when truly required
│
├── application/
│   ├── __init__.py
│   │
│   ├── commands/
│   │   ├── __init__.py
│   │   └── <one_use_case>.py
│   │
│   ├── queries/
│   │   ├── __init__.py
│   │   └── <one_query>.py
│   │
│   ├── dto/
│   │   ├── inputs.py
│   │   └── outputs.py
│   │
│   ├── ports/
│   │   ├── repositories.py
│   │   ├── providers.py
│   │   └── services.py
│   │
│   └── services/
│       └── <application_orchestrator>.py
│
├── domain/
│   ├── __init__.py
│   ├── entities.py
│   ├── value_objects.py
│   ├── enums.py
│   ├── events.py
│   ├── exceptions.py
│   ├── policies.py
│   └── services.py                    # pure domain service only
│
└── infrastructure/
    ├── __init__.py
    │
    ├── db/
    │   ├── models.py
    │   ├── repositories.py
    │   ├── query_services.py
    │   └── uow.py
    │
    ├── cache/
    │   └── repository.py              # only when module owns cached projection
    │
    └── providers/
        └── <provider_adapter>.py
```

Not every empty folder must be created on day one.

**Rule:** create a directory/file only when the module has an actual implementation responsibility for it.

---

# 6. Layer Dependency Rule

Allowed dependency direction:

```text
presentation
     │
     ▼
application
     │
     ▼
domain

infrastructure
     │
     ├──── implements application ports
     └──── maps persistence/provider data
```

Composition root (`app/bootstrap.py`) wires infrastructure into application ports.

### Allowed imports

```text
presentation → application
presentation → domain types (sparingly, mainly enums/read-only types)

application → domain
application → application ports
application → shared primitives

infrastructure → domain
infrastructure → application ports/DTO contracts
infrastructure → shared infrastructure primitives where explicitly allowed

app/bootstrap → everything required for dependency wiring
```

### Forbidden imports

```text
domain → FastAPI
domain → SQLAlchemy
domain → Redis client
domain → Razorpay/Stripe/Shiprocket SDK
domain → infrastructure

application → concrete SQLAlchemy repository
application → provider SDK
application → FastAPI Request/Response

repository → FastAPI
provider adapter → HTTP route
```

---

# 7. Module Ownership Matrix

| Module | Canonical ownership | Does NOT own |
|---|---|---|
| `store` | store identity, settings, domains, sales channels | staff authentication, product stock |
| `iam` | merchant/staff identity, sessions, RBAC | shopper/customer profile |
| `customers` | shopper profile, saved address, consent | order address snapshot |
| `catalog` | products, variants, options, media, collections, metafields | inventory count, order price history |
| `pricing` | market/catalog/price-list context and authoritative price selection | discount redemption, payment |
| `promotions` | discount definitions, eligibility, coupon codes, redemption ledger | final checkout orchestration |
| `inventory` | locations, stock levels, reservations, movements, transfers | product merchandising |
| `cart` | durable shopping intent | inventory reservation, final payment |
| `checkout` | short-lived orchestration session | permanent financial or order ledger |
| `orders` | immutable commercial order snapshot + lifecycle | gateway transactions, shipment provider state |
| `payments` | payment intents, transactions, provider inbox, refunds | inventory |
| `fulfillment` | allocations, shipments, tracking, NDR, COD reconciliation | catalog availability |
| `returns` | return eligibility/workflow/received disposition | payment ledger itself |
| `cms` | pages, blog, navigation, SEO, redirects | executable storefront theme |
| `notifications` | templates, delivery attempts | order state |
| `integrations` | provider config, outbound webhook subscriptions/deliveries | canonical business truth |
| `audit` | append-only privileged/security evidence | domain state |
| `bulk` | large job lifecycle/progress/item results | underlying catalog/inventory rules |

The owning module is the only module allowed to mutate its canonical state.

---

# 8. Cross-Module Communication Rules

## 8.1 Never mutate another module's ORM rows

Wrong:

```python
# checkout application code
inventory_level.reserved += qty
payment.status = "PAID"
order.status = "CONFIRMED"
```

Correct:

```text
Checkout application use case
    ↓
Inventory application port/command
    ↓
Inventory owns reservation transition

Checkout application use case
    ↓
Payments read contract
    ↓
Payments owns financial truth

Checkout application use case
    ↓
Orders create-order command
    ↓
Orders owns order snapshot
```

## 8.2 In-process command/query contracts first

Internal module communication should normally use Python application contracts:

```python
await inventory.reserve(...)
await payments.get_authoritative_state(...)
await orders.create_from_checkout(...)
```

Do **not** call your own FastAPI endpoints over HTTP.

## 8.3 Events for post-commit side effects

Use events when the consumer does not need to participate atomically:

```text
order.created
    ├── notifications
    ├── ERP outbound webhook
    ├── analytics
    └── operational automation
```

## 8.4 One transaction owner

A cross-module workflow must name one application use case as transaction owner.

Example:

```text
CompleteCheckoutUseCase
    = transaction owner

Inside UoW:
- revalidate checkout
- claim idempotency
- create order snapshots
- consume ACTIVE inventory reservation
- commit discount redemption
- write outbox

Outside UoW:
- notifications
- outbound webhooks
```

---

# 9. Application Layer Design

Application layer is the **use-case layer**.

It owns:

- command/query orchestration;
- transaction boundaries;
- authorization facts already resolved by presentation/auth layer;
- idempotency orchestration;
- calls to module ports;
- converting domain exceptions into application outcomes;
- coordinating multiple domain aggregates when necessary.

It does NOT own:

- FastAPI request objects;
- SQLAlchemy ORM traversal;
- provider-specific JSON;
- arbitrary business rules that belong in the domain layer.

## Command naming

Use imperative business names:

```text
CreateProduct
PublishProduct
ReserveInventory
ReleaseReservation
CompleteCheckout
CancelOrder
CreatePaymentIntent
ProcessPaymentProviderEvent
CreateRefund
CreateFulfillment
ReceiveReturn
```

Avoid vague names:

```text
ProcessData
UpdateStuff
HandleRequest
SaveOrder
ServiceManager
```

---

# 10. Domain Layer Design

The domain layer is framework-free.

Example:

```text
modules/inventory/domain/
├── entities.py
├── value_objects.py
├── enums.py
├── policies.py
├── events.py
├── exceptions.py
└── services.py
```

Good domain rules:

```python
reservation.can_release()
order.can_cancel()
refund_amount = refund_policy.calculate(...)
promotion_result = discount_policy.evaluate(...)
shipment.transition_to(...)
```

Domain objects may return facts/events, but must not:

```python
await db.execute(...)
await redis.get(...)
requests.post(...)
raise HTTPException(...)
```

### Domain exception examples

```text
OutOfStock
InvalidStateTransition
RefundExceedsAvailable
CheckoutExpired
DiscountNotEligible
ReturnQuantityExceeded
FulfillmentQuantityExceeded
```

Presentation maps those to HTTP codes defined in `docs/API_ARCHITECTURE.md`.

---

# 11. Infrastructure Layer Design

Infrastructure contains technology-specific implementations.

Examples:

```text
infrastructure/db/models.py
    SQLAlchemy mappings

infrastructure/db/repositories.py
    writes / aggregate persistence

infrastructure/db/query_services.py
    optimized read projections

infrastructure/db/uow.py
    SQLAlchemy transaction implementation

infrastructure/providers/razorpay.py
    provider adapter
```

### Important distinction

**Repository** is for canonical aggregate persistence.

**Query service** is for optimized reads/projections.

Do not force a storefront product listing through a huge aggregate graph if a bounded SQL projection is clearer and safer.

---

# 12. Example — Catalog Module

```text
modules/catalog/
├── presentation/http/
│   ├── router.py
│   ├── deps.py
│   ├── errors.py
│   ├── schemas/
│   │   ├── product_requests.py
│   │   ├── product_responses.py
│   │   ├── variant_requests.py
│   │   └── collection_responses.py
│   └── routes/
│       ├── storefront_products.py
│       ├── admin_products.py
│       ├── admin_variants.py
│       ├── admin_collections.py
│       └── admin_media.py
│
├── application/
│   ├── commands/
│   │   ├── create_product.py
│   │   ├── update_product.py
│   │   ├── publish_product.py
│   │   ├── archive_product.py
│   │   ├── create_variant.py
│   │   └── attach_media.py
│   ├── queries/
│   │   ├── get_product.py
│   │   ├── list_storefront_products.py
│   │   └── list_admin_products.py
│   └── ports/
│       ├── product_repository.py
│       ├── product_queries.py
│       └── media_storage.py
│
├── domain/
│   ├── entities.py
│   ├── value_objects.py
│   ├── enums.py
│   ├── policies.py
│   ├── events.py
│   └── exceptions.py
│
└── infrastructure/
    ├── db/
    │   ├── models.py
    │   ├── repositories.py
    │   └── query_services.py
    └── providers/
        └── object_storage.py
```

---

# 13. Example — Inventory Module

Inventory is concurrency-sensitive, so it gets explicit command files.

```text
modules/inventory/
├── application/
│   ├── commands/
│   │   ├── reserve.py
│   │   ├── release_reservation.py
│   │   ├── commit_reservation.py
│   │   ├── adjust_stock.py
│   │   ├── reconcile_stock.py
│   │   ├── create_transfer.py
│   │   ├── ship_transfer.py
│   │   └── receive_transfer.py
│   └── ports/
│       └── inventory_repository.py
│
├── domain/
│   ├── reservation.py
│   ├── movement.py
│   ├── transfer.py
│   ├── policies.py
│   ├── enums.py
│   └── exceptions.py
│
└── infrastructure/db/
    ├── models.py
    ├── repositories.py
    ├── atomic_reservation.py
    ├── query_services.py
    └── uow.py
```

`atomic_reservation.py` is allowed to contain PostgreSQL-specific locking/conditional SQL because race safety is an infrastructure responsibility implementing an application port.

---

# 14. Example — Checkout Module

Checkout is an orchestrator.

```text
modules/checkout/
├── application/
│   ├── commands/
│   │   ├── create_checkout.py
│   │   ├── set_shipping_address.py
│   │   ├── quote_shipping.py
│   │   ├── select_shipping_rate.py
│   │   ├── reserve_inventory.py
│   │   ├── create_payment_session.py
│   │   ├── complete_checkout.py
│   │   └── expire_checkout.py
│   │
│   ├── ports/
│   │   ├── checkout_repository.py
│   │   ├── pricing_port.py
│   │   ├── inventory_port.py
│   │   ├── payments_port.py
│   │   ├── orders_port.py
│   │   ├── promotions_port.py
│   │   └── shipping_quote_port.py
│   │
│   └── services/
│       └── pricing_pipeline.py
│
├── domain/
│   ├── checkout.py
│   ├── states.py
│   ├── policies.py
│   ├── events.py
│   └── exceptions.py
│
└── infrastructure/
    └── db/
        ├── models.py
        ├── repositories.py
        └── query_services.py
```

### Checkout module does not directly import:

```text
modules.inventory.infrastructure.*
modules.payments.infrastructure.*
modules.orders.infrastructure.*
```

It depends on application-level ports/contracts wired by the composition root.

---

# 15. Example — Payments Module

```text
modules/payments/
├── presentation/http/
│   ├── routes/
│   │   ├── admin.py
│   │   ├── storefront.py
│   │   └── webhooks.py
│   └── schemas/
│       ├── refund.py
│       └── webhook.py
│
├── application/
│   ├── commands/
│   │   ├── create_intent.py
│   │   ├── create_provider_session.py
│   │   ├── ingest_provider_event.py
│   │   ├── process_provider_event.py
│   │   ├── capture.py
│   │   ├── void.py
│   │   ├── request_refund.py
│   │   ├── process_refund.py
│   │   └── record_offline_payment.py
│   └── ports/
│       ├── payment_repository.py
│       ├── payment_gateway.py
│       └── payment_queries.py
│
├── domain/
│   ├── payment_intent.py
│   ├── transaction.py
│   ├── refund.py
│   ├── states.py
│   ├── policies.py
│   └── exceptions.py
│
└── infrastructure/
    ├── db/
    │   ├── models.py
    │   ├── repositories.py
    │   └── query_services.py
    └── providers/
        ├── razorpay.py
        └── stripe.py
```

Core business code sees:

```python
PaymentGatewayPort
```

not:

```python
razorpay.Client(...)
```

---

# 16. Unit of Work & Transaction Architecture

Use explicit Unit of Work for state-changing application commands.

Conceptual interface:

```python
class UnitOfWork(Protocol):
    async def __aenter__(self): ...
    async def __aexit__(self, exc_type, exc, tb): ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

Command:

```text
CompleteCheckout
    ↓
async with uow:
    claim idempotency
    validate state
    create order
    consume reservation
    write outbox
    commit
```

### Transaction rules

1. Application use case owns commit/rollback.
2. Repositories never call `commit()` themselves.
3. Nested repositories participate in the current transaction/session.
4. External HTTP calls are outside the transaction.
5. Lock order is deterministic for concurrency-critical commands.
6. Transaction is short and bounded.
7. Outbox/audit rows may be part of the same transaction.
8. Read-only projection queries do not need an artificial UoW unless consistency requires it.

---

# 17. SQLAlchemy Architecture

Use:

```text
SQLAlchemy 2.x
AsyncSession
Mapped[]
mapped_column()
explicit indexes/constraints
```

## Rules

- ORM models live inside the owning module's `infrastructure/db`.
- `app/db/metadata.py` imports all module ORM mappings for Alembic discovery.
- Do not place every application's models into one giant `app/models.py`.
- Foreign keys may exist across module tables where the DB requires integrity.
- A foreign key does **not** grant the foreign module permission to mutate the referenced module.
- Prefer explicit loading/projection queries.
- Configure relationships to avoid accidental N+1; `lazy="raise"` is preferred on risky relationships.
- Use `SELECT ... FOR UPDATE` or atomic SQL only where the business contention model requires it.
- Add indexes from actual API/query shapes described in the schema/API docs.

---

# 18. Repository vs Query Service

## Repository

Used by commands/business transitions:

```text
get_for_update()
add()
save()
find_by_idempotency_key()
reserve_atomic()
```

Repository methods should reflect domain intent.

Bad:

```python
repository.update_any_columns(id, payload)
```

Good:

```python
repository.save_product(product)
repository.lock_reservation(id)
repository.append_transaction(tx)
```

## Query service

Used for list/detail/report projections:

```text
list_storefront_products()
search_admin_orders()
get_customer_order_detail()
list_inventory_levels()
```

Query services can join multiple read-only tables when necessary, but:

- do not become a new source of truth;
- do not mutate state;
- still enforce store/ownership filters;
- select only needed columns;
- paginate unbounded results.

---

# 19. Redis Architecture

PostgreSQL remains canonical truth.

Redis is for:

- product/catalog hot cache;
- computed public storefront cache;
- rate limits;
- short authorization cache;
- distributed coordination only where accepted;
- worker broker if Celery/RQ chosen;
- ephemeral dedupe/performance helpers.

Redis is **not** the sole source of truth for:

- cart;
- inventory reservation;
- payment state;
- orders;
- refunds;
- staff membership.

Suggested key naming:

```text
lc:{env}:{store_id}:product:{product_id}:v{version}
lc:{env}:{store_id}:collection:{collection_id}:v{version}
lc:{env}:{store_id}:cart:{cart_id}:v{version}
lc:{env}:{store_id}:authz:{staff_id}:v{permission_version}
lc:{env}:ratelimit:{surface}:{subject}:{bucket}
```

### Cache rules

- cache key is namespaced by environment and store;
- TTL always exists unless explicitly justified;
- invalidation occurs after DB commit;
- stale/missing cache falls back to DB;
- never cache plaintext secrets/tokens;
- serialization is version-aware.

---

# 20. Event / Outbox Architecture

Domain/application mutation:

```text
Order creation transaction
├── orders
├── order_items
├── inventory commit
└── outbox_event(order.created)
        ↓ COMMIT
Outbox worker
├── notification
├── integration webhook
└── analytics
```

Standard event envelope:

```json
{
  "event_id": "uuid",
  "event_type": "order.created",
  "event_version": 1,
  "store_id": "uuid",
  "aggregate_type": "order",
  "aggregate_id": "uuid",
  "occurred_at": "UTC timestamp",
  "request_id": "req_xxx",
  "payload": {}
}
```

### Event rules

- past event payload versions remain understandable or migrate deliberately;
- consumer is idempotent by `event_id`;
- events contain stable business facts, not ORM objects;
- do not leak provider secrets;
- `processed_at` means delivery/dispatch contract satisfied, not merely “worker saw row”;
- retry/backoff/terminal failure is observable.

---

# 21. Idempotency Architecture

Shared implementation belongs in platform/core + persistence infrastructure, but ownership remains with the command.

Conceptual flow:

```text
HTTP request
    ↓
Idempotency-Key
    ↓
Application command
    ↓
atomic claim in DB
    ├── NEW → execute
    ├── SAME REQUEST + SUCCEEDED → replay response/resource
    ├── SAME KEY + DIFFERENT HASH → 409
    └── IN_PROGRESS → command-specific wait/conflict/recovery policy
```

Use for:

- checkout complete;
- refund create;
- draft order complete;
- provider session creation internally;
- shipment creation internally;
- reserve/release/commit internally;
- webhook event acceptance through external event IDs.

Do not apply generic idempotency middleware blindly to every POST without command-specific semantics.

---

# 22. Provider Adapter Architecture

External vendors are replaceable adapters.

```text
Application Port
      │
      ▼
PaymentGateway
├── RazorpayAdapter
└── StripeAdapter

ShippingProvider
├── ShiprocketAdapter
└── DelhiveryAdapter
```

Port DTO:

```text
CreatePaymentSessionInput
PaymentSessionResult
RefundRequest
RefundResult
ShippingQuoteRequest
ShipmentCreateResult
```

Provider adapter owns:

- provider SDK/HTTP API;
- provider authentication;
- request signing;
- timeouts;
- provider retry/idempotency headers;
- mapping provider response/errors to typed adapter result;
- safe logging.

Provider adapter does **not** own:

- order state;
- inventory state;
- refund eligibility;
- business permission;
- final status transition.

---

# 23. Incoming Webhook Architecture

Route responsibility:

```text
raw HTTP body
→ provider authentication/signature verification
→ minimal schema extraction
→ durable provider-event inbox/dedupe
→ quick HTTP ACK
→ async/application processing
```

Do not:

```text
webhook route
→ update order row directly
→ send email
→ call fulfillment provider
→ return after 10 seconds
```

Webhook processing belongs in an application command/worker.

---

# 24. HTTP Presentation Architecture

Each module mounts route groups into the root API surfaces.

Example:

```text
/api/v1/storefront/products
/api/v1/admin/products
/api/v1/webhooks/payments/razorpay
/api/v1/internal/inventory/reserve
```

Root:

```python
app.include_router(storefront_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(webhook_router)
app.include_router(internal_router)
```

Module:

```python
catalog_router.include_router(storefront_products_router)
catalog_router.include_router(admin_products_router)
```

### Route responsibility

Routes should be thin:

```text
parse request
→ authenticate/permission dependency
→ map request schema to command/query input
→ invoke application use case
→ map result to response schema
```

Routes do not contain:

- raw SQL;
- domain calculations;
- gateway SDK calls;
- long transaction orchestration.

---

# 25. Pydantic Schema Rules

Presentation schemas are API contracts.

Use separate request/response schemas when semantics differ.

Example:

```text
CreateProductRequest
UpdateProductRequest
ProductAdminResponse
ProductStorefrontResponse
```

Do not return ORM objects directly.

Sensitive write DTOs should reject unknown fields:

```python
model_config = ConfigDict(extra="forbid")
```

### Money

API:

```json
{
  "amount": "1999.00",
  "currency": "INR"
}
```

Python:

```python
Decimal("1999.00")
```

DB:

```text
NUMERIC(19,4)
```

---

# 26. Error Architecture

Domain:

```text
OutOfStock
InvalidStateTransition
RefundExceedsAvailable
```

Application:

```text
business result / propagated domain exception
```

Presentation mapping:

```text
OutOfStock            → 409 OUT_OF_STOCK
CheckoutExpired       → 410 CHECKOUT_EXPIRED
PermissionDenied      → 403 PERMISSION_DENIED
ResourceNotFound      → 404 RESOURCE_NOT_FOUND
```

Global response:

```json
{
  "error": {
    "code": "OUT_OF_STOCK",
    "message": "Requested quantity is unavailable",
    "details": []
  },
  "meta": {
    "request_id": "req_..."
  }
}
```

Never expose:

- SQL exceptions;
- stack traces;
- provider secrets;
- raw HTTP provider errors;
- internal table/column names unless explicitly safe.

---

# 27. Authentication & Authorization Architecture

Merchant/staff:

```text
Bearer access token
    ↓
IAM authentication dependency
    ↓
active session/user
    ↓
active store membership
    ↓
effective permissions
    ↓
application command
```

Customer:

```text
Customer JWT / guest opaque token
    ↓
ownership resolver
    ↓
store/customer/cart/order scope
```

Rules:

- permission is checked for every protected admin command;
- service/application use cases that can be invoked from multiple surfaces should receive an explicit actor/context object;
- store ID in request body is never authorization;
- customer URL ID never expands ownership;
- high-risk permissions are separated from general writes.

Suggested application context:

```python
@dataclass(frozen=True)
class ActorContext:
    request_id: str
    store_id: UUID
    actor_type: ActorType
    actor_id: UUID | None
    permissions: frozenset[str]
```

---

# 28. Request Context & Correlation

Every inbound request gets:

```text
request_id
correlation_id
store_id (when resolved)
actor/session id (when authenticated)
surface
route
```

Pass `request_id` into:

- logs;
- outbox events;
- audit records;
- external provider metadata where safe;
- worker correlation.

Do not pass entire FastAPI `Request` into domain/application layers just to access context.

---

# 29. Configuration Architecture

Use `pydantic-settings`.

```text
app/core/config.py
```

Configuration categories:

```text
AppSettings
DatabaseSettings
RedisSettings
JWTSettings
StorageSettings
ObservabilitySettings
WorkerSettings
ProviderSettings
```

Environment is the source for deployment secrets/config.

### Never commit:

- DB passwords;
- JWT signing secrets;
- Razorpay/Stripe secrets;
- SMTP/API keys;
- webhook signing secrets.

`.env.example` contains only fake/placeholding values and documentation.

Merchant-configurable provider credentials should be stored encrypted/secret-managed according to the integration design, never exposed as normal GET data.

---

# 30. Migration Architecture

Alembic is mandatory for persistent schema changes.

```text
migrations/versions/
    20260908_001_create_store_foundation.py
    20260908_002_create_iam.py
    ...
```

Rules:

1. ORM change and migration ship together.
2. Review autogenerated migration manually.
3. Already deployed migration is not edited; create a new migration.
4. Data migration is explicit and reversible where practical.
5. Destructive migrations require backup/rollback plan.
6. Add constraints/indexes deliberately.
7. Production deploy runs migrations before exposing code requiring the new schema.
8. Large table backfills use phased migrations to avoid long locks.
9. Seed/demo data is not embedded in schema migration unless it is true system reference data.

---

# 31. Worker Architecture

Do not make workers a second unstructured backend.

Worker entry points:

```text
app/workers/
```

Worker handler should call the same application use cases/contracts as HTTP paths where applicable.

Example:

```text
OutboxWorker
    ↓
Notification application service
    ↓
Notification provider adapter
```

Not:

```text
worker.py
    ↓
raw UPDATE many tables
```

### Scheduled jobs

- checkout/reservation expiry;
- outbox dispatch;
- notification retries;
- webhook retries;
- provider reconciliation;
- bulk jobs;
- scheduled CMS publishing;
- stale idempotency recovery/housekeeping.

All jobs require:

- bounded batch size;
- safe claiming/lease or `SKIP LOCKED`;
- idempotent handler;
- retry/backoff;
- terminal failure visibility;
- metrics.

---

# 32. Bulk Job Architecture

Large operations:

```text
upload/import request
    ↓
signed object storage upload
    ↓
bulk_job QUEUED
    ↓
worker streams file
    ↓
bounded batches
    ↓
normal domain commands/rules
    ↓
item errors/checkpoint
    ↓
COMPLETED/PARTIAL/FAILED
```

Bulk import must not bypass:

- SKU uniqueness;
- price validation;
- permission;
- inventory rules;
- audit rules.

Bulk mode may optimize batching, but cannot weaken domain invariants.

---

# 33. Media / Object Storage Architecture

Flow:

```text
Admin API requests upload session
    ↓
backend validates filename/type/size
    ↓
short-lived signed upload URL
    ↓
client uploads directly to object storage
    ↓
complete callback
    ↓
backend validates object metadata/checksum
    ↓
media READY
    ↓
image processing/CDN worker
```

API process should not proxy large media into application memory.

---

# 34. Search Architecture

## Phase 1

Use PostgreSQL:

- indexed filters;
- trigram/full-text where useful;
- bounded search;
- query service.

## Phase 2

Introduce OpenSearch/Elasticsearch only when real requirements justify it.

Search index is a **projection**, not canonical catalog truth.

```text
product.updated
    ↓
outbox
    ↓
search indexing worker
```

If search is down, admin/catalog DB operations remain durable.

---

# 35. Observability Architecture

Structured logs:

```json
{
  "timestamp": "...",
  "level": "INFO",
  "request_id": "req_...",
  "store_id": "...",
  "actor_id": "...",
  "module": "checkout",
  "operation": "complete_checkout",
  "duration_ms": 42,
  "outcome": "success"
}
```

Do not log:

- passwords;
- refresh/access tokens;
- OTP;
- raw card details;
- provider secret;
- unredacted authorization headers.

### Metrics

At minimum:

```text
HTTP latency P50/P95/P99
5xx rate
checkout created/completed
checkout conversion
inventory reserve conflict
payment success/failure
webhook backlog age
outbox backlog age
worker retry/failure
shipping provider errors
refund failure
bulk job failure
```

### Tracing

Trace:

```text
HTTP request
→ application command
→ DB transaction
→ provider call
→ outbox/worker continuation where trace propagation is supported
```

---

# 36. Health Architecture

Recommended:

```text
GET /health/live
GET /health/ready
```

`live`:

- process event loop alive.

`ready`:

- database reachable;
- critical bootstrap configuration loaded;
- optionally Redis depending on whether API can safely serve without it.

Do not make readiness depend on every optional vendor being up.

If Razorpay or Shiprocket is unavailable, API process may still be healthy while the provider circuit/metrics show degradation.

---

# 37. Deployment Architecture — Current LinkUp Business Model

Each client deployment:

```text
                           Internet
                              │
                         Nginx / TLS
                              │
                   ┌──────────▼──────────┐
                   │ LinkUp Commerce API  │
                   │ FastAPI replicas     │
                   └───────┬─────────────┘
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
     PostgreSQL          Redis            Workers
          │                                  │
          │                                  ├── notifications
          │                                  ├── outbox
          │                                  ├── webhooks
          │                                  └── bulk/reconcile
          │
          ▼
      Backups/PITR

Object Storage / CDN
Payment Providers
Shipping Providers
Email/SMS Provider
        = external services
```

### Initial VPS recommendation

Processes can begin as:

```text
nginx
api
worker
scheduler
postgres     # or managed DB when budget/criticality justifies
redis
```

Production preference over time:

```text
managed PostgreSQL
managed Redis
object storage
independent backup
```

Do not copy the full VPS as the only backup strategy.

---

# 38. One Client Per Deployment, Store-Scoped Internally

Current:

```text
Client A VPS
└── store_id=A
    └── DB A

Client B VPS
└── store_id=B
    └── DB B
```

Future SaaS:

```text
Shared platform
├── store_id=A
├── store_id=B
└── store_id=C
```

The internal store scope remains because it gives:

- clean ownership;
- unique constraints like `(store_id, sku)`;
- future migration path;
- safer test isolation;
- reusable APIs.

But initial runtime does **not** need complex SaaS tenant routing, billing or noisy-neighbor infrastructure.

---

# 39. Dependency Injection / Composition Root

Use explicit composition from:

```text
app/bootstrap.py
```

Example conceptual wiring:

```python
inventory_repo = SqlAlchemyInventoryRepository(session)
inventory_uow = SqlAlchemyInventoryUoW(session_factory)

payment_gateway = RazorpayAdapter(settings.razorpay)

complete_checkout = CompleteCheckout(
    checkout_repo=...,
    inventory=InventoryApplicationAdapter(...),
    payments=PaymentsApplicationAdapter(...),
    orders=OrdersApplicationAdapter(...),
    promotions=PromotionsApplicationAdapter(...),
    idempotency=...,
    uow=...
)
```

Do not instantiate provider SDKs randomly inside routes/use cases.

Dependency wiring may use FastAPI `Depends` at presentation level, but domain/application contracts remain testable without FastAPI.

---

# 40. Internal Application Adapters

When one module calls another, use a narrow adapter/port instead of importing foreign internals.

Example:

```text
checkout/application/ports/inventory_port.py

class InventoryPort(Protocol):
    async def reserve_checkout(...)
    async def release_checkout(...)
    async def commit_order(...)
```

Implementation:

```text
modules/checkout/infrastructure?   NO

Prefer composition adapter:
app/adapters/inventory_for_checkout.py
or public application facade:
modules/inventory/application/facade.py
```

Recommended convention for LinkUp:

```text
modules/<domain>/application/facade.py
```

Expose only stable in-process operations intended for other modules.

Other modules may import:

```python
from modules.inventory.application.facade import InventoryFacade
```

They must not import:

```python
from modules.inventory.infrastructure.db.models import InventoryLevelModel
```

---

# 41. Facade Rule

Each high-value module may expose a small application facade:

```text
inventory/application/facade.py
payments/application/facade.py
orders/application/facade.py
pricing/application/facade.py
promotions/application/facade.py
```

Facade:

- hides internal command wiring;
- gives stable typed contracts;
- simplifies Codex comprehension;
- avoids cross-module deep imports.

Do not turn facade into a god service.

---

# 42. Shared Code Policy

`shared/` must remain small.

Allowed:

- Money value type;
- identifier primitives;
- clock abstraction;
- base application protocol;
- generic pagination value objects;
- common non-business exceptions.

Not allowed:

```text
shared/product_service.py
shared/order_utils.py
shared/checkout_logic.py
shared/all_models.py
```

If logic contains domain vocabulary, it usually belongs to that domain.

---

# 43. API Versioning vs Domain Versioning

HTTP:

```text
/api/v1/...
```

Domain/application code is not duplicated under `v1`.

Correct:

```text
presentation/http/v1-like route surface
         ↓
same current application command
```

Event versioning is separate:

```text
order.created v1
order.created v2
```

Database migration version is separate again.

Do not confuse these three versioning systems.

---

# 44. Security Boundaries

## Public internet allowed

```text
/api/v1/storefront/*
/api/v1/auth/*
/api/v1/webhooks/*   # provider authenticated
/health/live
```

## Staff authenticated

```text
/api/v1/admin/*
```

## Private/service only

```text
/api/v1/internal/*
operational endpoints
worker controls
```

### Network rule

Internal endpoints should ideally be unreachable through public Nginx routing even if they also require service authentication.

Defense in depth:

```text
network boundary
+ service token/identity
+ store/resource validation
```

---

# 45. SSRF Protection Architecture

Relevant to:

- custom domain verification;
- outbound webhooks;
- integrations;
- media/source fetch if ever added.

Centralize safe outbound URL validation.

Block:

```text
localhost
127.0.0.0/8
::1
RFC1918 private networks
link-local
cloud metadata addresses
unsupported schemes
DNS rebinding to private IP
```

Provider adapters with fixed vendor base URLs are separate and simpler.

---

# 46. File Size / Complexity Guardrails

These are engineering guidelines, not rigid syntax laws.

Preferred:

```text
route file:            focused resource/surface
application command:   one business command
query service:         one coherent projection family
provider adapter:      one provider
domain policy:         one bounded business concern
```

When a file becomes hard for a reviewer/Codex to reason about, split by use case/resource—not arbitrary line count.

Avoid:

```text
commands.py with 70k lines
services.py containing all commerce
models.py for all modules
utils.py with business logic
```

---

# 47. Naming Conventions

Python:

```text
snake_case files/functions
PascalCase classes
UPPER_SNAKE_CASE constants
```

Commands:

```text
CreateProduct
CompleteCheckout
RequestRefund
```

Queries:

```text
GetProduct
ListOrders
SearchCustomers
```

Ports:

```text
ProductRepository
PaymentGateway
ShippingProvider
InventoryQueries
```

Database:

```text
plural snake_case table names
uuid *_id
created_at
updated_at
```

Event names:

```text
lowercase.dot.separated
order.created
payment.captured
inventory.reserved
shipment.status.changed
```

---

# 48. Status Field Rule

Do not introduce a generic:

```text
status VARCHAR
```

without defining:

- enum/allowed states;
- transition owner;
- allowed transitions;
- terminal states;
- retry/correction behavior;
- whether state is canonical or derived.

Do not accept arbitrary status via generic update DTO.

---

# 49. Feature Flags

Feature flags may be useful for optional client modules:

```text
returns
advanced_discounts
international_markets
b2b_pricing
stripe
shiprocket
blog
```

But feature flag is not authorization.

Use typed store capabilities/configuration.

Do not scatter:

```python
if settings.CLIENT_NAME == "ABC":
```

through business code.

Client customization belongs in:

- configuration;
- enabled capabilities;
- provider selection;
- custom frontend;
- explicitly versioned extension/metafield behavior.

---

# 50. Client Customization Boundary

The reusable backend should remain generic.

Safe client customization:

```text
brand frontend
theme/layout
content
navigation
SEO
payment provider configuration
shipping provider
store settings
enabled modules
custom metafields
approved business configuration
```

Avoid client-specific forks such as:

```python
if store == "FashionClient":
    checkout_total -= 100
```

If a client requires a genuinely new rule:

1. model it as configurable domain behavior if broadly valid; or
2. design an extension point/ADR; or
3. maintain a deliberate version/module—not hidden conditionals.

---

# 51. Testing Architecture Alignment

Full detail belongs in `docs/TESTING_STRATEGY.md`, but folder ownership should be:

```text
tests/unit/modules/catalog/
tests/unit/modules/inventory/

tests/integration/modules/inventory/
tests/integration/modules/payments/

tests/concurrency/
tests/contract/
tests/providers/
tests/e2e/
```

Unit tests:

- domain rules;
- application orchestration with fakes.

Integration tests:

- PostgreSQL repositories/UoW;
- Redis behaviors;
- outbox;
- migrations.

Concurrency tests:

- inventory;
- checkout idempotency;
- refunds;
- fulfillment;
- return receipt;
- refresh-token rotation.

Provider tests:

- recorded/sandbox contract mapping.

---

# 52. Codex-Optimized Repository Rules

This architecture is intentionally designed to make Codex effective.

A Codex task should be able to say:

```text
Implement TASK-INV-04 ReserveInventory.

Read:
- docs/BUSINESS_LOGIC.md Inventory section
- docs/DB_SCHEMA.md Inventory section
- docs/API_ARCHITECTURE.md Inventory section
- ARCHITECTURE.md §§ 5, 8, 13, 16

Expected files:
modules/inventory/application/commands/reserve.py
modules/inventory/application/ports/inventory_repository.py
modules/inventory/infrastructure/db/atomic_reservation.py
tests/concurrency/test_inventory_reservation.py
```

This is much safer than:

```text
"Build inventory module."
```

## Codex should never need to guess:

- table ownership;
- transaction owner;
- error code;
- provider boundary;
- where business logic belongs;
- whether Redis is authoritative;
- whether an operation is idempotent.

---

# 53. Architecture Enforcement Checks

Recommended static/repo checks later:

- Domain package may not import `fastapi`.
- Domain package may not import `sqlalchemy`.
- Application package may not import provider SDKs.
- Presentation routes may not import ORM models.
- Cross-module imports from `infrastructure` are forbidden.
- Migration head must be singular.
- OpenAPI route/permission inventory matches expected API surface.
- Ruff/mypy/pyright policy as chosen.
- Circular dependency detection.

These can be enforced through tests/scripts rather than relying only on documentation.

---

# 54. Architecture Anti-Patterns

## Anti-pattern 1 — Fat route

```python
@router.post("/checkout")
async def checkout(...):
    await db.execute(...)
    razorpay.order.create(...)
    await redis.set(...)
    await send_email(...)
```

**Rejected.**

---

## Anti-pattern 2 — Generic service god object

```text
EcommerceService
├── create_product
├── reserve_stock
├── charge_card
├── ship_order
├── refund
└── blog
```

**Rejected.**

---

## Anti-pattern 3 — Foreign ORM mutation

```text
Orders module directly updates Payment ORM
Checkout directly updates Inventory ORM
```

**Rejected.**

---

## Anti-pattern 4 — Provider-specific domain

```text
order.razorpay_status
order.shiprocket_payload
```

inside canonical order model.

**Rejected.**

Provider-specific evidence belongs at provider/integration boundary.

---

## Anti-pattern 5 — Cache as truth

```text
Redis stock says 4 therefore sell 4
```

**Rejected.**

PostgreSQL inventory transaction remains authoritative.

---

## Anti-pattern 6 — Business logic in Pydantic validators

Simple field validation is fine.

Complex rules such as:

```text
Can this order be cancelled?
Can this refund be issued?
Which discount wins?
```

belong in domain/application logic.

---

# 55. Initial Module Dependency Map

`→` means “may invoke an explicit application contract/read port of”.

```text
store
  └─ mostly foundational

iam
  └─ authorization context for admin surfaces

customers
  └─ orders (read/history linking only through contracts)

catalog
  ├─ inventory (qualification/reference boundary)
  └─ pricing

pricing
  └─ catalog

promotions
  ├─ catalog/read eligibility
  └─ customers/read eligibility

cart
  ├─ catalog
  ├─ pricing
  └─ promotions

checkout
  ├─ cart
  ├─ pricing
  ├─ promotions
  ├─ inventory
  ├─ payments
  └─ orders

orders
  ├─ customers/reference
  └─ no direct provider dependency

payments
  └─ orders/read identity/amount context through contract

fulfillment
  ├─ orders
  ├─ inventory
  └─ shipping provider adapter

returns
  ├─ orders
  ├─ inventory
  └─ payments

notifications
  └─ consumes durable events

integrations
  └─ consumes durable events

audit
  └─ accepts evidence from privileged commands

bulk
  └─ orchestrates normal module application commands
```

Avoid dependency cycles by depending on narrow ports/read models rather than importing full modules.

---

# 56. Recommended Facades

Stable cross-module facades:

```text
modules/catalog/application/facade.py
modules/pricing/application/facade.py
modules/promotions/application/facade.py
modules/inventory/application/facade.py
modules/orders/application/facade.py
modules/payments/application/facade.py
modules/fulfillment/application/facade.py
```

Examples:

```python
CatalogFacade.get_sellable_variant(...)
PricingFacade.price_lines(...)
InventoryFacade.reserve(...)
PaymentsFacade.get_payment_state(...)
OrdersFacade.create_from_checkout(...)
```

Facades do not expose ORM models.

---

# 57. Bootstrap Order

Application startup:

```text
1. Load/validate settings
2. Configure structured logging
3. Configure tracing/metrics
4. Build DB engine/session factory
5. Build Redis client
6. Build provider clients/adapters
7. Build module repositories/UoWs/facades
8. Mount module HTTP routers
9. Install exception handlers
10. Install request/correlation middleware
11. Expose health/OpenAPI according to environment
```

A missing required production secret should fail startup clearly rather than fail on the first customer checkout.

---

# 58. Graceful Shutdown

On shutdown:

```text
stop accepting new work
→ allow bounded in-flight request completion
→ stop worker claims
→ close DB pool
→ close Redis
→ close HTTP/provider clients
→ flush telemetry
```

Workers must not leave permanent `PROCESSING` locks without a lease/recovery mechanism.

---

# 59. Deployment / Release Sequence

Recommended:

```text
CI
├── lint/type checks
├── unit tests
├── integration tests
├── migration checks
└── contract tests
      ↓
build immutable image
      ↓
backup / verify migration plan
      ↓
run migration
      ↓
deploy API/workers
      ↓
readiness checks
      ↓
smoke tests
      ↓
traffic
```

For risky schema transitions:

```text
expand → deploy compatible code → backfill → switch reads/writes → contract later
```

---

# 60. Rollback Principle

Code rollback is easy only when DB/API compatibility remains safe.

Every risky change should consider:

- old code against new schema;
- new code against partially migrated data;
- worker version compatibility;
- event payload compatibility;
- provider request duplication.

Do not promise “rollback” if a destructive migration already erased data.

---

# 61. Backup / Data Safety

For each client production deployment:

- automated PostgreSQL backups;
- off-VPS backup copy;
- restore procedure tested;
- retention policy;
- encryption;
- DB credentials separated from source code;
- object storage versioning/lifecycle where practical.

Commerce ledgers/history make restore correctness important.

---

# 62. Documentation Ownership

| Change | Must review/update |
|---|---|
| Table/constraint/index | `docs/DB_SCHEMA.md`, migration, possibly ADR |
| Business invariant/state machine | `docs/BUSINESS_LOGIC.md` |
| Endpoint/request/response/permission | `docs/API_ARCHITECTURE.md` |
| Folder/layer/dependency/runtime change | `ARCHITECTURE.md` |
| Testing approach/gates | `docs/TESTING_STRATEGY.md` |
| New irreversible architecture decision | `docs/adr/*` |
| Codex operating rule | `AGENTS.md` |

Do not create duplicate documents for the same truth.

---

# 63. Recommended ADRs Before/While Implementation

```text
ADR-001 Modular Monolith
ADR-002 One-Store-Per-Deployment + Store-Scoped Schema
ADR-003 PostgreSQL as Canonical Commerce Truth
ADR-004 Transactional Outbox
ADR-005 Inventory Movement Ledger + Reservation Model
ADR-006 Durable Cart with Redis Cache
ADR-007 Checkout as Separate Domain
ADR-008 Immutable Order Snapshot
ADR-009 Provider Adapter Boundary
ADR-010 Idempotency Record Pattern
ADR-011 REST-First API, Transport-Neutral Application Layer
ADR-012 Async Bulk Operations
```

Each ADR should contain:

```text
Context
Decision
Consequences
Rejected alternatives
Migration/reversal notes
Status
```

---

# 64. Architecture Review Checklist

Before merging a feature, answer:

- [ ] Which module owns this business state?
- [ ] Is business logic outside the route?
- [ ] Does domain code remain framework-free?
- [ ] Is there a clear application command/query?
- [ ] Does the correct use case own the transaction?
- [ ] Does any repository commit independently? It should not.
- [ ] Does code mutate a foreign module ORM model? It should not.
- [ ] Are external HTTP calls outside core DB locks?
- [ ] Is retry/idempotency defined?
- [ ] Is concurrency behavior defined?
- [ ] Are store/ownership filters explicit?
- [ ] Are money values Decimal?
- [ ] Are status transitions centralized?
- [ ] Does a required side effect use outbox?
- [ ] Is Redis only cache/ephemeral infrastructure?
- [ ] Are errors mapped to stable API codes?
- [ ] Is observability/request ID preserved?
- [ ] Are unit/integration/concurrency tests in the correct layer?
- [ ] Did docs change if architecture/business/API/schema changed?

---

# 65. Codex Implementation Gate

Codex should **not** be asked to implement the entire platform in one prompt.

Recommended sequence:

```text
Phase 0  repository scaffold / core platform
Phase 1  Store + IAM
Phase 2  Customers
Phase 3  Catalog + Media
Phase 4  Inventory
Phase 5  Cart + Pricing + Promotions baseline
Phase 6  Checkout
Phase 7  Orders
Phase 8  Payments
Phase 9  Fulfillment / Shipping
Phase 10 Returns / Refund completion
Phase 11 CMS / SEO / Notifications
Phase 12 Integrations / Bulk / Operational hardening
Phase 13 P2 Markets / advanced pricing / extensibility
```

Each task should implement one coherent command/query/slice with acceptance tests.

---

# 66. Final Architecture Contract

The canonical architecture is:

```text
                         ┌──────────────────┐
                         │   Presentation   │
                         │ FastAPI / Pydantic│
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Application    │
                         │ Commands/Queries │
                         │ UoW/Orchestration│
                         └───────┬──────────┘
                                 │
                         ┌───────▼──────────┐
                         │      Domain      │
                         │ Rules/Invariants │
                         │ States/Policies  │
                         └──────────────────┘
                                  ▲
                                  │ implements ports
                         ┌────────┴─────────┐
                         │ Infrastructure   │
                         │ DB/Redis/Providers│
                         └──────────────────┘
```

Across modules:

```text
Owning application contract
        ↓
Owning domain
        ↓
Owning repository/state

Never:
foreign ORM mutation
```

Across transactions:

```text
local consistent DB mutation
+ audit/ledger
+ outbox
        ↓
COMMIT
        ↓
provider/notification/webhook async side effects
```

Across deployment:

```text
Reusable LinkUp Commerce codebase
        ↓
Client-specific environment/configuration
        ↓
Dedicated VPS/database initially
        ↓
Custom brand storefront
```

---

## Technical Lead Sign-Off

This architecture intentionally takes the clean layered modular structure used in FYNEURA-X and adapts it for a commerce-specific engine with stricter boundaries around **inventory concurrency, checkout orchestration, financial ledgers, provider adapters, immutable orders, idempotency and asynchronous side effects**.

The architecture should remain boring and predictable on purpose.

**If a future implementation requires bypassing one of these boundaries to “make it work quickly,” stop and document the exception/ADR before allowing that shortcut to become architecture.**

## Documentation Remediation Freeze Addendum

- Idempotency states are `IN_PROGRESS`, `SUCCEEDED`, `FAILED_RETRYABLE`, and `FAILED_FINAL`; claims use `(store_id, operation, idempotency_key)`, request hashes, response replay, attempt counts, and lease expiry.
- Outbox states are `PENDING`, `PROCESSING`, `PUBLISHED`, and `DEAD`. Workers claim bounded batches, set owner and lease fields, publish/process, then mark `PUBLISHED`; expired leases are safely reclaimable and consumers remain idempotent.
- `carts` and `checkout_sessions` use mandatory `BIGINT version` optimistic concurrency. Mutable admin resources may use version/ETag where specified; explicit state-machine commands remain mandatory for orders, payments, inventory, refunds, and fulfillment.
- Payment intent states are `CREATED`, `PENDING_CUSTOMER_ACTION`, `PROCESSING`, `AUTHORIZED`, `CAPTURED`, `FAILED`, `CANCELLED`, and `RECONCILIATION_REQUIRED`. Unknown provider outcomes never become automatic failure.
- Request and correlation IDs are opaque strings (recommended `VARCHAR(64)`), not UUID-only values.
- Variant store scope, SKU uniqueness, option signatures, and provider-event ownership are defined in `docs/DB_SCHEMA.md`.
