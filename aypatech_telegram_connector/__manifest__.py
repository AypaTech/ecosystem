# -*- coding: utf-8 -*-
{
    "name": "Telegram Discuss Connector",
    "version": "18.0.1.0.0",
    "category": "Productivity/Discuss",
    "summary": "Chat with your customers on Telegram from Odoo Discuss: webhook or polling, multi-bot, media, routing, delivery queue",
    "description": """
Connect one or more Telegram bots to Odoo Discuss. Customers write to your bot,
agents answer from Discuss. Webhook or polling, durable outbound queue with
retries, team routing, tags, logs and a setup wizard.
    """,
    "author": "Aypa Tech",
    "website": "https://aypatech.com",
    "license": "OPL-1",
    "depends": ["mail", "base_setup"],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "security/telegram_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter_data.xml",
        "data/ir_cron.xml",
        "views/telegram_bot_views.xml",
        "views/telegram_conversation_views.xml",
        "views/telegram_contact_views.xml",
        "views/telegram_chat_views.xml",
        "views/telegram_message_views.xml",
        "views/telegram_delivery_views.xml",
        "views/telegram_update_views.xml",
        "views/telegram_team_views.xml",
        "views/telegram_route_views.xml",
        "views/telegram_tag_views.xml",
        "views/telegram_log_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/telegram_setup_views.xml",
        "wizard/telegram_forget_identity_views.xml",
        "views/telegram_dashboard_views.xml",
        "views/menus.xml",
    ],
    "demo": [
        "demo/telegram_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "aypatech_telegram_connector/static/src/discuss/**/*",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
