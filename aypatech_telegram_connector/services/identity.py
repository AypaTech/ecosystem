# -*- coding: utf-8 -*-
"""Telegram identity ↔ Odoo partner (SPEC §7 ``TelegramIdentityService``).

Rules:
* one ``telegram.contact`` per (bot, telegram user) — enforced by a unique constraint;
* a new contact gets its own new partner;
* an existing partner is linked automatically only when ``auto_link_partner`` is on
  **and** exactly one partner matches the phone number the customer explicitly
  shared about *themselves* (contact message whose user_id is the sender).
"""
import logging
import re

import psycopg2

from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)


def _digits(phone):
    return re.sub(r"\D", "", phone or "")


class TelegramIdentityService:

    def __init__(self, env, bot):
        self.env = env
        self.bot = bot.sudo()

    # ------------------------------------------------------------------
    # Contact / chat
    # ------------------------------------------------------------------

    def get_or_create_contact(self, tg_user):
        """``tg_user`` is Telegram's ``User`` object (``message.from``)."""
        Contact = self.env["telegram.contact"].sudo()
        user_id = str(tg_user["id"])
        vals = {
            "username": tg_user.get("username") or False,
            "first_name": tg_user.get("first_name") or False,
            "last_name": tg_user.get("last_name") or False,
            "language_code": tg_user.get("language_code") or False,
        }
        domain = [("bot_id", "=", self.bot.id), ("telegram_user_id", "=", user_id)]
        contact = Contact.search(domain, limit=1)
        if contact:
            changed = {k: v for k, v in vals.items() if (contact[k] or False) != v and v}
            if changed:
                contact.write(changed)
            if contact.blocked:
                # the customer writes again: they unblocked the bot
                contact.blocked = False
            return contact, False
        contact = self._create_race_safe(Contact, domain, {
            **vals, "bot_id": self.bot.id, "telegram_user_id": user_id,
        })
        return contact, True

    def get_or_create_chat(self, tg_chat, contact):
        Chat = self.env["telegram.chat"].sudo()
        chat_id = str(tg_chat["id"])
        domain = [("bot_id", "=", self.bot.id), ("telegram_chat_id", "=", chat_id)]
        chat = Chat.search(domain, limit=1)
        title = tg_chat.get("title") or False
        if chat:
            if contact and chat.contact_id != contact:
                chat.contact_id = contact
            if title and chat.title != title:
                chat.title = title
            return chat
        return self._create_race_safe(Chat, domain, {
            "bot_id": self.bot.id,
            "telegram_chat_id": chat_id,
            "chat_type": tg_chat.get("type") or "private",
            "title": title,
            "contact_id": contact.id if contact else False,
        })

    def _create_race_safe(self, model, domain, vals):
        """Create, or return the row a concurrent worker just created (unique constraint)."""
        try:
            with mute_logger("odoo.sql_db"), self.env.cr.savepoint():
                return model.create(vals)
        except psycopg2.IntegrityError:
            record = model.search(domain, limit=1)
            if not record:
                raise
            return record

    # ------------------------------------------------------------------
    # Partner
    # ------------------------------------------------------------------

    def ensure_partner(self, contact):
        if contact.partner_id:
            return contact.partner_id
        partner = self.env["res.partner"].sudo().create(self._partner_vals(contact))
        contact.partner_id = partner
        return partner

    def _partner_vals(self, contact):
        lang = False
        if contact.language_code:
            code = contact.language_code.replace("-", "_")
            langs = self.env["res.lang"].sudo().search([("active", "=", True)])
            match = langs.filtered(lambda l: l.code == code) or langs.filtered(
                lambda l: l.code.split("_")[0] == code.split("_")[0])
            lang = match[:1].code
        vals = {
            "name": contact.name,
            "company_id": False,
            "comment": self.env._("Created from Telegram (bot @%s)", self.bot.username or self.bot.name),
        }
        if lang:
            vals["lang"] = lang
        return vals

    def link_shared_phone(self, contact, tg_contact, sender_id):
        """Handle a ``contact`` message. Only the sender's *own* phone is considered.

        Returns the partner the contact is linked to after the operation.
        """
        phone = (tg_contact or {}).get("phone_number")
        if not phone or str((tg_contact or {}).get("user_id") or "") != str(sender_id):
            return contact.partner_id
        contact.phone = phone
        partner = contact.partner_id
        if self.bot.auto_link_partner:
            match = self._find_unique_partner_by_phone(phone, exclude=partner)
            if match:
                _logger.info("Telegram contact %s linked to partner %s by shared phone", contact.id, match.id)
                contact.partner_id = match
                partner = match
        store_phone = self.env["ir.config_parameter"].sudo().get_param("telegram.contact_phone_to_partner") == "True"
        if store_phone and partner and not partner.phone:
            partner.sudo().phone = phone
        return partner

    def _find_unique_partner_by_phone(self, phone, exclude=None):
        digits = _digits(phone)
        if len(digits) < 7:
            return self.env["res.partner"]
        tail = digits[-9:]
        candidates = self.env["res.partner"].sudo().search([("phone", "ilike", tail[-4:])], limit=200)
        matches = candidates.filtered(lambda p: _digits(p.phone).endswith(tail))
        if exclude:
            matches -= exclude
        company = self.bot.company_id
        matches = matches.filtered(lambda p: not p.company_id or p.company_id == company)
        return matches if len(matches) == 1 else self.env["res.partner"]
