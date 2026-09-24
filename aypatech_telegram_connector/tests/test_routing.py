# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import TelegramCase


@tagged("post_install", "-at_install", "telegram")
class TestRouting(TelegramCase):

    def setUp(self):
        super().setUp()
        self.bot.default_user_id = False
        self.vip_team = self.env["telegram.team"].create({"name": "VIP", "member_ids": [(6, 0, self.agent2.ids)]})
        self.tag = self.env["telegram.tag"].create({"name": "Pricing"})

    def test_keyword_route(self):
        self.env["telegram.route"].create({
            "bot_id": self.bot.id, "name": "price", "sequence": 1, "condition_type": "keyword",
            "condition_value": "price, quote", "team_id": self.vip_team.id, "tag_ids": [(6, 0, self.tag.ids)],
        })
        self.receive(self.make_update(1, "What is the PRICE?"))
        conv = self.conversation_for()
        self.assertEqual(conv.team_id, self.vip_team)
        self.assertEqual(conv.tag_ids, self.tag)

    def test_language_route_and_sequence(self):
        self.env["telegram.route"].create([
            {"bot_id": self.bot.id, "name": "english", "sequence": 1, "condition_type": "language",
             "condition_value": "en", "user_id": self.agent.id},
            {"bot_id": self.bot.id, "name": "persian", "sequence": 2, "condition_type": "language",
             "condition_value": "fa", "user_id": self.agent2.id},
        ])
        self.receive(self.make_update(1, "salam"))  # fixture language_code = fa
        self.assertEqual(self.conversation_for().user_id, self.agent2)

    def test_new_customer_route(self):
        self.env["telegram.route"].create({
            "bot_id": self.bot.id, "name": "new", "condition_type": "new_customer", "team_id": self.vip_team.id,
        })
        self.receive(self.make_update(1, "first time"))
        self.assertEqual(self.conversation_for().team_id, self.vip_team)

    def test_fallback_to_bot_team_manual_adds_team_members(self):
        self.receive(self.make_update(1, "hi"))
        conv = self.conversation_for()
        self.assertEqual(conv.team_id, self.team)
        self.assertFalse(conv.user_id, "manual assignment")
        members = conv.channel_id.channel_member_ids.partner_id
        self.assertIn(self.agent.partner_id, members)
        self.assertIn(self.agent2.partner_id, members)

    def test_round_robin(self):
        self.team.assignment_method = "round_robin"
        users = []
        for user_id in (1, 2, 3):
            self.receive(self.make_update(user_id, "hi", user_id=user_id))
            users.append(self.conversation_for(user_id).user_id)
        ordered = (self.agent | self.agent2).sorted("id")
        self.assertEqual(users, [ordered[0], ordered[1], ordered[0]])

    def test_least_busy(self):
        self.team.assignment_method = "least_busy"
        self.receive(self.make_update(1, "hi", user_id=1))
        first = self.conversation_for(1).user_id
        self.receive(self.make_update(2, "hi", user_id=2))
        second = self.conversation_for(2).user_id
        self.assertNotEqual(first, second)

    def test_reassignment_is_tracked_and_member_added(self):
        self.receive(self.make_update(1, "hi"))
        conv = self.conversation_for().with_context(tracking_disable=False)
        conv.with_user(self.agent2).action_assign_to_me()
        self.env.cr.precommit.run()  # tracking values are written at precommit
        self.assertEqual(conv.user_id, self.agent2)
        self.assertIn(self.agent2.partner_id, conv.channel_id.channel_member_ids.partner_id)
        self.assertTrue(conv.message_ids.tracking_value_ids.filtered(lambda t: t.field_id.name == "user_id"))

    def test_remove_previous_assignee_setting(self):
        self.env["ir.config_parameter"].sudo().set_param("telegram.remove_previous_assignee", "True")
        self.bot.default_user_id = self.agent
        self.receive(self.make_update(1, "hi"))
        conv = self.conversation_for()
        conv.user_id = self.agent2
        members = conv.channel_id.channel_member_ids.partner_id
        self.assertIn(self.agent2.partner_id, members)
        self.assertNotIn(self.agent.partner_id, members)
