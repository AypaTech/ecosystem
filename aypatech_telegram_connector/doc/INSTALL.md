# Installation

Requirements: Odoo 19.0 (Community or Enterprise), Python `requests` (shipped with Odoo).

1. Copy `aypatech_telegram_connector` (and optionally the bridge modules) into your addons path.
2. Apps → Update Apps List → install **Telegram Discuss Connector**.
3. Give your agents the group *Telegram / User*; team leads *Telegram / Manager*.
4. As an administrator open **Telegram → Configuration → Setup Wizard** and follow the steps:
   create the bot with @BotFather, paste the token, choose webhook or polling, pick a team,
   edit the welcome/privacy messages, connect, and send `/start` to your bot.

Bridge modules (installed automatically when their dependency is installed):

| Module | Needs | Adds |
| --- | --- | --- |
| `aypatech_telegram_connector_crm` | CRM | Create Lead button, lead ↔ conversation smart buttons |
| `aypatech_telegram_connector_sale` | Sales | Customer orders and New Quotation on the conversation |
| `aypatech_telegram_connector_helpdesk` | Helpdesk (Enterprise) | Create Ticket, ticket replies sent to Telegram |
| `aypatech_telegram_connector_aypatech_helpdesk` | Aypatech Helpdesk | Same for the Aypatech helpdesk |

No server configuration, environment variable or file edit is needed.
