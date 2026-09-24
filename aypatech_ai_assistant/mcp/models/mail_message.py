from __future__ import annotations

from typing import Any

from odoo import api, fields, models


class MailMessage(models.Model):
    """Store and expose the originating MCP key name on messages."""

    _inherit = 'mail.message'

    # ----------------------------------------------------------
    # Fields
    # ----------------------------------------------------------

    mcp_name = fields.Char(
        string='MCP Key',
        readonly=True,
    )

    # ----------------------------------------------------------
    # Helper
    # ----------------------------------------------------------

    def _to_store(self, store, /, *, fields=None, **kwargs) -> None:
        """Add the MCP-origin flag to the fields sent to the web client."""
        super()._to_store(store, fields=fields, **kwargs)
        if fields is None:
            for message in self:
                store.add(message, {'mcp_name': message.mcp_name})

    # ----------------------------------------------------------
    # ORM
    # ----------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list: list[dict[str, Any]]) -> models.BaseModel:
        """Default ``mcp_name`` from the context when an MCP key is active."""
        if mcp_name := self.env.context.get('mcp_name'):
            for vals in vals_list:
                vals.setdefault('mcp_name', mcp_name)
        return super().create(vals_list)
