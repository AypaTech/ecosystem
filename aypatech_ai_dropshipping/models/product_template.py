from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_dropshipping_product = fields.Boolean(string="Dropshipping Product")
    dropshipping_source_url = fields.Char(string="Supplier Product URL")
    dropshipping_source_price = fields.Float(string="Supplier Price")
    dropshipping_source_currency = fields.Char(string="Supplier Currency")
    dropshipping_import_job_id = fields.Many2one(
        "dropshipping.import.job",
        string="Import Job",
        readonly=True,
    )

