# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

from ..services.utils import mask_secrets, truncate

_logger = logging.getLogger(__name__)


class TelegramLog(models.Model):
    _name = "telegram.log"
    _description = "Telegram Log"
    _order = "id desc"
    _log_access = True

    bot_id = fields.Many2one("telegram.bot", index=True, ondelete="cascade")
    company_id = fields.Many2one(related="bot_id.company_id", store=True, index=True)
    level = fields.Selection(
        [("info", "Info"), ("warning", "Warning"), ("error", "Error")], required=True, default="info",
    )
    category = fields.Selection(
        [("webhook", "Webhook"), ("api", "API"), ("delivery", "Delivery"), ("media", "Media"),
         ("config", "Configuration"), ("inbound", "Inbound")],
        required=True, default="api",
    )
    message = fields.Text(required=True)

    @api.model
    def _log(self, bot, level, category, message):
        """Create a log line. The message is sanitized: tokens/secrets never reach the table."""
        bot = bot.sudo() if bot else self.env["telegram.bot"]
        secrets = [bot.token, bot.webhook_secret, bot.webhook_key] if bot else []
        clean = truncate(mask_secrets(message, *secrets), 2000)
        log_fn = {"info": _logger.info, "warning": _logger.warning, "error": _logger.error}.get(level, _logger.info)
        log_fn("Telegram bot %s [%s]: %s", bot.id if bot else "-", category, clean)
        return self.sudo().create({
            "bot_id": bot.id if bot else False,
            "level": level,
            "category": category,
            "message": clean,
        })
