# -*- coding: utf-8 -*-
from odoo import fields, models


class AypatechMailLabel(models.Model):
    """User-defined organizational tag (Gmail-style "Label"), scoped to one
    mailbox account so shared-mailbox users see the same set of labels.
    Independent of folder_id: a label is metadata on a message, not a
    location, so applying/removing a label never moves the message between
    real IMAP folders.
    """
    _name = "aypatech.mail.label"
    _description = "Mail Label"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer(default=1, help="Index into the standard Odoo color palette.")
    account_id = fields.Many2one("aypatech.mail.account", required=True, ondelete="cascade", index=True)
    message_ids = fields.Many2many("aypatech.mail.message", string="Messages")
    message_count = fields.Integer(compute="_compute_message_count")

    _name_account_uniq = models.Constraint(
        "UNIQUE (account_id, name)", "This label already exists for this account.",
    )

    def _compute_message_count(self):
        counts = self.env["aypatech.mail.message"]._read_group(
            [("label_ids", "in", self.ids)], ["label_ids"], ["__count"]
        )
        count_by_label = {label.id: count for label, count in counts}
        for label in self:
            label.message_count = count_by_label.get(label.id, 0)
