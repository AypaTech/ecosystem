# -*- coding: utf-8 -*-
"""Incremental IMAP sync engine (spec section 9). This is the piece the
spec is explicit must run only as a background job (cron), never inline
on an HTTP request - see data/cron.xml and models/mail_account.py, which
only ever call this from a cron-triggered method.
"""
import logging

from odoo import fields

from . import parser as parser_module
from . import threading_service
from .attachment_service import store_attachments
from .imap_service import IMAPServiceError

_logger = logging.getLogger(__name__)

MAX_RETRY_COUNT = 5


def sync_account(env, account):
    """Sync every folder of one mailbox. Errors on one folder must not
    abort the others.
    """
    results = []
    for folder in account.folder_ids:
        try:
            results.append((folder, sync_folder(env, account, folder)))
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Sync failed for folder %s (account %s)", folder.remote_name, account.email)
            _record_folder_error(folder, str(exc))
            results.append((folder, 0))
    account.write({"last_full_sync": fields.Datetime.now()})
    return results


def sync_folder(env, account, folder):
    """Run steps 2-6 of section 9 for a single folder. Returns the number
    of new messages stored.
    """
    state = folder.ensure_sync_state()
    if state.sync_status == "running":
        # A previous run on this folder is still marked running - either a
        # concurrent worker or a crashed run; skip rather than double-sync.
        return 0

    state.write({"sync_status": "running"})
    imap = account.get_imap_service()
    stored = 0
    try:
        uidvalidity, _uidnext = imap.get_uidvalidity(folder.remote_name)
        if state.uid_validity and uidvalidity and state.uid_validity != uidvalidity:
            # Section 9 step 7 / section 30: folder was recreated server
            # side, old UIDs are meaningless now - controlled reset+resync.
            state.reset_for_resync(uidvalidity)
        elif not state.uid_validity:
            state.write({"uid_validity": uidvalidity})

        new_uids = imap.fetch_new_uids(folder.remote_name, state.last_uid or 0)
        for uid in new_uids:
            if _store_message_from_uid(env, account, folder, imap, uid):
                stored += 1
            state.write({"last_uid": uid})

        state.write({
            "sync_status": "idle",
            "retry_count": 0,
            "last_error": False,
            "last_sync_at": fields.Datetime.now(),
        })
    except IMAPServiceError as exc:
        _record_folder_error(folder, str(exc))
        raise
    finally:
        imap.close()
    return stored


def _store_message_from_uid(env, account, folder, imap, uid):
    Message = env["aypatech.mail.message"]
    existing = Message.search([("account_id", "=", account.id), ("folder_id", "=", folder.id), ("uid", "=", uid)], limit=1)
    if existing:
        return False

    raw_bytes, flags = imap.fetch_message(folder.remote_name, uid)
    parsed = parser_module.parse_email(raw_bytes)
    thread = threading_service.resolve_thread(env, account, parsed)

    message = Message.create({
        "account_id": account.id,
        "folder_id": folder.id,
        "thread_id": thread.id,
        "uid": uid,
        "message_id": parsed["message_id"],
        "in_reply_to": parsed["in_reply_to"],
        "references": parsed["references"],
        "subject": parsed["subject"],
        "email_from": parsed["email_from"],
        "email_to": parsed["email_to"],
        "email_cc": parsed["email_cc"],
        "date": parsed["date"] or False,
        "body_html": parsed["body_html"] or False,
        "body_text": parsed["body_text"] or False,
        "direction": "outgoing" if folder.folder_type == "sent" else "incoming",
        "is_read": "\\Seen" in flags,
        "send_state": "sent" if folder.folder_type == "sent" else "draft",
    })
    if parsed["attachments"]:
        store_attachments(env, message, parsed["attachments"])
    return True


def _record_folder_error(folder, error_message):
    state = folder.ensure_sync_state()
    retry_count = (state.retry_count or 0) + 1
    state.write({
        "sync_status": "error",
        "retry_count": retry_count,
        "last_error": error_message,
    })
