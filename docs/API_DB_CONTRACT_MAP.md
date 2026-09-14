# LinkUp API to database contract map

This is the explicit Release 1 vocabulary map. The OpenAPI contract is transport authority; DB names remain persistence authority.

## Wave A deterministic mapping freeze

In addition to the table below: store `country -> stores.country_code`; collection
`handle/description -> slug/description_html`; variant dimensions ->
`length/width/height/dimension_unit`; variant status -> `is_active`; market primary
-> `is_primary`; cart buyer -> `customer_id/email/phone`; notification
subject/body/status -> `subject_template/body_template/is_active`; integration
type/public config/secrets -> `integrations` + `integration_secrets`; webhook
topic/url/secret -> `event_type/endpoint_url/secret_ref`; role assignment ->
`staff_member_roles.role_id`; and effective permission -> same-store
`roles/role_permissions/permissions`. Catalog context is derived from market/channel
context, not duplicated persistence vocabulary. See the Wave A decision register
for client/server/write-only ownership.

| API DTO | DB field | Contract rule |
|---|---|---|
| `handle` | `slug` | Store-scoped URL handle; no undocumented alias. |
| product `description` | `description_html` | Sanitized API content is persisted as HTML. |
| variant `price` | `base_price` | HTTP money is a decimal string; server resolves it. |
| line `properties` | `properties` | Same term through cart, checkout and order snapshots; `attributes` is not accepted. |
| payment presentation `payment_status` | order `financial_status` | Storefront status is a sanitized projection of the financial ledger. |
| storefront `currency` | store `default_currency` | Currency comes from store configuration. |
| `order_number` | `order_number` | BIGINT merchant sequence, JSON integer. |
| `order_name` / order reference | `order_name` | Human-readable display reference such as `ORD-1042`. |
| `checkout_token` | `checkout_sessions.checkout_token` | Opaque unique VARCHAR(128) authorization material. |
| variant `width` | `product_variants.width` | Provider adapters may translate to provider `breadth`; internal name is `width`. |
| consent `state` | `customer_consents.state` | `SUBSCRIBED` or `UNSUBSCRIBED`; separate from customer status. |
| admin customer `note` | `customer_notes.body` | A note is appended with the authenticated `staff_member_id`; it is not a mutable customer profile field. |
| inventory movement `actor_user_id` | `inventory_movements.actor_user_id` | Identity actor, distinct from staff membership; null only for a documented system action. |
| inventory movement `reference_type` / `reference_id` | `inventory_movements.reference_type` / `reference_id` | Both persist the business cause of an append-only movement. |
| location `fulfills_online_orders` / `priority` | `locations.fulfills_online_orders` / `locations.priority` | Storefront allocation considers only eligible active locations in ascending priority order. |
| transfer item `damaged_qty` | `inventory_transfer_items.damaged_quantity` | Damaged received units remain part of received quantity but are excluded from sellable inventory. |
| store/channel `version` | `stores.version` / `sales_channels.version` | Incremented server-side for optimistic admin edits. |
| catalog `context_type` | derived from `catalogs.market_id` / `catalogs.channel_id` | `DEFAULT` has neither context FK; `MARKET` has `market_id`. It is transport vocabulary, not a DB column. |
| price-list adjustments and item `min_quantity` | `price_lists.adjustment_type` / `adjustment_value`; `price_list_items.min_quantity` | Persisted server/default/deferred fields; Release-1 HTTP requests do not expose them. |
| return disposition | return inventory disposition | `RESTOCK`, `DAMAGED`, `DISCARD`, or `INSPECT`; `REJECTED` is workflow state only. |
| notification `template_key` | `notification_templates.template_key` | Stable store-scoped key; create requires `event_type`, update may retain it. |
| notification `variables_schema` | `notification_templates.variables_schema` | Persisted JSON schema for allowed render variables. |
| bulk `job_type` | `bulk_jobs.job_type` | Operation class: `IMPORT`, `EXPORT`, or `UPDATE`. |
| bulk `resource_type` | `bulk_jobs.resource_type` | Independent target vocabulary: PRODUCT, INVENTORY, ORDER, CUSTOMER. |

## Deferred P1 contract items

CMS page `template_key` and storefront blog tag filtering are not Release 1 transport fields.
