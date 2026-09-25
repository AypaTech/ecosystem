# -*- coding: utf-8 -*-
"""Connection health (SPEC §7 ``TelegramHealthService``)."""
from odoo import fields

from . import exceptions as exc
from .telegram_api import TelegramAPI
from .utils import maybe_commit


class TelegramHealthService:

    def __init__(self, env, bot, api=None):
        self.env = env
        self.bot = bot.sudo()
        self.api = api or TelegramAPI.for_bot(self.bot)

    def check(self):
        """getMe + getWebhookInfo; update bot state. Returns a dict summary."""
        bot = self.bot
        summary = {"ok": False, "problems": []}
        try:
            me = self.api.get_me()
            bot._apply_get_me(me)
            info = self.api.get_webhook_info() or {}
        except exc.TelegramError as e:
            bot._mark_error(e)
            if isinstance(e, exc.TelegramAuthError):
                bot._notify_managers_auth_failure()
            bot._log("error", "api", f"Health check failed: {e}")
            summary["problems"].append(str(e))
            return summary

        _ = self.env._
        registered_url = info.get("url") or ""
        problems = []
        if bot.connection_mode == "webhook":
            if registered_url != bot.webhook_url:
                problems.append(_("The webhook registered on Telegram does not match this database. Press Connect again."))
            if info.get("last_error_message"):
                problems.append(_("Telegram reports: %s", info["last_error_message"]))
        elif registered_url:
            problems.append(_("A webhook is still registered while the bot is in polling mode. Press Connect again."))

        vals = {
            "pending_update_count": info.get("pending_update_count") or 0,
            "last_check": fields.Datetime.now(),
        }
        if problems:
            vals.update(state="error", last_error="\n".join(problems))
            bot._log("warning", "api", "; ".join(problems))
        elif bot.webhook_registered_mode:
            vals.update(state="connected", last_error=False)
        bot.write(vals)
        summary.update(ok=not problems, problems=problems, pending=vals["pending_update_count"])
        return summary

    @staticmethod
    def check_all_bots(env):
        bots = env["telegram.bot"].sudo().search([
            ("active", "=", True), ("state", "!=", "draft"), ("token", "!=", False),
        ])
        for bot in bots:
            TelegramHealthService(env, bot).check()
            maybe_commit(env)
