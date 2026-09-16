# -*- coding: utf-8 -*-
"""
Placeholder endpoint for future Mailcow/administrative event notifications.

Mailcow's open-source edition has no standardized outbound webhook system
today, so this intentionally does not trigger any sync logic yet (the real
sync path is the cron-driven IMAP engine in services/sync_service.py).
It exists so a future health/event hook has a stable, already-secured
place to land without needing a new controller.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MailcowWebhookController(http.Controller):

    @http.route("/aypatech_mail/webhook/mailcow", type="jsonrpc", auth="none", methods=["POST"], csrf=False)
    def mailcow_webhook(self, **kwargs):
        _logger.info("Received Mailcow webhook call (event=%s)", kwargs.get("event", "unknown"))
        return {"ok": True}
