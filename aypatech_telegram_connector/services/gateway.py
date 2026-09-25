# -*- coding: utf-8 -*-
"""Inbound entry point (SPEC §7 ``TelegramGateway``, §8) and polling."""
import logging

from odoo import fields

from . import exceptions as exc
from .conversation import TelegramConversationService
from .identity import TelegramIdentityService
from .message import TelegramMessageService
from .telegram_api import ALLOWED_UPDATES, TelegramAPI

_logger = logging.getLogger(__name__)

DONE = "done"
IGNORED = "ignored"


class TelegramGateway:

    def __init__(self, env, bot):
        self.env = env
        self.bot = bot.sudo()

    def handle(self, update):
        """Dispatch one raw update. Returns ``"done"`` or ``"ignored"``."""
        if "message" in update:
            return self._handle_message(update["message"], update.get("update_id"))
        if "edited_message" in update:
            return self._handle_message(update["edited_message"], update.get("update_id"), edited=True)
        if "my_chat_member" in update:
            return self._handle_my_chat_member(update["my_chat_member"])
        self.bot._log("info", "inbound", f"Ignored update type: {', '.join(k for k in update if k != 'update_id')}")
        return IGNORED

    # ------------------------------------------------------------------

    def _handle_message(self, msg, update_id, edited=False):
        chat = msg.get("chat") or {}
        sender = msg.get("from") or {}
        if chat.get("type") != "private":
            self.bot._log("info", "inbound", f"Ignored message from a {chat.get('type')} chat (only private chats are supported).")
            return IGNORED
        if not sender or sender.get("is_bot"):
            return IGNORED

        identity = TelegramIdentityService(self.env, self.bot)
        contact, is_new_customer = identity.get_or_create_contact(sender)
        tg_chat = identity.get_or_create_chat(chat, contact)
        partner = identity.ensure_partner(contact)
        text = msg.get("text") or msg.get("caption") or ""

        conv_service = TelegramConversationService(self.env, self.bot)
        conversation, _created = conv_service.get_or_create(
            tg_chat, contact, partner, text=text, is_new_customer=is_new_customer,
        )

        if msg.get("contact") and not edited:
            linked = identity.link_shared_phone(contact, msg["contact"], sender.get("id"))
            if linked and linked != conversation.partner_id:
                self._switch_customer_partner(conversation, linked)

        messages = TelegramMessageService(self.env)
        messages.create_inbound(conversation, msg, update_id=update_id, edited=edited)
        if not edited:
            conv_service.on_customer_message(conversation)
            if text.strip().split("@")[0].split(" ")[0] == "/start":
                self._send_welcome(conversation, messages)
        self.bot.sudo().last_update_received = fields.Datetime.now()
        return DONE

    def _switch_customer_partner(self, conversation, partner):
        """The customer was linked to an existing partner: replace them in the channel."""
        old = conversation.partner_id
        conversation.partner_id = partner
        channel = conversation.channel_id.sudo()
        if channel:
            channel._add_members(partners=partner, post_joined_message=False)
            channel.channel_member_ids.filtered(lambda m: m.partner_id == old).unlink()

    def _send_welcome(self, conversation, messages):
        bot = self.bot.with_context(lang=conversation.partner_id.lang or self.env.lang)
        texts = [t.strip() for t in (bot.welcome_message, bot.privacy_notice) if t and t.strip()]
        if texts:
            messages.post_bot_reply(conversation, "\n\n".join(texts))

    def _handle_my_chat_member(self, data):
        status = (data.get("new_chat_member") or {}).get("status")
        user = data.get("from") or {}
        if (data.get("chat") or {}).get("type") != "private" or not user:
            return IGNORED
        contact = self.env["telegram.contact"].sudo().search([
            ("bot_id", "=", self.bot.id), ("telegram_user_id", "=", str(user.get("id"))),
        ], limit=1)
        if not contact:
            return IGNORED
        if status == "kicked":
            contact.blocked = True
        elif status == "member":
            contact.blocked = False
        return DONE


class TelegramPoller:
    """getUpdates for one bot in polling mode (SPEC §8 "Polling mode")."""

    def __init__(self, env, bot, api=None):
        self.env = env
        self.bot = bot.sudo()
        self.api = api or TelegramAPI.for_bot(self.bot)

    def poll(self, limit=100):
        bot = self.bot
        try:
            if bot.webhook_registered_mode != "polling":
                self.api.delete_webhook(drop_pending_updates=False)
                bot.webhook_registered_mode = "polling"
            try:
                updates = self._get_updates(limit)
            except exc.TelegramConflict:
                # a webhook is still set (or was re-set elsewhere): remove it once and retry
                self.api.delete_webhook(drop_pending_updates=False)
                updates = self._get_updates(limit)
        except exc.TelegramConflict as e:
            bot._mark_error(e)
            bot._log("error", "api", f"Polling conflict: {e}")
            return 0
        except exc.TelegramError as e:
            if isinstance(e, exc.TelegramAuthError):
                bot._mark_error(e)
                bot._notify_managers_auth_failure()
            bot._log("warning", "api", f"Polling failed: {e}")
            return 0

        Update = self.env["telegram.update"].sudo()
        stored = 0
        max_id = None
        for update in updates or []:
            if "update_id" not in update:
                continue
            if Update._store(bot, update, "polling"):
                stored += 1
            max_id = max(max_id or 0, int(update["update_id"]))
        vals = {"last_check": fields.Datetime.now()}
        if bot.state == "error" and not bot.auth_failed:
            vals.update(state="connected", last_error=False)
        if max_id is not None:
            bot._set_polling_offset(max_id)
            vals["last_update_received"] = fields.Datetime.now()
        bot.write(vals)
        return stored

    def _get_updates(self, limit):
        return self.api.get_updates(
            offset=self.bot._get_polling_offset(), limit=limit, timeout=0, allowed_updates=ALLOWED_UPDATES,
        )
