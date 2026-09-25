# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import fields, models


class TelegramConversation(models.Model):
    _inherit = "telegram.conversation"

    lead_id = fields.Many2one("crm.lead", string="Lead", index="btree_not_null", tracking=True, copy=False)

    def action_create_lead(self):
        self.ensure_one()
        if self.lead_id:
            return self.action_open_lead()
        lead = self.env["crm.lead"].create(self._prepare_lead_values())
        self.lead_id = lead
        lead.message_post(body=Markup("<p>%s</p>") % self.env._(
            "Created from Telegram conversation %s", self.name))
        return self.action_open_lead()

    def _prepare_lead_values(self):
        self.ensure_one()
        lines = self.channel_id.sudo().message_ids.filtered(
            lambda m: m.message_type == "comment" and m.author_id == self.partner_id
        ).sorted("id")[-5:]
        description = Markup("<br/>").join(Markup("%s") % m.preview for m in lines if m.preview)
        return {
            "name": self.env._("Telegram: %s", self.partner_id.name or self.name),
            "partner_id": self.partner_id.id,
            "user_id": (self.user_id or self.env.user).id,
            "company_id": self.company_id.id,
            "description": description,
        }

    def action_open_lead(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "res_id": self.lead_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }
