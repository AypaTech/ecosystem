# -*- coding: utf-8 -*-
"""Test helpers. The real Telegram API is never called: every test patches
``TelegramAPI.for_bot`` (or ``requests``) with ``FakeTelegramAPI``."""
import copy
import itertools
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from odoo.tests import TransactionCase, new_test_user

from ..services import exceptions as exc
from ..services.telegram_api import TelegramAPI

FIXTURES = Path(__file__).parent / "fixtures"
TEST_TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"


def load_fixture(name, **overrides):
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    data.update(overrides)
    return data


class FakeTelegramAPI:
    """Records calls; answers with canned results or raises queued errors."""

    _ids = itertools.count(1000)

    def __init__(self):
        self.calls = []
        self.errors = []  # exceptions raised by the next send_* calls, in order
        self.files = {}   # file_id -> (file_path, bytes)
        self.updates = []
        self.get_updates_errors = []
        self.webhook_info = {"url": "", "pending_update_count": 0}

    # --- helpers
    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))

    def sent(self, name=None):
        return [c for c in self.calls if name is None or c[0] == name]

    def _send(self, name, *args, **kwargs):
        self._record(name, *args, **kwargs)
        if self.errors:
            error = self.errors.pop(0)
            if error is not None:
                raise error
        return {"message_id": next(self._ids)}

    # --- API surface
    def get_me(self):
        self._record("get_me")
        return {"id": 987654321, "is_bot": True, "first_name": "Acme", "username": "AcmeSupportBot"}

    def set_webhook(self, *args, **kwargs):
        self._record("set_webhook", *args, **kwargs)
        return True

    def delete_webhook(self, *args, **kwargs):
        self._record("delete_webhook", *args, **kwargs)
        self.webhook_info["url"] = ""
        return True

    def get_webhook_info(self):
        self._record("get_webhook_info")
        return dict(self.webhook_info)

    def get_updates(self, **kwargs):
        self._record("get_updates", **kwargs)
        if self.get_updates_errors:
            raise self.get_updates_errors.pop(0)
        offset = kwargs.get("offset")
        return [u for u in self.updates if offset is None or u["update_id"] >= offset]

    def send_message(self, chat_id, text, **kwargs):
        return self._send("send_message", chat_id, text, **kwargs)

    def send_photo(self, chat_id, file_tuple, caption=None, **kwargs):
        return self._send("send_photo", chat_id, file_tuple, caption=caption)

    def send_document(self, chat_id, file_tuple, caption=None, **kwargs):
        return self._send("send_document", chat_id, file_tuple, caption=caption)

    def send_video(self, chat_id, file_tuple, caption=None, **kwargs):
        return self._send("send_video", chat_id, file_tuple, caption=caption)

    def send_audio(self, chat_id, file_tuple, caption=None, **kwargs):
        return self._send("send_audio", chat_id, file_tuple, caption=caption)

    def send_voice(self, chat_id, file_tuple, caption=None, **kwargs):
        return self._send("send_voice", chat_id, file_tuple, caption=caption)

    def send_chat_action(self, chat_id, action="typing"):
        self._record("send_chat_action", chat_id, action)
        return True

    def get_file(self, file_id):
        self._record("get_file", file_id)
        path, content = self.files[file_id]
        return {"file_id": file_id, "file_path": path, "file_size": len(content)}

    def download_file(self, file_path, max_bytes):
        self._record("download_file", file_path)
        for path, content in self.files.values():
            if path == file_path:
                if len(content) > max_bytes:
                    raise exc.TelegramAttachmentError("File is larger than the configured limit.")
                return content
        raise exc.TelegramBadRequest("unknown file")


class TelegramCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.manager = new_test_user(
            cls.env, login="tg_manager", name="TG Manager",
            groups="base.group_user,aypatech_telegram_connector.group_telegram_manager",
        )
        cls.agent = new_test_user(
            cls.env, login="tg_agent", name="TG Agent",
            groups="base.group_user,aypatech_telegram_connector.group_telegram_user",
        )
        cls.agent2 = new_test_user(
            cls.env, login="tg_agent2", name="TG Agent 2",
            groups="base.group_user,aypatech_telegram_connector.group_telegram_user",
        )
        cls.team = cls.env["telegram.team"].create({
            "name": "Support",
            "member_ids": [(6, 0, (cls.agent | cls.agent2).ids)],
            "assignment_method": "manual",
        })
        cls.bot = cls.env["telegram.bot"].create({
            "name": "Acme",
            "token": TEST_TOKEN,
            "connection_mode": "webhook",
            "team_id": cls.team.id,
            "default_user_id": cls.agent.id,
        })
        cls.bot.write({
            "state": "connected", "username": "AcmeSupportBot",
            "bot_telegram_id": "987654321", "webhook_registered_mode": "webhook",
        })

    def setUp(self):
        super().setUp()
        self.api = FakeTelegramAPI()
        patcher = patch.object(TelegramAPI, "for_bot", return_value=self.api)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------------

    def make_update(self, update_id=1, text="Hello", user_id=111111, message_id=None, **message_overrides):
        update = copy.deepcopy(load_fixture("update_text"))
        update["update_id"] = update_id
        msg = update["message"]
        msg["message_id"] = message_id or update_id
        msg["from"]["id"] = user_id
        msg["chat"]["id"] = user_id
        if text is None:
            msg.pop("text", None)
        else:
            msg["text"] = text
        msg.update(message_overrides)
        return update

    def receive(self, update, bot=None):
        """Store + process one update like the webhook + cron would."""
        bot = bot or self.bot
        record = self.env["telegram.update"].sudo()._store(bot, update, "webhook")
        self.env["telegram.update"].sudo()._cron_process()
        return record

    def conversation_for(self, user_id=111111, bot=None):
        bot = bot or self.bot
        return self.env["telegram.conversation"].sudo().search([
            ("bot_id", "=", bot.id), ("chat_id.telegram_chat_id", "=", str(user_id)),
        ], order="id desc", limit=1)

    def deliver(self):
        from ..services.delivery import TelegramDeliveryService
        return TelegramDeliveryService(self.env).process_queue()

    @contextmanager
    def assertQueued(self, count):
        before = self.env["telegram.delivery"].sudo().search_count([])
        yield
        after = self.env["telegram.delivery"].sudo().search_count([])
        self.assertEqual(after - before, count, "unexpected number of queued deliveries")
