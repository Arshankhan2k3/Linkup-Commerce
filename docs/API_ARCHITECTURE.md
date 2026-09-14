 

# LinkUp Commerce Engine — API Architecture & Business Logic Specification

**Document type:** API Design / Technical SDR Input**Version:** v2.0**Target stack:** FastAPI + PostgreSQL + Redis + Alembic + async workers**Deployment model:** One client storefront per isolated VPS/database initially, with a reusable backend and custom frontend per deployment; store-scoped architecture remains available for future SaaS/multi-store evolution.**API style:** REST-first modular monolith now; service/domain layer kept transport-agnostic so GraphQL can be added later without rewriting commerce logic.

> This document defines API contracts, business responsibilities, negative rules and major production risks. It is intentionally more strict than a simple endpoint checklist because checkout, inventory, payment and fulfillment bugs directly create revenue loss.

## 1. Executive Architecture Decisions

| Decision           | Standard                                                                                                               | Why                                                                          |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| API surfaces       | Separate Storefront, Admin, Webhook, Internal/Worker and Ops surfaces.                                                 | Reduces accidental privilege mixing and makes rate/security policy explicit. |
| Versioning         | All external APIs under`/api/v1`; breaking changes create `/v2`, while additive fields remain backward-compatible. | Client storefronts and integrations can be upgraded intentionally.           |
| Identifiers        | Opaque UUIDs/tokens externally. Store scope comes from auth/deployment context, not request body.                      | Prevents cross-store IDOR and guessable IDs.                                 |
|                    |                                                                                                                        |                                                                              |
|                    |                                                                                                                        |                                                                              |
|                    |                                                                                                                        |                                                                              |
|                    |                                                                                                                        |                                                                              |
| Money              | Decimal strings at JSON boundary; PostgreSQL`NUMERIC(19,4)` internally.                                              | Avoids floating-point money errors.                                          |
| Time               | RFC3339/ISO-8601 UTC timestamps in API responses; store timezone only for display/scheduling input.                    | Avoids timezone ambiguity.                                                   |
| Pagination         | Cursor pagination for growing collections; default 25, max 100 unless endpoint says otherwise.                         | Stable under inserts/deletes and avoids deep OFFSET cost.                    |
| Idempotency        | Required for checkout completion, refunds, manual order completion and other side-effecting retry-prone operations.    | Network retries must not double-order, double-charge or double-refund.       |
| Concurrency        | State-changing services use DB constraints/row locks/atomic SQL/state machines, not check-then-write logic.            | Prevents overselling and duplicate transitions.                              |
| Async work         | Emails, webhooks, media processing, heavy imports/exports, provider retries and scheduled cleanup run in workers.      | Keeps request latency bounded and failures retryable.                        |
| External providers | Payment/shipping calls have strict timeout, retry policy, circuit breaker and local intent records.                    | Provider outage must not lock core DB transactions.                          |
| Events             | Transactional outbox is the source for reliable domain side effects.                                                   | No lost event after successful DB commit.                                    |
| Security           | Least-privilege permission codes on admin APIs; customer/order-token ownership on storefront APIs.                     | Avoids frontend-only authorization.                                          |

## 2. API Surface Map

| Surface           | Base path                     | Typical caller                   | Auth                                                | Rule                                            |
| ----------------- | ----------------------------- | -------------------------------- | --------------------------------------------------- | ----------------------------------------------- |
| Storefront        | `/api/v1/storefront`        | Custom Next.js/mobile storefront | Public, opaque cart/checkout token, or Customer JWT | Never exposes admin/internal fields             |
| Merchant Admin    | `/api/v1/admin`             | LinkUp client admin panel        | Staff JWT + granular permission                     | Every request store-scoped from auth context    |
| Authentication    | `/api/v1/auth`              | Merchant/staff auth UI           | Public/refresh/JWT                                  | Aggressive anti-abuse controls                  |
| Provider Webhooks | `/api/v1/webhooks`          | Razorpay/Stripe/Shiprocket/etc.  | Provider signature/secret                           | Raw-body verification + inbox dedupe + fast ACK |
| Operations        | `/health/ready`, `/metrics` | Load balancer/observability     | Ops/service auth                                    | No sensitive payloads; not versioned commerce APIs |

## 3. Standard Request Contract

### Required/common headers

| Header                             | Where                             | Purpose                                         |
| ---------------------------------- | --------------------------------- | ----------------------------------------------- |
| `Authorization: Bearer <token>`  | Authenticated admin/customer APIs | Identity                                        |
| `X-Request-ID`                   | All requests; generated if absent | Traceability across logs/traces                 |
| `Idempotency-Key`                | Selected POST operations          | Safe retry of side effects                      |
| `If-Match` or `version` field  | High-contention edits             | Optimistic concurrency / lost update protection |
| `Content-Type: application/json` | JSON APIs                         | Contract enforcement                            |
| Provider signature headers         | Webhook endpoints                 | Verify external event authenticity              |

### Request limits

- Default JSON body limit: **1 MB**. Media uploads use signed object-storage upload, not API-body upload.
- Default list array limit: **100** items; endpoint-specific upper bound may be lower.
- Search query max length: **200** characters unless endpoint specifies less.
- Unknown fields should be rejected for sensitive write DTOs (`extra='forbid'`) to surface client mistakes.

## 4. Standard Response Contract

Success example:

```json
{"data":{"order_id":"...","status":"PENDING"},"meta":{"request_id":"req_..."}}
```

Error example:

```json
{"error":{"code":"OUT_OF_STOCK","message":"One or more items are unavailable","details":[{"variant_id":"...","available":0}]},"meta":{"request_id":"req_..."}}
```

**Rules:** machine code is stable; human message can change. Never put stack traces, SQL, provider secrets or internal exception objects in production responses.

## 5. HTTP Status / Error Code Rules

|  Status | Use                                                                                               |
| ------: | ------------------------------------------------------------------------------------------------- |
|     200 | Successful read/update or idempotent replay returning existing result.                            |
|     201 | Synchronous resource created.                                                                     |
|     202 | Accepted async operation/provider work/bulk job.                                                  |
|     204 | Successful delete/revoke with no body.                                                            |
|     400 | Malformed business input that is not schema validation.                                           |
|     401 | Missing/invalid authentication.                                                                   |
|     403 | Authenticated but permission denied.                                                              |
|     404 | Resource absent**or intentionally hidden to prevent IDOR**.                                 |
|     409 | State conflict: out of stock, duplicate unique resource, version conflict, idempotency-key reuse. |
|     410 | Expired checkout/token when useful to distinguish from 404.                                       |
|     422 | DTO/schema validation failure.                                                                    |
|     429 | Rate limit exceeded; return`Retry-After`.                                                       |
| 502/503 | Upstream provider unavailable when request cannot be safely accepted asynchronously.              |

## 6. Pagination, Filtering & Sorting

Use connection-style responses for large collections:

```json
{"data":{"items":[...],"page_info":{"has_next_page":true,"end_cursor":"opaque..."}}}
```

- `first`: default 25, max 100.
- `after`: opaque signed/base64 cursor containing stable sort tuple, normally `(created_at,id)`.
- Never accept raw SQL column/order expressions from clients.
- Deep export/reporting requests move to Bulk Jobs.

## 7. Rate Limit Classes

| Class            | Example                          | Suggested initial policy                                     |
| ---------------- | -------------------------------- | ------------------------------------------------------------ |
| Public browse    | products/pages                   | IP + store bucket; generous, cache/CDN first                 |
| Public mutation  | cart/customer login              | tighter IP/token bucket                                      |
| Checkout/payment | reserve/complete/payment session | very tight per cart/customer/IP + fraud signals              |
| Admin reads      | catalog/orders                   | per staff + store                                            |
| Admin writes     | product/inventory/refund         | per staff + store, lower burst                               |
| Integration/app  | API token                        | per integration + store                                      |
| Webhook intake   | provider                         | provider/IP-independent signature validation + abuse ceiling |

Return `429` with `Retry-After`. Do not make the rate-limit key only IP-based because offices/NATs share IPs.

## 8. Module/API Count Summary

|  # | Module                                              |     API count | Primary priority               |
| -: | --------------------------------------------------- | ------------: | ------------------------------ |
|  1 | Store Foundation & Sales Channels                   |             8 | P0:5, P1:3                     |
|  2 | Identity, Staff & RBAC                              |            15 | P0:5, P1:10                    |
|  3 | Customers, Addresses & Consent                      |            12 | P0:9, P1:3                     |
|  4 | Product Catalog, Variants, Collections & Metafields |            28 | P0:13, P1:12, P2:3             |
|  5 | Locations, Inventory & Stock Ledger                 |            14 | P0:8, P1:6                     |
|  6 | Markets, Catalogs & Price Lists                     |             9 | P2:9                           |
|  7 | Discounts, Coupons & Promotions                     |             9 | P1:9                           |
|  8 | Cart & Checkout Orchestration                       |            14 | P0:13, P1:1                    |
|  9 | Orders & Immutable Commercial Snapshot              |            12 | P0:6, P1:6                     |
| 10 | Payments, Transactions & Refund Ledger              |             9 | P0:5, P1:4                     |
| 11 | Fulfillment, Shipping, NDR & COD                    |            14 | P0:6, P1:8                     |
| 12 | Returns & Reverse Logistics                         |             9 | P1:9                           |
| 13 | CMS, Navigation & SEO                               |            23 | P1:23                          |
| 14 | Notifications & Customer Communication              |             5 | P1:5                           |
| 15 | Integrations, Apps & Webhooks                       |            11 | P1:5, P2:6                     |
| 16 | Reliability, Audit, Outbox, Idempotency & Bulk Jobs |             6 | P0:1, P1:5                     |
|    | **TOTAL**                                           | **198** | **P0:71, P1:109, P2:18**      |

# 9. Module-by-Module API Specification

## 1. Store Foundation & Sales Channels

Store identity, operational defaults and order-origin channels. In the current LinkUp model one client deployment normally has one active store, while all APIs remain store-scoped for future evolution. DNS, public host mapping, reverse proxy configuration and TLS/SSL certificates are deployment infrastructure, not commerce-managed resources.

**Database ownership/touchpoints:** `stores`, `store_settings`, `sales_channels`
**API count:** 8

|  # | Pri | API                                                 | Auth           | Purpose                                                         | Request                                                                                                               | Response                                                         | Core business logic                                                                                                                   | Must NOT do                                                                                            | Main risk                       | Events                        |
| -: | :-: | --------------------------------------------------- | -------------- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------- | ----------------------------- |
|  1 | P0 | `GET /api/v1/storefront/store`                    | Public         | Return public store identity and safe storefront configuration. | None                                                                                                                  | {store_id,name,currency,country,timezone,public_settings} | Resolve the store from configured deployment/store context; expose only public-safe settings.                                          | Never expose secret/config JSON, gateway keys, internal flags or staff data.                           | Configuration leakage           | —                            |
|  2 | P0 | `GET /api/v1/admin/store`                         | store.read     | Fetch merchant store profile.                                   | None                                                                                                                  | Full StoreResponse                                               | Load store under authenticated staff context.                                                                                         | Do not trust client-computed state/totals; validate ownership, status and permissions server-side.     | Cross-store data leak           | —                            |
|  3 | P0 | `PATCH /api/v1/admin/store`                       | store.write    | Update merchant/store profile.                                  | {name,legal_name,country_code,timezone,status?}                                                                       | Updated StoreResponse                                            | Validate ISO codes/timezone; protect lifecycle status changes with stronger permission.                                               | Do not allow currency/status changes that invalidate existing orders without explicit migration rules. | Invalid global configuration    | store.updated                 |
|  4 | P0 | `GET /api/v1/admin/settings`                      | settings.read  | Fetch operational settings.                                     | None                                                                                                                  | StoreSettingsResponse                                            | Return typed settings, not raw secrets.                                                                                               | Do not trust client-computed state/totals; validate ownership, status and permissions server-side.     | Unsafe configuration exposure   | —                            |
|  5 | P0 | `PATCH /api/v1/admin/settings`                    | settings.write | Update checkout, tax, unit and inventory policies.              | {order_prefix,weight_unit,dimension_unit,tax_inclusive,allow_guest_checkout,inventory_policy,checkout_expiry_minutes} | Updated settings                                                 | Validate ranges and immutable-impact rules; Release 1 accepts`inventory_policy=DENY` only; clear related config cache after commit. | Do not store payment/shipping secrets here; do not accept arbitrary unvalidated config keys.           | Bad settings can break checkout | store.settings.updated        |
|  6 | P1 | `GET /api/v1/admin/sales-channels`                | channels.read  | List order/product sales channels.                              | {first?,after?,status?}                                                                                               | Connection<SalesChannelResponse></saleschannelresponse>          | Store-scoped cursor listing.                                                                                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side.     | Cross-store leak                | —                            |
|  7 | P1 | `POST /api/v1/admin/sales-channels`               | channels.write | Create a custom/manual/API channel.                             | {name,channel_type,config?}                                                                                           | SalesChannelResponse                                             | Validate known channel type and safe config schema.                                                                                   | Do not accept executable code or secrets in generic config.                                            | Untrusted channel configuration | —                            |
|  8 | P1 | `PATCH /api/v1/admin/sales-channels/{channel_id}` | channels.write | Update channel name/status/config.                              | {name?,status?,config?}                                                                                               | SalesChannelResponse                                             | Protect system channels; invalidate cached channel config.                                                                            | Do not delete/rename historical channel identifiers referenced by orders.                              | Order attribution corruption    | —                            |

### Module invariants / business rules

- Every mutable admin operation is store-scoped from auth context; `store_id` is never trusted from request body.
- Public store endpoint exposes a whitelist, not the `store_settings.config` blob.
- Changing default currency after commercial activity requires an explicit migration/business process; existing orders remain immutable.
- Store resolution comes from deployment/store context. DNS, public host mapping, reverse proxy and TLS/SSL are configured outside the commerce API.

### Generalized example

LinkUp deploys ACME Fashion on its own VPS/database. DNS and HTTPS are configured at the deployment layer. The custom frontend calls `/storefront/store` to obtain INR, timezone and safe public storefront configuration such as GA4 and Meta Pixel identifiers.

## 2. Identity, Staff & RBAC

Merchant/staff authentication, sessions and granular authorization. Customer authentication is handled in the Customer module so merchant identities are not mixed with shoppers.

**Database ownership/touchpoints:** `users`, `roles`, `permissions`, `role_permissions`, `staff_members`, `staff_member_roles`, `refresh_tokens`, `audit_logs`
**API count:** 15

|  # | Pri | API                                          | Auth          | Purpose                                                              | Request                                | Response                                                  | Core business logic                                                                                    | Must NOT do                                                                                        | Main risk                  | Events               |
| -: | :-: | -------------------------------------------- | ------------- | -------------------------------------------------------------------- | -------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | -------------------------- | -------------------- |
|  1 | P0 | `POST /api/v1/auth/login`                  | Public        | Merchant/staff login.                                                | {email,password}                       | {access_token,refresh_token,expires_in,staff,permissions} | Verify password, active user, active staff membership; rotate session identifier; log security event.  | Never reveal whether email exists; enforce rate limit and progressive lockout.                     | Credential stuffing        | auth.login.succeeded |
|  2 | P0 | `POST /api/v1/auth/refresh`                | Refresh token | Rotate access/refresh credentials.                                   | {refresh_token}                        | {access_token,refresh_token,expires_in}                   | Hash/lookup refresh token; enforce one-time rotation and revoke reused token family.                   | Never store plaintext refresh token in DB.                                                         | Refresh token replay       | —                   |
|  3 | P0 | `POST /api/v1/auth/logout`                 | Admin JWT     | Revoke current refresh session.                                      | {refresh_token?}                       | 204                                                       | Revoke current session/token family and clear server-side registry.                                    | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Token remains valid        | —                   |
|  4 | P1 | `POST /api/v1/auth/logout-all`             | Admin JWT     | Revoke all staff sessions.                                           | None                                   | 204                                                       | Revoke all refresh tokens for identity; access tokens expire naturally or use short revocation window. | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Stolen sessions            | —                   |
|  5 | P0 | `GET /api/v1/auth/me`                      | Admin JWT     | Return current staff identity, membership and effective permissions. | None                                   | {user,staff_member,roles,permissions}                     | Resolve effective permission set server-side.                                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Permission cache staleness | —                   |
|  6 | P1 | `POST /api/v1/admin/staff/invitations`     | staff.manage  | Invite staff member.                                                 | {email,role_ids[]}                     | {invitation_id,status,expires_at}                         | Create/invite identity safely; membership stays INVITED; send one-time signed invite.                  | Never allow inviter to grant permissions they themselves cannot delegate.                          | Privilege escalation       | staff.invited        |
|  7 | P1 | `POST /api/v1/auth/accept-invite`          | Invite token  | Accept staff invitation and set credential.                          | {invite_token,password,name?}          | {access_token,refresh_token,staff}                        | Verify signed one-time token, expiry and store; activate membership transactionally.                   | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Token replay               | —                   |
|  8 | P1 | `GET /api/v1/admin/staff`                  | staff.read    | List staff.                                                          | {first?,after?,status?}                | Connection<StaffResponse></staffresponse>                 | Cursor list memberships for current store.                                                             | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | PII leakage                | —                   |
|  9 | P1 | `PATCH /api/v1/admin/staff/{staff_id}`     | staff.manage  | Change staff status/profile.                                         | {status?,display_name?}                | StaffResponse                                             | Prevent self-lockout/last-owner lockout according to policy.                                           | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Admin lockout              | —                   |
| 10 | P1 | `DELETE /api/v1/admin/staff/{staff_id}`    | staff.manage  | Remove staff membership.                                             | None                                   | 204                                                       | Soft-disable membership; revoke sessions; preserve audit references.                                   | Do not hard-delete identity/audit history.                                                         | Loss of accountability     | —                   |
| 11 | P0 | `GET /api/v1/admin/roles`                  | roles.read    | List roles with permission summary.                                  | None                                   | RoleResponse[]                                            | Return store roles and system role markers.                                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Permission disclosure      | —                   |
| 12 | P1 | `POST /api/v1/admin/roles`                 | roles.manage  | Create custom role.                                                  | {name,description,permission_codes[]}  | RoleResponse                                              | Validate permission catalog; prevent forbidden super-admin permissions.                                | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Privilege escalation       | —                   |
| 13 | P1 | `PATCH /api/v1/admin/roles/{role_id}`      | roles.manage  | Update role and permissions.                                         | {name?,description?,permission_codes?} | RoleResponse                                              | Apply permission replacement transactionally; invalidate authorization cache.                          | Do not let user edit protected owner/system role unless policy permits.                            | Privilege escalation       | role.updated         |
| 14 | P1 | `DELETE /api/v1/admin/roles/{role_id}`     | roles.manage  | Delete unused custom role.                                           | None                                   | 204                                                       | Reject protected or assigned roles unless reassignment occurs first.                                   | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Orphan staff permissions   | —                   |
| 15 | P1 | `PUT /api/v1/admin/staff/{staff_id}/roles` | staff.manage  | Replace staff role assignments.                                      | {role_ids[]}                           | StaffResponse                                             | Validate role ownership and delegability; atomic replace.                                              | Do not accept permission codes directly on staff if RBAC model is role-based.                      | Privilege escalation       | staff.roles.updated  |

### Module invariants / business rules

- Access JWTs are short-lived; refresh tokens are rotated, hashed at rest and revocable.
- Authorization checks happen in service/dependency layer, never only in frontend.
- Permission cache must be invalidated immediately after role/staff changes.
- Last active owner/super-admin cannot accidentally remove their own required access.

### Generalized example

Store owner invites a warehouse manager with `inventory.read`, `inventory.write` and `orders.read`. The manager cannot grant themselves refunds because effective permissions are always calculated from server-owned role mappings.

## 3. Customers, Addresses & Consent

Storefront customer identity, guest/customer profiles, saved addresses and auditable marketing consent.

**Database ownership/touchpoints:** `customers`, `customer_addresses`, `customer_consents`, plus read access to `orders`
**API count:** 12

|  # | Pri | API                                                               | Auth             | Purpose                                  | Request                                                  | Response                                      | Core business logic                                                                                                                        | Must NOT do                                                                                        | Main risk                   | Events |
| -: | :-: | ----------------------------------------------------------------- | ---------------- | ---------------------------------------- | -------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | --------------------------- | ------ |
|  1 | P0 | `POST /api/v1/storefront/customers/register`                    | Public           | Create customer account.                 | {email,phone?,password,first_name?,last_name?}           | CustomerSessionResponse                       | Normalize identifiers; enforce store uniqueness; hash password; send verification if enabled.                                              | Do not auto-subscribe marketing consent during registration.                                       | Account enumeration / abuse | —     |
|  2 | P0 | `POST /api/v1/storefront/customers/login`                       | Public           | Customer login.                          | {email_or_phone,password}                                | CustomerSessionResponse                       | Rate-limit, verify active customer and password.                                                                                           | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Credential stuffing         | —     |
|  3 | P0 | `GET /api/v1/storefront/customers/me`                           | Customer JWT     | Fetch own customer profile.              | None                                                     | CustomerResponse                              | Use customer ID from token, never request body.                                                                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | IDOR                        | —     |
|  4 | P0 | `PATCH /api/v1/storefront/customers/me`                         | Customer JWT     | Update own profile.                      | {first_name?,last_name?,phone?}                          | CustomerResponse                              | Verify re-auth/OTP where sensitive identifier changes.                                                                                     | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Account takeover            | —     |
|  5 | P0 | `GET /api/v1/storefront/customers/me/addresses`                 | Customer JWT     | List saved addresses.                    | None                                                     | AddressResponse[]                             | Return only current customer's addresses.                                                                                                  | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | IDOR                        | —     |
|  6 | P0 | `POST /api/v1/storefront/customers/me/addresses`                | Customer JWT     | Create saved address.                    | AddressInput                                             | AddressResponse                               | Validate postal/country fields; enforce one default transactionally.                                                                       | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Invalid delivery data       | —     |
|  7 | P0 | `PATCH /api/v1/storefront/customers/me/addresses/{address_id}`  | Customer JWT     | Update saved address.                    | AddressPatch                                             | AddressResponse                               | Ownership check; does not alter historical order snapshots.                                                                                | Never update`order_addresses` from saved-address edits.                                          | Order history mutation      | —     |
|  8 | P1 | `DELETE /api/v1/storefront/customers/me/addresses/{address_id}` | Customer JWT     | Delete saved address.                    | None                                                     | 204                                           | Ownership check; reassign default if needed.                                                                                               | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Broken default address      | —     |
|  9 | P1 | `POST /api/v1/storefront/customers/me/consents`                 | Customer JWT     | Record marketing/privacy consent change. | {channel,purpose,state,source?}                          | ConsentResponse                               | Append consent history with timestamp/source; use SUBSCRIBED or UNSUBSCRIBED state.                                                        | Never overwrite consent history or infer consent from checkout without explicit policy.            | Regulatory/privacy risk     | —     |
| 10 | P0 | `GET /api/v1/admin/customers`                                   | customers.read   | Admin customer search/list.              | {query?,first?,after?,status?,created_from?,created_to?} | Connection<CustomerSummary></customersummary> | Store-scoped cursor search; redact sensitive fields based on permission.                                                                   | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | PII exposure                | —     |
| 11 | P0 | `GET /api/v1/admin/customers/{customer_id}`                     | customers.read   | Admin customer detail/history.           | None                                                     | CustomerDetailResponse                        | Return profile, consent summary, address summary, aggregate order data.                                                                    | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | PII exposure                | —     |
| 12 | P1 | `PATCH /api/v1/admin/customers/{customer_id}`                   | customers.write  | Admin edit customer metadata/status.     | {first_name?,last_name?,phone?,status?,note?}            | CustomerResponse                              | Audit changes; separate operational status from consent.                                                                                   | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Unauthorized profile change | —     |

### Module invariants / business rules

- Guest checkout may create/link a customer profile, but must not silently create login credentials.
- Historical order addresses are immutable snapshots.
- Consent changes are append-only/auditable; operational customer status is not equivalent to marketing consent.
- `customer_consents` records `channel` plus explicit `purpose`; staff refresh-token storage is never a customer session registry.
- Customer refresh/logout remain deferred architecture notes until a dedicated customer session registry exists; they are not Release 1 HTTP/OpenAPI operations and must not reuse staff refresh-token storage.
- Admin customer search is permission-protected and rate-limited because it exposes PII.

### Generalized example

A guest places an order with `buyer@example.com`; the order stores an immutable shipping address. Later the shopper creates an account using the same verified email and can be safely linked to the customer profile without changing the historical order.

## 4. Product Catalog, Variants, Collections & Metafields

Storefront product discovery and merchant catalog management including options, variants, media, collections, tags and future custom fields.

**Database ownership/touchpoints:** `products`, `product_options`, `product_option_values`, `product_variants`, `variant_option_values`, `media_assets`, `product_media`, `collections`, `collection_products`, `tags`, `product_tags`, `metafield_definitions`, `metafields`
**API count:** 28

|  # | Pri | API                                                               | Auth              | Purpose                                   | Request                                                                               | Response                                              | Core business logic                                                                                     | Must NOT do                                                                                        | Main risk                           | Events             |
| -: | :-: | ----------------------------------------------------------------- | ----------------- | ----------------------------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------------- | ------------------ |
|  1 | P0 | `GET /api/v1/storefront/products`                               | Public            | Browse published products.                | {first?,after?,query?,collection?,tag?,sort?,min_price?,max_price?}                   | Connection<ProductCardResponse></productcardresponse> | Only published/active products; cursor pagination; apply availability/pricing context.                  | Do not expose draft products, cost data, internal notes or unbounded filters.                      | Data leakage / expensive queries    | —                 |
|  2 | P0 | `GET /api/v1/storefront/products/{handle}`                      | Public            | Fetch product detail by public handle.    | None                                                                                  | ProductDetailResponse                                 | Load published product, variants, options, selected media, current price and availability.              | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Cache staleness                     | —                 |
|  3 | P1 | `GET /api/v1/storefront/collections`                            | Public            | List public collections.                  | {first?,after?}                                                                       | Connection<CollectionCard></collectioncard>           | Only active/published collections.                                                                      | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Draft leakage                       | —                 |
|  4 | P1 | `GET /api/v1/storefront/collections/{handle}`                   | Public            | Collection detail and products.           | {first?,after?,sort?}                                                                 | CollectionDetail + ProductConnection                  | Apply collection membership and publication filters.                                                    | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | N+1 / slow query                    | —                 |
|  5 | P1 | `GET /api/v1/storefront/search/suggestions`                     | Public            | Typeahead product/collection suggestions. | {q,limit<=10}                                                                         | SuggestionResponse                                    | Minimum query length; cached/search-index backed.                                                       | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Search abuse                        | —                 |
|  6 | P0 | `GET /api/v1/admin/products`                                    | products.read     | Admin catalog list.                       | {first?,after?,query?,status?,vendor?,tag?}                                           | Connection<AdminProductSummary></adminproductsummary> | Cursor pagination; include draft/archive states according to permission.                                | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Expensive admin query               | —                 |
|  7 | P0 | `POST /api/v1/admin/products`                                   | products.write    | Create product shell.                     | {title,description?,vendor?,status?,handle?,seo?,tags?}                               | ProductResponse                                       | Validate handle uniqueness per store; create audit/outbox event.                                        | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Duplicate handle / invalid state    | product.created    |
|  8 | P0 | `GET /api/v1/admin/products/{product_id}`                       | products.read     | Fetch full editable product.              | None                                                                                  | AdminProductDetail                                    | Eager-load bounded relations needed by editor.                                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | N+1                                 | —                 |
|  9 | P0 | `PATCH /api/v1/admin/products/{product_id}`                     | products.write    | Update product core fields.               | ProductPatchRequest                                                                   | ProductResponse                                       | Optimistic version check recommended; invalidate product/search caches after commit.                    | Do not allow catalog edits to rewrite historical order item snapshots.                             | Lost update                         | product.updated    |
| 10 | P0 | `POST /api/v1/admin/products/{product_id}/publish`              | products.publish  | Publish product.                          | {published_at?}                                                                       | ProductResponse                                       | Require at least one valid sellable variant, valid price and required media/business fields.            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Selling incomplete product          | product.published  |
| 11 | P0 | `POST /api/v1/admin/products/{product_id}/archive`              | products.write    | Archive product.                          | None                                                                                  | ProductResponse                                       | Stop new sales while preserving order/history references.                                               | Never hard-delete a product referenced by order lines.                                             | Historical data deletion            | —                 |
| 12 | P1 | `DELETE /api/v1/admin/products/{product_id}`                    | products.delete   | Delete never-used draft product.          | None                                                                                  | 204                                                   | Allow only when no commercial/history references; otherwise archive.                                    | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Referential corruption              | —                 |
| 13 | P0 | `POST /api/v1/admin/products/{product_id}/options`              | products.write    | Create option such as Size/Color.         | {name,position,values[]}                                                              | ProductOptionResponse                                 | Validate max option/value limits and normalized positions.                                              | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Variant explosion                   | —                 |
| 14 | P1 | `PATCH /api/v1/admin/products/{product_id}/options/{option_id}` | products.write    | Edit product option/value set.            | {name?,position?,values?}                                                             | ProductOptionResponse                                 | Detect impact on existing variants; require explicit destructive-change confirmation semantics.         | Do not silently delete variants when an option value is removed.                                   | Variant mismatch                    | —                 |
| 15 | P0 | `POST /api/v1/admin/products/{product_id}/variants`             | products.write    | Create one variant.                       | {sku,barcode?,option_value_ids[],price,compare_at_price?,weight?,dimensions?,status?} | VariantResponse                                       | Unique SKU per store; validate exact option combination uniqueness; create inventory item.              | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Duplicate SKU / option combination  | variant.created    |
| 16 | P1 | `POST /api/v1/admin/products/{product_id}/variants/bulk`        | products.write    | Create/update bounded variant batch.      | {items[<=100]}                                                                        | BulkVariantResult                                     | Transactional per logical batch or item-level result; validate before writes; larger jobs use bulk API. | Do not accept unbounded arrays; large imports must use bulk jobs.                                  | Partial failure / variant explosion | —                 |
| 17 | P0 | `PATCH /api/v1/admin/variants/{variant_id}`                      | products.write    | Edit one variant.                         | {sku?,barcode?,price?,compare_at_price?,weight?,dimensions?,status?}                | VariantResponse                                       | Optimistic version check; update only current catalog fields; preserve immutable order snapshots.       | Do not rewrite historical order lines or hard-delete a variant with commercial history.             | Lost update / price drift           | variant.updated    |
| 18 | P0 | `POST /api/v1/admin/media`                                      | media.write       | Create media upload session.              | {filename,content_type,size_bytes,checksum?}                                          | {media_id,upload_url,headers,expires_at}              | Validate type/size; issue short-lived object-storage signed upload.                                     | API server must not proxy huge files into memory.                                                  | Malware / oversized upload          | —                 |
| 19 | P0 | `POST /api/v1/admin/media/{media_id}/complete`                  | media.write       | Finalize uploaded media.                  | {checksum?,width?,height?}                                                            | MediaAssetResponse                                    | Verify object exists/size/checksum; enqueue image processing.                                           | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Fake upload completion              | media.ready        |
| 20 | P1 | `PUT /api/v1/admin/products/{product_id}/media`                 | products.write    | Replace ordered product media links.      | {media_ids[],featured_media_id?}                                                      | ProductMediaResponse                                  | Validate media ownership and ready status; atomic ordering.                                             | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Cross-store media reference         | —                 |
| 21 | P1 | `GET /api/v1/admin/collections`                                 | collections.read  | List collections.                         | {first?,after?,query?,status?}                                                        | Connection<CollectionResponse></collectionresponse>   | Cursor list.                                                                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Slow joins                          | —                 |
| 22 | P1 | `POST /api/v1/admin/collections`                                | collections.write | Create manual collection.                 | {title,handle?,description?,status?}                                                  | CollectionResponse                                    | Unique handle; manual membership initially.                                                             | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Duplicate handle                    | —                 |
| 23 | P1 | `PATCH /api/v1/admin/collections/{collection_id}`               | collections.write | Update collection.                        | CollectionPatch                                                                       | CollectionResponse                                    | Invalidate storefront collection cache/search index.                                                    | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Stale storefront                    | collection.updated |
| 24 | P1 | `PUT /api/v1/admin/collections/{collection_id}/products`        | collections.write | Replace/reorder collection products.      | {product_ids[]}                                                                       | CollectionProductsResponse                            | Validate product ownership; bounded list or bulk job.                                                   | Do not allow massive unbounded replacement in request.                                             | Huge transaction                    | —                 |
| 25 | P1 | `PUT /api/v1/admin/products/{product_id}/tags`                  | products.write    | Replace normalized product tags.          | {tags[]}                                                                              | TagResponse[]                                         | Normalize case/whitespace; reuse tag rows.                                                              | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Tag cardinality abuse               | —                 |
| 26 | P2 | `GET /api/v1/admin/metafield-definitions`                       | metafields.read   | List custom field definitions.            | {owner_type?}                                                                         | MetafieldDefinition[]                                 | P2 extension registry.                                                                                  | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Schema confusion                    | —                 |
| 27 | P2 | `POST /api/v1/admin/metafield-definitions`                      | metafields.write  | Create typed custom field definition.     | {namespace,key,owner_type,data_type,validation?}                                      | MetafieldDefinition                                   | Unique namespace/key/owner; validate safe data type.                                                    | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Unbounded custom data               | —                 |
| 28 | P2 | `PUT /api/v1/admin/{owner_type}/{owner_id}/metafields`          | metafields.write  | Upsert custom values.                     | {values:[{definition_id,value}]}                                                      | MetafieldResponse[]                                   | Validate owner/store and value against definition; bounded payload.                                     | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Validation bypass / JSON abuse      | —                 |

### Module invariants / business rules

- Product publication status is separate from physical deletion.
- SKU uniqueness is per store; option combination uniqueness is per product.
- Variant and product edits never rewrite historical order line snapshots.
- Money is Decimal/NUMERIC, never float.
- Large imports or exports use async bulk jobs, not huge synchronous payloads.

### Generalized example

A fashion client creates product `Classic Shirt`, options `Color` and `Size`, and 12 variants. Publishing is blocked until each sellable variant has a valid price; inventory items are created separately so warehouse stock remains an inventory concern, not a product-field hack.

## 5. Locations, Inventory & Stock Ledger

Location-aware stock, reservations, manual adjustments, transfers and immutable stock movement history. This module is the primary defense against overselling.

**Database ownership/touchpoints:** `locations`, `inventory_items`, `inventory_levels`, `inventory_reservations`, `inventory_movements`, `inventory_transfers`, `inventory_transfer_items`
**API count:** 14

|  # | Pri | API                                                              | Auth                | Purpose                                                        | Request                                                               | Response                                              | Core business logic                                                                                                                            | Must NOT do                                                                                        | Main risk                  | Events                         |
| -: | :-: | ---------------------------------------------------------------- | ------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | -------------------------- | ------------------------------ |
|  1 | P0 | `GET /api/v1/storefront/variants/{variant_id}/availability`    | Public              | Return sellable availability without exposing warehouse stock. | {quantity?=1}                                                         | {available:boolean,max_sellable_qty?}                 | Compute from policy/current available; optionally cap returned quantity.                                                                       | Do not expose exact warehouse stock unless product policy explicitly wants it.                     | Inventory leakage          | —                             |
|  2 | P0 | `GET /api/v1/admin/locations`                                  | locations.read      | List fulfillment/stock locations.                              | {first?,after?,status?}                                               | Connection<LocationResponse></locationresponse>       | Store-scoped list.                                                                                                                             | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Cross-store leak           | —                             |
|  3 | P0 | `POST /api/v1/admin/locations`                                 | locations.write     | Create location.                                               | {name,address_fields,fulfills_online_orders?}                         | LocationResponse                                      | Validate unique operational name if required and address.                                                                                      | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Bad routing data           | —                             |
|  4 | P0 | `PATCH /api/v1/admin/locations/{location_id}`                  | locations.write     | Update location.                                               | LocationPatch                                                         | LocationResponse                                      | Protect deactivation when active reservations/transfers exist.                                                                                 | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Orphan inventory           | —                             |
|  5 | P0 | `GET /api/v1/admin/inventory`                                  | inventory.read      | Inventory levels search.                                       | {location_id?,sku?,product_id?,low_stock?,first?,after?}              | Connection<InventoryLevelView></inventorylevelview>   | Join bounded level/item/variant data; cursor pagination.                                                                                       | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Expensive query            | —                             |
|  6 | P0 | `GET /api/v1/admin/inventory/{inventory_item_id}`              | inventory.read      | Inventory item by locations plus ledger summary.               | None                                                                  | InventoryItemDetail                                   | Return levels, availability, active reservations and recent movements.                                                                         | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Sensitive operational data | —                             |
|  7 | P0 | `POST /api/v1/admin/inventory/adjustments`                     | inventory.write     | Apply manual stock adjustment.                                 | {inventory_item_id,location_id,quantity_delta,reason,note?}           | InventoryLevelResponse                                | Single DB transaction: lock/update level + append movement + audit event.                                                                      | Never directly set`available` from client; derive quantities using controlled adjustment rules.  | Stock corruption           | inventory.adjusted             |
|  8 | P1 | `POST /api/v1/admin/inventory/set-on-hand`                     | inventory.reconcile | Reconcile physical stock to counted value.                     | {inventory_item_id,location_id,counted_on_hand,reason}                | InventoryLevelResponse                                | Calculate delta from current state; append reconciliation movement.                                                                            | Do not overwrite ledger history.                                                                   | Lost stock history         | —                             |
|  9 | P0 | `GET /api/v1/admin/inventory/{inventory_item_id}/movements`    | inventory.read      | View stock ledger.                                             | {location_id?,first?,after?,type?}                                    | Connection<InventoryMovement></inventorymovement>     | Append-only ledger query.                                                                                                                      | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Tampering risk             | —                             |
| 10 | P1 | `GET /api/v1/admin/inventory/reservations`                     | inventory.read      | List active/expired reservations.                              | {checkout_id?,order_id?,location_id?,status?,first?,after?}           | Connection<ReservationResponse></reservationresponse> | Operational/debug view; normal creation is internal checkout logic.                                                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Reservation manipulation   | —                             |
| 11 | P1 | `POST /api/v1/admin/inventory/transfers`                       | inventory.transfer  | Create stock transfer.                                         | {from_location_id,to_location_id,items:[{inventory_item_id,qty}]}     | InventoryTransferResponse                             | Validate source/destination differ; create transfer state without changing destination available yet.                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Inventory duplication      | —                             |
| 12 | P1 | `POST /api/v1/admin/inventory/transfers/{transfer_id}/ship`    | inventory.transfer  | Mark transfer shipped.                                         | None                                                                  | InventoryTransferResponse                             | Ship all previously requested transfer lines; move source on-hand to in-transit semantics and append movements.                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Double ship                | —                             |
| 13 | P1 | `POST /api/v1/admin/inventory/transfers/{transfer_id}/receive` | inventory.transfer  | Receive transfer quantities.                                   | {items:[{transfer_item_id,received_qty,damaged_qty?}]}                | InventoryTransferResponse                             | Idempotent partial receipt; update destination levels and movement ledger.                                                                     | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Over-receipt               | —                             |
| 14 | P1 | `POST /api/v1/admin/inventory/transfers/{transfer_id}/cancel`  | inventory.transfer  | Cancel eligible transfer.                                      | {reason}                                                              | InventoryTransferResponse                             | State-machine validation; restore source only when applicable.                                                                                 | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Stock duplication          | —                             |

### Module invariants / business rules

- `available` is a controlled derived/current state; callers never freely write it.
- Physical stock changes append an inventory movement; reserve/release/expire change only the level's `reserved` projection and reservation evidence.
- Reserve/release/commit are idempotent and state-machine driven.
- Inventory allocation uses deterministic location ordering to reduce deadlock risk.
- External payment/shipping network calls never occur while stock row locks are held.

### Generalized example

Only 5 units remain. Ten customers hit checkout together. Atomic reserve allows five successful reservations and rejects the rest with `409 OUT_OF_STOCK`; payment API is never called for rejected checkouts.

## 6. Markets, Catalogs & Price Lists

P2 abstraction for country/B2B/channel-specific product availability and prices. The initial India-only reusable engine may keep only the default catalog path while preserving these boundaries.

**Database ownership/touchpoints:** `markets`, `catalogs`, `catalog_products`, `price_lists`, `price_list_items`
**API count:** 9

| # | Pri | API                                                     | Auth           | Purpose                                             | Request                                        | Response                                      | Core business logic                                                                    | Must NOT do                                                                                        | Main risk                   | Events |
| -: | :-: | ------------------------------------------------------- | -------------- | --------------------------------------------------- | ---------------------------------------------- | --------------------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------- | ------ |
| 1 | P2 | `GET /api/v1/storefront/context`                      | Public         | Resolve storefront market/currency/catalog context. | {country_code?,currency?}                      | {market,currency,catalog_id}                  | Resolve allowed context from domain/customer/location; no arbitrary price-list access. | Never let client pass a raw price_list_id to obtain privileged/B2B pricing.                        | Price bypass                | —     |
| 2 | P2 | `GET /api/v1/admin/markets`                           | markets.read   | List markets.                                       | None                                           | MarketResponse[]                              | Store-scoped.                                                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | —                          | —     |
| 3 | P2 | `POST /api/v1/admin/markets`                          | markets.write  | Create market.                                      | {name,country_codes[],currency,status}         | MarketResponse                                | Validate country overlap policy and currency.                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Ambiguous pricing context   | —     |
| 4 | P2 | `PATCH /api/v1/admin/markets/{market_id}`             | markets.write  | Update market.                                      | MarketPatch                                    | MarketResponse                                | Revalidate catalog/price-list dependencies.                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Broken storefront pricing   | —     |
| 5 | P2 | `GET /api/v1/admin/catalogs`                          | catalogs.read  | List catalogs.                                      | {first?,after?}                                | Connection<CatalogResponse></catalogresponse> | Cursor list.                                                                           | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | —                          | —     |
| 6 | P2 | `POST /api/v1/admin/catalogs`                         | catalogs.write | Create catalog.                                     | {name,context_type,market_id?}                 | CatalogResponse                               | Bind to valid market/customer segment type.                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Unauthorized price exposure | —     |
| 7 | P2 | `PUT /api/v1/admin/catalogs/{catalog_id}/products`    | catalogs.write | Set catalog product availability.                   | {product_ids[]}                                | CatalogProductsResponse                       | Validate ownership; large replacement via bulk job.                                    | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Huge transaction            | —     |
| 8 | P2 | `POST /api/v1/admin/price-lists`                      | pricing.write  | Create price list.                                  | {catalog_id,currency,name,status}              | PriceListResponse                             | One active precedence strategy per context.                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Pricing ambiguity           | —     |
| 9 | P2 | `PUT /api/v1/admin/price-lists/{price_list_id}/items` | pricing.write  | Upsert bounded variant prices.                      | {items:[{variant_id,price,compare_at_price?}]} | PriceListItemResult                           | Decimal validation; duplicate variant prevention; invalidate pricing cache.            | Large price imports must use bulk jobs.                                                            | Wrong price / huge payload  | —     |

### Module invariants / business rules

- Checkout re-resolves authoritative price context; frontend-submitted price is ignored.
- A customer cannot select a privileged price list by identifier.
- Base variant price remains a fallback; contextual prices are explicit overrides.

### Generalized example

India storefront uses INR base prices. Later a US market is added with a USD catalog and price list without changing product variant identity or historical Indian orders.

## 7. Discounts, Coupons & Promotions

Server-side promotion rules, coupon codes, eligibility, redemption history and automatic discounts.

**Database ownership/touchpoints:** `discounts`, `discount_codes`, `discount_rules`, `discount_targets`, `discount_redemptions`
**API count:** 9

|  # | Pri | API                                                                 | Auth                | Purpose                                                   | Request                                                        | Response                                            | Core business logic                                                                                            | Must NOT do                                                                                        | Main risk              | Events           |
| -: | :-: | ------------------------------------------------------------------- | ------------------- | --------------------------------------------------------- | -------------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ---------------------- | ---------------- |
|  1 | P1 | `POST /api/v1/storefront/carts/{cart_token}/discount-codes`          | Cart token/customer | Apply discount code to cart.                              | {code}                                                         | CartPricingResponse                                 | Normalize code; evaluate active dates, customer/order/product eligibility and combinability; price cart again. | Never trust a client-provided discount amount.                                                     | Coupon abuse           | discount.applied |
|  2 | P1 | `DELETE /api/v1/storefront/carts/{cart_token}/discount-codes/{code}` | Cart token/customer | Remove applied code.                                      | None                                                           | CartPricingResponse                                 | Remove code reference and reprice authoritatively.                                                             | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Stale total            | —               |
|  3 | P1 | `GET /api/v1/admin/discounts`                                     | discounts.read      | List discounts.                                           | {first?,after?,status?,type?,query?}                           | Connection<DiscountSummary></discountsummary>       | Cursor list.                                                                                                   | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | —                     | —               |
|  4 | P1 | `POST /api/v1/admin/discounts`                                    | discounts.write     | Create discount definition.                               | {name,type,value,starts_at,ends_at?,combination_policy,status} | DiscountResponse                                    | Validate ranges; percentage <=100; date logic.                                                                 | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Revenue leakage        | —               |
|  5 | P1 | `PATCH /api/v1/admin/discounts/{discount_id}`                     | discounts.write     | Update discount.                                          | DiscountPatch                                                  | DiscountResponse                                    | Protect already-used definition semantics; edits affect future evaluations only.                               | Never rewrite order discount allocations.                                                          | Retroactive confusion  | —               |
|  6 | P1 | `POST /api/v1/admin/discounts/{discount_id}/codes`                | discounts.write     | Create coupon code(s).                                    | {codes[]\|generate:{prefix?,count<=100}}                       | DiscountCodeResult                                  | Normalize/unique per store; bounded generation.                                                                | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Code collision / abuse | —               |
|  7 | P1 | `POST /api/v1/admin/discounts/{discount_id}/rules`                | discounts.write     | Configure eligibility rules.                              | {rules:[{rule_type,operator,value}]}                           | DiscountRuleResponse[]                              | Validate supported rule types and values; no arbitrary executable expressions.                                 | Do not evaluate merchant-supplied code/scripts.                                                    | Rule injection         | —               |
|  8 | P1 | `PUT /api/v1/admin/discounts/{discount_id}/targets`               | discounts.write     | Set products/collections/customer targets.                | {targets:[{target_type,target_id}]}                            | DiscountTargetResponse[]                            | Validate ownership/existence and bounded count.                                                                | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Cross-store reference  | —               |
|  9 | P1 | `GET /api/v1/admin/discounts/{discount_id}/redemptions`           | discounts.read      | List redemption history.                                  | {first?,after?,customer_id?}                                   | Connection<DiscountRedemption></discountredemption> | Read immutable redemption ledger.                                                                              | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | PII leakage            | —               |

### Module invariants / business rules

- Discount preview/evaluation is side-effect free.
- Usage is consumed only when business rule says order is committed.
- All amounts are recalculated server-side at checkout.
- Historical order allocations never change when a promotion is edited.

### Generalized example

`WELCOME10` is valid only for first orders over ₹1,000. Cart preview shows ₹100 discount, but redemption is written only when the order is committed; concurrent attempts are protected by uniqueness/transaction rules.

## 8. Cart & Checkout Orchestration

Durable cart, authoritative repricing, checkout session, addresses, delivery options, stock reservation and final order creation.

**Database ownership/touchpoints:** `carts`, `cart_lines`, `checkout_sessions`, `checkout_lines`, `checkout_addresses`, `checkout_shipping_rates`, plus read/write coordination with catalog, pricing, discounts, inventory, orders, payments and idempotency
**API count:** 14

|  # | Pri | API                                                                    | Auth                    | Purpose                                  | Request                                             | Response                                      | Core business logic                                                                                                                                                                                                                                                                                                                                           | Must NOT do                                                                                               | Main risk                         | Events                 |
| -: | :-: | ---------------------------------------------------------------------- | ----------------------- | ---------------------------------------- | --------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | --------------------------------- | ---------------------- |
|  1 | P0 | `POST /api/v1/storefront/carts`                                      | Public                  | Create guest/customer cart.              | {currency?,market_context?,buyer_identity?}         | CartResponse                                  | Create durable DB cart + cache representation; bind secure opaque cart token.                                                                                                                                                                                                                                                                                 | Do not use sequential/publicly guessable IDs as sole authorization.                                       | Cart hijacking                    | —                     |
|  2 | P0 | `GET /api/v1/storefront/carts/{cart_token}`                          | Cart token/customer     | Fetch cart with current pricing summary. | None                                                | CartResponse                                  | Authorize by opaque token/customer; optionally reprice stale cart.                                                                                                                                                                                                                                                                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side.        | IDOR / stale totals               | —                     |
|  3 | P0 | `POST /api/v1/storefront/carts/{cart_token}/lines`                   | Cart token/customer     | Add variant.                             | {variant_id,quantity,properties?}                   | CartResponse                                  | Validate active/sellable variant and quantity bounds; price is looked up server-side.                                                                                                                                                                                                                                                                         | Never accept price, discount, stock availability or tax amount from client.                               | Price tampering                   | —                     |
|  4 | P0 | `PATCH /api/v1/storefront/carts/{cart_token}/lines/{line_id}`        | Cart token/customer     | Change line quantity/properties.         | {quantity,properties?}                              | CartResponse                                  | Validate ownership, quantity bounds; quantity 0 may map to delete by contract.                                                                                                                                                                                                                                                                                | Do not trust client-computed state/totals; validate ownership, status and permissions server-side.        | Negative/huge quantity            | —                     |
|  5 | P0 | `DELETE /api/v1/storefront/carts/{cart_token}/lines/{line_id}`       | Cart token/customer     | Remove line.                             | None                                                | CartResponse                                  | Ownership check then reprice.                                                                                                                                                                                                                                                                                                                                 | Do not trust client-computed state/totals; validate ownership, status and permissions server-side.        | IDOR                              | —                     |
|  6 | P0 | `PATCH /api/v1/storefront/carts/{cart_token}/buyer`                  | Cart token/customer     | Attach/update buyer identity.            | {email?,phone?,customer_token?}                     | CartResponse                                  | Verify customer token if linking; do not trust arbitrary customer_id.                                                                                                                                                                                                                                                                                         | Do not trust client-computed state/totals; validate ownership, status and permissions server-side.        | Account linking attack            | —                     |
|  7 | P0 | `POST /api/v1/storefront/checkouts`                                  | Cart token/customer     | Create checkout session from cart.       | {cart_token}                                        | CheckoutResponse                              | Freeze checkout line snapshot for session; compute totals; set expiry; no payment yet.                                                                                                                                                                                                                                                                        | Do not directly create order from unchecked client cart payload.                                          | Duplicate checkout / stale cart   | checkout.created       |
|  8 | P0 | `GET /api/v1/storefront/checkouts/{checkout_token}`                  | Checkout token/customer | Fetch checkout state/totals.             | None                                                | CheckoutResponse                              | Opaque token authorization; return state and expiry.                                                                                                                                                                                                                                                                                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side.        | Checkout hijacking                | —                     |
|  9 | P0 | `PUT /api/v1/storefront/checkouts/{checkout_token}/shipping-address` | Checkout token/customer | Set shipping address.                    | CheckoutAddressInput                                | CheckoutResponse                              | Validate country/postal; store session snapshot; invalidate shipping rate quote.                                                                                                                                                                                                                                                                              | Do not trust client-computed state/totals; validate ownership, status and permissions server-side.        | Invalid tax/shipping calc         | —                     |
| 10 | P1 | `PUT /api/v1/storefront/checkouts/{checkout_token}/billing-address`  | Checkout token/customer | Set/override billing address.            | CheckoutAddressInput\|{same_as_shipping:true}       | CheckoutResponse                              | Store immutable-for-session snapshot.                                                                                                                                                                                                                                                                                                                         | Do not trust client-computed state/totals; validate ownership, status and permissions server-side.        | Bad invoice data                  | —                     |
| 11 | P0 | `POST /api/v1/storefront/checkouts/{checkout_token}/shipping-rates`  | Checkout token/customer | Quote shipping.                          | None                                                | {rates[],expires_at}                          | Call shipping adapter with timeout/circuit-breaker or internal rate table; persist quote snapshot.                                                                                                                                                                                                                                                            | Do not hold DB transaction while calling carrier.                                                         | Provider timeout / price mismatch | —                     |
| 12 | P0 | `PUT /api/v1/storefront/checkouts/{checkout_token}/shipping-rate`    | Checkout token/customer | Select delivery option.                  | {rate_id}                                           | CheckoutResponse                              | Ensure rate belongs to same checkout and not expired; reprice total.                                                                                                                                                                                                                                                                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side.        | Forged shipping price             | —                     |
| 13 | P0 | `POST /api/v1/storefront/checkouts/{checkout_token}/payment-session` | Checkout token/customer | Create provider payment session/order.   | {payment_method,return_url?}                        | PaymentSessionResponse                        | Reprice, validate shipping, reserve inventory, create payment_intent, commit local work, then call provider outside DB txn; release/expire reservation idempotently if provider creation fails. | Never mark order paid from browser redirect/client callback; never expose a reserve-only public command. | Duplicate charge / stock hold     | payment.intent.created |
| 14 | P0 | `POST /api/v1/storefront/checkouts/{checkout_token}/complete`        | Checkout token/customer | Finalize checkout to order.              | Headers: Idempotency-Key; body:{payment_intent_id} | {order_id,order_number,status,payment_status} | `CompleteCheckoutUseCase` requires explicit payment intent; verified CAPTURED online evidence or COD PENDING intent; consumes reservations and writes immutable snapshots/outbox atomically. | External provider calls occur outside the transaction; missing payment context never becomes implicit COD. | Duplicate order / stock loss      | order.created          |

### Module invariants / business rules

- Cart is mutable shopping intent; checkout is a short-lived authoritative transaction session; order is the immutable commercial result.
- Every checkout-changing request carries/returns a version or ETag to prevent lost updates.
- Prices, discounts, tax, shipping and stock are revalidated at completion.
- Checkout completion requires an `Idempotency-Key` and DB uniqueness protection.
- Carrier/payment calls are never executed while holding core DB locks.

### Generalized example

Customer adds a ₹2,000 variant. At checkout the backend recalculates price, validates coupon, quotes ₹80 shipping, reserves one unit for 20 minutes, creates Razorpay order and only after verified payment rules does `/complete` produce immutable Order #ORD-1042.

## 9. Orders & Immutable Commercial Snapshot

Permanent order record, order lines, address/tax/discount snapshots and controlled lifecycle transitions.

**Database ownership/touchpoints:** `orders`, `order_items`, `order_addresses`, `order_discount_allocations`, `order_tax_lines`, `order_status_history`
**API count:** 12

|  # | Pri | API                                                      | Auth                               | Purpose                                               | Request                                                                                  | Response                                                | Core business logic                                                                                               | Must NOT do                                                                                        | Main risk                       | Events               |
| -: | :-: | -------------------------------------------------------- | ---------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------- | -------------------- |
|  1 | P0 | `GET /api/v1/storefront/customers/me/orders`           | Customer JWT                       | Customer order history.                               | {first?,after?}                                                                          | Connection<CustomerOrderSummary></customerordersummary> | Customer ID from JWT; cursor pagination.                                                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | IDOR                            | —                   |
|  2 | P0 | `GET /api/v1/storefront/orders/{order_number}`         | Customer JWT or signed order token | Customer/guest order detail using secure access rule. | {access_token?}                                                                          | CustomerOrderDetail                                     | Authenticated owner or signed guest order token.                                                                  | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Order data leakage              | —                   |
|  3 | P0 | `GET /api/v1/admin/orders`                             | orders.read                        | Admin order search/list.                              | {query?,status?,payment_status?,fulfillment_status?,channel_id?,from?,to?,first?,after?} | Connection<AdminOrderSummary></adminordersummary>       | Cursor pagination; indexed filters; permission-scoped PII.                                                        | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Slow query / PII exposure       | —                   |
|  4 | P0 | `GET /api/v1/admin/orders/{order_id}`                  | orders.read                        | Full admin order detail.                              | None                                                                                     | AdminOrderDetail                                        | Load immutable snapshots, payment/fillment summaries, bounded history.                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | N+1 / PII                       | —                   |
|  5 | P1 | `POST /api/v1/admin/orders/draft`                      | orders.write                       | Create manual/draft order.                            | {customer?,lines,shipping_address?,discount?,shipping?}                                  | DraftOrderResponse                                      | Server-price catalog lines or explicitly permitted custom line items; not paid/committed until completion.        | Custom prices require explicit privileged permission and audit.                                    | Fraud / price override          | —                   |
|  6 | P1 | `POST /api/v1/admin/orders/draft/{order_id}/complete`  | orders.write                       | Complete draft order.                                 | Headers:Idempotency-Key; body:{payment_mode}                                             | OrderResponse                                           | Same order-creation invariants as checkout; inventory and totals revalidated.                                     | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Duplicate/manual oversell       | —                   |
|  7 | P0 | `POST /api/v1/admin/orders/{order_id}/cancel`          | orders.cancel                      | Cancel eligible order.                                | {reason,restock_policy?,notify_customer?}                                                | OrderResponse                                           | State-machine check; release/restock unfulfilled inventory as appropriate; void/refund delegated to payment flow. | Do not mark cancelled by directly editing status column.                                           | Double restock/refund           | order.cancelled      |
|  8 | P1 | `POST /api/v1/admin/orders/{order_id}/hold`            | orders.manage                      | Place operational hold.                               | {reason}                                                                                 | OrderResponse                                           | Transition only from allowed states; block fulfillment.                                                           | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Fulfillment race                | —                   |
|  9 | P1 | `POST /api/v1/admin/orders/{order_id}/release-hold`    | orders.manage                      | Release hold.                                         | None                                                                                     | OrderResponse                                           | State validation; emit event.                                                                                     | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Race                            | —                   |
| 10 | P1 | `POST /api/v1/admin/orders/{order_id}/notes`           | orders.write                       | Append internal order note.                           | {note}                                                                                   | OrderNote/AuditResponse                                 | Audit log with actor/time; note may live in metadata/audit depending schema.                                      | Never return internal notes to storefront endpoints.                                               | Sensitive note leakage          | —                   |
| 11 | P0 | `GET /api/v1/admin/orders/{order_id}/history`          | orders.read                        | Fetch order status/audit timeline.                    | {first?,after?}                                                                          | Connection<OrderHistoryEvent></orderhistoryevent>       | Read immutable status history plus selected domain events.                                                        | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Audit leakage                   | —                   |
| 12 | P1 | `POST /api/v1/admin/orders/{order_id}/customer-notify` | orders.read                        | Resend order message.                                 | {template_key?}                                                                          | 202 NotificationJobResponse                             | Enqueue notification using immutable order snapshot.                                                              | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Spam / wrong recipient          | —                   |

### Module invariants / business rules

- Order financial/address/product snapshots are immutable after creation except explicitly modeled operational fields.
- All status changes go through one state-machine service and append history.
- Cancellation, refund and fulfillment are separate concerns; one status flip must not pretend to perform all three.
- Custom-price/manual order capabilities require stronger permissions and audit logs.

### Generalized example

A product price changes from ₹1,999 to ₹2,499 after purchase. Existing order detail still returns ₹1,999 because the order line is a snapshot; only new carts use ₹2,499.

## 10. Payments, Transactions & Refund Ledger

Gateway-independent intents, immutable transaction ledger, provider event inbox, COD handling and safe full/partial refunds.

**Database ownership/touchpoints:** `payment_intents`, `payment_transactions`, `payment_provider_events`, `refunds`, `refund_items`, plus `orders` and `outbox_events`
**API count:** 9

|  # | Pri | API                                                                   | Auth                 | Purpose                                  | Request                                                                                            | Response                             | Core business logic                                                                                                                                                                                    | Must NOT do                                                                                        | Main risk                   | Events                          |
| -: | :-: | --------------------------------------------------------------------- | -------------------- | ---------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | --------------------------- | ------------------------------- |
|  1 | P0 | `GET /api/v1/storefront/orders/{order_number}/payment-status`       | Customer/order token | Return sanitized payment state.          | {access_token?}                                                                                    | {payment_status,amount_due,currency} | Authorize order owner/guest token; no gateway secrets.                                                                                                                                                 | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Payment data leak           | —                              |
|  2 | P0 | `GET /api/v1/admin/orders/{order_id}/payments`                      | payments.read        | List payment intents/transactions.       | None                                                                                               | PaymentDetailResponse                | Permission-protected operational view.                                                                                                                                                                 | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Financial data exposure     | —                              |
|  3 | P0 | `POST /api/v1/webhooks/payments/razorpay`                           | Provider signature   | Razorpay webhook.                        | Raw provider payload + signature headers                                                           | 200 {received:true}                  | Verify signature on raw body; insert provider event with unique`(store_id, provider, external_event_id)`; ACK quickly; worker processes event idempotently.                                          | Never trust browser callback; never perform long processing before ACK.                            | Forged/replayed webhook     | payment.provider_event.received |
|  4 | P1 | `POST /api/v1/webhooks/payments/stripe`                             | Provider signature   | Stripe webhook.                          | Raw payload + Stripe-Signature                                                                     | 200 {received:true}                  | Same inbox/idempotent processing pattern.                                                                                                                                                              | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Forged/replayed webhook     | —                              |
|  5 | P1 | `POST /api/v1/admin/orders/{order_id}/capture`                      | payments.capture     | Capture authorized payment.              | {amount?}                                                                                          | PaymentTransactionResponse           | Validate capturable balance; provider call idempotency; append CAPTURE transaction after confirmed provider result.                                                                                    | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Double capture              | —                              |
|  6 | P1 | `POST /api/v1/admin/orders/{order_id}/void`                         | payments.manage      | Void authorization.                      | {reason?}                                                                                          | PaymentTransactionResponse           | Only authorized/unsettled payment; provider idempotency.                                                                                                                                               | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Wrong state                 | —                              |
|  7 | P0 | `POST /api/v1/admin/orders/{order_id}/refunds`                      | refunds.create       | Create refund request.                   | Headers:Idempotency-Key; body:{amount?,items?,reason,restock?}                                     | RefundResponse                       | Validate refundable balance/items; create local refund record; call provider asynchronously/safely; finalize on provider result.                                                                       | Never derive refundable amount solely from client request.                                         | Double refund / over-refund | refund.requested                |
|  8 | P0 | `GET /api/v1/admin/refunds/{refund_id}`                             | payments.read        | Fetch refund detail/status.              | None                                                                                               | RefundDetailResponse                 | Return transaction/item reconciliation.                                                                                                                                                                | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Financial data exposure     | —                              |
|  9 | P1 | `POST /api/v1/admin/orders/{order_id}/payment-reconcile`            | payments.manage      | Reconcile local vs provider state.       | {gateway?}                                                                                         | ReconciliationResponse               | Fetch provider state with timeout; never blindly overwrite; append reconciliation/audit event.                                                                                                         | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Provider/local drift        | —                              |

### Module invariants / business rules

- Provider webhook signature verification uses the raw request body.
- `external_event_id` is unique per `(store_id, provider)` to make webhook replay harmless without allowing cross-tenant collisions.
- Payment status is derived from immutable transaction history/state machine, not arbitrary admin edits.
- Refundable/capturable amounts are calculated server-side from ledger balances.
- No gateway network call occurs while holding the order/inventory transaction.
- Payment intent context is mandatory: CHECKOUT requires checkout_id, ORDER requires order_id, and ADMIN requires an explicit order or checkout context; store ownership is enforced transactionally and by composite relationships.
- One checkout has at most one nonterminal online Payment Intent per logical payment operation in `CREATED`, `PENDING_CUSTOMER_ACTION`, `PROCESSING`, `AUTHORIZED`, or `RECONCILIATION_REQUIRED`; a new provider target requires FAILED/CANCELLED or an explicit supersede command.
- Checkout expiry locks and re-reads payment state before releasing reservations. Protected payment states retain a reconciliation/completion path. A late CAPTURE after RELEASED/EXPIRED attempts atomic re-reservation; unavailable stock produces no oversell and requires reconciliation/refund handling.
- Completion reads only durable verified payment evidence; a racing capture webhook and completion request still yield one order, one reservation consumption and one financial effect.

### Generalized example

Razorpay sends the same `payment.captured` webhook three times. The first delivery is inserted and processed; later deliveries collide on unique provider event ID and return 200 without creating extra CAPTURE transactions.

## 11. Fulfillment, Shipping, NDR & COD

Allocate order lines into fulfillments, create one or more carrier shipments, track carrier events, delivery exceptions and COD settlements.

**Database ownership/touchpoints:** `fulfillments`, `fulfillment_items`, `shipments`, `shipment_events`, `ndr_events`, `cod_remittances`, plus locations/orders
**API count:** 14

|  # | Pri | API                                                            | Auth                  | Purpose                                       | Request                                                   | Response                                                  | Core business logic                                                                                                                        | Must NOT do                                                                                        | Main risk                            | Events                    |
| -: | :-: | -------------------------------------------------------------- | --------------------- | --------------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | ------------------------------------ | ------------------------- |
|  1 | P0 | `GET /api/v1/storefront/orders/{order_number}/tracking`      | Customer/order token  | Customer shipment tracking.                   | {access_token?}                                           | {fulfillments:[{status,shipments[]}]}                     | Authorize owner; expose safe tracking fields.                                                                                              | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | PII/provider leakage                 | —                        |
|  2 | P0 | `GET /api/v1/admin/fulfillments`                             | fulfillments.read     | List fulfillment work queue.                  | {status?,location_id?,first?,after?}                      | Connection<FulfillmentSummary></fulfillmentsummary>       | Indexed operational queue.                                                                                                                 | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Slow query                           | —                        |
|  3 | P0 | `POST /api/v1/admin/orders/{order_id}/fulfillments`          | fulfillments.write    | Create fulfillment allocation.                | {location_id,items:[{order_item_id,quantity}]}            | FulfillmentResponse                                       | Validate fulfillable remaining qty and location; lock order item fulfillment counters.                                                     | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Over-fulfillment                     | —                        |
|  4 | P1 | `PATCH /api/v1/admin/fulfillments/{fulfillment_id}`          | fulfillments.write    | Update packing metadata/status where allowed. | FulfillmentPatch                                          | FulfillmentResponse                                       | State-machine enforcement.                                                                                                                 | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Illegal fulfillment state            | —                        |
|  5 | P0 | `POST /api/v1/admin/fulfillments/{fulfillment_id}/shipments` | shipments.create      | Create carrier shipment.                      | {provider,service_code?,package,ship_from?,cod?}          | 202 ShipmentResponse                                      | Persist local shipment intent; call shipping adapter asynchronously/with timeout; save external ID/AWB.                                    | Never create carrier shipment twice on retry; use idempotency/local unique references.             | Duplicate shipment / provider outage | shipment.create.requested |
|  6 | P1 | `POST /api/v1/admin/shipments/{shipment_id}/cancel`          | shipments.manage      | Cancel eligible shipment.                     | {reason}                                                  | ShipmentResponse                                          | Provider cancellation + local transition only if provider confirms/known safe state.                                                       | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Local/provider drift                 | —                        |
|  7 | P1 | `POST /api/v1/admin/shipments/{shipment_id}/label`           | shipments.read        | Generate/retrieve shipping label.             | None                                                      | {download_url,expires_at}                                 | Fetch/store label asynchronously; return signed object URL.                                                                                | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Sensitive URL leakage                | —                        |
|  8 | P0 | `GET /api/v1/admin/shipments/{shipment_id}/tracking`         | shipments.read        | Admin detailed tracking.                      | None                                                      | ShipmentTrackingResponse                                  | Combine normalized shipment state and events.                                                                                              | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Provider payload leakage             | —                        |
|  9 | P0 | `POST /api/v1/webhooks/shipping/shiprocket`                  | Provider verification | Shiprocket carrier webhook.                   | Raw payload + provider auth/signature                     | 200 {received:true}                                       | Authenticate webhook; dedupe provider event; normalize asynchronously.                                                                     | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Forged carrier state                 | —                        |
| 10 | P1 | `POST /api/v1/webhooks/shipping/delhivery`                   | Provider verification | Delhivery carrier webhook.                    | Raw payload + auth                                        | 200 {received:true}                                       | Same normalized inbox/processing policy.                                                                                                   | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Forged carrier state                 | —                        |
| 11 | P1 | `GET /api/v1/admin/ndr`                                      | ndr.read              | List NDR cases.                               | {status?,provider?,first?,after?}                         | Connection<NdrResponse></ndrresponse>                     | Operational exception queue.                                                                                                               | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | PII                                  | —                        |
| 12 | P1 | `POST /api/v1/admin/ndr/{ndr_id}/actions`                    | ndr.manage            | Submit NDR action.                            | {action,new_phone?,new_address?,remarks?}                 | NdrResponse                                               | Validate allowed action and fields; call provider adapter; audit PII change.                                                               | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Wrong delivery change                | —                        |
| 13 | P1 | `GET /api/v1/admin/cod-remittances`                          | payments.read         | List COD settlement records.                  | {status?,from?,to?,provider?,first?,after?}               | Connection<CodRemittanceResponse></codremittanceresponse> | Financial reconciliation view.                                                                                                             | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Financial exposure                   | —                        |
| 14 | P1 | `POST /api/v1/admin/fulfillments/{fulfillment_id}/cancel`    | fulfillments.write    | Cancel unshipped fulfillment.                 | {reason}                                                  | FulfillmentResponse                                       | Restore fulfillable quantities only once; shipment-state guard.                                                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Double quantity restore              | —                        |

### Module invariants / business rules

- Order can have multiple fulfillments and shipments.
- Fulfilled quantity per order item can never exceed ordered quantity minus valid returns/cancellations.
- Carrier events are append-only and normalized through a state mapper.
- Out-of-order webhooks cannot blindly regress terminal states.
- Provider shipment creation/cancellation is idempotent.

### Generalized example

An order has two SKUs stocked in Noida and Mumbai. The engine creates two fulfillments and two AWBs; customer tracking still sees one order with both shipments.

## 12. Returns & Reverse Logistics

Return request, eligibility, approval, receipt/disposition and linkage to refund/restocking without conflating those processes.

**Database ownership/touchpoints:** `returns`, `return_items`, inventory ledger, refunds/payment tables
**API count:** 9

| # | Pri | API                                                       | Auth                     | Purpose                     | Request                                                                        | Response                                  | Core business logic                                                                       | Must NOT do                                                                                        | Main risk             | Events           |
| -: | :-: | --------------------------------------------------------- | ------------------------ | --------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------- | ---------------- |
| 1 | P1 | `POST /api/v1/storefront/orders/{order_number}/returns` | Customer JWT/order token | Customer return request.    | {items:[{order_item_id,qty,reason_code,comment?}]}                             | ReturnResponse                            | Verify order ownership, return window, delivered qty, prior returns and item eligibility. | Do not immediately refund or restock just because a request was submitted.                         | Return abuse          | return.requested |
| 2 | P1 | `GET /api/v1/storefront/returns/{return_id}`            | Customer JWT             | Customer return status.     | None                                                                           | CustomerReturnResponse                    | Ownership check; safe status only.                                                        | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | IDOR                  | —               |
| 3 | P1 | `GET /api/v1/admin/returns`                             | returns.read             | Return work queue.          | {status?,reason?,from?,to?,first?,after?}                                      | Connection<ReturnSummary></returnsummary> | Indexed queue.                                                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | PII                   | —               |
| 4 | P1 | `GET /api/v1/admin/returns/{return_id}`                 | returns.read             | Return detail.              | None                                                                           | AdminReturnDetail                         | Include line quantities, order/refund links and audit.                                    | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | PII                   | —               |
| 5 | P1 | `POST /api/v1/admin/returns/{return_id}/approve`        | returns.manage           | Approve requested items.    | {items?,return_method?,notes?}                                                 | ReturnResponse                            | Validate remaining returnable quantity and state.                                         | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Over-return           | —               |
| 6 | P1 | `POST /api/v1/admin/returns/{return_id}/reject`         | returns.manage           | Reject request.             | {reason}                                                                       | ReturnResponse                            | State transition + customer notification.                                                 | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Wrong rejection state | —               |
| 7 | P1 | `POST /api/v1/admin/returns/{return_id}/receive` | returns.manage | Record physical receipt/QC. | {items:[{return_item_id,received_quantity,condition?,disposition:RESTOCK\|DAMAGED\|DISCARD\|INSPECT}]} | ReturnResponse | Update return receipt and append inventory movement exactly once where disposition changes stock. | `REJECTED` is workflow state, never a receipt disposition. | Double restock | return.received |
| 8 | P1 | `POST /api/v1/admin/returns/{return_id}/refund`         | refunds.create           | Create linked refund.       | {items?,amount?,reason}                                                        | RefundResponse                            | Calculate refundable amount from order/return state; delegate Payment module.             | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Over-refund           | —               |
| 9 | P1 | `POST /api/v1/admin/returns/{return_id}/close`          | returns.manage           | Close completed return.     | None                                                                           | ReturnResponse                            | Only when operational/refund requirements resolved.                                       | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Premature closure     | —               |

### Module invariants / business rules

- Return, inventory disposition and refund are related but separate state machines.
- A quantity can be returned/restocked/refunded only up to the remaining eligible amount.
- Every restock/damage action writes inventory ledger movements.

### Generalized example

Customer returns 2 of 3 shirts. Warehouse receives one sellable and one damaged. Inventory gets +1 available and +1 damaged movement; refund can cover both approved items without falsely adding both back to sellable stock.

## 13. CMS, Navigation & SEO

Reusable client-controlled storefront content—pages, blog, navigation, SEO metadata and redirects—without coupling backend data to one frontend theme.

**Database ownership/touchpoints:** `pages`, `blog_categories`, `blog_posts`, `navigation_menus`, `navigation_items`, `seo_metadata`, `redirects`
**API count:** 23

|  # | Pri | API                                                 | Auth             | Purpose                      | Request                                                                | Response                                          | Core business logic                                                            | Must NOT do                                                                                        | Main risk                     | Events       |
| -: | :-: | --------------------------------------------------- | ---------------- | ---------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | ----------------------------- | ------------ |
|  1 | P1 | `GET /api/v1/storefront/pages/{handle}`           | Public           | Fetch published CMS page.    | None                                                                   | PagePublicResponse                                | Published-only; resolve SEO metadata.                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Draft leakage                 | —           |
|  2 | P1 | `GET /api/v1/storefront/blog`                     | Public           | List published posts.        | {first?,after?,category?}                                              | Connection<BlogPostCard></blogpostcard>           | Published_at/category filter, cursor pagination; tag filtering is deferred because no blog-tag model exists. | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Slow query                    | —           |
|  3 | P1 | `GET /api/v1/storefront/blog/{handle}`             | Public           | Fetch published blog post.   | None                                                                   | BlogPostPublicResponse                            | Published-only detail lookup by handle.                                           | Never expose draft posts or unpublished content.                                                   | Draft leakage                 | —           |
|  4 | P1 | `GET /api/v1/storefront/navigation/{key}`         | Public           | Fetch menu tree.             | None                                                                   | NavigationTree                                    | Return active items; bounded depth; cache heavily.                             | Do not allow unlimited menu depth.                                                                 | Recursive query abuse         | —           |
|  5 | P1 | `GET /api/v1/admin/pages`                         | content.read     | List pages.                  | {first?,after?,status?,query?}                                         | Connection<PageAdminResponse></pageadminresponse> | Cursor list.                                                                   | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | —                            | —           |
|  6 | P1 | `POST /api/v1/admin/pages`                        | content.write    | Create page.                 | {title,handle?,content,status?}                                        | PageAdminResponse                                 | Unique handle; frontend layout/theme remains code-driven; sanitize/store structured content according to editor contract. | Do not render unsanitized arbitrary HTML/scripts in storefront.                                    | Stored XSS                    | page.created |
|  7 | P1 | `PATCH /api/v1/admin/pages/{page_id}`             | content.write    | Update page.                 | PagePatch                                                              | PageAdminResponse                                 | Optimistic version recommended; invalidate CDN/cache.                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Lost update / XSS             | page.updated |
|  8 | P1 | `POST /api/v1/admin/pages/{page_id}/publish`      | content.publish  | Publish page.                | {published_at?}                                                        | PageAdminResponse                                 | Validate required title/handle and content status.                             | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Broken page publish           | —           |
|  9 | P1 | `GET /api/v1/admin/blog/categories`               | content.read     | List blog categories.        | None                                                                   | BlogCategory[]                                    | Store-scoped.                                                                  | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | —                            | —           |
| 10 | P1 | `POST /api/v1/admin/blog/categories`              | content.write    | Create category.             | {name,handle?}                                                         | BlogCategory                                      | Unique handle.                                                                 | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Duplicate URL                 | —           |
| 11 | P1 | `GET /api/v1/admin/blog/posts`                    | content.read     | List posts.                  | {first?,after?,status?,query?}                                         | Connection<BlogPostAdmin></blogpostadmin>         | Cursor list.                                                                   | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | —                            | —           |
| 12 | P1 | `POST /api/v1/admin/blog/posts`                   | content.write    | Create post.                 | {title,handle?,excerpt?,content,category_id?,author?,status?}          | BlogPostAdmin                                     | Sanitize content; unique handle; draft default.                                | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Stored XSS                    | —           |
| 13 | P1 | `PATCH /api/v1/admin/blog/posts/{post_id}`        | content.write    | Update post.                 | BlogPostPatch                                                          | BlogPostAdmin                                     | Optimistic update; cache invalidation.                                         | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Lost update                   | —           |
| 14 | P1 | `POST /api/v1/admin/blog/posts/{post_id}/publish` | content.publish  | Publish/schedule post.       | {published_at?}                                                        | BlogPostAdmin                                     | Validate schedule/timezone; worker can publish scheduled posts.                | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Wrong schedule                | —           |
| 15 | P1 | `GET /api/v1/admin/navigation`                    | navigation.read  | List menus.                  | None                                                                   | NavigationMenu[]                                  | Return menus and bounded item counts.                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | —                            | —           |
| 16 | P1 | `PUT /api/v1/admin/navigation/{menu_id}/tree`     | navigation.write | Replace validated menu tree. | {items:[{label,url\|resource_ref,parent_temp_id?,position}]}           | NavigationTree                                    | Validate URL/resource, depth, no cycles, bounded items; transactional replace. | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Cycle / bad links             | —           |
| 17 | P1 | `PUT /api/v1/admin/seo/{owner_type}/{owner_id}`   | seo.write        | Upsert SEO metadata.         | {title?,description?,canonical_url?,robots?,og_media_id?,schema_json?} | SeoMetadataResponse                               | Validate owner type, canonical host policy and structured-data schema.         | Do not allow arbitrary executable JSON-LD/script without sanitization.                             | SEO injection / bad canonical | —           |
| 18 | P1 | `GET /api/v1/admin/redirects`                     | seo.read         | List redirects.              | {first?,after?,query?}                                                 | Connection<RedirectResponse></redirectresponse>   | Cursor list.                                                                   | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | —                            | —           |
| 19 | P1 | `POST /api/v1/admin/redirects`                    | seo.write        | Create redirect.             | {from_path,to_url,status_code:301\|302}                                | RedirectResponse                                  | Normalize path; prevent redirect loops/open redirect policy violations.        | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Open redirect / loop          | —           |
| 20 | P1 | `DELETE /api/v1/admin/redirects/{redirect_id}`    | seo.write        | Delete redirect.             | None                                                                   | 204                                               | Invalidate redirect cache.                                                     | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Stale redirect                | —           |

| 21 | P1 | `GET /api/v1/admin/pages/{page_id}`               | content.read      | Fetch page detail for editor. | None                                                                  | PageAdminResponse                                | Return bounded editable content and metadata.                                        | Do not expose unpublished content to storefront callers.                                             | Content leakage               | —           |
| 22 | P1 | `GET /api/v1/admin/blog/posts/{post_id}`          | content.read      | Fetch post detail for editor.  | None                                                                  | BlogPostAdmin                                    | Return bounded editable content and metadata.                                        | Do not require list endpoints to carry full content blobs.                                            | Content leakage               | —           |
| 23 | P1 | `GET /api/v1/admin/navigation/{menu_id}/tree`     | navigation.read   | Fetch editable menu tree.      | None                                                                  | NavigationTree                                  | Return bounded validated tree for editor.                                            | Do not allow unlimited depth or cycles.                                                               | Recursive query abuse         | —           |

### Module invariants / business rules

- Frontend layout/theme remains code-driven; CMS stores content and structured configuration, not arbitrary executable templates.
- Published and draft content are strictly separated.
- Content capable of HTML/structured data is sanitized and schema-validated.
- Redirects cannot create loops or unrestricted open redirects.

### Generalized example

LinkUp launches a beauty-store frontend with a custom design. The same backend exposes About, blogs, navigation and SEO through neutral APIs, so the next electronics client can reuse the engine with a completely different UI.

## 14. Notifications & Customer Communication

Template-driven async email/SMS/WhatsApp-style transactional communication and delivery history. Request paths enqueue; workers send.

**Database ownership/touchpoints:** `notification_templates`, `notification_deliveries`, `outbox_events`
**API count:** 5

| # | Pri | API                                                                   | Auth                | Purpose                           | Request                                             | Response                                                | Core business logic                                                                                            | Must NOT do                                                                                        | Main risk             | Events |
| -: | :-: | --------------------------------------------------------------------- | ------------------- | --------------------------------- | --------------------------------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------- | ------ |
| 1 | P1 | `GET /api/v1/admin/notifications/templates`                         | notifications.read  | List notification templates.      | {channel?,event_type?}                              | NotificationTemplate[]                                  | Store-scoped templates.                                                                                        | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Sensitive content     | —     |
| 2 | P1 | `PUT /api/v1/admin/notifications/templates/{template_key}`          | notifications.write | Create/update template.           | {channel,subject?,body,variables_schema,status}     | NotificationTemplate                                    | Validate allowed variables and content length; version/audit edits.                                            | No arbitrary code execution in templates.                                                          | Template injection    | —     |
| 3 | P1 | `POST /api/v1/admin/notifications/templates/{template_key}/preview` | notifications.write | Render preview with sample data.  | {sample_data}                                       | {subject?,body}                                         | Sandboxed template renderer using variable allowlist.                                                          | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Template injection    | —     |
| 4 | P1 | `GET /api/v1/admin/notifications/deliveries`                        | notifications.read  | Delivery log.                     | {channel?,status?,order_id?,first?,after?}          | Connection<NotificationDelivery></notificationdelivery> | Redact message/recipient based on permission.                                                                  | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | PII exposure          | —     |
| 5 | P1 | `POST /api/v1/admin/notifications/deliveries/{delivery_id}/retry`   | notifications.write | Retry failed delivery.            | None                                                | 202 DeliveryResponse                                    | Only failed/retryable states; increment attempt count with backoff.                                            | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Spam loop             | —     |

### Module invariants / business rules

- Customer-facing requests never block on email/SMS provider.
- Retries use exponential backoff and a terminal failure state.
- Templates have an allowlisted variable schema and no arbitrary code execution.
- A dedupe key prevents repeated domain events from spamming customers.

### Generalized example

`order.created` is committed with the order via outbox. A worker later renders the order confirmation email and records delivery status; email provider downtime does not roll back the order.

## 15. Integrations, Apps & Webhooks

Payment/shipping/ERP/analytics connector configuration and outbound event subscriptions. This keeps vendor-specific credentials and delivery logic out of commerce tables.

**Database ownership/touchpoints:** `integrations`, `integration_secrets`, `webhook_subscriptions`, `webhook_deliveries`, `outbox_events`
**API count:** 11

|  # | Pri | API                                                            | Auth               | Purpose                                  | Request                                     | Response                                      | Core business logic                                                                              | Must NOT do                                                                                        | Main risk                  | Events                       |
| -: | :-: | -------------------------------------------------------------- | ------------------ | ---------------------------------------- | ------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | -------------------------- | ---------------------------- |
|  1 | P1 | `GET /api/v1/admin/integrations`                             | integrations.read  | List configured integrations and health. | {type?}                                     | IntegrationSummary[]                          | Return masked config/health only.                                                                | Never return decrypted secret values.                                                              | Secret leakage             | —                           |
|  2 | P1 | `POST /api/v1/admin/integrations`                            | integrations.write | Create integration configuration.        | {provider,type,public_config,secret_fields} | IntegrationSummary                            | Validate provider schema; store non-secret config in `integrations.config`; encrypt each write-only secret into `integration_secrets`. Do not run provider side effects unless `/test` is explicitly called. | Do not store raw long-lived secrets in generic JSON, logs or audit metadata.                       | Secret compromise / SSRF   | integration.created          |
|  3 | P1 | `PATCH /api/v1/admin/integrations/{integration_id}`          | integrations.write | Update integration.                      | IntegrationPatch                            | IntegrationSummary                            | Secret replacement uses write-only fields; persist ciphertext and safe health metadata without returning decrypted values. | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Secret leakage             | —                           |
|  4 | P1 | `POST /api/v1/admin/integrations/{integration_id}/test`      | integrations.write | Test connection.                         | None                                        | IntegrationHealthResponse                     | Canonical controlled, read-only provider adapter check with strict timeout; persist `health_status` and `last_checked_at`; safe result states are UNKNOWN, CONNECTED, AUTH_FAILED, UNREACHABLE, MISCONFIGURED, DEGRADED and NOT_SUPPORTED. | Never create charges/orders/shipments, send messages, call arbitrary URLs, or return raw provider payloads/secrets. | SSRF / provider outage     | —                           |
|  5 | P1 | `DELETE /api/v1/admin/integrations/{integration_id}`         | integrations.write | Disable/remove integration.              | None                                        | 204                                           | Soft-disable when historical refs exist; revoke secrets when possible.                           | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Breaking active orders     | —                           |
|  6 | P2 | `GET /api/v1/admin/webhooks`                                 | webhooks.read      | List outbound subscriptions.             | {status?,topic?}                            | WebhookSubscription[]                         | P2 app/integration webhooks.                                                                     | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Endpoint leak              | —                           |
|  7 | P2 | `POST /api/v1/admin/webhooks`                                | webhooks.write     | Create outbound subscription.            | {topic,url,api_version?,secret?}            | WebhookSubscription                           | HTTPS only; resolve/validate URL; block private IP ranges; generate signing secret; version pin. | Never allow localhost/private-network callback URLs by default.                                    | SSRF / data exfiltration   | webhook.subscription.created |
|  8 | P2 | `PATCH /api/v1/admin/webhooks/{subscription_id}`             | webhooks.write     | Update subscription.                     | {url?,status?,api_version?}                 | WebhookSubscription                           | Revalidate endpoint; version compatibility.                                                      | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | SSRF                       | —                           |
|  9 | P2 | `DELETE /api/v1/admin/webhooks/{subscription_id}`            | webhooks.write     | Delete/disable subscription.             | None                                        | 204                                           | Stop new deliveries; retain delivery history.                                                    | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Audit loss                 | —                           |
| 10 | P2 | `GET /api/v1/admin/webhooks/{subscription_id}/deliveries`    | webhooks.read      | List delivery history.                   | {first?,after?,status?}                     | Connection<WebhookDelivery></webhookdelivery> | Operational history with payload redaction policy.                                               | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Sensitive payload exposure | —                           |
| 11 | P2 | `POST /api/v1/admin/webhooks/deliveries/{delivery_id}/retry` | webhooks.write     | Retry failed delivery.                   | None                                        | 202 WebhookDelivery                           | Respect max retries and subscription status.                                                     | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Webhook storm              | —                           |

### Module invariants / business rules

- Secrets are write-only from admin API and masked on reads.
- Bootstrap/deployment secrets live in the client VPS environment, Docker/Kubernetes secrets, or an external secret manager; merchant integration secrets are encrypted into `integration_secrets` with `INTEGRATION_MASTER_KEY` held outside PostgreSQL.
- `integrations.config` contains non-secret public configuration only. Create/update requests split `public_config` from write-only `secret_fields`; GET responses expose safe configuration and health metadata only.
- Secret identifiers such as GA4 measurement IDs or Meta Pixel IDs are public configuration; tokens, passwords, private keys and signing secrets are never sent to the browser.
- Outbound webhook URLs are protected against SSRF and restricted to HTTPS/public networks by default.
- Webhook payload schema is versioned; subscriptions pin a version.
- Outbound delivery is at-least-once and carries a stable event ID for consumer deduplication.

### Generalized example

An ERP subscribes to `order.created`. The commerce transaction writes an outbox event; dispatcher signs a versioned payload, sends it to the ERP, and retries on 5xx without re-creating the order.

## 16. Reliability, Audit, Outbox, Idempotency & Bulk Jobs

Cross-cutting operational APIs for idempotency records, immutable audit trail, transactional outbox and asynchronous large imports/exports.

**Database ownership/touchpoints:** `idempotency_records`, `outbox_events`, `audit_logs`, `bulk_jobs`, `bulk_job_items`
**API count:** 6

|  # | Pri | API                                              | Auth            | Purpose                                        | Request                                                             | Response                                        | Core business logic                                                                                 | Must NOT do                                                                                        | Main risk                         | Events           |
| -: | :-: | ------------------------------------------------ | --------------- | ---------------------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------- | ---------------- |
|  1 | P0 | `GET /api/v1/admin/audit-logs`                 | audit.read      | Search immutable admin audit log.              | {actor_id?,entity_type?,entity_id?,action?,from?,to?,first?,after?} | Connection<AuditLogResponse></auditlogresponse> | Cursor pagination; append-only records; redact secret values.                                       | Audit log must never expose passwords/tokens/raw card data.                                        | Sensitive audit leakage           | —               |
|  2 | P1 | `GET /api/v1/admin/audit-logs/{log_id}`        | audit.read      | Audit event detail.                            | None                                                                | AuditLogDetail                                  | Permission + store scope.                                                                           | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Sensitive payload                 | —               |
|  3 | P1 | `POST /api/v1/admin/bulk-jobs`                 | bulk.manage     | Create import/export job.                      | {job_type,resource_type,file_id?\|filters?,options?}                | 202 BulkJobResponse                             | Validate job type/permissions/input object; enqueue; idempotency recommended.                       | Do not process CSV/JSON imports in HTTP request thread.                                            | Resource exhaustion               | bulk.job.created |
|  4 | P1 | `GET /api/v1/admin/bulk-jobs`                  | bulk.read       | List jobs.                                     | {status?,resource_type?,first?,after?}                              | Connection<BulkJobSummary></bulkjobsummary>     | Cursor list.                                                                                        | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | —                                | —               |
|  5 | P1 | `GET /api/v1/admin/bulk-jobs/{job_id}`         | bulk.read       | Job progress/result.                           | None                                                                | BulkJobDetail                                   | Return counts, status, safe result/error file URLs.                                                 | Do not trust client-computed state/totals; validate ownership, status and permissions server-side. | Data leakage                      | —               |
|  6 | P1 | `POST /api/v1/admin/bulk-jobs/{job_id}/cancel` | bulk.manage     | Cancel queued/processing job where supported.  | None                                                                | BulkJobResponse                                 | Cooperative cancellation flag; worker checks between batches.                                       | Never pretend cancellation rolled back already-committed batches.                                  | Partial-write confusion           | —               |

### Module invariants / business rules

- Idempotency is enforced by DB uniqueness, not only a pre-read.
- Same idempotency key + different request hash returns `409 IDEMPOTENCY_KEY_REUSED`.
- Outbox rows are written in the same transaction as the domain state change.
- Bulk jobs process bounded chunks and report partial item errors.
- Audit/outbox/ledger history is append-only except lifecycle housekeeping fields.

### Generalized example

A 50,000-product CSV upload returns `202` immediately. Worker validates/processes rows in chunks, stores row-level failures and provides a result file; one bad SKU does not hold a 20-minute HTTP request or giant DB transaction.

## Internal Application Commands / Worker Jobs — non-HTTP

LinkUp is a modular monolith. Same-application service calls and worker jobs are not versioned HTTP APIs and do not contribute to the API inventory. They retain the business rules, transaction ownership, idempotency and state-machine guarantees documented above:

- `InventoryService.reserve`, `InventoryService.release`, `InventoryService.consume`
- `DiscountService.evaluate`, `DiscountService.commit_redemptions`
- `CheckoutExpiryJob.run`
- `OrderStateMachine.transition`
- `PaymentService.create_intent`, `PaymentService.create_provider_session`
- `PaymentProviderEventProcessor.process`, `RefundProcessor.process`
- `ShipmentEventProcessor.process`, `CodRemittanceImporter.run`
- `NotificationService.enqueue`, `NotificationWorker.process`
- `OutboundWebhookDispatcher.run`
- `BulkJobWorker.process`, `OutboxDispatcher.run`

Operational readiness is exposed through deployment probes such as `/health/ready` and `/metrics`, outside the versioned commerce API. Idempotency records, outbox rows, reservations, payment intents, provider-event inboxes and delivery history remain durable database evidence.

## 10. Critical Cross-Module Business Flows

### 10.1 Product publish

1. Admin creates/updates product and variants.
2. Variant price is validated as Decimal; SKU and option combination uniqueness enforced.
3. Inventory item exists for each inventory-tracked variant.
4. Publish service checks minimum sellability requirements.
5. DB transaction updates publication state and writes `product.published` outbox event.
6. After commit, workers invalidate cache/search index and optionally send integration webhooks.

### 10.2 Cart → Checkout → Order

1. Cart mutation never trusts price from frontend.
2. `POST /checkouts` creates a short-lived checkout snapshot from current cart.
3. Addresses are validated; shipping rates are quoted and stored with expiry.
4. Checkout reprices catalog + contextual price + discount + tax + shipping.
5. Inventory reserve is atomic and has an expiry.
6. Payment intent/provider session is created outside the core order transaction.
7. `POST /complete` atomically claims idempotency key, revalidates checkout/payment state, creates immutable order snapshots, consumes the ACTIVE inventory reservation and writes outbox events.
8. Any duplicate request with the same key returns the same order; same key with different request hash returns 409.

### 10.3 Payment webhook

1. Read raw body and signature headers.
2. Verify provider signature before trusting payload.
3. Insert provider event inbox row using unique `(store_id, provider, external_event_id)`.
4. Return 200 quickly after durable acceptance.
5. Worker locks event, maps provider status to local state, appends transaction and updates payment/order state through state machine.
6. Write outbox events for notifications/fulfillment. Duplicate provider delivery becomes a no-op.

### 10.4 Order cancellation

1. Validate current order/payment/fulfillment states.
2. Order transition service records cancellation intent/history.
3. Unfulfilled inventory is released/restocked exactly once.
4. Payment void/refund is delegated to Payment module based on ledger state.
5. Fulfillment/shipment cancellation is delegated to Fulfillment module.
6. Customer communication is queued after commit.

### 10.5 Return → refund

1. Validate delivered/returnable remaining quantities and return window.
2. Create return request; no immediate stock/payment mutation.
3. Admin approves; warehouse receives item and records disposition.
4. RESTOCK disposition appends inventory movement; DAMAGED does not become available stock.
5. Refund service calculates remaining refundable amount and executes provider-safe refund.
6. Return closes only when required operational/refund steps are complete.

### 10.6 Bulk product import

1. Admin uploads file directly to object storage using signed URL.
2. Create bulk job with input file reference.
3. Worker validates rows in bounded chunks and records item-level errors.
4. Use short transactions per batch; unique constraints remain final authority.
5. Progress and result/error file are available from job API.
6. Outbox/search updates are batched; request thread never processes 50k rows.

## 11. Idempotency Matrix

| Operation                         |        Required?        | Scope/unique key                        | Cached/replayed result                                   |
| --------------------------------- | :----------------------: | --------------------------------------- | -------------------------------------------------------- |
| Checkout complete                 |           YES           | store + operation + Idempotency-Key     | Same OrderResponse                                       |
| Draft order complete              |           YES           | store + operation + key                 | Same order                                               |
| Refund create                     |           YES           | store + order + key                     | Same refund                                              |
| Provider payment session          |      YES internally      | payment_intent + provider + key         | Same provider reference                                  |
| Inventory reserve/release/consume |      YES internally      | checkout/order + reservation operation  | Same state transition result; terminal state is CONSUMED |
| Shipment create                   |      YES internally      | fulfillment + package/reference         | Same shipment/AWB                                        |
| Webhook event intake              | YES by external event id | store + provider + external_event_id    | 200 no-op on duplicate                                   |
| Bulk job create                   |       Recommended       | actor + file/filter hash + key          | Same job                                                 |
| Simple PATCH metadata             |        Usually no        | Use optimistic version/If-Match instead | 409 on version conflict                                  |

## 12. State Machines That Must Be Centralized

| Domain             | State model                                                                                                                                                    |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Checkout           | `OPEN → PRICED → INVENTORY_RESERVED → PAYMENT_PENDING → COMPLETED; side exits: EXPIRED, FAILED`                                                          |
| Order              | `DRAFT → PENDING → CONFIRMED → PROCESSING → COMPLETED; controlled side states: ON_HOLD, CANCELLED`                                                       |
| Payment intent     | `CREATED → PENDING_CUSTOMER_ACTION → PROCESSING → AUTHORIZED/CAPTURED/FAILED/CANCELLED/RECONCILIATION_REQUIRED`                                           |
| Refund             | `REQUESTED → PROCESSING → SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL/RECONCILIATION_REQUIRED`                                                                 |
| Fulfillment        | `OPEN → PACKING → READY → SHIPPED → COMPLETED; side: CANCELLED`                                                                                          |
| Shipment           | `CREATING → CREATED → PICKUP_SCHEDULED → PICKED_UP → IN_TRANSIT → OUT_FOR_DELIVERY → DELIVERED; exceptions: NDR/RTO/LOST/CANCELLED`                    |
| Return             | `REQUESTED → APPROVED/REJECTED → IN_TRANSIT → RECEIVED → REFUND_PENDING → COMPLETED; RECEIVED → COMPLETED when no refund is required; side: CANCELLED` |
| Bulk job           | `QUEUED → PROCESSING → COMPLETED/PARTIAL/FAILED/CANCELLED`                                                                                                 |
| Inventory transfer | `DRAFT → IN_TRANSIT → PARTIALLY_RECEIVED → RECEIVED`; side `CANCELLED` where valid.                                                                     |
| NDR case           | `OPEN → ACTION_SUBMITTED → RESOLVED`; shipment separately may become `RTO`.                                                                              |
| COD remittance     | `EXPECTED → REPORTED → RECONCILED → SETTLED`; mismatch `RECONCILIATION_REQUIRED`.                                                                       |

**Rule:** Controllers must not perform `model.status = request.status`. Every transition goes through the domain state-machine service.

## 13. Event Catalog

| Event                            | Producer     | Typical consumers                      |
| -------------------------------- | ------------ | -------------------------------------- |
| `product.created`              | Catalog      | Search index, integrations             |
| `product.updated`              | Catalog      | Cache/search/integrations              |
| `product.published`            | Catalog      | Storefront cache/search                |
| `inventory.adjusted`           | Inventory    | Analytics/ERP                          |
| `inventory.reserved`           | Inventory    | Checkout telemetry                     |
| `checkout.created`             | Checkout     | Analytics/abandonment                  |
| `order.created`                | Order        | Notification, fulfillment, ERP/webhook |
| `order.cancelled`              | Order        | Payment/inventory/notification         |
| `payment.intent.created`       | Payments     | Telemetry                              |
| `payment.captured`             | Payments     | Order confirmation/fulfillment         |
| `payment.failed`               | Payments     | Checkout/order notification            |
| `refund.requested`             | Payments     | Refund worker                          |
| `refund.succeeded`             | Payments     | Order/notification/accounting          |
| `shipment.create.requested`    | Fulfillment  | Shipping worker                        |
| `shipment.status.changed`      | Fulfillment  | Notification/order projection          |
| `return.requested`             | Returns      | Admin notification                     |
| `return.received`              | Returns      | Inventory/refund workflow              |
| `page.updated`                 | CMS          | CDN/cache invalidation                 |
| `webhook.subscription.created` | Integrations | Audit                                  |
| `bulk.job.created`             | Reliability  | Bulk worker                            |

Event envelope should include `event_id`, `event_type`, `event_version`, `store_id`, `aggregate_type`, `aggregate_id`, `occurred_at`, `request_id`, and typed `payload`.

## 14. What APIs Must Never Do

- **NEVER:** Accept `store_id` from public/admin request body as authorization scope.
- **NEVER:** Accept price, discount, tax, shipping charge, payment status or stock availability from the frontend as authoritative.
- **NEVER:** Call payment/shipping/email providers while holding long DB locks/transactions.
- **NEVER:** Mark an order paid from a browser redirect or unverified client callback.
- **NEVER:** Use FLOAT/DOUBLE for money.
- **NEVER:** Use read-then-write idempotency without a DB unique constraint.
- **NEVER:** Hard-delete products/variants/customers referenced by commercial history.
- **NEVER:** Mutate saved customer address and thereby alter historical order address.
- **NEVER:** Let generic admin PATCH endpoints edit domain state fields (`payment_status`, `order_status`, `stock_available`).
- **NEVER:** Allow arbitrary URLs for server-side fetch/webhooks without SSRF protection.
- **NEVER:** Run 10k–50k imports/exports synchronously.
- **NEVER:** Return raw provider payloads, secrets, password hashes, refresh tokens, stack traces or SQL errors.
- **NEVER:** Expose internal service endpoints to the public internet.
- **NEVER:** Use unbounded list endpoints or deep OFFSET pagination for growing operational data.
- **NEVER:** Assume external webhooks arrive once or in order.

## 15. Risk Register & Required Controls

| Risk                        | Domain                        | Required control                                                                       | Priority |
| --------------------------- | ----------------------------- | -------------------------------------------------------------------------------------- | :------: |
| Overselling                 | Checkout/Inventory            | Atomic conditional reservation; reservation TTL; idempotent release/commit; race tests |    P0    |
| Duplicate order             | Checkout                      | DB-backed Idempotency-Key claim + request hash                                         |    P0    |
| Duplicate charge/refund     | Payments                      | Provider/local idempotency + immutable transaction ledger                              |    P0    |
| Forged webhook              | Payments/Shipping             | Raw-body signature/auth verification                                                   |    P0    |
| Webhook replay/out-of-order | Payments/Shipping             | Unique external event ID + state machine + event timestamps                            |    P0    |
| IDOR/cross-store leak       | All                           | Store scope from token/deployment; ownership checks; 404 hiding                        |    P0    |
| Privilege escalation        | Admin/RBAC                    | Granular permissions, delegation rule, protected roles                                 |    P0    |
| Money precision             | All commerce                  | Decimal strings + NUMERIC                                                              |    P0    |
| Lost update                 | Catalog/CMS/settings          | Version column/ETag/If-Match for editor flows                                          |    P1    |
| Provider outage             | Payment/Shipping/Notify       | Timeouts, circuit breaker, async retry and local intents                               |    P0    |
| SSRF                        | Integrations/webhooks         | Allowlist protocols; public IP validation; DNS rebinding defense                       |    P0    |
| Stored XSS                  | CMS/product rich text         | Sanitization + structured editor contract + CSP                                        |    P0    |
| PII leakage                 | Customer/order/audit          | Permission gates, field whitelists, log redaction                                      |    P0    |
| Bulk resource exhaustion    | Imports/exports               | File size/row caps, async chunks, worker concurrency quotas                            |    P1    |
| Cache inconsistency         | Catalog/pricing/CMS           | Outbox-based invalidation + TTL + versioned cache keys                                 |    P1    |
| Audit tampering             | Admin/financial/inventory     | Append-only audit/ledgers; restricted DB role                                          |    P0    |
| Deadlocks                   | Inventory/order               | Deterministic lock ordering, short transactions, retry serialization errors            |    P0    |
| Fraud/abuse                 | Login/checkout/refund         | Rate limiting, fraud hooks, high-risk permission separation, audit                     |    P1    |

## 16. Testing Contract Before Production

| Domain                | Mandatory tests                                                                                              |
| --------------------- | ------------------------------------------------------------------------------------------------------------ |
| Auth                  | brute-force/rate limit, expired/rotated refresh token, permission denial, cross-store IDs                    |
| Catalog               | duplicate handle/SKU, variant option conflicts, publish incomplete product, concurrent edit version conflict |
| Inventory             | 10+ concurrent reservations against limited stock; release replay; commit replay; deadlock retry             |
| Checkout              | stale price, stale shipping quote, expired checkout, duplicate complete key, same key different body         |
| Payments              | invalid signature, duplicate webhook, webhook out of order, provider timeout, partial refund, over-refund    |
| Orders                | illegal state transition, cancel after partial fulfillment, immutable snapshot after catalog/address edit    |
| Shipping              | duplicate shipment create, late carrier event after delivered, split fulfillment, NDR flow                   |
| Returns               | over-return, double receive, double restock, refund greater than remaining eligible amount                   |
| CMS                   | stored XSS payload, redirect loop, malicious canonical/URL                                                   |
| Webhooks/Integrations | SSRF private IP, DNS rebinding defense, retry storm, versioned payload                                       |
| Bulk                  | 50k rows, malformed rows, cancellation, worker crash/resume, repeated job claim                              |

Add contract tests from OpenAPI, integration tests with PostgreSQL/Redis, provider sandbox tests, k6/Locust load tests, and chaos tests that kill workers between DB commit and side-effect processing.

## 17. Observability Requirements

- Every request: `request_id`, route, method, status, latency, store_id, actor_id/customer_id when safe.
- Never log passwords, tokens, card data, OTPs or full provider secrets.
- Metrics: P50/P95/P99 latency, 4xx/5xx, checkout success, reserve conflicts, payment failure, webhook backlog, outbox age, worker retries, notification failures.
- Distributed trace external provider calls separately from DB transaction spans.
- Alert on: payment webhook backlog, outbox oldest age, repeated inventory conflict spike, high 5xx, provider timeout surge, failed bulk-job rate.

## 18. Implementation Phases

| Phase                             | Modules                                                       | Gate                                                             |
| --------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------- |
| Phase A — Platform skeleton      | Store, Auth/RBAC, Customers, Catalog basics, media, locations | OpenAPI conventions, auth middleware, audit, request IDs         |
| Phase B — Commerce core          | Inventory, Cart, Checkout, Orders                             | Atomic reserve, idempotency, immutable snapshots, state machines |
| Phase C — Money & logistics      | Payments, Refunds, Fulfillment, Shipping                      | Provider adapters, webhook inbox, transaction ledger             |
| Phase D — Merchandising baseline | Discounts, Collections, CMS/SEO, Notifications                | Client-ready reusable store feature set                          |
| Phase E — Operations             | Bulk jobs, advanced audit/observability, reconciliation       | Scale and supportability                                         |
| Phase F — Advanced product       | Markets/catalog price lists, outbound app webhooks/metafields | Only when international/B2B/app use-cases justify it             |

## 19. Recommended FastAPI Code Boundaries

```text
app/
  api/
    v1/
      storefront/
      admin/
      auth/
      webhooks/
      ops/              # only concrete deployment probes, not commerce APIs
  domains/
    catalog/
    inventory/
    checkout/
    orders/
    payments/
    fulfillment/
    returns/
    cms/
  services/          # orchestration/use-cases
  repositories/      # DB access; no HTTP assumptions
  integrations/      # Razorpay, Stripe, Shiprocket, Delhivery, email etc.
  workers/
  core/              # config, security, request-id, rate limits, errors
```

**Dependency rule:** API controller → service/use-case → repository/domain. Repository must not call API controller; provider adapter must not directly mutate arbitrary DB models.

## 20. REST Now, GraphQL Later

For LinkUp Web's current model—custom storefronts built by the same team—REST-first is simpler to implement, cache, secure and debug. Keep domain services transport-neutral. If LinkUp later offers a headless public developer platform, GraphQL can be added as another adapter over the same services.

Shopify currently uses versioned GraphQL for its Admin and Storefront APIs, cursor/connection-style access for large datasets, async bulk operations for large jobs, and versioned webhook payloads. Those are useful design references, but LinkUp does not need to copy Shopify's API surface to benefit from the same reliability principles.

## 21. Source / Design References (Conceptual)

- [Shopify GraphQL Admin API](https://shopify.dev/docs/api/admin-graphql/latest)
- [Shopify Storefront API](https://shopify.dev/docs/api/storefront/latest)
- [Shopify API versioning](https://shopify.dev/docs/api/usage/versioning)
- [Shopify API limits](https://shopify.dev/docs/api/usage/limits)
- [Shopify bulk operations](https://shopify.dev/docs/api/usage/bulk-operations/queries)
- [Shopify webhook subscriptions/versioning](https://shopify.dev/docs/apps/build/webhooks/subscribe)

> References are conceptual validation only. This LinkUp API architecture is independently designed around LinkUp Web's reusable one-client-per-deployment commerce-engine model.

## 22. Final API Count

- **Total specified HTTP APIs: 198**
- **P0: 71 APIs**
- **P1: 109 APIs**
- **P2: 18 APIs**

The endpoint count is an architecture inventory, not a requirement to launch every P1/P2 endpoint in the first client release. P0 commerce invariants are the part that should be treated as non-negotiable.

## 23. Critical API Request / Response Examples

These examples are intentionally detailed for the APIs where implementation mistakes are most expensive. All identifiers are illustrative.

### 23.1 Create product

**Request**

```http
POST /api/v1/admin/products
Authorization: Bearer <staff_jwt>
Content-Type: application/json
```

```json
{
  "title": "Classic Shirt",
  "description": "Premium cotton shirt",
  "vendor": "ACME",
  "status": "DRAFT",
  "handle": "classic-shirt",
  "tags": ["shirts", "cotton"]
}
```

**Response — 201**

```json
{
  "data": {
    "product_id": "019...",
    "title": "Classic Shirt",
    "handle": "classic-shirt",
    "status": "DRAFT",
    "created_at": "2026-09-08T06:00:00Z"
  },
  "meta": {"request_id": "req_123"}
}
```

**Important:** creating a product does not automatically make it sellable. Publication is a separate controlled action.

---

### 23.2 Add cart line

**Request**

```http
POST /api/v1/storefront/carts/cart_xxx/lines
Content-Type: application/json
```

```json
{
  "variant_id": "019...",
  "quantity": 2
}
```

**Response — 200**

```json
{
  "data": {
    "cart_token": "cart_xxx",
    "lines": [
      {
        "line_id": "019...",
        "variant_id": "019...",
        "quantity": 2,
        "unit_price": "1999.00",
        "line_subtotal": "3998.00",
        "currency": "INR"
      }
    ],
    "subtotal": "3998.00",
    "discount_total": "0.00",
    "grand_total": "3998.00",
    "version": 3
  },
  "meta": {"request_id": "req_124"}
}
```

**Important:** request contains no price. The backend resolves the current price.

---

### 23.3 Atomic inventory reserve (internal command)

**Internal request**

```http
InventoryService.reserve(checkout_id, lines, expires_at)
```

```json
{
  "checkout_id": "019...",
  "expires_at": "2026-09-08T06:30:00Z",
  "lines": [
    {
      "inventory_item_id": "019...",
      "location_id": "019...",
      "qty": 2
    }
  ]
}
```

**Success — 200**

```json
{
  "data": {
    "status": "RESERVED",
    "reservations": [
      {
        "reservation_id": "019...",
        "inventory_item_id": "019...",
        "quantity": 2,
        "expires_at": "2026-09-08T06:30:00Z"
      }
    ]
  },
  "meta": {"request_id": "req_125"}
}
```

**Conflict — 409**

```json
{
  "error": {
    "code": "OUT_OF_STOCK",
    "message": "Requested quantity is no longer available",
    "details": [
      {
        "inventory_item_id": "019...",
        "requested": 2,
        "available": 1
      }
    ]
  },
  "meta": {"request_id": "req_125"}
}
```

**Important:** availability check and reservation must not be two independent non-atomic writes.

---

### 23.4 Complete checkout

**Request**

```http
POST /api/v1/storefront/checkouts/chk_xxx/complete
Idempotency-Key: checkout-9fd4ef...
Content-Type: application/json
```

```json
{
  "payment_intent_id": "019..."
}
```

**Success — 201/200**

```json
{
  "data": {
    "order_id": "019...",
    "order_number": 1042,
    "order_name": "ORD-1042",
    "order_status": "CONFIRMED",
    "payment_status": "PAID",
    "currency": "INR",
    "grand_total": "4078.00"
  },
  "meta": {
    "request_id": "req_126",
    "idempotent_replay": false
  }
}
```

If the same request is retried with the same `Idempotency-Key`, return the same order:

```json
{
  "data": {
    "order_id": "019...",
    "order_number": 1042,
    "order_name": "ORD-1042",
    "order_status": "CONFIRMED",
    "payment_status": "PAID",
    "currency": "INR",
    "grand_total": "4078.00"
  },
  "meta": {
    "request_id": "req_127",
    "idempotent_replay": true
  }
}
```

If the same key is reused with a materially different request:

```json
{
  "error": {
    "code": "IDEMPOTENCY_KEY_REUSED",
    "message": "This idempotency key was already used for a different request"
  },
  "meta": {"request_id": "req_128"}
}
```

**Important transaction boundary**

```text
SHORT DB TX:
claim idempotency key
→ validate checkout snapshot
→ verify authoritative payment state
→ create order + order snapshots
→ consume ACTIVE inventory reservation
→ write status history
→ write outbox events
COMMIT

AFTER COMMIT:
notifications / ERP webhook / search / other side effects
```

---

### 23.5 Razorpay webhook intake

**Request**

```http
POST /api/v1/webhooks/payments/razorpay
X-Razorpay-Signature: <signature>
```

Body is the raw provider JSON.

**Processing contract**

1. Read raw body.
2. Verify signature before trusting parsed fields.
3. Extract stable external event identifier/provider reference.
4. Insert `payment_provider_events` using unique `(store_id, provider, external_event_id)` provider-event constraint.
5. Return `200` after durable acceptance.
6. Process event asynchronously/idempotently.
7. Append payment transaction only if the state machine allows it.

**Response**

```json
{
  "received": true
}
```

A duplicate valid webhook must still safely return success and must not append a second CAPTURE transaction.

---

### 23.6 Create refund

**Request**

```http
POST /api/v1/admin/orders/019.../refunds
Authorization: Bearer <staff_jwt>
Idempotency-Key: refund-44a5...
```

```json
{
  "items": [
    {
      "order_item_id": "019...",
      "quantity": 1
    }
  ],
  "reason": "CUSTOMER_RETURN",
  "restock": false
}
```

**Response — 202/201**

```json
{
  "data": {
    "refund_id": "019...",
    "status": "REQUESTED",
    "amount": "1999.00",
    "currency": "INR"
  },
  "meta": {"request_id": "req_130"}
}
```

The backend calculates `1999.00`; the client is not allowed to decide the authoritative refundable amount.

---

### 23.7 Create shipment

**Request**

```http
POST /api/v1/admin/fulfillments/019.../shipments
Authorization: Bearer <staff_jwt>
Idempotency-Key: ship-fulfillment-019...
```

```json
{
  "provider": "SHIPROCKET",
  "service_code": "STANDARD",
  "package": {
    "weight": "0.850",
    "weight_unit": "kg",
    "length": "30.0",
    "width": "20.0",
    "height": "10.0",
    "dimension_unit": "cm"
  },
  "cod": false
}
```

**Response — 202**

```json
{
  "data": {
    "shipment_id": "019...",
    "status": "CREATING",
    "provider": "SHIPROCKET"
  },
  "meta": {"request_id": "req_131"}
}
```

Carrier AWB creation can finish asynchronously. A retry must reuse the same local shipment/provider idempotency reference rather than creating another AWB.

---

### 23.8 Bulk product import

**Request**

```http
POST /api/v1/admin/bulk-jobs
Authorization: Bearer <staff_jwt>
Idempotency-Key: product-import-file-abc
```

```json
{
  "job_type": "IMPORT",
  "resource_type": "PRODUCT",
  "file_id": "media_or_upload_reference",
  "options": {
    "update_existing_by": "SKU",
    "dry_run": false
  }
}
```

**Response — 202**

```json
{
  "data": {
    "job_id": "019...",
    "status": "QUEUED",
    "processed_count": 0,
    "success_count": 0,
    "error_count": 0
  },
  "meta": {"request_id": "req_132"}
}
```

The worker processes rows in bounded chunks and records item-level failures. The HTTP request never loops through tens of thousands of rows.

---

## 24. Final Technical Lead Sign-off Criteria Before SDR Freeze

## 25. Documentation Remediation Freeze Addendum

Request/correlation IDs are opaque strings, recommended maximum 64 characters,
and are stored consistently in audit, outbox, idempotency, and webhook-delivery
records. `If-Match` or an expected `version` is required for versioned cart,
checkout, and mutable admin resources; stateful financial and inventory commands
use their explicit transition contracts.

The canonical payment intent states are `CREATED`, `PENDING_CUSTOMER_ACTION`,
`PROCESSING`, `AUTHORIZED`, `CAPTURED`, `FAILED`, `CANCELLED`, and
`RECONCILIATION_REQUIRED`. Refund states are `REQUESTED`, `PROCESSING`,
`SUCCEEDED`, `FAILED_RETRYABLE`, `FAILED_FINAL`, and
`RECONCILIATION_REQUIRED`. Replace the earlier illustrative state labels with
these values in endpoint DTOs and examples.

Payment provider events are resolved to a store through the configured provider
integration, never from an untrusted payload store ID. The persisted event keeps
`store_id`, provider/event identity, optional resolved payment/order references,
signature result, processing status, payload, and timestamps; uniqueness is
`(store_id, provider, external_event_id)`.

Architecture and domain contracts may freeze before runtime DTO implementation. Before a specific endpoint is implemented or accepted, its concrete Pydantic/OpenAPI contract must be complete. All Release 1 P0 endpoint contracts must be complete before Release 1 production sign-off:

- API + DB field names use one consistent vocabulary (`variant`, `order_item`, `fulfillment`, `shipment`, etc.).
- The endpoint being implemented has a complete OpenAPI request/response DTO.
- Every admin route has a named permission code.
- Every state-changing P0 operation declares transaction boundaries.
- Every external provider call declares timeout, retry and idempotency behavior.
- Every webhook declares signature/authentication, event dedupe and replay behavior.
- Checkout, inventory, payments, refunds and shipments have documented state machines.
- Order/payment/inventory history tables are append-only where required.
- Error codes are centralized and stable.
- Rate limits are classified by API surface.
- Cursor pagination is used for growing operational collections.
- Contract/integration/race-condition tests exist before production launch.
- P1/P2 endpoints that are not implemented return no misleading placeholder behavior; they remain outside the exposed OpenAPI until actually supported.

Release 1 version/ETag coverage is explicit for `store_settings`, `products`,
`product_variants`, `pages`, and `blog_posts`, plus mandatory cart and checkout
versions. Generic version PATCH is not used for orders, payments, refunds,
inventory, or fulfillments.

Provider-event processing states are `RECEIVED → PROCESSING → PROCESSED`, with
`PROCESSING → FAILED_RETRYABLE → PROCESSING`, `FAILED_TERMINAL`, or optional
verified `IGNORED`. These are inbox states, not payment-intent states.

**Recommended freeze order:** DB schema → domain state machines → API contracts → event catalog → provider adapters → final SDR → implementation tickets.
