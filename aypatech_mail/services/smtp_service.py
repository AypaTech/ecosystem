# -*- coding: utf-8 -*-
"""Real SMTP client wrapper (stdlib smtplib) for actually sending mail
through Mailcow's Postfix. Message-ID/In-Reply-To/References are always
set here so threading (section 12) works for messages we send ourselves.
"""
import base64
import logging
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid, formatdate, getaddresses

_logger = logging.getLogger(__name__)


class SMTPServiceError(Exception):
    pass


class SMTPService:
    def __init__(self, host, port, use_tls, use_ssl, login, password, timeout=15):
        self.host = host
        self.port = port or (465 if use_ssl else 587)
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.login_name = login
        self.password = password
        self.timeout = timeout
        self._conn = None

    def connect(self):
        if self._conn is not None:
            return self._conn
        if not self.host:
            raise SMTPServiceError("SMTP host is not configured")
        try:
            if self.use_ssl:
                conn = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout)
            else:
                conn = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                if self.use_tls:
                    conn.starttls()
            if self.login_name:
                conn.login(self.login_name, self.password or "")
        except (smtplib.SMTPException, OSError) as exc:
            raise SMTPServiceError("SMTP connection failed: %s" % exc) from exc
        self._conn = conn
        return conn

    def close(self):
        if self._conn is None:
            return
        try:
            self._conn.quit()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._conn = None

    def send(self, mime_message, from_addr):
        conn = self.connect()
        recipients = [addr for _, addr in getaddresses(
            mime_message.get_all("To", []) + mime_message.get_all("Cc", []) + mime_message.get_all("Bcc", [])
        ) if addr]
        # Bcc must never be transmitted in the actual message headers.
        if "Bcc" in mime_message:
            del mime_message["Bcc"]
        try:
            conn.send_message(mime_message, from_addr=from_addr, to_addrs=recipients)
        except smtplib.SMTPException as exc:
            raise SMTPServiceError("SMTP send failed: %s" % exc) from exc
        return True


def build_mime_message(mail_message, domain_for_msgid=None):
    """Build a stdlib EmailMessage from an aypatech.mail.message record,
    including To/CC/BCC, HTML + plain text alternative, attachments, and
    the headers threading (section 12) relies on.
    """
    msg = EmailMessage()
    msg["Subject"] = mail_message.subject or ""
    msg["From"] = mail_message.email_from or mail_message.account_id.email
    if mail_message.email_to:
        msg["To"] = mail_message.email_to
    if mail_message.email_cc:
        msg["Cc"] = mail_message.email_cc
    if mail_message.email_bcc:
        msg["Bcc"] = mail_message.email_bcc
    msg["Date"] = formatdate(localtime=True)

    domain = domain_for_msgid or (mail_message.account_id.email.split("@")[-1] if mail_message.account_id.email else None)
    msg["Message-ID"] = make_msgid(domain=domain)

    if mail_message.in_reply_to:
        msg["In-Reply-To"] = mail_message.in_reply_to
    if mail_message.references:
        msg["References"] = mail_message.references

    plain_text = mail_message.body_text or _html_to_plain_fallback(mail_message.body_html)
    msg.set_content(plain_text or "")
    if mail_message.body_html:
        msg.add_alternative(mail_message.body_html, subtype="html")

    for attachment in mail_message.attachment_ids:
        content = base64.b64decode(attachment.datas) if attachment.datas else b""
        maintype, _, subtype = (attachment.mimetype or "application/octet-stream").partition("/")
        msg.add_attachment(
            content, maintype=maintype or "application", subtype=subtype or "octet-stream",
            filename=attachment.name or "attachment",
        )

    return msg


def _html_to_plain_fallback(html):
    if not html:
        return ""
    import re  # noqa: PLC0415

    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()
