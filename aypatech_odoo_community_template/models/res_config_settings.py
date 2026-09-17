from __future__ import annotations

from odoo import fields, models


class ResConfigSettingsAppsBar(models.TransientModel):
    """Expose the company sidebar footer image in the general settings."""

    _inherit = 'res.config.settings'

    appbar_image = fields.Binary(
        related='company_id.appbar_image',
        readonly=False,
    )


class ResConfigSettingsColors(models.TransientModel):
    """Expose theme color variables as light and dark configuration fields."""

    _inherit = 'res.config.settings'

    # ----------------------------------------------------------
    # Properties
    # ----------------------------------------------------------

    @property
    def COLOR_FIELDS(self) -> list[str]:
        """Return the names of the customizable color variables."""
        return [
            'color_brand',
            'color_primary',
            'color_success',
            'color_info',
            'color_warning',
            'color_danger',
        ]

    @property
    def COLOR_ASSET_LIGHT_URL(self) -> str:
        """Return the SCSS asset URL for light mode colors."""
        return '/aypatech_odoo_community_template/static/src/scss/colors/colors_light.scss'

    @property
    def COLOR_BUNDLE_LIGHT_NAME(self) -> str:
        """Return the asset bundle name for light mode colors."""
        return 'web._assets_primary_variables'

    @property
    def COLOR_ASSET_DARK_URL(self) -> str:
        """Return the SCSS asset URL for dark mode colors."""
        return '/aypatech_odoo_community_template/static/src/scss/colors/colors_dark.scss'

    @property
    def COLOR_BUNDLE_DARK_NAME(self) -> str:
        """Return the asset bundle name for dark mode colors."""
        return 'web.assets_web_dark'

    # ----------------------------------------------------------
    # Fields Light Mode
    # ----------------------------------------------------------

    color_brand_light = fields.Char(string='Brand Light Color')

    color_primary_light = fields.Char(string='Primary Light Color')

    color_success_light = fields.Char(string='Success Light Color')

    color_info_light = fields.Char(string='Info Light Color')

    color_warning_light = fields.Char(string='Warning Light Color')

    color_danger_light = fields.Char(string='Danger Light Color')

    # ----------------------------------------------------------
    # Fields Dark Mode
    # ----------------------------------------------------------

    color_brand_dark = fields.Char(string='Brand Dark Color')

    color_primary_dark = fields.Char(string='Primary Dark Color')

    color_success_dark = fields.Char(string='Success Dark Color')

    color_info_dark = fields.Char(string='Info Dark Color')

    color_warning_dark = fields.Char(string='Warning Dark Color')

    color_danger_dark = fields.Char(string='Danger Dark Color')

    # ----------------------------------------------------------
    # Helper
    # ----------------------------------------------------------

    def _get_light_color_values(self) -> dict:
        """Return the current light mode color values from the saved asset."""
        return self.env[
            'aypatech_odoo_community_template.color_assets_editor'
        ].get_color_variables_values(
            self.COLOR_ASSET_LIGHT_URL,
            self.COLOR_BUNDLE_LIGHT_NAME,
            self.COLOR_FIELDS,
        )

    def _get_dark_color_values(self) -> dict:
        """Return the current dark mode color values from the saved asset."""
        return self.env[
            'aypatech_odoo_community_template.color_assets_editor'
        ].get_color_variables_values(
            self.COLOR_ASSET_DARK_URL,
            self.COLOR_BUNDLE_DARK_NAME,
            self.COLOR_FIELDS,
        )

    def _set_light_color_values(self, values: dict) -> dict:
        """Populate ``values`` with the current light mode color values."""
        colors = self._get_light_color_values()
        for var, value in colors.items():
            values[f'{var}_light'] = value
        return values

    def _set_dark_color_values(self, values: dict) -> dict:
        """Populate ``values`` with the current dark mode color values."""
        colors = self._get_dark_color_values()
        for var, value in colors.items():
            values[f'{var}_dark'] = value
        return values

    def _detect_light_color_change(self) -> bool:
        """Return whether any light mode color field differs from the asset."""
        colors = self._get_light_color_values()
        return any(self[f'{var}_light'] != val for var, val in colors.items())

    def _detect_dark_color_change(self) -> bool:
        """Return whether any dark mode color field differs from the asset."""
        colors = self._get_dark_color_values()
        return any(self[f'{var}_dark'] != val for var, val in colors.items())

    def _replace_light_color_values(self) -> None:
        """Save the current light mode color fields to the customized asset."""
        variables = [
            {'name': field, 'value': self[f'{field}_light']}
            for field in self.COLOR_FIELDS
        ]
        return self.env[
            'aypatech_odoo_community_template.color_assets_editor'
        ].replace_color_variables_values(
            self.COLOR_ASSET_LIGHT_URL,
            self.COLOR_BUNDLE_LIGHT_NAME,
            variables,
        )

    def _replace_dark_color_values(self) -> None:
        """Save the current dark mode color fields to the customized asset."""
        variables = [
            {'name': field, 'value': self[f'{field}_dark']}
            for field in self.COLOR_FIELDS
        ]
        return self.env[
            'aypatech_odoo_community_template.color_assets_editor'
        ].replace_color_variables_values(
            self.COLOR_ASSET_DARK_URL,
            self.COLOR_BUNDLE_DARK_NAME,
            variables,
        )

    def _reset_light_color_assets(self) -> None:
        """Remove the customized light mode color asset."""
        self.env['aypatech_odoo_community_template.color_assets_editor'].reset_color_asset(
            self.COLOR_ASSET_LIGHT_URL,
            self.COLOR_BUNDLE_LIGHT_NAME,
        )

    def _reset_dark_color_assets(self) -> None:
        """Remove the customized dark mode color asset."""
        self.env['aypatech_odoo_community_template.color_assets_editor'].reset_color_asset(
            self.COLOR_ASSET_DARK_URL,
            self.COLOR_BUNDLE_DARK_NAME,
        )

    # ----------------------------------------------------------
    # Action
    # ----------------------------------------------------------

    def action_reset_light_color_assets(self) -> dict:
        """Reset light mode colors and reload the client."""
        self._reset_light_color_assets()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_reset_dark_color_assets(self) -> dict:
        """Reset dark mode colors and reload the client."""
        self._reset_dark_color_assets()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    # ----------------------------------------------------------
    # Functions
    # ----------------------------------------------------------

    def get_values(self) -> dict:
        """Add the stored light and dark color values to the settings values."""
        res = super().get_values()
        res = self._set_light_color_values(res)
        return self._set_dark_color_values(res)

    def set_values(self) -> None:
        """Persist changed light and dark color values to their assets."""
        res = super().set_values()
        if self._detect_light_color_change():
            self._replace_light_color_values()
        if self._detect_dark_color_change():
            self._replace_dark_color_values()
        return res


class ResConfigSettingsTheme(models.TransientModel):
    """Add backend favicon and app sidebar color settings."""

    _inherit = 'res.config.settings'

    @property
    def THEME_COLOR_FIELDS(self) -> list[str]:
        """Return the appsbar color variable names managed by this theme."""
        return [
            'color_appsmenu_text',
            'color_appbar_text',
            'color_appbar_active',
            'color_appbar_background',
        ]

    @property
    def COLOR_ASSET_THEME_LIGHT_URL(self) -> str:
        """Return the URL of the light theme color asset."""
        return '/aypatech_odoo_community_template/static/src/scss/colors/appbar_colors_light.scss'

    @property
    def COLOR_BUNDLE_THEME_LIGHT_NAME(self) -> str:
        """Return the asset bundle name holding the light theme colors."""
        return 'web._assets_primary_variables'

    @property
    def COLOR_ASSET_THEME_DARK_URL(self) -> str:
        """Return the URL of the dark theme color asset."""
        return '/aypatech_odoo_community_template/static/src/scss/colors/appbar_colors_dark.scss'

    @property
    def COLOR_BUNDLE_THEME_DARK_NAME(self) -> str:
        """Return the asset bundle name holding the dark theme colors."""
        return 'web.assets_web_dark'

    # ----------------------------------------------------------
    # Fields
    # ----------------------------------------------------------

    theme_favicon = fields.Binary(
        related='company_id.favicon',
        readonly=False,
    )

    theme_background_image = fields.Binary(
        related='company_id.background_image',
        readonly=False,
    )

    theme_color_appsmenu_text_light = fields.Char(
        string='Apps Menu Text Light Color',
    )

    theme_color_appsmenu_text_dark = fields.Char(
        string='Apps Menu Text Dark Color',
    )

    theme_color_appbar_text_light = fields.Char(
        string='AppsBar Text Light Color',
    )

    theme_color_appbar_active_light = fields.Char(
        string='AppsBar Active Light Color',
    )

    theme_color_appbar_background_light = fields.Char(
        string='AppsBar Background Light Color',
    )

    theme_color_appbar_text_dark = fields.Char(
        string='AppsBar Text Dark Color',
    )

    theme_color_appbar_active_dark = fields.Char(
        string='AppsBar Active Dark Color',
    )

    theme_color_appbar_background_dark = fields.Char(
        string='AppsBar Background Dark Color',
    )

    # ----------------------------------------------------------
    # Helper
    # ----------------------------------------------------------

    def _get_light_theme_color_values(self) -> dict:
        """Return the current light theme color values from the editor."""
        return self.env[
            'aypatech_odoo_community_template.color_assets_editor'
        ].get_color_variables_values(
            self.COLOR_ASSET_THEME_LIGHT_URL,
            self.COLOR_BUNDLE_THEME_LIGHT_NAME,
            self.THEME_COLOR_FIELDS,
        )

    def _get_dark_theme_color_values(self) -> dict:
        """Return the current dark theme color values from the editor."""
        return self.env[
            'aypatech_odoo_community_template.color_assets_editor'
        ].get_color_variables_values(
            self.COLOR_ASSET_THEME_DARK_URL,
            self.COLOR_BUNDLE_THEME_DARK_NAME,
            self.THEME_COLOR_FIELDS,
        )

    def _set_light_theme_color_values(self, values: dict) -> dict:
        """Populate the light theme color fields into the settings values."""
        colors = self._get_light_theme_color_values()
        for var, value in colors.items():
            values[f'theme_{var}_light'] = value
        return values

    def _set_dark_theme_color_values(self, values: dict) -> dict:
        """Populate the dark theme color fields into the settings values."""
        colors = self._get_dark_theme_color_values()
        for var, value in colors.items():
            values[f'theme_{var}_dark'] = value
        return values

    def _detect_light_theme_color_change(self) -> bool:
        """Return whether any light theme color value differs from the asset."""
        colors = self._get_light_theme_color_values()
        return any(self[f'theme_{var}_light'] != val for var, val in colors.items())

    def _detect_dark_theme_color_change(self) -> bool:
        """Return whether any dark theme color value differs from the asset."""
        colors = self._get_dark_theme_color_values()
        return any(self[f'theme_{var}_dark'] != val for var, val in colors.items())

    def _replace_light_theme_color_values(self):
        """Write the configured light theme color values into the asset."""
        variables = [
            {
                'name': field,
                'value': self[f'theme_{field}_light'],
            }
            for field in self.THEME_COLOR_FIELDS
        ]
        return self.env[
            'aypatech_odoo_community_template.color_assets_editor'
        ].replace_color_variables_values(
            self.COLOR_ASSET_THEME_LIGHT_URL,
            self.COLOR_BUNDLE_THEME_LIGHT_NAME,
            variables,
        )

    def _replace_dark_theme_color_values(self):
        """Write the configured dark theme color values into the asset."""
        variables = [
            {
                'name': field,
                'value': self[f'theme_{field}_dark'],
            }
            for field in self.THEME_COLOR_FIELDS
        ]
        return self.env[
            'aypatech_odoo_community_template.color_assets_editor'
        ].replace_color_variables_values(
            self.COLOR_ASSET_THEME_DARK_URL,
            self.COLOR_BUNDLE_THEME_DARK_NAME,
            variables,
        )

    def _reset_light_theme_color_assets(self) -> None:
        """Reset the light theme color asset to its default values."""
        self.env['aypatech_odoo_community_template.color_assets_editor'].reset_color_asset(
            self.COLOR_ASSET_THEME_LIGHT_URL,
            self.COLOR_BUNDLE_THEME_LIGHT_NAME,
        )

    def _reset_dark_theme_color_assets(self) -> None:
        """Reset the dark theme color asset to its default values."""
        self.env['aypatech_odoo_community_template.color_assets_editor'].reset_color_asset(
            self.COLOR_ASSET_THEME_DARK_URL,
            self.COLOR_BUNDLE_THEME_DARK_NAME,
        )

    # ----------------------------------------------------------
    # Action
    # ----------------------------------------------------------

    def action_reset_light_theme_color_assets(self):
        """Reset the light theme color asset and reload the client."""
        self._reset_light_theme_color_assets()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_reset_dark_theme_color_assets(self):
        """Reset the dark theme color asset and reload the client."""
        self._reset_dark_theme_color_assets()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    # ----------------------------------------------------------
    # Functions
    # ----------------------------------------------------------

    def get_values(self) -> dict:
        """Add the light and dark theme color values to the settings."""
        res = super().get_values()
        res = self._set_light_theme_color_values(res)
        return self._set_dark_theme_color_values(res)

    def set_values(self):
        """Persist changed light and dark theme color values into the assets."""
        res = super().set_values()
        if self._detect_light_theme_color_change():
            self._replace_light_theme_color_values()
        if self._detect_dark_theme_color_change():
            self._replace_dark_theme_color_values()
        return res
