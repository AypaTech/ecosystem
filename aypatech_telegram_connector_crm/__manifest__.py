# -*- coding: utf-8 -*-
{
    "name": "Telegram Discuss Connector - CRM",
    "version": "18.0.1.0.0",
    "category": "Sales/CRM",
    "summary": "Create or link CRM leads from Telegram conversations",
    "author": "Aypa Tech",
    "website": "https://aypatech.com",
    "license": "OPL-1",
    "depends": ["aypatech_telegram_connector", "crm"],
    "data": [
        "views/telegram_conversation_views.xml",
        "views/crm_lead_views.xml",
    ],
    "installable": True,
    "auto_install": True,
}
