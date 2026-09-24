# Telegram Discuss for Odoo — Build Specification

Version 1.0 · September 2026 · Target: commercial app on Odoo Apps Store

This document is the single source of truth for building the product. Read it fully before writing code. When this document and your assumptions disagree, this document wins. When this document and the actual Odoo source code disagree about how an Odoo API works, the Odoo source wins — note the discrepancy in `docs/DECISIONS.md`.

---

## 1. Product in one paragraph

An installable Odoo module that connects one or more Telegram bots to Odoo Discuss. Customers chat with the business's Telegram bot; support agents read and reply inside Odoo Discuss without ever opening Telegram. No extra bot server: Odoo itself receives Telegram updates (webhook, or polling when Odoo has no public HTTPS URL) and sends replies through the Telegram Bot API. The product competes on completeness: webhook + polling, multi-bot, all common media types, team routing, CRM/Helpdesk/Sales links, logs, and a setup wizard a non-developer can finish in five minutes.

## 2. Version and edition strategy

| Decision | Value |
| --- | --- |
| Primary target | **Odoo 18.0** (build and stabilize here first) |
| Second target | Odoo 19.0 (port after 18.0 MVP is accepted) |
| Future | Odoo 20.0 only after its official release and our own testing. Never claim 20.0 support before that. |
| Edition | Core module must work on **Community**. Enterprise-only integrations live in separate bridge modules. |
| Python | Whatever the target Odoo version requires (3.10+ for 18.0). |
| License | OPL-1 for paid modules (confirm with owner before publishing). |

Code organization for multi-version support: keep business logic in plain Python services (`services/`) that depend only on stable ORM APIs. Keep version-sensitive code (Discuss frontend patches, `discuss.channel` overrides, view XML) thin and isolated so that porting touches as few files as possible. Each Odoo version lives in its own git branch (`18.0`, `19.0`), which is the Odoo Apps convention.

## 3. Module split

| Module | Depends on | Edition | Purpose |
| --- | --- | --- | --- |
| `telegram_discuss` | `mail`, `base_setup` | Community | Core: bots, identities, conversations, inbound/outbound, media, delivery queue, routing, tags, logs, wizard, dashboard. |
| `telegram_discuss_crm` | `telegram_discuss`, `crm` | Community | Create/link lead from conversation; smart buttons. |
| `telegram_discuss_sale` | `telegram_discuss`, `sale` | Community | Link sale orders; smart button on partner and conversation. |
| `telegram_discuss_helpdesk` | `telegram_discuss`, `helpdesk` | **Enterprise** | Create/link ticket from conversation; post ticket replies back to Telegram (optional). |

Build `telegram_discuss` first. Bridge modules come in Phase 6.

## 4. Architecture

```
Customer ⇄ Telegram ⇄ Bot API
                         │  webhook POST (or getUpdates via cron)
                         ▼
        controllers/telegram_webhook.py   ← validate secret, store raw update, return 200 fast
                         │
                         ▼
        telegram.update (inbox, unique bot+update_id)
                         │  processed by cron (triggered immediately)
                         ▼
        services: gateway → identity → conversation → message → media
                         │
                         ▼
        discuss.channel (channel_type='telegram')  ⇄  Agent in Discuss
                         │  agent posts a comment
                         ▼
        discuss.channel.message_post override → telegram.message + telegram.delivery (queued)
                         │  after commit, cron triggered
                         ▼
        TelegramDeliveryService → Bot API send* → store external message_id / error
```

Key architectural rules:

1. **Never call the Telegram API inside the request transaction that creates the data.** Persist first, commit, then send from a cron job triggered via `ir.cron._trigger()`. This makes every outbound message durable and retryable, and a rollback never produces a "ghost" Telegram message.
2. **Inbox pattern for inbound.** The webhook controller only validates, stores the raw update in `telegram.update`, triggers processing, and returns HTTP 200. Duplicate `update_id` is silently accepted (return 200) without reprocessing.
3. **Concurrency-safe queue processing.** Cron jobs select work rows with `SELECT ... FOR UPDATE SKIP LOCKED` so multiple workers never send the same message twice.
4. **Channel-agnostic core, Telegram adapter at the edge.** `TelegramAPI` and `TelegramFormatter` are the only places that know Telegram's wire format. Gateway/conversation/routing services work with normalized dicts so a future WhatsApp/website adapter can reuse them. Do not over-engineer this now — a clean boundary is enough; no plugin framework.
5. **Explicit relations, no heuristics.** Outbound detection uses `channel_type == 'telegram'` and the message's author/type, never body text. `telegram.message.mail_message_id` links the two worlds directly.

## 5. Discuss integration design

Model each Telegram conversation as a `discuss.channel` with a new `channel_type = 'telegram'` (added via `selection_add`, with `ondelete` set). This mirrors how Odoo's own `im_livechat` (Community) and `whatsapp` (Enterprise) modules integrate external conversations. Study `im_livechat` in the Odoo source as the primary reference; study `whatsapp` too if the Enterprise source is available.

Requirements:

- The customer is represented by a `res.partner` (created or matched by the identity service) and is a member of the channel, so their messages appear with their name and avatar.
- Assigned agent(s) are members of the channel and receive normal Discuss notifications.
- Channel name: customer display name + bot name (e.g. "Ali Rezaei · @AcmeSupportBot").
- Customer-visible replies = messages with `message_type='comment'` posted by an internal user in a telegram channel. Internal notes (`subtype` note / `is_internal`) must **never** be sent. Add a test for this.
- Frontend: patch the Discuss thread/sidebar so telegram channels appear in their own sidebar category ("Telegram") with a Telegram icon, similar to how livechat channels appear. Keep all JS patches in `static/src/discuss/` so porting is contained.
- A `telegram.conversation` record holds business state (state, priority, tags, team, assignee, linked records) and has a Many2one to the channel. Agents can open the conversation form from the channel header and vice versa.

**Phase 0 spike (mandatory before Phase 2):** confirm in the actual 18.0 source how `im_livechat` adds its channel_type, sidebar category, and member handling. Write findings and the exact files/classes to patch into `docs/DISCUSS_NOTES.md`. If a custom channel_type turns out to be impractical, stop and report the alternative before building on it.

## 6. Data model (`telegram_discuss`)

All models: `company_id` where relevant, `_check_company_auto = True`, proper indexes on external IDs. Field names below are the contract; add fields if needed but do not rename these without recording why in `docs/DECISIONS.md`.

### telegram.bot
| Field | Type | Notes |
| --- | --- | --- |
| name | Char | Display name |
| token | Char | `groups='base.group_system'`; never shown in list views, logs or error messages; UI shows masked value |
| bot_telegram_id, username | Char | Filled by `getMe` |
| active | Boolean | |
| company_id | Many2one res.company | |
| connection_mode | Selection | `webhook`, `polling` |
| webhook_key | Char | Random URL path segment, ≥32 chars, generated with `secrets` |
| webhook_secret | Char | Sent as `secret_token` in `setWebhook`; `[A-Za-z0-9_-]`, generated; system group only |
| webhook_url | Char (computed) | `web.base.url` + `/telegram/webhook/<webhook_key>` |
| polling_offset | Integer | Last processed update_id + 1 |
| state | Selection | `draft`, `connected`, `error`, `disabled` |
| last_error, last_check | Text, Datetime | |
| team_id | Many2one telegram.team | Default team |
| default_user_id | Many2one res.users | Optional default agent |
| welcome_message, privacy_notice | Text (translate) | Sent on `/start` |
| auto_link_partner | Boolean | Try to match existing partner (see identity service) |
| store_media | Boolean | Download inbound media into attachments |
| max_media_size_mb | Integer | Default 20 (Bot API download limit) |

SQL constraints: unique `webhook_key`; unique `(bot_telegram_id, company_id)`.

### telegram.contact
`telegram_user_id` (Char, indexed), `username`, `first_name`, `last_name`, `language_code`, `partner_id`, `bot_id`, `blocked` (Boolean: customer blocked the bot, detected from 403 on send). Unique `(bot_id, telegram_user_id)`.

### telegram.chat
`telegram_chat_id` (Char — chat IDs can exceed 32-bit, never store as Integer), `chat_type` (private/group/supergroup/channel), `title`, `contact_id`, `bot_id`. Unique `(bot_id, telegram_chat_id)`. MVP only handles `private` chats; others are logged and ignored.

### telegram.conversation
`name`, `chat_id`, `contact_id`, `partner_id`, `bot_id`, `channel_id` (discuss.channel), `team_id`, `user_id` (assignee), `state` (`new`, `open`, `pending_customer`, `pending_internal`, `resolved`, `closed`), `priority` (0–3), `tag_ids`, `last_customer_message_date`, `last_agent_message_date`, `message_count`, `company_id`. Inherits `mail.thread` + `mail.activity.mixin` for its own audit trail (state/assignee tracking), which is separate from the customer channel.

Reopen rule: a new customer message on a `resolved` conversation reopens it; on `closed`, behavior depends on setting `closed_behavior` (`reopen` or `new_conversation`).

### telegram.message
`bot_id`, `conversation_id`, `mail_message_id`, `direction` (`inbound`/`outbound`), `message_kind` (`text`, `photo`, `document`, `video`, `audio`, `voice`, `location`, `contact`, `sticker`, `other`), `telegram_message_id` (Char), `update_id`, `state` (`received`, `queued`, `sending`, `sent`, `failed`), `error_message`, `attachment_ids`. Unique `(bot_id, chat telegram id, telegram_message_id)` where not null.

### telegram.delivery
`message_id`, `state` (`queued`, `sending`, `sent`, `failed_retryable`, `failed_permanent`, `cancelled`), `attempt` (Integer), `next_retry_at`, `error_class`, `error_message`, `response_summary` (truncated, no token). Index on `(state, next_retry_at)`.

### telegram.update (inbox)
`bot_id`, `update_id` (BigInt-safe — use Char or check that Integer range is sufficient; prefer `fields.Char` + index if unsure), `received_at`, `state` (`pending`, `done`, `ignored`, `error`), `error`, `payload` (Json/Text, deleted by retention job), `payload_hash`. **Unique `(bot_id, update_id)`** — this is the idempotency guarantee.

### telegram.team
`name`, `member_ids` (res.users), `assignment_method` (`manual`, `round_robin`, `least_busy`), `company_id`, `active`. (Named `telegram.team` so the core has no dependency on Helpdesk/CRM teams.)

### telegram.route
`bot_id`, `sequence`, `name`, `condition_type` (`always`, `keyword`, `language`, `new_customer`), `condition_value`, `team_id`, `user_id`, `tag_ids`, `active`. First match by sequence wins; fallback to bot's `team_id`.

### telegram.tag
`name`, `color`, `active`.

### telegram.log
`bot_id`, `level` (`info`/`warning`/`error`), `category` (`webhook`, `api`, `delivery`, `media`, `config`), `message`, `create_date`. Never contains tokens or full payloads.

### res.partner (inherit)
`telegram_contact_ids` (One2many), smart button showing conversation count.

## 7. Services (`services/`)

Plain Python classes instantiated with `env` (and bot where relevant). No global state; everything must work with multiple bots and companies.

| Service | Responsibility |
| --- | --- |
| `TelegramAPI(bot)` | Thin HTTP client around Bot API with `requests`, timeout (connect 5s, read 30s), JSON parsing, conversion of Telegram errors into typed exceptions (see §12). Methods: `get_me`, `set_webhook`, `delete_webhook`, `get_webhook_info`, `get_updates`, `send_message`, `send_photo`, `send_document`, `send_video`, `send_audio`, `send_voice`, `send_chat_action`, `get_file`, `download_file`. Masks the token in every exception/log string. |
| `TelegramGateway` | Entry point for an inbound update: normalize → dispatch by update type (`message`, `edited_message`, `my_chat_member`, `callback_query` later). |
| `TelegramIdentityService` | Find/create `telegram.contact` and `telegram.chat`; find/create/link `res.partner`. Never merge with an existing partner automatically unless `auto_link_partner` is on **and** there is exactly one unambiguous match (e.g. by a phone the customer explicitly shared via contact message). Otherwise create a new partner and let agents link manually. |
| `TelegramConversationService` | Find the open conversation for a chat or create one (with channel); apply routing on creation; state transitions with validation; reopen logic. |
| `TelegramMessageService` | Inbound: create `telegram.message` + post into channel as the customer partner. Outbound: build `telegram.message` + `telegram.delivery` from a `mail.message`. |
| `TelegramMediaService` | Inbound: `get_file` → size check → download → `ir.attachment`. Outbound: pick send method by mimetype; enforce size limits; send captions. |
| `TelegramFormatter` | Odoo HTML → Telegram HTML subset (`b, i, u, s, a, code, pre, blockquote`), escape everything else, strip unsupported tags, split text > 4096 chars into multiple messages, captions ≤ 1024 chars (overflow sent as follow-up text). Telegram → Odoo: escape text, keep line breaks, render entities safely. |
| `TelegramRoutingService` | Evaluate routes, pick team and user (manual / round robin / least busy = fewest open conversations). |
| `TelegramDeliveryService` | Process queued deliveries with row locking, send, classify errors, schedule retries with exponential backoff (e.g. 30s, 2m, 10m, 30m, 2h; max 5 attempts, configurable), honor `retry_after` on 429, mark permanent failures and post a visible notice in the channel for the agent. |
| `TelegramHealthService` | `getMe` + `getWebhookInfo`, compare expected URL, surface `last_error_message` and `pending_update_count`, update bot state. |

## 8. Inbound flow

1. `POST /telegram/webhook/<webhook_key>` — `type='http'`, `auth='public'`, `csrf=False`, `methods=['POST']`.
2. Look up bot by `webhook_key` with sudo; unknown key → 404 (no detail).
3. Compare header `X-Telegram-Bot-Api-Secret-Token` with `webhook_secret` using `hmac.compare_digest`; mismatch → 403 + log.
4. Enforce a body size limit; parse JSON; missing `update_id` → 400.
5. Insert `telegram.update`; on unique violation return 200 (duplicate, already stored). Use a savepoint so the violation doesn't break the transaction.
6. `ir.cron._trigger()` the processing cron; return 200 immediately.
7. Processing cron: lock pending updates (`SKIP LOCKED`), run gateway per update inside a savepoint, set state `done`/`ignored`/`error`.
8. Gateway: identity → conversation → message → post into channel (as customer partner, `message_type='comment'`) → media download (if `store_media`) → routing on first message → `/start` sends welcome + privacy notice.

Polling mode: cron `telegram_polling` calls `deleteWebhook` once when switching mode (getUpdates fails with 409 while a webhook is set), then `getUpdates(offset=polling_offset, timeout=0 or small, limit=100)`, stores updates into the same inbox, and advances `polling_offset`. The wizard must state clearly that polling latency is ~1 minute because Odoo crons cannot run more often.

## 9. Outbound flow

1. Override `discuss.channel.message_post` (or the narrowest suitable hook confirmed in the Phase 0 spike): if `channel_type == 'telegram'`, the author is an internal user, `message_type == 'comment'`, and the subtype is not internal → call `TelegramMessageService.create_outbound(mail_message)`.
2. Create `telegram.message` (state `queued`) + `telegram.delivery` (state `queued`), then `_trigger()` the delivery cron. Use `self.env.cr.postcommit` only if needed to trigger after commit; the durable records are created in the same transaction as the mail.message.
3. Delivery cron: lock, format, send (text and each attachment), store `telegram_message_id`, mark `sent`.
4. Per-conversation ordering: do not send delivery N+1 of a conversation while N is `sending` or `failed_retryable`.
5. Failure → classify (§12). Permanent failures show a red status indicator on the message in Discuss if feasible (Phase 5), and always create a system note in the channel, plus appear in *Telegram → Deliveries → Failed* with a **Retry** button.
6. If a customer blocked the bot (403), mark `telegram.contact.blocked = True` and stop retrying.

## 10. Message types

| Type | Phase | Inbound | Outbound |
| --- | --- | --- | --- |
| Text | MVP | ✔ | ✔ |
| Photo | MVP | ✔ attachment + caption | ✔ image attachments |
| Document | MVP | ✔ | ✔ other attachments |
| Video, Audio, Voice | Phase 4 | ✔ | ✔ by mimetype |
| Location | Phase 4 | Structured text + map link | — |
| Contact | Phase 4 | Structured text; optional phone → partner (setting, privacy-sensitive) | — |
| Sticker | Phase 4 | As image if static, else text placeholder "[sticker]" | — |
| Edited message | Phase 4 | Post a note "Customer edited a message: …" | — |
| Poll, inline buttons | Future | Log + ignore | — |

Bot API limits to respect: download via `getFile` up to 20 MB; upload up to 50 MB; text 4096 chars; caption 1024 chars. Make limits configurable and show a friendly agent-facing error when exceeded.

## 11. Setup wizard (`wizard/telegram_setup.py`)

Steps: (1) short BotFather instructions with a link; (2) paste token → validate with `getMe` → show bot username/avatar; (3) choose company; (4) choose mode — wizard auto-detects whether `web.base.url` is HTTPS and not localhost/private IP and recommends accordingly; (5) default team and optional default agent; (6) welcome message and privacy notice (prefilled, translatable); (7) connect: `setWebhook(url, secret_token, allowed_updates, drop_pending_updates=False)` or start polling; (8) live test: "Send /start to @YourBot now" with a polling check in the wizard that turns green when the first update arrives; (9) done → open dashboard.

No step may require editing files, environment variables or server config. Error messages must say what to do next (e.g. "Telegram cannot reach https://… — make sure the site is public and uses a valid certificate").

## 12. Error classification

| Class | Detection | Action |
| --- | --- | --- |
| `auth` | 401 / "Unauthorized" | Stop all deliveries for the bot, bot state `error`, notify managers via activity. |
| `blocked` | 403 "bot was blocked by the user" | Permanent; mark contact blocked. |
| `bad_request` | 400 | Permanent; show Telegram's description to the agent (sanitized). |
| `rate_limit` | 429, `parameters.retry_after` | Retry exactly after `retry_after`. |
| `transient` | 5xx, timeout, connection error | Retry with backoff. |
| `not_found` | chat not found | Permanent. |
| `attachment` | Size/type exceeded (local check) | Permanent, agent notified before sending. |
| `internal` | Unexpected Python/DB error | Retry if safe (max attempts), log with traceback in server log only. |

## 13. Routing and assignment

On conversation creation: evaluate `telegram.route` by sequence → team/user/tags; fallback to bot defaults. Methods: manual, round robin (store pointer per team), least busy. Reassignment is tracked in the conversation chatter. Assignee is added as channel member; previous assignee stays unless setting `remove_previous_assignee` is on.

## 14. Security

- Groups: `group_telegram_user` (read/create/reply on conversations they're allowed to see), `group_telegram_manager` (bots, routes, teams, deliveries, logs, settings; implies user). System admin: everything including tokens.
- Record rules: multi-company on all models; users see conversations of their teams or assigned to them, managers see all in their companies.
- Token and webhook secret: `groups='base.group_system'`, masked in UI (`123456:ABC…xyz`), never in logs, exceptions, chatter, or `response_summary`.
- Webhook: non-guessable path + secret header + constant-time compare + body size cap + JSON validation.
- Media: only download from Telegram's file endpoint for the bot's own token; never fetch arbitrary URLs from payloads (SSRF). Validate size before download (from `file_size`) and after.
- Public routes never expose chat IDs, partner data or bot tokens.
- Configuration changes on `telegram.bot` tracked (`tracking=True`) except secret fields.

## 15. Privacy

Settings: raw payload retention days (default 7), log retention days (default 30). Cleanup cron deletes `telegram.update.payload` and old logs. Provide a "Forget Telegram identity" action on contacts (unlinks partner, deletes contact/chat mapping, keeps or anonymizes message history per setting). Document stored data categories in `doc/PRIVACY.md`. The privacy notice text is sent on `/start` when configured.

## 16. Scheduled jobs (`data/ir_cron.xml`)

| Cron | Interval | Notes |
| --- | --- | --- |
| Process inbound updates | 1 min + `_trigger()` | Inbox processor |
| Deliver outbound messages | 1 min + `_trigger()` | Delivery queue + retries |
| Polling | 1 min | Only bots in polling mode |
| Stuck delivery watchdog | 15 min | `sending` older than 10 min → `failed_retryable` |
| Health check | 1 hour | Optional per bot |
| Cleanup | daily | Retention |
| Inactive conversations | daily | Optional auto-resolve after N days |

All crons must be batch-limited and commit per batch so one bad record never blocks the rest.

## 17. UI

Menu **Telegram**: Dashboard · Conversations (kanban by state, list, form, search with filters: mine, unassigned, open, pending, by bot/team/tag) · Contacts · Deliveries (queued / failed with Retry) · Configuration → Bots (form with Connect, Test, Health buttons, masked token), Teams, Routes, Tags, Logs, Settings (in `res.config.settings`).

Dashboard (OWL client action or kanban on bots): per bot connection state, open/unassigned conversations, failed deliveries in last 24h, messages today, last error. Keep it simple and fast.

Partner form: smart button "Telegram" (conversation count). Conversation form header: buttons Open chat, Assign to me, Resolve, Reopen, Close; bridge modules add Create Lead / Create Ticket / Linked orders.

## 18. File structure

```
telegram_discuss/
├── __init__.py
├── __manifest__.py
├── controllers/telegram_webhook.py
├── models/  (one file per model + discuss_channel.py, res_partner.py, res_config_settings.py)
├── services/ (telegram_api.py, gateway.py, identity.py, conversation.py, message.py,
│              media.py, formatter.py, routing.py, delivery.py, health.py, exceptions.py)
├── wizard/  (telegram_setup.py + views)
├── views/   (one XML per model, menus.xml, dashboard)
├── security/ (telegram_security.xml, ir.model.access.csv)
├── data/    (ir_cron.xml, default data)
├── static/src/discuss/   (all Discuss JS/SCSS patches)
├── static/description/   (icon.png, index.html, screenshots — for Apps Store)
├── i18n/    (telegram_discuss.pot, fa.po)
├── tests/
└── doc/     (INSTALL.md, WEBHOOK_VS_POLLING.md, PRIVACY.md, TROUBLESHOOTING.md)
```

Repository root also contains `docs/DECISIONS.md`, `docs/DISCUSS_NOTES.md`, `docker-compose.yml` for local dev, `CLAUDE.md`, and the bridge modules as sibling folders.

## 19. Testing

Use Odoo's test framework (`TransactionCase`, `HttpCase` for the controller), tagged `post_install`, `-at_install`. **Never call the real Telegram API in tests** — patch `TelegramAPI` methods / `requests` and use JSON fixtures of real Bot API payloads in `tests/fixtures/`.

Required coverage: formatter (escaping, splitting, captions); identity matching; routing methods; state transitions; webhook (valid, wrong secret, unknown key, malformed JSON, duplicate update_id); inbound text/photo/document; outbound success, 400, 403, 429 with retry_after, 5xx, timeout; internal note never queued; per-conversation ordering; stuck delivery watchdog; ACL and record rules for user vs manager vs other company; token masking in logs/exceptions; polling offset advance and 409 handling; module upgrade keeps mappings.

## 20. Development phases and definition of done

Each phase ends with: all tests green, module installs on a fresh DB with and without demo data, no warnings in the install log, and a short entry in `CHANGELOG.md`.

| Phase | Scope | Done when |
| --- | --- | --- |
| 0 Spike | Dev env (docker-compose Odoo 18 + Postgres), read `im_livechat` source, write `docs/DISCUSS_NOTES.md` | Notes explain exactly how channel_type, sidebar category and member handling will be implemented |
| 1 Foundation | Models, security, `TelegramAPI`, bot form with Test button, setup wizard (getMe only) | Token validates; token is masked everywhere |
| 2 Core messaging | Webhook, inbox, identity, conversation + channel, text in/out, delivery queue (basic) | Customer text appears in Discuss; agent reply arrives in Telegram; internal note does not |
| 3 Reliability | Idempotency tests, error classes, retries/backoff, 429, watchdog, ordering, logs, polling mode | All §19 reliability tests pass |
| 4 Media | Photo, document, video, audio, voice, location, contact, sticker, edits | Round-trip for each MVP/Phase-4 type |
| 5 Operations & UX | Teams, routing, assignment, tags, lifecycle, dashboard, Discuss sidebar category/icon, failed-status indicator, partner smart button | Agent workflow usable end-to-end without leaving Odoo |
| 6 Bridges | `telegram_discuss_crm`, `_sale`, `_helpdesk` | Each installs independently; core works without them |
| 7 Hardening | Security review, privacy tools, performance (burst of 500 inbound updates), upgrade test, `fa` translation | Checklist in §21 complete |
| 8 Release | `static/description/index.html`, screenshots, docs, demo data, license, pricing, port to 19.0 branch | Passes Odoo Apps upload checks |

## 21. MVP acceptance checklist (end of Phase 3)

- [ ] Installs on clean Odoo 18.0 Community.
- [ ] Bot connected through wizard; webhook status active (and polling works on a private instance).
- [ ] Customer message appears in Discuss under the Telegram category.
- [ ] Agent reply reaches Telegram; internal notes never do.
- [ ] Duplicate update does not create a duplicate message.
- [ ] One Telegram identity ↔ one Odoo partner.
- [ ] Assign, tag, resolve, reopen work.
- [ ] Failed deliveries visible and retryable; 429 honored.
- [ ] Unauthorized users cannot see bots/tokens or other teams' conversations.
- [ ] Multi-bot and multi-company isolation verified.
- [ ] Automated test suite passes.

## 22. Out of scope for v1

Group chats, Telegram channels as broadcast targets, inline keyboards/callback buttons, payments, Telegram Business accounts / user-account (MTProto) integration, AI features, WhatsApp or other adapters. Keep the boundaries clean so these can be added later as separate modules.
