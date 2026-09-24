# Webhook or polling?

| | Webhook | Polling |
| --- | --- | --- |
| Latency | Instant | About 1 minute (Odoo scheduled actions run at most every minute) |
| Needs | Public HTTPS address with a valid certificate (`web.base.url`) | Outgoing internet access only |
| Good for | Production servers | Local/private installations, tests |

**Webhook**: Telegram POSTs every update to `https://<your-odoo>/telegram/webhook/<random key>`
with a secret header. Odoo stores the raw update, answers 200 immediately and processes it in the
background. The URL key and the secret can be regenerated on the bot (Options → Security).

**Polling**: the scheduled action *Telegram: polling* calls `getUpdates` every minute. Switching a bot to
polling removes its webhook first (Telegram refuses `getUpdates` while a webhook is set).

The wizard detects whether `web.base.url` is HTTPS and not a private address and recommends a mode.
