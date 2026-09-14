# LinkUp Commerce Engine — Database Schema Architecture

**Document type:** Production DB Architecture / SDR Input  
**Target stack:** FastAPI + PostgreSQL + Redis + Alembic + async workers  
**Deployment model:** One client e-commerce deployment per isolated VPS/database initially; schema intentionally keeps a `stores` root so the same engine can later support multi-store/SaaS without a rewrite. The reusable backend is paired with a client-specific VPS/database and custom frontend; this is not a hosted Shopify clone.
**Design goal:** Shopify-inspired commerce capabilities, but optimized for LinkUp Web's reusable custom-store delivery model rather than copying Shopify internals.

> This file is the proposed target database architecture after auditing the earlier LinkUp Ecommerce ERD. It is a design specification, not an instruction to implement every P2 table on day one.

---

## 1. Architecture Decisions That Are Locked Before Coding

| Decision | Standard | Why |
|---|---|---|
| Store boundary | Keep `store_id` root even for one-store VPS deployments | Cheap future-proofing; cleaner ownership and possible SaaS migration |
| Primary keys | UUID generated in application (prefer time-sortable UUID v7 where library support is stable) | No central sequence dependency; safe distributed writes |
| Money | `NUMERIC(19,4)` + `CHAR(3)` currency | Never use FLOAT/DOUBLE for money |
| Time | `TIMESTAMPTZ` in UTC | Correct cross-timezone behavior |
| Status fields | `VARCHAR` + application enum/DB CHECK for stable states | Easier controlled evolution than heavy DB enum coupling |
| Flexible data | JSONB only for metadata/provider payload/rules/custom properties | Core searchable relationships remain normalized |
| Cart | PostgreSQL durable source + Redis cache | Enables recovery, analytics, cross-device behavior |
| Order history | Immutable commercial snapshots | Historical product/address/price stays correct |
| Inventory | Current level + reservations + append-only movements | Prevents oversell and supports audit/reconciliation |
| Payments | Intent + transaction ledger + provider event inbox | Supports retries/refunds/webhook replay safely |
| Shipping | Fulfillment sits between order and shipment | Supports split shipments/multiple warehouses |
| Async side effects | Transactional outbox | No lost notifications/webhooks after DB commit |
| High-volume operations | Async bulk jobs | Prevents long blocking requests |
| Bootstrap secrets | VPS environment, Docker/Kubernetes secrets, or an external secret manager | Never store deployment credentials in the database or Git |
| Merchant integration secrets | Encrypted ciphertext in `integration_secrets`; master key outside DB | Plaintext is transient only and never returned, logged, audited, or placed in generic JSON |

### Priority legend

- **P0 — Core:** required for a strong production commerce engine.
- **P1 — Standard:** implement for the reusable LinkUp Web product baseline or early client needs.
- **P2 — Advanced:** schema boundary should be preserved; implement only when international/B2B/apps/advanced feature demand appears.

---

## 2. Module Summary

| # | Module | Tables | Purpose |
|---:|---|---:|---|
| 1 | Store Foundation & Sales Channels | 3 | Defines the commerce store, store-wide defaults and where products/orders originate. DNS, host mapping, reverse proxy and TLS are deployment infrastructure. |
| 2 | Identity, Staff & RBAC | 7 | Separates login identity from staff authorization. Customer accounts are intentionally separate from admin/staff accounts. |
| 3 | Customers, Addresses & Consent | 4 | Customer CRM identity used for storefront orders, marketing consent, saved addresses and customer history. |
| 4 | Product Catalog, Variants, Collections & Metafields | 13 | Core merchandising model for simple products, configurable variants, media, grouping and custom merchant fields. |
| 5 | Locations, Inventory & Stock Ledger | 7 | Tracks physical stock by variant and location, prevents overselling, supports reservations and creates an auditable stock movement ledger. |
| 6 | Markets, Catalogs & Price Lists | 5 | Provides default pricing now and enables B2B/international/channel-specific pricing later without rewriting variants. |
| 7 | Discounts, Coupons & Promotions | 5 | Rule-based promotion engine supporting codes, automatic discounts, limits and redemption history. |
| 8 | Cart & Checkout Orchestration | 6 | Keeps shopping intent durable, calculates authoritative totals, reserves inventory and creates an order safely. |
| 9 | Orders & Immutable Commercial Snapshot | 6 | Permanent commercial record created from checkout. Stores historical prices, addresses, taxes, discounts and state changes independently of future catalog edits. |
| 10 | Payments, Transactions & Refund Ledger | 5 | Gateway-independent payment model supporting online/COD, retries, authorization/capture, provider webhooks, partial refunds and reconciliation. |
| 11 | Fulfillment, Shipping, NDR & COD | 6 | Separates what must be fulfilled from individual carrier shipments so split shipments/multiple warehouses remain possible. |
| 12 | Returns & Reverse Logistics | 2 | Controls return request, item approval, receipt, restocking and downstream refund. |
| 13 | CMS, Navigation & SEO | 7 | Provides client-editable storefront content without coupling frontend layout to database structure. |
| 14 | Notifications & Customer Communication | 2 | Template-driven asynchronous transactional messages with delivery logs. |
| 15 | Integrations, Apps & Webhooks | 4 | Keeps payment/shipping/analytics/ERP configuration, encrypted merchant secrets and outbound subscriptions isolated from commerce tables. |
| 16 | Reliability, Audit, Outbox, Idempotency & Bulk Jobs | 5 | Cross-cutting infrastructure that prevents duplicate side effects and makes the backend operable at production scale. |

**Total proposed tables in this architecture: 87**
**Reconciled priority split:** 44 P0 Core; 34 P1 Standard; 9 P2 Advanced.
> The total includes P2 future-ready tables. Do not confuse schema completeness with MVP implementation scope.

---

## 1. Store Foundation & Sales Channels

Defines the commerce store, store-wide defaults and where products/orders originate. DNS, host mapping, reverse proxy and TLS are deployment infrastructure; keeping a store root makes the engine reusable and future multi-store capable.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `stores` | P0 | 10 | Root commerce store record. Usually one active row per client deployment. |
| `store_settings` | P0 | 12 | Structured operational settings for the deployment. |
| `sales_channels` | P1 | 8 | Defines storefront/admin/manual/marketplace channels. |

### 1.1 `stores` — P0

Root commerce store record. Usually one active row per client deployment.

**Attribute count: 10**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `store_id` | `UUID` | PK | Primary store identifier. |
| `name` | `VARCHAR(160)` | NOT NULL | Merchant/store display name. |
| `legal_name` | `VARCHAR(200)` | NULL | Registered business name. |
| `default_currency` | `CHAR(3)` | NOT NULL | ISO currency such as INR. |
| `country_code` | `CHAR(2)` | NOT NULL | Primary ISO country code. |
| `timezone` | `VARCHAR(64)` | NOT NULL | Store operating timezone. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE, PAUSED, CLOSED. |
| `version` | `BIGINT` | NOT NULL DEFAULT 1 | Optimistic concurrency version for admin edits. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Creation time UTC. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Last update UTC. |

**Key constraints**
- CHECK default_currency uses ISO-4217 code at application boundary

**Recommended indexes**
- `status`
- `created_at`

### 1.2 `store_settings` — P0

Structured operational settings for the deployment.

**Attribute count: 12**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `settings_id` | `UUID` | PK | Settings row id. |
| `store_id` | `UUID` | FK stores.store_id UNIQUE | One settings row per store. |
| `order_prefix` | `VARCHAR(20)` | NOT NULL DEFAULT ORD | Human order number prefix. |
| `weight_unit` | `VARCHAR(8)` | NOT NULL | kg, g, lb. |
| `dimension_unit` | `VARCHAR(8)` | NOT NULL | cm, in. |
| `tax_inclusive` | `BOOLEAN` | NOT NULL DEFAULT false | Whether catalog price already contains tax. |
| `allow_guest_checkout` | `BOOLEAN` | NOT NULL DEFAULT true | Guest checkout switch. |
| `inventory_policy` | `VARCHAR(24)` | NOT NULL DEFAULT DENY | Release 1 supports DENY only; CONTINUE is deferred until a complete backorder policy exists. |
| `checkout_expiry_minutes` | `INT` | NOT NULL DEFAULT 30 | Reservation/checkout lifetime. |
| `version` | `BIGINT` | NOT NULL DEFAULT 1 | Optimistic concurrency version for settings edits. |
| `config` | `JSONB` | NOT NULL DEFAULT {} | Low-risk extensible flags. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Last change. |

### 1.3 `sales_channels` — P1

Defines storefront/admin/manual/marketplace channels.

**Attribute count: 8**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `channel_id` | `UUID` | PK | Channel id. |
| `store_id` | `UUID` | FK stores.store_id | Owning store. |
| `name` | `VARCHAR(100)` | NOT NULL | Online Store, Admin Draft, Instagram, etc. |
| `channel_type` | `VARCHAR(32)` | NOT NULL | STOREFRONT, ADMIN, MARKETPLACE, POS, API. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE/INACTIVE. |
| `config` | `JSONB` | NOT NULL DEFAULT {} | Channel-specific configuration. |
| `version` | `BIGINT` | NOT NULL DEFAULT 1 | Optimistic concurrency version for admin edits. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(store_id,name)

**Recommended indexes**
- `store_id`
- `channel_type`
- `status`

### Relationships

stores 1─1 store_settings; stores 1─N sales_channels.

### Generalized example

Example: LinkUp deploys ACME Fashion on an isolated VPS/database with a custom frontend. DNS, host mapping, reverse proxy and TLS are configured outside the commerce schema; `stores` has one ACME row, default currency is INR, and the primary sales channel is `Online Store`.

### Technical notes

- Do not remove store_id just because the first deployment has one store. It is a cheap future-proofing boundary.
- Custom-domain ownership, DNS, reverse proxy, certificate issuance and renewal belong to deployment infrastructure, not commerce tables or APIs.

---

## 2. Identity, Staff & RBAC

Separates login identity from staff authorization. Customer accounts are intentionally separate from admin/staff accounts.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `users` | P0 | 9 | Login identities for merchant/staff/admin users. |
| `roles` | P0 | 6 | Named staff roles. |
| `permissions` | P0 | 5 | Global permission catalog used by roles. |
| `role_permissions` | P0 | 3 | Many-to-many role → permission mapping. |
| `staff_members` | P0 | 7 | Assigns a user identity to a store. |
| `staff_member_roles` | P0 | 3 | Many-to-many staff → role mapping. |
| `refresh_tokens` | P0 | 12 | Server-side revocable staff refresh-token/session registry. |

### 2.1 `users` — P0

Login identities for merchant/staff/admin users.

**Attribute count: 9**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `user_id` | `UUID` | PK | Identity id. |
| `email` | `CITEXT` | NOT NULL | Login email. |
| `phone` | `VARCHAR(32)` | NULL | Optional login/contact phone. |
| `password_hash` | `VARCHAR(255)` | NOT NULL | Argon2id/bcrypt hash. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE, LOCKED, INVITED. |
| `email_verified_at` | `TIMESTAMPTZ` | NULL | Verification timestamp. |
| `last_login_at` | `TIMESTAMPTZ` | NULL | Last successful login. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(email)

**Recommended indexes**
- `status`
- `created_at`

### 2.2 `roles` — P0

Named staff roles.

**Attribute count: 6**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `role_id` | `UUID` | PK | Role id. |
| `store_id` | `UUID` | FK stores.store_id | Store scope. |
| `name` | `VARCHAR(80)` | NOT NULL | Owner, Catalog Manager, Support. |
| `is_system` | `BOOLEAN` | NOT NULL DEFAULT false | Protected built-in role flag. |
| `description` | `TEXT` | NULL | Human purpose. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(store_id,name)

### 2.3 `permissions` — P0

Global permission catalog used by roles.

**Attribute count: 5**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `permission_id` | `UUID` | PK | Permission id. |
| `code` | `VARCHAR(100)` | NOT NULL | e.g. products.write. |
| `module` | `VARCHAR(50)` | NOT NULL | Catalog, Orders, Settings. |
| `description` | `TEXT` | NULL | Meaning. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(code)

### 2.4 `role_permissions` — P0

Many-to-many role → permission mapping.

**Attribute count: 3**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `role_id` | `UUID` | PK, FK roles.role_id | Role. |
| `permission_id` | `UUID` | PK, FK permissions.permission_id | Permission. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Granted time. |

### 2.5 `staff_members` — P0

Assigns a user identity to a store.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `staff_member_id` | `UUID` | PK | Membership id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `user_id` | `UUID` | FK users.user_id | User. |
| `display_name` | `VARCHAR(140)` | NULL | Staff display name. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE, INVITED, DISABLED. |
| `is_owner` | `BOOLEAN` | NOT NULL DEFAULT false | Store owner flag. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(store_id,user_id)
- At most one owner per store at application level

**Recommended indexes**
- `store_id`
- `status`

### 2.6 `staff_member_roles` — P0

Many-to-many staff → role mapping.

**Attribute count: 3**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `staff_member_id` | `UUID` | PK, FK staff_members.staff_member_id | Staff membership. |
| `role_id` | `UUID` | PK, FK roles.role_id | Assigned role. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Assignment time. |

### 2.7 `refresh_tokens` — P0

Server-side refresh-token/session registry.

**Attribute count: 12**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `token_id` | `UUID` | PK | Token/session id. |
| `user_id` | `UUID` | NOT NULL, FK users.user_id | Owner. |
| `family_id` | `UUID` | NOT NULL | Rotation family identifier. |
| `parent_token_id` | `UUID` | FK refresh_tokens.token_id NULL | Presented predecessor; NULL for a new login. |
| `replaced_by_token_id` | `UUID` | FK refresh_tokens.token_id NULL | Successor created by rotation. |
| `token_hash` | `VARCHAR(255)` | NOT NULL | Hashed refresh token. |
| `device_info` | `JSONB` | NOT NULL DEFAULT {} | UA/device hints. |
| `ip_address` | `INET` | NULL | Login IP. |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | Expiry. |
| `consumed_at` | `TIMESTAMPTZ` | NULL | One-time-use rotation marker. |
| `revoked_at` | `TIMESTAMPTZ` | NULL | Revocation time. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Issued time. |

**Key constraints**
- UNIQUE(token_hash)
- CHECK (parent_token_id IS NULL OR parent_token_id <> token_id)
- CHECK (replaced_by_token_id IS NULL OR replaced_by_token_id <> token_id)
- Self-referential parent/successor FKs are lineage evidence only; token timestamps and transactional rotation rules determine authority.

**Recommended indexes**
- `user_id`
- `family_id`
- `expires_at`
- `revoked_at`

### Relationships

users 1─N staff_members; stores 1─N staff_members; staff_members N─M roles via staff_member_roles; roles N─M permissions via role_permissions.

Refresh rotation is staff-only: a new login creates a new `family_id`; a valid
refresh locks the presented hash, marks `consumed_at`, and creates one successor in
the same family. Reuse of a consumed token revokes the entire family. Customer
refresh/logout storage is intentionally not present here; customer refresh APIs are
deferred until a dedicated customer session registry is approved.

### Generalized example

Example: Store owner Harsh has `Owner` role; another employee gets `Catalog Manager` with `products.read/write` but no `refunds.create` or `settings.manage` permission.

---

## 3. Customers, Addresses & Consent

Customer CRM identity used for storefront orders, marketing consent, saved addresses and customer history.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `customers` | P0 | 14 | Store-scoped buyer/customer profile. |
| `customer_addresses` | P0 | 15 | Reusable saved customer addresses. |
| `customer_consents` | P1 | 9 | Consent/audit ledger for marketing and privacy. |
| `customer_notes` | P1 | 5 | Append-only internal support/merchant notes. |

### 3.1 `customers` — P0

Store-scoped buyer/customer profile.

**Attribute count: 14**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `customer_id` | `UUID` | PK | Customer id. |
| `store_id` | `UUID` | FK stores.store_id | Owning store. |
| `email` | `CITEXT` | NULL | Customer email. |
| `phone` | `VARCHAR(32)` | NULL | Customer phone. |
| `first_name` | `VARCHAR(100)` | NULL | First name. |
| `last_name` | `VARCHAR(100)` | NULL | Last name. |
| `password_hash` | `VARCHAR(255)` | NULL | Optional storefront account password hash. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE, DISABLED. |
| `accepts_marketing` | `BOOLEAN` | NOT NULL DEFAULT false | Convenience current consent state. |
| `total_spent` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Derived/cached lifetime spend. |
| `orders_count` | `INT` | NOT NULL DEFAULT 0 | Derived/cached order count. |
| `last_order_at` | `TIMESTAMPTZ` | NULL | Latest order time. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,email) WHERE email IS NOT NULL

**Recommended indexes**
- `store_id`
- `email`
- `phone`
- `created_at`

### 3.2 `customer_addresses` — P0

Reusable saved customer addresses.

**Attribute count: 15**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `address_id` | `UUID` | PK | Address id. |
| `customer_id` | `UUID` | FK customers.customer_id | Customer. |
| `label` | `VARCHAR(50)` | NULL | Home, Office. |
| `first_name` | `VARCHAR(100)` | NULL | Recipient first name. |
| `last_name` | `VARCHAR(100)` | NULL | Recipient last name. |
| `phone` | `VARCHAR(32)` | NULL | Recipient phone. |
| `line1` | `VARCHAR(255)` | NOT NULL | Address line 1. |
| `line2` | `VARCHAR(255)` | NULL | Address line 2. |
| `city` | `VARCHAR(120)` | NOT NULL | City. |
| `state` | `VARCHAR(120)` | NOT NULL | State/region. |
| `postal_code` | `VARCHAR(24)` | NOT NULL | PIN/postal code. |
| `country_code` | `CHAR(2)` | NOT NULL | ISO country. |
| `is_default` | `BOOLEAN` | NOT NULL DEFAULT false | Default saved address. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Recommended indexes**
- `customer_id`
- `postal_code`

**Key constraints**
- UNIQUE(customer_id) WHERE is_default = true

### 3.3 `customer_consents` — P1

Consent/audit ledger for marketing and privacy.

**Attribute count: 8**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `consent_id` | `UUID` | PK | Consent event id. |
| `customer_id` | `UUID` | FK customers.customer_id | Customer. |
| `channel` | `VARCHAR(24)` | NOT NULL | EMAIL, SMS, WHATSAPP. |
| `purpose` | `VARCHAR(40)` | NOT NULL | MARKETING, PROMOTIONAL, NEWSLETTER. |
| `state` | `VARCHAR(24)` | NOT NULL | SUBSCRIBED, UNSUBSCRIBED. |
| `source` | `VARCHAR(50)` | NULL | Checkout, signup form, admin import. |
| `ip_address` | `INET` | NULL | Consent IP where applicable. |
| `occurred_at` | `TIMESTAMPTZ` | NOT NULL | Event time. |
| `metadata` | `JSONB` | NOT NULL DEFAULT {} | Evidence/provider metadata. |

**Recommended indexes**
- `customer_id`
- `channel`
- `occurred_at`

### 3.4 `customer_notes` — P1

Internal support/merchant notes. Notes are append-only operational evidence and
are never exposed in a storefront customer profile.

**Attribute count: 5**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `customer_note_id` | `UUID` | PK | Note id. |
| `customer_id` | `UUID` | FK customers.customer_id | Customer being annotated. |
| `actor_staff_member_id` | `UUID` | FK staff_members.staff_member_id NULL | Staff author; nullable for imported/system notes. |
| `body` | `TEXT` | NOT NULL | Bounded note text at the application boundary. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Immutable creation time. |

**Recommended indexes**
- `customer_id`
- `created_at`

### Relationships

stores 1─N customers; customers 1─N customer_addresses; customers 1─N customer_consents.

### Generalized example

Example: Guest checkout with `a@x.com` can create/attach a customer record. Their saved Home address may later change, but completed orders keep their own immutable order-address snapshot.

---

## 4. Product Catalog, Variants, Collections & Metafields

Core merchandising model for simple products, configurable variants, media, grouping and custom merchant fields.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `products` | P0 | 14 | Base merchandising product entity. |
| `product_options` | P0 | 5 | Variant dimensions such as Size or Color. |
| `product_option_values` | P0 | 6 | Allowed values under an option. |
| `product_variants` | P0 | 23 | Sellable SKU-level product unit including nullable shipping dimensions. |
| `variant_option_values` | P0 | 3 | Defines the exact option combination for a variant. |
| `media_assets` | P0 | 11 | Reusable image/video/file metadata; binary lives in object storage/CDN. |
| `product_media` | P0 | 7 | Attaches media to products and optionally a specific variant. |
| `collections` | P1 | 10 | Manual or rule-based merchandising collection. |
| `collection_products` | P1 | 4 | Many-to-many collection membership. |
| `tags` | P1 | 4 | Normalized store-level product tags. |
| `product_tags` | P1 | 3 | Many-to-many product tagging. |
| `metafield_definitions` | P2 | 8 | Defines validated custom fields available to resources. |
| `metafields` | P2 | 7 | Stores custom structured values without changing core schema. |

### 4.1 `products` — P0

Base merchandising product entity.

**Attribute count: 14**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `product_id` | `UUID` | PK | Product id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `title` | `VARCHAR(255)` | NOT NULL | Product title. |
| `slug` | `VARCHAR(255)` | NOT NULL | SEO/storefront URL handle. |
| `description_html` | `TEXT` | NULL | Rich description HTML. |
| `vendor` | `VARCHAR(160)` | NULL | Brand/vendor. |
| `product_type` | `VARCHAR(120)` | NULL | Merchant product type. |
| `status` | `VARCHAR(24)` | NOT NULL | DRAFT, ACTIVE, ARCHIVED. |
| `requires_shipping` | `BOOLEAN` | NOT NULL DEFAULT true | Default shipping behavior. |
| `taxable` | `BOOLEAN` | NOT NULL DEFAULT true | Default tax behavior. |
| `version` | `BIGINT` | NOT NULL DEFAULT 1 | Optimistic concurrency version for admin edits. |
| `published_at` | `TIMESTAMPTZ` | NULL | First/active publish time. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,slug)
- UNIQUE(store_id,product_id)

**Recommended indexes**
- `store_id`
- `status`
- `product_type`
- `vendor`
- `created_at`

### 4.2 `product_options` — P0

Variant dimensions such as Size or Color.

**Attribute count: 5**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `option_id` | `UUID` | PK | Option id. |
| `product_id` | `UUID` | FK products.product_id | Parent product. |
| `name` | `VARCHAR(80)` | NOT NULL | Size, Color. |
| `position` | `SMALLINT` | NOT NULL | UI ordering. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(product_id,name)
- UNIQUE(product_id,position)

### 4.3 `product_option_values` — P0

Allowed values under an option.

**Attribute count: 6**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `option_value_id` | `UUID` | PK | Value id. |
| `option_id` | `UUID` | FK product_options.option_id | Option. |
| `value` | `VARCHAR(120)` | NOT NULL | M, Red. |
| `position` | `SMALLINT` | NOT NULL | UI ordering. |
| `metadata` | `JSONB` | NOT NULL DEFAULT {} | Swatch hex, image hint, etc. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(option_id,value)

### 4.4 `product_variants` — P0

Sellable SKU-level product unit.

**Attribute count: 23**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `variant_id` | `UUID` | PK | Variant id. |
| `store_id` | `UUID` | FK stores.store_id | Owning store; must match the parent product store. |
| `product_id` | `UUID` | FK products.product_id | Parent product. |
| `sku` | `VARCHAR(120)` | NULL | Merchant SKU. |
| `barcode` | `VARCHAR(120)` | NULL | EAN/UPC/other barcode. |
| `option_signature` | `VARCHAR(512)` | NOT NULL | Canonical sorted option/value identity for this variant. |
| `title` | `VARCHAR(255)` | NULL | Derived display variant title. |
| `base_price` | `NUMERIC(19,4)` | NOT NULL | Default selling price. |
| `compare_at_price` | `NUMERIC(19,4)` | NULL | MRP/strike price. |
| `cost_price` | `NUMERIC(19,4)` | NULL | Internal product cost. |
| `currency` | `CHAR(3)` | NOT NULL | Default price currency. |
| `weight` | `NUMERIC(12,4)` | NULL | Variant weight. |
| `weight_unit` | `VARCHAR(8)` | NULL | kg/g/lb. |
| `length` | `NUMERIC(12,4)` | NULL | Shipping length. |
| `width` | `NUMERIC(12,4)` | NULL | Shipping width; provider `breadth` is adapter-only. |
| `height` | `NUMERIC(12,4)` | NULL | Shipping height. |
| `dimension_unit` | `VARCHAR(8)` | NULL | cm/in. |
| `position` | `INT` | NOT NULL DEFAULT 0 | Variant ordering. |
| `inventory_policy` | `VARCHAR(24)` | NOT NULL DEFAULT DENY | DENY for Release 1; CONTINUE is deferred and must not be implemented implicitly. |
| `is_active` | `BOOLEAN` | NOT NULL DEFAULT true | Sellability switch. |
| `version` | `BIGINT` | NOT NULL DEFAULT 1 | Optimistic concurrency version for admin edits. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(product_id,variant_id)
- UNIQUE(store_id,sku) WHERE sku IS NOT NULL
- UNIQUE(product_id,option_signature)
- Composite FK `(store_id,product_id)` references `products(store_id,product_id)`; reject parent-store drift.

**Recommended indexes**
- `product_id`
- `sku`
- `barcode`
- `base_price`
- `is_active`

### 4.5 `variant_option_values` — P0

Defines the exact option combination for a variant.

**Attribute count: 3**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `variant_id` | `UUID` | PK, FK product_variants.variant_id | Variant. |
| `option_value_id` | `UUID` | PK, FK product_option_values.option_value_id | Selected option value. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Combination invariant**

`option_signature` is generated transactionally from validated sorted
`(option_id,option_value_id)` pairs. It is not client-authoritative. Every option
value must belong to this product, each product option contributes at most one
value, and `UNIQUE(product_id,option_signature)` prevents two sellable variants
of one product from representing the same exact combination.

The join rows also enforce one value per product option and same-product option
value ownership transactionally.

### 4.6 `media_assets` — P0

Reusable image/video/file metadata; binary lives in object storage/CDN.

**Attribute count: 11**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `media_id` | `UUID` | PK | Media id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `media_type` | `VARCHAR(24)` | NOT NULL | IMAGE, VIDEO, FILE. |
| `storage_key` | `VARCHAR(512)` | NOT NULL | Object storage path/key. |
| `public_url` | `TEXT` | NOT NULL | CDN/public URL. |
| `alt_text` | `VARCHAR(255)` | NULL | Accessibility/SEO alt text. |
| `mime_type` | `VARCHAR(100)` | NULL | MIME type. |
| `width` | `INT` | NULL | Image/video width. |
| `height` | `INT` | NULL | Image/video height. |
| `size_bytes` | `BIGINT` | NULL | File size. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(storage_key)

**Recommended indexes**
- `store_id`
- `media_type`

### 4.7 `product_media` — P0

Attaches media to products and optionally a specific variant.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `product_media_id` | `UUID` | PK | Mapping id. |
| `product_id` | `UUID` | FK products.product_id | Product. |
| `variant_id` | `UUID` | FK product_variants.variant_id NULL | Optional variant-specific media. |
| `media_id` | `UUID` | FK media_assets.media_id | Media. |
| `position` | `INT` | NOT NULL DEFAULT 0 | Gallery order. |
| `is_primary` | `BOOLEAN` | NOT NULL DEFAULT false | Primary product/variant media. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Recommended indexes**
- `product_id`
- `variant_id`
- `position`

### 4.8 `collections` — P1

Manual or rule-based merchandising collection.

**Attribute count: 10**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `collection_id` | `UUID` | PK | Collection id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `title` | `VARCHAR(200)` | NOT NULL | Collection title. |
| `slug` | `VARCHAR(220)` | NOT NULL | URL handle. |
| `description_html` | `TEXT` | NULL | Collection copy. |
| `collection_type` | `VARCHAR(24)` | NOT NULL | MANUAL or SMART. |
| `rule_json` | `JSONB` | NULL | Smart collection rule expression. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE/DRAFT. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,slug)

**Recommended indexes**
- `store_id`
- `status`

### 4.9 `collection_products` — P1

Many-to-many collection membership.

**Attribute count: 4**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `collection_id` | `UUID` | PK, FK collections.collection_id | Collection. |
| `product_id` | `UUID` | PK, FK products.product_id | Product. |
| `position` | `INT` | NOT NULL DEFAULT 0 | Manual ordering. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Added time. |

**Recommended indexes**
- `collection_id`
- `position`
- `product_id`

### 4.10 `tags` — P1

Normalized store-level product tags.

**Attribute count: 4**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `tag_id` | `UUID` | PK | Tag id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `name` | `VARCHAR(100)` | NOT NULL | Summer, Bestseller. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(store_id,name)

### 4.11 `product_tags` — P1

Many-to-many product tagging.

**Attribute count: 3**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `product_id` | `UUID` | PK, FK products.product_id | Product. |
| `tag_id` | `UUID` | PK, FK tags.tag_id | Tag. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Tagged time. |

### 4.12 `metafield_definitions` — P2

Defines validated custom fields available to resources.

**Attribute count: 8**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `definition_id` | `UUID` | PK | Definition id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `resource_type` | `VARCHAR(40)` | NOT NULL | PRODUCT, VARIANT, CUSTOMER, ORDER. |
| `namespace` | `VARCHAR(80)` | NOT NULL | e.g. custom. |
| `key` | `VARCHAR(100)` | NOT NULL | e.g. fabric. |
| `value_type` | `VARCHAR(40)` | NOT NULL | text, integer, boolean, json, url. |
| `validation` | `JSONB` | NOT NULL DEFAULT {} | Min/max/list/etc. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(store_id,resource_type,namespace,key)

### 4.13 `metafields` — P2

Stores custom structured values without changing core schema.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `metafield_id` | `UUID` | PK | Metafield id. |
| `definition_id` | `UUID` | FK metafield_definitions.definition_id | Definition. |
| `resource_type` | `VARCHAR(40)` | NOT NULL | Resource type. |
| `resource_id` | `UUID` | NOT NULL | Resource id; app-enforced polymorphic reference. |
| `value_json` | `JSONB` | NOT NULL | Typed value representation. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(definition_id,resource_id)

**Recommended indexes**
- `resource_type`
- `resource_id`

### Relationships

products 1─N product_options; product_options 1─N product_option_values; products 1─N product_variants; variants N─M option_values via variant_option_values; products 1─N product_media; collections N─M products; products N─M tags.

### Generalized example

Example: T-Shirt is one product. Options = Color and Size. Values = Black/White and M/L. Sellable variant = Black + M with SKU TSH-BLK-M and its own price, barcode, image and inventory item.

### Technical notes

- Keep variant attributes normalized for filtering/indexing. JSONB is fine for low-risk extensibility, not as the only variant model.

---

## 5. Locations, Inventory & Stock Ledger

Tracks physical stock by variant and location, prevents overselling, supports reservations and creates an auditable stock movement ledger.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `locations` | P0 | 14 | Physical inventory/fulfillment location. |
| `inventory_items` | P0 | 7 | Inventory control record linked 1:1 with a variant. |
| `inventory_levels` | P0 | 8 | Current quantity buckets for an inventory item at a location. |
| `inventory_reservations` | P0 | 10 | Temporary stock holds used by checkout/order orchestration. |
| `inventory_movements` | P0 | 10 | Immutable stock ledger explaining every stock change. |
| `inventory_transfers` | P1 | 10 | Header for moving stock between two locations. |
| `inventory_transfer_items` | P1 | 7 | Line items within a transfer. |

### 5.1 `locations` — P0

Physical inventory/fulfillment location.

**Attribute count: 14**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `location_id` | `UUID` | PK | Location id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `name` | `VARCHAR(160)` | NOT NULL | Noida Warehouse. |
| `location_type` | `VARCHAR(32)` | NOT NULL | WAREHOUSE, STORE, 3PL. |
| `line1` | `VARCHAR(255)` | NULL | Address. |
| `city` | `VARCHAR(120)` | NULL | City. |
| `state` | `VARCHAR(120)` | NULL | State. |
| `postal_code` | `VARCHAR(24)` | NULL | Postal code. |
| `country_code` | `CHAR(2)` | NOT NULL | Country. |
| `is_active` | `BOOLEAN` | NOT NULL DEFAULT true | Operational flag. |
| `fulfills_online_orders` | `BOOLEAN` | NOT NULL DEFAULT true | Eligible for storefront allocation. |
| `priority` | `INT` | NOT NULL DEFAULT 100 | Lower values are selected first for deterministic allocation. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Last configuration change. |

**Key constraints**
- UNIQUE(store_id,name)
- CHECK priority BETWEEN 0 AND 10000

**Recommended indexes**
- `store_id`
- `is_active`

### 5.2 `inventory_items` — P0

Inventory control record linked 1:1 with a variant.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `inventory_item_id` | `UUID` | PK | Inventory item id. |
| `variant_id` | `UUID` | FK product_variants.variant_id UNIQUE | Variant. |
| `tracked` | `BOOLEAN` | NOT NULL DEFAULT true | Whether inventory is tracked. |
| `harmonized_code` | `VARCHAR(32)` | NULL | HS/HSN code. |
| `country_of_origin` | `CHAR(2)` | NULL | ISO origin country. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

### 5.3 `inventory_levels` — P0

Current quantity buckets for an inventory item at a location.

**Attribute count: 8**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `inventory_level_id` | `UUID` | PK | Level id. |
| `inventory_item_id` | `UUID` | FK inventory_items.inventory_item_id | Item. |
| `location_id` | `UUID` | FK locations.location_id | Location. |
| `on_hand` | `INT` | NOT NULL DEFAULT 0 | Physical counted stock. |
| `reserved` | `INT` | NOT NULL DEFAULT 0 | Held for active checkout/order. |
| `incoming` | `INT` | NOT NULL DEFAULT 0 | Expected inbound stock. |
| `damaged` | `INT` | NOT NULL DEFAULT 0 | Unsellable damaged stock. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Last update. |

**Key constraints**
- UNIQUE(inventory_item_id,location_id)
- CHECK on_hand >= 0
- CHECK reserved >= 0
- CHECK incoming >= 0
- CHECK damaged >= 0
- CHECK reserved + damaged <= on_hand

Reserve increments only `reserved`; release/expire decrements only `reserved`;
consume decrements `reserved` and `on_hand`. Reservations are allocation evidence,
while movements are physical-stock evidence. Reserve/release/expire therefore do
not create physical movement rows; consume creates exactly one
`RESERVATION_CONSUME` row with `quantity_delta=-quantity` and the order reference.

**Recommended indexes**
- `location_id`
- `inventory_item_id`

### 5.4 `inventory_reservations` — P0

Temporary stock holds used by checkout/order orchestration.

**Attribute count: 10**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `reservation_id` | `UUID` | PK | Reservation id. |
| `inventory_item_id` | `UUID` | FK inventory_items.inventory_item_id | Reserved SKU/item. |
| `location_id` | `UUID` | FK locations.location_id | Reservation location. |
| `checkout_id` | `UUID` | NULL | Checkout session reference. |
| `order_id` | `UUID` | NULL | Order reference after conversion. |
| `quantity` | `INT` | NOT NULL | Held qty. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE, CONSUMED, RELEASED, EXPIRED. |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | Auto-release deadline. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- CHECK quantity > 0
- CHECK (checkout_id IS NOT NULL OR order_id IS NOT NULL)

**Recommended indexes**
- `inventory_item_id`
- `location_id`
- `status`
- `expires_at`

### 5.5 `inventory_movements` — P0

Immutable stock ledger explaining every stock change.

**Attribute count: 10**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `movement_id` | `UUID` | PK | Movement id. |
| `inventory_item_id` | `UUID` | FK inventory_items.inventory_item_id | Item. |
| `location_id` | `UUID` | FK locations.location_id | Location. |
| `movement_type` | `VARCHAR(40)` | NOT NULL | PURCHASE_RECEIPT, RESERVATION_CONSUME, RETURN_RESTOCK, RETURN_DAMAGED, MANUAL_ADJUSTMENT, RECONCILIATION, TRANSFER_OUT, TRANSFER_IN. |
| `quantity_delta` | `INT` | NOT NULL | Signed quantity change. |
| `reference_type` | `VARCHAR(40)` | NULL | ORDER, RETURN, TRANSFER, ADMIN. |
| `reference_id` | `UUID` | NULL | Related business object. |
| `reason` | `VARCHAR(255)` | NULL | Human/business reason. |
| `actor_user_id` | `UUID` | FK users.user_id NULL | Staff/system actor. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Immutable event time. |

**Recommended indexes**
- `inventory_item_id`
- `location_id`
- `created_at`
- `reference_type`
- `reference_id`

### 5.6 `inventory_transfers` — P1

Header for moving stock between two locations.

**Attribute count: 10**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `transfer_id` | `UUID` | PK | Transfer id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `from_location_id` | `UUID` | FK locations.location_id | Source. |
| `to_location_id` | `UUID` | FK locations.location_id | Destination. |
| `status` | `VARCHAR(24)` | NOT NULL | DRAFT, IN_TRANSIT, PARTIALLY_RECEIVED, RECEIVED, CANCELLED. |
| `reference` | `VARCHAR(100)` | NULL | Merchant reference. |
| `created_by` | `UUID` | FK users.user_id NULL | Staff actor. |
| `shipped_at` | `TIMESTAMPTZ` | NULL | Transfer dispatch time. |
| `received_at` | `TIMESTAMPTZ` | NULL | Receive time. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- CHECK from_location_id <> to_location_id

**Recommended indexes**
- `store_id`
- `status`
- `created_at`

### 5.7 `inventory_transfer_items` — P1

Line items within a transfer.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `transfer_item_id` | `UUID` | PK | Transfer line id. |
| `transfer_id` | `UUID` | FK inventory_transfers.transfer_id | Transfer. |
| `inventory_item_id` | `UUID` | FK inventory_items.inventory_item_id | Inventory item. |
| `quantity` | `INT` | NOT NULL | Requested qty. |
| `received_quantity` | `INT` | NOT NULL DEFAULT 0 | Actually received qty. |
| `damaged_quantity` | `INT` | NOT NULL DEFAULT 0 | Received quantity classified as damaged and not sellable. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(transfer_id,inventory_item_id)
- CHECK quantity > 0
- CHECK damaged_quantity >= 0 AND damaged_quantity <= received_quantity

### Relationships

product_variants 1─1 inventory_items; inventory_items 1─N inventory_levels; locations 1─N inventory_levels; inventory_reservations temporarily consume availability; inventory_movements is append-only audit ledger.

### Generalized example

Example: SKU has on_hand=10, reserved=2, damaged=1 → sellable available = 10 - 2 - 1 = 7. Checkout reserves 1 more atomically; payment failure releases it; successful completion consumes the reservation and records a RESERVATION_CONSUME movement.

### Technical notes

- Treat available quantity as a derived business calculation; avoid independently storing both on_hand and available unless you can guarantee consistency.

---

## 6. Markets, Catalogs & Price Lists

Provides default pricing now and enables B2B/international/channel-specific pricing later without rewriting variants.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `markets` | P2 | 8 | Geographic/commercial customer context. |
| `catalogs` | P2 | 7 | Defines what products are available in a context. |
| `catalog_products` | P2 | 4 | Product publication/availability in a catalog. |
| `price_lists` | P2 | 9 | Pricing context attached to a catalog. |
| `price_list_items` | P2 | 8 | Variant-specific contextual prices. |

### 6.1 `markets` — P2

Geographic/commercial customer context.

**Attribute count: 8**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `market_id` | `UUID` | PK | Market id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `name` | `VARCHAR(120)` | NOT NULL | India, UAE, Wholesale India. |
| `currency` | `CHAR(3)` | NOT NULL | Market currency. |
| `country_codes` | `JSONB` | NOT NULL DEFAULT [] | ISO countries served. |
| `is_primary` | `BOOLEAN` | NOT NULL DEFAULT false | Primary market. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE/INACTIVE. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(store_id,name)

### 6.2 `catalogs` — P2

Defines what products are available in a context.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `catalog_id` | `UUID` | PK | Catalog id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `market_id` | `UUID` | FK markets.market_id NULL | Optional market context. |
| `channel_id` | `UUID` | FK sales_channels.channel_id NULL | Optional sales channel context. |
| `name` | `VARCHAR(160)` | NOT NULL | Catalog name. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE/INACTIVE. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(store_id,name)

### 6.3 `catalog_products` — P2

Product publication/availability in a catalog.

**Attribute count: 4**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `catalog_id` | `UUID` | PK, FK catalogs.catalog_id | Catalog. |
| `product_id` | `UUID` | PK, FK products.product_id | Product. |
| `is_available` | `BOOLEAN` | NOT NULL DEFAULT true | Availability. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Published time. |

### 6.4 `price_lists` — P2

Pricing context attached to a catalog.

**Attribute count: 9**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `price_list_id` | `UUID` | PK | Price list id. |
| `catalog_id` | `UUID` | FK catalogs.catalog_id | Catalog. |
| `name` | `VARCHAR(160)` | NOT NULL | India Retail INR. |
| `currency` | `CHAR(3)` | NOT NULL | Price-list currency. |
| `adjustment_type` | `VARCHAR(24)` | NULL | PERCENTAGE or FIXED/default overrides. |
| `adjustment_value` | `NUMERIC(19,4)` | NULL | Default adjustment. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE/INACTIVE. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

### 6.5 `price_list_items` — P2

Variant-specific contextual prices.

**Attribute count: 8**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `price_list_item_id` | `UUID` | PK | Price item id. |
| `price_list_id` | `UUID` | FK price_lists.price_list_id | Price list. |
| `variant_id` | `UUID` | FK product_variants.variant_id | Variant. |
| `price` | `NUMERIC(19,4)` | NOT NULL | Override selling price. |
| `compare_at_price` | `NUMERIC(19,4)` | NULL | Contextual compare-at price. |
| `min_quantity` | `INT` | NULL | Optional quantity tier threshold. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(price_list_id,variant_id,min_quantity)

**Recommended indexes**
- `variant_id`
- `price_list_id`

### Relationships

markets 1─N catalogs; catalogs N─M products via catalog_products; catalogs 1─N price_lists; price_lists 1─N price_list_items; price_list_items N─1 variants.

### Generalized example

Example: Default Black/M variant price is ₹1,999. India retail uses default; UAE catalog can expose the same SKU at AED 99; wholesale catalog can set a lower price above 10 units.

### Technical notes

- P2 means design now, implement when a client actually needs international/B2B contextual pricing.

---

## 7. Discounts, Coupons & Promotions

Rule-based promotion engine supporting codes, automatic discounts, limits and redemption history.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `discounts` | P1 | 15 | Promotion header and lifecycle. |
| `discount_codes` | P1 | 5 | One or more codes attached to a CODE discount. |
| `discount_rules` | P1 | 6 | Conditions under which the discount applies. |
| `discount_targets` | P1 | 5 | Limits discount to products/variants/collections/shipping. |
| `discount_redemptions` | P1 | 8 | Immutable usage ledger; authoritative source for usage counts. |

### 7.1 `discounts` — P1

Promotion header and lifecycle.

**Attribute count: 15**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `discount_id` | `UUID` | PK | Discount id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `name` | `VARCHAR(160)` | NOT NULL | Summer 10%. |
| `method` | `VARCHAR(24)` | NOT NULL | CODE or AUTOMATIC. |
| `discount_type` | `VARCHAR(32)` | NOT NULL | PERCENTAGE, FIXED_AMOUNT, FREE_SHIPPING, BUY_X_GET_Y. |
| `value` | `NUMERIC(19,4)` | NULL | Percent or fixed amount depending type. |
| `currency` | `CHAR(3)` | NULL | Required for fixed money discount. |
| `starts_at` | `TIMESTAMPTZ` | NULL | Activation time. |
| `ends_at` | `TIMESTAMPTZ` | NULL | Expiry. |
| `usage_limit_total` | `INT` | NULL | Global max uses. |
| `usage_limit_per_customer` | `INT` | NULL | Per-customer max uses. |
| `is_combinable` | `BOOLEAN` | NOT NULL DEFAULT false | Can combine with other promos. |
| `status` | `VARCHAR(24)` | NOT NULL | DRAFT, ACTIVE, EXPIRED, DISABLED. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Recommended indexes**
- `store_id`
- `status`
- `starts_at`
- `ends_at`

### 7.2 `discount_codes` — P1

One or more codes attached to a CODE discount.

**Attribute count: 5**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `discount_code_id` | `UUID` | PK | Code id. |
| `discount_id` | `UUID` | FK discounts.discount_id | Discount. |
| `code` | `CITEXT` | NOT NULL | SAVE10. |
| `usage_limit` | `INT` | NULL | Optional code-specific limit. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(code) within a single-store DB; multi-store scope if shared DB

**Recommended indexes**
- `code`

### 7.3 `discount_rules` — P1

Conditions under which the discount applies.

**Attribute count: 6**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `rule_id` | `UUID` | PK | Rule id. |
| `discount_id` | `UUID` | FK discounts.discount_id | Discount. |
| `rule_type` | `VARCHAR(40)` | NOT NULL | MIN_SUBTOTAL, MIN_QTY, FIRST_ORDER, CUSTOMER_TAG. |
| `operator` | `VARCHAR(16)` | NOT NULL | GTE, EQ, IN, etc. |
| `value_json` | `JSONB` | NOT NULL | Rule value. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

### 7.4 `discount_targets` — P1

Limits discount to products/variants/collections/shipping.

**Attribute count: 5**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `target_id` | `UUID` | PK | Target id. |
| `discount_id` | `UUID` | FK discounts.discount_id | Discount. |
| `target_type` | `VARCHAR(32)` | NOT NULL | ALL, PRODUCT, VARIANT, COLLECTION, SHIPPING. |
| `resource_id` | `UUID` | NULL | Target resource id when needed. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Recommended indexes**
- `discount_id`
- `target_type`
- `resource_id`

### 7.5 `discount_redemptions` — P1

Immutable usage ledger; authoritative source for usage counts.

**Attribute count: 8**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `redemption_id` | `UUID` | PK | Redemption id. |
| `discount_id` | `UUID` | FK discounts.discount_id | Discount. |
| `discount_code_id` | `UUID` | FK discount_codes.discount_code_id NULL | Used code. |
| `customer_id` | `UUID` | FK customers.customer_id NULL | Customer if known. |
| `order_id` | `UUID` | NOT NULL, FK orders.order_id | Completed order reference. |
| `discount_amount` | `NUMERIC(19,4)` | NOT NULL | Amount actually allocated. |
| `currency` | `CHAR(3)` | NOT NULL | Order currency. |
| `redeemed_at` | `TIMESTAMPTZ` | NOT NULL | Redemption time. |

**Recommended indexes**
- `discount_id`
- `customer_id`
- `redeemed_at`

**Key constraints**
- UNIQUE(order_id,discount_id,discount_code_id) NULLS NOT DISTINCT
- `discount_code_id` is NULL for automatic discounts; each evaluated application gets one redemption identity.

### Relationships

discounts 1─N discount_codes/rules/targets/redemptions. Redemptions attach to completed orders and customers for usage enforcement.

### Generalized example

Example: SAVE10 = CODE + PERCENTAGE 10. Rule requires subtotal >= ₹2,000; target = all products; usage limit = once/customer. Usage is checked from redemption records, not only a mutable counter.

---

## 8. Cart & Checkout Orchestration

Keeps shopping intent durable, calculates authoritative totals, reserves inventory and creates an order safely.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `carts` | P0 | 13 | Durable active/abandoned shopping cart; Redis may cache this record. |
| `cart_lines` | P0 | 7 | Variant lines selected in a cart. |
| `checkout_sessions` | P0 | 18 | Server-authoritative checkout state machine with opaque guest token. |
| `checkout_lines` | P0 | 12 | Immutable-ish priced line snapshot for the checkout attempt. |
| `checkout_addresses` | P0 | 11 | Shipping/billing address snapshot before order creation. |
| `checkout_shipping_rates` | P1 | 11 | Provider-calculated/merchant shipping options for a checkout. |

### 8.1 `carts` — P0

Durable active/abandoned shopping cart; Redis may cache this record.

**Attribute count: 13**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `cart_id` | `UUID` | PK | Cart id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `customer_id` | `UUID` | FK customers.customer_id NULL | Logged-in/recognized customer. |
| `cart_token` | `VARCHAR(128)` | NOT NULL | Public opaque cart token. |
| `version` | `BIGINT` | NOT NULL DEFAULT 1 | Optimistic concurrency version, incremented on every mutation. |
| `channel_id` | `UUID` | FK sales_channels.channel_id NULL | Sales channel. |
| `currency` | `CHAR(3)` | NOT NULL | Cart currency. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE, CONVERTED, ABANDONED, EXPIRED. |
| `email` | `CITEXT` | NULL | Checkout/contact email. |
| `phone` | `VARCHAR(32)` | NULL | Checkout/contact phone. |
| `expires_at` | `TIMESTAMPTZ` | NULL | Cart expiry. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(cart_token)

**Recommended indexes**
- `store_id`
- `customer_id`
- `status`
- `updated_at`

### 8.2 `cart_lines` — P0

Variant lines selected in a cart.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `cart_line_id` | `UUID` | PK | Cart line id. |
| `cart_id` | `UUID` | FK carts.cart_id | Cart. |
| `variant_id` | `UUID` | FK product_variants.variant_id | Variant. |
| `quantity` | `INT` | NOT NULL | Requested qty. |
| `properties` | `JSONB` | NOT NULL DEFAULT {} | Line personalization/custom properties. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Added time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- CHECK quantity > 0
- Typically UNIQUE(cart_id,variant_id,properties hash)

**Recommended indexes**
- `cart_id`
- `variant_id`

### 8.3 `checkout_sessions` — P0

Server-authoritative checkout state machine.

**Attribute count: 18**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `checkout_id` | `UUID` | PK | Checkout id. |
| `checkout_token` | `VARCHAR(128)` | NOT NULL UNIQUE | Opaque guest-checkout authorization material; never sequential. |
| `version` | `BIGINT` | NOT NULL DEFAULT 1 | Optimistic concurrency version, incremented on every mutation. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `cart_id` | `UUID` | FK carts.cart_id | Source cart. |
| `customer_id` | `UUID` | FK customers.customer_id NULL | Customer. |
| `idempotency_key` | `VARCHAR(160)` | NULL | Creation/retry key where applicable; completion uses `idempotency_records`. |
| `status` | `VARCHAR(32)` | NOT NULL | OPEN, PRICED, INVENTORY_RESERVED, PAYMENT_PENDING, COMPLETED, EXPIRED, FAILED. |
| `currency` | `CHAR(3)` | NOT NULL | Checkout currency. |
| `subtotal_amount` | `NUMERIC(19,4)` | NOT NULL | Lines subtotal. |
| `discount_amount` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Discount total. |
| `tax_amount` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Tax total. |
| `shipping_amount` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Shipping total. |
| `grand_total` | `NUMERIC(19,4)` | NOT NULL | Authoritative amount due. |
| `selected_shipping_rate_id` | `UUID` | NULL | Chosen shipping option. |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | Checkout/reservation expiry. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,idempotency_key)
- UNIQUE(store_id,checkout_id)

**Recommended indexes**
- `cart_id`
- `status`
- `expires_at`

### 8.4 `checkout_lines` — P0

Immutable-ish priced line snapshot for the checkout attempt.

**Attribute count: 12**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `checkout_line_id` | `UUID` | PK | Checkout line id. |
| `checkout_id` | `UUID` | FK checkout_sessions.checkout_id | Checkout. |
| `variant_id` | `UUID` | FK product_variants.variant_id | Variant source. |
| `product_title` | `VARCHAR(255)` | NOT NULL | Snapshot title. |
| `variant_title` | `VARCHAR(255)` | NULL | Snapshot variant title. |
| `sku` | `VARCHAR(120)` | NULL | Snapshot SKU. |
| `quantity` | `INT` | NOT NULL | Quantity. |
| `unit_price` | `NUMERIC(19,4)` | NOT NULL | Server-resolved price. |
| `discount_amount` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Line discount. |
| `tax_amount` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Line tax. |
| `line_total` | `NUMERIC(19,4)` | NOT NULL | Final line total. |
| `properties` | `JSONB` | NOT NULL DEFAULT {} | Personalization snapshot. |

**Key constraints**
- CHECK quantity > 0

**Recommended indexes**
- `checkout_id`
- `variant_id`

### 8.5 `checkout_addresses` — P0

Shipping/billing address snapshot before order creation.

**Attribute count: 14**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `checkout_address_id` | `UUID` | PK | Address snapshot id. |
| `checkout_id` | `UUID` | FK checkout_sessions.checkout_id | Checkout. |
| `address_type` | `VARCHAR(16)` | NOT NULL | SHIPPING or BILLING. |
| `name` | `VARCHAR(200)` | NOT NULL | Recipient/billing name. |
| `phone` | `VARCHAR(32)` | NULL | Phone. |
| `line1` | `VARCHAR(255)` | NOT NULL | Line 1. |
| `line2` | `VARCHAR(255)` | NULL | Line 2. |
| `city` | `VARCHAR(120)` | NOT NULL | City. |
| `state` | `VARCHAR(120)` | NOT NULL | State. |
| `postal_code` | `VARCHAR(24)` | NOT NULL | Postal code. |
| `country_code` | `CHAR(2)` | NOT NULL | Country. |

**Key constraints**
- UNIQUE(checkout_id,address_type)

### 8.6 `checkout_shipping_rates` — P1

Provider-calculated/merchant shipping options for a checkout.

**Attribute count: 11**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `shipping_rate_id` | `UUID` | PK | Rate id. |
| `checkout_id` | `UUID` | FK checkout_sessions.checkout_id | Checkout. |
| `provider` | `VARCHAR(64)` | NULL | Shiprocket, Delhivery, MANUAL. |
| `service_code` | `VARCHAR(80)` | NULL | Provider service code. |
| `title` | `VARCHAR(160)` | NOT NULL | Standard Delivery. |
| `amount` | `NUMERIC(19,4)` | NOT NULL | Rate amount. |
| `currency` | `CHAR(3)` | NOT NULL | Currency. |
| `estimated_days_min` | `INT` | NULL | Min transit days. |
| `estimated_days_max` | `INT` | NULL | Max transit days. |
| `expires_at` | `TIMESTAMPTZ` | NULL | Quote validity. |
| `raw_quote` | `JSONB` | NOT NULL DEFAULT {} | Provider response subset. |

**Recommended indexes**
- `checkout_id`
- `provider`

### Relationships

carts 1─N cart_lines; carts 1─N checkout_sessions; checkout_sessions 1─N checkout_lines/addresses/shipping_rates; checkout completion atomically creates one order and consumes inventory reservations.

### Generalized example

Example: Customer adds 2 shoes to cart. Checkout recalculates live price, applies SAVE10, validates PIN code, quotes shipping, reserves stock, initiates payment and then converts to one immutable order. Browser-sent totals are never trusted.

### Technical notes

- Redis should cache carts and rate-limit/session data, but PostgreSQL remains durable source of truth.

---

## 9. Orders & Immutable Commercial Snapshot

Permanent commercial record created from checkout. Stores historical prices, addresses, taxes, discounts and state changes independently of future catalog edits.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `orders` | P0 | 22 | Order header and high-level commercial state. |
| `order_items` | P0 | 15 | Immutable item snapshot purchased by the customer. |
| `order_addresses` | P0 | 11 | Immutable order shipping/billing address snapshots. |
| `order_discount_allocations` | P1 | 7 | Explains which discount reduced which order/line amount. |
| `order_tax_lines` | P1 | 7 | Tax breakdown for invoice/reporting. |
| `order_status_history` | P0 | 9 | Append-only order lifecycle timeline. |

### 9.1 `orders` — P0

Order header and high-level commercial state.

**Attribute count: 22**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `order_id` | `UUID` | PK | Order id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `order_number` | `BIGINT` | NOT NULL | Sequential merchant-facing number. |
| `order_name` | `VARCHAR(40)` | NOT NULL | Display reference e.g. #LU10021. |
| `customer_id` | `UUID` | FK customers.customer_id NULL | Customer. |
| `checkout_id` | `UUID` | FK checkout_sessions.checkout_id NULL | Source checkout. |
| `channel_id` | `UUID` | FK sales_channels.channel_id NULL | Source channel. |
| `currency` | `CHAR(3)` | NOT NULL | Order currency. |
| `subtotal_amount` | `NUMERIC(19,4)` | NOT NULL | Subtotal snapshot. |
| `discount_amount` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Total discounts. |
| `tax_amount` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Tax total. |
| `shipping_amount` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Shipping total. |
| `grand_total` | `NUMERIC(19,4)` | NOT NULL | Final order amount. |
| `financial_status` | `VARCHAR(32)` | NOT NULL | PENDING, AUTHORIZED, PAID, PARTIALLY_REFUNDED, REFUNDED, VOIDED. |
| `fulfillment_status` | `VARCHAR(32)` | NOT NULL | Derived order summary: UNFULFILLED, PARTIAL, FULFILLED, RETURNED; not the fulfillment aggregate lifecycle. |
| `order_status` | `VARCHAR(32)` | NOT NULL | DRAFT, PENDING, CONFIRMED, PROCESSING, COMPLETED, ON_HOLD, CANCELLED. |
| `customer_note` | `TEXT` | NULL | Buyer note. |
| `admin_note` | `TEXT` | NULL | Internal note. |
| `placed_at` | `TIMESTAMPTZ` | NULL | Placement time; NULL while `order_status=DRAFT`. |
| `cancelled_at` | `TIMESTAMPTZ` | NULL | Cancellation time. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,order_number)
- UNIQUE(store_id,order_name)
- UNIQUE(store_id,order_id)
- UNIQUE(store_id,checkout_id) WHERE checkout_id IS NOT NULL
- CHECK ((order_status = 'DRAFT' AND placed_at IS NULL) OR (order_status <> 'DRAFT' AND placed_at IS NOT NULL))

**Recommended indexes**
- `store_id`
- `customer_id`
- `financial_status`
- `fulfillment_status`
- `order_status`
- `placed_at`

### 9.2 `order_items` — P0

Immutable item snapshot purchased by the customer.

**Attribute count: 15**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `order_item_id` | `UUID` | PK | Order item id. |
| `order_id` | `UUID` | NOT NULL, FK orders.order_id | Owning order; every item belongs to exactly one order. |
| `product_id` | `UUID` | FK products.product_id NULL | Original product reference; nullable if deleted. |
| `variant_id` | `UUID` | FK product_variants.variant_id NULL | Original variant reference; nullable if deleted. |
| `product_title` | `VARCHAR(255)` | NOT NULL | Purchase-time product title. |
| `variant_title` | `VARCHAR(255)` | NULL | Purchase-time variant title. |
| `sku` | `VARCHAR(120)` | NULL | Purchase-time SKU. |
| `quantity` | `INT` | NOT NULL | Purchased qty. |
| `unit_price` | `NUMERIC(19,4)` | NOT NULL | Price each. |
| `discount_amount` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Line discount. |
| `tax_amount` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Line tax. |
| `line_total` | `NUMERIC(19,4)` | NOT NULL | Final line total. |
| `requires_shipping` | `BOOLEAN` | NOT NULL | Snapshot. |
| `properties` | `JSONB` | NOT NULL DEFAULT {} | Customization snapshot. |

**Key constraints**
- CHECK quantity > 0

**Recommended indexes**
- `order_id`
- `sku`

### 9.3 `order_addresses` — P0

Immutable order shipping/billing address snapshots.

**Attribute count: 11**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `order_address_id` | `UUID` | PK | Address id. |
| `order_id` | `UUID` | FK orders.order_id | Order. |
| `address_type` | `VARCHAR(16)` | NOT NULL | SHIPPING or BILLING. |
| `name` | `VARCHAR(200)` | NOT NULL | Recipient/billing name. |
| `phone` | `VARCHAR(32)` | NULL | Phone. |
| `line1` | `VARCHAR(255)` | NOT NULL | Address line 1. |
| `line2` | `VARCHAR(255)` | NULL | Address line 2. |
| `city` | `VARCHAR(120)` | NOT NULL | City. |
| `state` | `VARCHAR(120)` | NOT NULL | State. |
| `postal_code` | `VARCHAR(24)` | NOT NULL | Postal code. |
| `country_code` | `CHAR(2)` | NOT NULL | Country. |

**Key constraints**
- UNIQUE(order_id,address_type)

### 9.4 `order_discount_allocations` — P1

Explains which discount reduced which order/line amount.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `allocation_id` | `UUID` | PK | Allocation id. |
| `order_id` | `UUID` | FK orders.order_id | Order. |
| `order_item_id` | `UUID` | FK order_items.order_item_id NULL | Null for order/shipping-level discount. |
| `discount_id` | `UUID` | FK discounts.discount_id NULL | Source discount. |
| `title` | `VARCHAR(160)` | NOT NULL | Snapshot promo title/code. |
| `amount` | `NUMERIC(19,4)` | NOT NULL | Allocated money. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Recommended indexes**
- `order_id`
- `order_item_id`

### 9.5 `order_tax_lines` — P1

Tax breakdown for invoice/reporting.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `tax_line_id` | `UUID` | PK | Tax line id. |
| `order_id` | `UUID` | FK orders.order_id | Order. |
| `order_item_id` | `UUID` | FK order_items.order_item_id NULL | Optional line-level tax. |
| `tax_name` | `VARCHAR(80)` | NOT NULL | GST, IGST, VAT. |
| `rate` | `NUMERIC(9,6)` | NOT NULL | Tax rate fraction/percent convention documented by app. |
| `amount` | `NUMERIC(19,4)` | NOT NULL | Tax amount. |
| `metadata` | `JSONB` | NOT NULL DEFAULT {} | HSN/jurisdiction details. |

**Recommended indexes**
- `order_id`
- `order_item_id`

### 9.6 `order_status_history` — P0

Append-only order lifecycle timeline.

**Attribute count: 9**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `history_id` | `UUID` | PK | History id. |
| `order_id` | `UUID` | FK orders.order_id | Order. |
| `status_type` | `VARCHAR(40)` | NOT NULL | ORDER, FINANCIAL, FULFILLMENT. |
| `from_status` | `VARCHAR(32)` | NULL | Previous state. |
| `to_status` | `VARCHAR(32)` | NOT NULL | New state. |
| `reason` | `VARCHAR(255)` | NULL | Reason/comment. |
| `actor_type` | `VARCHAR(24)` | NOT NULL | SYSTEM, STAFF, CUSTOMER, PROVIDER. |
| `actor_id` | `UUID` | NULL | Actor when available. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Transition time. |

**Recommended indexes**
- `order_id`
- `created_at`
- `status_type`

### Relationships

orders 1─N order_items/order_addresses/discount_allocations/tax_lines/status_history. Customer and catalog references are useful links but snapshot columns remain authoritative for history.

### Generalized example

Example: Customer later changes Home address and merchant renames product from “Classic Tee” to “Classic T-Shirt”. Old order still shows exactly the purchased title, price and shipping address from order snapshot.

---

## 10. Payments, Transactions & Refund Ledger

Gateway-independent payment model supporting online/COD, retries, authorization/capture, provider webhooks, partial refunds and reconciliation.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `payment_intents` | P0 | 16 | One payment orchestration attempt/context, created before or after order creation. |
| `payment_transactions` | P0 | 13 | Immutable money-movement/attempt ledger. |
| `payment_provider_events` | P0 | 18 | Inbound webhook inbox with replay protection. |
| `refunds` | P0 | 11 | Refund business object; supports partial/multiple refunds. |
| `refund_items` | P0 | 7 | How a refund maps to order lines/restocking. |

### 10.1 `payment_intents` — P0

One payment orchestration attempt/context. A checkout-origin intent may exist before an order; an order/admin-origin intent may link to an order at creation or later.

**Attribute count: 16**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `payment_intent_id` | `UUID` | PK | Intent id. |
| `store_id` | `UUID` | FK stores.store_id | Owning store and tenant boundary. |
| `checkout_id` | `UUID` | FK checkout_sessions.checkout_id NULL | Source checkout when intent is created before order. |
| `order_id` | `UUID` | FK orders.order_id NULL | Linked order when available. |
| `origin` | `VARCHAR(24)` | NOT NULL | CHECKOUT, ORDER, ADMIN. |
| `operation` | `VARCHAR(80)` | NOT NULL | Logical operation name used in request idempotency scope. |
| `provider` | `VARCHAR(40)` | NOT NULL | RAZORPAY, STRIPE, COD, MANUAL. |
| `provider_intent_id` | `VARCHAR(200)` | NULL | Gateway order/payment-intent id. |
| `method` | `VARCHAR(40)` | NULL | CARD, UPI, NETBANKING, COD. |
| `amount` | `NUMERIC(19,4)` | NOT NULL | Intended amount. |
| `currency` | `CHAR(3)` | NOT NULL | Currency. |
| `status` | `VARCHAR(32)` | NOT NULL | CREATED, PENDING_CUSTOMER_ACTION, PROCESSING, AUTHORIZED, CAPTURED, FAILED, CANCELLED, RECONCILIATION_REQUIRED. |
| `idempotency_key` | `VARCHAR(160)` | NOT NULL | Request retry key scoped to `(store_id, operation, key)`; provider idempotency is separate. |
| `expires_at` | `TIMESTAMPTZ` | NULL | Intent expiry. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,provider,provider_intent_id) WHERE provider_intent_id IS NOT NULL
- UNIQUE(store_id,operation,idempotency_key)
- CHECK ((origin = 'CHECKOUT' AND checkout_id IS NOT NULL) OR (origin = 'ORDER' AND order_id IS NOT NULL) OR (origin = 'ADMIN' AND (order_id IS NOT NULL OR checkout_id IS NOT NULL)))
- FOREIGN KEY (store_id,checkout_id) REFERENCES checkout_sessions(store_id,checkout_id)
- FOREIGN KEY (store_id,order_id) REFERENCES orders(store_id,order_id)
- UNIQUE(store_id,checkout_id,operation) WHERE origin = 'CHECKOUT' AND status IN ('CREATED','PENDING_CUSTOMER_ACTION','PROCESSING','AUTHORIZED','RECONCILIATION_REQUIRED')

**Recommended indexes**
- `order_id`
- `status`
- `provider`

### 10.2 `payment_transactions` — P0

Immutable money-movement/attempt ledger.

**Attribute count: 13**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `transaction_id` | `UUID` | PK | Transaction id. |
| `payment_intent_id` | `UUID` | FK payment_intents.payment_intent_id | Intent. |
| `provider` | `VARCHAR(40)` | NOT NULL | Provider resolved from the payment intent; repeated here for explicit reference identity. |
| `provider_transaction_id` | `VARCHAR(200)` | NULL | Gateway transaction/ref id. |
| `transaction_type` | `VARCHAR(24)` | NOT NULL | AUTHORIZE, CAPTURE, SALE, VOID, REFUND, COD_COLLECT. |
| `status` | `VARCHAR(24)` | NOT NULL | PENDING, SUCCESS, FAILED. |
| `amount` | `NUMERIC(19,4)` | NOT NULL | Transaction amount. |
| `currency` | `CHAR(3)` | NOT NULL | Currency. |
| `gateway_fee` | `NUMERIC(19,4)` | NULL | Provider fee if known. |
| `failure_code` | `VARCHAR(100)` | NULL | Normalized/provider failure code. |
| `failure_message` | `TEXT` | NULL | Failure detail. |
| `processed_at` | `TIMESTAMPTZ` | NULL | Provider processing time. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(provider,provider_transaction_id) WHERE provider_transaction_id IS NOT NULL
- `provider` is resolved from the linked Payment Intent and repeated here so provider transaction identity is not assumed globally unique.

**Recommended indexes**
- `payment_intent_id`
- `status`
- `transaction_type`
- `created_at`

### 10.3 `payment_provider_events` — P0

Inbound webhook inbox with replay protection.

**Attribute count: 18**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `provider_event_id` | `UUID` | PK | Internal event id. |
| `store_id` | `UUID` | FK stores.store_id | Trusted owning store resolved from integration context. |
| `provider` | `VARCHAR(40)` | NOT NULL | Gateway/provider. |
| `external_event_id` | `VARCHAR(200)` | NOT NULL | Provider event id, unique within store and provider. |
| `payment_intent_id` | `UUID` | NULL | Resolved local payment intent. |
| `order_id` | `UUID` | NULL | Resolved local order where available. |
| `event_type` | `VARCHAR(120)` | NOT NULL | payment.captured etc. |
| `signature_verified` | `BOOLEAN` | NOT NULL DEFAULT false | Security verification result. |
| `payload` | `JSONB` | NOT NULL | Raw/sanitized provider payload. |
| `processing_status` | `VARCHAR(24)` | NOT NULL | RECEIVED, PROCESSING, PROCESSED, FAILED_RETRYABLE, FAILED_TERMINAL, IGNORED. |
| `attempt_count` | `INT` | NOT NULL DEFAULT 0 | Processor attempts. |
| `last_error` | `TEXT` | NULL | Last processor error. |
| `claimed_at` | `TIMESTAMPTZ` | NULL | Worker claim time. |
| `claim_owner` | `VARCHAR(128)` | NULL | Worker holding the processing lease. |
| `lease_expires_at` | `TIMESTAMPTZ` | NULL | Safe reclaim deadline. |
| `received_at` | `TIMESTAMPTZ` | NOT NULL | Received time. |
| `processed_at` | `TIMESTAMPTZ` | NULL | Processed time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Last processing/lease update. |

**Key constraints**
- UNIQUE(store_id,provider,external_event_id)

**Recommended indexes**
- `provider`
- `processing_status`
- `received_at`

### 10.4 `refunds` — P0

Refund business object; supports partial/multiple refunds.

**Attribute count: 11**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `refund_id` | `UUID` | PK | Refund id. |
| `order_id` | `UUID` | FK orders.order_id | Order. |
| `payment_intent_id` | `UUID` | FK payment_intents.payment_intent_id NULL | Source payment. |
| `amount` | `NUMERIC(19,4)` | NOT NULL | Refund total. |
| `currency` | `CHAR(3)` | NOT NULL | Currency. |
| `reason` | `VARCHAR(255)` | NULL | Refund reason. |
| `status` | `VARCHAR(24)` | NOT NULL | REQUESTED, PROCESSING, SUCCEEDED, FAILED_RETRYABLE, FAILED_FINAL, RECONCILIATION_REQUIRED. |
| `provider_refund_id` | `VARCHAR(200)` | NULL | Gateway refund id. |
| `created_by` | `UUID` | FK users.user_id NULL | Staff actor. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `processed_at` | `TIMESTAMPTZ` | NULL | Completion time. |

**Key constraints**
- UNIQUE(provider_refund_id) WHERE provider_refund_id IS NOT NULL

**Recommended indexes**
- `order_id`
- `status`

### 10.5 `refund_items` — P0

How a refund maps to order lines/restocking.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `refund_item_id` | `UUID` | PK | Refund line id. |
| `refund_id` | `UUID` | FK refunds.refund_id | Refund. |
| `order_item_id` | `UUID` | FK order_items.order_item_id | Order item. |
| `quantity` | `INT` | NOT NULL | Refunded qty. |
| `amount` | `NUMERIC(19,4)` | NOT NULL | Refunded item amount. |
| `restock_type` | `VARCHAR(24)` | NULL | NO_RESTOCK, RETURN, CANCEL. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- CHECK quantity > 0

**Recommended indexes**
- `refund_id`
- `order_item_id`

### Relationships

orders 1─N payment_intents; payment_intents 1─N payment_transactions; provider webhooks first land in payment_provider_events; orders 1─N refunds; refunds 1─N refund_items.

### Generalized example

Example: Razorpay payment intent ₹4,998 → CAPTURE transaction succeeds → order becomes PAID. Later one item worth ₹1,999 is returned → separate refund + REFUND transaction, leaving order PARTIALLY_REFUNDED.

### Technical notes

- Never mark an order paid only because frontend says payment succeeded. Provider signature-verified server webhook/event is authoritative.

---

## 11. Fulfillment, Shipping, NDR & COD

Separates what must be fulfilled from individual carrier shipments so split shipments/multiple warehouses remain possible.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `fulfillments` | P0 | 7 | Operational fulfillment group for one order/location. |
| `fulfillment_items` | P0 | 5 | Order quantities assigned to a fulfillment. |
| `shipments` | P0 | 17 | Carrier package/tracking object attached to fulfillment. |
| `shipment_events` | P0 | 9 | Normalized tracking timeline from carrier webhooks/polls. |
| `ndr_events` | P1 | 9 | Non-delivery-report workflow. |
| `cod_remittances` | P1 | 12 | COD collection and courier settlement reconciliation. |

### 11.1 `fulfillments` — P0

Operational fulfillment group for one order/location.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `fulfillment_id` | `UUID` | PK | Fulfillment id. |
| `order_id` | `UUID` | FK orders.order_id | Order. |
| `location_id` | `UUID` | FK locations.location_id | Fulfillment location. |
| `status` | `VARCHAR(32)` | NOT NULL | OPEN, PACKING, READY, SHIPPED, COMPLETED, CANCELLED. |
| `created_by` | `UUID` | FK users.user_id NULL | Staff/system actor. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Recommended indexes**
- `order_id`
- `location_id`
- `status`

### 11.2 `fulfillment_items` — P0

Order quantities assigned to a fulfillment.

**Attribute count: 5**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `fulfillment_item_id` | `UUID` | PK | Fulfillment line id. |
| `fulfillment_id` | `UUID` | FK fulfillments.fulfillment_id | Fulfillment. |
| `order_item_id` | `UUID` | FK order_items.order_item_id | Order item. |
| `quantity` | `INT` | NOT NULL | Qty fulfilled from this location. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(fulfillment_id,order_item_id)
- CHECK quantity > 0

### 11.3 `shipments` — P0

Carrier package/tracking object attached to fulfillment.

**Attribute count: 17**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `shipment_id` | `UUID` | PK | Shipment id. |
| `fulfillment_id` | `UUID` | FK fulfillments.fulfillment_id | Fulfillment. |
| `provider` | `VARCHAR(50)` | NOT NULL | SHIPROCKET, DELHIVERY, MANUAL. |
| `external_shipment_id` | `VARCHAR(200)` | NULL | Provider shipment id. |
| `awb_code` | `VARCHAR(120)` | NULL | Tracking/AWB. |
| `carrier` | `VARCHAR(120)` | NULL | Courier company. |
| `service_name` | `VARCHAR(120)` | NULL | Service level. |
| `status` | `VARCHAR(40)` | NOT NULL | CREATING, CREATED, PICKUP_SCHEDULED, PICKED_UP, IN_TRANSIT, OUT_FOR_DELIVERY, DELIVERED, NDR, RTO, CANCELLED, LOST. |
| `tracking_url` | `TEXT` | NULL | Tracking URL. |
| `shipping_cost` | `NUMERIC(19,4)` | NULL | Merchant shipping cost. |
| `currency` | `CHAR(3)` | NULL | Cost currency. |
| `is_cod` | `BOOLEAN` | NOT NULL DEFAULT false | COD flag. |
| `estimated_delivery_at` | `TIMESTAMPTZ` | NULL | ETA. |
| `shipped_at` | `TIMESTAMPTZ` | NULL | Dispatch time. |
| `delivered_at` | `TIMESTAMPTZ` | NULL | Delivery time. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(provider,external_shipment_id) WHERE external_shipment_id IS NOT NULL
- UNIQUE(awb_code) WHERE awb_code IS NOT NULL

**Recommended indexes**
- `fulfillment_id`
- `status`
- `awb_code`

### 11.4 `shipment_events` — P0

Normalized tracking timeline from carrier webhooks/polls.

**Attribute count: 9**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `shipment_event_id` | `UUID` | PK | Tracking event id. |
| `shipment_id` | `UUID` | FK shipments.shipment_id | Shipment. |
| `external_event_id` | `VARCHAR(200)` | NULL | Provider event id if supplied. |
| `status` | `VARCHAR(40)` | NOT NULL | Normalized status. |
| `description` | `TEXT` | NULL | Carrier status text. |
| `location_text` | `VARCHAR(255)` | NULL | Scan location. |
| `occurred_at` | `TIMESTAMPTZ` | NOT NULL | Carrier event time. |
| `raw_payload` | `JSONB` | NOT NULL DEFAULT {} | Provider-specific event subset. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Ingest time. |

**Recommended indexes**
- `shipment_id`
- `occurred_at`
- `status`

### 11.5 `ndr_events` — P1

Non-delivery-report workflow.

**Attribute count: 9**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `ndr_id` | `UUID` | PK | NDR id. |
| `shipment_id` | `UUID` | FK shipments.shipment_id | Shipment. |
| `reason_code` | `VARCHAR(80)` | NULL | Normalized NDR reason. |
| `reason_text` | `TEXT` | NULL | Provider/customer reason. |
| `status` | `VARCHAR(24)` | NOT NULL | OPEN, ACTION_SUBMITTED, RESOLVED. RTO is an alternate terminal outcome, not an NDR status. |
| `action` | `VARCHAR(80)` | NULL | REATTEMPT, CHANGE_ADDRESS, RTO. |
| `action_payload` | `JSONB` | NOT NULL DEFAULT {} | Updated phone/address/date etc. |
| `raised_at` | `TIMESTAMPTZ` | NOT NULL | NDR raised. |
| `resolved_at` | `TIMESTAMPTZ` | NULL | Resolution time. |

**Recommended indexes**
- `shipment_id`
- `status`
- `raised_at`

### 11.6 `cod_remittances` — P1

COD collection and courier settlement reconciliation.

**Attribute count: 12**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `remittance_id` | `UUID` | PK | Remittance id. |
| `shipment_id` | `UUID` | FK shipments.shipment_id | Shipment. |
| `provider_reference` | `VARCHAR(160)` | NULL | Courier settlement ref. |
| `collected_amount` | `NUMERIC(19,4)` | NOT NULL | Cash collected from customer. |
| `shipping_charge` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Deducted shipping. |
| `cod_fee` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | COD fee. |
| `other_adjustments` | `NUMERIC(19,4)` | NOT NULL DEFAULT 0 | Other deductions/additions. |
| `net_payout` | `NUMERIC(19,4)` | NOT NULL | Expected/actual merchant payout. |
| `currency` | `CHAR(3)` | NOT NULL | Currency. |
| `status` | `VARCHAR(32)` | NOT NULL | EXPECTED, REPORTED, RECONCILED, SETTLED, RECONCILIATION_REQUIRED. |
| `settled_at` | `TIMESTAMPTZ` | NULL | Settlement time. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Recommended indexes**
- `shipment_id`
- `status`
- `settled_at`

### Relationships

orders 1─N fulfillments; fulfillments 1─N fulfillment_items and shipments; shipments 1─N shipment_events/NDR events/COD remittances.

### Generalized example

Example: Order has shirt + perfume. Shirt ships from Noida and perfume from Mumbai, so one order can have 2 fulfillments and 2 AWBs. This is why `orders → shipments` should not be modeled as strict 1:1.

---

## 12. Returns & Reverse Logistics

Controls return request, item approval, receipt, restocking and downstream refund.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `returns` | P1 | 12 | Return/RMA header. |
| `return_items` | P1 | 10 | Line-level return quantity, condition and disposition. |

### 12.1 `returns` — P1

Return/RMA header.

**Attribute count: 12**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `return_id` | `UUID` | PK | Return id. |
| `order_id` | `UUID` | FK orders.order_id | Original order. |
| `customer_id` | `UUID` | FK customers.customer_id NULL | Requesting customer. |
| `status` | `VARCHAR(32)` | NOT NULL | REQUESTED, APPROVED, REJECTED, IN_TRANSIT, RECEIVED, REFUND_PENDING, COMPLETED, CANCELLED. |
| `reason_summary` | `VARCHAR(255)` | NULL | High-level reason. |
| `return_method` | `VARCHAR(32)` | NULL | PICKUP, SELF_SHIP, IN_STORE. |
| `reverse_shipment_id` | `UUID` | FK shipments.shipment_id NULL | Optional reverse logistics shipment. |
| `requested_at` | `TIMESTAMPTZ` | NOT NULL | Request time. |
| `approved_at` | `TIMESTAMPTZ` | NULL | Approval time. |
| `received_at` | `TIMESTAMPTZ` | NULL | Warehouse receive time. |
| `completed_at` | `TIMESTAMPTZ` | NULL | Completion time. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Recommended indexes**
- `order_id`
- `status`
- `requested_at`

### 12.2 `return_items` — P1

Line-level return quantity, condition and disposition.

**Attribute count: 10**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `return_item_id` | `UUID` | PK | Return line id. |
| `return_id` | `UUID` | FK returns.return_id | Return. |
| `order_item_id` | `UUID` | FK order_items.order_item_id | Purchased item. |
| `quantity` | `INT` | NOT NULL | Return qty. |
| `reason_code` | `VARCHAR(80)` | NULL | SIZE_ISSUE, DAMAGED, WRONG_ITEM, etc. |
| `condition` | `VARCHAR(32)` | NULL | NEW, OPENED, DAMAGED. |
| `disposition` | `VARCHAR(32)` | NULL | RESTOCK, DAMAGED, DISCARD, INSPECT. |
| `refund_amount` | `NUMERIC(19,4)` | NULL | Expected/approved item refund. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- CHECK quantity > 0

**Recommended indexes**
- `return_id`
- `order_item_id`

### Relationships

orders 1─N returns; returns 1─N return_items; return completion can create refunds and inventory movements.

### Generalized example

Example: Customer returns 1 of 2 T-shirts due to size. Warehouse receives it in NEW condition → disposition RESTOCK → inventory +1 movement → ₹999 partial refund.

---

## 13. CMS, Navigation & SEO

Provides client-editable storefront content without coupling frontend layout to database structure.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `pages` | P1 | 10 | Generic content pages such as About, Contact, Shipping Policy. |
| `blog_categories` | P1 | 5 | Blog grouping. |
| `blog_posts` | P1 | 14 | SEO/content marketing article. |
| `navigation_menus` | P1 | 6 | Named menus consumed by any custom frontend. |
| `navigation_items` | P1 | 10 | Tree items for menus. |
| `seo_metadata` | P1 | 11 | Reusable SEO metadata for product/collection/page/blog resources. |
| `redirects` | P1 | 7 | Permanent/temporary URL redirects for SEO migrations. |

### 13.1 `pages` — P1

Generic content pages such as About, Contact, Shipping Policy.

**Attribute count: 10**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `page_id` | `UUID` | PK | Page id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `title` | `VARCHAR(255)` | NOT NULL | Page title. |
| `slug` | `VARCHAR(255)` | NOT NULL | URL handle. |
| `content_json` | `JSONB` | NOT NULL DEFAULT {} | Structured blocks/content portable across frontends. |
| `status` | `VARCHAR(24)` | NOT NULL | DRAFT, PUBLISHED. |
| `version` | `BIGINT` | NOT NULL DEFAULT 1 | Optimistic concurrency version for admin edits. |
| `published_at` | `TIMESTAMPTZ` | NULL | Publish time. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,slug)

**Recommended indexes**
- `store_id`
- `status`

### 13.2 `blog_categories` — P1

Blog grouping.

**Attribute count: 5**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `blog_category_id` | `UUID` | PK | Category id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `name` | `VARCHAR(160)` | NOT NULL | Category title. |
| `slug` | `VARCHAR(180)` | NOT NULL | URL handle. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(store_id,slug)

### 13.3 `blog_posts` — P1

SEO/content marketing article.

**Attribute count: 13**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `blog_post_id` | `UUID` | PK | Post id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `blog_category_id` | `UUID` | FK blog_categories.blog_category_id NULL | Category. |
| `title` | `VARCHAR(255)` | NOT NULL | Post title. |
| `slug` | `VARCHAR(255)` | NOT NULL | URL handle. |
| `excerpt` | `TEXT` | NULL | Summary. |
| `content_json` | `JSONB` | NOT NULL DEFAULT {} | Structured article blocks. |
| `featured_media_id` | `UUID` | FK media_assets.media_id NULL | Hero image. |
| `author_name` | `VARCHAR(160)` | NULL | Display author. |
| `status` | `VARCHAR(24)` | NOT NULL | DRAFT, PUBLISHED, ARCHIVED. |
| `version` | `BIGINT` | NOT NULL DEFAULT 1 | Optimistic concurrency version for admin edits. |
| `published_at` | `TIMESTAMPTZ` | NULL | Publish time. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,slug)

**Recommended indexes**
- `store_id`
- `status`
- `published_at`

### 13.4 `navigation_menus` — P1

Named menus consumed by any custom frontend.

**Attribute count: 6**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `menu_id` | `UUID` | PK | Menu id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `name` | `VARCHAR(100)` | NOT NULL | Header, Footer. |
| `handle` | `VARCHAR(100)` | NOT NULL | header-main. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,handle)

### 13.5 `navigation_items` — P1

Tree items for menus.

**Attribute count: 10**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `menu_item_id` | `UUID` | PK | Menu item id. |
| `menu_id` | `UUID` | FK navigation_menus.menu_id | Menu. |
| `parent_item_id` | `UUID` | FK navigation_items.menu_item_id NULL | Parent for dropdown/tree. |
| `label` | `VARCHAR(160)` | NOT NULL | Display label. |
| `link_type` | `VARCHAR(32)` | NOT NULL | URL, PRODUCT, COLLECTION, PAGE. |
| `resource_id` | `UUID` | NULL | Linked internal resource. |
| `url` | `TEXT` | NULL | External/custom URL. |
| `position` | `INT` | NOT NULL DEFAULT 0 | Ordering. |
| `is_visible` | `BOOLEAN` | NOT NULL DEFAULT true | Visibility. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Recommended indexes**
- `menu_id`
- `parent_item_id`
- `position`

### 13.6 `seo_metadata` — P1

Reusable SEO metadata for product/collection/page/blog resources.

**Attribute count: 11**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `seo_id` | `UUID` | PK | SEO id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `resource_type` | `VARCHAR(40)` | NOT NULL | PRODUCT, COLLECTION, PAGE, BLOG_POST. |
| `resource_id` | `UUID` | NOT NULL | Application-enforced resource reference. |
| `meta_title` | `VARCHAR(255)` | NULL | SEO title. |
| `meta_description` | `VARCHAR(320)` | NULL | Meta description. |
| `canonical_url` | `TEXT` | NULL | Canonical override. |
| `robots` | `VARCHAR(80)` | NULL | index/follow directives. |
| `og_media_id` | `UUID` | FK media_assets.media_id NULL | Social preview media. |
| `structured_data` | `JSONB` | NOT NULL DEFAULT {} | Additional JSON-LD data controlled by app. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,resource_type,resource_id)

**Recommended indexes**
- `resource_type`
- `resource_id`

### 13.7 `redirects` — P1

Permanent/temporary URL redirects for SEO migrations.

**Attribute count: 7**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `redirect_id` | `UUID` | PK | Redirect id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `source_path` | `VARCHAR(1024)` | NOT NULL | Old path. |
| `target_url` | `TEXT` | NOT NULL | Destination. |
| `status_code` | `SMALLINT` | NOT NULL DEFAULT 301 | 301/302 etc. |
| `is_active` | `BOOLEAN` | NOT NULL DEFAULT true | Enabled flag. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Key constraints**
- UNIQUE(store_id,source_path)

**Recommended indexes**
- `store_id`
- `is_active`

### Relationships

stores own pages/blog/navigation/SEO/redirects; navigation_items self-reference for dropdown trees; SEO metadata points to catalog/content resources by resource_type + resource_id.

### Generalized example

Example: Client frontend can be completely redesigned next year, but `/collections/summer`, Header menu, About page and blog content continue coming from the same backend APIs.

---

## 14. Notifications & Customer Communication

Template-driven asynchronous transactional messages with delivery logs.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `notification_templates` | P1 | 9 | Editable channel template definitions. |
| `notification_deliveries` | P1 | 17 | Per-message delivery/audit log. |

### 14.1 `notification_templates` — P1

Editable channel template definitions.

**Attribute count: 9**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `template_id` | `UUID` | PK | Template id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `template_key` | `VARCHAR(120)` | NOT NULL | Stable API lookup key. |
| `event_type` | `VARCHAR(100)` | NOT NULL | ORDER_CREATED, PAYMENT_SUCCESS, SHIPPED. |
| `channel` | `VARCHAR(24)` | NOT NULL | EMAIL, SMS, WHATSAPP. |
| `subject_template` | `TEXT` | NULL | Email subject template. |
| `body_template` | `TEXT` | NOT NULL | Provider-agnostic template body. |
| `variables_schema` | `JSONB` | NOT NULL DEFAULT '{}'::jsonb | Allowed render variables and validation metadata. |
| `provider_template_id` | `VARCHAR(160)` | NULL | WhatsApp/SMS provider template id. |
| `is_active` | `BOOLEAN` | NOT NULL DEFAULT true | Enabled flag. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,template_key)
- UNIQUE(store_id,event_type,channel)

### 14.2 `notification_deliveries` — P1

Per-message delivery/audit log.

**Attribute count: 17**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `delivery_id` | `UUID` | PK | Delivery id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `event_type` | `VARCHAR(100)` | NOT NULL | Trigger event. |
| `channel` | `VARCHAR(24)` | NOT NULL | EMAIL/SMS/WHATSAPP. |
| `source_event_id` | `UUID` | NULL | Canonical domain event that triggered this delivery. |
| `dedupe_key` | `VARCHAR(255)` | NOT NULL | Deterministic logical notification identity; explicit resends use a new key. |
| `recipient` | `VARCHAR(255)` | NOT NULL | Masked/protected recipient as appropriate. |
| `provider` | `VARCHAR(80)` | NULL | SES, SendGrid, MSG91, etc. |
| `provider_message_id` | `VARCHAR(200)` | NULL | Provider reference. |
| `status` | `VARCHAR(24)` | NOT NULL | QUEUED, SENT, DELIVERED, FAILED. |
| `reference_type` | `VARCHAR(40)` | NULL | ORDER, SHIPMENT, RETURN. |
| `reference_id` | `UUID` | NULL | Related object. |
| `attempt_count` | `INT` | NOT NULL DEFAULT 0 | Send attempts. |
| `last_error` | `TEXT` | NULL | Last failure. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `sent_at` | `TIMESTAMPTZ` | NULL | Send time. |
| `delivered_at` | `TIMESTAMPTZ` | NULL | Delivery time. |

**Recommended indexes**
- `store_id`
- `status`
- UNIQUE(store_id,dedupe_key)
- `reference_type`
- `reference_id`

### Relationships

outbox event → notification worker → notification_templates → notification_deliveries. Transactional HTTP request does not wait for email/SMS/WhatsApp sending.

### Generalized example

Example: Payment capture transaction commits `payment.captured` event. Worker sends invoice email + WhatsApp confirmation and records provider IDs/retries separately.

---

## 15. Integrations, Apps & Webhooks

Keeps payment/shipping/analytics/ERP credentials and outbound subscriptions isolated from commerce tables.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `integrations` | P1 | 10 | Installed external service configuration and non-secret health metadata. |
| `integration_secrets` | P1 | 8 | Encrypted write-only merchant integration secrets. |
| `webhook_subscriptions` | P2 | 9 | Outbound event subscriptions for custom apps/integrations. |
| `webhook_deliveries` | P2 | 11 | Attempt/retry log for outbound webhooks. |

### 15.1 `integrations` — P1

Installed external service configuration.

**Attribute count: 10**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `integration_id` | `UUID` | PK | Integration id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `integration_type` | `VARCHAR(40)` | NOT NULL | PAYMENT, SHIPPING, CRM, ANALYTICS, ERP. |
| `provider` | `VARCHAR(80)` | NOT NULL | RAZORPAY, SHIPROCKET, GA4, etc. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE, DISABLED, ERROR. |
| `health_status` | `VARCHAR(24)` | NOT NULL | UNKNOWN, CONNECTED, AUTH_FAILED, UNREACHABLE, MISCONFIGURED, DEGRADED, NOT_SUPPORTED. |
| `config` | `JSONB` | NOT NULL DEFAULT {} | Non-secret configuration. |
| `last_checked_at` | `TIMESTAMPTZ` | NULL | Last completed read-only provider health check. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,integration_type,provider)

**Recommended indexes**
- `store_id`
- `integration_type`
- `status`

### 15.2 `integration_secrets` — P1

Encrypted write-only merchant integration secrets. The database stores ciphertext only; the master key is supplied through `INTEGRATION_MASTER_KEY` outside the database.

**Attribute count: 8**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `integration_secret_id` | `UUID` | PK | Secret record id. |
| `integration_id` | `UUID` | FK integrations.integration_id | Owning integration. |
| `secret_name` | `VARCHAR(100)` | NOT NULL | Provider-defined logical secret name. |
| `ciphertext` | `BYTEA` | NOT NULL | AEAD-encrypted secret value. |
| `nonce` | `BYTEA` | NOT NULL | Unique per encryption operation. |
| `key_version` | `SMALLINT` | NOT NULL DEFAULT 1 | Supports controlled key rotation. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Last replacement time. |

**Key constraints**
- UNIQUE(integration_id,secret_name)
- FK integration_id → integrations.integration_id

**Technical notes**
- Use an authenticated-encryption construction (AEAD) with unique nonces and AAD containing store/integration/secret identity and key version.
- Plaintext exists only transiently during the provider call; never return it through APIs, logs, audit records, metrics, exports or generic JSON.
- `INTEGRATION_MASTER_KEY` is never stored in PostgreSQL.

### 15.3 `webhook_subscriptions` — P2

Outbound event subscriptions for custom apps/integrations.

**Attribute count: 9**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `subscription_id` | `UUID` | PK | Subscription id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `integration_id` | `UUID` | FK integrations.integration_id NULL | Optional installed integration. |
| `event_type` | `VARCHAR(120)` | NOT NULL | order.created, product.updated. |
| `endpoint_url` | `TEXT` | NOT NULL | HTTPS callback URL. |
| `api_version` | `VARCHAR(20)` | NOT NULL | Contract version. |
| `secret_ref` | `VARCHAR(255)` | NULL | Signing secret reference. |
| `status` | `VARCHAR(24)` | NOT NULL | ACTIVE, PAUSED, DISABLED. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |

**Recommended indexes**
- `store_id`
- `event_type`
- `status`

### 15.4 `webhook_deliveries` — P2

Attempt/retry log for outbound webhooks.

**Attribute count: 11**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `webhook_delivery_id` | `UUID` | PK | Delivery id. |
| `subscription_id` | `UUID` | FK webhook_subscriptions.subscription_id | Subscription. |
| `outbox_event_id` | `UUID` | NULL | Source event. |
| `attempt_no` | `INT` | NOT NULL | Attempt number. |
| `request_id` | `VARCHAR(64)` | NOT NULL | Opaque trace/idempotency request id. |
| `http_status` | `INT` | NULL | Receiver response code. |
| `status` | `VARCHAR(24)` | NOT NULL | PENDING, SUCCESS, RETRY, DEAD. |
| `next_retry_at` | `TIMESTAMPTZ` | NULL | Backoff schedule. |
| `last_error` | `TEXT` | NULL | Error. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `completed_at` | `TIMESTAMPTZ` | NULL | Completion time. |

**Recommended indexes**
- `subscription_id`
- `status`
- `next_retry_at`

### Relationships

stores 1─N integrations; integrations 1─N integration_secrets; integrations may own webhook subscriptions; each subscription receives many deliveries sourced from outbox events.

### Generalized example

Example: Client wants ERP sync later. Install ERP integration without touching orders/products schema; encrypt its write-only credentials in `integration_secrets`, then subscribe it to `order.created` and `inventory.adjusted` events.

---

## 16. Reliability, Audit, Outbox, Idempotency & Bulk Jobs

Cross-cutting infrastructure that prevents duplicate side effects and makes the backend operable at production scale.

### Module table inventory

| Table | Priority | Attributes | Main responsibility |
|---|---|---:|---|
| `idempotency_records` | P0 | 13 | Atomic request deduplication for checkout/payment/admin writes. |
| `outbox_events` | P0 | 13 | Transactional event outbox written in same DB transaction as business change. |
| `audit_logs` | P0 | 12 | Append-only staff/system audit trail for sensitive actions. |
| `bulk_jobs` | P1 | 14 | Async import/export or mass-update job header. |
| `bulk_job_items` | P1 | 10 | Optional row-level result/error records for a bulk job. |

### 16.1 `idempotency_records` — P0

Atomic request deduplication for checkout/payment/admin writes.

**Attribute count: 16**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `idempotency_id` | `UUID` | PK | Record id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `idempotency_key` | `VARCHAR(160)` | NOT NULL | Client-provided/generated key. |
| `operation` | `VARCHAR(100)` | NOT NULL | checkout.complete, refund.create, etc. |
| `request_hash` | `CHAR(64)` | NOT NULL | Hash of canonical request body. |
| `status` | `VARCHAR(24)` | NOT NULL | IN_PROGRESS, SUCCEEDED, FAILED_RETRYABLE, FAILED_FINAL. |
| `resource_type` | `VARCHAR(40)` | NULL | Created resource type. |
| `resource_id` | `UUID` | NULL | Created resource id. |
| `response_status` | `INT` | NULL | Saved HTTP response status. |
| `response_body` | `JSONB` | NULL | Replayable response subset. |
| `attempt_count` | `INT` | NOT NULL DEFAULT 0 | Execution attempts. |
| `lease_expires_at` | `TIMESTAMPTZ` | NULL | Claim lease expiry for stale recovery. |
| `last_error_code` | `VARCHAR(100)` | NULL | Stable normalized failure code. |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | Retention expiry. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated time. |

**Key constraints**
- UNIQUE(store_id,operation,idempotency_key)

Same key plus the same semantic request hash replays or waits on the existing
result. A different hash returns `IDEMPOTENCY_KEY_REUSED`. Claims are atomic;
expired `IN_PROGRESS` records may be reclaimed under a bounded lease policy.

**Recommended indexes**
- `status`
- `expires_at`

### 16.2 `outbox_events` — P0

Transactional event outbox written in same DB transaction as business change.

**Attribute count: 17**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `event_id` | `UUID` | PK | Event id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `aggregate_type` | `VARCHAR(60)` | NOT NULL | ORDER, PAYMENT, PRODUCT. |
| `aggregate_id` | `UUID` | NOT NULL | Business object id. |
| `event_type` | `VARCHAR(120)` | NOT NULL | order.created etc. |
| `event_version` | `SMALLINT` | NOT NULL DEFAULT 1 | Payload contract version. |
| `payload` | `JSONB` | NOT NULL | Event data. |
| `status` | `VARCHAR(24)` | NOT NULL DEFAULT PENDING | PENDING, PROCESSING, PUBLISHED, DEAD. |
| `claimed_at` | `TIMESTAMPTZ` | NULL | Time the worker claimed the event. |
| `claim_owner` | `VARCHAR(128)` | NULL | Worker identity holding the lease. |
| `lease_expires_at` | `TIMESTAMPTZ` | NULL | Reclaim deadline after worker failure. |
| `available_at` | `TIMESTAMPTZ` | NOT NULL | Earliest process time. |
| `attempt_count` | `INT` | NOT NULL DEFAULT 0 | Retries. |
| `last_error` | `TEXT` | NULL | Last failure. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Event time. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Last lifecycle/lease update. |
| `published_at` | `TIMESTAMPTZ` | NULL | Successful dispatch time. |

**Recommended indexes**
- `status`
- `available_at`
- `store_id`
- `aggregate_type`
- `aggregate_id`

### 16.3 `audit_logs` — P0

Append-only staff/system audit trail for sensitive actions.

**Attribute count: 12**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `audit_id` | `UUID` | PK | Audit id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `actor_type` | `VARCHAR(24)` | NOT NULL | STAFF, SYSTEM, API. |
| `actor_id` | `UUID` | NULL | Staff/API identity. |
| `action` | `VARCHAR(120)` | NOT NULL | product.update, refund.create. |
| `entity_type` | `VARCHAR(60)` | NOT NULL | Target resource. |
| `entity_id` | `UUID` | NULL | Target id. |
| `before_data` | `JSONB` | NULL | Sensitive fields redacted. |
| `after_data` | `JSONB` | NULL | Sensitive fields redacted. |
| `request_id` | `VARCHAR(64)` | NULL | Opaque trace id such as `req_01J...`. |
| `ip_address` | `INET` | NULL | Actor IP. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Action time. |

**Recommended indexes**
- `store_id`
- `entity_type`
- `entity_id`
- `actor_id`
- `created_at`

### 16.4 `bulk_jobs` — P1

Async import/export or mass-update job header.

**Attribute count: 15**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `bulk_job_id` | `UUID` | PK | Bulk job id. |
| `store_id` | `UUID` | FK stores.store_id | Store. |
| `job_type` | `VARCHAR(60)` | NOT NULL | Operation class: IMPORT, EXPORT, UPDATE. |
| `resource_type` | `VARCHAR(60)` | NOT NULL | PRODUCT, INVENTORY, ORDER, CUSTOMER. |
| `status` | `VARCHAR(24)` | NOT NULL | QUEUED, PROCESSING, COMPLETED, PARTIAL, FAILED, CANCELLED. |
| `input_file_key` | `VARCHAR(512)` | NULL | Object storage input file. |
| `output_file_key` | `VARCHAR(512)` | NULL | Generated result/export file. |
| `total_rows` | `INT` | NOT NULL DEFAULT 0 | Total work items. |
| `processed_rows` | `INT` | NOT NULL DEFAULT 0 | Processed count. |
| `success_rows` | `INT` | NOT NULL DEFAULT 0 | Succeeded count. |
| `failed_rows` | `INT` | NOT NULL DEFAULT 0 | Failed count. |
| `created_by` | `UUID` | FK users.user_id NULL | Staff actor. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `started_at` | `TIMESTAMPTZ` | NULL | Start time. |
| `completed_at` | `TIMESTAMPTZ` | NULL | Completion time. |

**Recommended indexes**
- `store_id`
- `status`
- `job_type`
- `resource_type`
- `created_at`

### 16.5 `bulk_job_items` — P1

Optional row-level result/error records for a bulk job.

**Attribute count: 10**

| Attribute | Data type | Constraint | Use |
|---|---|---|---|
| `bulk_job_item_id` | `UUID` | PK | Job item id. |
| `bulk_job_id` | `UUID` | FK bulk_jobs.bulk_job_id | Bulk job. |
| `row_number` | `INT` | NOT NULL | Source row number. |
| `idempotency_key` | `VARCHAR(160)` | NULL | Per-row retry safety. |
| `status` | `VARCHAR(24)` | NOT NULL | PENDING, SUCCESS, FAILED, SKIPPED. |
| `resource_id` | `UUID` | NULL | Affected/created object. |
| `error_code` | `VARCHAR(100)` | NULL | Normalized error. |
| `error_message` | `TEXT` | NULL | Human readable error. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Created time. |
| `processed_at` | `TIMESTAMPTZ` | NULL | Processing time. |

**Key constraints**
- UNIQUE(bulk_job_id,row_number)

**Recommended indexes**
- `bulk_job_id`
- `status`

### Relationships

Business transaction writes domain row + outbox_events atomically. Workers process outbox asynchronously. Idempotency records protect writes/retries. Audit logs preserve sensitive admin history. Bulk jobs move large work off HTTP request path.

### Generalized example

Example: Admin imports 20,000 SKUs. API creates one bulk job and returns 202. Worker processes rows with per-row idempotency, records 19,850 success / 150 failure, and generates an error file—no 10-minute HTTP request.

---

## 17. Cross-Module Relationship Map

```text
STORE
├── Staff / RBAC
├── Customers
├── Sales Channels
├── Catalog
│   └── Product
│       ├── Options → Values
│       ├── Variants → Inventory Item
│       ├── Media
│       ├── Collections
│       └── Metafields
├── Inventory
│   ├── Locations
│   ├── Levels
│   ├── Reservations
│   └── Movements
├── Pricing
│   └── Market → Catalog → Price List → Variant Price
├── Discounts
├── Cart
│   └── Checkout
│       ├── Priced Lines
│       ├── Address Snapshot
│       ├── Shipping Rate
│       └── Inventory Reservations
├── Order
│   ├── Order Items
│   ├── Address Snapshots
│   ├── Tax/Discount Allocations
│   ├── Payment Intents → Transactions → Refunds
│   ├── Fulfillments → Shipments → Tracking/NDR/COD
│   └── Returns → Return Items
├── CMS / SEO
├── Integrations / Webhooks
└── System Reliability
    ├── Idempotency
    ├── Outbox
    ├── Audit Logs
    └── Bulk Jobs
```

---

## 18. Critical Transaction Flows

### 18.1 Checkout → Payment → Order

```text
Cart
  ↓ validate current variants/prices
Checkout Session
  ↓ calculate discounts + tax + shipping
Atomic Inventory Reservation
  ↓
Create/Update Payment Intent
  ↓ provider checkout
Verified Provider Event
  ↓ same DB transaction where applicable
Payment Transaction = SUCCESS
Order Financial Status = PAID
Consume Reservation
Write Outbox Events
  ↓ async
Fulfillment / Email / WhatsApp / Analytics / Webhooks
```

**Required safety rules:**

- Client totals are never authoritative.
- Idempotency key is atomically claimed before side effects.
- Inventory reservation is conditional/atomic in PostgreSQL.
- Provider webhook signature must be verified.
- `(store_id, provider, external_event_id)` must be unique.
- Payment HTTP calls remain outside long DB transactions.
- Order creation/payment transitions and outbox events must be committed consistently.

### 18.2 Cancellation

```text
Order OPEN + not fulfilled → Cancel → Release/Reverse inventory reservation → Void/Refund if needed → status history + outbox
```

### 18.3 Return

```text
Delivered Order → Return Request → Approval → Reverse Shipment → Receive + Inspect → Inventory Disposition → Refund → Close Return
```

---

## 19. Indexing & PostgreSQL Rules

1. Index every foreign key used in joins/filtering. PostgreSQL does not automatically index FK columns.
2. Use composite indexes matching store-scoped admin queries, e.g. `(store_id, status, created_at DESC)`.
3. Use partial indexes for hot states where useful, e.g. active reservations or pending outbox events.
4. Prefer cursor/keyset pagination for very large order/product tables; avoid deep OFFSET pagination.
5. Use GIN indexes only on JSONB fields with proven query patterns; do not GIN-index every JSONB column by default.
6. Use `CITEXT` (extension) or normalized lowercase columns for case-insensitive email/code uniqueness.
7. Financial and ledger tables should not be soft-deleted. Use reversal/status records.
8. Consider table partitioning only after measured volume justifies it (likely audit/outbox/provider events before core orders).

### Suggested high-value indexes

```sql
CREATE INDEX idx_orders_store_status_created
  ON orders (store_id, order_status, created_at DESC);

CREATE INDEX idx_orders_customer_created
  ON orders (customer_id, created_at DESC);

CREATE INDEX idx_products_store_status_created
  ON products (store_id, status, created_at DESC);

CREATE INDEX idx_inventory_res_active_expiry
  ON inventory_reservations (expires_at)
  WHERE status = 'ACTIVE';

CREATE INDEX idx_outbox_pending_available
  ON outbox_events (available_at, created_at)
  WHERE status = 'PENDING';

CREATE INDEX idx_provider_events_unprocessed
  ON payment_provider_events (received_at)
  WHERE processing_status IN ('RECEIVED','FAILED_RETRYABLE');
```

---

## 20. Data Integrity Rules

| Rule | Implementation direction |
|---|---|
| No money FLOAT | NUMERIC(19,4) everywhere |
| No duplicate provider event processing | UNIQUE(store_id, provider, external_event_id) |
| No duplicate checkout side effect | UNIQUE(store_id, operation, idempotency key) + atomic claim |
| No overselling | conditional inventory UPDATE / row locking strategy + reservation ledger |
| No mutable historical address | order_addresses snapshot |
| No mutable historical price | checkout_lines + order_items snapshot |
| No silent stock edits | inventory_movements required for adjustments |
| No lost async event after commit | outbox written in same business transaction |
| No plaintext secrets | Bootstrap secrets stay in VPS env/Docker secrets/external manager; merchant secrets use AEAD ciphertext in `integration_secrets` with `INTEGRATION_MASTER_KEY` outside PostgreSQL |
| No admin action without trace | request_id + audit log for sensitive writes |

---

## 21. Implementation Phases for LinkUp Web Reusable Commerce Engine

### Phase A — Core Store Engine (implement first)

`stores`, `store_settings`, `sales_channels`, `users`, RBAC, `customers`, catalog tables, `locations`, core inventory tables, `carts`, checkout tables, orders, payment tables, fulfillment, `idempotency_records`, `outbox_events`, `audit_logs`.

**Result:** reusable backend that can safely power most D2C/standard e-commerce clients.

### Phase B — Client-ready Standard Features

Collections, discount engine, returns/refunds, CMS/blog/navigation/SEO, notifications, Shiprocket/Delhivery adapters, COD reconciliation, bulk CSV jobs.

**Result:** LinkUp Web can package a Shopify-like feature set while still delivering a fully custom frontend and separate deployment.

### Phase C — Advanced / enterprise add-ons

Markets/catalogs/price lists, advanced metafields, outbound app webhooks, deeper ERP integration, multi-location transfers, B2B pricing and advanced channel integrations.

**Result:** bigger clients can be upgraded without changing the core commerce data model.

---

## 22. What Should NOT Be Built Into the DB

- Raw images/videos: store in S3/R2/GCS/ImageKit-compatible object storage; DB stores metadata and keys/URLs.
- Full observability logs: use structured logs/OpenTelemetry; DB audit logs are business/security audit only.
- Search index: PostgreSQL first; use OpenSearch/Elasticsearch/Typesense only when real scale/search requirements justify it.
- Analytics event firehose: send events to analytics stack/warehouse instead of bloating transactional PostgreSQL.
- Bootstrap/API deployment secrets: keep them in the client VPS environment, Docker/Kubernetes secrets, or an external secret manager; merchant integration secrets use encrypted `integration_secrets` ciphertext with `INTEGRATION_MASTER_KEY` outside PostgreSQL.
- Frontend theme implementation details: keep frontend blocks/config separately; the commerce schema should remain brand/UI agnostic.

---

## 23. Final Recommendation for LinkUp Web

The reusable product should be treated as a **Commerce Engine**, not a copied Shopify database. The strong business model is:

```text
One hardened LinkUp Commerce backend codebase
          +
repeatable infrastructure template
          +
client-specific environment / database / VPS
          +
client-specific integrations and configuration
          +
fully custom Next.js storefront / UI / brand experience
```

This gives LinkUp Web speed of delivery without forcing every client into the same visual storefront. It also isolates clients operationally while allowing the backend team to improve one shared product codebase.

For the initial architecture, keep `store_id` and deployment ownership boundaries, but **do not build platform billing, tenant provisioning, app marketplace or complex organization hierarchy until LinkUp intentionally decides to become a SaaS platform.** Each client receives an isolated VPS/database and custom frontend backed by the reusable commerce engine; custom-domain DNS, reverse proxy and TLS remain deployment concerns.

---

## 24. Shopify-Inspired Design References (Conceptual Only)

- Product → ProductVariant → Inventory Item style separation.
- Inventory tracked per location with quantity states.
- Catalog/price-list abstraction for contextual pricing.
- Idempotent write operations and retry safety.
- Event/webhook-driven integration model.

Reference documentation reviewed while validating these concepts:

- Shopify ProductVariant (Admin GraphQL): https://shopify.dev/docs/api/admin-graphql/latest/objects/productvariant
- Shopify Catalogs: https://shopify.dev/docs/apps/build/markets/build-catalog
- Shopify PriceList: https://shopify.dev/docs/api/admin-graphql/latest/objects/pricelist
- Shopify Idempotency guidance: https://shopify.dev/docs/api/usage/implementing-idempotency

> These concepts are used as industry references. LinkUp Commerce remains an independently designed backend for the LinkUp Web delivery model.

---

**End of DB Schema Architecture v1**
