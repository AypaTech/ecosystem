# Installation

Requirements: Odoo 20.0 (Community or Enterprise), Python `requests` (shipped with Odoo).

1. Copy `aypatech_telegram_connector` into your addons path.
2. Apps → Update Apps List → install **Telegram Discuss Connector**.
3. Give your agents the group *Telegram / User*; team leads *Telegram / Manager*.
4. As an administrator open **Telegram → Configuration → Setup Wizard** and follow the steps:
   create the bot with @BotFather, paste the token, choose webhook or polling, pick a team,
   edit the welcome/privacy messages, connect, and send `/start` to your bot.

Built in (one module, nothing extra to install):

| Needs | Adds |
| --- | --- |
| CRM (installed with the module) | Create Lead button, lead ↔ conversation smart buttons |
| Sales (installed with the module) | Customer orders and New Quotation on the conversation |
| Helpdesk (optional) | Create Ticket, ticket replies sent to Telegram |

Helpdesk is optional: the module uses the Enterprise **Helpdesk** when it is installed,
otherwise **AypaTech Helpdesk** (`aypatech_helpdesk`). With no helpdesk the module still
installs; the conversation form then offers an *Install Helpdesk* button to administrators.

No server configuration, environment variable or file edit is needed.
