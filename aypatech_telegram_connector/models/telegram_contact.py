# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TelegramContact(models.Model):
    _name = "telegram.contact"
    _description = "Telegram Contact"
    _order = "id desc"
    _rec_names_search = ["first_name", "last_name", "username", "telegram_user_id"]
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    telegram_user_id = fields.Char("Telegram User ID", required=True, index=True, readonly=True)
    username = fields.Char()
    first_name = fields.Char()
    last_name = fields.Char()
    language_code = fields.Char()
    phone = fields.Char(help="Phone number the customer explicitly shared through Telegram.")
    partner_id = fields.Many2one("res.partner", index=True, ondelete="set null")
    bot_id = fields.Many2one("telegram.bot", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="bot_id.company_id", store=True, index=True)
    blocked = fields.Boolean(help="The customer blocked the bot (detected from a 403 on send).")
    chat_ids = fields.One2many("telegram.chat", "contact_id")
    conversation_ids = fields.One2many("telegram.conversation", "contact_id")
    conversation_count = fields.Integer(compute="_compute_conversation_count")

    _bot_user_unique = models.Constraint(
        "UNIQUE(bot_id, telegram_user_id)", "This Telegram user already exists for this bot.",
    )

    @api.depends("first_name", "last_name", "username", "telegram_user_id")
    def _compute_name(self):
        for contact in self:
            full = " ".join(p for p in (contact.first_name, contact.last_name) if p)
            contact.name = full or (contact.username and f"@{contact.username}") or contact.telegram_user_id

    def _compute_conversation_count(self):
        data = dict(self.env["telegram.conversation"]._read_group(
            [("contact_id", "in", self.ids)], ["contact_id"], ["__count"],
        ))
        for contact in self:
            contact.conversation_count = data.get(contact, 0)

    def action_open_conversations(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("aypatech_telegram_connector.action_telegram_conversation")
        action["domain"] = [("contact_id", "=", self.id)]
        action["context"] = {}
        return action

    def action_forget_identity(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("aypatech_telegram_connector.action_telegram_forget_identity")
        action["context"] = {"active_model": self._name, "active_ids": self.ids}
        return action
