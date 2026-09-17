from __future__ import annotations

from odoo import models


class IrHttpAppsBar(models.AbstractModel):
    """Expose appsbar image availability per company in the session info."""

    _inherit = 'ir.http'

    def session_info(self) -> dict:
        """Flag companies that carry a sidebar footer image."""
        result = super().session_info()
        if self.env.user._is_internal():
            for company in self.env.user.company_ids.with_context(bin_size=True):
                result['user_companies']['allowed_companies'][company.id].update(
                    {
                        'has_appsbar_image': bool(company.appbar_image),
                    }
                )
        return result


class IrHttpChatter(models.AbstractModel):
    """Expose the user chatter position in the session info."""

    _inherit = 'ir.http'

    def session_info(self) -> dict:
        """Add the user chatter position to the session info."""
        result = super().session_info()
        result['chatter_position'] = self.env.user.chatter_position
        return result


class IrHttpDialog(models.AbstractModel):
    """Expose the user dialog size preference through the session info."""

    _inherit = 'ir.http'

    def session_info(self) -> dict:
        """Add the current user dialog size to the session info payload."""
        result = super().session_info()
        result['dialog_size'] = self.env.user.dialog_size
        return result


class IrHttpRefresh(models.AbstractModel):
    """Expose the configured pager auto-load interval to the web client."""

    _inherit = 'ir.http'

    def session_info(self) -> dict:
        """Add the pager auto-load interval to the session information."""
        result = super().session_info()
        result['pager_autoload_interval'] = int(
            self.env['ir.config_parameter']
            .sudo()
            .get_param(
                'aypatech_odoo_community_template.pager_autoload_interval',
                default=30000,
            )
        )
        return result


class IrHttpAppsMenu(models.AbstractModel):
    """Expose apps-menu background image availability in the session info."""

    _inherit = 'ir.http'

    def session_info(self) -> dict:
        """Flag companies that carry an apps-menu background image."""
        result = super().session_info()
        if self.env.user._is_internal():
            for company in self.env.user.company_ids.with_context(bin_size=True):
                result['user_companies']['allowed_companies'][company.id].update(
                    {
                        'has_background_image': bool(company.background_image),
                    }
                )
        return result
