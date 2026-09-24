from odoo import models, fields
from ..services.scraper_service import fetch_html
from ..services.parser_service import parse_product
from ..services.ai_service import rewrite_product_text


class ImportProductWizard(models.TransientModel):
    _name = "dropshipping.import.wizard"
    _description = "Import Product Wizard"

    url = fields.Char(required=True)

    state = fields.Selection([
        ("input", "Input"),
        ("preview", "Preview"),
        ("done", "Done"),
    ], default="input")

    title = fields.Char()
    description = fields.Text()
    price = fields.Float()
    currency = fields.Char()

    target_language = fields.Selection([
        ("Persian", "Persian"),
        ("English", "English"),
        ("Italian", "Italian"),
        ("German", "German"),
    ], default="Persian")

    ai_result = fields.Text(string="AI Result")

    def action_fetch(self):
        html = fetch_html(self.url)
        data = parse_product(html)

        self.write({
            "title": data.get("title"),
            "description": data.get("description"),
            "price": data.get("price"),
            "currency": data.get("currency"),
            "state": "preview",
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_ai_rewrite(self):
        result = rewrite_product_text(
            self.env,
            self.title or "",
            self.description or "",
            self.target_language,
        )

        self.ai_result = result

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm(self):
        product = self.env["product.template"].create({
            "name": self.title or "Imported Product",
            "list_price": self.price or 0.0,
            "description_sale": self.ai_result or self.description or "",
        })

        self.state = "done"

        return {
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "res_id": product.id,
            "view_mode": "form",
            "target": "current",
        }