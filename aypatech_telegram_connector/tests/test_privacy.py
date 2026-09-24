# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import TelegramCase


@tagged("post_install", "-at_install", "telegram")
class TestPrivacy(TelegramCase):

    def test_retention_cleanup(self):
        self.receive(self.make_update(1, "hi"))
        update = self.env["telegram.update"].search([("bot_id", "=", self.bot.id)])
        self.assertTrue(update.payload)
        update.received_at = fields.Datetime.now() - timedelta(days=8)
        log = self.env["telegram.log"]._log(self.bot, "info", "api", "old")
        self.env.cr.execute("UPDATE telegram_log SET create_date = now() - interval '40 days' WHERE id = %s", (log.id,))
        log.invalidate_recordset()
        self.env["telegram.bot"]._cron_cleanup()
        self.assertFalse(update.payload)
        self.assertFalse(log.exists())

    def test_forget_identity_anonymize(self):
        self.receive(self.make_update(1, "my secret address"))
        conv = self.conversation_for()
        contact = conv.contact_id
        partner = conv.partner_id
        wizard = self.env["telegram.forget.identity"].with_context(
            active_model="telegram.contact", active_ids=contact.ids).create({"mode": "anonymize"})
        wizard.action_forget()
        self.assertFalse(contact.exists())
        self.assertFalse(conv.chat_id)
        self.assertEqual(conv.state, "closed")
        self.assertIn("Anonymous", partner.name)
        bodies = conv.channel_id.message_ids.mapped(lambda m: str(m.body))
        self.assertFalse(any("my secret address" in b for b in bodies))

    def test_forget_identity_keep(self):
        self.receive(self.make_update(1, "keep me"))
        conv = self.conversation_for()
        wizard = self.env["telegram.forget.identity"].create({"contact_ids": [(6, 0, conv.contact_id.ids)], "mode": "keep"})
        wizard.action_forget()
        self.assertFalse(conv.contact_id)
        self.assertTrue(any("keep me" in str(b) for b in conv.channel_id.message_ids.mapped("body")))
