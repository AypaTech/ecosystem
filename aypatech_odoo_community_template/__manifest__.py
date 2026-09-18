# -*- coding: utf-8 -*-
{
    'name': "Aypatech Odoo Community Template",
    'summary': "Aypa Tech's backend UI baseline: app sidebar, chatter, dialogs, "
               "theme colors, grouping and view-refresh tools",
    'description': """
Aypatech Odoo Community Template
=================================
Aypa Tech's own backend UI foundation, built to give every Aypa Tech
deployment the same everyday comfort features:

- App sidebar: a persistent list of installed apps down the side of the
  screen, with a per-user size preference (large, small or hidden) and an
  optional company logo/footer image.
- Full-screen apps menu: replaces the default apps dropdown with a
  full-screen app grid over an optional company background image, with
  the command palette opening as soon as you start typing.
- Chatter upgrades: side or bottom chatter placement per user, a resizable
  side chatter, a show/hide toggle for system notification messages, and a
  clear separation between messages sent to the customer and internal notes
  routed only to internal followers.
- Dialog controls: a per-user default dialog size and a one-click fullscreen
  toggle on every dialog and select/create popup.
- Theme & branding settings: light/dark color pickers for the core Odoo
  palette and for the app sidebar, a company favicon, and a sidebar logo,
  all editable from Settings and reset back to their defaults on demand.
- View grouping: "Expand All" / "Collapse All" actions in the list and
  kanban cog menu for grouped views.
- View refresh: a manual refresh button in the control panel, with an
  optional auto-refresh timer, plus a "Reload Views" server action type to
  push view refreshes to connected users over the bus (e.g. from automation
  rules).
    """,
    'author': "Aypa Tech",
    'website': 'https://www.aypatech.com',
    'license': 'LGPL-3',
    'category': 'Tools/UI',
    'version': '20.0.1.0.0',
    'depends': [
        'base_setup',
        'web',
        'mail',
        'bus',
        'base_automation',
    ],
    'data': [
        'views/res_config_settings.xml',
        'views/res_users.xml',
        'views/ir_actions_server_views.xml',
        'templates/webclient.xml',
        'templates/web_layout.xml',
    ],
    'demo': [
        'demo/base_automation.xml',
        'demo/ir_actions_server.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            'aypatech_odoo_community_template/static/src/scss/appsbar_variables.scss',
            ('prepend', 'aypatech_odoo_community_template/static/src/scss/colors/colors.scss'),
            (
                'before',
                'aypatech_odoo_community_template/static/src/scss/colors/colors.scss',
                'aypatech_odoo_community_template/static/src/scss/colors/colors_light.scss',
            ),
            (
                'before',
                'aypatech_odoo_community_template/static/src/scss/colors/colors.scss',
                'aypatech_odoo_community_template/static/src/scss/colors/appbar_colors_light.scss',
            ),
            'aypatech_odoo_community_template/static/src/scss/colors/appbar_theme_overrides_light.scss',
            (
                'after',
                'web/static/src/scss/primary_variables.scss',
                'aypatech_odoo_community_template/static/src/scss/form_variables.scss',
            ),
            (
                'after',
                'web/static/src/scss/primary_variables.scss',
                'aypatech_odoo_community_template/static/src/scss/theme_variables.scss',
            ),
        ],
        'web._assets_backend_helpers': [
            'aypatech_odoo_community_template/static/src/scss/mixins.scss',
        ],
        'web.assets_web_dark': [
            (
                'after',
                'aypatech_odoo_community_template/static/src/scss/appsbar_variables.scss',
                'aypatech_odoo_community_template/static/src/scss/appsbar_variables.dark.scss',
            ),
            (
                'after',
                'aypatech_odoo_community_template/static/src/scss/colors/colors.scss',
                'aypatech_odoo_community_template/static/src/scss/colors/colors_dark.scss',
            ),
            (
                'after',
                'aypatech_odoo_community_template/static/src/scss/colors/colors.scss',
                'aypatech_odoo_community_template/static/src/scss/colors/appbar_colors_dark.scss',
            ),
            'aypatech_odoo_community_template/static/src/scss/colors/appbar_theme_overrides_dark.scss',
            'aypatech_odoo_community_template/static/src/views/form/form.dark.scss',
        ],
        'web.assets_backend': [
            (
                'after',
                'web/static/src/webclient/webclient.js',
                'aypatech_odoo_community_template/static/src/webclient/webclient.js',
            ),
            (
                'after',
                'web/static/src/webclient/webclient.xml',
                'aypatech_odoo_community_template/static/src/webclient/webclient.xml',
            ),
            (
                'after',
                'web/static/src/webclient/webclient.js',
                'aypatech_odoo_community_template/static/src/webclient/menus/app_menu_service.js',
            ),
            (
                'after',
                'web/static/src/webclient/webclient.js',
                'aypatech_odoo_community_template/static/src/webclient/appsbar/appsbar.js',
            ),
            'aypatech_odoo_community_template/static/src/webclient/webclient.scss',
            'aypatech_odoo_community_template/static/src/webclient/appsbar/appsbar.xml',
            'aypatech_odoo_community_template/static/src/webclient/appsbar/appsbar.scss',
            'aypatech_odoo_community_template/static/src/webclient/appsmenu/appsmenu.js',
            'aypatech_odoo_community_template/static/src/webclient/appsmenu/appsmenu.scss',
            'aypatech_odoo_community_template/static/src/webclient/appsmenu/widgets/appsmenu_widgets.js',
            'aypatech_odoo_community_template/static/src/webclient/appsmenu/widgets/appsmenu_widgets.xml',
            'aypatech_odoo_community_template/static/src/webclient/appsmenu/widgets/appsmenu_widgets.scss',
            'aypatech_odoo_community_template/static/src/webclient/navbar/navbar.js',
            'aypatech_odoo_community_template/static/src/webclient/navbar/navbar.xml',
            'aypatech_odoo_community_template/static/src/webclient/navbar/navbar.scss',
            'aypatech_odoo_community_template/static/src/core/recipients_list/recipients_list.js',
            'aypatech_odoo_community_template/static/src/core/recipients_list/recipients_list.xml',
            'aypatech_odoo_community_template/static/src/core/recipients_popover/recipients_popover.js',
            'aypatech_odoo_community_template/static/src/core/recipients_popover/recipients_popover.xml',
            'aypatech_odoo_community_template/static/src/core/thread/thread.js',
            'aypatech_odoo_community_template/static/src/chatter/chatter.scss',
            'aypatech_odoo_community_template/static/src/chatter/chatter.xml',
            (
                'after',
                'mail/static/src/chatter/web_portal_project/chatter.js',
                'aypatech_odoo_community_template/static/src/chatter/chatter.js',
            ),
            (
                'after',
                'mail/static/src/core/common/composer.js',
                'aypatech_odoo_community_template/static/src/chatter/composer.js',
            ),
            (
                'after',
                'mail/static/src/core/common/store_service.js',
                'aypatech_odoo_community_template/static/src/chatter/store_service.js',
            ),
            (
                'after',
                'mail/static/src/chatter/web/form_compiler.js',
                'aypatech_odoo_community_template/static/src/views/form/form_compiler.js',
            ),
            'aypatech_odoo_community_template/static/src/views/form/form_renderer.js',
            (
                'after',
                'web/static/src/core/dialog/dialog.js',
                'aypatech_odoo_community_template/static/src/core/dialog/dialog.js',
            ),
            (
                'after',
                'web/static/src/core/dialog/dialog.scss',
                'aypatech_odoo_community_template/static/src/core/dialog/dialog.scss',
            ),
            (
                'after',
                'web/static/src/core/dialog/dialog.xml',
                'aypatech_odoo_community_template/static/src/core/dialog/dialog.xml',
            ),
            'aypatech_odoo_community_template/static/src/search/collapse_all/collapse_all.js',
            'aypatech_odoo_community_template/static/src/search/collapse_all/collapse_all.xml',
            'aypatech_odoo_community_template/static/src/search/expand_all/expand_all.js',
            'aypatech_odoo_community_template/static/src/search/expand_all/expand_all.xml',
            'aypatech_odoo_community_template/static/src/core/refresh/utils.js',
            'aypatech_odoo_community_template/static/src/scss/refresh.scss',
            (
                'after',
                'web/static/src/search/control_panel/control_panel.js',
                'aypatech_odoo_community_template/static/src/search/control_panel.js',
            ),
            (
                'after',
                'web/static/src/search/control_panel/control_panel.xml',
                'aypatech_odoo_community_template/static/src/search/control_panel.xml',
            ),
            'aypatech_odoo_community_template/static/src/services/refresh_service.js',
            'aypatech_odoo_community_template/static/src/views/form/form.scss',
            'aypatech_odoo_community_template/static/src/scss/theme_presets.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': '_setup_module',
    'uninstall_hook': '_uninstall_cleanup',
}
