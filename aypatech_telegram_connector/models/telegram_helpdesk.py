# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError

# Helpdesk is optional: Enterprise helpdesk wins when both are installed.
HELPDESK_MODELS = ("helpdesk.ticket", "aypatech.helpdesk.ticket")
HELPDESK_MODULES = ("helpdesk", "aypatech_helpdesk")


class TelegramConversation(models.Model):
    _inherit = "telegram.conversation"

    ticket_ref = fields.Reference(
        selection="_selection_ticket_model", string="Ticket", index="btree_not_null", copy=False, tracking=True,
    )
    ticket_forward_replies = fields.Boolean(
        "Send ticket replies to Telegram", default=True,
        help="Public replies posted on the linked ticket by agents are also sent to the customer on Telegram.",
    )
    helpdesk_model = fields.Char(compute="_compute_helpdesk_model")
    can_create_ticket = fields.Boolean(compute="_compute_helpdesk_model")

    @api.model
    def _selection_ticket_model(self):
        return [(name, self.env[name]._description) for name in HELPDESK_MODELS if name in self.env]

    @api.model
    def _get_helpdesk_model(self):
        return next((name for name in HELPDESK_MODELS if name in self.env), False)

    def _compute_helpdesk_model(self):
        model = self._get_helpdesk_model()
        can_create = bool(model) and self.env[model].has_access("create")
        for conv in self:
            conv.helpdesk_model = model
            conv.can_create_ticket = can_create

    def action_create_ticket(self):
        self.ensure_one()
        if self.ticket_ref:
            return self.action_open_ticket()
        model = self._get_helpdesk_model()
        if not model:
            raise UserError(self.env._("Install a helpdesk app to create tickets from Telegram."))
        Ticket = self.env[model]
        values = {key: value for key, value in self._prepare_ticket_values().items() if key in Ticket._fields}
        ticket = Ticket.create(values)
        self.ticket_ref = ticket
        ticket.message_post(body=Markup("<p>%s</p>") % self.env._(
            "Created from Telegram conversation %s", self.name))
        return self.action_open_ticket()

    def _prepare_ticket_values(self):
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
        }

    def action_open_ticket(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.ticket_ref._name,
            "res_id": self.ticket_ref.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }

    def action_install_helpdesk(self):
        """Install the Enterprise helpdesk when it ships with this Odoo, else the AypaTech one."""
        modules = self.env["ir.module.module"].sudo().search([("name", "in", HELPDESK_MODULES)])
        module = next((m for name in HELPDESK_MODULES for m in modules if m.name == name), None)
        if not module:
            raise UserError(self.env._(
                "No helpdesk app found. Add AypaTech Helpdesk (aypatech_helpdesk) to your addons "
                "and update the apps list."))
        return module.button_immediate_install()

    @api.model
    def _forward_ticket_message(self, ticket, message):
        """Copy a public agent reply into the latest open Telegram conversation of the ticket.

        Posting in the channel reuses the normal outbound path (queue, retries, logs)."""
        if message.message_type != "comment" or message.is_internal or message.subtype_id.internal:
            return
        if not message.author_id.sudo().user_ids.filtered(lambda u: not u.share):
            return
        conversation = self.sudo().search([
            ("ticket_ref", "=", "%s,%s" % (ticket._name, ticket.id)),
            ("ticket_forward_replies", "=", True),
            ("channel_id", "!=", False),
            ("chat_id", "!=", False),
            ("state", "!=", "closed"),
        ], order="id desc", limit=1)
        if not conversation:
            return
        channel = conversation.channel_id
        copies = self.env["ir.attachment"].sudo()
        for attachment in message.sudo().attachment_ids:
            copies |= attachment.copy({"res_model": "discuss.channel", "res_id": channel.id})
        channel.message_post(
            author_id=message.author_id.id,
            body=message.body,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            attachment_ids=copies.ids,
        )


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _message_post_after_hook(self, message, msg_vals):
        res = super()._message_post_after_hook(message, msg_vals)
        if self._name in HELPDESK_MODELS:
            for ticket in self:
                self.env["telegram.conversation"]._forward_ticket_message(ticket, message)
        return res
