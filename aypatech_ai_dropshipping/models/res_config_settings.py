from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ai_dropshipping_ai_enabled = fields.Boolean(
        string="Enable AI API",
        default=False,
        config_parameter="ai_dropshipping_assistant.ai_enabled",
    )

    ai_dropshipping_provider = fields.Selection([
        ("openai", "OpenAI / ChatGPT"),
        ("gemini", "Gemini"),
    ], string="AI Provider", default="gemini",
        config_parameter="ai_dropshipping_assistant.ai_provider")

    ai_dropshipping_openai_model = fields.Selection([
        ("gpt-4.1-mini", "GPT 4.1 Mini"),
        ("gpt-4.1", "GPT 4.1"),
        ("gpt-4o-mini", "GPT 4o Mini"),
        ("gpt-4o", "GPT 4o"),
    ], string="OpenAI Model", default="gpt-4.1-mini",
        config_parameter="ai_dropshipping_assistant.openai_model")

    ai_dropshipping_openai_api_key = fields.Char(
        string="OpenAI API Key",
        config_parameter="ai_dropshipping_assistant.openai_api_key",
    )

    ai_dropshipping_gemini_model = fields.Selection([
        ("gemini-2.5-flash", "Gemini 2.5 Flash"),
        ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite"),
        ("gemini-1.5-flash", "Gemini 1.5 Flash"),
    ], string="Gemini Model", default="gemini-2.5-flash",
        config_parameter="ai_dropshipping_assistant.gemini_model")

    ai_dropshipping_gemini_api_key = fields.Char(
        string="Gemini API Key",
        config_parameter="ai_dropshipping_assistant.gemini_api_key",
    )

    ai_dropshipping_default_markup_percent = fields.Float(
        string="Default Markup (%)",
        default=20.0,
        config_parameter="ai_dropshipping_assistant.default_markup_percent",
    )

    ai_dropshipping_publish_after_create = fields.Boolean(
        string="Publish Product After Creation",
        default=False,
        config_parameter="ai_dropshipping_assistant.publish_after_create",
    )

    ai_dropshipping_auto_confirm_ai_content = fields.Boolean(
        string="Auto Confirm AI Content",
        default=False,
        config_parameter="ai_dropshipping_assistant.auto_confirm_ai_content",
    )