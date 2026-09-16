# -*- coding: utf-8 -*-
{
    'name': "Aypatech Helpdesk",
    'summary': "Return (RMA) and helpdesk ticket management",
    'description': "Return (RMA) and helpdesk ticket management, integrated with sales orders and stock returns.",
    'author': "Aypa Tech",
    'images': ['static/description/icon.png'],
    'website': 'https://www.aypatech.com',
    'license': 'LGPL-3',
    'category': 'Inventory',
    'version': '19.0.2',
    'depends': ['base', 'sale', 'helpdesk_stock', 'huroos_shippypro_connector', 'huroos_api_session_manager'],
    # always loaded
    'data': [
        'data/etichette.xml',
        'data/mail_template.xml',
        'data/stage_id.xml',
        'views/helpdesk.xml',
        'security/ir.model.access.csv',
        'wizard/wizard_cambio.xml',
        'wizard/wizard_seleziona_etichetta_reso_view.xml'
    ],
    'installable': True,
    'auto_install': False,
}
