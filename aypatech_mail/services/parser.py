# -*- coding: utf-8 -*-
"""Turn a raw RFC822 byte string into a plain dict the rest of the module
can work with, without touching the ORM - kept pure/stdlib-only so it can
be unit tested with a handful of raw messages, no IMAP server required.
"""
import email
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime, getaddresses


def parse_email(raw_bytes):
    message = email.message_from_bytes(raw_bytes)
    return {
        "message_id": _clean_id(message.get("Message-ID")),
        "in_reply_to": _clean_id(message.get("In-Reply-To")),
        "references": _clean_references(message.get("References")),
        "subject": _decode(message.get("Subject")),
        "email_from": _decode_addresses(message.get("From")),
        "email_to": _decode_addresses(message.get("To")),
        "email_cc": _decode_addresses(message.get("Cc")),
        "date": _parse_date(message.get("Date")),
        "body_html": _get_body(message, "html"),
        "body_text": _get_body(message, "plain"),
        "attachments": _get_attachments(message),
    }


def _decode(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001
        return value


def _decode_addresses(value):
    if not value:
        return ""
    addresses = getaddresses([value])
    parts = []
    for name, addr in addresses:
        name = _decode(name)
        parts.append("%s <%s>" % (name, addr) if name else addr)
    return ", ".join(parts)


def _clean_id(value):
    return value.strip() if value else False


def _clean_references(value):
    return value.strip() if value else False


def _parse_date(value):
    if not value:
        return False
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return False
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


def _get_body(message, subtype):
    if message.is_multipart():
        # Prefer a body part that is not itself an attachment.
        for part in message.walk():
            content_disposition = str(part.get("Content-Disposition") or "")
            if "attachment" in content_disposition.lower():
                continue
            if part.get_content_type() == "text/%s" % subtype:
                return _decode_payload(part)
        return False
    if message.get_content_type() == "text/%s" % subtype:
        return _decode_payload(message)
    return False


def _decode_payload(part):
    payload = part.get_payload(decode=True)
    if payload is None:
        return False
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")


def _get_attachments(message):
    attachments = []
    if not message.is_multipart():
        return attachments
    for part in message.walk():
        content_disposition = str(part.get("Content-Disposition") or "")
        filename = part.get_filename()
        is_attachment = "attachment" in content_disposition.lower() or (
            filename and part.get_content_maintype() != "multipart"
        )
        if not is_attachment or not filename:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        attachments.append({
            "filename": _decode(filename),
            "mimetype": part.get_content_type(),
            "content": payload,
            "size": len(payload),
        })
    return attachments
