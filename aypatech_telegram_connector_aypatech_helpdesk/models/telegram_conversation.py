# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import fields, models


class TelegramConversation(models.Model):
    _inherit = "telegram.conversation"

    aypatech_ticket_id = fields.Many2one("aypatech.helpdesk.ticket", string="Ticket", index="btree_not_null", tracking=True, copy=False)

    def action_create_aypatech_ticket(self):
        self.ensure_one()
        if not self.aypatech_ticket_id:
            ticket = self.env["aypatech.helpdesk.ticket"].create(self._prepare_aypatech_ticket_values())
            self.aypatech_ticket_id = ticket
            ticket.message_post(body=Markup("<p>%s</p>") % self.env._(
                "Created from Telegram conversation %s", self.name))
        return self.action_open_aypatech_ticket()

    def _prepare_aypatech_ticket_values(self):
        self.ensure_one()
        lines = self.channel_id.sudo().message_ids.filtered(
            lambda m: m.message_type == "comment" and m.author_id == self.partner_id
        ).sorted("id")[-5:]
        return {
            "name": self.env._("Telegram: %s", self.partner_id.name or self.name),
            "partner_id": self.partner_id.id,
            "user_id": (self.user_id or self.env.user).id,
            "company_id": self.company_id.id,
            "description": Markup("<br/>").join(Markup("%s") % m.preview for m in lines if m.preview),
            "telegram_forward_replies": True,
        }

    def action_open_aypatech_ticket(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "aypatech.helpdesk.ticket",
            "res_id": self.aypatech_ticket_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }
