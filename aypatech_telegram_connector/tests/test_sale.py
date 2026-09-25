# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.aypatech_telegram_connector.tests.common import TelegramCase


@tagged("post_install", "-at_install", "telegram")
class TestTelegramSale(TelegramCase):

    def test_linked_orders(self):
        self.receive(self.make_update(1, "where is my order?"))
        conv = self.conversation_for()
        self.assertEqual(conv.sale_order_count, 0)
        order = self.env["sale.order"].create({"partner_id": conv.partner_id.id})
        conv.invalidate_recordset(["sale_order_ids", "sale_order_count"])
        self.assertEqual(conv.sale_order_ids, order)
        action = conv.action_open_sale_orders()
        self.assertEqual(action["domain"], [("id", "in", order.ids)])
        self.assertEqual(conv.action_new_quotation()["context"]["default_partner_id"], conv.partner_id.id)
