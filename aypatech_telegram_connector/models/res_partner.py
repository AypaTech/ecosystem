# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    telegram_contact_ids = fields.One2many("telegram.contact", "partner_id", string="Telegram Identities")
    telegram_conversation_count = fields.Integer(
        compute="_compute_telegram_conversation_count",
        groups="aypatech_telegram_connector.group_telegram_user",
    )

    def _compute_telegram_conversation_count(self):
        data = dict(self.env["telegram.conversation"]._read_group(
            [("partner_id", "in", self.ids)], ["partner_id"], ["__count"],
        ))
        for partner in self:
            partner.telegram_conversation_count = data.get(partner, 0)

    def action_open_telegram_conversations(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("aypatech_telegram_connector.action_telegram_conversation")
        action["domain"] = [("partner_id", "=", self.id)]
        action["context"] = {"default_partner_id": self.id}
        return action
