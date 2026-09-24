from __future__ import annotations

from odoo import fields, models


class MailMessage(models.Model):
    """Link messages to the AI session that produced them."""

    _inherit = 'mail.message'

    # ----------------------------------------------------------
    # Fields
    # ----------------------------------------------------------

    aypatech_ai_session_id = fields.Many2one(
        comodel_name='aypatech_ai.session',
        string='AI Session',
        index='btree_not_null',
        ondelete='cascade',
    )
