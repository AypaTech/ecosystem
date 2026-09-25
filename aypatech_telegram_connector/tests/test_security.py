# -*- coding: utf-8 -*-
import logging

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from ..services import exceptions as exc
from .common import TEST_TOKEN, TelegramCase


@tagged("post_install", "-at_install", "telegram")
class TestSecurity(TelegramCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.outsider = new_test_user(
            cls.env, login="tg_outsider", name="Outsider",
            groups="base.group_user,aypatech_telegram_connector.group_telegram_user",
        )
        cls.employee = new_test_user(cls.env, login="plain_employee", groups="base.group_user")
        cls.other_team = cls.env["telegram.team"].create({"name": "Other", "member_ids": [(6, 0, cls.outsider.ids)]})

    def setUp(self):
        super().setUp()
        self.receive(self.make_update(1, "hi"))
        self.conv = self.conversation_for()

    def test_token_hidden_from_non_admins(self):
        for user in (self.manager, self.agent):
            bot = self.bot.with_user(user)
            with self.assertRaises(AccessError):
                bot.read(["token"])
            with self.assertRaises(AccessError):
                bot.read(["webhook_secret"])
            self.assertEqual(bot.token_masked, "123456789:AAH…saw")

    def test_agent_cannot_manage_bots(self):
        with self.assertRaises(AccessError):
            self.env["telegram.bot"].with_user(self.agent).create({"name": "x"})
        with self.assertRaises(AccessError):
            self.bot.with_user(self.agent).write({"name": "x"})

    def test_plain_employee_sees_nothing(self):
        with self.assertRaises(AccessError):
            self.env["telegram.conversation"].with_user(self.employee).search([])
        channel = self.conv.channel_id.with_user(self.employee)
        self.assertFalse(channel.has_access("read"))

    def test_team_visibility(self):
        Conversation = self.env["telegram.conversation"]
        self.assertIn(self.conv, Conversation.with_user(self.agent2).search([]), "team member")
        self.assertNotIn(self.conv, Conversation.with_user(self.outsider).search([]), "other team")
        self.assertIn(self.conv, Conversation.with_user(self.manager).search([]), "manager")
        self.assertTrue(self.conv.channel_id.with_user(self.agent2).has_access("read"),
                        "team member can open the channel without being a member")
        self.assertFalse(self.conv.channel_id.with_user(self.outsider).has_access("read"))
        self.conv.team_id = self.other_team
        self.assertTrue(self.conv.channel_id.with_user(self.agent).has_access("read"), "assignee keeps access")

    def test_team_member_can_reply_without_membership(self):
        self.bot.default_user_id = False
        self.receive(self.make_update(2, "hi", user_id=424242))
        conv = self.conversation_for(424242)
        conv.channel_id.channel_member_ids.filtered(lambda m: m.partner_id == self.agent2.partner_id).unlink()
        with self.assertQueued(1):
            conv.channel_id.with_user(self.agent2).message_post(
                body="hello", message_type="comment", subtype_xmlid="mail.mt_comment")

    def test_other_company_isolated(self):
        other_company = self.env["res.company"].create({"name": "Other Co"})
        bot2 = self.env["telegram.bot"].create({"name": "B2", "token": TEST_TOKEN, "company_id": other_company.id})
        self.receive(self.make_update(3, "x", user_id=333), bot=bot2)
        conv2 = self.conversation_for(333, bot=bot2)
        self.assertNotIn(conv2, self.env["telegram.conversation"].with_user(self.manager).search([]))
        self.assertNotIn(bot2, self.env["telegram.bot"].with_user(self.manager).search([]))
        self.assertFalse(conv2.channel_id.with_user(self.manager).has_access("read"))

    def test_token_never_in_logs_or_records(self):
        # an unmasked error (TelegramAPI masks already; services must mask again)
        self.api.errors = [exc.TelegramBadRequest(f"https://api.telegram.org/bot{TEST_TOKEN}/sendMessage failed")]
        secret = self.bot.webhook_secret
        with self.assertLogs("odoo.addons.aypatech_telegram_connector", level=logging.INFO) as logs:
            self.conv.channel_id.with_user(self.agent).message_post(
                body="hello", message_type="comment", subtype_xmlid="mail.mt_comment")
            self.deliver()
            self.bot._log("error", "api", f"token {TEST_TOKEN} secret {secret}")
        for line in logs.output:
            self.assertNotIn(TEST_TOKEN, line)
            self.assertNotIn(secret, line)
        for log in self.env["telegram.log"].search([("bot_id", "=", self.bot.id)]):
            self.assertNotIn(TEST_TOKEN, log.message)
            self.assertNotIn(secret, log.message)
        delivery = self.env["telegram.delivery"].search([("conversation_id", "=", self.conv.id)])
        self.assertEqual(delivery.state, "failed_permanent")
        for text in (delivery.error_message, delivery.response_summary, delivery.message_id.error_message,
                     *self.conv.channel_id.message_ids.mapped(lambda m: str(m.body))):
            self.assertNotIn(TEST_TOKEN, text or "")

    def test_tracking_excludes_secrets(self):
        bot = self.bot.with_context(tracking_disable=False)
        bot.write({"token": "999:ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ", "name": "Renamed"})
        self.env.cr.precommit.run()  # tracking values are written at precommit
        tracked = self.tracked_labels(bot)
        self.assertIn("Name", tracked)
        self.assertNotIn("Token", tracked)
        for message in bot.message_ids:
            self.assertNotIn("ZZZZZZZZ", str(message.body))
