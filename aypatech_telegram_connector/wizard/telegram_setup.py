# -*- coding: utf-8 -*-
"""Five-minute setup wizard (SPEC §11). No step requires files, env vars or server config."""
from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.telegram_bot import is_public_https_url
from ..services import exceptions as exc
from ..services.gateway import TelegramPoller
from ..services.telegram_api import TelegramAPI

STEPS = [
    ("intro", "BotFather"),
    ("token", "Token"),
    ("mode", "Company & mode"),
    ("team", "Team"),
    ("messages", "Messages"),
    ("test", "Live test"),
    ("done", "Done"),
]


class TelegramSetupWizard(models.TransientModel):
    _name = "telegram.setup.wizard"
    _description = "Telegram Setup Wizard"

    step = fields.Selection(STEPS, default="intro", required=True)
    bot_id = fields.Many2one("telegram.bot")
    token = fields.Char()
    bot_username = fields.Char(readonly=True)
    bot_name = fields.Char("Display Name")
    bot_telegram_id = fields.Char(readonly=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    base_url = fields.Char(compute="_compute_base_url")
    public_https = fields.Boolean(compute="_compute_base_url")
    connection_mode = fields.Selection(
        [("webhook", "Webhook (instant, needs a public HTTPS address)"),
         ("polling", "Polling (works anywhere, ~1 minute delay)")],
        default=lambda self: "webhook" if self._default_public() else "polling",
    )
    team_id = fields.Many2one("telegram.team", domain="[('company_id', '=', company_id)]")
    default_user_id = fields.Many2one("res.users", domain="[('share', '=', False)]")
    welcome_message = fields.Text(default=lambda self: self.env._(
        "Hello! 👋 Thanks for contacting us. An agent will answer you here shortly."))
    privacy_notice = fields.Text(default=lambda self: self.env._(
        "Your messages and the name/username of your Telegram account are stored in our "
        "customer service system to answer your requests."))
    connected_at = fields.Datetime(readonly=True)
    test_received = fields.Boolean(readonly=True)

    # ------------------------------------------------------------------

    @api.model
    def _default_public(self):
        return is_public_https_url(self.env["ir.config_parameter"].sudo().get_str("web.base.url"))

    @api.depends("company_id")
    def _compute_base_url(self):
        url = self.env["ir.config_parameter"].sudo().get_str("web.base.url")
        for wizard in self:
            wizard.base_url = url
            wizard.public_https = is_public_https_url(url)

    @api.model
    def default_get(self, fields_list):
        if not self.env.is_system():
            raise UserError(self.env._("Only administrators can connect Telegram bots (bot tokens are secrets)."))
        res = super().default_get(fields_list)
        bot = self.env["telegram.bot"].browse(res.get("bot_id") or self.env.context.get("default_bot_id"))
        if bot:
            res.update({
                "bot_name": bot.name,
                "company_id": bot.company_id.id,
                "connection_mode": bot.connection_mode,
                "team_id": bot.team_id.id,
                "default_user_id": bot.default_user_id.id,
                "welcome_message": bot.welcome_message or res.get("welcome_message"),
                "privacy_notice": bot.privacy_notice or res.get("privacy_notice"),
                "bot_username": bot.username,
            })
        return res

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def _go(self, step):
        self.step = step
        return self._reopen()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def action_back(self):
        keys = [k for k, _v in STEPS]
        idx = keys.index(self.step)
        return self._go(keys[max(idx - 1, 0)])

    def action_next(self):
        handler = getattr(self, f"_validate_{self.step}", None)
        if handler:
            handler()
        keys = [k for k, _v in STEPS]
        return self._go(keys[min(keys.index(self.step) + 1, len(keys) - 1)])

    def _validate_token(self):
        """Step 2: validate with getMe."""
        token = (self.token or "").strip()
        if not token and self.bot_id and self.bot_id.sudo().token:
            token = self.bot_id.sudo().token
        if not token:
            raise UserError(self.env._("Paste the token @BotFather gave you (looks like 123456789:AA...)."))
        try:
            info = TelegramAPI(token).get_me()
        except exc.TelegramAuthError:
            raise UserError(self.env._(
                "Telegram rejected this token. Open @BotFather → /mybots → your bot → API Token and copy it again.")) from None
        except exc.TelegramError as e:
            raise UserError(self.env._(
                "Odoo could not reach Telegram (%s). Check that this server can access https://api.telegram.org.",
                e.description)) from None
        self.write({
            "token": token,
            "bot_username": info.get("username"),
            "bot_telegram_id": str(info.get("id")),
            "bot_name": self.bot_name or info.get("first_name") or info.get("username"),
        })

    def _validate_mode(self):
        if self.connection_mode == "webhook" and not self.public_https:
            raise UserError(self.env._(
                "Webhook mode needs a public HTTPS address, but this database's URL is %(url)s. "
                "Choose Polling, or set the 'web.base.url' system parameter to your public https:// address.",
                url=self.base_url or "-"))

    def _validate_messages(self):
        """Step 7: create/update the bot and connect."""
        self._connect()

    # ------------------------------------------------------------------
    # Connect / test
    # ------------------------------------------------------------------

    def _connect(self):
        Bot = self.env["telegram.bot"].sudo()
        vals = {
            "name": self.bot_name or self.bot_username or "Telegram Bot",
            "company_id": self.company_id.id,
            "connection_mode": self.connection_mode,
            "team_id": self.team_id.id,
            "default_user_id": self.default_user_id.id,
            "welcome_message": self.welcome_message,
            "privacy_notice": self.privacy_notice,
        }
        bot = self.bot_id.sudo()
        if not bot:
            bot = Bot.search([
                ("bot_telegram_id", "=", self.bot_telegram_id), ("company_id", "=", self.company_id.id),
                ("active", "in", (True, False)),
            ], limit=1)
        if self.token and (not bot or self.token != bot.token):
            vals["token"] = self.token
        if bot:
            vals["active"] = True
            bot.write(vals)
        else:
            bot = Bot.create(vals)
        bot._connect()
        self.write({"bot_id": bot.id, "connected_at": fields.Datetime.now(), "token": False})

    def action_check_test(self):
        """Step 8: did an update arrive since we connected?"""
        bot = self.bot_id.sudo()
        if not bot:
            raise UserError(self.env._("Connect the bot first."))
        if bot.connection_mode == "polling":
            TelegramPoller(self.env, bot).poll()
        received = self.env["telegram.update"].sudo().search_count([
            ("bot_id", "=", bot.id), ("received_at", ">=", self.connected_at or fields.Datetime.now()),
        ])
        self.test_received = bool(received)
        if received:
            self.env.ref("aypatech_telegram_connector.ir_cron_telegram_process_updates").sudo()._trigger()
        return self._reopen()

    def action_open_dashboard(self):
        return self.env["ir.actions.act_window"]._for_xml_id("aypatech_telegram_connector.action_telegram_dashboard")
