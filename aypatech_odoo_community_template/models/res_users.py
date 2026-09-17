from __future__ import annotations

from odoo import fields, models


class ResUsers(models.Model):
    """Add per-user backend UI preferences: sidebar, chatter and dialogs."""

    _inherit = 'res.users'

    # ----------------------------------------------------------
    # Properties
    # ----------------------------------------------------------

    @property
    def SELF_READABLE_FIELDS(self) -> list[str]:
        """Allow users to read their own backend UI preferences."""
        return super().SELF_READABLE_FIELDS + [
            'sidebar_type',
            'chatter_position',
            'dialog_size',
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self) -> list[str]:
        """Allow users to write their own backend UI preferences."""
        return super().SELF_WRITEABLE_FIELDS + [
            'sidebar_type',
            'chatter_position',
            'dialog_size',
        ]

    # ----------------------------------------------------------
    # Fields
    # ----------------------------------------------------------

    sidebar_type = fields.Selection(
        selection=[
            ('invisible', 'Invisible'),
            ('small', 'Small'),
            ('large', 'Large'),
        ],
        string='Sidebar Type',
        default='large',
        required=True,
    )

    chatter_position = fields.Selection(
        selection=[
            ('side', 'Side'),
            ('bottom', 'Bottom'),
        ],
        string='Chatter Position',
        default='side',
        required=True,
    )

    dialog_size = fields.Selection(
        selection=[
            ('minimize', 'Minimize'),
            ('maximize', 'Maximize'),
        ],
        string='Dialog Size',
        default='minimize',
        required=True,
    )
