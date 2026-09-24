# -*- coding: utf-8 -*-
from odoo import fields, models


class AypatechMailTag(models.Model):
    """Free-form per-message tag - deliberately separate from
    aypatech.mail.label. A Label is an organizational category the user
    picks from a fixed, curated list (shown as sidebar navigation, one
    message can belong to a few). A Tag is closer to a hashtag: anyone can
    invent a new one inline while tagging a single message, existing tags
    are reused by name, and there is no dedicated navigation surface for
    them - they only ever show up on the message itself.
    """
    _name = "aypatech.mail.tag"
    _description = "Mail Tag"
    _order = "name"

    name = fields.Char(required=True)
    account_id = fields.Many2one("aypatech.mail.account", required=True, ondelete="cascade", index=True)
    message_ids = fields.Many2many("aypatech.mail.message", string="Messages")

    _sql_constraints = [
        ('name_account_uniq', 'UNIQUE (account_id, name)', 'This tag already exists for this account.'),
    ]

