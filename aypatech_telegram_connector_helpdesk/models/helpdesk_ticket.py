# -*- coding: utf-8 -*-
from odoo import fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    telegram_conversation_ids = fields.One2many("telegram.conversation", "ticket_id", string="Telegram Conversations")
    telegram_conversation_count = fields.Integer(
        compute="_compute_telegram_conversation_count",
        groups="aypatech_telegram_connector.group_telegram_user",
    )
    telegram_forward_replies = fields.Boolean(
        "Send replies to Telegram",
        help="Public replies posted on this ticket by agents are also sent to the customer on Telegram.",
    )

    def _compute_telegram_conversation_count(self):
        for ticket in self:
            ticket.telegram_conversation_count = len(ticket.telegram_conversation_ids)

    def action_open_telegram_conversations(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("aypatech_telegram_connector.action_telegram_conversation")
        action["domain"] = [("ticket_id", "=", self.id)]
        action["context"] = {}
        return action

    def _message_post_after_hook(self, message, msg_vals):
        res = super()._message_post_after_hook(message, msg_vals)
        for ticket in self.filtered("telegram_forward_replies"):
            ticket._telegram_forward(message)
        return res

    def _telegram_forward(self, message):
        """Copy a public agent reply into the latest open Telegram conversation of the ticket.

        Posting in the channel reuses the normal outbound path (queue, retries, logs)."""
        self.ensure_one()
        if message.message_type != "comment" or message.is_internal or message.subtype_id.internal:
            return
        if not message.author_id.sudo().user_ids.filtered(lambda u: not u.share):
            return
        conversation = self.sudo().telegram_conversation_ids.filtered(
            lambda c: c.channel_id and c.chat_id and c.state != "closed"
        ).sorted("id", reverse=True)[:1]
        if not conversation:
            return
        channel = conversation.channel_id.sudo()
        attachments = message.sudo().attachment_ids
        copies = self.env["ir.attachment"].sudo()
        for attachment in attachments:
            copies |= attachment.copy({"res_model": "discuss.channel", "res_id": channel.id})
        channel.message_post(
            author_id=message.author_id.id,
            body=message.body,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            attachment_ids=copies.ids,
        )
