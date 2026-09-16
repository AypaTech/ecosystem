# Copyright 2026 - Aypa Tech - www.aypatech.com
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)

from odoo import fields, models


class AypatechHelpdeskCategory(models.Model):
    _name = 'aypatech.helpdesk.category'
    _description = "Helpdesk Ticket Category"
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
