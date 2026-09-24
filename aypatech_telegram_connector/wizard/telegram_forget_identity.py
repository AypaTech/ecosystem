# -*- coding: utf-8 -*-
"""'Forget Telegram identity' (SPEC §15)."""
from markupsafe import Markup

from odoo import api, fields, models


class TelegramForgetIdentity(models.TransientModel):
    _name = "telegram.forget.identity"
    _description = "Forget Telegram Identity"

    contact_ids = fields.Many2many("telegram.contact", string="Telegram Contacts")
    mode = fields.Selection(
        [("keep", "Keep message history"), ("anonymize", "Anonymize message history")],
        required=True,
        default=lambda self: self.env["ir.config_parameter"].sudo().get_param("telegram.forget_mode", "anonymize"),
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") == "telegram.contact" and self.env.context.get("active_ids"):
            res["contact_ids"] = [(6, 0, self.env.context["active_ids"])]
        return res

    def action_forget(self):
        self.ensure_one()
        for contact in self.contact_ids.sudo():
            conversations = contact.conversation_ids | self.env["telegram.conversation"].sudo().search(
                [("chat_id", "in", contact.chat_ids.ids)])
            partner = contact.partner_id
            if self.mode == "anonymize":
                self._anonymize(conversations, partner)
            conversations.write({"contact_id": False, "chat_id": False})
            conversations.filtered(lambda c: c.state != "closed")._set_state("closed", force=True)
            for conversation in conversations:
                conversation.message_post(body=Markup("<p>%s</p>") % self.env._(
                    "Telegram identity forgotten (%s).", dict(self._fields["mode"].selection)[self.mode]))
            contact.chat_ids.unlink()
            contact.unlink()
        return {"type": "ir.actions.act_window_close"}

    def _anonymize(self, conversations, partner):
        inbound = self.env["telegram.message"].sudo().search([
            ("conversation_id", "in", conversations.ids), ("direction", "=", "inbound"),
        ])
        mail_messages = inbound.mail_message_id
        inbound.attachment_ids.unlink()
        mail_messages.write({"body": Markup("<p><i>%s</i></p>") % self.env._("[removed]")})
        if partner and not partner.user_ids:
            label = self.env._("Anonymous Telegram user")
            partner.write({"name": f"{label} #{partner.id}", "phone": False, "email": False, "comment": False})
        for conversation in conversations:
            conversation.name = self.env._("Anonymous Telegram conversation #%s", conversation.id)
            if conversation.channel_id:
                conversation.channel_id.name = conversation.name
