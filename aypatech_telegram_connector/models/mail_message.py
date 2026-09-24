# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.mail.tools.discuss import Store


class MailMessage(models.Model):
    _inherit = "mail.message"

    def _to_store_defaults(self, target):
        return super()._to_store_defaults(target) + ["telegram_delivery_state"]

    def _to_store(self, store: Store, fields, **kwargs):
        """Expose the Telegram delivery state of outbound messages (failed indicator in Discuss)."""
        super()._to_store(store, [f for f in fields if f != "telegram_delivery_state"], **kwargs)
        if "telegram_delivery_state" not in fields:
            return
        channel_messages = self.filtered(lambda m: m.model == "discuss.channel" and m.message_type == "comment")
        if not channel_messages:
            return
        # sudo: telegram.message - only the state of messages the user can already read is exposed
        tg_messages = self.env["telegram.message"].sudo().search_fetch(
            [("mail_message_id", "in", channel_messages.ids), ("direction", "=", "outbound")],
            ["mail_message_id", "state", "error_message"],
        )
        for tg in tg_messages:
            store.add(tg.mail_message_id, {
                "telegram_delivery_state": tg.state,
                "telegram_delivery_error": tg.error_message or False if tg.state == "failed" else False,
            })
