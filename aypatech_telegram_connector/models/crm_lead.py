# -*- coding: utf-8 -*-
from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    telegram_conversation_ids = fields.One2many("telegram.conversation", "lead_id", string="Telegram Conversations")
    telegram_conversation_count = fields.Integer(
        compute="_compute_telegram_conversation_count",
        groups="aypatech_telegram_connector.group_telegram_user",
    )

    def _compute_telegram_conversation_count(self):
        for lead in self:
            lead.telegram_conversation_count = len(lead.telegram_conversation_ids)

    def action_open_telegram_conversations(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("aypatech_telegram_connector.action_telegram_conversation")
        action["domain"] = [("lead_id", "=", self.id)]
        action["context"] = {}
        return action
