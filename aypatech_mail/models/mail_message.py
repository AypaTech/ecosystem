# -*- coding: utf-8 -*-
from email.utils import parseaddr

from odoo import api, fields, models
from odoo.exceptions import UserError


class AypatechMailMessage(models.Model):
    """Metadata + body for one synced (or locally composed) email.

    Deliberately named aypatech.mail.message (not mail.message) to avoid
    any collision with Odoo's own chatter message model - this is real
    email data, not a chatter log entry.
    """
    _name = "aypatech.mail.message"
    _description = "Email Message"
    _order = "date desc, id desc"
    _rec_name = "subject"

    account_id = fields.Many2one("aypatech.mail.account", required=True, ondelete="cascade", index=True)
    folder_id = fields.Many2one("aypatech.mail.folder", ondelete="set null", index=True)
    thread_id = fields.Many2one("aypatech.mail.thread", ondelete="set null", index=True)

    # --- IMAP identity (empty for locally-composed outgoing messages
    # until they are actually appended to the Sent folder) ---
    uid = fields.Integer(string="IMAP UID", index=True)

    # --- RFC 5322 identity, used for threading (section 12) ---
    message_id = fields.Char(string="Message-ID", index=True)
    in_reply_to = fields.Char(string="In-Reply-To")
    references = fields.Text(string="References")

    # --- Envelope ---
    subject = fields.Char()
    email_from = fields.Char(string="From")
    email_to = fields.Char(string="To")
    email_cc = fields.Char(string="Cc")
    email_bcc = fields.Char(string="Bcc")
    date = fields.Datetime(required=True, index=True, default=lambda self: fields.Datetime.now())

    # --- Body ---
    body_html = fields.Html(string="Body (HTML)", sanitize=False)
    body_text = fields.Text(string="Body (Plain Text)")

    attachment_ids = fields.Many2many(
        "ir.attachment", "aypatech_mail_message_attachment_rel", "message_id", "attachment_id",
        string="Attachments",
    )
    attachment_count = fields.Integer(compute="_compute_attachment_count")

    # --- Flags (section 9, step 6: kept in sync with IMAP flags) ---
    is_read = fields.Boolean(string="Read", default=False)
    is_starred = fields.Boolean(string="Starred", default=False)
    is_draft = fields.Boolean(string="Draft", default=False)

    direction = fields.Selection(
        selection=[("incoming", "Incoming"), ("outgoing", "Outgoing")],
        default="incoming",
        required=True,
    )

    # --- Outgoing send lifecycle (section 11): Draft -> Queued -> Sending
    # -> Sent, with a Failed -> Retry loop back to Sending. ---
    send_state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("sending", "Sending"),
            ("sent", "Sent"),
            ("failed", "Failed"),
        ],
        default="draft",
    )
    send_attempts = fields.Integer(default=0)
    last_send_error = fields.Text()

    linked_record_ids = fields.One2many(
        related="thread_id.linked_record_ids", string="Linked Records", readonly=True,
    )

    label_ids = fields.Many2many("aypatech.mail.label", string="Labels")
    tag_ids = fields.Many2many("aypatech.mail.tag", string="Tags")

    partner_id = fields.Many2one(
        "res.partner", string="Contact", compute="_compute_partner_id",
        help="Matched by looking up the other party's e-mail address against Contacts. Not stored - "
             "always resolved fresh, so it stays correct if the Contacts side changes later.",
    )

    def _compute_attachment_count(self):
        for message in self:
            message.attachment_count = len(message.attachment_ids)

    def _other_party_email(self):
        """آدرس ایمیل طرف مقابل (نه خودمان): برای پیام دریافتی یعنی فرستنده،
        برای پیام ارسالی یعنی گیرنده - همانی که باید به عنوان Contact
        شناسایی/ساخته شود."""
        self.ensure_one()
        addr = self.email_from if self.direction == "incoming" else self.email_to
        return parseaddr(addr or "")[1] or False

    @api.depends("email_from", "email_to", "direction")
    def _compute_partner_id(self):
        pairs = [(m, m._other_party_email()) for m in self]
        emails = {email.lower() for _, email in pairs if email}
        partners = self.env["res.partner"].sudo().search([("email", "in", list(emails))]) if emails else self.env["res.partner"]
        by_email = {}
        for partner in partners:
            if partner.email:
                by_email.setdefault(partner.email.strip().lower(), partner)
        for message, email in pairs:
            message.partner_id = by_email.get(email.lower()) if email else False

    def action_create_partner(self):
        """اگر طرف مقابل این پیام هنوز مخاطب شناخته‌شده‌ای نیست، یک Contact
        حداقلی (نام + ایمیل) برایش می‌سازد و فرم آن را برای تکمیل (نام کامل،
        تصویر، تلفن و...) باز می‌کند. اگر از قبل موجود بود، همان را باز می‌کند."""
        self.ensure_one()
        email = self._other_party_email()
        if not email:
            raise UserError("آدرس ایمیل معتبری برای ساخت مخاطب یافت نشد.")

        Partner = self.env["res.partner"].sudo()
        partner = Partner.search([("email", "=", email)], limit=1)
        if not partner:
            addr = self.email_from if self.direction == "incoming" else self.email_to
            display_name = parseaddr(addr or "")[0]
            partner = Partner.create({"name": display_name or email, "email": email})

        return {
            "type": "ir.actions.act_window",
            "name": "Contact",
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": partner.id,
            "target": "current",
        }

    def action_mark_unread(self):
        return self.action_mark_read(read=False)

    def action_mark_read(self, read=True):
        self.write({"is_read": read})
        for message in self:
            if message.uid and message.folder_id:
                imap = message.account_id.get_imap_service()
                try:
                    imap.set_flag(message.folder_id.remote_name, message.uid, "\\Seen", set_flag=read)
                finally:
                    imap.close()
        return True

    def action_toggle_star(self):
        for message in self:
            message.is_starred = not message.is_starred

    def _reply_references(self):
        self.ensure_one()
        existing_refs = (self.references or "").strip()
        own_id = self.message_id or ""
        if existing_refs and own_id:
            return "%s %s" % (existing_refs, own_id)
        return own_id or existing_refs

    def action_reply_all(self):
        return self.action_reply(reply_all=True)

    def action_reply(self, reply_all=False):
        """Open a new Draft pre-filled to continue this message's thread
        (spec section 12: one conversation even across several replies).
        """
        self.ensure_one()
        to_addr = self.email_from if self.direction == "incoming" else self.email_to
        cc_addr = self.email_cc if reply_all else False
        subject = self.subject or ""
        if not subject.lower().startswith("re:"):
            subject = "Re: %s" % subject

        draft = self.create({
            "account_id": self.account_id.id,
            "thread_id": self.thread_id.id,
            "folder_id": False,
            "subject": subject,
            "email_from": self.account_id.email,
            "email_to": to_addr,
            "email_cc": cc_addr,
            "in_reply_to": self.message_id,
            "references": self._reply_references(),
            "date": fields.Datetime.now(),
            "direction": "outgoing",
            "send_state": "draft",
        })
        return {
            "type": "ir.actions.act_window",
            "name": "Reply",
            "res_model": "aypatech.mail.message",
            "view_mode": "form",
            "res_id": draft.id,
            "target": "current",
        }

    def action_forward(self):
        self.ensure_one()
        subject = self.subject or ""
        if not subject.lower().startswith("fwd:"):
            subject = "Fwd: %s" % subject
        body_html = "<p>---------- Forwarded message ----------</p>%s" % (self.body_html or "")

        draft = self.create({
            "account_id": self.account_id.id,
            "thread_id": self.thread_id.id,
            "folder_id": False,
            "subject": subject,
            "email_from": self.account_id.email,
            "body_html": body_html,
            "body_text": self.body_text,
            "attachment_ids": [(6, 0, self.attachment_ids.ids)],
            "date": fields.Datetime.now(),
            "direction": "outgoing",
            "send_state": "draft",
        })
        return {
            "type": "ir.actions.act_window",
            "name": "Forward",
            "res_model": "aypatech.mail.message",
            "view_mode": "form",
            "res_id": draft.id,
            "target": "current",
        }

    def action_send(self):
        """Hand a Draft/Queued message to the SMTP service (section 11)."""
        from ..services.smtp_service import build_mime_message  # noqa: PLC0415

        for message in self.filtered(lambda m: m.send_state in ("draft", "queued", "failed")):
            message.send_state = "sending"
            account = message.account_id
            try:
                smtp = account.get_smtp_service()
                mime_message = build_mime_message(message)
                smtp.send(mime_message, from_addr=account.email)
                message.write({
                    "send_state": "sent",
                    "message_id": mime_message["Message-ID"],
                    "date": fields.Datetime.now(),
                })
            except Exception as exc:  # noqa: BLE001
                message.write({
                    "send_state": "failed",
                    "send_attempts": message.send_attempts + 1,
                    "last_send_error": str(exc),
                })
        return True
