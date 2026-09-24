# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.sql import create_index

from ..services.delivery import TelegramDeliveryService
from ..services.exceptions import ERROR_CLASSES


class TelegramDelivery(models.Model):
    _name = "telegram.delivery"
    _description = "Telegram Delivery"
    _order = "id desc"
    _check_company_auto = True

    message_id = fields.Many2one("telegram.message", required=True, index=True, ondelete="cascade")
    bot_id = fields.Many2one(related="message_id.bot_id", store=True, index=True)
    company_id = fields.Many2one(related="message_id.company_id", store=True, index=True)
    conversation_id = fields.Many2one(related="message_id.conversation_id", store=True, index=True)
    mail_message_id = fields.Many2one(related="message_id.mail_message_id")
    body_preview = fields.Char(related="message_id.body_preview")
    state = fields.Selection(
        [
            ("queued", "Queued"),
            ("sending", "Sending"),
            ("sent", "Sent"),
            ("failed_retryable", "Failed (will retry)"),
            ("failed_permanent", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="queued", required=True,
    )
    attempt = fields.Integer(default=0, readonly=True)
    next_retry_at = fields.Datetime(readonly=True)
    sending_started_at = fields.Datetime(readonly=True)
    parts_sent = fields.Integer(default=0, readonly=True, help="Number of parts (text chunks/files) already accepted by Telegram.")
    error_class = fields.Selection(ERROR_CLASSES, readonly=True)
    error_message = fields.Text(readonly=True)
    response_summary = fields.Char(readonly=True, help="Truncated Telegram response, never contains the token.")

    def init(self):
        super().init()
        create_index(
            self.env.cr,
            f'{self._table}_state_retry_idx',
            self._table,
            ['state', 'next_retry_at'],
        )
        create_index(
            self.env.cr,
            f'{self._table}_conversation_state_idx',
            self._table,
            ['conversation_id', 'state', 'id'],
        )

    def action_retry(self):
        """Manual retry from the Failed list (SPEC §9.5)."""
        if not self.env.user.has_group("aypatech_telegram_connector.group_telegram_user"):
            raise UserError(self.env._("You are not allowed to retry Telegram deliveries."))
        todo = self.filtered(lambda d: d.state in ("failed_permanent", "failed_retryable", "cancelled"))
        blocked = todo.filtered(lambda d: d.message_id.conversation_id.contact_id.blocked)
        if blocked and len(blocked) == len(todo):
            raise UserError(self.env._("The customer blocked the bot; the message cannot be delivered."))
        (todo - blocked).sudo().write({
            "state": "queued",
            "next_retry_at": False,
            "error_class": False,
            "error_message": False,
        })
        (todo - blocked).message_id.sudo().write({"state": "queued", "error_message": False})
        TelegramDeliveryService(self.env).notify_state((todo - blocked).message_id)
        self.env.ref("aypatech_telegram_connector.ir_cron_telegram_delivery")._trigger()
        return True

    def action_cancel(self):
        todo = self.filtered(lambda d: d.state in ("queued", "failed_retryable", "failed_permanent"))
        todo.sudo().write({"state": "cancelled"})
        todo.message_id.sudo().write({"state": "failed"})
        TelegramDeliveryService(self.env).notify_state(todo.message_id)
        return True

    @api.model
    def _cron_deliver(self):
        TelegramDeliveryService(self.env).process_queue()

    @api.model
    def _cron_watchdog(self):
        TelegramDeliveryService(self.env).watchdog()
