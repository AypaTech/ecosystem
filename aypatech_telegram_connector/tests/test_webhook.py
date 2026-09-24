# -*- coding: utf-8 -*-
import json

from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from .common import TEST_TOKEN, load_fixture


@tagged("post_install", "-at_install", "telegram")
class TestWebhook(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot = cls.env["telegram.bot"].create({"name": "Hook", "token": TEST_TOKEN})
        cls.url = f"/telegram/webhook/{cls.bot.webhook_key}"
        cls.secret = cls.bot.webhook_secret

    def _post(self, body, secret=None, url=None):
        headers = {"Content-Type": "application/json"}
        if secret is not None:
            headers["X-Telegram-Bot-Api-Secret-Token"] = secret
        data = body if isinstance(body, (bytes, str)) else json.dumps(body)
        return self.url_open(url or self.url, data=data, headers=headers)

    def _updates(self):
        return self.env["telegram.update"].sudo().search([("bot_id", "=", self.bot.id)])

    def test_valid_update_is_stored_and_processing_triggered(self):
        cron = self.env.ref("aypatech_telegram_connector.ir_cron_telegram_process_updates")
        triggers_before = self.env["ir.cron.trigger"].sudo().search_count([("cron_id", "=", cron.id)])
        response = self._post(load_fixture("update_text"), secret=self.secret)
        self.assertEqual(response.status_code, 200)
        update = self._updates()
        self.assertEqual(len(update), 1)
        self.assertEqual(update.update_id, "900000001")
        self.assertEqual(update.state, "pending")
        self.assertEqual(update.update_type, "message")
        self.assertGreater(self.env["ir.cron.trigger"].sudo().search_count([("cron_id", "=", cron.id)]), triggers_before)

    def test_duplicate_update_id_returns_200_without_new_row(self):
        body = load_fixture("update_text")
        self.assertEqual(self._post(body, secret=self.secret).status_code, 200)
        self.assertEqual(self._post(body, secret=self.secret).status_code, 200)
        self.assertEqual(len(self._updates()), 1)

    @mute_logger("odoo.addons.aypatech_telegram_connector.models.telegram_log")
    def test_wrong_secret(self):
        self.assertEqual(self._post(load_fixture("update_text"), secret="nope").status_code, 403)
        self.assertEqual(self._post(load_fixture("update_text")).status_code, 403)
        self.assertFalse(self._updates())
        log = self.env["telegram.log"].sudo().search([("bot_id", "=", self.bot.id)], limit=1)
        self.assertIn("wrong secret", log.message)
        self.assertNotIn(self.secret, log.message)

    def test_unknown_key(self):
        response = self._post(load_fixture("update_text"), secret=self.secret,
                              url="/telegram/webhook/" + "x" * 43)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.text, "")

    @mute_logger("odoo.addons.aypatech_telegram_connector.models.telegram_log")
    def test_malformed_json(self):
        self.assertEqual(self._post(b"{not json", secret=self.secret).status_code, 400)
        self.assertEqual(self._post({"no_update_id": 1}, secret=self.secret).status_code, 400)
        self.assertFalse(self._updates())

    def test_body_too_large(self):
        big = json.dumps({"update_id": 5, "message": {"text": "x" * (1024 * 1024 + 10)}})
        self.assertEqual(self._post(big, secret=self.secret).status_code, 413)

    def test_get_not_allowed(self):
        response = self.url_open(self.url)
        self.assertEqual(response.status_code, 405)

    def test_archived_bot(self):
        self.bot.active = False
        self.assertEqual(self._post(load_fixture("update_text"), secret=self.secret).status_code, 404)
