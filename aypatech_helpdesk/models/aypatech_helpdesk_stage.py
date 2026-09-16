# Copyright 2026 - Aypa Tech - www.aypatech.com
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)

from odoo import fields, models


class AypatechHelpdeskStage(models.Model):
    _name = 'aypatech.helpdesk.stage'
    _description = "Helpdesk Stage"
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(string="Folded in Kanban")
    closed = fields.Boolean(
        string="Closing Stage",
        help="Tickets reaching this stage are considered resolved/closed.",
    )
    active = fields.Boolean(default=True)
