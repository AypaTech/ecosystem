# Troubleshooting

| Symptom | Check |
| --- | --- |
| Bot is in **Error**, "Telegram rejected the token" | Copy the token again from @BotFather and press **Test**. Outgoing messages are paused until then. |
| Webhook: nothing arrives | Bot → **Health Check**. It compares the webhook registered on Telegram with this database and shows Telegram's last delivery error. `web.base.url` must be the public https address. |
| "409 Conflict" in logs | Another program reads the same bot with `getUpdates`, or a webhook is still registered. Press **Connect** again. |
| Messages arrive ~1 minute late | Normal in polling mode. Use webhook mode for instant delivery. |
| Reply shows a red ⚠ in Discuss | Telegram → Deliveries → Failed shows the reason and a **Retry** button. |
| "the customer blocked the bot" | The customer must unblock/restart the bot; messages resume when they write again. |
| Updates stuck in *Pending* | Settings → Technical → Scheduled Actions → *Telegram: process inbound updates* must be active. Errors are visible in Telegram → Configuration → Technical → Inbound Updates. |
