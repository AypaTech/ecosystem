# Stored data

| Category | Where | Retention |
| --- | --- | --- |
| Telegram identity: user id, username, first/last name, language | `telegram.contact` | Until "Forget Telegram identity" |
| Phone number shared by the customer through a contact message | `telegram.contact.phone` (and the Odoo contact if the setting is on) | Until forgotten |
| Chat id | `telegram.chat` | Until forgotten |
| Messages and files | Discuss channel messages / attachments | Like any Discuss message |
| Raw updates (JSON) | `telegram.update.payload` | Deleted after *Raw update retention* days (default 7) |
| Technical logs (no tokens, no payloads) | `telegram.log` | Deleted after *Log retention* days (default 30) |
| Bot token, webhook secret | `telegram.bot` (administrators only) | Until changed |

**Forget Telegram identity** (Telegram → Contacts → action) deletes the contact, chat and ids, closes
the conversations and, in *anonymize* mode, removes customer messages/files and renames the
auto-created Odoo contact.

The privacy notice configured on the bot is sent to the customer on `/start`.
