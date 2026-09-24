# -*- coding: utf-8 -*-
"""Telegram conversations are ``discuss.channel`` records with channel_type='telegram'.

See docs/DISCUSS_NOTES.md for the core behaviours this relies on.
"""
from odoo import fields, models
from odoo.addons.mail.tools.discuss import Store

from ..services.message import TelegramMessageService


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    channel_type = fields.Selection(
        selection_add=[("telegram", "Telegram Conversation")],
        ondelete={"telegram": "cascade"},
    )
    telegram_conversation_id = fields.Many2one(
        "telegram.conversation", index="btree_not_null", readonly=True, copy=False, ondelete="set null",
    )

    def _is_telegram_outbound(self, message):
        """Customer-visible reply? (SPEC §5: comment by an internal user, never a note)."""
        self.ensure_one()
        if self.channel_type != "telegram" or not self.telegram_conversation_id:
            return False
        if self.env.context.get("telegram_inbound"):
            return False
        if message.message_type != "comment":
            return False
        if message.is_internal or message.subtype_id.internal:
            return False
        if not message.subtype_id:
            return False
        author_users = message.author_id.sudo().user_ids
        return bool(author_users.filtered(lambda u: not u.share))

    def _message_post_after_hook(self, message, msg_vals):
        res = super()._message_post_after_hook(message, msg_vals)
        for channel in self:
            if channel._is_telegram_outbound(message):
                TelegramMessageService(self.env).create_outbound(channel.telegram_conversation_id, message)
        return res

    def _notify_get_recipients(self, message, msg_vals=False, **kwargs):
        recipients = super()._notify_get_recipients(message, msg_vals=msg_vals, **kwargs)
        if self.channel_type != "telegram":
            return recipients
        # The Telegram customer is reached through the bot only: never email/push them.
        customer = self.telegram_conversation_id.sudo().partner_id
        return [r for r in recipients if r.get("id") != customer.id]

    def execute_command_leave(self, **kwargs):
        if self.channel_type == "telegram":
            self.action_unfollow()
        else:
            super().execute_command_leave(**kwargs)

    def _to_store(self, store: Store):
        super()._to_store(store)
        for channel in self.filtered(_is_telegram):
            store.add(channel, {
                # plain id: the frontend has no telegram.conversation model, it only opens the form
                "telegram_conversation_id": channel.telegram_conversation_id.id,
                # sudo: telegram.conversation - only the customer partner id of an accessible channel
                "telegram_partner_id": channel.telegram_conversation_id.sudo().partner_id.id,
            })


def _is_telegram(channel):
    return channel.channel_type == "telegram"
