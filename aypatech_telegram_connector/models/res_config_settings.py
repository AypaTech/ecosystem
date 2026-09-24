# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    telegram_closed_behavior = fields.Selection(
        [("reopen", "Reopen the conversation"), ("new_conversation", "Start a new conversation")],
        string="Message on a closed conversation",
        config_parameter="telegram.closed_behavior", default="new_conversation",
    )
    telegram_remove_previous_assignee = fields.Boolean(
        "Remove previous assignee from the chat", config_parameter="telegram.remove_previous_assignee",
    )
    telegram_payload_retention_days = fields.Integer(
        "Raw update retention (days)", config_parameter="telegram.payload_retention_days", default=7,
    )
    telegram_log_retention_days = fields.Integer(
        "Log retention (days)", config_parameter="telegram.log_retention_days", default=30,
    )
    telegram_max_attempts = fields.Integer(
        "Max delivery attempts", config_parameter="telegram.max_attempts", default=5,
    )
    telegram_auto_resolve_days = fields.Integer(
        "Auto-resolve inactive conversations after (days)",
        config_parameter="telegram.auto_resolve_days", default=0,
        help="0 disables auto-resolve.",
    )
    telegram_contact_phone_to_partner = fields.Boolean(
        "Store phone numbers shared by customers on the contact",
        config_parameter="telegram.contact_phone_to_partner",
        help="Privacy sensitive: when a customer shares their phone through Telegram, write it on their Odoo contact.",
    )
    telegram_forget_keeps_history = fields.Selection(
        [("keep", "Keep message history"), ("anonymize", "Anonymize the customer contact")],
        string="Forget identity",
        config_parameter="telegram.forget_mode", default="anonymize",
    )
