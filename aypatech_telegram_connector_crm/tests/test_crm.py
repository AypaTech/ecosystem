# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.aypatech_telegram_connector.tests.common import TelegramCase


@tagged("post_install", "-at_install", "telegram")
class TestTelegramCrm(TelegramCase):

    def test_create_lead_from_conversation(self):
        self.receive(self.make_update(1, "I want to buy 10 licences"))
        conv = self.conversation_for()
        action = conv.action_create_lead()
        lead = conv.lead_id
        self.assertTrue(lead)
        self.assertEqual(action["res_id"], lead.id)
        self.assertEqual(lead.partner_id, conv.partner_id)
        self.assertEqual(lead.user_id, conv.user_id)
        self.assertIn("buy 10 licences", str(lead.description))
        self.assertEqual(lead.telegram_conversation_ids, conv)
        # second click opens the same lead
        self.assertEqual(conv.action_create_lead()["res_id"], lead.id)
