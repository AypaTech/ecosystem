# -*- coding: utf-8 -*-
"""Outbound delivery queue (SPEC §7 ``TelegramDeliveryService``, §9, §12).

Flow per delivery:
1. claim (``FOR UPDATE SKIP LOCKED``, only the head of each conversation queue),
   set ``sending`` and commit *before* any HTTP call;
2. send each part not yet accepted (``parts_sent``), commit after each part;
3. on error classify → retry with backoff / honour 429 / fail permanently.
"""
import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import fields

from . import exceptions as exc
from .conversation import TelegramConversationService
from .formatter import html_to_caption, html_to_telegram
from .media import TelegramMediaService
from .telegram_api import TelegramAPI
from .utils import mask_secrets, maybe_commit, truncate

_logger = logging.getLogger(__name__)

BACKOFF_SECONDS = [30, 120, 600, 1800, 7200]
STUCK_AFTER = timedelta(minutes=10)
DEFAULT_MAX_ATTEMPTS = 5


class TelegramDeliveryService:

    def __init__(self, env, api_factory=None):
        self.env = env
        # tests inject a fake API; production builds one per bot
        self._api_factory = api_factory or TelegramAPI.for_bot
        self._apis = {}

    def _api(self, bot):
        if bot.id not in self._apis:
            self._apis[bot.id] = self._api_factory(bot)
        return self._apis[bot.id]

    def _max_attempts(self):
        value = self.env["ir.config_parameter"].sudo().get_param("telegram.max_attempts")
        return int(value) if value and value.isdigit() and int(value) > 0 else DEFAULT_MAX_ATTEMPTS

    # ------------------------------------------------------------------
    # Queue
    # ------------------------------------------------------------------

    def _claim(self, limit):
        # the raw select joins bots too (auth_failed/active may have changed this round)
        self.env["telegram.delivery"].flush_model()
        self.env["telegram.bot"].flush_model(["active", "auth_failed"])
        self.env.cr.execute(
            """
            SELECT d.id
              FROM telegram_delivery d
              JOIN telegram_bot b ON b.id = d.bot_id
             WHERE d.state IN ('queued', 'failed_retryable')
               AND (d.next_retry_at IS NULL OR d.next_retry_at <= %s)
               AND b.active IS TRUE
               AND b.auth_failed IS NOT TRUE
               AND NOT EXISTS (
                    SELECT 1 FROM telegram_delivery p
                     WHERE p.conversation_id = d.conversation_id
                       AND p.id < d.id
                       AND p.state IN ('queued', 'sending', 'failed_retryable'))
             ORDER BY d.id
             LIMIT %s
               FOR UPDATE OF d SKIP LOCKED
            """,
            # same clock as the one that wrote next_retry_at (SQL now() is frozen per transaction)
            (fields.Datetime.now(), limit),
        )
        return self.env["telegram.delivery"].sudo().browse([r[0] for r in self.env.cr.fetchall()])

    def process_queue(self, batch_size=50, max_rounds=100):
        """Send what can be sent. Returns the number of deliveries handled."""
        handled = 0
        for _round in range(max_rounds):
            deliveries = self._claim(batch_size)
            if not deliveries:
                break
            now = fields.Datetime.now()
            deliveries.write({"state": "sending", "sending_started_at": now})
            deliveries.message_id.write({"state": "sending"})
            maybe_commit(self.env)
            for delivery in deliveries:
                self.send(delivery)
                handled += 1
                maybe_commit(self.env)
        return handled

    def watchdog(self):
        """``sending`` for more than 10 minutes → ``failed_retryable`` (SPEC §16)."""
        limit = fields.Datetime.now() - STUCK_AFTER
        stuck = self.env["telegram.delivery"].sudo().search([
            ("state", "=", "sending"), ("sending_started_at", "<", limit),
        ])
        if stuck:
            stuck.write({
                "state": "failed_retryable",
                "next_retry_at": fields.Datetime.now(),
                "error_class": exc.ERROR_INTERNAL,
                "error_message": "Stuck in 'sending' (worker interrupted); will retry.",
            })
            stuck.message_id.write({"state": "queued"})
            for delivery in stuck:
                delivery.bot_id._log("warning", "delivery", f"Delivery {delivery.id} was stuck and is re-queued.")
            self.env.ref("aypatech_telegram_connector.ir_cron_telegram_delivery")._trigger()
        return len(stuck)

    # ------------------------------------------------------------------
    # Sending one delivery
    # ------------------------------------------------------------------

    def build_parts(self, tg_message):
        """Deterministic list of parts for a message (same result on every retry)."""
        body = tg_message.mail_message_id.sudo().body or ""
        attachments = tg_message.attachment_ids.sorted("id")
        parts = []
        if attachments:
            caption, overflow = html_to_caption(body)
            parts.append({"type": "file", "attachment": attachments[0], "caption": caption})
            parts += [{"type": "text", "text": t} for t in overflow]
            parts += [{"type": "file", "attachment": a, "caption": ""} for a in attachments[1:]]
        else:
            parts = [{"type": "text", "text": t} for t in html_to_telegram(body)]
        return parts

    def _reply_to(self, tg_message):
        parent = tg_message.mail_message_id.sudo().parent_id
        if not parent:
            return None
        ref = self.env["telegram.message"].sudo().search(
            [("mail_message_id", "=", parent.id), ("telegram_message_id", "!=", False)], limit=1)
        return ref.telegram_message_id or None

    def send(self, delivery):
        delivery = delivery.sudo()
        tg_message = delivery.message_id
        conversation = tg_message.conversation_id
        bot = tg_message.bot_id
        chat_id = conversation.chat_id.telegram_chat_id
        delivery.attempt += 1
        try:
            api = self._api(bot)
            media = TelegramMediaService(self.env, bot, api=api)
            if not chat_id:
                raise exc.TelegramNotFound("The Telegram identity of this conversation was removed.")
            parts = self.build_parts(tg_message)
            if not parts:
                raise exc.TelegramBadRequest("Nothing to send (empty message).")
            reply_to = self._reply_to(tg_message)
            for index, part in enumerate(parts):
                if index < delivery.parts_sent:
                    continue  # accepted by Telegram in a previous attempt
                if part["type"] == "text":
                    result = api.send_message(chat_id, part["text"],
                                              reply_to_message_id=reply_to if index == 0 else None)
                else:
                    media.check_outbound(part["attachment"])
                    result = media.send_attachment(chat_id, part["attachment"], caption=part["caption"])
                # savepoint: a DB error here must not abort the transaction used by _handle_error
                with self.env.cr.savepoint():
                    tg_message._add_sent_telegram_id((result or {}).get("message_id"))
                    delivery.write({
                        "parts_sent": index + 1,
                        "response_summary": truncate(f"ok message_id={(result or {}).get('message_id')}", 200),
                    })
                maybe_commit(self.env)
        except exc.TelegramError as e:
            self._handle_error(delivery, e)
            return False
        except Exception as e:  # noqa: BLE001 - classified as internal, retried
            _logger.exception("Unexpected error sending Telegram delivery %s", delivery.id)
            self._handle_error(delivery, exc.TelegramError(truncate(str(e), 300)))
            return False
        delivery.write({
            "state": "sent",
            "next_retry_at": False,
            "error_class": False,
            "error_message": False,
        })
        tg_message.write({"state": "sent", "error_message": False})
        TelegramConversationService.on_agent_message(conversation)
        self.notify_state(tg_message)
        return True

    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------

    def _handle_error(self, delivery, error):
        tg_message = delivery.message_id
        bot = delivery.bot_id
        error_class = error.error_class
        # TelegramAPI already masks; mask again so no token can reach records or the channel
        secrets = (bot.sudo().token, bot.sudo().webhook_secret)
        message = truncate(mask_secrets(str(error), *secrets), 1000)
        error.description = mask_secrets(error.description, *secrets)
        vals = {"error_class": error_class, "error_message": message,
                "response_summary": truncate(message, 200)}
        now = fields.Datetime.now()
        cron = self.env.ref("aypatech_telegram_connector.ir_cron_telegram_delivery")

        if error_class == exc.ERROR_AUTH:
            # pause the whole bot; this attempt does not count
            vals.update(state="queued", next_retry_at=False, attempt=delivery.attempt - 1)
            delivery.write(vals)
            tg_message.write({"state": "queued"})
            bot._mark_error(error)
            bot._notify_managers_auth_failure()
            bot._log("error", "delivery", message)
            return
        if error_class == exc.ERROR_RATE_LIMIT:
            retry_at = now + timedelta(seconds=error.retry_after or 5)
            vals.update(state="failed_retryable", next_retry_at=retry_at, attempt=delivery.attempt - 1)
            delivery.write(vals)
            tg_message.write({"state": "queued"})
            bot._log("warning", "delivery", f"429 rate limit, retry after {error.retry_after}s")
            cron._trigger(retry_at)
            return
        if error.retryable and delivery.attempt < self._max_attempts():
            delay = BACKOFF_SECONDS[min(delivery.attempt - 1, len(BACKOFF_SECONDS) - 1)]
            retry_at = now + timedelta(seconds=delay)
            vals.update(state="failed_retryable", next_retry_at=retry_at)
            delivery.write(vals)
            tg_message.write({"state": "queued"})
            bot._log("warning", "delivery", f"Delivery {delivery.id} attempt {delivery.attempt} failed: {message}")
            cron._trigger(retry_at)
            return

        # permanent
        vals.update(state="failed_permanent", next_retry_at=False)
        delivery.write(vals)
        tg_message.write({"state": "failed", "error_message": message})
        if error_class == exc.ERROR_BLOCKED:
            tg_message.conversation_id.contact_id.write({"blocked": True})
        bot._log("error", "delivery", f"Delivery {delivery.id} failed permanently: {message}")
        self._post_failure_notice(delivery, error)
        self.notify_state(tg_message)

    def _post_failure_notice(self, delivery, error):
        channel = delivery.conversation_id.channel_id
        if not channel:
            return
        _ = self.env._
        reasons = {
            exc.ERROR_BLOCKED: _("the customer blocked the bot"),
            exc.ERROR_NOT_FOUND: _("Telegram does not know this chat anymore"),
            exc.ERROR_ATTACHMENT: _("the file is too large or not accepted by Telegram"),
        }
        reason = reasons.get(error.error_class) or error.description or error.error_class
        body = Markup('<div class="o_mail_notification">%s</div>') % _(
            "⚠️ Message not delivered to Telegram: %(reason)s. Retry it from Telegram → Deliveries → Failed.",
            reason=reason,
        )
        channel.with_context(telegram_inbound=True).sudo().message_post(
            body=body,
            author_id=self.env.ref("base.partner_root").id,
            message_type="notification",
            subtype_xmlid="mail.mt_comment",
        )

    def notify_state(self, tg_messages):
        """Push the delivery state to Discuss clients (failed indicator)."""
        for tg_message in tg_messages.sudo():
            channel = tg_message.conversation_id.channel_id
            mail_message = tg_message.mail_message_id
            if not channel or not mail_message:
                continue
            channel._bus_send_store(mail_message, {
                "telegram_delivery_state": tg_message.state,
                "telegram_delivery_error": tg_message.error_message or False,
            })
