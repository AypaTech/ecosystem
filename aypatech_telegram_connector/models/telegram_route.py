# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TelegramRoute(models.Model):
    _name = "telegram.route"
    _description = "Telegram Routing Rule"
    _order = "bot_id, sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True)
    bot_id = fields.Many2one("telegram.bot", required=True, index=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="bot_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    condition_type = fields.Selection(
        [
            ("always", "Always"),
            ("keyword", "Message contains keyword"),
            ("language", "Customer language"),
            ("new_customer", "New customer"),
        ],
        default="always", required=True,
    )
    condition_value = fields.Char(
        help="Keyword: comma separated words (case insensitive). Language: comma separated codes, e.g. fa,en.",
    )
    team_id = fields.Many2one("telegram.team", check_company=True)
    user_id = fields.Many2one("res.users", string="Assignee", domain="[('share', '=', False)]")
    tag_ids = fields.Many2many("telegram.tag", string="Tags")

    @api.constrains("condition_type", "condition_value")
    def _check_condition_value(self):
        for route in self:
            if route.condition_type in ("keyword", "language") and not (route.condition_value or "").strip():
                raise ValidationError(self.env._("Route '%s' needs a condition value.", route.name))
