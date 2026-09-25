# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..services import exceptions as exc
from ..services.gateway import TelegramPoller
from .common import TelegramCase


@tagged("post_install", "-at_install", "telegram")
class TestPolling(TelegramCase):

    def setUp(self):
        super().setUp()
        self.bot.write({"connection_mode": "polling", "webhook_registered_mode": "webhook"})

    def test_offset_advances_and_updates_are_stored(self):
        self.api.updates = [self.make_update(5000000001, "a"), self.make_update(5000000002, "b")]
        stored = self.env["telegram.update"]._cron_poll()
        self.assertEqual(stored, 2)
        self.assertEqual(self.bot.polling_offset, "5000000003", "offset beyond 32 bits is safe")
        self.assertTrue(self.api.sent("delete_webhook"), "webhook removed before getUpdates")
        self.assertEqual(self.bot.webhook_registered_mode, "polling")
        # second poll asks from the new offset and stores nothing new
        self.assertEqual(self.env["telegram.update"]._cron_poll(), 0)
        self.assertEqual(self.api.sent("get_updates")[-1][2]["offset"], 5000000003)
        self.env["telegram.update"]._cron_process()
        self.assertEqual(self.conversation_for().message_count, 2)

    def test_409_deletes_webhook_and_retries(self):
        self.bot.webhook_registered_mode = "polling"
        self.api.get_updates_errors = [exc.TelegramConflict("Conflict: can't use getUpdates while webhook is active")]
        self.api.updates = [self.make_update(10, "x")]
        self.assertEqual(TelegramPoller(self.env, self.bot, api=self.api).poll(), 1)
        self.assertEqual(len(self.api.sent("delete_webhook")), 1)

    @mute_logger("odoo.addons.aypatech_telegram_connector.models.telegram_log")
    def test_409_twice_marks_error(self):
        self.bot.webhook_registered_mode = "polling"
        self.api.get_updates_errors = [exc.TelegramConflict("Conflict"), exc.TelegramConflict("Conflict")]
        self.assertEqual(TelegramPoller(self.env, self.bot, api=self.api).poll(), 0)
        self.assertEqual(self.bot.state, "error")

    def test_duplicate_updates_from_polling_ignored(self):
        update = self.make_update(77, "dup")
        self.api.updates = [update]
        self.env["telegram.update"]._cron_poll()
        self.bot.polling_offset = False  # simulate a lost offset
        self.env["telegram.update"]._cron_poll()
        self.assertEqual(self.env["telegram.update"].search_count([("bot_id", "=", self.bot.id)]), 1)
