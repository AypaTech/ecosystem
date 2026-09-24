# -*- coding: utf-8 -*-
from odoo import fields, models


class AypatechMailAlias(models.Model):
    """Administrative mirror of a Mailcow alias (e.g. info@ -> a mailbox
    or a distribution list). Same rule as domains: managed only through
    the Mailcow API, never a direct DB write.
    """
    _name = "aypatech.mail.alias"
    _description = "Mail Alias (Mailcow)"
    _order = "alias"

    alias = fields.Char(required=True, help="The alias address, e.g. info@example.com")
    target = fields.Char(required=True, help="Destination address(es), comma-separated for multiple.")
    domain_id = fields.Many2one("aypatech.mail.domain", required=True, ondelete="cascade")
    active = fields.Boolean(default=True)
    mailcow_id = fields.Char(string="Mailcow Alias ID")

    def action_create_in_mailcow(self):
        for alias in self:
            client = alias.domain_id.server_id.get_mailcow_client()
            result = client.create_alias(alias.alias, alias.target)
            if result.get("ok"):
                alias.mailcow_id = alias.alias
        return True

    def action_delete_from_mailcow(self):
        for alias in self:
            client = alias.domain_id.server_id.get_mailcow_client()
            client.delete_alias(alias.alias)
        return True
