# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AypatechMailFolder(models.Model):
    _name = "aypatech.mail.folder"
    _description = "IMAP Folder"
    _order = "sequence, name"

    account_id = fields.Many2one("aypatech.mail.account", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True, help="Display name shown to the user.")
    remote_name = fields.Char(required=True, help="Real IMAP mailbox path, e.g. INBOX.Sent.")
    delimiter = fields.Char(default="/", help="IMAP hierarchy delimiter reported by the server.")
    sequence = fields.Integer(default=10)

    folder_type = fields.Selection(
        selection=[
            ("inbox", "Inbox"),
            ("sent", "Sent"),
            ("drafts", "Drafts"),
            ("archive", "Archive"),
            ("spam", "Spam"),
            ("trash", "Trash"),
            ("custom", "Custom"),
        ],
        default="custom",
        required=True,
    )

    message_ids = fields.One2many("aypatech.mail.message", "folder_id", string="Messages")
    message_count = fields.Integer(compute="_compute_message_counts")
    unread_count = fields.Integer(compute="_compute_message_counts")

    sync_state_id = fields.One2many("aypatech.mail.sync.state", "folder_id", string="Sync State")

    _sql_constraints = [
        ('remote_name_account_uniq', 'UNIQUE (account_id, remote_name)', 'This folder already exists for this account.'),
    ]


    def _compute_message_counts(self):
        counts = self.env["aypatech.mail.message"]._read_group(
            [("folder_id", "in", self.ids)], ["folder_id"], ["__count"]
        )
        total_by_folder = {folder.id: count for folder, count in counts}
        unread_counts = self.env["aypatech.mail.message"]._read_group(
            [("folder_id", "in", self.ids), ("is_read", "=", False)], ["folder_id"], ["__count"]
        )
        unread_by_folder = {folder.id: count for folder, count in unread_counts}
        for folder in self:
            folder.message_count = total_by_folder.get(folder.id, 0)
            folder.unread_count = unread_by_folder.get(folder.id, 0)

    @api.model
    def _guess_folder_type(self, remote_name, flags=()):
        """Best-effort classification of a freshly-discovered IMAP folder,
        using the special-use flags Mailcow/Dovecot advertises (RFC 6154)
        first, falling back to common English names.
        """
        flags_lower = {f.lower() for f in (flags or ())}
        special_use_map = {
            "\\inbox": "inbox",
            "\\sent": "sent",
            "\\drafts": "drafts",
            "\\archive": "archive",
            "\\junk": "spam",
            "\\trash": "trash",
        }
        for flag, ftype in special_use_map.items():
            if flag in flags_lower:
                return ftype

        name_upper = (remote_name or "").upper()
        if name_upper in ("INBOX",):
            return "inbox"
        if "SENT" in name_upper:
            return "sent"
        if "DRAFT" in name_upper:
            return "drafts"
        if "ARCHIVE" in name_upper:
            return "archive"
        if "JUNK" in name_upper or "SPAM" in name_upper:
            return "spam"
        if "TRASH" in name_upper or "DELETED" in name_upper:
            return "trash"
        return "custom"

    def ensure_sync_state(self):
        self.ensure_one()
        state = self.sync_state_id
        if not state:
            state = self.env["aypatech.mail.sync.state"].create({"folder_id": self.id})
        return state
