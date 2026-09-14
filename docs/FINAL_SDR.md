# LinkUp Commerce Engine — Final System Design & Requirements (SDR)

**Document type:** Final System Design & Requirements / Technical Product Specification  
**Version:** v1.0  
**Date:** 2026-09-08  
**Organization:** LinkUp Group Pvt. Ltd.  
**Technology division:** LinkUp Web  
**Product:** LinkUp Commerce Engine  
**Primary backend stack:** FastAPI + PostgreSQL + Redis + Alembic + Async Workers  
**Primary frontend strategy:** Custom Next.js storefront/admin experiences per client  
**Architecture style:** Modular Monolith + Domain Modules + Unit of Work + Ports/Adapters + Transactional Outbox  
**Deployment model:** One client deployment/VPS/database initially; store-scoped architecture retained for future shared multi-store/SaaS evolution

> **Wave A canonical override (2026-09-10):** `docs/audits/API_CANONICAL_CONTRACT_DECISIONS.md` is the authoritative contract-decision register. It resolves legacy illustrative conflicts, including return disposition (`RESTOCK|DAMAGED|DISCARD|INSPECT`; `REJECTED` is a workflow state only), without asserting current mock conformance.

---

# 1. Executive Summary

LinkUp Commerce Engine is a reusable, production-grade e-commerce backend intended
to let LinkUp Web deliver custom branded online stores faster without rebuilding
commerce fundamentals from scratch for every client.

The platform is not intended to be a generic low-code storefront builder in the
first release. Instead, the operating model is:

```text
One hardened reusable commerce backend codebase
        +
repeatable deployment template
        +
client-specific VPS / environment / database
        +
client-specific provider configuration
        +
fully custom Next.js storefront/UI/UX
```

The engine is designed to support most standard Shopify-like commerce capabilities
while preserving LinkUp Web's ability to deliver custom design, custom workflows,
and client-specific integrations.

The system prioritizes:

- commerce correctness;
- reusable backend modules;
- safe inventory and checkout;
- immutable order and financial evidence;
- payment-provider independence;
- split fulfillment and returns;
- CMS/SEO controls;
- asynchronous side effects;
- auditability;
- operational recovery;
- future SaaS/multi-store evolution.

The first version is deliberately a **modular monolith**, not a microservice
platform.

---

# 2. Product Vision

## 2.1 Business objective

Enable LinkUp Web to build e-commerce clients using:

```text
Reusable commerce engine
        ↓
Client-specific configuration
        ↓
Custom storefront
        ↓
Fast delivery
        ↓
Lower engineering duplication
        ↓
Higher reliability
```

## 2.2 Product positioning

LinkUp Commerce is:

- a reusable commerce backend;
- a configurable commerce foundation;
- a custom-store enablement engine;
- future-ready for more platform behavior.

It is not initially:

- a public Shopify competitor;
- a full multi-tenant SaaS billing platform;
- an app marketplace;
- a theme marketplace;
- a public developer ecosystem;
- a microservice mesh.

---

# 3. Current Deployment Model

Each client receives an isolated deployment.

```text
Client A
├── custom storefront
├── LinkUp Commerce API
├── client DB
├── client Redis
├── client workers
└── client provider configuration

Client B
├── custom storefront
├── same LinkUp Commerce codebase
├── separate DB
├── separate Redis
└── separate configuration
```

Each deployment normally has one active store, but the schema remains store-scoped.

### Why keep `store_id` now?

- future shared multi-store migration;
- scoped uniqueness;
- safer data ownership;
- cleaner module contracts;
- better test isolation;
- avoids a large future rewrite.

---

# 4. Future Evolution Model

Potential future progression:

```text
Stage 1
One client = one deployment/database

Stage 2
Central deployment tooling and standard configuration

Stage 3
Optional shared platform services

Stage 4
Shared multi-store runtime where justified

Stage 5
Potential public SaaS/platform capabilities
```

Future SaaS functionality must not be implemented prematurely.

---

# 5. Core Architectural Principles

1. **Modular monolith first**
2. **PostgreSQL is canonical commerce truth**
3. **Redis is cache/ephemeral infrastructure**
4. **Business logic belongs in domain/application layers**
5. **Routes stay thin**
6. **Modules do not mutate foreign ORM state**
7. **Cross-module operations use explicit facades/ports**
8. **One explicit transaction owner per business command**
9. **External provider calls occur outside core DB locks**
10. **Money uses Decimal / NUMERIC**
11. **Order/payment/inventory evidence is immutable**
12. **State changes use explicit state machines**
13. **Retry-prone commands are idempotent**
14. **Async side effects use transactional outbox**
15. **At-least-once delivery is assumed**
16. **Security and store/customer ownership fail closed**
17. **P0 concurrency claims require real PostgreSQL tests**
18. **Client customization is configuration-driven, not hidden code forks**

---

# 6. Documentation Authority

This SDR is the master product/system summary.

Detailed documents remain authoritative in their specific areas.

| Document | Authority |
|---|---|
| `AGENTS.md` | repository/Codex operating contract |
| `ARCHITECTURE.md` | repository/runtime/module dependency design |
| `docs/DB_SCHEMA.md` | database/table/constraint/index detail |
| `docs/BUSINESS_LOGIC.md` | domain invariants, rules, pre/post conditions |
| `docs/API_ARCHITECTURE.md` | API endpoint/request/response/error/permission detail |
| `docs/TESTING_STRATEGY.md` | detailed test architecture when finalized |
| `docs/adr/*` | historical/accepted architecture decisions |
| `docs/STATUS.md` | current implementation reality |
| `docs/implementation/IMPLEMENTATION_PLAN.md` | Codex execution sequence |

If this SDR conflicts with a more detailed accepted domain specification, resolve the
conflict explicitly rather than silently inventing behavior.

---

# 7. Product Scope by Priority

## P0 — Core production commerce

Required for reliable production launch:

- Store foundation
- Staff authentication
- RBAC
- Customers
- Catalog
- Variants/options
- Media
- Inventory locations
- Inventory ledger
- Inventory reservation
- Cart
- Checkout
- Orders
- Basic pricing
- Basic discounts/coupons
- Payment intents
- Razorpay payment
- Payment webhooks
- Refund foundation
- Fulfillment
- Shipments
- Tracking
- Returns baseline
- CMS baseline
- Notifications
- Idempotency
- Transactional outbox
- Audit
- Operational health

## P1 — Standard reusable merchant capability

- Advanced collections/tags
- Advanced discount rules
- Multiple shipping providers
- NDR
- COD remittance reconciliation
- Bulk import/export
- Outbound webhooks
- Integration management
- Rich CMS/SEO
- Delivery templates
- Advanced admin projections
- transfer workflows
- better reconciliation tooling

## P2 — Advanced platform capability

- Markets
- International pricing
- Price lists
- B2B pricing
- advanced metafields
- advanced channel support
- public app ecosystem
- shared multi-store runtime
- platform billing
- tenant provisioning
- organization hierarchy
- complex merchant extension framework

---

# 8. Functional Module Map

The approved architecture contains the following domains.

| # | Module | Core responsibility | Priority |
|---:|---|---|:---:|
| 1 | Store | store identity, domains, settings, sales channels | P0/P1 |
| 2 | IAM | staff login, sessions, roles, permissions | P0 |
| 3 | Customers | shopper profile, addresses, consent | P0/P1 |
| 4 | Catalog | products, variants, options, media, collections | P0/P1 |
| 5 | Inventory | stock, locations, reservations, movements, transfers | P0 |
| 6 | Pricing | authoritative prices, market/catalog context | P0/P2 |
| 7 | Promotions | coupons, discounts, eligibility, redemption | P0/P1 |
| 8 | Cart | mutable shopping intent | P0 |
| 9 | Checkout | transaction-session orchestration | P0 |
| 10 | Orders | immutable commercial order snapshot | P0 |
| 11 | Payments | payment intents, transactions, provider events, refunds | P0 |
| 12 | Fulfillment | fulfillment, shipments, tracking, NDR, COD | P0/P1 |
| 13 | Returns | return workflow and disposition | P1 |
| 14 | CMS | pages, blogs, navigation, SEO, redirects | P1 |
| 15 | Notifications | transactional communication | P0/P1 |
| 16 | Integrations | provider configuration, outbound webhooks | P1 |
| 17 | Audit | privileged/security evidence | P0 |
| 18 | Bulk | large import/export jobs | P1 |
| 19 | Reliability | idempotency, outbox, operational workers | P0 |

---

# 9. Canonical Repository Architecture

```text
linkup-commerce/
│
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
│
├── app/
│   ├── main.py
│   ├── bootstrap.py
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── cache/
│   ├── events/
│   ├── workers/
│   └── observability/
│
├── modules/
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
├── shared/
├── migrations/
├── tests/
├── docs/
├── scripts/
└── deploy/
```

---

# 10. Domain Module Architecture

Each domain follows:

```text
modules/<domain>/
├── presentation/
│   └── http/
├── application/
│   ├── commands/
│   ├── queries/
│   ├── ports/
│   ├── dto/
│   └── facade.py
├── domain/
│   ├── entities.py
│   ├── value_objects.py
│   ├── policies.py
│   ├── states.py
│   ├── events.py
│   └── exceptions.py
└── infrastructure/
    ├── db/
    ├── cache/
    └── providers/
```

### Layer rule

```text
Presentation
     ↓
Application
     ↓
Domain

Infrastructure
     ↑
implements application ports
```

Domain must remain framework-free.

---

# 11. Cross-Module Ownership Rules

The owning module is the only module allowed to mutate canonical state.

Examples:

```text
Checkout cannot directly update Inventory ORM.
Orders cannot directly update Payment ORM.
Fulfillment cannot directly edit Order items.
Returns cannot directly edit Payment transaction rows.
```

Instead:

```text
Checkout
   ↓
InventoryFacade.reserve()

Returns
   ↓
PaymentsFacade.request_refund()
```

No internal localhost HTTP between modules.

---

# 12. Database Architecture Summary

The approved DB design contains approximately:

- **16 logical schema groups**
- **86 tables**
- **43 P0**
- **34 P1**
- **9 P2**

Detailed fields, indexes and relationships belong in `docs/DB_SCHEMA.md`.

## 12.1 Core database conventions

- PK: UUID
- Money: `NUMERIC(19,4)`
- Currency: `CHAR(3)`
- Time: `TIMESTAMPTZ`
- Flexible metadata: JSONB only where genuinely flexible
- Status: controlled enum/check/application enum
- Historical ledgers: append-only
- Store ownership: `store_id`
- Migrations: Alembic only

---

# 13. Database Domain Groups

## Store Foundation

```text
stores
store_domains
store_settings
sales_channels
```

## IAM

```text
users
roles
permissions
role_permissions
staff_members
staff_member_roles
refresh_tokens
```

## Customers

```text
customers
customer_addresses
customer_consents
```

## Catalog

```text
products
product_options
product_option_values
product_variants
variant_option_values
media_assets
product_media
collections
collection_products
tags
product_tags
metafield_definitions
metafields
```

## Inventory

```text
locations
inventory_items
inventory_levels
inventory_reservations
inventory_movements
inventory_transfers
inventory_transfer_items
```

## Pricing

```text
markets
catalogs
catalog_products
price_lists
price_list_items
```

## Promotions

```text
discounts
discount_codes
discount_rules
discount_targets
discount_redemptions
```

## Cart / Checkout

```text
carts
cart_lines
checkout_sessions
checkout_lines
checkout_addresses
checkout_shipping_rates
```

## Orders

```text
orders
order_items
order_addresses
order_discount_allocations
order_tax_lines
order_status_history
```

`order_items.order_id` is mandatory and references `orders.order_id`; the canonical
relationship is `orders 1 → N order_items`, with no orphan order items.

## Payments

```text
payment_intents
payment_transactions
payment_provider_events
refunds
refund_items
```

## Fulfillment

```text
fulfillments
fulfillment_items
shipments
shipment_events
ndr_events
cod_remittances
```

## Returns

```text
returns
return_items
```

## CMS

```text
pages
blog_categories
blog_posts
navigation_menus
navigation_items
seo_metadata
redirects
```

## Notifications

```text
notification_templates
notification_deliveries
```

## Integrations

```text
integrations
webhook_subscriptions
webhook_deliveries
```

## Reliability

```text
idempotency_records
outbox_events
audit_logs
bulk_jobs
bulk_job_items
```

---

# 14. API Architecture Summary

Estimated API surface:

- **227 APIs**
- **88 P0**
- **120 P1**
- **19 P2**

Detailed contracts remain in `docs/API_ARCHITECTURE.md`.

Canonical route surfaces:

```text
/api/v1/storefront
/api/v1/admin
/api/v1/auth
/api/v1/webhooks
/api/v1/internal
```

---

# 15. API Contract Rules

Common headers may include:

```text
Authorization: Bearer <token>
X-Request-ID
Idempotency-Key
If-Match / version
Content-Type: application/json
```

Success envelope:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_..."
  }
}
```

Error envelope:

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

---

# 16. Standard HTTP Semantics

| Status | Usage |
|---:|---|
| 200 | read/update/idempotent replay |
| 201 | synchronous create |
| 202 | accepted async work |
| 204 | successful delete/revoke with no body |
| 400 | malformed business request |
| 401 | unauthenticated |
| 403 | forbidden |
| 404 | absent or hidden by ownership |
| 409 | state/version/idempotency/business conflict |
| 410 | expired resource where useful |
| 422 | schema validation |
| 429 | throttled |
| 502/503 | upstream failure when request cannot safely be accepted |

---

# 17. Global Business Invariants

## 17.1 Server authority

Frontend never controls authoritative:

- price;
- discount;
- tax;
- shipping rate;
- stock;
- payment state;
- refund eligibility;
- order lifecycle.

## 17.2 Money

Never use float.

```text
Python → Decimal
JSON → decimal string
PostgreSQL → NUMERIC(19,4)
```

## 17.3 History

Do not rewrite final evidence.

Use:

- reversal;
- adjustment;
- refund;
- return;
- reconciliation;
- status history.

## 17.4 Store scope

`store_id` comes from authenticated/deployment context, not request-body authority.

---

# 18. Product Catalog Rules

- product starts DRAFT;
- product cannot publish unless complete;
- variant is the sellable SKU unit;
- SKU is store scoped;
- exact option combination is unique per product;
- catalog price is current, not historical;
- product archive does not delete historical references;
- order snapshot is independent from later catalog changes;
- media uses direct signed storage workflow;
- rich content must be sanitized.

---

# 19. Inventory Truth Model

Inventory uses:

```text
Current projected level
+
Active reservations
+
Append-only movements
```

Conceptual availability:

```text
available = on_hand - reserved - damaged

Release 1 inventory levels are exactly `on_hand`, `reserved`, `incoming`, and
`damaged`; `incoming` is not sellable. Inventory policy is `DENY` only. Reservation
states are only `ACTIVE → CONSUMED | RELEASED | EXPIRED`, with deterministic row
locking/conditional updates and level plus append-only movement written atomically.
```

Key invariants:

- stock cannot oversell;
- every physical stock change has movement evidence;
- reservation is atomic;
- release/consume are idempotent;
- inventory DB enforces `on_hand >= 0`, `reserved >= 0`, `incoming >= 0`, `damaged >= 0`, and `reserved + damaged <= on_hand`;
- reserve increments only `reserved` with no physical movement; release/expire decrements only `reserved` with no physical movement; consume decrements `on_hand` and `reserved` and writes exactly one `RESERVATION_CONSUME` movement;
- transfer lifecycle is `DRAFT → IN_TRANSIT → PARTIALLY_RECEIVED → RECEIVED`, with valid `CANCELLED` side transition;
- reconciliation writes an adjustment movement;
- direct generic stock patch is forbidden.

---

# 20. Inventory Concurrency Requirement

Example:

```text
stock = 5

10 concurrent reservation requests

expected:
5 success
5 OUT_OF_STOCK
```

This must be verified on real PostgreSQL.

SQLite/fake repository evidence is insufficient.

---

# 21. Pricing Pipeline

Canonical pipeline:

```text
current variant/context price
        ↓
line subtotal
        ↓
discount eligibility/allocation
        ↓
taxable base
        ↓
tax
        ↓
shipping
        ↓
shipping tax/discount if applicable
        ↓
grand total
```

One authoritative pricing pipeline must be reused by storefront checkout and
admin/manual order completion.

Release 1 inventory policy is `DENY` only. `CONTINUE`/backorder behavior is
deferred until an explicitly approved complete backorder design exists.

Tax is server-authoritative and calculated by a dedicated service. Orders persist
immutable tax lines, support place-of-supply and intra/inter-state capability,
and historical tax never changes. **DECISION REQUIRED — GST POLICY:** GST
registrations, CGST/SGST/IGST rules, HSN/SAC, shipping tax, tax-inclusive policy,
rounding, and invoice/credit-note compliance require business/compliance
validation and must not be invented during implementation.

---

# 22. Discount Rules

Discount preview:

```text
side-effect free
```

Redemption:

```text
recorded exactly once at the approved order/payment business point
```

Usage limits require a redemption ledger and concurrency protection.

Do not treat mutable `used_count` alone as financial truth.

---

# 23. Cart Model

Cart is:

- mutable;
- durable;
- PostgreSQL-backed;
- optionally cached in Redis.

Cart contains intent, not final commercial truth.

Cart line requests do not control final price/stock.

---

# 24. Checkout Model

Checkout is a separate short-lived transaction session.

```text
Cart
  ↓
Checkout Session
  ↓
Pricing
  ↓
Shipping
  ↓
Inventory Reservation
  ↓
Payment
  ↓
Order
```

Checkout is versioned and expires.

---

# 25. Checkout State Machine

Canonical Release 1:

```text
OPEN
 ↓
PRICED
 ↓
INVENTORY_RESERVED
 ↓
PAYMENT_PENDING
 ↓
COMPLETED
```

Side exits:

```text
EXPIRED
FAILED
```

---

# 26. Checkout Completion Contract

Critical transaction:

```text
claim Idempotency-Key
        ↓
revalidate checkout
        ↓
verify authoritative payment state
        ↓
create immutable order snapshots
        ↓
consume ACTIVE inventory reservation
        ↓
commit discount redemption
        ↓
write status history
        ↓
write outbox events
        ↓
COMMIT
```

After commit:

```text
notification
ERP/webhook
analytics
other side effects
```

---

# 27. Checkout Idempotency

Same request + same key:

```text
same logical result/order
```

Same key + different semantic request:

```text
409 IDEMPOTENCY_KEY_REUSED
```

Concurrent same-key requests must create only one order.

---

# 28. Order Model

Order is an immutable commercial snapshot.

Snapshot includes:

- product title;
- SKU;
- unit price;
- quantity;
- address;
- discount allocation;
- tax allocation;
- shipping;
- currency.

Later catalog/customer profile edits cannot rewrite historical order data.

---

# 29. Order State Model

Lifecycle should remain separate from financial and fulfillment projections.

Example:

```text
DRAFT
        ↓
PENDING
        ↓
CONFIRMED
        ↓
PROCESSING
        ↓
COMPLETED
```

Controlled side states:

```text
ON_HOLD
CANCELLED
```

Financial state derives from payment ledger.

Fulfillment state derives from fulfillment records.

---

# 30. Payment Architecture

Payment consists of:

```text
Payment Intent
        ↓
Provider Session
        ↓
Verified Provider Evidence
        ↓
Payment Transaction Ledger
        ↓
Derived Order Financial State
```

Browser redirect is never authoritative.

Payment intents support `CHECKOUT`, `ORDER`, and `ADMIN` origins. A checkout-origin
intent may exist before an order and is linked through `checkout_id`; an order is
created at most once per checkout through unique `(store_id, checkout_id)`. Local
request idempotency is scoped by `(store_id, operation, key)`; provider calls use a
separate provider idempotency key and bounded timeout.

`CompleteCheckoutUseCase` owns the short completion transaction: claim idempotency,
lock and revalidate checkout state/version, final totals and shipping-rate freshness,
verify ACTIVE reservations and payment rule, create the order/items/address/tax/
discount snapshots, consume reservations, commit redemption, set `orders.checkout_id`,
link the Payment Intent, write initial order history and outbox, mark checkout
completed, and save the replay response. Provider/network calls are outside this
transaction. `orders.placed_at` is NULL for DRAFT orders. The unique checkout
constraint guarantees one order even when different idempotency keys race.

---

# 31. Payment Intent State

Canonical:

```text
CREATED
 ↓
PENDING_CUSTOMER_ACTION
 ↓
PROCESSING
 ↓
AUTHORIZED
 ↓
CAPTURED
```

Side states:

```text
FAILED
CANCELLED
RECONCILIATION_REQUIRED
```

Provider-specific states are normalized.

---

# 32. Webhook Ingestion

Provider webhook route:

```text
raw body
        ↓
signature/auth verification
        ↓
provider event ID
        ↓
durable dedupe inbox
        ↓
quick ACK
        ↓
application/worker processing
```

Webhook may be repeated or out of order. Dedupe is unique on
`(store_id, provider, external_event_id)`; intake ACKs after durable insert and
processing is leased/idempotent.

---

# 33. Payment Transaction Ledger

Financial transactions are append-only.

Examples:

```text
AUTHORIZE
CAPTURE
SALE
VOID
REFUND
OFFLINE
COD
```

Do not overwrite transaction history.

---

# 34. Refund Contract

Refundable balance is server derived.

Conceptually:

```text
eligible captured value
- successful refunds
- protected pending refund value
= remaining refundable value
```

Partial refund is supported.

Concurrent over-refund must be prevented.

---

# 35. Provider Timeout Rule

Timeout is not automatically failure.

On uncertain provider result:

```text
RECONCILIATION_REQUIRED
```

Reconcile by stable local/provider reference before creating another provider action.

One checkout has at most one nonterminal online attempt per logical payment operation
(`CREATED`, `PENDING_CUSTOMER_ACTION`, `PROCESSING`, `AUTHORIZED`, or
`RECONCILIATION_REQUIRED`). Checkout expiry locks and re-reads payment state; it does
not release protected reservations blindly. A verified late CAPTURE after release or
expiry attempts atomic re-reservation; if stock is unavailable, no order is faked or
oversold and the payment enters reconciliation/refund handling.

---

# 36. Fulfillment Model

Order and shipment are not 1:1.

```text
Order
 ├── Fulfillment A
 │    └── Shipment A
 └── Fulfillment B
      └── Shipment B
```

This supports:

- multiple warehouses;
- split packages;
- partial shipment;
- partial cancellation;
- partial returns.

---

# 37. Fulfillment State

Canonical:

```text
OPEN
 ↓
PACKING
 ↓
READY
 ↓
SHIPPED
 ↓
COMPLETED
```

Side:

```text
CANCELLED
```

---

# 38. Shipment State

Canonical:

```text
CREATING
 ↓
CREATED
 ↓
PICKUP_SCHEDULED
 ↓
PICKED_UP
 ↓
IN_TRANSIT
 ↓
OUT_FOR_DELIVERY
 ↓
DELIVERED
```

Side:

```text
NDR
RTO
LOST
CANCELLED
```

Carrier events are append-only.

Old events do not blindly regress terminal state.

---

# 39. NDR

NDR workflow:

```text
OPEN
 ↓
ACTION_SUBMITTED
 ↓
RESOLVED
```

The NDR case ends only in `RESOLVED`; the associated shipment may separately
transition to `RTO`.

PII/address changes must be audited.

---

# 40. COD Reconciliation

Delivered does not automatically mean merchant received COD settlement.

COD settlement has separate reconciliation evidence.

```text
EXPECTED
 ↓
REPORTED
 ↓
RECONCILED
 ↓
SETTLED
```

Mismatch remains explicit.

The canonical mismatch state is `RECONCILIATION_REQUIRED`; only an explicitly
reconciled remittance may transition to `SETTLED`.

---

# 41. Return Model

Return request is not:

- stock receipt;
- refund;
- restock.

Separate lifecycle:

```text
REQUESTED
 ↓
APPROVED / REJECTED
 ↓
IN_TRANSIT
 ↓
RECEIVED
 ↓
REFUND_PENDING
 ↓
COMPLETED
```

---

# 42. Return Inventory Disposition

Received return item disposition may be:

```text
RESTOCK
DAMAGED
DISCARD
INSPECT
```

`REJECTED` is a return workflow state only; it is never a warehouse receipt
disposition.

Only RESTOCK increases sellable inventory.

---

# 43. CMS / SEO

CMS supports:

- pages;
- blogs;
- blog categories;
- navigation;
- SEO metadata;
- redirects.

CMS does not execute arbitrary merchant backend code.

Draft content is not public.

Rich text is sanitized.

Redirect loops/open redirects are blocked.

---

# 44. Notifications

Notifications are asynchronous.

```text
domain event
 ↓
outbox
 ↓
notification delivery
 ↓
provider
```

Provider outage does not roll back order/payment.

Duplicate events must not spam customer.

Each delivery has a deterministic `dedupe_key` and optional `source_event_id`; the
database enforces unique `(store_id, dedupe_key)`. Explicit merchant resends use a
new command/idempotency context and therefore a new dedupe key.

Marketing consent is separate from transactional communication policy.

Consent evidence always includes `channel` and explicit `purpose`. Saved customer
addresses have one overall default per customer enforced by a partial unique
constraint. Customer refresh/logout persistence is P1/deferred: staff
`refresh_tokens` are never reused for shoppers, and no dedicated customer session
table is added until separately approved.

---

# 45. Integration Boundary

Provider/integration secrets are not embedded in canonical commerce tables.

Integrations are adapters/configuration.

Examples:

```text
Razorpay
Stripe
Shiprocket
Delhivery
Email/SMS
ERP
CRM
```

Secrets should be secret-manager/encrypted references, never normal response fields.

---

# 46. Outbound Webhooks

Outbound webhooks are:

- signed;
- versioned;
- at-least-once;
- retryable;
- dedupe-friendly.

URLs require SSRF protection.

---

# 47. Transactional Outbox

Required when a committed business change must produce async side effects.

```text
business mutation
+ outbox event
= same transaction
```

Worker dispatches after commit.

This prevents:

```text
order saved
but notification/integration event lost
```

---

# 48. Idempotency Infrastructure

Used for retry-prone commands:

- checkout completion;
- refund;
- shipment create;
- provider session create;
- inventory commands where needed;
- webhook ingestion by provider event ID.

Idempotency must be DB-enforced.

Unsafe check-then-write alone is forbidden.

---

# 49. Bulk Jobs

Large import/export must be asynchronous.

Flow:

```text
job create
 ↓
QUEUED
 ↓
PROCESSING
 ↓
COMPLETED / PARTIAL / FAILED / CANCELLED
```

Workers process bounded chunks.

Crash/resume must be safe.

---

# 50. Security Architecture

## 50.1 Authentication

Merchant:

```text
access token
+ refresh token rotation
+ active staff membership
```

Customer:

```text
customer session/token
```

Guest:

```text
high-entropy opaque resource tokens
```

## 50.2 Authorization

Every protected admin operation has a named permission.

Examples:

```text
products.write
inventory.write
inventory.reconcile
orders.read
refunds.create
staff.manage
roles.manage
integrations.write
```

Frontend visibility is not permission.

---

# 51. Session Security

Refresh token:

- hashed at rest;
- rotated one time;
- replay-detected;
- family-revocable.

Concurrent replay test required.

---

# 52. IDOR Protection

Store/customer resource ownership must be verified on server.

Do not trust URL IDs as authorization.

When useful, return 404 rather than leak existence.

---

# 53. SSRF Protection

Required for:

- custom domain verification;
- outbound webhook URLs;
- integration test URLs;
- any future URL fetch.

Block:

```text
localhost
private networks
link-local
cloud metadata
unsupported schemes
DNS rebinding
```

---

# 54. Secrets

Never expose/log:

- passwords;
- access/refresh tokens;
- OTP;
- DB credentials;
- JWT secrets;
- provider secrets;
- full auth header;
- raw card data;
- CVV.

---

# 55. Media Security

Media uploads use direct object storage.

Validate:

- file size;
- content type;
- ownership;
- object existence/checksum where supported.

Do not proxy large files through FastAPI memory.

---

# 56. Error Security

Never expose:

- SQL exception;
- stack trace;
- raw internal provider errors;
- secret configuration;
- sensitive DB structure.

Use stable business error codes.

---

# 57. Database Concurrency Strategy

Use combinations of:

- unique constraints;
- conditional updates;
- row locks;
- deterministic lock ordering;
- optimistic versioning;
- idempotency records;
- append-only ledgers.

Do not rely on application-only pre-checks for P0 race safety.

---

# 58. Required Concurrency Tests

At minimum:

| Operation | Required test |
|---|---|
| inventory reserve | stock=5, 10 concurrent reservations |
| reservation consume/release | duplicate calls cannot double-change stock |
| checkout complete | 10 same-key concurrent requests → one order |
| refund | concurrent over-refund prevented |
| fulfillment | concurrent over-fulfillment prevented |
| return receive | duplicate restock prevented |
| transfer receive | duplicate receipt prevented |
| refresh token | concurrent replay allows one valid rotation |

---

# 59. Redis Architecture

Redis may hold:

- product cache;
- storefront projection cache;
- rate limits;
- short permission cache;
- worker broker;
- ephemeral coordination.

Redis does not own:

- orders;
- payment state;
- inventory truth;
- refund state;
- cart durability.

---

# 60. Caching Rules

- environment/store namespace;
- TTL required unless justified;
- DB fallback;
- invalidate after DB commit;
- outbox-driven invalidation when reliability matters;
- never cache raw secrets.

---

# 61. Search

Phase 1:

```text
PostgreSQL filters/indexes/full-text/trigram
```

Phase 2 if needed:

```text
OpenSearch/Elasticsearch projection
```

Search index never becomes canonical catalog truth.

---

# 62. Configuration Model

Use `pydantic-settings`.

Configuration groups:

```text
App
Database
Redis
JWT
Storage
Workers
Observability
Provider defaults
```

Merchant provider secrets should be stored securely and not returned through normal
GET APIs.

---

# 63. Migration Strategy

Alembic only.

Rules:

- ORM + migration together;
- do not edit applied migrations;
- one head unless explicit merge;
- review autogenerate;
- destructive migration requires plan;
- large backfill uses phased strategy.

Recommended:

```text
EXPAND
 ↓
compatible deployment
 ↓
BACKFILL
 ↓
switch
 ↓
verify
 ↓
CONTRACT
```

---

# 64. Observability

Every request should preserve:

```text
request_id
correlation_id
store_id
actor_id when safe
module
operation
duration
outcome
```

---

# 65. Core Metrics

Track:

```text
HTTP P50/P95/P99
4xx/5xx
checkout success
inventory reserve conflicts
payment success/failure
webhook backlog
outbox backlog age
worker retries
shipping provider errors
refund failures
bulk job failures
```

---

# 66. Alerting

Recommended alerts:

- payment webhook backlog age;
- outbox oldest pending age;
- inventory reserve conflict spike;
- elevated 5xx;
- provider timeout spike;
- refund failures;
- failed bulk jobs;
- database connection exhaustion;
- disk/backup failure.

---

# 67. Health Endpoints

```text
/health/live
/health/ready
```

Readiness should include critical local dependencies.

Do not make readiness depend on every external vendor.

---

# 68. Deployment Architecture

```text
Internet
   ↓
Nginx / TLS
   ↓
FastAPI API
   ├── PostgreSQL
   ├── Redis
   ├── Workers
   ├── Object Storage
   └── External Providers
```

Processes:

```text
nginx
api
worker
scheduler
postgres/managed DB
redis/managed Redis
```

---

# 69. Production Data Safety

Required:

- automated database backups;
- off-host copy;
- restore process tested;
- object storage durability;
- encrypted secrets;
- retention policy;
- backup health monitoring.

---

# 70. Repository Operating Contract

Codex/developers must obey `AGENTS.md`.

Key rules:

- inspect repo before editing;
- respect task scope/mode;
- do not touch unrelated dirty work;
- read only relevant docs progressively;
- do not weaken tests;
- report validation evidence;
- do not claim production readiness without evidence.

---

# 71. Implementation Strategy

Approved phase sequence:

```text
Phase 0  Foundation
Phase 1  Store + IAM
Phase 2  Customers
Phase 3  Catalog + Media
Phase 4  Inventory
Phase 5  Pricing + Promotions + Cart
Phase 6  Checkout
Phase 7  Orders
Phase 8  Payments + Refund
Phase 9  Fulfillment + Shipping
Phase 10 Returns
Phase 11 CMS + SEO + Notifications
Phase 12 Integrations + Bulk + Ops
Phase 13 Advanced Markets/Pricing
Phase 14 Production Hardening
```

Detailed task IDs and dependencies live in `docs/implementation/IMPLEMENTATION_PLAN.md`.

---

# 72. Critical Path

```text
Foundation
→ IAM
→ Catalog
→ Inventory
→ Pricing/Cart
→ Checkout
→ Order
→ Payment
→ Fulfillment
```

Do not prioritize P2 features ahead of this path.

---

# 73. Recommended First Production Release

## Included

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
Basic Pricing
Basic Discounts
Checkout
Orders
Razorpay
Refund basics
Fulfillment
Shiprocket
Tracking
Returns baseline
CMS basics
Notifications
Audit
Idempotency
Outbox
Health/observability
```

## Later

```text
Stripe
Delhivery
advanced markets
B2B pricing
advanced metafields
advanced bulk
public app ecosystem
shared SaaS runtime
```

---

# 74. Testing Strategy Summary

A full `docs/TESTING_STRATEGY.md` is recommended, but minimum required test families are:

- unit tests;
- API tests;
- authorization/IDOR;
- PostgreSQL integration;
- migration tests;
- concurrency tests;
- idempotency tests;
- provider adapter tests;
- webhook replay tests;
- cross-module regression;
- load tests;
- chaos/recovery tests.

---

# 75. Unit Test Scope

Focus on:

- domain policies;
- state transitions;
- money calculation;
- discount eligibility;
- refund calculation;
- return eligibility;
- application orchestration with fakes.

---

# 76. Integration Test Scope

Use real PostgreSQL for:

- repository behavior;
- constraints;
- UoW;
- migrations;
- outbox;
- transaction rollback;
- query projections.

Use Redis integration where cache/rate-limit behavior matters.

---

# 77. Contract Tests

Validate:

- Pydantic request/response;
- OpenAPI;
- error codes;
- required permissions;
- provider adapters;
- event envelope versions.

---

# 78. Provider Tests

Must cover:

- success;
- invalid auth/signature;
- timeout;
- duplicate request;
- malformed response;
- provider retry;
- unknown state;
- reconciliation.

---

# 79. Load / Performance Tests

Recommended:

```text
catalog browse
cart mutation
checkout creation
inventory hot SKU
order admin lists
worker backlog throughput
```

Performance must not weaken transaction safety.

---

# 80. Production Sign-Off Criteria

Before first client production launch:

- [ ] all P0 release modules verified;
- [ ] one Alembic head;
- [ ] fresh migration install passes;
- [ ] migration upgrade chain passes;
- [ ] inventory race tests pass;
- [ ] checkout idempotency race passes;
- [ ] payment webhook replay tests pass;
- [ ] over-refund race test passes;
- [ ] order snapshots immutable;
- [ ] provider timeout reconciliation works;
- [ ] split fulfillment supported;
- [ ] return duplicate restock prevented;
- [ ] RBAC/IDOR tests pass;
- [ ] secrets/log redaction reviewed;
- [ ] SSRF protections verified;
- [ ] backup/restore tested;
- [ ] internal routes network-restricted;
- [ ] alerts/health enabled;
- [ ] no unresolved P0 blocker.

---

# 81. Non-Functional Requirements

## Reliability

- graceful recovery after API/worker crash;
- idempotent retries;
- durable events;
- explicit reconciliation;
- no silent financial/stock mutation.

## Security

- least privilege;
- store/customer isolation;
- secret protection;
- input validation;
- replay resistance;
- SSRF controls;
- audit.

## Maintainability

- modular domain ownership;
- small use-case files;
- explicit contracts;
- no giant god service;
- no client-specific hidden hacks.

## Performance

- bounded pagination;
- indexed queries;
- async provider calls;
- no long-running API imports;
- controlled caching.

## Observability

- structured logs;
- metrics;
- health endpoints;
- trace/correlation IDs.

---

# 82. Scalability Strategy

Scale vertically/horizontally only where needed.

Initial:

```text
1–N API workers
1–N background workers
single primary PostgreSQL
Redis
object storage
```

Later:

- API horizontal scaling;
- worker scaling by queue;
- read replicas if required;
- managed DB;
- search projection;
- shared platform only when business requires.

Avoid premature distributed consistency problems.

---

# 83. Client Customization Rules

Allowed:

- custom frontend;
- theme/UI;
- content;
- provider configuration;
- feature flags;
- store settings;
- metafields;
- SEO;
- shipping/payment choices.

Forbidden:

```python
if client_name == "ABC":
    total -= 100
```

Reusable business rules must be modeled explicitly.

---

# 84. Feature Flag Strategy

Potential optional capabilities:

```text
returns
advanced_discounts
stripe
shiprocket
delhivery
international_markets
b2b_pricing
blog
```

Feature flags do not replace authorization.

---

# 85. ADR Strategy

Recommended initial ADRs:

```text
ADR-001 Modular Monolith
ADR-002 One Store Per Deployment + Store Scope
ADR-003 PostgreSQL Canonical Commerce Truth
ADR-004 Transactional Outbox
ADR-005 Inventory Ledger + Reservation
ADR-006 PostgreSQL Cart + Redis Cache
ADR-007 Checkout Separate from Cart/Order
ADR-008 Immutable Order Snapshot
ADR-009 Provider Adapter Boundary
ADR-010 DB-backed Idempotency
ADR-011 REST-first API
ADR-012 Async Bulk Operations
```

ADRs should not be deleted when superseded.

---

# 86. Technical Risk Register

| Risk | Severity | Main control |
|---|:---:|---|
| overselling | P0 | atomic inventory reserve |
| duplicate order | P0 | DB-backed idempotency |
| duplicate charge | P0 | provider/local idempotency + reconcile |
| duplicate refund | P0 | refundable ledger + concurrency control |
| webhook replay | P0 | signature + provider event unique key |
| out-of-order webhook | P0 | state machine + event history |
| IDOR | P0 | authenticated ownership/store scope |
| privilege escalation | P0 | RBAC/delegation controls |
| money precision | P0 | Decimal/NUMERIC |
| lost update | P1 | version/ETag |
| provider outage | P0/P1 | timeout + reconciliation + retry |
| SSRF | P0 | public-network URL validation |
| stored XSS | P0/P1 | sanitization + CSP |
| PII leakage | P0 | redaction + permissions |
| bulk resource exhaustion | P1 | async chunked jobs |
| cache drift | P1 | DB source + invalidation |
| audit tampering | P0 | append-only evidence |
| deadlocks | P0 | deterministic lock order + bounded retry |
| duplicate AWB | P0 | local shipment intent + reconcile |
| double restock | P0 | idempotent return receipt |
| COD settlement mismatch | P1 | explicit reconciliation |

---

# 87. Forbidden Architecture/Behavior

Never:

- use frontend price as authority;
- use frontend payment status as authority;
- use float for money;
- use Redis as sole inventory/cart truth;
- directly patch payment/order/fulfillment state;
- mutate another module's ORM rows;
- call own modules through localhost HTTP;
- call provider while holding stock locks;
- use unsafe check-before-write idempotency;
- delete ledger/history to fix data;
- retry unknown provider action blindly;
- hard-code client-specific hidden behavior;
- expose secrets;
- accept unsafe webhook URLs;
- run large bulk operation synchronously;
- claim P2 support without implementation.

---

# 88. Implementation Governance

Every Codex task should have:

```text
MODE
TASK ID
GOAL
READ
DEPENDENCIES
EXPECTED AREA
ACCEPTANCE
TESTS
NON-GOALS
RISKS
COMPLETION EVIDENCE
```

Example:

```text
MODE: IMPLEMENTATION
TASK ID: INV-007
GOAL: Atomic inventory reservation
ACCEPTANCE: no overselling
TEST: real PostgreSQL concurrency
NON-GOALS: payment/shipping
```

---

# 89. Definition of Done — Task

A task is done when:

- scope implemented;
- correct module/layer used;
- business invariants satisfied;
- API behavior aligned;
- migration included if needed;
- authorization enforced;
- tests pass;
- docs updated if contract changed;
- no hidden P0 risk;
- evidence reported.

---

# 90. Definition of Done — Phase

A phase is done when:

- every P0 task is VERIFIED;
- migrations work from clean DB;
- relevant module tests pass;
- cross-module regressions pass;
- no accepted-doc/code drift remains;
- STATUS.md updated;
- exit gate reviewed.

---

# 91. Definition of Production Ready

Production ready does not mean:

```text
API returns 200
```

It means:

```text
correct
+
concurrency-safe
+
idempotent
+
recoverable
+
observable
+
secure
+
migration-safe
+
tested
```

---

# 92. First-Client Launch Model

For first production client:

```text
same engine image
+
client-specific environment
+
client DB
+
client Redis
+
client provider keys
+
client custom frontend
```

No backend fork unless an explicitly approved reusable/extension requirement exists.

---

# 93. Post-Launch Operations

Monitor:

- checkout failure rate;
- payment failures;
- webhook backlog;
- inventory conflicts;
- shipping errors;
- worker retries;
- outbox backlog;
- refund failures;
- DB performance;
- backup success.

Run periodic:

- payment reconciliation;
- shipping reconciliation;
- COD reconciliation;
- inventory reconciliation;
- backup restore drill;
- dependency/security updates.

---

# 94. Recommended Next Artifacts

Before large-scale implementation, recommended final artifacts:

```text
docs/TESTING_STRATEGY.md
docs/adr/*
docs/STATUS.md
```

Then begin Phase 0 using `docs/implementation/IMPLEMENTATION_PLAN.md`.

---

# 95. Final Technical Decision

The approved implementation direction is:

```text
FastAPI modular monolith
        +
PostgreSQL canonical truth
        +
Redis cache
        +
domain/application separation
        +
explicit Unit of Work
        +
typed cross-module facades
        +
transactional outbox
        +
DB-backed idempotency
        +
immutable commerce ledgers/snapshots
        +
provider adapters
        +
async workers
        +
custom Next.js storefront per client
```

This design is intentionally optimized for LinkUp Web's immediate client-delivery
business while protecting the core from decisions that would make future
multi-store/platform evolution unnecessarily difficult.

---

# 96. Architecture Freeze Statement

The following decisions are considered frozen for initial implementation unless
explicitly changed through an accepted ADR:

- modular monolith;
- one-client-per-deployment initially;
- store-scoped schema;
- PostgreSQL canonical truth;
- Redis as non-authoritative cache;
- Decimal/NUMERIC money;
- normalized orders;
- immutable commercial snapshots;
- inventory level + reservation + movement ledger;
- checkout separate from cart/order;
- payment transaction ledger;
- provider event inbox/dedupe;
- fulfillment between order and shipment;
- transactional outbox;
- DB-backed idempotency;
- ports/adapters for providers;
- external side effects after commit.

---

# 97. Final Sign-Off Checklist

## Product

- [ ] Release 1 scope approved
- [ ] P0/P1/P2 boundaries accepted
- [ ] first-client provider choices confirmed

## Architecture

- [ ] repository structure frozen
- [ ] module ownership frozen
- [ ] transaction ownership rules accepted
- [ ] provider adapter boundary accepted

## Database

- [ ] P0 tables accepted
- [ ] P0 indexes/constraints accepted
- [ ] migration strategy accepted

## API

- [ ] P0 API contracts accepted
- [ ] permissions accepted
- [ ] errors/versioning accepted

## Business Logic

- [ ] state machines accepted
- [ ] inventory rules accepted
- [ ] payment/refund rules accepted
- [ ] cancellation/return rules accepted

## Reliability

- [ ] idempotency pattern accepted
- [ ] outbox accepted
- [ ] retry/reconciliation rules accepted

## Security

- [ ] auth/RBAC model accepted
- [ ] IDOR/store scope accepted
- [ ] secret/SSRF policy accepted

## Testing

- [ ] P0 concurrency scenarios accepted
- [ ] provider replay scenarios accepted
- [ ] launch acceptance gates accepted

## Implementation

- [x] `AGENTS.md` in repo
- [x] `docs/implementation/IMPLEMENTATION_PLAN.md` in repo
- [x] canonical docs paths established
- [ ] Codex starts from Phase 0 only

---

# 98. Final SDR Status

## Release 1 Scope Freeze Addendum

Architecture priority is not release scope. The first-client release is limited
to Foundation, Store/IAM, Customers, Catalog, Inventory, basic Pricing/Cart,
Checkout, Orders, Razorpay, refund baseline, Fulfillment, one selected shipping
provider, tracking, basic CMS/notifications, Reliability, and Audit. P2
markets, B2B pricing, advanced metafields, public apps, and shared SaaS runtime
remain later scope. The 88 architecture-P0 APIs are not a simultaneous launch
requirement; each exposed endpoint requires its own implementation and evidence.

**Status:** READY FOR IMPLEMENTATION PLANNING / REPOSITORY BOOTSTRAP

The architecture and product behavior are sufficiently specified to begin controlled
implementation using Codex, provided the repository follows `AGENTS.md` and the
phase/task boundaries in `docs/implementation/IMPLEMENTATION_PLAN.md`.

For production acceptance, the implementation must still produce runtime evidence,
migrations, tests, provider validation, observability and launch verification.

---

# 99. Final Rule

## Freeze Cleanup Decisions

Release 1 uses `DRAFT → PENDING → CONFIRMED → PROCESSING → COMPLETED` for order
lifecycle, with `ON_HOLD` and `CANCELLED` side states. Financial and fulfillment
summaries remain derived from their owning ledgers. Fulfillment uses
`OPEN → PACKING → READY → SHIPPED → COMPLETED` with `CANCELLED`; shipment uses
the full canonical carrier-neutral state set including `CREATING`, `PICKED_UP`,
`NDR`, `RTO`, `LOST`, and `CANCELLED`; returns include `REFUND_PENDING` and a
valid no-refund `RECEIVED → COMPLETED` path.

Release 1 optimistic versioning applies to store settings, products, variants,
pages, blog posts, carts, and checkouts only. Orders, payments, refunds,
inventory, and fulfillments use explicit commands and state-machine/locking
rules. `TAX-000 — Freeze India GST Policy` must complete before `CHK-007` or
`ORD-001`; it is a compliance decision gate, not runtime implementation.

Provider-event inbox processing is `RECEIVED → PROCESSING → PROCESSED`, with
retryable failure returning to `PROCESSING`, terminal failure becoming
`FAILED_TERMINAL`, and optional verified no-effect events becoming `IGNORED`.
This inbox lifecycle is separate from payment-intent lifecycle.

If implementation discovers a conflict between:

```text
DB schema
business rule
API contract
architecture
provider reality
```

do not silently patch around it.

The correct sequence is:

```text
identify conflict
→ determine canonical owner
→ update decision/specification with approval
→ create ADR if architectural
→ implement
→ test
→ update STATUS
```

**The implementation must not silently become the specification.**
