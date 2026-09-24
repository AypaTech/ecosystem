from __future__ import annotations

import json

from odoo.tests.common import new_test_user

from odoo.addons.aypatech_ai_assistant.tests.common import AITestCommon


class TestApprovalPreviewAccess(AITestCommon):
    """Verify the approval preview never leaks data the caller cannot read."""

    # ----------------------------------------------------------
    # Setup
    # ----------------------------------------------------------

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.restricted = new_test_user(
            cls.env, login='ai_appr_restricted', groups='base.group_user'
        )
        cls.secret = cls.env['ir.config_parameter'].create(
            {'key': 'aypatech_ai_assistant.ai_approval_leak_probe', 'value': 'TOP-SECRET'}
        )

    # ----------------------------------------------------------
    # Tests
    # ----------------------------------------------------------

    def test_read_current_respects_access(self):
        approval = self.env['aypatech_ai.approval'].with_user(self.restricted)
        model = self.env['ir.config_parameter'].with_user(self.restricted)
        self.assertEqual(approval._read_current(model, [self.secret.id], ['value']), {})

    def test_preview_masks_unreadable_targets_and_values(self):
        preview = (
            self.env['aypatech_ai.approval']
            .with_user(self.restricted)
            ._build_preview(
                'update_records',
                {
                    'model': 'ir.config_parameter',
                    'ids': [self.secret.id],
                    'values': {'value': 'redacted'},
                },
            )
        )
        self.assertNotIn('TOP-SECRET', json.dumps(preview))
        self.assertEqual(preview['targets'][0]['display_name'], '(no access)')
        self.assertEqual(preview['changes'][0]['from'], '')
