# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TelegramCase


@tagged("post_install", "-at_install", "telegram")
class TestConversationState(TelegramCase):

    def setUp(self):
        super().setUp()
        self.receive(self.make_update(1, "hi"))
        self.conv = self.conversation_for()

    def test_transitions(self):
        self.assertEqual(self.conv.state, "open", "assigned on creation → open")
        self.conv.action_pending_customer()
        self.assertEqual(self.conv.state, "pending_customer")
        self.receive(self.make_update(2, "answer"))
        self.assertEqual(self.conv.state, "open", "customer answer → open")
        self.conv.action_resolve()
        self.assertEqual(self.conv.state, "resolved")
        with self.assertRaises(UserError):
            self.conv.action_pending_customer()
        self.conv.action_close()
        self.conv.action_reopen()
        self.assertEqual(self.conv.state, "open")

    def test_resolved_reopens_on_customer_message(self):
        self.conv.action_resolve()
        self.receive(self.make_update(2, "one more thing"))
        self.assertEqual(self.conversation_for(), self.conv)
        self.assertEqual(self.conv.state, "open")

    def test_closed_new_conversation_by_default(self):
        self.conv.action_close()
        self.receive(self.make_update(2, "new question"))
        new = self.conversation_for()
        self.assertNotEqual(new, self.conv)
        self.assertEqual(new.contact_id, self.conv.contact_id, "same identity")
        self.assertEqual(new.partner_id, self.conv.partner_id)
        self.assertNotEqual(new.channel_id, self.conv.channel_id)

    def test_closed_reopen_setting(self):
        self.env["ir.config_parameter"].sudo().set_param("telegram.closed_behavior", "reopen")
        self.conv.action_close()
        self.receive(self.make_update(2, "again"))
        self.assertEqual(self.conversation_for(), self.conv)
        self.assertEqual(self.conv.state, "open")

    def test_auto_resolve(self):
        self.env["ir.config_parameter"].sudo().set_param("telegram.auto_resolve_days", "3")
        self.conv.last_customer_message_date = fields.Datetime.now() - timedelta(days=4)
        self.env["telegram.conversation"]._cron_auto_resolve()
        self.assertEqual(self.conv.state, "resolved")

    def test_open_chat_action(self):
        action = self.conv.action_open_chat()
        self.assertEqual(action["tag"], "mail.action_discuss")
        self.assertEqual(action["context"]["active_id"], self.conv.channel_id.id)
