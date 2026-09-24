# -*- coding: utf-8 -*-
{
    "name": "Telegram Discuss Connector - Aypatech Helpdesk",
    "version": "18.0.1.0.0",
    "category": "After-Sales",
    "summary": "Create helpdesk tickets from Telegram conversations and send ticket replies to Telegram",
    "author": "Aypa Tech",
    "website": "https://aypatech.com",
    "license": "OPL-1",
    "depends": ["aypatech_telegram_connector", "aypatech_helpdesk"],
    "data": [
        "views/telegram_conversation_views.xml",
        "views/aypatech_helpdesk_ticket_views.xml",
    ],
    "installable": True,
    "auto_install": True,
}
