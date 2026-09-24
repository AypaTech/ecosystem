# -*- coding: utf-8 -*-
{
    "name": "Aypatech Mail",
    "version": "20.0.1.0.0",
    "category": "Discuss",
    "summary": "Business Email Client & Communication Layer for Odoo, backed by Mailcow",
    "description": """
Aypatech Mail
=============
A real email client inside Odoo, using Mailcow as the mail infrastructure:

- IMAP/SMTP for actual mailbox operations (read, send).
- Mailcow REST API for administration only (domain / mailbox / alias /
  quota) - never direct DB access to Mailcow.
- Incremental IMAP sync (UID/UIDVALIDITY based), running as background
  cron jobs, never on the HTTP request path.
- Proper email threading based on Message-ID / In-Reply-To / References,
  with a Subject+participants fallback.
- Attachments stored through ir.attachment with access control tied to
  the owning mailbox/business record.
- A generic "MailProvider" abstraction so other backends (plain IMAP/SMTP,
  Gmail, Microsoft) can be added later without changing the client layer.
- Designed to attach emails to any Odoo business record (Contacts, CRM,
  Sales, Helpdesk, Project, Purchase, ...) through simple relations,
  never hard-coded per-module logic.

    """,
    "author": "Aypa Tech",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "security/security.xml",
        "views/mail_server_views.xml",
        "views/mail_account_views.xml",
        "views/mail_folder_views.xml",
        "views/mail_label_views.xml",
        "views/mail_tag_views.xml",
        "views/mail_message_views.xml",
        "views/mail_domain_views.xml",
        "views/mail_alias_views.xml",
        "views/mail_menu.xml",
        "data/cron.xml",
        'security/ir.access.csv',
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
