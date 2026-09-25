# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

import requests

from odoo.tests import BaseCase, tagged

from ..services import exceptions as exc
from ..services.telegram_api import TelegramAPI
from ..services.utils import mask_secrets, mask_token
from .common import TEST_TOKEN


def _response(status, payload=None, text=""):
    response = MagicMock()
    response.status_code = status
    if payload is None:
        response.json.side_effect = ValueError("no json")
    else:
        response.json.return_value = payload
    response.text = text
    return response


@tagged("post_install", "-at_install", "telegram")
class TestTelegramAPI(BaseCase):

    def setUp(self):
        super().setUp()
        self.session = MagicMock()
        self.api = TelegramAPI(TEST_TOKEN, session=self.session)

    def _post_returns(self, response):
        self.session.post.return_value = response

    def test_success(self):
        self._post_returns(_response(200, {"ok": True, "result": {"id": 1, "username": "b"}}))
        self.assertEqual(self.api.get_me()["username"], "b")
        url = self.session.post.call_args[0][0]
        self.assertTrue(url.endswith("/getMe"))
        self.assertEqual(self.session.post.call_args[1]["timeout"], (5, 30))

    def _assert_raises(self, response, exc_class):
        self._post_returns(response)
        with self.assertRaises(exc_class) as ctx:
            self.api.send_message("1", "x")
        self.assertNotIn(TEST_TOKEN, str(ctx.exception))
        return ctx.exception

    def test_classification(self):
        self._assert_raises(_response(401, {"ok": False, "error_code": 401, "description": "Unauthorized"}),
                            exc.TelegramAuthError)
        self._assert_raises(_response(403, {"ok": False, "error_code": 403,
                                            "description": "Forbidden: bot was blocked by the user"}),
                            exc.TelegramBlockedError)
        self._assert_raises(_response(400, {"ok": False, "error_code": 400,
                                            "description": "Bad Request: chat not found"}),
                            exc.TelegramNotFound)
        self._assert_raises(_response(400, {"ok": False, "error_code": 400,
                                            "description": "Bad Request: can't parse entities"}),
                            exc.TelegramBadRequest)
        error = self._assert_raises(_response(429, {"ok": False, "error_code": 429,
                                                    "description": "Too Many Requests: retry after 17",
                                                    "parameters": {"retry_after": 17}}),
                                    exc.TelegramRateLimit)
        self.assertEqual(error.retry_after, 17)
        self._assert_raises(_response(502, None, "Bad Gateway"), exc.TelegramTransientError)
        self._assert_raises(_response(409, {"ok": False, "error_code": 409, "description": "Conflict"}),
                            exc.TelegramConflict)

    def test_timeout_and_connection_error_are_transient_and_masked(self):
        self.session.post.side_effect = requests.Timeout(f"https://api.telegram.org/bot{TEST_TOKEN}/sendMessage timed out")
        with self.assertRaises(exc.TelegramTransientError) as ctx:
            self.api.send_message("1", "x")
        self.assertNotIn(TEST_TOKEN, str(ctx.exception))
        self.session.post.side_effect = requests.ConnectionError(f"bot{TEST_TOKEN} unreachable")
        with self.assertRaises(exc.TelegramTransientError) as ctx:
            self.api.get_me()
        self.assertNotIn(TEST_TOKEN, str(ctx.exception))

    def test_masking_helpers(self):
        self.assertEqual(mask_token(TEST_TOKEN), "123456789:AAH…saw")
        text = f"GET https://api.telegram.org/bot{TEST_TOKEN}/getMe failed secret=abc"
        masked = mask_secrets(text, "abc")
        self.assertNotIn(TEST_TOKEN, masked)
        self.assertNotIn("abc", masked)

    def test_download_rejects_bad_path_and_big_file(self):
        with self.assertRaises(exc.TelegramBadRequest):
            self.api.download_file("../etc/passwd", 100)
        with self.assertRaises(exc.TelegramBadRequest):
            self.api.download_file("https://evil.example/x", 100)
        response = MagicMock(status_code=200, headers={"Content-Length": "5000"})
        self.session.get.return_value = response
        with self.assertRaises(exc.TelegramAttachmentError):
            self.api.download_file("photos/file_1.jpg", 100)
        url = self.session.get.call_args[0][0]
        self.assertTrue(url.startswith("https://api.telegram.org/file/bot"))

    def test_download_streaming_limit(self):
        response = MagicMock(status_code=200, headers={})
        response.iter_content.return_value = [b"x" * 60, b"x" * 60]
        self.session.get.return_value = response
        with self.assertRaises(exc.TelegramAttachmentError):
            self.api.download_file("documents/file_2.pdf", 100)

    def test_no_token(self):
        with self.assertRaises(exc.TelegramAuthError):
            TelegramAPI("")

    @patch("requests.post")
    def test_default_session_is_requests(self, post):
        post.return_value = _response(200, {"ok": True, "result": True})
        TelegramAPI(TEST_TOKEN).delete_webhook()
        self.assertTrue(post.called)
