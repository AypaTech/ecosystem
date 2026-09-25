# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.aypatech_telegram_connector.tests.common import TelegramCase


@tagged("post_install", "-at_install", "telegram")
class TestTelegramHelpdesk(TelegramCase):

    def test_ticket_from_conversation_and_reply_forwarding(self):
        model = self.env["telegram.conversation"]._get_helpdesk_model()
        if not model:
            self.skipTest("no helpdesk app installed")
        self.receive(self.make_update(1, "My device is broken"))
        conv = self.conversation_for()
        self.assertTrue(conv.can_create_ticket)
        action = conv.action_create_ticket()
        ticket = conv.ticket_ref
        self.assertEqual(ticket._name, model)
        self.assertEqual(action["res_id"], ticket.id)
        self.assertEqual(ticket.partner_id, conv.partner_id)
        self.assertIn("device is broken", str(ticket.description))
        # second click opens the same ticket
        self.assertEqual(conv.action_create_ticket()["res_id"], ticket.id)

        with self.assertQueued(1):
            ticket.message_post(
                body="We are on it", author_id=self.agent.partner_id.id,
                message_type="comment", subtype_xmlid="mail.mt_comment")
        with self.assertQueued(0):
            ticket.message_post(body="internal", message_type="comment", subtype_xmlid="mail.mt_note")
        self.deliver()
        self.assertEqual(self.api.sent("send_message")[-1][1][1], "We are on it")

        conv.ticket_forward_replies = False
        with self.assertQueued(0):
            ticket.message_post(
                body="not forwarded", author_id=self.agent.partner_id.id,
                message_type="comment", subtype_xmlid="mail.mt_comment")

    def test_without_helpdesk(self):
        if self.env["telegram.conversation"]._get_helpdesk_model():
            self.skipTest("a helpdesk app is installed")
        self.receive(self.make_update(1, "hello"))
        conv = self.conversation_for()
        self.assertFalse(conv.can_create_ticket)
        with self.assertRaises(UserError):
            conv.action_create_ticket()
