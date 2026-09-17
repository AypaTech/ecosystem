from __future__ import annotations

from . import models

import base64

from odoo.api import Environment
from odoo.tools import file_open


def _setup_module(env: Environment) -> None:
    """Seed the main company's sidebar footer image and favicon."""
    main_company = env.ref('base.main_company', False)
    if not main_company:
        return
    with file_open('base/static/img/res_company_logo.png', 'rb') as file:
        main_company.appbar_image = base64.b64encode(file.read()).decode()
    with file_open('web/static/img/favicon.ico', 'rb') as file:
        main_company.favicon = base64.b64encode(file.read()).decode()


def _uninstall_cleanup(env: Environment) -> None:
    """Reset every customized theme color asset on uninstall."""
    settings = env['res.config.settings']
    settings._reset_light_color_assets()
    settings._reset_dark_color_assets()
    settings._reset_light_theme_color_assets()
    settings._reset_dark_theme_color_assets()
