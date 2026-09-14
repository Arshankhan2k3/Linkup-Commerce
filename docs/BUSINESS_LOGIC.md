# LinkUp Commerce Engine — Domain Business Logic Specification

**Document type:** Production Business Logic / Domain Rules / Codex Implementation Contract  
**Version:** v1.0  
**Date:** 2026-09-08  
**Target stack:** FastAPI + PostgreSQL + Redis + Alembic + asynchronous workers  
**Deployment model:** One LinkUp Web e-commerce client per VPS/database initially; shared reusable commerce-engine codebase; store-scoped design retained for future SaaS/multi-store evolution.  
**Companion documents:** `docs/DB_SCHEMA.md`, `docs/API_ARCHITECTURE.md`

> **Purpose of this file:** The DB document defines what data exists. The API document defines how callers interact with the backend. **This document defines how the commerce system is allowed to behave.** Codex/developers must treat the domain invariants, pre-conditions, post-conditions, state transitions and forbidden actions here as implementation constraints.

---

## 1. Non-Negotiable Global Commerce Invariants

- **Server authority:** frontend/client input is never authoritative for price, discount amount, tax, shipping cost, stock availability, payment success, refund eligibility or domain status.
- **Money:** use Decimal in Python and `NUMERIC(19,4)` in PostgreSQL. JSON monetary values are decimal strings. Never use FLOAT/DOUBLE for financial values.
- **Time:** persist `TIMESTAMPTZ` UTC. Store timezone is for display and business scheduling only.
- **Store scope:** merchant-owned data is store-scoped from authentication/deployment context. Never authorize using a request-body `store_id`.
- **Immutable commerce history:** order line price/SKU/title snapshots, order addresses, payment transactions, inventory movements, redemptions and status histories are not retroactively rewritten.
- **State machines:** payment/order/checkout/fulfillment/shipment/return/refund/reservation states may only change through domain transition services—not generic `PATCH status`.
- **Idempotency:** retry-prone money/stock/order/shipment operations must be safe under duplicate and concurrent requests.
- **Concurrency:** use DB constraints, atomic SQL, row locks and deterministic lock ordering. Do not implement critical invariants as unsafe read-then-write checks.
- **Short transactions:** external payment/shipping/email/webhook HTTP calls are outside core DB transactions and stock locks.
- **Transactional outbox:** whenever a committed domain mutation requires an asynchronous side effect, write the event in the same DB transaction.
- **At-least-once reality:** workers/webhooks/events can run more than once. Consumers must be replay-safe.
- **No destructive history cleanup:** fix incorrect operational state with compensating transitions/ledger entries, not by deleting evidence.
- **Durable cart:** PostgreSQL is cart source of truth; Redis is cache only.
- **Separation of concerns:** Catalog owns sellable definitions, Inventory owns stock, Checkout orchestrates, Order snapshots, Payment owns financial ledger, Fulfillment owns delivery work.
- **Fail safe:** ambiguous payment, stock, price or permission state must reject/hold/reconcile rather than guess in favor of completing a commercial action.

## 2. Domain Command Execution Standard

Every state-changing service/use-case should follow this conceptual sequence:

```text
1. Authenticate / authorize actor
2. Resolve store + resource ownership
3. Validate request schema
4. Load authoritative domain state
5. Check PRE-CONDITIONS
6. Acquire required DB lock / atomic idempotency claim
7. Re-check concurrency-sensitive invariants
8. Perform domain calculation / state transition
9. Persist domain changes + audit/ledger/outbox in one short transaction
10. COMMIT
11. Perform/enqueue external side effects
12. Return stable response or idempotent replay
13. Observe metrics/logs using request_id
```

**Important:** Steps 5 and 7 are intentionally both present. A business rule checked before a lock can become false before the write.

## 3. Transaction Boundary Rules

| Situation | Inside DB transaction | Outside DB transaction |
|---|---|---|
| Checkout completion | idempotency claim, order snapshots, reservation consumption, status history, outbox | email, ERP webhook, analytics delivery |
| Inventory reserve | lock/atomic level updates and reservation evidence | none |
| Payment provider session | local payment intent creation/update | Razorpay/Stripe HTTP call |
| Payment webhook | durable provider-event inbox insert | heavy processing may happen in worker |
| Refund | local refund claim/protection, final ledger writes | gateway refund HTTP call |
| Shipment creation | local shipment intent/idempotency row | Shiprocket/Delhivery HTTP call |
| CMS publish | content state + outbox | CDN/search invalidation |
| Bulk import | one bounded batch | file parsing may stream outside; next batch separate |

## 4. Global Pre-condition / Post-condition Vocabulary

| Term | Meaning |
|---|---|
| **Pre-condition** | Must be true immediately before the command is allowed to mutate state. |
| **Post-condition** | Must be guaranteed after a successful commit. |
| **Invariant** | Must remain true across every command and concurrency scenario. |
| **Side effect** | Work triggered by a committed mutation but not required inside the same DB transaction. |
| **Compensation** | A new corrective business operation when a prior external action cannot be rolled back transactionally. |
| **Idempotent replay** | Duplicate call returns/produces the same logical outcome without a second business effect. |
| **Reconciliation** | Compare local state against an external provider/physical reality and append controlled corrective state rather than overwriting history. |

## 5. Canonical Calculation Rules

### 5.1 Money rounding

- Keep intermediate arithmetic in Decimal at sufficient precision.
- Round only at explicitly defined allocation/currency boundaries.
- Allocation residuals (for example a ₹10 discount distributed across three lines) must be assigned deterministically so line allocations sum exactly to the order-level amount.
- Never recalculate an old order using today's product price/tax/discount rules.

### 5.2 Order pricing pipeline

```text
authoritative variant/context prices
→ line merchandise subtotals
→ eligible discount rules + allocations
→ taxable bases
→ tax lines
→ shipping quote/charge
→ shipping discounts/tax if applicable
→ final grand total
```

The exact country/tax implementation can evolve, but there must be only **one canonical pricing service/pipeline** used by storefront checkout and admin/manual order completion.

## 6. Domain Summary

| # | Domain | Priority | Primary ownership |
|---:|---|:---:|---|
| 1 | Store Foundation & Sales Channels | P0/P1 | `stores`, `store_settings`, `store_domains`, `sales_channels` |
| 2 | Identity, Staff & RBAC | P0 | `users`, `staff_members`, `roles`, `permissions`, `role_permissions`, `staff_member_roles`, `refresh_tokens`, `audit_logs` |
| 3 | Customers, Addresses & Consent | P0/P1 | `customers`, `customer_addresses`, `customer_consents` |
| 4 | Product Catalog, Variants, Collections & Metafields | P0/P1/P2 | `products`, `product_options`, `product_option_values`, `product_variants`, `variant_option_values`, `media_assets`, `product_media`, `collections`, `collection_products`, `tags`, `product_tags`, `metafield_definitions`, `metafields` |
| 5 | Locations, Inventory & Stock Ledger | P0 | `locations`, `inventory_items`, `inventory_levels`, `inventory_reservations`, `inventory_movements`, `inventory_transfers`, `inventory_transfer_items` |
| 6 | Markets, Catalogs & Price Lists | P2 | `markets`, `catalogs`, `catalog_products`, `price_lists`, `price_list_items` |
| 7 | Discounts, Coupons & Promotions | P0/P1 | `discounts`, `discount_codes`, `discount_rules`, `discount_targets`, `discount_redemptions` |
| 8 | Cart & Checkout Orchestration | P0 | `carts`, `cart_lines`, `checkout_sessions`, `checkout_lines`, `checkout_addresses`, `checkout_shipping_rates` and orchestration across pricing, discounts, inventory, payments and orders |
| 9 | Orders & Immutable Commercial Snapshot | P0/P1 | `orders`, `order_items`, `order_addresses`, `order_discount_allocations`, `order_tax_lines`, `order_status_history` |
| 10 | Payments, Transactions & Refund Ledger | P0 | `payment_intents`, `payment_transactions`, `payment_provider_events`, `refunds`, `refund_items` |
| 11 | Fulfillment, Shipping, NDR & COD | P0/P1 | `fulfillments`, `fulfillment_items`, `shipments`, `shipment_events`, `ndr_events`, `cod_remittances` |
| 12 | Returns & Reverse Logistics | P1 | `returns`, `return_items` and orchestration with inventory/refunds |
| 13 | CMS, Navigation & SEO | P1 | `pages`, `blog_categories`, `blog_posts`, `navigation_menus`, `navigation_items`, `seo_metadata`, `redirects` |
| 14 | Notifications & Customer Communication | P0/P1 | `notification_templates`, `notification_deliveries`, `outbox_events` |
| 15 | Integrations, Apps & Webhooks | P1/P2 | `integrations`, `webhook_subscriptions`, `webhook_deliveries`, secret-manager references |
| 16 | Reliability, Audit, Outbox, Idempotency & Bulk Jobs | P0/P1 | `idempotency_records`, `outbox_events`, `audit_logs`, `bulk_jobs`, `bulk_job_items` |

---

## 7. Store Foundation & Sales Channels

**Priority:** P0/P1  
**Owns/touches:** `stores`, `store_settings`, `store_domains`, `sales_channels`

### Purpose

Defines the operational identity and global defaults of one LinkUp Commerce deployment. The current business model normally runs one client store per VPS/database, but all domain data remains store-scoped so the engine can evolve into multi-store/SaaS later.

### Source of truth / ownership

- `stores` is the source of truth for store identity, lifecycle status, country, timezone and default currency.
- `store_settings` is the source of truth for checkout/inventory/tax/unit policies.
- `store_domains` owns domain verification and primary-domain state.
- `sales_channels` identifies order/product origin; historical orders snapshot the channel reference.

### Domain invariants

- Every merchant-owned domain object must resolve to exactly one store. Controllers must derive store scope from deployment/auth context, not trust a request-body `store_id`.
- There should be one operational default store for the current single-client deployment. Additional rows must not accidentally become routable without explicit future multi-store support.
- Store status `PAUSED` may disable new storefront checkout while still allowing admin reads, refunds, fulfillment and historical customer order access according to policy.
- Store status `CLOSED` is an operational lifecycle state, not permission to erase commerce history.
- Default currency changes affect future pricing contexts only. Existing orders, payments, refunds and reports retain their original currency snapshots.
- Timezone affects display/scheduling rules; persisted event timestamps remain UTC.
- Only a verified domain may become primary.
- A primary domain cannot be deleted until a different verified domain is promoted.
- Sales channel identifiers referenced by historical orders are never hard-deleted or silently repurposed.

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Update store settings | Authenticated staff has `settings.write`; payload passes typed validation; store is not CLOSED for settings that affect selling. | Validate units, checkout expiry, tax flags and inventory policy. Write settings transactionally and increment configuration version. | New requests use the new settings; previous orders/checkouts retain their own snapshots where required; config cache is invalidated after commit. | Rollback DB change on validation/constraint failure. Cache invalidation is retried through an event if necessary. | `store.settings.updated` | Bad global settings can break every checkout. Use typed fields, bounded numeric values, audit logs and protected changes for currency/status. |
| Register custom domain | Staff has domain permission; host normalizes to a valid hostname and is not already claimed. | Create PENDING domain record. Generate verification challenge. Verification/SSL is async and isolated from private-network access. | Domain exists but is not routable as PRIMARY until verification succeeds. | Verifier failure changes verification/SSL state; it does not roll back the domain row. Retry is safe. | `domain.verification.requested`, `domain.verified` | SSRF/domain takeover. Never fetch arbitrary admin URLs from internal network; validate DNS/IP and ownership. |
| Change primary domain | Target domain is verified and SSL-active. | In one transaction, unset old primary and set new primary with uniqueness protection. | Exactly one primary domain exists. | Rollback entire primary swap if any constraint fails. | `store.primary_domain.changed` | Two primary domains or no primary can break routing. Enforce partial unique index or equivalent transaction rule. |

### Explicitly forbidden

- ❌ Expose secret provider configuration through public store settings.
- ❌ Use store name/domain as a security boundary instead of store ID/auth scope.
- ❌ Physically delete a store because a merchant pauses or closes it.
- ❌ Change historical order currency/channel attribution after the fact.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Global misconfiguration | P0 | Typed settings, audit log, versioned config, protected permission. |
| Cross-store leakage | P0 | Always inject store scope at service/repository boundary. |
| Domain takeover/SSRF | P0 | Ownership verification, public-network-only DNS/HTTP validation, no arbitrary server fetch. |
| Currency migration confusion | P1 | Treat order currency as immutable; explicit migration process for catalog defaults. |

### Generalized business example

A LinkUp client initially launches on `acme.linkup-preview.in`. After DNS verification of `shop.acme.in`, an admin promotes it. Existing orders are unaffected; new storefront requests resolve the same store through the new primary host.

---

## 8. Identity, Staff & RBAC

**Priority:** P0  
**Owns/touches:** `users`, `staff_members`, `roles`, `permissions`, `role_permissions`, `staff_member_roles`, `refresh_tokens`, `audit_logs`

### Purpose

Separates authentication identity from store membership and granular merchant authorization. Merchant/staff identities must not be mixed with shopper/customer credentials.

### Source of truth / ownership

- `users` owns staff login identity and credential state.
- `staff_members` owns whether an identity is an active member of the store.
- `roles` + permission mappings own authorization; frontend role labels are never authoritative.
- `refresh_tokens`/session registry owns revocable long-lived sessions.
- `audit_logs` records privileged changes and security-sensitive actions.

### Domain invariants

- Access tokens are short-lived and contain identity/session references, not a permanently trusted permission snapshot.
- Effective permissions are resolved from current active staff membership and role mappings. Permission caches must be invalidated after any role change.
- Refresh tokens are random, one-time-rotated and stored hashed. Reuse of an already-rotated refresh token revokes the token family/session.
- Rotation is transactional: lock the presented token, require unexpired/unrevoked/unconsumed, set `consumed_at`, and create exactly one successor with the same `family_id`; concurrent reuse loses and revokes the family.
- Passwords are one-way hashed with a modern password hashing function. Plaintext passwords never enter logs or audit payloads.
- Login errors must not reveal whether an email exists.
- Staff invitations are one-time, signed, expire and are tied to the intended store/email.
- An inviter cannot grant privileges they are not allowed to delegate.
- Protected owner/super-admin access cannot be removed if it would leave the store with no recoverable owner.
- Disabling/removing staff revokes refresh sessions and prevents new access-token authorization immediately or within the configured short cache window.
- Every privileged action records actor, action, entity and safe before/after metadata where useful.

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Merchant login | Valid login DTO; anti-abuse limit not exceeded. | Normalize email, locate identity, verify password with constant-behavior error handling, verify active membership, create short access token and rotated refresh session. | A valid authenticated session exists and login security event is recorded. | Failed authentication does not mutate store data. Rate-limit counters may update. | `auth.login.succeeded` / security log | Credential stuffing/account enumeration. Rate limit by identity fingerprint + IP; generic error messages. |
| Refresh session | Presented refresh token exists, is unexpired, not revoked and has not been rotated. | Hash lookup, lock token/session family, mark old token consumed, create new token atomically. | Old refresh token can never create another session; new access/refresh pair returned. | On detected replay, revoke family and require login. | `auth.token.rotated`, `auth.session.revoked` | Refresh-token theft/replay. One-time rotation must be transactional. |
| Assign role | Actor has `staff.manage`/role delegation privilege; target staff and roles belong to current store. | Validate protected-role rules; atomically replace/add role mappings; invalidate permission cache. | Next authorization decision reflects new effective permission set. | Rollback assignments if any role invalid or last-owner invariant violated. | `staff.roles.updated` | Privilege escalation. Never accept arbitrary permission strings directly from the browser as effective authority. |

### Explicitly forbidden

- ❌ Store plaintext passwords, refresh tokens or OTPs.
- ❌ Rely on frontend hiding buttons as authorization.
- ❌ Put permanent `ADMIN` trust only in JWT and skip DB membership checks forever.
- ❌ Hard-delete audit history when staff leaves.
- ❌ Allow a user to create/grant a permission that is not in the server-owned permission catalog.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Privilege escalation | P0 | Granular permissions, protected roles, delegability checks. |
| Session theft/replay | P0 | Short access TTL, hashed rotating refresh tokens, family revocation. |
| Credential stuffing | P0 | Rate limiting, lockout/backoff, security telemetry. |
| Audit gaps | P0 | Central privileged-action audit middleware/service. |

### Generalized business example

Warehouse staff has `orders.read`, `inventory.read`, `inventory.write`. They can receive stock but cannot issue refunds because `refunds.create` is not in their effective permission set, even if they manually call the refund API.

---

## 9. Customers, Addresses & Consent

**Priority:** P0/P1  
**Owns/touches:** `customers`, `customer_addresses`, `customer_consents`

### Purpose

Represents shoppers independently from merchant staff, including guest-to-account evolution, saved addresses and auditable consent.

### Source of truth / ownership

- `customers` is the store-scoped shopper/CRM identity.
- `customer_addresses` owns mutable saved addresses only.
- `order_addresses` owns historical commercial address snapshots after order creation.
- `customer_consents` is append-only evidence for marketing/privacy preference changes.

### Domain invariants

- Customer uniqueness is scoped by store and normalized email/phone policy.
- A guest checkout may create or link a customer CRM profile, but must not silently create a password/login account.
- Linking a guest history to an account requires verified ownership of the identifier or a trusted checkout/account flow.
- Saved address edits never update prior order addresses.
- Exactly one default address per address type/customer may be enforced; replacement occurs transactionally.
- For Release 1, exactly one overall default address per customer is enforced by a partial unique constraint; address-type-specific defaults require a future explicit model.
- Customer status (ACTIVE/BLOCKED/etc.) is operational and does not imply marketing consent.
- Marketing consent must be explicit, purpose/channel specific and auditable with timestamp/source.
- Staff `refresh_tokens` are never used for shoppers. Customer login/account support exists, but dedicated long-lived customer refresh/logout sessions are P1 and persistence is not implementable until a separate customer session registry is approved.
- Deleting an address or deactivating a customer must preserve orders and legal/financial history.
- Admin customer data is PII and permission-gated; exports require stronger permissions and audit.

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Register customer account | Email/phone satisfies format and store uniqueness; password policy passes. | Create account identity/customer mapping, hash credential, set verification state, do not infer marketing consent. | Customer can authenticate after configured verification rule; profile exists. | Unique conflict returns deterministic error; no partial credential row. | `customer.account.created` | Account enumeration and duplicate identity linking. |
| Update saved address | Authenticated customer owns address. | Validate postal/country fields, update mutable saved address only; handle default flag atomically. | Future checkouts can use new address; historical orders remain unchanged. | Rollback on invalid default/constraint. | `customer.address.updated` | IDOR and historical-order corruption. |
| Change marketing consent | Customer/approved channel has authority to change the particular preference. | Append consent event with previous/new status, channel, purpose, source and timestamp. | Current preference can be derived while evidence remains auditable. | If downstream marketing sync fails, local consent still commits and sync retries via event. | `customer.consent.changed` | Regulatory/privacy risk. Never silently subscribe during registration or checkout. |

### Explicitly forbidden

- ❌ Treat phone/email alone as proof that two customer records belong to the same person.
- ❌ Edit historical order shipping/billing address through customer profile APIs.
- ❌ Automatically opt users into marketing because they bought something.
- ❌ Return full PII in generic logs or public search endpoints.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| IDOR/PII leakage | P0 | Ownership checks, field whitelists, permission-gated admin APIs. |
| Bad account merging | P0 | Verified identifier ownership and explicit merge policy. |
| Consent compliance | P0 | Append-only consent evidence, explicit purpose/channel. |
| Historical address mutation | P0 | Separate mutable customer addresses from order snapshots. |

### Generalized business example

A guest buys using `buyer@example.com`. The system creates a CRM customer record but no password. Later the user verifies that email and creates an account; history can be linked without altering the original order address snapshot.

---

## 10. Product Catalog, Variants, Collections & Metafields

**Priority:** P0/P1/P2  
**Owns/touches:** `products`, `product_options`, `product_option_values`, `product_variants`, `variant_option_values`, `media_assets`, `product_media`, `collections`, `collection_products`, `tags`, `product_tags`, `metafield_definitions`, `metafields`

### Purpose

Owns merchandising truth: products, sellable variants, options, media, collections/tags and typed extensibility. Catalog data describes what can be sold; it does not own stock or order history.

### Source of truth / ownership

- `products` owns common merchandising data and publication state.
- `product_variants` is the sellable SKU/price-bearing unit.
- `product_options`/values define valid variant dimensions such as Size/Color.
- `inventory_items` owns whether/where a variant is stocked; catalog must not keep ad-hoc stock truth.
- `order_items` owns historical purchase snapshots.
- `media_assets` owns uploaded asset metadata; product-media links own display ordering.
- `metafield_definitions` define allowed typed custom data; metafields hold validated values.

### Domain invariants

- Product creation defaults to DRAFT unless an explicit controlled workflow says otherwise.
- A product becomes publishable only when required merchandising fields exist and at least one sellable active variant satisfies price/availability policy.
- SKU is unique per store, not globally across every deployment.
- For a product, one exact option-value combination maps to at most one active variant.
- Variant price is Decimal/NUMERIC; request JSON uses decimal strings, never binary float.
- Catalog price is a current selling input. Order line price is copied/snapshotted at checkout/order creation and never retroactively changed.
- Deleting a product/variant referenced by commerce history is prohibited; archive instead.
- Removing option values must not silently delete/rewrite variants. Destructive changes require explicit impact handling.
- Media upload uses signed object storage; the API does not hold large file bodies in memory.
- Only media that is successfully finalized/validated can be attached as READY storefront media.
- Tags are normalized to avoid meaningless duplicates caused by case/whitespace.
- Metafield values must validate against a server-owned typed definition; arbitrary executable schema/code is not accepted.
- Storefront listing returns only published/active products and safe fields.

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Create product | Staff has `products.write`; handle/title payload valid. | Normalize/generate handle, create DRAFT product, tags/SEO references as controlled sub-operations, write audit/outbox. | A non-sellable draft product exists. | Whole product-shell transaction rolls back on uniqueness/validation failure. | `product.created` | Duplicate handles and accidentally selling incomplete products. |
| Create variant | Parent product exists; option values belong to parent; SKU and option combination are unique. | Create variant with Decimal price; if inventory-tracked, create associated inventory item in same logical transaction. | Variant is addressable and inventory can be managed separately. | Rollback variant if required inventory-item creation fails. | `variant.created` | Duplicate SKU/combinations; orphan variant without inventory representation. |
| Publish product | Product is DRAFT/ACTIVE-eligible; required fields, at least one active sellable variant, valid pricing and required media/policy pass. | Transition publication state through catalog service; write outbox for cache/search invalidation. | Storefront may return product after commit/cache propagation. | If post-commit index invalidation fails, DB stays authoritative and worker retries. | `product.published` | Publishing incomplete/zero-price/wrong-state merchandise. |
| Update variant price | Variant exists and staff has permission; Decimal price is non-negative and currency context is valid. | Update current catalog/base price; increment version; invalidate pricing/product cache. | New carts/checkouts use new current price; existing order snapshots remain unchanged. | Stale editor version returns 409 rather than silently overwriting. | `variant.updated` | Lost update, price precision, historical price mutation. |
| Archive product/variant | Entity exists and actor authorized. | Change availability/publication state; preserve relational history; invalidate storefront/search. | No new sales through normal storefront while historical orders still resolve snapshots. | If entity is already archived, operation is idempotent. | `product.archived` / `variant.archived` | Hard deletion breaking reports/refunds/returns. |

### Explicitly forbidden

- ❌ Store authoritative inventory count inside generic product JSON.
- ❌ Use JSONB-only option/variant relationships when core filters/uniqueness need normalized tables.
- ❌ Accept frontend-provided current price as truth in cart/order creation.
- ❌ Hard-delete products or variants referenced by orders, returns, inventory movements or financial history.
- ❌ Execute merchant-supplied scripts through metafields/templates.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Price/history corruption | P0 | Order snapshots, Decimal money, no retroactive rewrite. |
| Variant explosion | P1 | Bound options/values and bulk sizes; async jobs for large generation. |
| Lost concurrent edits | P1 | Version/ETag optimistic concurrency. |
| Stored XSS/media abuse | P0 | Sanitize rich text; signed upload; content type/size/checksum validation. |
| Search/cache staleness | P1 | Outbox-driven invalidation plus TTL. |

### Generalized business example

`Classic Shirt` has Color {Black, White} and Size {M, L}. Four variants are created, each with a store-unique SKU. Changing Black/M from ₹1,999 to ₹2,199 affects new carts only; an order already placed at ₹1,999 remains ₹1,999 forever.

---

## 11. Locations, Inventory & Stock Ledger

**Priority:** P0  
**Owns/touches:** `locations`, `inventory_items`, `inventory_levels`, `inventory_reservations`, `inventory_movements`, `inventory_transfers`, `inventory_transfer_items`

### Purpose

Owns physical stock truth, warehouse/location allocation, temporary checkout reservations, transfers and immutable stock movement evidence. Preventing oversell is a non-negotiable domain invariant.

### Source of truth / ownership

- `inventory_items` maps sellable variants to inventory identity.
- `inventory_levels` is the current materialized stock state by item/location.
- `inventory_reservations` owns temporary reservation state; `CONSUMED` is the terminal state for stock consumed by an order.
- `inventory_movements` is the append-only audit ledger explaining every stock delta.
- `inventory_transfers` owns inter-location stock movement workflow.

### Domain invariants

- Available stock is never accepted from frontend. It is calculated/maintained by controlled inventory operations.
- A physical-stock-changing transaction must update the current level and append a corresponding movement atomically; reservation-only changes require reservation evidence in the same transaction instead.
- Reservation must be race-safe using atomic conditional SQL or deterministic row locking. A separate `check available` followed by unsafe write is forbidden.
- Reservation quantity must be positive and cannot exceed `available` under Release 1 `DENY` policy.
- Reservations have expiry and transition only `ACTIVE → CONSUMED | RELEASED | EXPIRED`; release/consume are idempotent.
- A reservation cannot be consumed twice or released after it has reached a terminal state.
- Reservation expiry worker must use safe row claiming (`FOR UPDATE SKIP LOCKED` or equivalent) to prevent duplicate processing.
- Manual adjustment records reason, actor and quantity delta; setting physical counted stock computes an adjustment delta rather than deleting history.
- `inventory_levels` is exactly `on_hand`, `reserved`, `incoming`, and `damaged`; `available = on_hand - reserved - damaged`.
- Negative `on_hand`, `reserved`, `incoming`, `damaged`, or `available` is rejected. Release 1 uses `DENY`; no backorder exception exists.
- Release 1 supports `DENY` inventory policy only. `CONTINUE`/backorder behavior is deferred and must not be inferred by implementation.
- Location allocation order must be deterministic to minimize deadlocks when multiple lines/locations are locked.
- External provider/network calls never occur while inventory locks are held.
- Transfer source and destination must differ. Shipping/receiving transitions control when stock leaves one location and becomes available at the other.
- Partial transfer receipts are permitted up to shipped quantity; over-receipt is rejected.

### Calculations / derived values

| Calculation | Rule |
|---|---|
| Available stock | `available = on_hand - reserved - damaged`. `incoming` is informational and never sellable in Release 1. |
| Reserve condition | `available >= requested_qty` must be evaluated in the same atomic DB write/lock that increments reservation/current reserved quantity. |
| Reconciliation delta | `delta = counted_on_hand - current_on_hand`; append `RECONCILIATION` movement with `delta`. |
| Transfer receipt | `remaining_receivable = shipped_qty - already_received_qty`; received quantity cannot exceed remaining. |

### State machines

| Aggregate | Allowed lifecycle |
|---|---|
| Inventory reservation | `ACTIVE → CONSUMED | RELEASED | EXPIRED` |
| Inventory transfer | `DRAFT → IN_TRANSIT → PARTIALLY_RECEIVED → RECEIVED`; side state `CANCELLED` where allowed |

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Reserve stock | Checkout exists, is unexpired, authoritative line quantities known; inventory item/location valid. | Lock/atomically update levels in deterministic order; if every line can reserve, increment `reserved` and create ACTIVE reservation rows in one short transaction. No physical movement row is created. | Either every required line is reserved according to checkout policy, or no partial reservation remains. | If any line insufficient, rollback transaction and return 409 OUT_OF_STOCK. Serialization/deadlock errors may be retried with bounded backoff. | `inventory.reserved` | Oversell, deadlock, partial reservation. This is a P0 concurrency-critical operation. |
| Release reservation | Reservation is ACTIVE and release reason supplied; duplicate calls allowed. | Lock reservation and level in deterministic order; transition once and decrement `reserved` atomically. No physical movement row is created. | Stock is sellable exactly once; reservation evidence remains. | RELEASED/EXPIRED returns idempotent success; CONSUMED is terminal and cannot release. | `inventory.reservation.released` | Double release causing artificial stock growth. |
| Consume reservation | Order/checkout is authorized to consume reservation; reservation ACTIVE. | Lock reservation and level; transition to CONSUMED, decrement both `reserved` and `on_hand`, append `RESERVATION_CONSUME` atomically. | Units are no longer sellable and order owns the consumed evidence. | Repeated consume returns existing outcome; never decrements twice. | `inventory.reservation.consumed` | Double decrement or order/inventory drift. |
| Manual stock adjustment | Admin has inventory permission; item/location valid; reason required. | Compute new state under lock, reject disallowed negative result, append adjustment movement and audit in same transaction. | Current level equals old level + delta and ledger explains difference. | Rollback both level and movement on failure. | `inventory.adjusted` | Silent stock manipulation/fraud. Always actor + reason + immutable ledger. |
| Receive transfer | Transfer shipped/in-transit; quantity does not exceed remaining receivable. | Under lock update transfer item receipt, destination inventory level and append TRANSFER_IN movement; source already handled by ship transition. | Destination available/on-hand reflects only actually received quantity. | Duplicate receive request is idempotent using transfer-item state/idempotency; over-receipt rejected. | `inventory.transfer.received` | Inventory duplication through repeated receipt. |

### Explicitly forbidden

- ❌ Direct generic CRUD update of `stock_available`, `reserved`, `on_hand` from an admin JSON payload.
- ❌ Delete inventory movement history to make counts match.
- ❌ Reserve stock in Redis as the sole source of truth.
- ❌ Hold DB stock locks while calling Razorpay, Shiprocket or any external HTTP service.
- ❌ Release or consume a reservation based solely on frontend state.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Overselling | P0 | Atomic reserve + DB constraints + concurrency tests. |
| Double release/consume | P0 | Reservation state machine + idempotency. |
| Deadlocks | P0 | Deterministic lock order, short transactions, bounded retry. |
| Stock fraud/audit loss | P0 | Append-only movements + actor/reason audit. |
| Transfer duplication | P1 | State/quantity invariants and idempotent receiving. |

### Generalized business example

Stock = 5. Ten concurrent checkouts each request one unit. The reservation operation is atomic: exactly five succeed and five receive `OUT_OF_STOCK`. At no point can `available` go below the policy floor.

---

## 12. Markets, Catalogs & Price Lists

**Priority:** P2  
**Owns/touches:** `markets`, `catalogs`, `catalog_products`, `price_lists`, `price_list_items`

### Purpose

Provides a future-safe pricing/availability context for international, B2B or channel-specific commerce without changing variant identity.

### Source of truth / ownership

- `markets` resolves geographic/commercial context.
- `catalogs` own which products are available to a context.
- `price_lists`/items own contextual variant price overrides.
- `product_variants.price` remains base/fallback price unless a valid contextual price overrides it.

### Domain invariants

- Frontend may request/express country context but may not choose a privileged raw price-list ID.
- Pricing engine resolves context from domain, customer/B2B eligibility, shipping country and configured market rules.
- Checkout always re-resolves the authoritative pricing context; cart/display price is not final authority.
- Every monetary output includes currency.
- A price list must declare a currency compatible with the resolved market/catalog policy.
- Changing current market pricing never rewrites historical orders.
- Conflicting active price lists require an explicit precedence rule; accidental multiple winners are invalid configuration.
- Large price-list imports run as bulk jobs.

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Resolve market context | Store active; request/domain/customer context available. | Apply deterministic market resolution rules and select one valid catalog/currency context. | Downstream catalog/pricing services receive a server-owned context object. | If no specific market matches, use default store market/fallback; never expose privileged catalog through fallback. | `pricing.context.resolved` optional telemetry | Price bypass or ambiguous context. |
| Resolve variant price | Variant sellable and market context valid. | Check active contextual price override; fallback to base price; apply currency compatibility and Decimal rules. | Return one authoritative unit price + source context/version. | If required context has no permitted product/price, mark unavailable rather than guessing. | — | Wrong-market price leakage. |

### Explicitly forbidden

- ❌ Accept `price_list_id` from a public client and trust it.
- ❌ Convert currencies with arbitrary client exchange rates.
- ❌ Use contextual price updates to edit previous order lines.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Privileged/B2B price leakage | P0 if enabled | Server-owned context resolution. |
| Ambiguous active pricing | P1 | Unique/preference rules and validation. |
| Currency mismatch | P1 | Currency on every price and checkout snapshot. |

### Generalized business example

The same SKU has INR ₹1,999 for India and USD $35 for a US market. Both are current catalog prices; an Indian order already placed remains INR even if the US price list changes.

---

## 13. Discounts, Coupons & Promotions

**Priority:** P0/P1  
**Owns/touches:** `discounts`, `discount_codes`, `discount_rules`, `discount_targets`, `discount_redemptions`

### Purpose

Evaluates server-side promotions deterministically and records actual usage only when the configured commercial commit point is reached.

### Source of truth / ownership

- `discounts` owns promotion definition/lifecycle.
- `discount_rules` and targets own eligibility.
- `discount_codes` owns normalized customer-entered codes.
- `discount_redemptions` is the authoritative usage ledger; a mutable `used_count` is at most a derived cache.

### Domain invariants

- Cart/checkout discount evaluation is server-side and does not trust client discount amount.
- Preview/evaluation is side-effect free: simply viewing a discount must not consume usage.
- Redemption is committed at the defined order/payment business point, in a transaction protected against global/per-customer usage races. Each automatic or code application has one redemption identity per order; `discount_code_id=NULL` is handled with NULLS-NOT-DISTINCT uniqueness.
- Percentage discount is bounded (normally 0–100) and final discount cannot exceed eligible amount unless explicit credit logic exists elsewhere.
- Flat discount cannot make monetary subtotal negative.
- Minimum order thresholds are evaluated against explicitly defined bases (e.g. merchandise subtotal before shipping/tax); the basis must be consistent and documented.
- Promotion dates are evaluated using UTC timestamps derived from store scheduling rules.
- Target products/collections/customers must belong to the same store/context.
- Combination policy must be deterministic. If multiple discounts conflict, pricing engine applies declared precedence/combinability rules.
- Editing a discount affects future evaluations; prior `order_discount_allocations` remain immutable.

### Calculations / derived values

| Calculation | Rule |
|---|---|
| Percentage | `raw_discount = eligible_base × percent / 100`; then apply max cap and round by currency policy. |
| Flat | `discount = min(flat_value, eligible_base)` unless explicit cross-line allocation rule applies. |
| Order total | Discount allocation occurs before/after shipping/tax exactly as the promotion definition specifies; checkout must use one canonical calculation pipeline. |

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Apply coupon to cart | Cart valid; code normalized; promotion active; customer/context eligibility available. | Evaluate without consuming usage. Store code intent on cart and recalculate pricing projection. | Cart shows current estimated discount/application details. | If invalid/expired return stable error. No redemption row is created. | `discount.previewed` optional analytics | Coupon probing/abuse; rate limit repeated invalid attempts. |
| Evaluate discounts | Authoritative line prices/quantities and context provided by pricing engine. | Resolve automatic + code discounts, targets, thresholds, combination rules and allocation deterministically. | Return allocations and total discount; no durable usage side effect. | Any unsupported/conflicting rule fails safely rather than silently over-discounting. | — | Revenue leakage from rule ambiguity. |
| Commit redemption | Order is at configured commit state; exact discount applications/snapshots known. | Lock/validate usage constraints, insert one redemption per application under the unique order/discount/code guard, update any derived counters. | Usage ledger reflects order exactly once. | Duplicate call returns existing redemption; race exceeding usage limit fails/rolls back according to order workflow. | `discount.redeemed` | Double redemption or oversubscribed limited coupon. |

### Explicitly forbidden

- ❌ Increment coupon usage during cart preview.
- ❌ Trust frontend to calculate percentage/flat discount.
- ❌ Use arbitrary executable merchant rule code.
- ❌ Retroactively rewrite order discount allocations when merchant edits a campaign.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Revenue leakage | P0 | Canonical pricing pipeline and typed rule engine. |
| Usage-limit race | P0 | Redemption ledger + transaction/locks/unique constraints. |
| Coupon brute force | P1 | Rate-limit invalid-code attempts and avoid leaking internal rules. |
| Rounding drift | P0 | Decimal arithmetic and one allocation/rounding policy. |

### Generalized business example

`WELCOME10` gives 10% off first order above ₹1,000, capped at ₹500. Cart can preview the discount many times; only the successfully committed order creates one redemption row.

---

## 14. Cart & Checkout Orchestration

**Priority:** P0  
**Owns/touches:** `carts`, `cart_lines`, `checkout_sessions`, `checkout_lines`, `checkout_addresses`, `checkout_shipping_rates` and orchestration across pricing, discounts, inventory, payments and orders

### Purpose

Separates mutable shopping intent (Cart) from a short-lived, versioned transaction session (Checkout), then safely produces one immutable Order.

### Source of truth / ownership

- `carts`/lines own mutable shopping intent.
- `checkout_sessions` and checkout snapshots own the authoritative short-lived pricing/shipping/reservation context.
- Inventory module owns stock.
- Pricing/discount modules own monetary evaluation.
- Payment module owns money/provider state.
- Order module owns the permanent commercial record.

### Domain invariants

- Cart is durable in PostgreSQL; Redis is only a cache/acceleration layer.
- Guest cart access uses an unguessable opaque token; authenticated customer access additionally verifies ownership.
- Cart line requests contain variant/quantity/custom properties only—not authoritative price, tax, discount or stock.
- Every cart/checkout mutation increments a version. High-contention checkout actions validate expected version to prevent stale updates.
- Creating checkout snapshots current cart lines/context but checkout completion must still revalidate price/discount/shipping/inventory/payment according to freshness rules.
- Shipping-rate quotes are time-bounded and tied to checkout/address/package context. A rate ID from another checkout is invalid.
- Inventory is reserved for a bounded checkout expiry window, not forever.
- Creating payment provider session requires a valid, priced checkout and required reservation state.
- Browser redirect/success callback is not authoritative proof of payment.
- Checkout completion requires DB-backed idempotency.
- Same idempotency key + same semantic request returns the same order. Same key + materially different request hash returns 409.
- The order creation transaction contains only local DB operations needed for consistency; external provider HTTP calls happen before/after as appropriate, never while core order locks are held.
- Expired/abandoned checkout releases reservations exactly once.
- A cart may remain as historical/converted state after order completion; it must not accidentally produce multiple orders without explicit new checkout/idempotency behavior.

### Calculations / derived values

| Calculation | Rule |
|---|---|
| Merchandise subtotal | Sum authoritative `unit_price × quantity` across eligible checkout lines. |
| Grand total | Canonical pipeline: merchandise subtotal − discount allocations + tax + shipping + other explicit charges. All intermediate values are Decimal and snapped. |
| Checkout freshness | Pricing/shipping/reservation components carry version/timestamp; completion rejects or recomputes stale components. |

### State machines

| Aggregate | Allowed lifecycle |
|---|---|
| Cart | `ACTIVE → CONVERTED | ABANDONED/EXPIRED` (exact states may be simplified in schema) |
| Checkout | `OPEN → PRICED → INVENTORY_RESERVED → PAYMENT_PENDING → COMPLETED`; side exits `EXPIRED`, `FAILED` |

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Add cart line | Cart active and caller owns opaque token/customer; variant exists and is sellable. | Validate quantity bounds; resolve current display price server-side; insert/update line; bump cart version; invalidate cache. | Cart reflects line and recalculated estimate. | DB is source; Redis update failure does not lose cart and may be rebuilt. | `cart.updated` | Price tampering, IDOR, huge quantities. |
| Create checkout | Cart active, non-empty and caller authorized. | Create checkout session with line snapshot/current context; calculate authoritative pricing estimate; set expiry/version. | A short-lived checkout token/state exists separate from cart. | No stock or payment side effect unless explicitly part of later actions. | `checkout.created` | Duplicate/stale checkout; session must not accidentally be permanent inventory lock. |
| Set shipping address / rate | Checkout open/unexpired; caller authorized; address valid. | Update checkout address snapshot; invalidate previous shipping quote when address/package changes. Quote rates externally with timeout outside DB transaction; persist bounded-expiry rate results. | Selected rate always belongs to current checkout version/context. | Provider failure does not corrupt checkout; return retriable error or configured fallback. | `checkout.shipping.updated` | Forged shipping price, carrier timeout, stale quote. |
| Reserve checkout inventory | Checkout complete enough to sell, current prices/discounts validated, expected version matches. | Invoke inventory atomic reserve for all required lines; persist reservation references/expiry and transition state. | Either required stock is safely reserved or checkout remains unreserved with explicit error. | Inventory transaction rolls back on insufficient line. Any stale checkout requires reprice/retry. | `inventory.reserved`, `checkout.inventory_reserved` | Overselling and partial reservation. |
| Create payment session | Checkout has valid reservation if required, totals current, payment method allowed. | Persist checkout-origin local intent before order creation with authoritative amount and request idempotency; call gateway outside the DB transaction with provider idempotency; attach provider reference. | One logical checkout intent maps safely to one provider session/reference. | Provider timeout leaves `RECONCILIATION_REQUIRED`; retry reconciles local/provider identity before creating another charge target. | `payment.intent.created` | Duplicate gateway orders/charges. |
| Complete checkout | Checkout unexpired; ownership valid; required reservation ACTIVE; authoritative final totals fresh; payment rule satisfied; Idempotency-Key supplied. | `CompleteCheckoutUseCase` owns one short DB transaction: claim idempotency; lock/revalidate checkout, lines, totals and reservation; require verified CAPTURED evidence online or create COD order with PENDING financial state; insert order and immutable snapshots; consume reservation; set `orders.checkout_id`; link Payment Intent to Order; commit applicable discount redemption; write initial order history/outbox and save replay response. | Unique `(store_id, checkout_id)` guarantees at most one order; inventory/order/payment agree; side effects are durable. | Any local consistency failure rolls back all steps. Provider/network calls are outside this transaction. Duplicate replay returns saved result. | `order.created`, `checkout.completed` | Duplicate orders, stock drift, payment/order mismatch. Highest-risk transaction in system. |
| Expire checkout | Checkout due and not completed; worker safely claims row. | Transition to EXPIRED, release active reservations idempotently, write event. | No active stock remains trapped by expired session. | Worker crash can retry; state/row locks prevent double release. | `checkout.expired` | Inventory leakage or double release. |

### Explicitly forbidden

- ❌ Create final order directly from an arbitrary frontend cart payload.
- ❌ Trust frontend grand total, shipping price, coupon amount or payment success.
- ❌ Call gateway/carrier while holding the final order/inventory transaction.
- ❌ Use Redis as the only durable cart/reservation authority.
- ❌ Allow stale checkout version to silently overwrite newer address/rate/quantity state.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Duplicate order | P0 | DB-backed idempotency record + unique constraint + response replay. |
| Overselling | P0 | Atomic inventory reservation and freshness checks. |
| Stale pricing/shipping | P0 | Versioned checkout + authoritative completion revalidation. |
| Payment/order mismatch | P0 | Verified payment state + local intent/transaction ledger. |
| Abandoned reservation leak | P0 | Expiry worker + idempotent release. |

### Generalized business example

Customer sees a ₹2,000 item, applies a coupon, enters address and selects ₹80 shipping. Before completion, price changes. Checkout completion revalidates the authoritative pricing rules instead of trusting the old browser total, then either updates/requires confirmation per policy or safely completes with the allowed snapshot.

---

## 15. Orders & Immutable Commercial Snapshot

**Priority:** P0/P1  
**Owns/touches:** `orders`, `order_items`, `order_addresses`, `order_discount_allocations`, `order_tax_lines`, `order_status_history`

### Purpose

Owns the permanent commercial fact of what was ordered, at what price, where it should be delivered/billed and the controlled lifecycle of that order.

### Source of truth / ownership

- `orders` owns order identity, totals, current lifecycle summaries and currency.
- `order_items` owns immutable purchased-product/SKU/price/quantity snapshots.
- Every `order_item` has a mandatory `order_id`; the canonical relationship is `orders 1 → N order_items` and no orphan item is valid.
- `order_addresses`, discount allocations and tax lines are immutable historical snapshots.
- `order_status_history` is the append-only transition history.
- Payment/refund truth remains in payment ledger; fulfillment truth remains in fulfillment module.

### Domain invariants

- Order number is unique per store and generated server-side; it is not the PK security boundary.
- Core commercial fields become immutable after order creation: line unit price, SKU/title snapshot, original quantities, currency, shipping/billing snapshot, tax/discount allocation.
- Catalog edits never rewrite order items.
- Saved customer-address edits never rewrite order addresses.
- `order_status`, `payment_status` and `fulfillment_status` cannot be directly patched by generic CRUD; domain services derive/transition them.
- All lifecycle transitions pass through a central state machine and append history with actor/source/reason.
- Cancellation, refund, inventory restock and shipment cancellation are coordinated but remain separate domain actions.
- An order may be partially fulfilled, partially returned and partially refunded; a single simplistic status must not destroy those facts.
- Manual/draft orders with custom prices require explicit privileged permission and audit.
- Order reads for customers require authenticated ownership or a secure signed guest-order token.

### State machines

| Aggregate | Allowed lifecycle |
|---|---|
| Order lifecycle | `DRAFT → PENDING → CONFIRMED → PROCESSING → COMPLETED`; side states `ON_HOLD`, `CANCELLED`. Financial and fulfillment summaries remain derived. |
| Financial summary | Derived from payment transactions/refunds: e.g. `PENDING`, `AUTHORIZED`, `PAID`, `PARTIALLY_REFUNDED`, `REFUNDED`, `FAILED`. |
| Fulfillment summary | Derived from fulfillments: e.g. `UNFULFILLED`, `PARTIAL`, `FULFILLED`. |

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Create order from checkout | Only checkout orchestration calls this with verified immutable snapshots and valid idempotency context. | Insert order, items, addresses, discounts/taxes, initial status history and outbox inside one transaction. | Permanent commercial record exists exactly once. | Any insert/constraint failure rolls back all order snapshot records. | `order.created` | Partial order creation or duplicate order. |
| Cancel order | Actor authorized; order not already terminal; fulfillment/payment state allows cancellation or coordinated sub-actions. | State machine records cancellation intent/reason. Determine unfulfilled stock release/restock; delegate payment void/refund and shipment cancellation according to their own state. | Order is cancelled only with consistent downstream outcomes/recorded pending sub-actions; no new fulfillment proceeds. | Each sub-action is idempotent. If provider refund/cancel is async, order records a recoverable pending state/event rather than pretending success. | `order.cancelled` | Double restock/refund; cancelling shipped order incorrectly. |
| Place/release hold | Order in allowed non-terminal state. | Transition hold flag/state with actor/reason and append history. | Fulfillment creation/processing honors hold until released. | Idempotent if already in desired hold state. | `order.hold.changed` | Warehouse race—fulfillment must re-check hold under transaction. |
| Create manual/draft order | Privileged admin; customer/lines valid; any custom price override permission explicit. | Server resolves normal prices or records audited custom line price; order is created in `DRAFT` until controlled completion. | Draft is not counted as a paid sale or consumed stock until completion logic succeeds; `placed_at` remains NULL. | Invalid draft can be abandoned without affecting payment/stock. | `draft_order.created` | Fraud/accidental revenue manipulation via custom prices. |

### Explicitly forbidden

- ❌ Edit historical unit prices after order creation.
- ❌ Update order payment status because an admin says 'paid' without payment/offline-transaction evidence.
- ❌ Use order cancellation as a substitute for refund or shipment cancellation.
- ❌ Hard-delete orders to fix operational mistakes.
- ❌ Expose internal notes/audit data to storefront APIs.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Historical corruption | P0 | Immutable snapshot tables and restricted update paths. |
| Illegal state transitions | P0 | Central state machine. |
| Double stock/refund on cancel | P0 | Idempotent coordinated domain operations. |
| PII exposure | P0 | Customer ownership + admin permissions + response whitelists. |

### Generalized business example

A customer buys `Classic Shirt / Black / M` for ₹1,999. Merchant later renames product and changes price to ₹2,499. Order #ORD-1042 still shows the original title/SKU/price/address snapshots.

---

## 16. Payments, Transactions & Refund Ledger

**Priority:** P0  
**Owns/touches:** `payment_intents`, `payment_transactions`, `payment_provider_events`, `refunds`, `refund_items`

### Purpose

Provides gateway-independent financial truth, replay-safe provider webhooks and full/partial refund behavior without trusting browser callbacks.

### Source of truth / ownership

- `payment_intents` owns one logical attempt/expected payment amount/context; request idempotency is scoped by `(store_id, operation, key)`.
- `payment_transactions` is the immutable financial ledger of AUTHORIZE/CAPTURE/SALE/VOID/REFUND/OFFLINE actions.
- `payment_provider_events` is the durable deduplicated inbox for gateway webhooks.
- `refunds` and refund items own refund workflow; successful provider transaction finalizes financial effect.
- Order payment summary is a projection/derived state, not an independently editable truth.

### Domain invariants

- Authoritative payment amount comes from checkout/order, never request-body price from storefront.
- Gateway provider session is created from a local persisted intent with local/provider idempotency.
- Browser redirect, JS callback or client `payment_success=true` is never proof of payment.
- Provider webhook signature is verified against the raw body before trusted parsing/processing.
- Every provider event has a stable unique `(store_id, provider, external_event_id)` dedupe key.
- Payment intents support `CHECKOUT`, `ORDER`, and `ADMIN` origins. Checkout-origin intents may exist without an order; order/admin intents may link to an order later.
- A checkout has at most one active online intent per logical payment operation while status is `CREATED`, `PENDING_CUSTOMER_ACTION`, `PROCESSING`, `AUTHORIZED`, or `RECONCILIATION_REQUIRED`. A new provider target requires `FAILED`, `CANCELLED`, or an explicit supersede command; a new request idempotency key does not bypass this rule.
- Webhook intake acknowledges quickly after durable acceptance; long business processing occurs asynchronously/idempotently.
- Webhook processing must tolerate duplicates and out-of-order delivery.
- Financial transactions are append-only. Corrections are new transactions/reconciliation events, not silent edits.
- Capturable amount = authorized amount − prior captures/voids according to provider semantics.
- Refundable amount = captured/settled eligible amount − successful/pending protected refunds, bounded by selected return/order lines.
- Partial refunds are first-class.
- Refund request is idempotent; provider refund calls use a stable idempotency/reference.
- Payment gateway HTTP calls never occur inside long order/inventory DB transactions.
- Provider timeout is an UNKNOWN/reconcilable condition, not automatic failure that blindly retries and may double charge.
- Provider calls use a bounded connect/read timeout and stable provider idempotency key; timeout recovery reconciles before retrying.
- Checkout expiry locks and re-reads payment state before releasing reservations. Protected payment states (`PROCESSING`, `AUTHORIZED`, `CAPTURED`, `RECONCILIATION_REQUIRED`) retain the checkout in a protected reconciliation path. A late verified capture after RELEASED/EXPIRED triggers atomic re-reservation; if unavailable, no order/oversell is created and the payment enters reconciliation/refund handling.
- Customer session policy: Release 1 may defer dedicated customer long-lived sessions; staff `refresh_tokens` are never reused for storefront customers. If customer persistence is enabled later, use a separate revocable customer-session registry.
- COD/offline/manual collection requires strong permission and an append-only offline transaction with actor/reference.

### Calculations / derived values

| Calculation | Rule |
|---|---|
| Captured balance | Sum successful CAPTURE/SALE transactions minus successful VOID semantics where applicable. |
| Refunded balance | Sum successful REFUND transactions. |
| Amount due | Order payable total − successful captured/sale/offline collections + applicable refunds only when business reporting defines net due; keep gross/order totals immutable. |
| Refundable | `max(0, eligible_captured - already_refunded_or_reserved_for_pending_refund)`. |

### State machines

| Aggregate | Allowed lifecycle |
|---|---|
| Payment intent | `CREATED → PENDING_CUSTOMER_ACTION → PROCESSING → AUTHORIZED | CAPTURED | FAILED | CANCELLED | RECONCILIATION_REQUIRED`; provider-specific transitions mapped centrally. |
| Refund | `REQUESTED → PROCESSING → SUCCEEDED | FAILED_RETRYABLE | FAILED_FINAL | RECONCILIATION_REQUIRED`. |
| Provider event inbox | `RECEIVED → PROCESSING → PROCESSED`; processing may move to `FAILED_RETRYABLE` and retry to `PROCESSING`, or to `FAILED_TERMINAL`; verified no-effect events may be `IGNORED`. |

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Create payment intent/provider session | Checkout/order total authoritative, currency valid, payment method allowed. | Insert local intent first; commit. Call provider with strict timeout and stable idempotency. Persist provider reference/status. | A retriable local record exists even if provider response is uncertain. | On timeout query/reconcile using provider reference/idempotency before creating a new intent. | `payment.intent.created` | Duplicate gateway order/charge and amount tampering. |
| Accept provider webhook | Request arrives at provider-specific endpoint. | Read raw body, verify signature/auth, derive external event ID, insert inbox row uniquely, return 200 after durable acceptance. | Valid unique event is safely queued; duplicate valid event is harmless. | Invalid signature returns 4xx without business mutation. Duplicate unique conflict can return success/no-op. | `payment.provider_event.received` | Forged/replayed webhook. |
| Process payment event | Verified durable provider event exists and worker claims it. | Map provider event to allowed local state; lock payment intent/order projection as needed; append transaction exactly once; update derived statuses; write outbox. | Local ledger matches accepted provider event and downstream events are durable. | Out-of-order/regressive event that conflicts with terminal state is recorded/ignored or sent to reconciliation—not blindly applied. | `payment.captured`, `payment.failed`, etc. | Double capture/confirmation and state regression. |
| Request refund | Authorized actor; order/payment has refundable balance; selected quantity/amount eligible; Idempotency-Key supplied. | Calculate amount server-side, reserve/protect refundable balance via local refund record, then execute provider refund asynchronously/idempotently. | One logical refund exists and over-refund is impossible under concurrent requests. | Provider failure transitions refund safely; amount becomes retryable/available according to terminal state rules. | `refund.requested` | Double/over refund. |
| Record COD/offline collection | Privileged actor; order has payable offline balance and method allows it. | Append OFFLINE/COD payment transaction with amount/reference/time/actor; recompute financial projection. | Audit trail explains manual payment state. | Never replace existing transaction; correction requires compensating transaction/process. | `payment.offline_recorded` | Internal fraud or accidental payment marking. |

### Explicitly forbidden

- ❌ Mark order PAID from browser success page.
- ❌ Overwrite provider transaction history.
- ❌ Retry unknown gateway timeout by blindly creating a new payment.
- ❌ Accept refund amount without server-side eligibility calculation.
- ❌ Store raw card number/CVV or sensitive PCI data.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Double charge | P0 | Local + provider idempotency, reconciliation on timeout. |
| Forged/replayed webhooks | P0 | Raw-body signature + event unique key. |
| Over-refund | P0 | Ledger-calculated refundable balance + transactional protection. |
| Out-of-order events | P0 | State machine and event-time/provider-state reconciliation. |
| Sensitive financial data | P0 | Tokenized provider references only; strict redaction. |

### Generalized business example

Razorpay sends the same capture webhook three times. Inbox uniqueness accepts one logical event, processing appends one CAPTURE transaction, and later duplicates return 200 without changing the order again.

---

## 17. Fulfillment, Shipping, NDR & COD

**Priority:** P0/P1  
**Owns/touches:** `fulfillments`, `fulfillment_items`, `shipments`, `shipment_events`, `ndr_events`, `cod_remittances`

### Purpose

Separates ordered quantity from warehouse fulfillment and external carrier shipment so an order can split across locations/packages while preserving normalized tracking.

### Source of truth / ownership

- `fulfillments` owns which order quantities are allocated/processed from a location.
- `fulfillment_items` owns fulfilled quantity per order line.
- `shipments` owns carrier package/AWB identity.
- `shipment_events` is append-only normalized tracking history.
- `ndr_events` owns delivery exceptions/actions.
- `cod_remittances` owns settlement reconciliation for COD shipments.

### Domain invariants

- One order may have zero, one or many fulfillments; one fulfillment may produce one or more shipments if business requires.
- Sum of active fulfilled quantities for an order item cannot exceed fulfillable remaining quantity.
- Fulfillment creation must respect order hold/cancel state and the consumed inventory evidence/allocation contract.
- Carrier shipment creation starts with a local shipment intent/reference; provider retries must not create duplicate AWBs.
- Carrier network call occurs outside the core DB transaction.
- Carrier webhook/event is authenticated/deduplicated where provider supports IDs; all normalized events append to history.
- Out-of-order carrier events cannot blindly regress a terminal state such as DELIVERED to IN_TRANSIT.
- NDR address/phone changes require explicit allowed action, audit and provider confirmation behavior.
- COD settlement import is deduplicated by provider/batch/reference and reconciled against shipment/order expected amounts; delivery never marks remittance settled.
- Shipment cancellation is only allowed in provider/local states where cancellation is valid; local state cannot claim cancellation if provider is already shipped unless a compensating workflow exists.
- Fulfillment cancellation restores fulfillable quantities/inventory exactly once where applicable.

### State machines

| Aggregate | Allowed lifecycle |
|---|---|
| Fulfillment | `OPEN → PACKING → READY → SHIPPED → COMPLETED`; side `CANCELLED` where allowed. |
| Shipment | `CREATING → CREATED → PICKUP_SCHEDULED → PICKED_UP → IN_TRANSIT → OUT_FOR_DELIVERY → DELIVERED`; exception states `NDR`, `RTO`, `LOST`, and `CANCELLED`. Terminal shipment states cannot be regressed by older events. |
| NDR | `OPEN → ACTION_SUBMITTED → RESOLVED`; the associated shipment may separately transition to `RTO`. |
| COD remittance | `EXPECTED → REPORTED → RECONCILED → SETTLED`; mismatch enters `RECONCILIATION_REQUIRED` before settlement. |

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Create fulfillment | Order eligible, not held/cancelled; item quantities remain fulfillable; selected location valid. | Under transaction lock relevant order item counters/allocation, create fulfillment/items, and associate inventory already consumed by the order according to the allocation record. | Fulfillment owns only requested remaining quantities and cannot over-fulfill. | Rollback entire fulfillment if any line over quantity or invalid. | `fulfillment.created` | Over-fulfillment or race with cancellation. |
| Create carrier shipment | Fulfillment eligible/ready; package/address valid; no existing equivalent active shipment unless split intentionally. | Create local shipment intent/idempotency reference, commit. Worker/provider adapter calls carrier, persists AWB/external ID. | One logical package has one intended provider shipment; retry finds same reference. | Provider timeout remains CREATING/UNKNOWN until reconcile; do not create second AWB blindly. | `shipment.create.requested`, `shipment.created` | Duplicate AWB/provider charges. |
| Process carrier tracking event | Authenticated/durable carrier event maps to known shipment. | Append normalized event; compare event time/rank/state policy; update current shipment projection only if transition valid. | History preserves all events; current state remains monotonic unless explicit correction. | Duplicate event no-op; stale regression recorded but does not regress current terminal state. | `shipment.status.changed` | Out-of-order webhooks and false delivered/RTO. |
| Handle NDR action | NDR open; actor allowed; action supported by carrier; updated PII validated. | Record requested action/audit then call provider adapter; transition based on provider acknowledgement. | Operational history shows who requested what and provider outcome. | Provider failure leaves retryable action state rather than claiming resolution. | `ndr.action.submitted` | Wrong delivery-address modification/PII abuse. |
| Import COD remittance | Trusted provider file/API batch; batch/reference not already processed. | Validate totals, match AWB/shipment/order, insert reconciliation records, flag mismatch; never silently force match. | Each settlement item is accounted once and discrepancies visible. | Duplicate batch returns existing result; unmatched items go to exception queue. | `cod.remittance.reconciled` | Double settlement and accounting mismatch. |

### Explicitly forbidden

- ❌ Model Shipment as permanently 1:1 with Order.
- ❌ Let carrier webhook directly set arbitrary order status.
- ❌ Regress DELIVERED because an older IN_TRANSIT webhook arrives late.
- ❌ Create a second provider shipment on timeout without reconciliation.
- ❌ Mark COD settled solely because shipment says DELIVERED.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Over-fulfillment | P0 | Quantity locks/invariants. |
| Duplicate AWB | P0 | Local shipment intent + provider idempotency/reconciliation. |
| Out-of-order tracking | P0 | Append-only events + transition rank/state machine. |
| COD accounting mismatch | P1 | Batch dedupe and reconciliation exceptions. |
| PII changes via NDR | P1 | Strong permission, validation, audit. |

### Generalized business example

One order contains a shirt in Noida and shoes in Mumbai. Two fulfillments and AWBs are created. Customer sees one order with both tracking histories; delivered status for one package does not falsely mark the other package delivered.

---

## 18. Returns & Reverse Logistics

**Priority:** P1  
**Owns/touches:** `returns`, `return_items` and orchestration with inventory/refunds

### Purpose

Controls the request/approval/receipt/disposition lifecycle. Returning an item, restocking it and refunding it are related but separate facts.

### Source of truth / ownership

- `returns` owns return case lifecycle.
- `return_items` owns requested/approved/received quantities and disposition.
- Inventory movement ledger owns actual stock effect.
- Refund/payment ledger owns money returned.

### Domain invariants

- Return eligibility is server-side: ownership, delivered state, return window, product policy and remaining returnable quantity.
- Requested return quantity cannot exceed delivered quantity minus quantities already successfully returned/in active protected returns according to policy.
- Submitting a return request does not automatically restock inventory or refund money.
- Approval does not mean physical receipt.
- Physical receipt records actual received quantity and disposition: RESTOCK, DAMAGED, DISCARD, or INSPECT. `REJECTED` is a return workflow state and never a receipt disposition.
- Only RESTOCK disposition increases sellable inventory; DAMAGED increases damaged/non-sellable bucket if modeled.
- Refund amount is calculated from original order allocations/remaining refundable value, not current product price.
- Return and refund may be partial.
- Every receive/restock action is idempotent and quantity-bounded.
- Closing a return requires required operational/refund steps to be resolved.

### State machines

| Aggregate | Allowed lifecycle |
|---|---|
| Return | `REQUESTED → APPROVED | REJECTED → IN_TRANSIT → RECEIVED → REFUND_PENDING → COMPLETED`; `RECEIVED → COMPLETED` is valid when no refund is required; side `CANCELLED`. |
| Return item | Track requested, approved, received, restocked/damaged and refunded quantities separately if needed for audit. |

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Request return | Customer owns order; order item delivered/eligible; within return window; requested qty >0 and <= remaining returnable. | Create return case/items without changing stock/payment. | Return workflow exists in REQUESTED state. | Reject invalid quantities/reason/window with no side effect. | `return.requested` | Return abuse/over-return. |
| Approve/reject return | Admin authorized; return in REQUESTED; quantities still valid. | Transition approved quantities or reject with reason; optionally initiate reverse shipping. | Customer can see decision; no sellable stock/refund yet unless configured downstream. | State invalidation returns conflict. | `return.approved` / `return.rejected` | Approving more than ordered/delivered. |
| Receive returned goods | Return approved/inbound; received qty <= outstanding approved qty. | Record receipt and disposition under transaction; append inventory movement for RESTOCK/DAMAGED exactly once. | Physical inventory and return quantities agree. | Duplicate receipt cannot restock twice; over-receipt rejected. | `return.received`, `inventory.adjusted` | Double restock/incorrect damaged stock. |
| Refund return | Return item eligible and has remaining refundable amount/qty; refund permission. | Use original order financial allocation to request refund through Payment module. | Money workflow linked to return; return closes only after successful/accepted refund policy. | Payment failure leaves the refund in `FAILED_RETRYABLE` or `RECONCILIATION_REQUIRED` rather than altering received stock history. | `refund.requested` | Refunding current price or over-refunding. |

### Explicitly forbidden

- ❌ Restock when customer merely submits a return request.
- ❌ Refund based on current catalog price.
- ❌ Use one boolean `returned=true` for partial-return cases.
- ❌ Delete failed/rejected return history.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Over-return | P0 | Remaining quantity calculations + locks. |
| Double restock | P0 | Idempotent receive/disposition. |
| Over-refund | P0 | Original allocation + payment ledger balance. |
| Fraudulent reason/eligibility | P1 | Policy engine/admin review and evidence fields. |

### Generalized business example

Customer bought 3 shirts and returns 2. Warehouse receives both: one RESTOCK, one DAMAGED. Only one returns to sellable inventory; refund can still cover the approved two based on original order value.

---

## 19. CMS, Navigation & SEO

**Priority:** P1  
**Owns/touches:** `pages`, `blog_categories`, `blog_posts`, `navigation_menus`, `navigation_items`, `seo_metadata`, `redirects`

### Purpose

Lets each LinkUp client manage content and SEO while the custom storefront/theme remains code-controlled and brand-specific.

### Source of truth / ownership

- CMS tables own content/state, not arbitrary executable frontend layout.
- SEO metadata is contextual metadata attached to supported resource owners.
- Redirects own path redirection rules.
- Frontend code/theme remains the rendering authority.

### Domain invariants

- Draft content is never returned by public endpoints.
- Publish is a controlled state change with valid handle/title/content requirements.
- Rich text is sanitized/validated against the chosen editor format.
- Arbitrary `<script>` execution from CMS is forbidden.
- Navigation tree is bounded in depth/items and cannot contain cycles.
- Resource links must resolve to current-store resources or validated external URLs according to policy.
- SEO canonical URLs must respect allowed domain policy; avoid arbitrary malicious schemes/hosts.
- Structured SEO/schema JSON must be validated, not passed as arbitrary executable script.
- Redirect `from_path` is normalized and unique as required; redirect graph cannot contain loops.
- Open redirects to arbitrary untrusted schemes/domains are blocked according to business policy.
- Scheduled publishing uses store timezone for user input but persists UTC.

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Save draft page/post | Content editor authorized; payload valid/sanitizable. | Store sanitized structured content, DRAFT status and optimistic version. | Admin preview/editor sees draft; public API does not. | Invalid content fails before publish; no public cache invalidation needed unless preview system. | `page.updated` / `blog.updated` | Stored XSS and lost concurrent edits. |
| Publish content | Content valid; status eligible; schedule valid. | Transition publish state/time; write outbox for CDN/cache invalidation/search/sitemap. | Public API can return content after commit/propagation. | If cache invalidation fails, DB stays truth and worker retries. | `page.published`, `blog.published` | Draft leakage/stale cache. |
| Replace navigation tree | Actor authorized; menu exists. | Validate bounded item count/depth, no cycles, valid links; atomically replace/update ordered tree. | Exactly one valid tree version becomes current. | Any cycle/bad resource rejects whole update. | `navigation.updated` | Recursive cycle and broken storefront navigation. |
| Create redirect | Normalized source path and target valid. | Check loop against existing redirect graph and open-redirect policy, then persist/invalidate redirect cache. | Request to source follows one valid redirect chain within configured limit. | Loop/conflict rejects without partial rule. | `redirect.created` | SEO loop/open redirect security issue. |

### Explicitly forbidden

- ❌ Let CMS execute merchant-supplied Python/JS on backend.
- ❌ Expose draft content on public endpoints.
- ❌ Allow unlimited navigation recursion.
- ❌ Allow `javascript:` or unvalidated redirect/canonical schemes.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Stored XSS | P0 | Sanitize/structured editor + CSP. |
| Redirect abuse | P0 | Scheme/domain validation + loop detection. |
| Draft leakage | P1 | Strict publication filters. |
| SEO cache staleness | P1 | Outbox invalidation. |

### Generalized business example

LinkUp builds a premium electronics frontend. Client can edit About, blogs, menu and SEO in admin, but cannot change backend code/theme through arbitrary scripts, keeping the reusable commerce engine safe.

---

## 20. Notifications & Customer Communication

**Priority:** P0/P1  
**Owns/touches:** `notification_templates`, `notification_deliveries`, `outbox_events`

### Purpose

Sends transactional messages asynchronously with templates, retries, deduplication and delivery evidence without blocking commerce transactions.

### Source of truth / ownership

- `notification_templates` owns approved message templates/variable contracts.
- `notification_deliveries` owns per-recipient attempt/state history and a deterministic store-scoped `dedupe_key`; explicit resends use a new command identity.
- `outbox_events` triggers notification jobs after successful domain commits.

### Domain invariants

- Commerce request paths never synchronously wait for email/SMS provider to complete.
- Template variables are allowlisted/typed; template language cannot execute arbitrary code.
- Transactional notifications may be triggered by domain events such as order.created/payment.captured/shipment.changed.
- Marketing notifications must separately honor customer consent; transactional required messages follow legal/business policy.
- Delivery retries use exponential backoff with max attempts and terminal failure.
- At-least-once event infrastructure requires a stable dedupe key so duplicate domain events do not spam the customer.
- Recipient and message data are PII and redacted from general logs.
- Provider outage never rolls back a successful order/payment.

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Enqueue notification | A committed domain event/authorized resend supplies event type, recipient and template context. | Create/dedupe delivery record/job and return immediately. | One logical notification is queued. | Duplicate dedupe key returns existing delivery; no extra send. | `notification.queued` | Duplicate spam. |
| Process delivery | Worker safely claims due delivery; template active; recipient/channel valid. | Render with approved variables; call provider with timeout; record provider reference/status; retry transient failures. | Delivery reaches SENT/DELIVERED or terminal FAILED with attempts/history. | Worker crash/retry does not intentionally send duplicates; provider idempotency/reference used where available. | `notification.sent` / `notification.failed` | Duplicate send, PII leak, provider retry storm. |

### Explicitly forbidden

- ❌ Send customer email directly inside the order DB transaction.
- ❌ Log full OTP/token/message secrets.
- ❌ Execute arbitrary template code.
- ❌ Treat marketing consent as implied by a transactional order event.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Duplicate spam | P0 | Dedupe key + idempotent job claim. |
| Provider outage | P1 | Async retry/backoff, no commerce rollback. |
| Template injection | P0 | Allowlisted renderer. |
| PII leakage | P0 | Log redaction and permissioned delivery logs. |

### Generalized business example

Order commits successfully while email provider is down. `order.created` outbox event remains durable; worker retries later and sends one confirmation without affecting the order.

---

## 21. Integrations, Apps & Webhooks

**Priority:** P1/P2  
**Owns/touches:** `integrations`, `webhook_subscriptions`, `webhook_deliveries`, secret-manager references

### Purpose

Isolates provider/integration configuration and supports safe outbound event delivery to ERP/CRM/custom apps without coupling third-party secrets into commerce tables.

### Source of truth / ownership

- `integrations` owns provider type/status/public configuration and a reference to securely stored secrets.
- `webhook_subscriptions` owns topic, version and endpoint configuration.
- `webhook_deliveries` owns delivery attempts/outcomes.
- Transactional outbox supplies domain events for outbound dispatch.

### Domain invariants

- Secrets are write-only from admin APIs and never returned decrypted.
- Long-lived secrets belong in environment/secret manager/KMS-backed secret storage, not raw generic JSON.
- Integration provider configuration is schema-validated per provider.
- Connection test uses a controlled adapter and strict timeout; generic user-supplied server fetch is forbidden.
- Outbound webhook URL is HTTPS by default, resolves to allowed public network and is protected against SSRF/DNS rebinding.
- Webhook subscription pins an API/event version.
- Outbound payload includes stable event ID/version so receivers can dedupe.
- Delivery is at-least-once with bounded exponential retries; non-retryable 4xx eventually disable/alert according to policy.
- Response body from subscriber is truncated/redacted before storage/logging.
- Deleting an integration with historical references should disable/revoke it rather than erase history.

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Create integration | Staff has permission; provider/type recognized; config validates. | Store safe public config and encrypted secret reference; optionally test asynchronously. | Integration exists in ACTIVE/PENDING state without exposing secrets. | Secret-storage failure rolls back creation. Provider test failure changes health, not secret confidentiality. | `integration.created` | Secret leakage/misconfiguration. |
| Create outbound webhook subscription | Actor allowed; topic supported; HTTPS URL valid and public-network safe. | Validate DNS/IP, generate signing secret, pin payload version, persist subscription. | Future matching outbox events can produce signed deliveries. | Unsafe/private endpoint rejected. | `webhook.subscription.created` | SSRF/data exfiltration. |
| Dispatch outbound webhook | Due delivery/subscription active and worker claimed record. | Render versioned payload, sign HMAC, call endpoint with timeout, record safe response metadata, retry transient errors. | Delivery history proves attempts; duplicate retries use same event/delivery identity. | Max attempts lead terminal failure/alert; no infinite retry storm. | `webhook.delivery.succeeded/failed` | Duplicate delivery and webhook storm. |

### Explicitly forbidden

- ❌ Return provider secrets from GET APIs.
- ❌ Allow localhost, metadata service or private subnet webhook URLs by default.
- ❌ Store arbitrary executable connector code in DB.
- ❌ Assume outbound webhook is exactly-once.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Secret compromise | P0 | Secret manager/KMS reference, write-only APIs, redaction. |
| SSRF | P0 | Public IP/domain validation, DNS rebinding defense, HTTPS. |
| Webhook retry storm | P1 | Backoff, max attempts, circuit breaker/disable. |
| Consumer duplicate side effect | P1 | Stable event ID and documented at-least-once semantics. |

### Generalized business example

Client ERP subscribes to `order.created`. Order transaction writes outbox; dispatcher sends a signed v1 payload. ERP returns 500 twice, then 200. LinkUp records all attempts but does not create another order.

---

## 22. Reliability, Audit, Outbox, Idempotency & Bulk Jobs

**Priority:** P0/P1  
**Owns/touches:** `idempotency_records`, `outbox_events`, `audit_logs`, `bulk_jobs`, `bulk_job_items`

### Purpose

Provides cross-cutting guarantees that retries are safe, domain events are not lost, privileged actions are auditable and large operations do not block API requests.

### Source of truth / ownership

- `idempotency_records` owns result/replay contract for retry-prone commands.
- `outbox_events` owns durable unpublished domain events committed with business state.
- `audit_logs` owns append-only privileged/security change evidence.
- `bulk_jobs`/items own long-running import/export progress and row-level outcomes.

### Domain invariants

- Idempotency is enforced by a DB unique constraint/atomic claim, never only `SELECT then INSERT`.
- Idempotency scope includes store + operation + client/actor context as needed + key.
- Request semantic hash is stored. Same key with different semantic request returns `IDEMPOTENCY_KEY_REUSED`.
- Successful/retriable command response/resource reference can be replayed for the same key.
- Outbox event is inserted in the same transaction as the domain mutation that requires the event.
- Outbox dispatcher uses safe row claiming, attempt count, backoff and processed timestamp. At-least-once delivery means consumers must be idempotent.
- Audit records are append-only and redact secrets/passwords/tokens/card data.
- Bulk jobs return 202 quickly and process bounded chunks; no 50k-row synchronous transaction.
- Bulk job cancellation is cooperative: already committed batches remain committed and are reported.
- Workers must checkpoint progress so crash/restart can resume safely.
- Poison messages/jobs eventually move to terminal failure/dead-letter/ops queue instead of infinite retry.
- Operational health measures outbox backlog age, failed attempts and bulk-job failures.

### State machines

| Aggregate | Allowed lifecycle |
|---|---|
| Idempotency record | `IN_PROGRESS → SUCCEEDED | FAILED_RETRYABLE | FAILED_FINAL` according to command policy; stale IN_PROGRESS requires recovery lease/timeout. |
| Outbox | `PENDING → PROCESSING → PUBLISHED`; expired processing leases are reclaimed; exhausted failures become `DEAD`. |
| Bulk job | `QUEUED → PROCESSING → COMPLETED | PARTIAL | FAILED | CANCELLED`. |

### Operation business contracts

| Operation | PRE-CONDITIONS | Business logic / transaction | POST-CONDITIONS | Failure / rollback / retry | Events / side effects | Primary risk |
|---|---|---|---|---|---|---|
| Claim idempotency key | Operation requires idempotency; key format/length valid. | Attempt atomic insert/claim with request hash. On conflict load existing record and compare semantic hash/state. | Exactly one logical executor owns new command; duplicates replay/wait/return existing contract. | Stale IN_PROGRESS recovered only by explicit lease/timeout rule. | — | Duplicate orders/refunds from race. |
| Write domain + outbox | Business mutation is valid and an event is required. | Within same DB transaction update domain state and insert outbox envelope with event version/aggregate/request context. | It is impossible to commit domain change while losing its required event row. | Transaction rollback removes both. | Domain-specific event | Lost notification/webhook/integration event. |
| Dispatch outbox | Worker claims due rows with lock/lease. | Deliver/enqueue to relevant internal consumers, record attempts, mark processed only according to delivery contract. | Event is eventually processed at least once or visibly failed. | Worker crash causes safe retry; consumer idempotency prevents duplicate side effects. | `outbox.failed` telemetry | Duplicate delivery or lost event. |
| Create/process bulk job | Actor authorized; input file/filter valid, within quota. | Persist job, enqueue. Worker streams/parses and processes bounded batches with per-item errors/checkpoints. | API remains responsive; job exposes progress/success/error counts and result file. | One batch failure does not hold giant transaction. Fatal format error can fail job without partial hidden state. | `bulk.job.created/completed` | Resource exhaustion, partial unknown imports. |
| Write audit log | Privileged action occurred or failed action qualifies for security audit. | Append actor, action, target, request ID, safe before/after metadata; redact secrets. | Investigation can reconstruct who changed operational state. | Audit failure for critical financial/inventory action should be treated according to strict policy—prefer same transaction when feasible. | — | Untraceable fraud/changes. |

### Explicitly forbidden

- ❌ Implement idempotency as only `if existing: return` without DB uniqueness/atomic claim.
- ❌ Delete audit or financial/inventory ledger entries to fix UI.
- ❌ Publish an external side effect before the business DB transaction commits unless workflow explicitly supports compensation.
- ❌ Process huge imports in API request thread.
- ❌ Retry poison jobs forever.

### Risk register

| Risk | Severity | Required control |
|---|:---:|---|
| Duplicate side effects | P0 | Idempotency record + idempotent consumers. |
| Lost events | P0 | Transactional outbox. |
| Audit tampering | P0 | Append-only logs, restricted DB permissions. |
| Worker double-processing | P0 | SKIP LOCKED/lease + idempotent handler. |
| Bulk resource exhaustion | P1 | Chunking, quotas, file/row limits. |

### Generalized business example

Two identical `/checkout/complete` requests arrive simultaneously. Atomic idempotency claim allows only one executor to create the order; the other receives the same saved order response rather than reserving/deducting inventory twice.

---

## 23. Cross-Domain Critical Flows

### 23.1 Customer checkout → paid order

1. Storefront creates/loads durable cart; variant prices are display estimates resolved by server.
2. Create checkout snapshot from cart. Resolve customer/guest identity and current price/market context.
3. Validate shipping address. Obtain shipping rates outside DB transaction and persist quote with expiry/context hash.
4. Evaluate coupons/automatic discounts without consuming redemption.
5. Recalculate final authoritative checkout totals.
6. Atomically reserve inventory with checkout expiry.
7. Create local payment intent, then create provider session using provider/local idempotency.
8. Payment confirmation comes from verified provider state/webhook—not browser.
9. `checkout.complete` atomically claims Idempotency-Key and revalidates checkout, payment and reservation.
10. Create immutable Order + order items + addresses + tax/discount/shipping snapshots.
11. Consume inventory reservations and commit discount redemptions at configured commercial point.
12. Write order/payment/inventory status history + outbox events inside transaction; commit.
13. Workers send confirmation, create/queue fulfillment/integrations and invalidate analytics/cache.

**Success post-condition:** one logical checkout produces at most one order; order totals match immutable snapshots; consumed inventory cannot be sold again; required side-effect events are durable.

### 23.2 Payment webhook race with browser completion

Both browser and webhook may arrive in any order. Business logic must not assume browser first or webhook first.

```text
Browser says success ─┐
                     ├─> NEVER mark paid directly
Verified webhook ────┘
       ↓
payment_provider_events unique inbox
       ↓
payment transaction ledger
       ↓
derived payment state
       ↓
checkout/order completion can verify that authoritative state
```

### 23.3 Order cancellation matrix

| Situation | Inventory action | Payment action | Fulfillment/shipping action | Order behavior |
|---|---|---|---|---|
| Unpaid, unfulfilled | Release ACTIVE reservation; no CONSUMED allocation is silently reversed | Cancel/expire intent | None | Cancel immediately |
| Paid, unfulfilled | Restore/release stock exactly once | Void/refund according to capture state | None | Cancel with refund workflow/status |
| Paid, fulfillment created but not shipped | Restore through fulfillment cancellation | Refund/void | Cancel fulfillment/provider shipment if created | Cancel after/while coordinated actions are tracked |
| Shipped | Do not pretend stock is local | Refund usually follows return/RTO policy | Carrier cancellation may be impossible | Use return/RTO workflow rather than naive cancellation |
| Partially fulfilled | Only remaining unfulfilled allocation restored | Refund eligible cancelled portion | Preserve shipped fulfillment | Order may need partial-cancel representation rather than one destructive status |

### 23.4 Return → inventory → refund

```text
Return requested
  ↓  (NO stock/refund yet)
Approved
  ↓
Physically received
  ├─ RESTOCK → inventory movement +sellable
  ├─ DAMAGED → damaged/non-sellable movement
  └─ REJECTED → no sellable increment
  ↓
Refund eligibility from original order allocations
  ↓
Payment refund ledger/provider
  ↓
Return closes
```

### 23.5 Inventory reservation expiry

1. Worker queries due checkout reservations in bounded batch.
2. Rows are claimed with lock/lease so two workers cannot process same reservation concurrently.
3. Re-check checkout/order/reservation state under lock.
4. If still active and expired: transition reservation to EXPIRED and decrement `reserved`; no physical movement row is written.
5. Write event and commit.
6. Duplicate worker run becomes a no-op.

## 24. Business Error Catalogue

| Code | HTTP | Business meaning |
|---|---:|---|
| `OUT_OF_STOCK` | 409 | Authoritative inventory cannot reserve requested quantity. |
| `CHECKOUT_EXPIRED` | 410 | Checkout expiry passed and cannot be completed. |
| `CHECKOUT_VERSION_CONFLICT` | 409 | Client is modifying/completing a stale checkout version. |
| `PRICE_CHANGED` | 409 or business-specific response | Authoritative price changed and policy requires customer reconfirmation. |
| `SHIPPING_RATE_EXPIRED` | 409 | Selected rate is no longer valid for current checkout context. |
| `IDEMPOTENCY_KEY_REUSED` | 409 | Same key used with a different semantic request. |
| `INVALID_STATE_TRANSITION` | 409 | Aggregate cannot move from current state to requested target. |
| `PAYMENT_NOT_CONFIRMED` | 409 | Verified financial state does not satisfy completion rule. |
| `PAYMENT_STATE_UNKNOWN` | 409/202 | Provider result is uncertain; reconciliation required. |
| `REFUND_EXCEEDS_AVAILABLE` | 409 | Requested refund exceeds remaining refundable balance. |
| `RETURN_QTY_EXCEEDED` | 409 | Requested/received return quantity exceeds remaining eligible quantity. |
| `FULFILLMENT_QTY_EXCEEDED` | 409 | Fulfillment exceeds remaining order-item quantity. |
| `DUPLICATE_PROVIDER_EVENT` | 200/no-op webhook semantics | Provider event was already durably accepted. |
| `PERMISSION_DENIED` | 403 | Authenticated actor lacks required effective permission. |
| `RESOURCE_NOT_FOUND` | 404 | Not found or hidden due to ownership/store-scope rule. |
| `VERSION_CONFLICT` | 409 | Optimistic concurrency version/ETag mismatch. |

## 25. Recovery & Reconciliation Rules

| Failure scenario | Required recovery behavior |
|---|---|
| Gateway timeout after payment-session create | Do not immediately create a second provider order. Query/reconcile by local/provider idempotency/reference. Keep intent in UNKNOWN/PENDING state until resolved. |
| Webhook processor crashes after transaction commit | Provider inbox row/outbox remains; worker retries. Transaction handlers must be idempotent. |
| Worker crashes after claiming outbox job | Lease/processing timeout makes it eligible again. Consumer dedupe prevents second business effect. |
| Redis unavailable | Durable cart/session-sensitive truth falls back to PostgreSQL where designed. Cache failure must not invent data. |
| Search index unavailable | PostgreSQL remains catalog source of truth; admin writes succeed if core DB commit succeeds and outbox retries indexing. |
| Email/SMS provider down | Commerce commit succeeds; notification delivery retries asynchronously. |
| Shipping provider timeout after create request | Keep local shipment in CREATING/UNKNOWN; reconcile by local reference before retrying provider creation. |
| Inventory projection mismatch with physical count | Use reconciliation adjustment movement; never delete/alter old movements. |
| COD settlement mismatch | Place item in exception/reconciliation state; do not force paid/settled. |
| Bulk import worker crash | Resume from checkpoint/batch state; previously committed batches remain visible and reported. |

## 26. Concurrency-Critical Operations

| Operation | Concurrency danger | Required protection | Mandatory test |
|---|---|---|---|
| Inventory reserve | Oversell | Atomic conditional update or row lock + deterministic order | 10 requests against stock=5 → exactly 5 success |
| Checkout complete | Duplicate order | DB idempotency claim + unique constraint | 10 same keys → one order |
| Coupon limited redemption | Usage limit exceeded | Lock/unique redemption ledger | Concurrent final-use requests respect cap |
| Refund | Over-refund | Lock refundable ledger/refund protection + idempotency | Two full refunds concurrently → one succeeds |
| Fulfillment create | Over-fulfillment | Lock order-item remaining quantity | Two workers cannot fulfill same remaining qty twice |
| Return receive | Double restock | Return-item receipt state/quantity lock | Duplicate receive does not add stock twice |
| Transfer receive | Inventory duplication | Transfer-item remaining receivable lock | Duplicate receipt idempotent |
| Refresh token rotation | Session replay | Token row/family lock + one-time use | Two simultaneous refresh calls → one valid rotation |
| Primary domain swap | Two primaries | Transactional update + uniqueness | Concurrent promotions leave one primary |

## 27. Authorization Business Rules

- Every admin command names a permission code. Controllers may reject early, but service layer must remain protected when invoked internally by other HTTP handlers.
- Ownership/store checks happen before returning resource existence details where IDOR would leak data.
- Financial operations (`refunds.create`, offline payment, capture/void), staff/role changes, integration secrets and inventory reconciliation should be high-risk permissions separated from generic write access.
- Customer JWT authorizes only the token's customer; customer IDs from URL/body do not expand ownership.
- Guest order access requires a high-entropy signed/opaque order-access token with expiry/revocation policy.
- Internal service endpoints require service identity/private network policy and are never exposed as public admin shortcuts.

## 28. Audit Requirements by Risk

| Action | Audit level | Minimum fields |
|---|:---:|---|
| Role/staff permission change | Critical | actor, target staff, previous roles, new roles, request_id |
| Inventory manual adjustment/reconciliation | Critical | actor, item, location, delta/count, reason, before/after projection |
| Refund/manual payment/COD collection | Critical | actor, order/payment/refund, amount, currency, reason/reference |
| Order cancellation/hold | High | actor/source, order, previous/new state, reason |
| Integration secret/config change | Critical | actor, provider, fields changed; **never secret value** |
| Store currency/status/settings | High | actor, previous/new safe settings |
| Product price change | Normal/High by business | actor, variant, old/new price |
| CMS content change | Normal | actor, content id, version/action |
| Failed high-risk authorization | Security | actor/session/IP fingerprint where safe, target/action |

## 29. Codex / Developer Implementation Rules

- Before implementing a domain, read its section in this file plus the matching DB/API sections.
- Do not create a generic repository method that lets callers directly update protected status/money/stock fields.
- Business calculations live in domain/service functions with unit tests, not routers or Pydantic schemas.
- Repositories expose purpose-specific persistence operations for concurrency-critical actions.
- Provider adapters translate provider-specific payload/state into internal typed DTOs; provider names/status strings must not spread through core domain logic.
- Every P0 state-changing command must document its transaction boundary in code comments/docstring or use-case tests.
- Every operation marked idempotent must have a duplicate-request test.
- Every concurrency-critical operation must have a real PostgreSQL integration/race test; SQLite-only tests are insufficient.
- Any change that weakens an invariant in this document requires updating this file/ADR before merge.
- Do not implement P2 functionality merely because tables/contracts exist; expose only features included in the current implementation phase.

## 30. Mandatory Test Scenarios Before Production

| Domain | Required scenarios |
|---|---|
| Catalog | Publish incomplete product rejected; duplicate SKU; duplicate option combination; old order unaffected by price/name edit. |
| Inventory | Stock=5 with 10 simultaneous reserves; duplicate release; duplicate commit; expired reservation worker race; manual adjustment ledger. |
| Checkout | Empty cart; stale checkout version; stale price; expired shipping quote; expired checkout; same idempotency key repeat; same key different body. |
| Payments | Invalid webhook signature; same provider event x5; out-of-order events; provider timeout/reconcile; partial capture/refund; concurrent over-refund. |
| Orders | Immutable address/price snapshot; illegal status transition; cancel unpaid; cancel paid-unfulfilled; partial fulfillment cancellation. |
| Fulfillment | Concurrent over-fulfillment; duplicate shipment create; tracking event regression; split fulfillment. |
| Returns | Over-return rejected; duplicate receive; restock vs damaged; refund original value not current price. |
| RBAC | Cross-role forbidden operations; removed staff session; concurrent refresh-token reuse; last-owner protection. |
| CMS | Stored XSS payload; draft not public; redirect loop/open redirect; navigation cycle. |
| Reliability | Worker crash between commit and side effect; outbox replay; bulk job resume; poison job terminal failure. |

## 31. Production Sign-Off Checklist

- [ ] All P0 domain state machines are implemented centrally and tested.
- [ ] All financial values use Decimal/NUMERIC end-to-end.
- [ ] Store/customer ownership checks have IDOR tests.
- [ ] Inventory reserve/release/commit pass real concurrent PostgreSQL tests.
- [ ] Checkout complete passes duplicate/concurrent Idempotency-Key tests.
- [ ] Provider webhook raw signature + dedupe + replay tests pass.
- [ ] Refundable/capturable balances derive from ledger, not editable status.
- [ ] Order commercial snapshots cannot be mutated by catalog/customer-address edits.
- [ ] Outbox is written in same transactions as required domain events and backlog is observable.
- [ ] External providers use explicit timeout/retry/reconciliation rules.
- [ ] Audit logs exist for high-risk staff/inventory/financial/integration changes.
- [ ] Redis/cache outage does not destroy durable commerce truth.
- [ ] Bulk operations are bounded and resumable.
- [ ] No P1/P2 placeholder endpoint is exposed as if production-ready when logic is absent.
- [ ] API error codes match the shared error catalogue.
- [ ] Business logic, API architecture, DB schema and code naming use the same vocabulary.

## 32. Recommended Documentation Freeze Order

## 33. Documentation Remediation Freeze Addendum

### Payment and refund vocabulary

Payment intent lifecycle is `CREATED → PENDING_CUSTOMER_ACTION → PROCESSING →
AUTHORIZED → CAPTURED`, with `FAILED`, `CANCELLED`, and
`RECONCILIATION_REQUIRED` side states. Provider-specific statuses stay inside
adapters. An unknown timeout outcome is never marked `FAILED` automatically.

Refund lifecycle is `REQUESTED → PROCESSING → SUCCEEDED`, with
`FAILED_RETRYABLE`, `FAILED_FINAL`, and `RECONCILIATION_REQUIRED` side states.
`REQUESTED`, `PROCESSING`, `SUCCEEDED`, and `RECONCILIATION_REQUIRED` amounts
are protected against the remaining refundable balance. Refund creation owns a
short PostgreSQL transaction that locks the relevant order/payment refundable
ledger, claims the amount idempotently, and writes the refund record before any
provider call.

### Tax/GST decision boundary

Tax is server-authoritative, calculated by a dedicated service, and persisted as
immutable order tax lines. Place-of-supply and intra/inter-state capability are
supported, and historical order tax never changes. GST registrations, CGST/SGST/
IGST policy, HSN/SAC requirements, shipping tax, tax-inclusive pricing,
rounding, and invoice/credit-note compliance remain **DECISION REQUIRED — GST
POLICY** and must not be invented by implementation.

### Exact variant identity and concurrency

Variant option signatures are generated from validated sorted option/value IDs;
one value per product option and same-product ownership are validated in the
same transaction. `UNIQUE(product_id, option_signature)` prevents duplicate
sellable combinations. Carts and checkouts use mandatory versions; stale writes
return a version conflict.

Release 1 optimistic versioning applies to `store_settings`, `products`,
`product_variants`, `pages`, and `blog_posts`, in addition to mandatory cart and
checkout versions. Orders, payments, refunds, inventory, and fulfillments do not
use generic version PATCH semantics; their state changes use explicit commands,
locks, and state-machine rules.

```text
DB_SCHEMA.md
  ↓
BUSINESS_LOGIC.md   ← this document
  ↓
API_ARCHITECTURE.md (contracts aligned with final domain rules)
  ↓
ARCHITECTURE.md (code/layer/package design)
  ↓
TESTING_STRATEGY.md
  ↓
AGENTS.md
  ↓
IMPLEMENTATION_PLAN.md / phase tickets
  ↓
FINAL SDR
  ↓
CODEX IMPLEMENTATION
```

> **Technical Lead rule:** If code, API and this document disagree on a P0 invariant, stop implementation and resolve the architecture explicitly. Do not let the implementation silently become the new specification.
