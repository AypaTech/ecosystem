from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPlaygroundTour(HttpCase):
    """Run the MCP playground browser tour end to end."""

    # ----------------------------------------------------------
    # Tests
    # ----------------------------------------------------------

    def test_playground_tour(self):
        self.start_tour(
            '/odoo/action-aypatech_ai_assistant.mcp_action_mcp_playground',
            'aypatech_mcp_playground_tour',
            login='admin',
        )
