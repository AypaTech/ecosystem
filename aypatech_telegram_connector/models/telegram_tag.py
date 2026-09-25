# -*- coding: utf-8 -*-
from random import randint

from odoo import fields, models


class TelegramTag(models.Model):
    _name = "telegram.tag"
    _description = "Telegram Conversation Tag"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer(default=lambda self: randint(1, 11))
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint("UNIQUE(name)", "A tag with this name already exists.")
