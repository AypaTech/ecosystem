# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TelegramConversation(models.Model):
    _inherit = "telegram.conversation"

    sale_order_ids = fields.Many2many(
        "sale.order", string="Linked Orders", compute="_compute_sale_order_ids",
        help="Sale orders of the customer (and their company).",
    )
    sale_order_count = fields.Integer(compute="_compute_sale_order_ids")

    @api.depends("partner_id")
    def _compute_sale_order_ids(self):
        SaleOrder = self.env["sale.order"]
        can_read = SaleOrder.has_access("read")
        for conv in self:
            orders = SaleOrder
            if can_read and conv.partner_id:
                orders = SaleOrder.search([
                    ("partner_id", "child_of", conv.partner_id.commercial_partner_id.id),
                    ("company_id", "=", conv.company_id.id),
                ])
            conv.sale_order_ids = orders
            conv.sale_order_count = len(orders)

    def action_open_sale_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("sale.action_quotations_with_onboarding")
        action["domain"] = [("id", "in", self.sale_order_ids.ids)]
        action["context"] = {"default_partner_id": self.partner_id.id}
        return action

    def action_new_quotation(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "form",
            "views": [(False, "form")],
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_user_id": (self.user_id or self.env.user).id,
                "default_company_id": self.company_id.id,
            },
        }
