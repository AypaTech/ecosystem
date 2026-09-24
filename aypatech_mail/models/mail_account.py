# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AypatechMailAccount(models.Model):
    """One real Mailcow mailbox mapped into Odoo. Owns the connection
    credentials and profile; Message/Folder model the actual mailbox data.
    A mailbox can be personal (user_id set, shared_user_ids empty) or
    shared (shared_user_ids holding the extra users who may access it).
    """
    _name = "aypatech.mail.account"
    _description = "Mail Account (Mailbox)"
    _order = "email"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)

    server_id = fields.Many2one("aypatech.mail.server", string="Server", required=True, ondelete="restrict")
    email = fields.Char(required=True)
    username = fields.Char(help="IMAP/SMTP login, defaults to the email address if left empty.")
    password = fields.Char(groups="aypatech_mail.group_mail_administrator")

    user_id = fields.Many2one("res.users", string="Owner", help="Primary owner of this mailbox.")
    shared_user_ids = fields.Many2many(
        "res.users", "aypatech_mail_account_shared_user_rel", "account_id", "user_id",
        string="Shared With",
        help="Additional users allowed to read/send from this mailbox (e.g. support@, sales@).",
    )
    is_shared = fields.Boolean(compute="_compute_is_shared", store=True)

    signature = fields.Html(string="Signature")

    folder_ids = fields.One2many("aypatech.mail.folder", "account_id", string="Folders")
    domain_id = fields.Many2one("aypatech.mail.domain", string="Domain", ondelete="set null")

    last_full_sync = fields.Datetime(readonly=True)
    sync_enabled = fields.Boolean(default=True)

    _sql_constraints = [
        ('email_server_uniq', 'UNIQUE (email, server_id)', 'This mailbox already exists on this server.'),
    ]


    @api.depends("email")
    def _compute_name(self):
        for account in self:
            account.name = account.email

    @api.depends("shared_user_ids")
    def _compute_is_shared(self):
        for account in self:
            account.is_shared = bool(account.shared_user_ids)

    @api.constrains("email")
    def _check_email(self):
        for account in self:
            if account.email and "@" not in account.email:
                raise ValidationError("آدرس ایمیل معتبر نیست: %s" % account.email)

    def _get_login(self):
        self.ensure_one()
        return self.username or self.email

    def get_allowed_user_ids(self):
        """Users who may read this mailbox / send as this mailbox's From."""
        self.ensure_one()
        return (self.user_id | self.shared_user_ids).ids

    def get_imap_service(self):
        self.ensure_one()
        from ..services.imap_service import IMAPService  # noqa: PLC0415

        server = self.server_id
        return IMAPService(
            host=server.imap_host,
            port=server.imap_port,
            use_ssl=server.imap_ssl,
            login=self._get_login(),
            password=self.sudo().password,
            timeout=server.timeout or 15,
        )

    def get_smtp_service(self):
        self.ensure_one()
        from ..services.smtp_service import SMTPService  # noqa: PLC0415

        server = self.server_id
        return SMTPService(
            host=server.smtp_host,
            port=server.smtp_port,
            use_tls=server.smtp_tls,
            use_ssl=server.smtp_ssl,
            login=self._get_login(),
            password=self.sudo().password,
            timeout=server.timeout or 15,
        )

    def action_discover_folders(self):
        """First-connection folder discovery (section 9, step 1 of the spec)."""
        Folder = self.env["aypatech.mail.folder"].sudo()
        for account in self:
            imap = account.get_imap_service()
            try:
                remote_folders = imap.list_folders()
            finally:
                imap.close()
            existing = {f.remote_name: f for f in account.folder_ids}
            for remote_name, delimiter, flags in remote_folders:
                if remote_name in existing:
                    continue
                Folder.create({
                    "account_id": account.id,
                    "remote_name": remote_name,
                    "name": remote_name,
                    "delimiter": delimiter,
                    "folder_type": Folder._guess_folder_type(remote_name, flags),
                })
        return True

    @api.model
    def _cron_sync_all_accounts(self):
        """Entry point wired to data/cron.xml. Runs entirely in the
        background worker - never triggered from an HTTP request path
        (spec section 9: "Sync نباید هنگام باز شدن Inbox توسط HTTP request
        اجرا شود").
        """
        from ..services.sync_service import sync_account  # noqa: PLC0415

        accounts = self.sudo().search([("active", "=", True), ("sync_enabled", "=", True)])
        for account in accounts:
            try:
                sync_account(self.env, account)
                self.env.cr.commit()
            except Exception:  # noqa: BLE001
                # A single broken mailbox must never stop the others, and
                # must not lose the progress already made on them.
                self.env.cr.rollback()

    def action_test_connection(self):
        self.ensure_one()
        errors = []
        try:
            imap = self.get_imap_service()
            imap.connect()
            imap.close()
        except Exception as exc:  # noqa: BLE001
            errors.append("IMAP: %s" % exc)
        try:
            smtp = self.get_smtp_service()
            smtp.connect()
            smtp.close()
        except Exception as exc:  # noqa: BLE001
            errors.append("SMTP: %s" % exc)

        ok = not errors
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "تست اتصال",
                "message": "اتصال با موفقیت برقرار شد." if ok else "؛ ".join(errors),
                "type": "success" if ok else "danger",
                "sticky": not ok,
            },
        }
