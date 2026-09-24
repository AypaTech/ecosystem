# -*- coding: utf-8 -*-
from odoo import fields, models


class TelegramChat(models.Model):
    _name = "telegram.chat"
    _description = "Telegram Chat"
    _order = "id desc"
    _rec_name = "display_title"
    _check_company_auto = True

    # Chat ids can exceed 32 bits: always Char.
    telegram_chat_id = fields.Char("Telegram Chat ID", required=True, index=True, readonly=True)
    chat_type = fields.Selection(
        [("private", "Private"), ("group", "Group"), ("supergroup", "Supergroup"), ("channel", "Channel")],
        required=True, default="private",
    )
    title = fields.Char()
    display_title = fields.Char(compute="_compute_display_title")
    contact_id = fields.Many2one("telegram.contact", index=True, ondelete="cascade")
    bot_id = fields.Many2one("telegram.bot", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="bot_id.company_id", store=True, index=True)

    _sql_constraints = [
        ('bot_chat_unique', 'UNIQUE(bot_id, telegram_chat_id)', 'This Telegram chat already exists for this bot.'),
    ]

    def _compute_display_title(self):
        for chat in self:
            chat.display_title = chat.title or chat.contact_id.name or chat.telegram_chat_id
