# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AypatechMailServer(models.Model):
    """Connection settings for one mail backend (a Mailcow instance today,
    a generic IMAP/SMTP host or another provider tomorrow). Kept separate
    from mail.account so several mailboxes can share one server profile.
    """
    _name = "aypatech.mail.server"
    _description = "Mail Server / Backend Connection"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    provider = fields.Selection(
        selection=[
            ("mailcow", "Mailcow"),
            ("generic", "Generic IMAP/SMTP"),
        ],
        string="Provider",
        default="mailcow",
        required=True,
        help="Which MailProvider implementation handles accounts on this server.",
    )

    # --- IMAP ---
    imap_host = fields.Char(string="IMAP Host")
    imap_port = fields.Integer(string="IMAP Port", default=993)
    imap_ssl = fields.Boolean(string="IMAP over SSL", default=True)

    # --- SMTP ---
    smtp_host = fields.Char(string="SMTP Host")
    smtp_port = fields.Integer(string="SMTP Port", default=587)
    smtp_tls = fields.Boolean(string="SMTP STARTTLS", default=True)
    smtp_ssl = fields.Boolean(string="SMTP over SSL", default=False)

    # --- Mailcow administration API (management plane only) ---
    mailcow_api_url = fields.Char(
        string="Mailcow API URL",
        help="Base URL of the Mailcow instance, e.g. https://mail.example.com",
    )
    mailcow_api_key = fields.Char(string="Mailcow API Key", groups="aypatech_mail.group_mail_administrator")
    mailcow_api_key_display = fields.Char(
        string="API Key",
        compute="_compute_mailcow_api_key_display",
        help="Masked representation of the API key, safe to show in the UI.",
    )

    timeout = fields.Integer(string="Connection Timeout (s)", default=15)

    account_ids = fields.One2many("aypatech.mail.account", "server_id", string="Accounts")
    account_count = fields.Integer(compute="_compute_account_count", string="Account Count")

    @api.depends("mailcow_api_key")
    def _compute_mailcow_api_key_display(self):
        for server in self:
            key = server.sudo().mailcow_api_key
            server.mailcow_api_key_display = ("•" * 8 + key[-4:]) if key and len(key) > 4 else ("•" * 8 if key else "")

    def _compute_account_count(self):
        counts = self.env["aypatech.mail.account"]._read_group(
            [("server_id", "in", self.ids)], ["server_id"], ["__count"]
        )
        count_by_server = {server.id: count for server, count in counts}
        for server in self:
            server.account_count = count_by_server.get(server.id, 0)

    def action_view_accounts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Accounts",
            "res_model": "aypatech.mail.account",
            "view_mode": "list,form",
            "domain": [("server_id", "=", self.id)],
            "context": {"default_server_id": self.id},
        }

    def get_mailcow_client(self):
        """Return a ready-to-use MailcowClient for this server (management API only)."""
        self.ensure_one()
        from ..services.mailcow_client import MailcowClient  # noqa: PLC0415

        return MailcowClient(
            base_url=self.mailcow_api_url,
            api_key=self.sudo().mailcow_api_key,
            timeout=self.timeout or 15,
        )

    def action_health_check(self):
        self.ensure_one()
        client = self.get_mailcow_client()
        result = client.health_check()
        message = "متصل شد" if result.get("ok") else (result.get("error") or "خطای نامشخص")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "بررسی اتصال Mailcow",
                "message": message,
                "type": "success" if result.get("ok") else "danger",
                "sticky": False,
            },
        }
