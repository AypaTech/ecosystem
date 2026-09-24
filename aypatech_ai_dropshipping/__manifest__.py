{
    "name": "AI Dropshipping Assistant",
    "version": "18.0.1.0.0",
    "summary": "AI-powered dropshipping assistant for Odoo",
    "description": """
AI Dropshipping Assistant for Odoo.
Import products from supplier URLs, translate content with AI,
calculate prices, and manage dropshipping orders.
""",
    "depends": [
        "base",
        "product",
        "sale_management",
        "website",
        "website_sale",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/import_job_views.xml",
        "views/product_template_views.xml",
        "views/menu.xml",
        "views/res_config_settings_views.xml",
        "views/website_product_template.xml",
    ],
    "installable": True,
    "application": True,
    "author": "Aypa Tech",
    "website": "https://www.aypatech.com",
    "license": "LGPL-3",
}