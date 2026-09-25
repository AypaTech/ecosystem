# -*- coding: utf-8 -*-
"""Conversation lifecycle + Discuss channel (SPEC §7 ``TelegramConversationService``)."""
from odoo import fields

from .routing import TelegramRoutingService

OPEN_STATES = ("new", "open", "pending_customer", "pending_internal")


class TelegramConversationService:

    def __init__(self, env, bot):
        self.env = env
        self.bot = bot.sudo()

    def get_or_create(self, chat, contact, partner, text="", is_new_customer=False):
        """Return ``(conversation, created)`` for an incoming customer message."""
        Conversation = self.env["telegram.conversation"].sudo()
        conv = Conversation.search([("chat_id", "=", chat.id)], order="id desc", limit=1)
        if conv and conv.state in OPEN_STATES:
            self._ensure_channel(conv)
            return conv, False
        if conv and conv.state == "resolved":
            conv._set_state("open")
            self._ensure_channel(conv)
            return conv, False
        if conv and conv.state == "closed":
            behavior = self.env["ir.config_parameter"].sudo().get_param(
                "telegram.closed_behavior", "new_conversation")
            if behavior == "reopen":
                conv._set_state("open")
                self._ensure_channel(conv)
                return conv, False
        conv = self._create(chat, contact, partner)
        TelegramRoutingService(self.env, self.bot).route(
            conv, text=text, language_code=contact.language_code if contact else "",
            is_new_customer=is_new_customer,
        )
        if not conv.user_id:
            self._add_fallback_members(conv)
        return conv, True

    def _create(self, chat, contact, partner):
        conv = self.env["telegram.conversation"].sudo().create({
            "name": self._channel_name(partner, contact),
            "bot_id": self.bot.id,
            "chat_id": chat.id,
            "contact_id": contact.id if contact else False,
            "partner_id": partner.id,
            "company_id": self.bot.company_id.id,
            "state": "new",
        })
        self._create_channel(conv)
        return conv

    def _channel_name(self, partner, contact):
        who = partner.name or (contact.name if contact else "") or "Telegram"
        bot = f"@{self.bot.username}" if self.bot.username else self.bot.name
        return f"{who} · {bot}"

    def _create_channel(self, conv):
        Channel = self.env["discuss.channel"].sudo()
        creator = self.env.user.partner_id
        channel = Channel.with_context(mail_create_nosubscribe=True).create({
            "name": conv.name,
            "channel_type": "telegram",
            "telegram_conversation_id": conv.id,
            "channel_member_ids": [(0, 0, {"partner_id": conv.partner_id.id})],
        })
        # discuss.channel.create() always adds the current user (OdooBot in crons): drop it.
        extra = channel.channel_member_ids.filtered(lambda m: m.partner_id == creator and creator != conv.partner_id)
        extra.unlink()
        conv.channel_id = channel
        return channel

    def _ensure_channel(self, conv):
        if not conv.channel_id:
            self._create_channel(conv)
            if conv.user_id:
                conv.channel_id._add_members(users=conv.user_id, post_joined_message=False)
            else:
                self._add_fallback_members(conv)

    def _add_fallback_members(self, conv):
        """Nobody assigned: make the conversation visible in Discuss for the team (or managers)."""
        users = conv.team_id.member_ids
        if not users:
            group = self.env.ref("aypatech_telegram_connector.group_telegram_manager", raise_if_not_found=False)
            users = group.sudo().users if group else self.env["res.users"]
        users = users.filtered(
            lambda u: u.active and not u.share and conv.company_id in u.company_ids and u.id != self.env.ref("base.user_root").id
        )
        if users:
            conv.channel_id.sudo()._add_members(users=users, post_joined_message=False)

    # ------------------------------------------------------------------
    # Counters / automatic transitions
    # ------------------------------------------------------------------

    @staticmethod
    def on_customer_message(conv):
        vals = {
            "last_customer_message_date": fields.Datetime.now(),
            "message_count": conv.message_count + 1,
        }
        if conv.state == "pending_customer":
            vals["state"] = "open"
        conv.sudo().write(vals)

    @staticmethod
    def on_agent_message(conv):
        vals = {
            "last_agent_message_date": fields.Datetime.now(),
            "message_count": conv.message_count + 1,
        }
        if conv.state == "new":
            vals["state"] = "open"
        conv.sudo().write(vals)
