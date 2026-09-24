from __future__ import annotations

import odoo.tests
from odoo.tests.common import new_test_user, tagged


@tagged('post_install', '-at_install')
class TestHoot(odoo.tests.HttpCase):
    """Drive the browser-side Hoot suite tagged aypatech_mcp."""

    # ----------------------------------------------------------
    # Setup
    # ----------------------------------------------------------

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.hoot_user = new_test_user(
            cls.env,
            login='hoot_aypatech_mcp',
            password='hoot_aypatech_mcp',
            groups='base.group_user',
            context={
                'mail_create_nosubscribe': True,
                'mail_notrack': True,
                'no_reset_password': True,
            },
        )

    # ----------------------------------------------------------
    # Tests
    # ----------------------------------------------------------

    @odoo.tests.no_retry
    def test_hoot_aypatech_mcp(self):
        self.browser_js(
            '/web/tests?headless&loglevel=2&preset=desktop&timeout=15000&tag=aypatech_mcp',
            '',
            '',
            login=self.hoot_user.login,
            timeout=1800,
            success_signal='[HOOT] Test suite succeeded',
            error_checker=lambda message: '[HOOT]' not in message,
        )
