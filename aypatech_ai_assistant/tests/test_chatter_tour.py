from __future__ import annotations

from odoo import models
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestChatterTour(HttpCase):
    """Drive the AI Sessions chatter box on a record linked to a session."""

    # ----------------------------------------------------------
    # Helper
    # ----------------------------------------------------------

    def _make_linked_session(self) -> models.Model:
        """Create a partner and one AI session linked to it via res_model/res_id."""
        partner = self.env['res.partner'].create({'name': 'Tour Linked Partner'})
        self.env['aypatech_ai.session'].create(
            {
                'name': 'Tour Session',
                'state': 'done',
                'agent_id': self.env.ref('aypatech_ai_assistant.ai_agent_general').id,
                'res_model': 'res.partner',
                'res_id': partner.id,
            }
        )
        return partner

    # ----------------------------------------------------------
    # Tests
    # ----------------------------------------------------------

    def test_aypatech_ai_chatter_tour(self):
        partner = self._make_linked_session()
        self.start_tour(
            f'/odoo/action-base.action_partner_form/{partner.id}',
            'aypatech_ai_chatter_tour',
            login='admin',
        )
