# -*- coding: utf-8 -*-
import ipaddress
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlparse

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import exceptions as exc
from ..services.health import TelegramHealthService
from ..services.telegram_api import ALLOWED_UPDATES, TelegramAPI
from ..services.utils import is_testing, mask_token

_logger = logging.getLogger(__name__)

WEBHOOK_ROUTE = "/telegram/webhook/"


def _generate_webhook_key():
    return secrets.token_urlsafe(32)  # 43 chars, [A-Za-z0-9_-]


def _generate_webhook_secret():
    return secrets.token_urlsafe(48)[:64]


def is_public_https_url(url):
    """True when Telegram can reach ``url``: https and not localhost/private IP."""
    try:
        parsed = urlparse(url or "")
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True  # a domain name
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)


class TelegramBot(models.Model):
    _name = "telegram.bot"
    _description = "Telegram Bot"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True, tracking=True,
        default=lambda self: self.env.company,
    )
    # --- secrets (system group only, never tracked) ---
    token = fields.Char(groups="base.group_system", copy=False)
    token_masked = fields.Char("Token", compute="_compute_token_masked", compute_sudo=True)
    webhook_key = fields.Char(
        groups="base.group_system", copy=False, default=lambda self: _generate_webhook_key(), index=True,
    )
    webhook_secret = fields.Char(groups="base.group_system", copy=False, default=lambda self: _generate_webhook_secret())
    webhook_url = fields.Char(compute="_compute_webhook_url", compute_sudo=True, groups="base.group_system")
    # --- identity ---
    bot_telegram_id = fields.Char("Telegram Bot ID", readonly=True, copy=False, index=True)
    username = fields.Char(readonly=True, copy=False)
    # --- connection ---
    connection_mode = fields.Selection(
        [("webhook", "Webhook"), ("polling", "Polling")],
        default="webhook", required=True, tracking=True,
    )
    polling_offset = fields.Char(copy=False, readonly=True, help="Last processed update_id + 1")
    webhook_registered_mode = fields.Selection(
        [("webhook", "Webhook"), ("polling", "Polling")], readonly=True, copy=False,
        help="Mode currently registered on Telegram's side.",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("connected", "Connected"), ("error", "Error"), ("disabled", "Disabled")],
        default="draft", required=True, readonly=True, tracking=True, copy=False,
    )
    auth_failed = fields.Boolean(readonly=True, copy=False, help="Telegram rejected the token; deliveries are paused.")
    last_error = fields.Text(readonly=True, copy=False)
    last_check = fields.Datetime(readonly=True, copy=False)
    pending_update_count = fields.Integer(readonly=True, copy=False)
    last_update_received = fields.Datetime(readonly=True, copy=False)
    # --- routing ---
    team_id = fields.Many2one("telegram.team", string="Default Team", tracking=True, check_company=True)
    default_user_id = fields.Many2one(
        "res.users", string="Default Agent", tracking=True,
        domain="[('share', '=', False)]",
    )
    route_ids = fields.One2many("telegram.route", "bot_id", string="Routes")
    # --- customer facing ---
    welcome_message = fields.Text(translate=True, tracking=True)
    privacy_notice = fields.Text(translate=True, tracking=True)
    auto_link_partner = fields.Boolean(
        tracking=True,
        help="Link the Telegram customer to an existing contact when exactly one contact "
             "matches the phone number the customer shared.",
    )
    store_media = fields.Boolean(default=True, tracking=True)
    max_media_size_mb = fields.Integer(default=20, tracking=True)
    # --- stats (dashboard) ---
    conversation_ids = fields.One2many("telegram.conversation", "bot_id")
    open_conversation_count = fields.Integer(compute="_compute_dashboard_stats")
    unassigned_conversation_count = fields.Integer(compute="_compute_dashboard_stats")
    failed_delivery_count = fields.Integer(compute="_compute_dashboard_stats")
    messages_today_count = fields.Integer(compute="_compute_dashboard_stats")
    color = fields.Integer(compute="_compute_color")

    _webhook_key_unique = models.Constraint("UNIQUE(webhook_key)", "The webhook key must be unique.")
    _bot_company_unique = models.Constraint(
        "UNIQUE(bot_telegram_id, company_id)",
        "This Telegram bot is already configured for this company.",
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("token")
    def _compute_token_masked(self):
        for bot in self:
            bot.token_masked = mask_token(bot.token)

    @api.depends("webhook_key")
    def _compute_webhook_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_str("web.base.url").rstrip("/")
        for bot in self:
            bot.webhook_url = f"{base_url}{WEBHOOK_ROUTE}{bot.webhook_key}" if bot.webhook_key else False

    @api.depends("state")
    def _compute_color(self):
        colors = {"draft": 0, "connected": 10, "error": 1, "disabled": 3}
        for bot in self:
            bot.color = colors.get(bot.state, 0)

    def _compute_dashboard_stats(self):
        Conversation = self.env["telegram.conversation"]
        open_states = Conversation._open_states()
        open_data = dict(Conversation._read_group(
            [("bot_id", "in", self.ids), ("state", "in", open_states)], ["bot_id"], ["__count"],
        ))
        unassigned = dict(Conversation._read_group(
            [("bot_id", "in", self.ids), ("state", "in", open_states), ("user_id", "=", False)],
            ["bot_id"], ["__count"],
        ))
        since = fields.Datetime.now() - timedelta(hours=24)
        failed = dict(self.env["telegram.delivery"]._read_group(
            [("bot_id", "in", self.ids), ("state", "=", "failed_permanent"), ("write_date", ">=", since)],
            ["bot_id"], ["__count"],
        ))
        today = fields.Datetime.to_datetime(fields.Date.context_today(self))
        messages = dict(self.env["telegram.message"]._read_group(
            [("bot_id", "in", self.ids), ("create_date", ">=", today)], ["bot_id"], ["__count"],
        ))
        for bot in self:
            bot.open_conversation_count = open_data.get(bot, 0)
            bot.unassigned_conversation_count = unassigned.get(bot, 0)
            bot.failed_delivery_count = failed.get(bot, 0)
            bot.messages_today_count = messages.get(bot, 0)

    # ------------------------------------------------------------------
    # Constraints / CRUD
    # ------------------------------------------------------------------

    @api.constrains("max_media_size_mb")
    def _check_max_media_size(self):
        for bot in self:
            if bot.max_media_size_mb <= 0:
                raise ValidationError(self.env._("The maximum media size must be positive."))

    @api.constrains("webhook_key")
    def _check_webhook_key(self):
        for bot in self.sudo():
            if bot.webhook_key and len(bot.webhook_key) < 32:
                raise ValidationError(self.env._("The webhook key must be at least 32 characters long."))

    def write(self, vals):
        if "token" in vals:
            vals["token"] = (vals["token"] or "").strip() or False
            # a new token must be validated again
            vals.setdefault("state", "draft")
            vals.setdefault("auth_failed", False)
        res = super().write(vals)
        if "active" in vals:
            if not vals["active"]:
                self.sudo().write({"state": "disabled"})
            else:
                self.filtered(lambda b: b.state == "disabled").sudo().write({"state": "draft"})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("token"):
                vals["token"] = vals["token"].strip()
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _api(self):
        self.ensure_one()
        return TelegramAPI.for_bot(self)

    def _log(self, level, category, message):
        self.env["telegram.log"].sudo()._log(self, level, category, message)

    def _get_polling_offset(self):
        self.ensure_one()
        try:
            return int(self.polling_offset) if self.polling_offset else None
        except ValueError:
            return None

    def _set_polling_offset(self, update_id):
        self.ensure_one()
        self.sudo().polling_offset = str(int(update_id) + 1)

    def _check_manager(self):
        if not self.env.user.has_group("aypatech_telegram_connector.group_telegram_manager"):
            raise UserError(self.env._("Only Telegram managers can do this."))

    def _mark_error(self, error):
        """Store a sanitized error on the bot (error is a TelegramError or text)."""
        message = str(error)
        vals = {"state": "error", "last_error": message, "last_check": fields.Datetime.now()}
        if isinstance(error, exc.TelegramAuthError):
            vals["auth_failed"] = True
        self.sudo().write(vals)

    def _notify_managers_auth_failure(self):
        """SPEC §12: auth errors notify managers through an activity."""
        group = self.env.ref("aypatech_telegram_connector.group_telegram_manager", raise_if_not_found=False)
        root = self.env.ref("base.user_root")
        users = group.sudo().all_user_ids.filtered(
            lambda u: u.active and not u.share and u != root
        ).sorted("id") if group else self.env["res.users"]
        activity_type = self.env.ref("mail.mail_activity_data_warning", raise_if_not_found=False) \
            or self.env.ref("mail.mail_activity_data_todo")
        for bot in self:
            existing = bot.sudo().activity_ids.filtered(lambda a: a.activity_type_id == activity_type)
            if existing:
                continue
            for user in users[:1] or self.env.user:
                bot.sudo().activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=user.id,
                    summary=self.env._("Telegram rejected the bot token"),
                    note=self.env._(
                        "Telegram answered 'Unauthorized' for bot %(bot)s. Outgoing messages are paused. "
                        "Paste a valid token from @BotFather and press Test.", bot=bot.name,
                    ),
                )

    # ------------------------------------------------------------------
    # Actions (buttons)
    # ------------------------------------------------------------------

    def action_test_connection(self):
        """getMe: validate the token and fill bot id/username."""
        self._check_manager()
        for bot in self:
            try:
                info = bot._api().get_me()
            except exc.TelegramError as e:
                bot._mark_error(e)
                bot._log("error", "api", str(e))
                raise UserError(bot._explain_error(e)) from None
            bot._apply_get_me(info)
            bot._log("info", "api", self.env._("Token validated for @%s", info.get("username")))
        return self._notification(self.env._("Connection successful."), "success")

    def _apply_get_me(self, info):
        self.ensure_one()
        was_auth_failed = self.auth_failed
        vals = {
            "bot_telegram_id": str(info.get("id")),
            "username": info.get("username"),
            "auth_failed": False,
            "last_error": False,
            "last_check": fields.Datetime.now(),
        }
        if self.state in ("draft", "error"):
            vals["state"] = "connected" if self.webhook_registered_mode else "draft"
        self.sudo().write(vals)
        if was_auth_failed:
            self.env.ref("aypatech_telegram_connector.ir_cron_telegram_delivery")._trigger()

    def action_connect(self):
        """Register the webhook, or switch to polling."""
        self._check_manager()
        for bot in self:
            bot._connect()
        return self._notification(self.env._("Bot connected."), "success")

    def _connect(self):
        self.ensure_one()
        bot = self.sudo()
        if not bot.token:
            raise UserError(self.env._("Paste the bot token from @BotFather first."))
        api = bot._api()
        try:
            info = api.get_me()
            self._apply_get_me(info)
            if bot.connection_mode == "webhook":
                if not is_public_https_url(bot.webhook_url):
                    raise UserError(self.env._(
                        "Telegram cannot reach %(url)s. Webhook mode needs a public HTTPS address "
                        "(check the 'web.base.url' system parameter) or use Polling mode.",
                        url=bot.webhook_url,
                    ))
                api.set_webhook(bot.webhook_url, bot.webhook_secret, allowed_updates=ALLOWED_UPDATES)
            else:
                # getUpdates fails with 409 while a webhook is set
                api.delete_webhook(drop_pending_updates=False)
        except exc.TelegramError as e:
            bot._mark_error(e)
            bot._log("error", "config", str(e))
            raise UserError(self._explain_error(e)) from None
        bot.write({
            "state": "connected",
            "webhook_registered_mode": bot.connection_mode,
            "last_error": False,
            "last_check": fields.Datetime.now(),
        })
        bot._log("info", "config", self.env._("Connected in %s mode.", bot.connection_mode))
        if bot.connection_mode == "polling":
            self.env.ref("aypatech_telegram_connector.ir_cron_telegram_polling")._trigger()

    def action_disconnect(self):
        self._check_manager()
        for bot in self.sudo():
            try:
                if bot.token and bot.webhook_registered_mode == "webhook":
                    bot._api().delete_webhook()
            except exc.TelegramError as e:
                bot._log("warning", "config", str(e))
            bot.write({"state": "draft", "webhook_registered_mode": False})
        return True

    def action_health_check(self):
        self._check_manager()
        for bot in self:
            TelegramHealthService(self.env, bot).check()
        return self._notification(self.env._("Health check finished. See the bot status."), "info")

    def action_regenerate_webhook_secret(self):
        """New random webhook key+secret. The webhook must be registered again."""
        self._check_manager()
        for bot in self.sudo():
            bot.write({"webhook_key": _generate_webhook_key(), "webhook_secret": _generate_webhook_secret()})
            if bot.state == "connected" and bot.connection_mode == "webhook":
                bot._connect()
        return True

    def action_open_setup_wizard(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("aypatech_telegram_connector.action_telegram_setup_wizard")
        if len(self) == 1:
            action["context"] = {"default_bot_id": self.id}
        return action

    def action_open_conversations(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("aypatech_telegram_connector.action_telegram_conversation")
        action["domain"] = [("bot_id", "=", self.id)]
        action["context"] = {"search_default_filter_open": 1}
        return action

    def action_open_failed_deliveries(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("aypatech_telegram_connector.action_telegram_delivery_failed")
        action["domain"] = [("bot_id", "=", self.id), ("state", "=", "failed_permanent")]
        return action

    def action_open_logs(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("aypatech_telegram_connector.action_telegram_log")
        action["domain"] = [("bot_id", "=", self.id)]
        return action

    def _notification(self, message, kind):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": message, "type": kind, "sticky": False,
                       "next": {"type": "ir.actions.client", "tag": "soft_reload"}},
        }

    # ------------------------------------------------------------------
    # Crons
    # ------------------------------------------------------------------

    @api.model
    def _cron_health_check(self):
        TelegramHealthService.check_all_bots(self.env)

    @api.model
    def _cron_cleanup(self):
        """Retention (SPEC §15): drop raw payloads and old logs, batch by batch."""
        ICP = self.env["ir.config_parameter"].sudo()

        def days(key, default):
            return ICP.get_int(key, default)

        now = fields.Datetime.now()
        payload_limit = now - timedelta(days=days("telegram.payload_retention_days", 7))
        log_limit = now - timedelta(days=days("telegram.log_retention_days", 30))
        Update = self.env["telegram.update"].sudo()
        while True:
            updates = Update.search([
                ("received_at", "<", payload_limit), ("payload", "!=", False), ("state", "!=", "pending"),
            ], limit=1000)
            if not updates:
                break
            updates.write({"payload": False})
            if is_testing() or self.env["ir.cron"]._commit_progress(len(updates)) <= 0:
                break
        Log = self.env["telegram.log"].sudo()
        while True:
            logs = Log.search([("create_date", "<", log_limit)], limit=1000)
            if not logs:
                break
            logs.unlink()
            if is_testing() or self.env["ir.cron"]._commit_progress(len(logs)) <= 0:
                break

    def _explain_error(self, error):
        """Turn a TelegramError into an actionable message (SPEC §11)."""
        _ = self.env._
        if isinstance(error, exc.TelegramAuthError):
            return _("Telegram rejected the token. Copy it again from @BotFather (/mybots → API Token).")
        if isinstance(error, exc.TelegramTransientError):
            return _("Odoo could not reach api.telegram.org. Check the server's internet access and try again. (%s)", error.description)
        if isinstance(error, exc.TelegramBadRequest) and "webhook" in (error.description or "").lower():
            return _("Telegram refused the webhook URL: %s. Make sure the site is public and uses a valid certificate.", error.description)
        if isinstance(error, exc.TelegramConflict):
            return _("Another program is reading this bot's updates (409 Conflict). Stop it or use webhook mode.")
        return _("Telegram error: %s", error.description)
