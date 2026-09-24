# -*- coding: utf-8 -*-
"""Attachment storage (spec section 13): always through ir.attachment,
never a large blob kept on the message's own JSON/text field. Mailcow's
Rspamd/ClamAV layer is responsible for scanning mail content in transit;
this service only enforces a basic size policy on our side and leaves
final access control to ir.attachment's own rules (scoped to the
aypatech.mail.message record it is attached to).
"""
import logging

_logger = logging.getLogger(__name__)

# Reasonable default; exposed as a constant so it is easy to turn into a
# System Parameter later without touching call sites.
MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25 MB


def store_attachments(env, message, parsed_attachments):
    """Create ir.attachment records for every attachment parsed off one
    raw email and link them to `message` (an aypatech.mail.message record).
    Oversized attachments are skipped (policy: reject), not silently
    truncated, and the skip is logged for the admin to notice.
    """
    Attachment = env["ir.attachment"].sudo()
    created = Attachment.browse()
    for item in parsed_attachments:
        size = item.get("size") or len(item.get("content") or b"")
        if size > MAX_ATTACHMENT_SIZE:
            _logger.warning(
                "Skipping oversized attachment '%s' (%s bytes) on message %s",
                item.get("filename"), size, message.id,
            )
            continue
        attachment = Attachment.create({
            "name": item.get("filename") or "attachment",
            "raw": item.get("content") or b"",
            "mimetype": item.get("mimetype") or "application/octet-stream",
            "res_model": "aypatech.mail.message",
            "res_id": message.id,
        })
        created |= attachment
    if created:
        message.write({"attachment_ids": [(4, att.id) for att in created]})
    return created
