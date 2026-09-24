# -*- coding: utf-8 -*-
from odoo import api, fields, models

MESSAGE_KINDS = [
    ("text", "Text"),
    ("photo", "Photo"),
    ("document", "Document"),
    ("video", "Video"),
    ("audio", "Audio"),
    ("voice", "Voice"),
    ("location", "Location"),
    ("contact", "Contact"),
    ("sticker", "Sticker"),
    ("other", "Other"),
]


class TelegramMessage(models.Model):
    _name = "telegram.message"
    _description = "Telegram Message"
    _order = "id desc"
    _check_company_auto = True

    bot_id = fields.Many2one("telegram.bot", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="bot_id.company_id", store=True, index=True)
    conversation_id = fields.Many2one("telegram.conversation", index=True, ondelete="cascade")
    chat_telegram_id = fields.Char(
        "Telegram Chat ID", related="conversation_id.chat_id.telegram_chat_id", store=True, index=True,
    )
    mail_message_id = fields.Many2one("mail.message", index="btree_not_null", ondelete="set null")
    direction = fields.Selection([("inbound", "Inbound"), ("outbound", "Outbound")], required=True)
    message_kind = fields.Selection(MESSAGE_KINDS, default="text", required=True)
    telegram_message_id = fields.Char("Telegram Message ID", index=True, copy=False)
    extra_telegram_message_ids = fields.Char(
        copy=False, help="Other Telegram message ids produced by a split text or attachments (comma separated).",
    )
    update_id = fields.Char(copy=False)
    state = fields.Selection(
        [("received", "Received"), ("queued", "Queued"), ("sending", "Sending"),
         ("sent", "Sent"), ("failed", "Failed")],
        required=True, default="received", index=True,
    )
    error_message = fields.Text()
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")
    delivery_ids = fields.One2many("telegram.delivery", "message_id")
    body_preview = fields.Char(compute="_compute_body_preview")

    _telegram_message_unique = models.UniqueIndex(
        "(bot_id, chat_telegram_id, telegram_message_id) WHERE telegram_message_id IS NOT NULL",
        "This Telegram message is already stored.",
    )

    @api.depends("mail_message_id.preview")
    def _compute_body_preview(self):
        for message in self:
            message.body_preview = message.mail_message_id.sudo().preview

    def _get_all_telegram_ids(self):
        self.ensure_one()
        ids = [self.telegram_message_id] if self.telegram_message_id else []
        ids += [i for i in (self.extra_telegram_message_ids or "").split(",") if i]
        return ids

    def _add_sent_telegram_id(self, telegram_id):
        """Record a Telegram message id produced while sending this message."""
        self.ensure_one()
        telegram_id = str(telegram_id)
        if not self.telegram_message_id:
            self.telegram_message_id = telegram_id
        else:
            extra = [i for i in (self.extra_telegram_message_ids or "").split(",") if i]
            if telegram_id not in extra:
                extra.append(telegram_id)
            self.extra_telegram_message_ids = ",".join(extra)
