# -*- coding: utf-8 -*-
{
    'name': "Aypatech Helpdesk",
    'summary': "Aypa Tech's Helpdesk & customer support ticketing system",
    'description': """
Aypatech Helpdesk
==================
Aypa Tech's own helpdesk and customer-support ticketing system: tickets,
teams, pipeline stages, categories, and a customer portal, built entirely
in-house with no dependency on any third-party helpdesk module:

- Ticket management: create, assign, categorize and track support tickets
  through configurable pipeline stages, with a full customer-facing portal
  (ticket submission, ticket list, replies, closing) out of the box.
- "Whose turn is it" tracking: every ticket knows whether it's awaiting a
  customer reply or an agent reply, with a "reply needed" activity created
  for the assigned agent automatically.
- Urgency scoring (priority x days open) recomputed daily, with automatic
  escalation once a per-team threshold is crossed.
- Automatic closing of tickets left waiting on the customer for too long
  (configurable per team, 10 days by default).
    """,
    'author': "Aypa Tech",
    'images': ['static/description/icon.png'],
    'website': 'https://www.aypatech.com',
    'license': 'LGPL-3',
    'category': 'After-Sales',
    'version': '18.0.1.0.0',
    'depends': ['base', 'mail', 'portal'],
    'data': [
        'security/aypatech_helpdesk_security.xml',
        'security/ir.model.access.csv',
        'data/aypatech_helpdesk_data.xml',
        'data/ir_cron.xml',
        'views/aypatech_helpdesk_ticket_views.xml',
        'views/aypatech_helpdesk_team_views.xml',
        'views/aypatech_helpdesk_stage_category_views.xml',
        'views/aypatech_helpdesk_menus.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
