# LinkUp Commerce Engine — Implementation Plan

**Document type:** Codex Execution Roadmap / Engineering Delivery Plan  
**Version:** v1.0  
**Date:** 2026-09-08  
**Architecture:** FastAPI Modular Monolith  
**Primary implementation agent:** Codex / engineering team  
**Companion docs:** `AGENTS.md`, `ARCHITECTURE.md`, `docs/DB_SCHEMA.md`, `docs/BUSINESS_LOGIC.md`, `docs/API_ARCHITECTURE.md`

---

# 1. Purpose

This document converts the approved LinkUp Commerce architecture into **small,
dependency-aware, testable implementation slices**.

The goal is not to maximize coding speed by generating the entire backend in one
prompt.

The goal is to maximize:

- correctness;
- Codex reliability;
- reviewability;
- safe migrations;
- predictable integration;
- test evidence;
- production readiness.

The implementation model is:

```text
Architecture
    ↓
Business rules
    ↓
DB/API contracts
    ↓
Small approved task
    ↓
Code
    ↓
Focused tests
    ↓
Review
    ↓
Phase gate
    ↓
Next task
```

---

# 2. Implementation Principles

1. **One coherent task at a time.**
2. **P0 correctness before P1/P2 feature breadth.**
3. **Database + domain + application + API + tests move together for each slice.**
4. **Do not create placeholder features that appear production-ready.**
5. **Do not let Codex invent missing business decisions.**
6. **Do not jump ahead because a later task is easier.**
7. **Concurrency-sensitive flows require real PostgreSQL tests.**
8. **Provider-facing flows require idempotency/reconciliation behavior before launch.**
9. **Every phase has an explicit exit gate.**
10. **Any architecture deviation requires ADR/document update before broad continuation.**

---

# 3. Documentation Preflight

Before Phase 0 begins, canonical repository docs should exist at:

```text
AGENTS.md
ARCHITECTURE.md

docs/
├── DB_SCHEMA.md
├── API_ARCHITECTURE.md
├── BUSINESS_LOGIC.md
├── TESTING_STRATEGY.md
├── STATUS.md
└── adr/
```

Existing generated documents should be renamed/copied into those canonical paths.

---

# 4. Priority Classification

| Priority | Meaning | Release rule |
|---|---|---|
| **P0** | Core commerce correctness/security/reliability | Required before production |
| **P1** | Standard reusable e-commerce capability | Add after core path is stable |
| **P2** | Advanced SaaS/B2B/international/extensibility | Implement only on approved demand |

---

# 5. Delivery Phases

```text
PHASE 0   Repository & Platform Foundation
PHASE 1   Store + IAM / RBAC
PHASE 2   Customers
PHASE 3   Catalog + Media + Collections
PHASE 4   Inventory
PHASE 5   Pricing + Promotions + Cart
PHASE 6   Checkout
PHASE 7   Orders
PHASE 8   Payments + Refund Foundation
PHASE 9   Fulfillment + Shipping + NDR + COD
PHASE 10  Returns
PHASE 11  CMS + SEO + Notifications
PHASE 12  Integrations + Webhooks + Bulk + Operations
PHASE 13  Advanced Markets / Price Lists / Metafields
PHASE 14  Production Hardening / Load / Security / Launch
```

---

# 6. High-Level Dependency Graph

```text
Foundation
   ↓
Store / IAM
   ↓
Customers
   ↓
Catalog
   ↓
Inventory
   ↓
Pricing / Promotions / Cart
   ↓
Checkout
   ↓
Orders
   ↓
Payments
   ↓
Fulfillment
   ↓
Returns
   ↓
CMS / Notifications / Integrations
   ↓
Advanced capabilities
   ↓
Production hardening
```

Some modules can be developed in parallel after their dependencies are stable, but
Codex should not parallelize P0 transaction work unless merge/integration ownership
is explicit.

---

# 7. Standard Task Format

Every Codex implementation prompt should follow:

```text
MODE: IMPLEMENTATION

TASK ID:
TASK-XXX

GOAL:
One clear business outcome.

READ:
- AGENTS.md
- relevant ARCHITECTURE.md sections
- relevant BUSINESS_LOGIC.md section
- relevant API_ARCHITECTURE.md section
- relevant DB_SCHEMA.md section
- relevant ADRs

DEPENDENCIES:
Prior task IDs that must already be complete.

EXPECTED AREA:
Likely files/modules.

ACCEPTANCE CRITERIA:
Concrete observable requirements.

TESTS:
Exact categories/scenarios required.

NON-GOALS:
Explicitly out of scope.

RISKS:
Known P0/P1 risks.

COMPLETION EVIDENCE:
Files changed, migrations, tests, commands, results, docs updated.
```

---

# 8. Phase 0 — Repository & Platform Foundation

**Goal:** create a stable modular-monolith skeleton before domain implementation.

**Phase priority:** P0

## Tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| FND-001 | Initialize repository structure | — | folders/files matching `ARCHITECTURE.md` |
| FND-002 | Python project configuration | FND-001 | `pyproject.toml`, lint/type/test tooling |
| FND-003 | FastAPI app factory/bootstrap | FND-001 | `app/main.py`, `bootstrap.py`, router mounts |
| FND-004 | Pydantic settings/config | FND-002 | environment config + validation |
| FND-005 | Structured logging/request IDs | FND-003 | request/correlation context |
| FND-006 | PostgreSQL async engine/session | FND-002 | SQLAlchemy async DB foundation |
| FND-007 | Alembic setup | FND-006 | migration environment |
| FND-008 | Redis client/cache foundation | FND-004 | Redis wrapper/key conventions |
| FND-009 | Global error envelope | FND-003 | stable error model/handlers |
| FND-010 | Pagination primitives | FND-003 | cursor types/helpers |
| FND-011 | Unit of Work base contracts | FND-006 | shared UoW protocol/implementation base |
| FND-012 | Event envelope/outbox base | FND-006 | event contracts/base persistence |
| FND-013 | Idempotency base infrastructure | FND-006 | idempotency record service/repository |
| FND-014 | Worker bootstrap | FND-004,FND-006 | worker app + scheduler entrypoints |
| FND-015 | Health/readiness endpoints | FND-003,FND-006,FND-008 | `/health/live`, `/health/ready` |
| FND-016 | Docker local environment | FND-006,FND-008 | API/Postgres/Redis/workers |
| FND-017 | Test infrastructure base | FND-006 | disposable Postgres fixtures |
| FND-018 | Architecture import guard tests | FND-001 | layer-boundary enforcement |
| FND-019 | CI baseline | FND-002,FND-017 | lint/type/unit/integration pipeline |
| FND-020 | Create initial STATUS.md | FND-001 | implementation status tracker |

## Detailed critical tasks

### FND-003 — FastAPI app factory

**Acceptance**
- app starts without domain modules implemented;
- routers mount by API surface;
- environment controls docs/OpenAPI exposure;
- no provider/DB work at import time;
- startup/shutdown lifecycle closes clients cleanly.

**Tests**
- app factory smoke test;
- health route registration;
- no duplicate route prefix.

**Non-goals**
- auth;
- business endpoints.

---

### FND-006 — PostgreSQL foundation

**Acceptance**
- SQLAlchemy 2.x async;
- explicit session factory;
- no global shared session;
- transaction-safe dependency;
- test DB override supported.

**Tests**
- DB connection;
- transaction rollback;
- two independent concurrent sessions.

---

### FND-013 — Idempotency infrastructure

**Acceptance**
- DB uniqueness prevents duplicate claim race;
- stores semantic request hash;
- same key/same request can replay;
- same key/different request returns conflict;
- stale in-progress policy modeled.

**Tests**
- simultaneous atomic claim;
- request hash mismatch;
- successful result replay.

---

## Phase 0 Exit Gate

Must be true:

- [ ] application starts in Docker;
- [ ] PostgreSQL/Redis connectivity verified;
- [ ] one Alembic head;
- [ ] test database is disposable and reproducible;
- [ ] UoW works;
- [ ] request ID/logging works;
- [ ] architecture import guards exist;
- [ ] CI baseline passes;
- [ ] no business module is prematurely implemented.

---

# 9. Phase 1 — Store + IAM / RBAC

**Goal:** establish store context, merchant authentication and server-side permissions.

## Store tasks

| ID | Task | Depends on |
|---|---|---|
| STO-001 | Store/domain ORM + migration | Phase 0 |
| STO-002 | Store repository/UoW | STO-001 |
| STO-003 | Public store read API | STO-002 |
| STO-004 | Admin store settings API | STO-002,IAM auth minimum |
| STO-005 | Domain registration model | STO-001 |
| STO-006 | Domain verification workflow | STO-005 |
| STO-007 | Sales channel model/API | STO-001 |

## IAM tasks

| ID | Task | Depends on |
|---|---|---|
| IAM-001 | User/staff/role/permission schema | Phase 0 |
| IAM-002 | Password hashing/security primitives | IAM-001 |
| IAM-003 | Login + access token | IAM-002 |
| IAM-004 | Refresh token persistence/rotation | IAM-003 |
| IAM-005 | Logout/session revoke | IAM-004 |
| IAM-006 | Effective permission resolver | IAM-001 |
| IAM-007 | Auth dependencies / ActorContext | IAM-003,IAM-006 |
| IAM-008 | Role CRUD | IAM-006 |
| IAM-009 | Staff invite/accept | IAM-004,IAM-006 |
| IAM-010 | Staff role assignment | IAM-008 |
| IAM-011 | Last-owner/protected-role safeguards | IAM-010 |
| IAM-012 | Auth rate-limit integration | IAM-003 |
| IAM-013 | Audit high-risk IAM changes | IAM-008,IAM-010 |

### IAM-004 — Refresh rotation

**Acceptance**
- refresh tokens hashed at rest;
- `family_id`, `parent_token_id`, `replaced_by_token_id`, and `consumed_at` persist rotation lineage;
- one-time rotation;
- replay revokes token family;
- simultaneous refresh race cannot create two valid chains; PostgreSQL row locking/unique token hash is authoritative.

**Required test**
- two concurrent refresh requests using same token → one valid successor.

### IAM-006 — Permission resolver

**Acceptance**
- permission is server resolved;
- role changes invalidate cache;
- inactive staff denied;
- no request-body store authorization.

## Phase 1 Exit Gate

- [ ] admin authentication complete;
- [ ] server-side RBAC enforced;
- [ ] protected role invariants pass;
- [ ] refresh race test passes PostgreSQL;
- [ ] public/admin store context works;
- [ ] high-risk IAM changes audited.

---

# 10. Phase 2 — Customers

**Goal:** shopper identity, saved addresses and consent without mixing customer/staff identity.

| ID | Task | Depends on |
|---|---|---|
| CUS-001 | Customer/address/consent schema | Phase 1 |
| CUS-002 | Customer repository/query services | CUS-001 |
| CUS-003 | Customer registration | CUS-002 |
| CUS-004 | Customer login/session (access-only; customer refresh deferred) | CUS-003 |
| CUS-005 | Customer profile API | CUS-004 |
| CUS-006 | Address CRUD + default invariant | CUS-005 |
| CUS-007 | Consent ledger | CUS-005 |
| CUS-008 | Admin customer list/detail | CUS-002,IAM-007 |
| CUS-009 | Admin customer update | CUS-008 |
| CUS-010 | Guest customer/profile linking groundwork | CUS-002 |

### CUS-006 Acceptance
- ownership enforced;
- exactly one default where policy requires;
- saved-address edits cannot affect order snapshots;
- IDOR tests.

Customer refresh/logout persistence is not implemented in CUS-004: staff
`refresh_tokens` must never store customer sessions. Those P1 APIs remain deferred
until a dedicated customer session registry is approved.

### CUS-007 Acceptance
- append-only consent evidence;
- operational status separated from marketing consent;
- no implicit opt-in.

## Phase 2 Exit Gate
- [ ] customer/staff identities clearly separated;
- [ ] customer IDOR tests pass;
- [ ] consent history append-only;
- [ ] address ownership/default rules pass.

---

# 11. Phase 3 — Catalog + Media + Collections

**Goal:** production-ready reusable product master and storefront catalog.

| ID | Task | Depends on |
|---|---|---|
| CAT-001 | Product/variant/options schema | Phase 2 |
| CAT-002 | Catalog ORM/repositories | CAT-001 |
| CAT-003 | Product create/update | CAT-002 |
| CAT-004 | Variant create/update | CAT-002 |
| CAT-005 | Option/value management | CAT-002 |
| CAT-006 | Product publish/archive state machine | CAT-003,CAT-004 |
| CAT-007 | Storefront product detail | CAT-002 |
| CAT-008 | Storefront product listing | CAT-002 |
| CAT-009 | Admin product listing | CAT-002 |
| CAT-010 | Media asset schema/storage port | Phase 0 |
| CAT-011 | Signed media upload session | CAT-010 |
| CAT-012 | Media finalize/validation | CAT-011 |
| CAT-013 | Product-media ordering | CAT-012,CAT-002 |
| CAT-014 | Collections schema/CRUD | CAT-001 |
| CAT-015 | Collection-product membership | CAT-014 |
| CAT-016 | Tags | CAT-001 |
| CAT-017 | Search suggestions baseline | CAT-008 |
| CAT-018 | Catalog cache invalidation via outbox | CAT-006,FND-012 |

### CAT-004 Critical rules
- store-scoped SKU unique;
- exact option combination unique;
- Decimal money;
- creating inventory-tracked variant prepares inventory identity through explicit contract in Phase 4 or transitional pending mechanism.

### CAT-006 Publish acceptance
- incomplete product rejected;
- at least one valid sellable variant;
- no hard delete for referenced commerce entity;
- publish event emitted.

## Phase 3 Exit Gate
- [ ] product CRUD;
- [ ] variant/options invariant;
- [ ] publish/archive workflow;
- [ ] media direct upload;
- [ ] collections;
- [ ] no money float;
- [ ] storefront queries bounded/paginated.

---

# 12. Phase 4 — Inventory

**Goal:** safe stock accounting and reservation foundation before checkout exists.

**This is a P0 critical phase.**

| ID | Task | Depends on |
|---|---|---|
| INV-001 | Locations schema | Phase 3 |
| INV-002 | Inventory item/level schema | INV-001 |
| INV-003 | Inventory movements ledger | INV-002 |
| INV-004 | Manual stock adjustment | INV-003 |
| INV-005 | Physical reconciliation | INV-004 |
| INV-006 | Reservation schema/state model | INV-002 |
| INV-007 | Atomic reserve command | INV-006 |
| INV-008 | Reservation release | INV-007 |
| INV-009 | Consume Reservation | INV-007 |
| INV-010 | Reservation expiry worker | INV-008 |
| INV-011 | Admin inventory list/detail | INV-002 |
| INV-012 | Movement ledger API | INV-003 |
| INV-013 | Inventory transfer schema | INV-002 |
| INV-014 | Create/ship transfer | INV-013 |
| INV-015 | Partial receive transfer | INV-014 |
| INV-016 | Inventory application facade | INV-007,INV-008,INV-009 |
| INV-017 | Inventory observability | INV-007 |
| INV-018 | Concurrency/race suite | INV-007,INV-008,INV-009,INV-015 |

### INV-007 — Atomic reservation

**Acceptance**
- all requested quantities validated atomically;
- deterministic lock ordering;
- no oversell;
- insufficient stock gives `OUT_OF_STOCK`;
- no partial hidden reservation after failure;
- reservation evidence durable.

**Mandatory test**
```text
stock=5
10 concurrent reserve requests
exactly 5 succeed
```

### INV-008 / INV-009
Release/expire changes only `reserved`; consume performs `ACTIVE → CONSUMED`,
decrements `on_hand` and `reserved`, and appends exactly one
`RESERVATION_CONSUME` movement. Repeated release/consume must not change stock twice.

### INV-002 / INV-003 acceptance
Document and enforce `on_hand >= 0`, `reserved >= 0`, `incoming >= 0`,
`damaged >= 0`, and `reserved + damaged <= on_hand`.

### INV-015
Repeated partial transfer receipt cannot duplicate destination stock.

## Phase 4 Exit Gate

- [ ] stock movement ledger implemented;
- [ ] manual adjustment audited;
- [ ] reserve/release/commit idempotent;
- [ ] reservation expiry worker safe;
- [ ] real PostgreSQL race tests pass;
- [ ] transfer receipt duplication test passes.

**Do not begin checkout production work if this gate fails.**

---

# 13. Phase 5 — Pricing + Promotions + Cart

**Goal:** authoritative shopping-intent layer before final transaction orchestration.

## Pricing baseline

### TAX-000 — Freeze India GST Policy (documentation/compliance gate)

This planning task freezes approved tax configuration and compliance decisions;
it creates no runtime code. It must be completed before `CHK-007` Checkout
repricing pipeline and `ORD-001` Order tax snapshot schema implementation.
GST registrations, CGST/SGST/IGST, HSN/SAC, shipping tax, tax-inclusive policy,
rounding, and invoice/credit-note behavior remain `DECISION REQUIRED — GST
POLICY` until business/compliance approval. Phase 0, Store/IAM, Customers,
Catalog, and Inventory remain unblocked.

| ID | Task | Depends on |
|---|---|---|
| PRC-001 | Money/pricing value objects | Catalog |
| PRC-002 | Base variant pricing service | PRC-001 |
| PRC-003 | Pricing application facade | PRC-002 |
| PRC-004 | Pricing snapshot/version metadata | PRC-002 |

## Promotions

| ID | Task | Depends on |
|---|---|---|
| PRO-001 | Discount/code/redemption schema | PRC-002 |
| PRO-002 | Percentage/flat rule engine | PRO-001 |
| PRO-003 | Eligibility/target engine | PRO-002 |
| PRO-004 | Combination/precedence rules | PRO-002 |
| PRO-005 | Cart preview evaluation | PRO-003 |
| PRO-006 | Redemption commit command | PRO-005 |
| PRO-007 | Usage concurrency tests | PRO-006 |
| PRO-008 | Admin promotion APIs | PRO-001 |

## Cart

| ID | Task | Depends on |
|---|---|---|
| CRT-001 | Cart/cart-line schema | PRC-002 |
| CRT-002 | Opaque guest cart token | CRT-001 |
| CRT-003 | Create/get cart | CRT-002 |
| CRT-004 | Add/update/remove line | CRT-003,CAT |
| CRT-005 | Buyer identity attach | CRT-003,CUS |
| CRT-006 | Cart authoritative reprice | CRT-004,PRC-003,PRO-005 |
| CRT-007 | Redis cache projection | CRT-006 |
| CRT-008 | Cart expiry/abandonment baseline | CRT-003 |
| CRT-009 | Storefront cart tests | CRT-004,CRT-006 |

### Promotion rule
Preview does not consume usage.

### Cart rule
PostgreSQL is source; Redis cache may be rebuilt.

## Phase 5 Exit Gate
- [ ] cart durable;
- [ ] cart price comes server-side;
- [ ] promotion preview has no usage side effect;
- [ ] limited promotion redemption concurrency protected;
- [ ] Redis outage does not destroy cart truth.

---

# 14. Phase 6 — Checkout

**Goal:** build the authoritative short-lived commerce transaction session.

**Highest-risk orchestration phase.**

| ID | Task | Depends on |
|---|---|---|
| CHK-001 | Checkout/session/line/address schema | Phase 5,Inventory |
| CHK-002 | Checkout repository/state model | CHK-001 |
| CHK-003 | Create checkout from cart | CHK-002 |
| CHK-004 | Set shipping/billing address | CHK-003 |
| CHK-005 | Shipping quote port + rate snapshot | CHK-004 |
| CHK-006 | Select shipping rate | CHK-005 |
| CHK-007 | Checkout repricing pipeline | CHK-003,PRC,PRO,TAX-000 |
| CHK-008 | Reserve checkout inventory | CHK-007,INV-016 |
| CHK-009 | Checkout version conflict protection | CHK-003 |
| CHK-010 | Checkout expiry worker | CHK-008 |
| CHK-011 | Payment-session application port | CHK-008 |
| CHK-012 | Checkout state-machine tests | CHK-003..010 |
| CHK-013 | Checkout storefront APIs | CHK-003..011 |
| CHK-014 | Checkout observability | CHK-013 |

### CHK-003
Cart remains separate; checkout gets independent expiry/version.

### CHK-005
Carrier/provider call is outside DB transaction. Rate belongs to checkout+address/package context and expires.

### CHK-008
Reprice before reserve.

## Phase 6 Exit Gate
- [ ] checkout versioning;
- [ ] rate invalidation on address/package change;
- [ ] atomic inventory reserve integrated;
- [ ] checkout expiry releases reservation once;
- [ ] no payment truth implemented in browser;
- [ ] no provider call under inventory lock.

---

# 15. Phase 7 — Orders

**Goal:** permanent immutable commercial snapshot and state machine.

| ID | Task | Depends on |
|---|---|---|
| ORD-001 | Order/order-item/address/tax/discount schema | Phase 6,TAX-000 |
| ORD-002 | Order number generation | ORD-001 |
| ORD-003 | Order repository | ORD-001 |
| ORD-004 | Create order snapshot command | ORD-003 |
| ORD-005 | Order state machine/history | ORD-003 |
| ORD-006 | Checkout completion orchestration | ORD-004,CHK,INV,PRO,FND idempotency |
| ORD-007 | Customer order history/detail | ORD-003,CUS |
| ORD-008 | Admin order list/detail | ORD-003 |
| ORD-009 | Hold/release hold | ORD-005 |
| ORD-010 | Cancellation orchestration baseline | ORD-005 |
| ORD-011 | Draft/manual order baseline | ORD-004 |
| ORD-012 | Order export bulk-job request | ORD-008,Bulk later |
| ORD-013 | Order immutability tests | ORD-004 |
| ORD-014 | Checkout complete idempotency race tests | ORD-006 |

### ORD-006 — Checkout completion

**Completion contract**
COD/offline completion may create an order with `financial_status=PENDING` and an
append-only offline collection record. Online completion requires verified CAPTURED
provider evidence. `CompleteCheckoutUseCase` owns the idempotent short transaction,
consumes ACTIVE reservations, sets `orders.checkout_id`, and relies on unique
`(store_id, checkout_id)` for the one-checkout/one-order invariant.

**Acceptance**
- DB-backed idempotency claim;
- same key same request = same order;
- same key different request = 409;
- immutable order/address/line snapshots;
- inventory reservation consumption (`ACTIVE → CONSUMED`);
- Payment Intent linked to Order in the same completion transaction;
- redemption commit;
- outbox `order.created`;
- no external provider HTTP inside transaction.

### ORD-014 mandatory
```text
10 simultaneous complete requests
same idempotency key
→ exactly one order
```

## Phase 7 Exit Gate
- [ ] immutable snapshots;
- [ ] state transitions centralized;
- [ ] order completion idempotent under race;
- [ ] catalog/address edits cannot alter old order;
- [ ] cancellation does not blindly refund/restock.

---

# 16. Phase 8 — Payments + Refund Foundation

**Goal:** gateway-independent financial ledger and verified payment evidence.

**P0 financial phase.**

| ID | Task | Depends on |
|---|---|---|
| PAY-001 | Payment intent/transaction/provider-event schema | FND,CHK-003 |
| PAY-002 | Payment repository/query services | PAY-001 |
| PAY-003 | Payment gateway port | PAY-001 |
| PAY-004 | Razorpay adapter | PAY-003 |
| PAY-005 | Stripe adapter optional | PAY-003 |
| PAY-006 | Create local payment intent | PAY-002,CHK-003 |
| PAY-007 | Create provider session safely | PAY-006,PAY-004 |
| PAY-008 | Razorpay webhook raw signature intake | PAY-004 |
| PAY-009 | Provider event durable dedupe | PAY-008 |
| PAY-010 | Process provider event | PAY-009 |
| PAY-011 | Payment transaction projection/status | PAY-010 |
| PAY-012 | Checkout-origin payment-session integration | PAY-007,CHK-003 |
| PAY-013 | Verified-payment/COD checkout completion integration | PAY-010,ORD-006 |
| PAY-014 | Refund schema/repository | PAY-001 |
| PAY-015 | Refundable balance calculation | PAY-014 |
| PAY-016 | Request refund idempotently | PAY-015 |
| PAY-017 | Provider refund execution | PAY-016,PAY-004 |
| PAY-018 | Partial refund | PAY-017 |
| PAY-019 | Offline/COD manual payment transaction | PAY-002 |
| PAY-020 | Payment reconciliation command | PAY-004 |
| PAY-021 | Webhook replay/out-of-order tests | PAY-010 |
| PAY-022 | Concurrent refund race tests | PAY-016 |
| PAY-023 | Provider timeout recovery tests | PAY-007,PAY-020 |
| PAY-024 | Payment observability | PAY-010 |

### PAY-008
Signature must use raw body.

### PAY-009
Unique provider event identity: `(store_id, provider, external_event_id)`.

### PAY-001 / PAY-006 / PAY-007
Payment intent schema and creation enforce CHECKOUT/ORDER/ADMIN context rules,
same-store ownership, `(store_id, operation, idempotency_key)` request scope,
provider-scoped reference uniqueness, and at most one nonterminal online attempt per
checkout/logical payment. Timeout means reconciliation, never blind creation of a
second provider target.

### PAY-013
Browser callback does not mark paid. Acceptance includes capture-vs-expiry and
capture-vs-complete races; late capture after RELEASED/EXPIRED uses controlled
re-reservation or reconciliation/refund without oversell.

### PAY-022 mandatory
Two concurrent maximum refunds cannot both consume the same balance.

## Phase 8 Exit Gate
- [ ] online payment state verified from provider evidence;
- [ ] webhook replay safe;
- [ ] out-of-order event rule tested;
- [ ] payment transaction ledger immutable;
- [ ] partial refund works;
- [ ] concurrent over-refund prevented;
- [ ] unknown provider timeout reconciles instead of blind duplicate.

---

# 17. Phase 9 — Fulfillment + Shipping + NDR + COD

**Goal:** split fulfillment and provider-independent shipping workflow.

| ID | Task | Depends on |
|---|---|---|
| FUL-001 | Fulfillment/item schema | Orders,Inventory |
| FUL-002 | Fulfillment create command | FUL-001 |
| FUL-003 | Fulfillment quantity locking | FUL-002 |
| FUL-004 | Fulfillment state machine | FUL-002 |
| SHP-001 | Shipment/event schema | FUL-001 |
| SHP-002 | Shipping provider port | SHP-001 |
| SHP-003 | Shiprocket adapter | SHP-002 |
| SHP-004 | Delhivery adapter optional | SHP-002 |
| SHP-005 | Shipment local intent/idempotency | SHP-001 |
| SHP-006 | Create provider shipment | SHP-003,SHP-005 |
| SHP-007 | Label retrieval | SHP-006 |
| SHP-008 | Shipment cancellation | SHP-006 |
| SHP-009 | Tracking webhook intake | SHP-003 |
| SHP-010 | Normalized tracking event processor | SHP-009 |
| SHP-011 | Customer tracking API | SHP-010 |
| SHP-012 | Admin shipment tracking | SHP-010 |
| NDR-001 | NDR schema/workflow | SHP-010 |
| NDR-002 | NDR action provider integration | NDR-001 |
| COD-001 | COD remittance schema | SHP-001 |
| COD-002 | COD settlement import/reconcile | COD-001 |
| FUL-005 | Fulfillment cancellation | FUL-004 |
| FUL-006 | Concurrent over-fulfillment test | FUL-003 |
| SHP-013 | Duplicate AWB timeout test | SHP-006 |
| SHP-014 | Out-of-order tracking test | SHP-010 |
| PAY-025 | Payment/checkout-expiry recovery race tests | PAY-013,INV-010 |
| PAY-026 | Concurrent payment-session attempt guard test | PAY-007,PAY-020 |

### Key invariants
- order may split into multiple fulfillments/shipments;
- no duplicate AWB on timeout;
- late IN_TRANSIT cannot regress DELIVERED;
- COD delivery does not automatically mean remittance settled.
- COD remittance lifecycle is `EXPECTED → REPORTED → RECONCILED → SETTLED`; mismatch is `RECONCILIATION_REQUIRED`.

## Phase 9 Exit Gate
- [ ] split fulfillment works;
- [ ] over-fulfillment race blocked;
- [ ] provider timeout does not duplicate AWB;
- [ ] tracking events append-only;
- [ ] NDR audited;
- [ ] COD settlement reconciled separately from delivery.

---

# 18. Phase 10 — Returns

**Goal:** reverse-logistics lifecycle separated from inventory and refund facts.

| ID | Task | Depends on |
|---|---|---|
| RET-001 | Return/return-item schema | Orders,Fulfillment,Payments |
| RET-002 | Return eligibility service | RET-001 |
| RET-003 | Customer return request API | RET-002 |
| RET-004 | Admin approve/reject | RET-003 |
| RET-005 | Return receive/disposition | RET-004,Inventory |
| RET-006 | Restock/damaged inventory integration | RET-005 |
| RET-007 | Return-linked refund | RET-005,Payments |
| RET-008 | Return close rules | RET-007 |
| RET-009 | Over-return concurrency tests | RET-003 |
| RET-010 | Duplicate receive/restock race test | RET-005 |

## Phase 10 Exit Gate
- [ ] return request alone changes no stock/money;
- [ ] approved qty cannot exceed returnable;
- [ ] duplicate receive does not restock twice;
- [ ] damaged item not sellable;
- [ ] refund based on original order allocation.

---

# 19. Phase 11 — CMS + SEO + Notifications

## CMS / SEO

| ID | Task | Depends on |
|---|---|---|
| CMS-001 | Page/blog schema | Foundation |
| CMS-002 | Page CRUD/publish | CMS-001 |
| CMS-003 | Blog/category CRUD/publish | CMS-001 |
| CMS-004 | Navigation schema/tree | CMS-001 |
| CMS-005 | Navigation cycle validation | CMS-004 |
| CMS-006 | SEO metadata | CMS-001 |
| CMS-007 | Redirects + loop protection | CMS-006 |
| CMS-008 | Public CMS APIs | CMS-002,CMS-003,CMS-004 |
| CMS-009 | Sanitization/XSS tests | CMS-002,CMS-003 |
| CMS-010 | Cache invalidation | CMS-002 |

## Notifications

| ID | Task | Depends on |
|---|---|---|
| NOT-001 | Notification template schema | Foundation |
| NOT-002 | Template rendering contract | NOT-001 |
| NOT-003 | Delivery schema | NOT-001 |
| NOT-004 | Notification provider port | NOT-003 |
| NOT-005 | Email provider adapter | NOT-004 |
| NOT-006 | Queue/enqueue via outbox | NOT-003,FND outbox |
| NOT-007 | Delivery worker/retry | NOT-006 |
| NOT-008 | Order/payment/shipment templates | NOT-007 |
| NOT-009 | Delivery logs/admin | NOT-003 |
| NOT-010 | Dedupe/retry tests | NOT-007 |

## Phase 11 Exit Gate
- [ ] draft content not public;
- [ ] stored XSS tests;
- [ ] redirect loop/open redirect blocked;
- [ ] notification failure cannot roll back order;
- [ ] duplicate domain event does not spam customer.

---

# 20. Phase 12 — Integrations + Outbound Webhooks + Bulk + Operations

## Integrations

| ID | Task | Depends on |
|---|---|---|
| INT-001 | Integration config schema | Foundation |
| INT-002 | Secret storage abstraction | INT-001 |
| INT-003 | Integration CRUD/health | INT-002 |
| INT-004 | Provider connection tests | INT-003 |

## Outbound webhooks

| ID | Task | Depends on |
|---|---|---|
| WHK-001 | Webhook subscription/delivery schema | Outbox |
| WHK-002 | Subscription CRUD | WHK-001 |
| WHK-003 | SSRF-safe endpoint validator | WHK-002 |
| WHK-004 | Versioned payload/signing | WHK-001 |
| WHK-005 | Delivery dispatcher | WHK-004 |
| WHK-006 | Retry/backoff/disable | WHK-005 |
| WHK-007 | Delivery history/retry API | WHK-006 |
| WHK-008 | SSRF/retry tests | WHK-003,WHK-006 |

## Bulk

| ID | Task | Depends on |
|---|---|---|
| BLK-001 | Bulk job/item schema | Foundation |
| BLK-002 | Create/list/detail/cancel job | BLK-001 |
| BLK-003 | Worker claim/checkpoint | BLK-001 |
| BLK-004 | Product import | BLK-003,Catalog |
| BLK-005 | Price import | BLK-003,Pricing |
| BLK-006 | Order export | BLK-003,Orders |
| BLK-007 | Error/result file | BLK-003 |
| BLK-008 | Crash/resume tests | BLK-003 |

## Operations

| ID | Task | Depends on |
|---|---|---|
| OPS-001 | Outbox backlog metrics | Outbox |
| OPS-002 | Worker failure metrics | Workers |
| OPS-003 | Audit admin APIs | Audit |
| OPS-004 | Reconciliation queues | Payments/Shipping/COD |
| OPS-005 | Provider circuit breaker policies | Providers |
| OPS-006 | Operational dashboards baseline | Metrics |

## Phase 12 Exit Gate
- [ ] secrets never returned decrypted;
- [ ] outbound webhook SSRF protections pass;
- [ ] webhooks at-least-once semantics documented;
- [ ] bulk jobs resume after worker crash;
- [ ] outbox/provider backlogs observable.

---

# 21. Phase 13 — Advanced Markets / Price Lists / Metafields

**P2 — implement only when approved by product/client need.**

| ID | Task | Depends on |
|---|---|---|
| ADV-001 | Market schema/context | Pricing |
| ADV-002 | Catalog availability context | ADV-001 |
| ADV-003 | Price list schema | ADV-001 |
| ADV-004 | Price list item resolution | ADV-003 |
| ADV-005 | Storefront market resolver | ADV-002 |
| ADV-006 | Checkout contextual repricing | ADV-004,Checkout |
| ADV-007 | Metafield definitions | Catalog |
| ADV-008 | Typed metafield values | ADV-007 |
| ADV-009 | Metafield APIs | ADV-008 |
| ADV-010 | Privileged price-context tests | ADV-006 |

## Exit Gate
- [ ] public client cannot select privileged raw price list;
- [ ] contextual pricing remains server resolved;
- [ ] historical orders untouched;
- [ ] typed metafields cannot execute arbitrary code.

---

# 22. Phase 14 — Production Hardening / Launch

**Goal:** prove the engine is operationally safe, not merely feature-complete.

## Security

| ID | Task |
|---|---|
| SEC-001 | IDOR/store-isolation review |
| SEC-002 | RBAC privilege escalation review |
| SEC-003 | webhook signature/replay review |
| SEC-004 | SSRF review |
| SEC-005 | secret/log redaction review |
| SEC-006 | auth rate-limit/credential stuffing tests |
| SEC-007 | CMS stored-XSS/CSP review |
| SEC-008 | dependency vulnerability audit |

## Reliability

| ID | Task |
|---|---|
| REL-001 | Outbox crash/replay chaos test |
| REL-002 | Redis outage behavior |
| REL-003 | payment provider outage/reconcile |
| REL-004 | shipping provider outage/reconcile |
| REL-005 | worker restart/lease recovery |
| REL-006 | checkout expiry backlog recovery |
| REL-007 | backup restore test |

## Performance

| ID | Task |
|---|---|
| PERF-001 | catalog list load test |
| PERF-002 | cart mutation load test |
| PERF-003 | checkout concurrency load test |
| PERF-004 | inventory hot-SKU contention test |
| PERF-005 | order admin pagination test |
| PERF-006 | DB query/index review |
| PERF-007 | N+1 detection |
| PERF-008 | worker throughput test |

## Database

| ID | Task |
|---|---|
| DBH-001 | migration fresh-install test |
| DBH-002 | migration upgrade-chain test |
| DBH-003 | schema/doc consistency audit |
| DBH-004 | index/constraint verification |
| DBH-005 | backup/PITR plan |
| DBH-006 | retention/data cleanup jobs |

## Release

| ID | Task |
|---|---|
| RLS-001 | production `.env` validation |
| RLS-002 | TLS/Nginx/internal route boundary |
| RLS-003 | API/worker process management |
| RLS-004 | health/readiness monitoring |
| RLS-005 | alert rules |
| RLS-006 | smoke tests |
| RLS-007 | rollback/forward-fix runbook |
| RLS-008 | first-client launch checklist |

---

# 23. First Production Release Scope Recommendation

Do not wait for every P1/P2 feature before first usable client launch.

Recommended **Release 1 Core**:

```text
Store
IAM/RBAC
Customers
Catalog
Variants
Media
Collections
Inventory
Cart
Basic Discounts
Checkout
Orders
Razorpay
Refund basics
Shiprocket
Fulfillment
Tracking
CMS basics
Notifications
Audit/Outbox
```

Can remain later:

```text
Stripe
Delhivery
advanced markets
B2B price lists
advanced metafields
complex discount combinations
full ERP app ecosystem
advanced bulk operations
```

---

# 24. Critical Path

The implementation critical path is:

```text
Foundation
→ IAM
→ Catalog
→ Inventory
→ Cart/Pricing
→ Checkout
→ Order
→ Payment
→ Fulfillment
```

Do not spend weeks on CMS or P2 metafields while atomic inventory/checkout/payment
correctness is unfinished.

---

# 25. Codex Parallelization Strategy

Safe parallel work after stable contracts:

```text
Catalog read APIs      || Media provider
CMS                    || Notification templates
Admin query services   || Storefront query services
Provider adapters      || Core domain tests
```

Avoid parallel modification of the same transactional core:

```text
CompleteCheckout
Inventory reservation
Order creation
Payment transition
```

unless one developer/agent owns integration.

---

# 26. Commit / PR Strategy

Prefer one task or tightly coupled slice per PR/commit group.

Examples:

```text
feat(inventory): add atomic reservation
test(inventory): add concurrent oversell coverage

feat(payments): add razorpay webhook inbox
test(payments): verify webhook replay dedupe
```

Avoid:

```text
"implement ecommerce backend"
```

with hundreds of unrelated files.

---

# 27. Codex Review Loop

For every important task:

```text
1. IMPLEMENT
2. RUN focused tests
3. SELF-REVIEW against docs
4. Ask Codex/reviewer:
   "Review this slice against AGENTS.md, BUSINESS_LOGIC.md,
    API_ARCHITECTURE.md and DB_SCHEMA.md.
    Report deviations before editing."
5. Fix approved findings
6. Re-run tests
7. Mark task complete
```

For P0 tasks, use an independent review prompt/session where practical.

---

# 28. Task Completion Record

Maintain a status table in `docs/STATUS.md`.

Suggested format:

| Task | Status | Commit/PR | Tests | Notes |
|---|---|---|---|---|
| FND-001 | DONE | `abc123` | scaffold smoke | — |
| INV-007 | IN_PROGRESS | — | concurrency pending | P0 |
| PAY-008 | NOT_STARTED | — | — | — |

Allowed statuses:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
IMPLEMENTED_UNVERIFIED
VERIFIED
DEFERRED
```

Do not label `VERIFIED` without evidence.

---

# 29. Blocker Policy

Mark a task BLOCKED when implementation requires an unresolved decision such as:

- unclear state transition;
- contradictory schema/business rule;
- missing provider contract;
- destructive migration decision;
- unknown refund ownership;
- missing required environment/secret;
- conflict with existing implementation.

Do not “solve” the blocker by inventing behavior.

---

# 30. Migration Sequencing

For each module:

```text
schema decision
→ ORM
→ migration
→ migration test
→ repository
→ domain/application
→ API
→ tests
```

For risky live changes:

```text
EXPAND
→ compatible code
→ backfill
→ switch
→ verify
→ CONTRACT
```

---

# 31. API Implementation Sequencing

Within one resource:

```text
domain rule
→ application command/query
→ persistence
→ API schema
→ route
→ error mapping
→ permission
→ contract test
```

Do not start from route and invent domain behavior inside it.

---

# 32. Provider Integration Sequencing

Payment/shipping provider:

```text
port DTO
→ fake adapter
→ application behavior tests
→ concrete provider adapter
→ sandbox/contract test
→ timeout/retry behavior
→ webhook intake
→ reconciliation
→ production enablement
```

This keeps provider SDK behavior from defining domain rules.

---

# 33. P0 Test Gates

The following cannot be considered complete without the stated test:

| Capability | Required evidence |
|---|---|
| Inventory reserve | real PostgreSQL race |
| Reservation release/commit | duplicate replay |
| Checkout complete | concurrent same-key idempotency |
| Refresh token rotation | concurrent replay |
| Payment webhook | invalid signature + duplicate replay |
| Refund | concurrent over-refund |
| Fulfillment | concurrent over-fulfillment |
| Shipment create | provider timeout duplicate-AWB safety |
| Return receive | duplicate restock race |
| Transfer receive | duplicate receipt race |

---

# 34. Definition of Done per Task

A task is complete when:

- [ ] approved scope implemented;
- [ ] no unrelated refactor;
- [ ] architecture boundaries respected;
- [ ] DB migration exists if required;
- [ ] request/response matches API contract;
- [ ] business pre/post conditions pass;
- [ ] permissions implemented;
- [ ] errors stable;
- [ ] tests appropriate to risk pass;
- [ ] docs updated if contract changed;
- [ ] completion evidence reported;
- [ ] no hidden P0 risk remains.

---

# 35. Definition of Done per Phase

A phase is complete only when:

- all P0 tasks in phase are VERIFIED;
- migrations apply from clean database;
- focused module suite passes;
- relevant cross-module regression passes;
- no unresolved architecture drift;
- STATUS.md updated;
- exit gate explicitly reviewed.

---

# 36. What Not to Ask Codex

Avoid prompts like:

```text
Build the whole backend.
Make Shopify clone.
Implement all APIs.
Create all database models and services.
Finish entire checkout/payment/shipping.
```

These prompts maximize hidden inconsistencies.

Prefer:

```text
Implement INV-007 Atomic Reservation only.
Do not modify checkout/payment.
Use existing inventory schema.
Add concurrency test.
```

---

# 37. Example Codex Prompt — Foundation

```text
MODE: IMPLEMENTATION

TASK ID: FND-006
GOAL: Implement SQLAlchemy 2.x asynchronous PostgreSQL session foundation.

READ:
- AGENTS.md
- ARCHITECTURE.md DB/UoW sections

DEPENDENCIES:
FND-001, FND-002, FND-004

ACCEPTANCE:
- AsyncEngine + async_sessionmaker
- no global shared AsyncSession
- transaction rollback support
- clean shutdown
- disposable test DB override

EXPECTED:
app/db/session.py
app/db/base.py
tests/integration/db/

NON-GOALS:
Alembic migrations
business models
Redis

VALIDATION:
run focused integration DB tests.
```

---

# 38. Example Codex Prompt — Atomic Inventory

```text
MODE: IMPLEMENTATION

TASK ID: INV-007

GOAL:
Implement atomic inventory reservation with no overselling.

READ:
- AGENTS.md
- ARCHITECTURE.md Inventory/UoW sections
- docs/BUSINESS_LOGIC.md Inventory
- docs/API_ARCHITECTURE.md Inventory reserve
- docs/DB_SCHEMA.md Inventory
- relevant inventory ADR

DEPENDENCIES:
INV-001 through INV-006

ACCEPTANCE:
- authoritative PostgreSQL reservation
- deterministic locking
- all-or-nothing checkout reservation
- OUT_OF_STOCK conflict
- reservation evidence
- no provider/network call
- transaction remains short

TESTS:
- unit policy tests
- repository integration
- stock=5 / 10 concurrent requests
- duplicate reservation behavior
- transaction rollback

NON-GOALS:
checkout HTTP route
payment
shipping
```

---

# 39. Example Codex Prompt — Payment Webhook

```text
MODE: IMPLEMENTATION

TASK ID: PAY-008/PAY-009

GOAL:
Implement safe Razorpay webhook intake and durable dedupe.

READ:
- AGENTS.md
- BUSINESS_LOGIC Payments
- API_ARCHITECTURE payment webhooks
- DB_SCHEMA payment_provider_events
- ARCHITECTURE provider/webhook sections

ACCEPTANCE:
- raw request body used for signature verification
- invalid signature cannot mutate payment state
- durable event inbox
- unique provider external event identity
- duplicate valid delivery returns safe ACK
- no order mutation directly in route
- heavy processing deferred to application worker/command

TESTS:
- valid signature
- invalid signature
- duplicate event x5
- malformed payload
```

---

# 40. Example Codex Prompt — Complete Checkout

```text
MODE: IMPLEMENTATION

TASK ID: ORD-006

GOAL:
Create exactly one immutable order from one valid checkout.

DEPENDENCIES:
Checkout, Inventory, Promotions, Order schema, Idempotency infrastructure.

READ:
- AGENTS.md
- BUSINESS_LOGIC Checkout + Orders + Inventory + Payments
- API_ARCHITECTURE checkout complete
- DB_SCHEMA checkout/orders/inventory/idempotency
- ARCHITECTURE UoW/cross-module facades

ACCEPTANCE:
- atomic idempotency claim
- same key same body replay
- same key different body 409
- checkout state revalidated
- immutable order snapshot
- inventory reservation consumed exactly once (`ACTIVE → CONSUMED`)
- discount redemption exactly once
- outbox order.created written in transaction
- no payment/shipping/email HTTP calls inside transaction

TESTS:
- success
- stale/expired checkout
- same key replay
- same key different payload
- 10 concurrent same-key calls → one order
- rollback on order line failure
```

---

# 41. Suggested Release Milestones

## Milestone A — Admin Commerce Foundation
After Phase 4:

```text
Store
IAM
Customers
Catalog
Inventory
```

Useful for internal/admin testing.

## Milestone B — Offline/COD Store
After Phase 7 plus permitted offline/COD order flow:

```text
Cart
Checkout
Order
Inventory
Basic discount
```

Can support limited controlled selling without online gateway if product approves.

## Milestone C — Online Commerce
After Phase 9:

```text
Razorpay
Refund
Fulfillment
Shiprocket
Tracking
```

Main reusable production backend.

## Milestone D — Merchant Product
After Phase 12:

```text
CMS
Notifications
Integrations
Bulk
Operational tooling
```

## Milestone E — Platform Expansion
Phase 13+:

```text
Markets
Price lists
advanced extensions
future SaaS capabilities
```

---

# 42. First Client Deployment Strategy

Do not customize backend by forking business logic.

For first client:

```text
same LinkUp Commerce image
+
client environment
+
client database
+
client store config
+
client providers
+
custom frontend
```

Track client-only feature requests separately.

Promote reusable features back into canonical engine only through approved task/ADR.

---

# 43. Branching Recommendation

Simple approach:

```text
main
feature/FND-006-db-session
feature/INV-007-atomic-reservation
feature/PAY-008-razorpay-webhook
```

Keep branches short-lived.

Do not maintain long-running divergent client backend branches if configuration can
solve the requirement.

---

# 44. CI Gate Recommendation

PR checks should eventually include:

```text
ruff / formatting
type checks
unit tests
PostgreSQL integration tests
architecture dependency tests
migration head check
OpenAPI contract checks
target concurrency tests when affected
```

Full expensive race/load tests may run on merge/nightly while affected P0 focused
race tests should still run before acceptance.

---

# 45. Implementation Metrics

Track engineering progress by verified behavior, not line count.

Useful:

```text
tasks VERIFIED / phase
P0 tasks remaining
migration heads
test pass/fail/skip
known P0 blockers
OpenAPI implemented endpoints
concurrency invariants verified
provider reconciliation scenarios verified
```

Do not use “number of APIs generated” as production readiness.

---

# 46. Risk-Based Review Priority

Review order:

```text
1. Inventory
2. Checkout
3. Payment
4. Refund
5. Order cancellation
6. Fulfillment
7. Return/restock
8. Auth/RBAC
9. Provider webhooks
10. Everything else
```

A CMS layout bug is less dangerous than a double-refund or oversell race.

---

# 47. Documentation Freeze Before Broad Implementation

Before starting many tasks in parallel, freeze:

- module names;
- critical state machines;
- P0 DB tables;
- money model;
- idempotency pattern;
- inventory reservation model;
- order snapshot model;
- provider boundary;
- API error envelope.

If these move every week, Codex will produce conflicting slices.

---

# 48. Implementation Review Questions

At the end of each P0 task ask:

1. What is the source of truth?
2. Who owns the transaction?
3. What can race?
4. Is the operation idempotent?
5. What happens on retry?
6. What happens after process crash?
7. What happens on provider timeout?
8. What evidence remains?
9. Can a duplicate request double money/stock?
10. Does this mutate another module's state directly?
11. Does frontend assert a value it should not control?
12. Which test proves the invariant?

---

# 49. Project Completion Criteria

The engine is ready for first production client only when:

- P0 Release 1 modules are VERIFIED;
- production migrations are tested;
- core concurrency tests pass;
- payment webhook/reconciliation tests pass;
- backup/restore validated;
- internal routes restricted;
- secrets configured safely;
- alerting/health active;
- no unresolved P0 blocker;
- launch smoke test passes;
- first-client configuration does not require hidden backend hacks.

---

# 50. Final Execution Rule

## 51. Documentation Remediation Freeze Addendum

Phase gates must use the canonical states and schema decisions in the canonical
documents. Phase 0 remains `NOT STARTED` until the repository bootstrap creates
runtime scaffolding, migration/test infrastructure, and `STATUS.md` evidence.
First-client delivery follows the bounded Release 1 scope in `docs/FINAL_SDR.md`;
architecture inventory priority must not be interpreted as permission to launch
all 88 P0 APIs or any P2 capability.

Codex should optimize for:

```text
small task
→ correct task
→ tested task
→ reviewed task
→ documented task
```

not:

```text
maximum code generation per prompt
```

The implementation plan may evolve, but **phase dependencies and P0 safety gates
must not be bypassed silently**.

If a task discovers that the architecture/business specification is wrong or
incomplete, stop that slice, document the conflict, update the governing decision
with approval, then resume implementation.
