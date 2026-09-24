# -*- coding: utf-8 -*-
import base64
from datetime import timedelta
from unittest.mock import patch

from markupsafe import Markup

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..services import exceptions as exc
from .common import TelegramCase

LOGGERS = (
    "odoo.addons.aypatech_telegram_connector.models.telegram_log",
    "odoo.addons.aypatech_telegram_connector.services.delivery",
)


@tagged("post_install", "-at_install", "telegram")
class TestOutbound(TelegramCase):

    def setUp(self):
        super().setUp()
        self.receive(self.make_update(1, "Hi, I need help"))
        self.conv = self.conversation_for()
        self.channel = self.conv.channel_id

    def reply(self, body="Hello from Odoo", user=None, **kwargs):
        user = user or self.agent
        kwargs.setdefault("message_type", "comment")
        kwargs.setdefault("subtype_xmlid", "mail.mt_comment")
        # like the Discuss composer: HTML bodies are Markup (plain str would be escaped)
        return self.channel.with_user(user).message_post(body=Markup(body), **kwargs)

    def last_delivery(self):
        return self.env["telegram.delivery"].search([("conversation_id", "=", self.conv.id)], order="id desc", limit=1)

    # ------------------------------------------------------------------ queueing

    def test_agent_reply_is_queued_then_sent(self):
        cron = self.env.ref("aypatech_telegram_connector.ir_cron_telegram_delivery")
        with self.assertQueued(1):
            message = self.reply("<p>Hello <b>Ali</b></p>")
        self.assertFalse(self.api.sent("send_message"), "never sent inside the posting transaction")
        self.assertTrue(self.env["ir.cron.trigger"].search([("cron_id", "=", cron.id)]))
        delivery = self.last_delivery()
        self.assertEqual(delivery.state, "queued")
        self.assertEqual(delivery.message_id.mail_message_id, message)
        self.deliver()
        self.assertEqual(delivery.state, "sent")
        self.assertEqual(delivery.message_id.state, "sent")
        self.assertTrue(delivery.message_id.telegram_message_id)
        [(name, args, _kw)] = self.api.sent("send_message")
        self.assertEqual(args, ("111111", "Hello <b>Ali</b>"))
        self.assertTrue(self.conv.last_agent_message_date)

    def test_internal_note_never_queued(self):
        with self.assertQueued(0):
            self.reply("secret note", subtype_xmlid="mail.mt_note")
            self.channel.with_user(self.agent).message_post(
                body="internal", message_type="comment", subtype_xmlid="mail.mt_comment", is_internal=True)
            self.channel.with_user(self.agent).message_post(body="notif", message_type="notification")

    def test_non_telegram_channel_not_queued(self):
        channel = self.env["discuss.channel"].create({"name": "general-test", "channel_type": "channel"})
        with self.assertQueued(0):
            channel.message_post(body="hello", message_type="comment", subtype_xmlid="mail.mt_comment")

    def test_attachment_sent_with_caption(self):
        attachment = self.env["ir.attachment"].create({
            "name": "photo.png", "raw": b"\x89PNG fake", "mimetype": "image/png",
            "res_model": "discuss.channel", "res_id": self.channel.id,
        })
        self.reply("<p>See photo</p>", attachment_ids=attachment.ids)
        self.deliver()
        [(name, args, kwargs)] = self.api.sent("send_photo")
        self.assertEqual(args[1][0], "photo.png")
        self.assertEqual(kwargs["caption"], "See photo")
        self.assertFalse(self.api.sent("send_message"))

    def test_too_big_attachment_refused_before_sending(self):
        attachment = self.env["ir.attachment"].create({
            "name": "big.bin", "datas": base64.b64encode(b"x" * 10), "res_model": "discuss.channel",
            "res_id": self.channel.id,
        })
        # 10 bytes > a 1 byte limit (stands for the 50 MB Bot API limit)
        with patch("odoo.addons.aypatech_telegram_connector.services.media.TelegramMediaService.upload_limit",
                   return_value=1):
            with self.assertRaises(UserError):
                self.reply("file", attachment_ids=attachment.ids)
        self.assertFalse(self.env["telegram.delivery"].search([("conversation_id", "=", self.conv.id)]))

    def test_long_text_split(self):
        self.reply("<p>" + "word " * 1200 + "</p>")
        self.deliver()
        self.assertEqual(len(self.api.sent("send_message")), 2)
        tg = self.last_delivery().message_id
        self.assertEqual(len(tg._get_all_telegram_ids()), 2)

    # ------------------------------------------------------------------ errors

    @mute_logger(*LOGGERS)
    def test_400_is_permanent_with_notice(self):
        self.api.errors = [exc.TelegramBadRequest("sendMessage: Bad Request: can't parse entities")]
        self.reply()
        self.deliver()
        delivery = self.last_delivery()
        self.assertEqual((delivery.state, delivery.error_class), ("failed_permanent", "bad_request"))
        self.assertEqual(delivery.message_id.state, "failed")
        notice = self.channel.message_ids[:1]
        self.assertEqual(notice.message_type, "notification")
        self.assertIn("not delivered", str(notice.body))
        self.assertEqual(self.conv.failed_delivery_count, 1)

    @mute_logger(*LOGGERS)
    def test_403_marks_contact_blocked(self):
        self.api.errors = [exc.TelegramBlockedError("Forbidden: bot was blocked by the user")]
        self.reply()
        self.deliver()
        self.assertEqual(self.last_delivery().state, "failed_permanent")
        self.assertTrue(self.conv.contact_id.blocked)

    @mute_logger(*LOGGERS)
    def test_429_honours_retry_after(self):
        self.api.errors = [exc.TelegramRateLimit("Too Many Requests", retry_after=42)]
        self.reply()
        before = fields.Datetime.now()
        self.deliver()
        delivery = self.last_delivery()
        self.assertEqual(delivery.state, "failed_retryable")
        self.assertEqual(delivery.error_class, "rate_limit")
        self.assertAlmostEqual((delivery.next_retry_at - before).total_seconds(), 42, delta=5)
        self.assertEqual(delivery.attempt, 0, "429 does not consume an attempt")
        # not retried before retry_after
        self.deliver()
        self.assertEqual(len(self.api.sent("send_message")), 1)
        delivery.next_retry_at = fields.Datetime.now() - timedelta(seconds=1)
        self.deliver()
        self.assertEqual(delivery.state, "sent")

    @mute_logger(*LOGGERS)
    def test_5xx_and_timeout_retry_with_backoff_then_fail(self):
        self.env["ir.config_parameter"].sudo().set_param("telegram.max_attempts", "2")
        self.api.errors = [exc.TelegramTransientError("502"), exc.TelegramTransientError("Timeout calling sendMessage")]
        self.reply()
        self.deliver()
        delivery = self.last_delivery()
        self.assertEqual((delivery.state, delivery.attempt), ("failed_retryable", 1))
        self.assertTrue(delivery.next_retry_at > fields.Datetime.now())
        delivery.next_retry_at = fields.Datetime.now() - timedelta(seconds=1)
        self.deliver()
        self.assertEqual((delivery.state, delivery.attempt), ("failed_permanent", 2))
        self.assertEqual(delivery.error_class, "transient")

    @mute_logger(*LOGGERS)
    def test_manual_retry(self):
        self.api.errors = [exc.TelegramBadRequest("bad")]
        self.reply()
        self.deliver()
        delivery = self.last_delivery()
        delivery.with_user(self.agent).action_retry()
        self.assertEqual(delivery.state, "queued")
        self.deliver()
        self.assertEqual(delivery.state, "sent")

    @mute_logger(*LOGGERS)
    def test_auth_error_pauses_bot(self):
        self.api.errors = [exc.TelegramAuthError("Unauthorized")]
        self.reply("one")
        self.deliver()
        delivery = self.last_delivery()
        self.assertEqual(delivery.state, "queued")
        self.assertTrue(self.bot.auth_failed)
        self.assertEqual(self.bot.state, "error")
        self.assertTrue(self.bot.activity_ids, "managers are notified")
        self.deliver()
        self.assertEqual(len(self.api.sent("send_message")), 1, "no send while the bot is paused")
        self.bot.with_user(self.manager).action_test_connection()
        self.assertFalse(self.bot.auth_failed)
        self.deliver()
        self.assertEqual(delivery.state, "sent")

    # ------------------------------------------------------------------ ordering / watchdog

    @mute_logger(*LOGGERS)
    def test_per_conversation_ordering(self):
        self.api.errors = [exc.TelegramTransientError("503")]
        self.reply("first")
        self.reply("second")
        self.deliver()
        first, second = self.env["telegram.delivery"].search([("conversation_id", "=", self.conv.id)], order="id")
        self.assertEqual(first.state, "failed_retryable")
        self.assertEqual(second.state, "queued", "N+1 waits while N is failed_retryable")
        self.assertEqual(len(self.api.sent("send_message")), 1)
        first.next_retry_at = fields.Datetime.now() - timedelta(seconds=1)
        self.deliver()
        self.assertEqual((first.state, second.state), ("sent", "sent"))
        texts = [c[1][1] for c in self.api.sent("send_message")]
        self.assertEqual(texts, ["first", "first", "second"])

    def test_other_conversation_not_blocked(self):
        self.receive(self.make_update(50, "other customer", user_id=222222))
        other = self.conversation_for(222222)
        self.reply("to first")
        # sending delivery on first conversation must not block the second one
        first = self.last_delivery()
        first.state = "sending"
        first.sending_started_at = fields.Datetime.now()
        other.channel_id.with_user(self.agent).message_post(
            body="to second", message_type="comment", subtype_xmlid="mail.mt_comment")
        self.deliver()
        texts = [c[1][1] for c in self.api.sent("send_message")]
        self.assertEqual(texts, ["to second"])

    @mute_logger(*LOGGERS)
    def test_stuck_delivery_watchdog(self):
        self.reply()
        delivery = self.last_delivery()
        delivery.write({"state": "sending", "sending_started_at": fields.Datetime.now() - timedelta(minutes=11)})
        self.env["telegram.delivery"]._cron_watchdog()
        self.assertEqual(delivery.state, "failed_retryable")
        self.deliver()
        self.assertEqual(delivery.state, "sent")

    def test_partial_send_is_not_repeated(self):
        attachment = self.env["ir.attachment"].create({
            "name": "a.pdf", "raw": b"%PDF", "mimetype": "application/pdf",
            "res_model": "discuss.channel", "res_id": self.channel.id,
        })
        attachment2 = self.env["ir.attachment"].create({
            "name": "b.pdf", "raw": b"%PDF", "mimetype": "application/pdf",
            "res_model": "discuss.channel", "res_id": self.channel.id,
        })
        self.api.errors = [None, exc.TelegramTransientError("502")]
        with mute_logger(*LOGGERS):
            self.reply("docs", attachment_ids=(attachment | attachment2).ids)
            self.deliver()
        delivery = self.last_delivery()
        self.assertEqual((delivery.state, delivery.parts_sent), ("failed_retryable", 1))
        delivery.next_retry_at = fields.Datetime.now() - timedelta(seconds=1)
        self.deliver()
        names = [c[1][1][0] for c in self.api.sent("send_document")]
        self.assertEqual(names, ["a.pdf", "b.pdf", "b.pdf"], "a.pdf is not sent twice")
        self.assertEqual(delivery.state, "sent")
