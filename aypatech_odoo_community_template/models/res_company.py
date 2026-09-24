from __future__ import annotations

from odoo import fields, models


class ResCompany(models.Model):
    """Add the sidebar footer image, apps-menu background, and favicon."""

    _inherit = 'res.company'

    # ----------------------------------------------------------
    # Fields
    # ----------------------------------------------------------

    appbar_image = fields.Binary(
        string='Apps Sidebar Footer Image',
        attachment=True,
    )

    background_image = fields.Binary(
        string='Apps Menu Background Image',
        attachment=True,
    )

    favicon = fields.Binary(
        string='Company Favicon',
        attachment=True,
    )
