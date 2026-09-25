# -*- coding: utf-8 -*-
"""Webhook endpoint (SPEC §8). Validate → store raw update → trigger → 200. Nothing else."""
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 1024 * 1024  # Telegram updates are small; media is fetched separately
SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


class TelegramWebhookController(http.Controller):

    @http.route(
        "/telegram/webhook/<string:webhook_key>",
        type="http", auth="public", methods=["POST"], csrf=False, save_session=False,
    )
    def telegram_webhook(self, webhook_key, **kwargs):
        # 1. bot lookup (unknown key → bare 404)
        if len(webhook_key) < 32:
            return self._response(404)
        bot = request.env["telegram.bot"].sudo().search(
            [("webhook_key", "=", webhook_key), ("active", "=", True)], limit=1,
        )
        if not bot:
            return self._response(404)

        # 2. secret header, constant time
        received = request.httprequest.headers.get(SECRET_HEADER, "")
        if not bot.webhook_secret or not hmac.compare_digest(received.encode(), bot.webhook_secret.encode()):
            bot._log("warning", "webhook", "Rejected webhook call with a wrong secret token.")
            return self._response(403)

        # 3. body size + JSON
        length = request.httprequest.content_length
        if length is not None and length > MAX_BODY_BYTES:
            return self._response(413)
        raw = request.httprequest.get_data(cache=False, as_text=False)
        if len(raw) > MAX_BODY_BYTES:
            return self._response(413)
        try:
            update = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            bot._log("warning", "webhook", "Rejected malformed JSON body.")
            return self._response(400)
        if not isinstance(update, dict) or not isinstance(update.get("update_id"), int):
            return self._response(400)

        # 4. inbox (duplicate update_id → already stored → still 200)
        stored = request.env["telegram.update"].sudo()._store(bot, update, "webhook")
        if stored:
            request.env.ref("aypatech_telegram_connector.ir_cron_telegram_process_updates").sudo()._trigger()
        return self._response(200)

    @staticmethod
    def _response(status):
        return request.make_response("", status=status, headers=[("Content-Type", "text/plain")])
