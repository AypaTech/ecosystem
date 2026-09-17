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
            'appsbar_theme',
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self) -> list[str]:
        """Allow users to write their own backend UI preferences."""
        return super().SELF_WRITEABLE_FIELDS + [
            'sidebar_type',
            'chatter_position',
            'dialog_size',
            'appsbar_theme',
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

    appsbar_theme = fields.Selection(
        # Keep the preset keys/labels in sync with THEME_PRESETS in
        # models/res_config_settings.py.
        selection=[
            ('company_default', 'Company Default'),
            ('odoo_classic', 'Odoo Classic'),
            ('ocean_blue', 'Ocean Blue'),
            ('forest_green', 'Forest Green'),
            ('sunset_orange', 'Sunset Orange'),
            ('slate_gray', 'Slate Gray'),
            ('royal_purple', 'Royal Purple'),
        ],
        string='Sidebar Color Theme',
        default='company_default',
        required=True,
    )
