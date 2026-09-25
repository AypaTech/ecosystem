# Changelog

## 18.0.1.1.0 — 2026-09-25

- The CRM, Sales and Helpdesk bridge modules are merged into this module. CRM and Sales are
  now dependencies; Helpdesk stays optional (Enterprise `helpdesk` or `aypatech_helpdesk`,
  linked through the `ticket_ref` reference field).
- Ticket reply forwarding is switched per conversation (`ticket_forward_replies`).

## 19.0.1.0.0 — 2026-09-22 (development, not yet installed)

Phases 0–6 of SPEC §20 written in one pass on request of the owner. **Nothing has been installed or
run on an Odoo server yet**: Python/XML/JSON syntax and pyflakes are clean, the formatter was
exercised standalone; the Odoo test suite has not been executed.

- Phase 0: Odoo 19.0 source studied, `docs/DISCUSS_NOTES.md`.
- Phase 1: models, groups/rules, `TelegramAPI`, bot form (Test / Connect / Health), setup wizard.
- Phase 2: webhook controller, inbox, identity, conversation + `discuss.channel` (`channel_type='telegram'`),
  text in/out, delivery queue.
- Phase 3: error classes, retries with backoff, 429 `retry_after`, auth pause, per-conversation ordering,
  stuck watchdog, logs, polling mode (409 handling).
- Phase 4: photo, document, video, audio, voice, location, contact, sticker, edited messages.
- Phase 5: teams, routes (always/keyword/language/new customer), round robin / least busy, tags,
  lifecycle, dashboard, Discuss sidebar category + icon, delivery status indicator, partner smart button.
- Phase 6: bridges `aypatech_telegram_connector_crm`, `_sale`, `_helpdesk` (Enterprise),
  `_aypatech_helpdesk`.
- Phase 7 (partial): privacy tools (retention cleanup, forget identity).

Open items: run the test suite on 19.0; install on fresh DB with/without demo; `fa` translation and
`.pot`; burst test (500 updates); real upgrade test; Phase 8 release material.
