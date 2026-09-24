import base64
import requests

from odoo import fields, models


class DropshippingImportJobImage(models.Model):
    _name = "dropshipping.import.job.image"
    _description = "Dropshipping Import Job Image"
    _order = "sequence, id"

    job_id = fields.Many2one(
        "dropshipping.import.job",
        string="Import Job",
        required=True,
        ondelete="cascade",
    )

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Name")
    image_url = fields.Char(string="Image URL")
    image = fields.Image(string="Image", max_width=1024, max_height=1024)
    is_main = fields.Boolean(string="Main Image")

    def action_set_main(self):
        for rec in self:
            rec.job_id.image_ids.write({"is_main": False})
            rec.is_main = True
            rec.job_id.image_url = rec.image_url
            rec.job_id.image_preview = rec.image