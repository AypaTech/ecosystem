# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AypatechMailDomain(models.Model):
    """Administrative mirror of a Mailcow domain. Odoo never talks to
    Mailcow's database; this record is created/kept in sync purely through
    Mailcow API calls (see services/mailcow_client.py).
    """
    _name = "aypatech.mail.domain"
    _description = "Mail Domain (Mailcow)"
    _order = "name"

    name = fields.Char(string="Domain", required=True)
    active = fields.Boolean(default=True)
    server_id = fields.Many2one("aypatech.mail.server", required=True, ondelete="restrict")
    mailcow_id = fields.Char(string="Mailcow Domain ID", help="Identifier as reported by the Mailcow API.")

    mailbox_ids = fields.One2many("aypatech.mail.account", "domain_id", string="Mailboxes")
    alias_ids = fields.One2many("aypatech.mail.alias", "domain_id", string="Aliases")

    dns_verified = fields.Boolean(string="DNS Verified", default=False)
    dkim_verified = fields.Boolean(string="DKIM Verified", default=False)

    _name_server_uniq = models.Constraint(
        "UNIQUE (name, server_id)", "This domain is already registered on this server.",
    )

    def action_sync_from_mailcow(self):
        """Pull the current domain state from Mailcow (read-only refresh)."""
        for domain in self:
            client = domain.server_id.get_mailcow_client()
            info = client.get_domain(domain.name)
            if info:
                domain.mailcow_id = info.get("domain_name") or info.get("id") or domain.mailcow_id
        return True

    def action_create_in_mailcow(self):
        for domain in self:
            client = domain.server_id.get_mailcow_client()
            result = client.create_domain(domain.name)
            if result.get("ok"):
                domain.mailcow_id = domain.name
        return True
