# CLAUDE.md — Telegram Discuss for Odoo

## What we are building
A commercial Odoo app (`telegram_discuss` + bridge modules) that connects Telegram bots to Odoo Discuss. The full specification is in `SPEC.md`. Read it before any work and re-read the relevant section before each phase.

## Environment
- Target: Odoo **18.0** Community first (branch `18.0`). Port to 19.0 only in Phase 8.
- Odoo source is expected at `../odoo` (and Enterprise, if available, at `../enterprise`). **Before using any Odoo API you are not 100% sure about, grep the actual source** — especially `addons/mail`, `addons/im_livechat`, `odoo/models.py`, `odoo/addons/base/models/ir_cron.py`. Do not rely on memory of other Odoo versions; APIs changed a lot between 16, 17 and 18.
- Local dev: `docker-compose.yml` with Odoo 18 + PostgreSQL, addons path mounted from this repo.
- Run tests: `odoo -d test_tg --addons-path=... -i telegram_discuss --test-enable --stop-after-init --test-tags /telegram_discuss`
- For live webhook testing, expose local Odoo with a tunnel (e.g. cloudflared or ngrok) and set `web.base.url` accordingly.

## How to work
1. Work **one phase at a time** (SPEC §20). At the start of a phase, write a short plan; at the end, run the full test suite and update `CHANGELOG.md`.
2. Phase 0 (Discuss spike) is mandatory before Phase 2. Record findings in `docs/DISCUSS_NOTES.md`.
3. Record every non-obvious design decision, or any deviation from SPEC.md, in `docs/DECISIONS.md` (date, decision, reason).
4. Write tests together with the code, not after. Never call the real Telegram API in tests.
5. If something in SPEC.md is impossible or clearly wrong for Odoo 18, stop and explain instead of silently working around it.

## Hard rules
- Never call the Telegram API inside the transaction that creates the data. Persist → commit → send from cron (`_trigger()`).
- Bot tokens and webhook secrets: never in logs, exceptions, chatter, test output or commit history. Mask in UI.
- Internal notes must never be delivered to Telegram.
- Store Telegram IDs (chat, user, message, update) as `Char` or verified-safe types — chat IDs exceed 32-bit.
- Idempotency via unique constraints (`bot_id + update_id`, etc.), not via Python checks alone.
- Queue processing uses `FOR UPDATE SKIP LOCKED`.
- All Discuss frontend patches live in `static/src/discuss/`.
- Core module must not depend on Enterprise modules.
- Follow Odoo coding guidelines: manifest keys, XML ids `view_telegram_*`, `action_telegram_*`, `menu_telegram_*`; translatable strings via `_()` / `env._()` as appropriate for 18.0; no `print`, use `_logger`.
- Keep services free of UI code; keep controllers thin.

## Definition of done (every phase)
Tests green · installs on fresh DB with and without demo data · no install warnings · CHANGELOG updated · DECISIONS updated if anything changed.
