# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.mail.tools.discuss import Store


class MailMessage(models.Model):
    _inherit = "mail.message"

    def _store_message_fields(self, res: Store.FieldList, **kwargs):
        """Expose the Telegram delivery state of outbound messages (failed indicator in Discuss)."""
        super()._store_message_fields(res, **kwargs)
        records = res.records if res.records is not None else self
        channel_messages = records.filtered(
            lambda m: m.model == "discuss.channel" and m.message_type == "comment"
        )
        if not channel_messages:
            return
        # sudo: telegram.message - only the state of messages the user can already read is exposed
        tg_messages = self.env["telegram.message"].sudo().search_fetch(
            [("mail_message_id", "in", channel_messages.ids), ("direction", "=", "outbound")],
            ["mail_message_id", "state", "error_message"],
        )
        by_message = {tg.mail_message_id.id: tg for tg in tg_messages}

        def state(message):
            tg = by_message.get(message.id)
            return tg.state if tg else False

        def error(message):
            tg = by_message.get(message.id)
            return tg.error_message or False if tg and tg.state == "failed" else False

        has_state = lambda message: message.id in by_message  # noqa: E731
        res.attr("telegram_delivery_state", state, predicate=has_state)
        res.attr("telegram_delivery_error", error, predicate=has_state)
