# -*- coding: utf-8 -*-
from odoo import fields, models


class AypatechMailSyncState(models.Model):
    """Per-folder sync bookmark (section 9 / 39.4). Sync must be resumable
    and incremental: we never re-fetch a folder from scratch unless the
    server reports a new UIDVALIDITY (meaning the folder was recreated and
    old UIDs are no longer meaningful).
    """
    _name = "aypatech.mail.sync.state"
    _description = "Mail Folder Sync State"

    folder_id = fields.Many2one("aypatech.mail.folder", required=True, ondelete="cascade", index=True)
    account_id = fields.Many2one(related="folder_id.account_id", store=True)

    uid_validity = fields.Char()
    last_uid = fields.Integer(default=0)
    last_sync_at = fields.Datetime()

    sync_status = fields.Selection(
        selection=[
            ("idle", "Idle"),
            ("running", "Running"),
            ("error", "Error"),
        ],
        default="idle",
    )
    retry_count = fields.Integer(default=0)
    last_error = fields.Text()

    _sql_constraints = [
        ('folder_uniq', 'UNIQUE (folder_id)', 'A folder can only have one sync state.'),
    ]


    def reset_for_resync(self, new_uid_validity):
        """UIDVALIDITY changed under us: per section 30, this must be a
        controlled reset + resync, not a silent partial sync.
        """
        self.ensure_one()
        self.write({
            "uid_validity": new_uid_validity,
            "last_uid": 0,
            "sync_status": "idle",
            "retry_count": 0,
            "last_error": False,
        })
