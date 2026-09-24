# -*- coding: utf-8 -*-
"""Conversation resolution (spec section 12).

Primary signal: Message-ID / In-Reply-To / References - these are the
only fields that reliably identify a reply chain per RFC 5322/5322bis.
Subject is explicitly NOT trusted as the primary key (mail clients localize
"Re:"/"Fwd:" prefixes inconsistently, and unrelated messages frequently
share a generic subject like "Invoice").

Fallback, used only when no header-based match exists (e.g. the first
message of a conversation, or a client that stripped References):
normalized subject + participants + a time window.
"""
import re
from datetime import timedelta

_RE_PREFIX = re.compile(r"^\s*(re|fw|fwd|رونوشت|بازارسال|پاسخ)\s*:\s*", re.IGNORECASE)
FALLBACK_TIME_WINDOW = timedelta(days=30)


def normalize_subject(subject):
    subject = subject or ""
    prev = None
    while prev != subject:
        prev = subject
        subject = _RE_PREFIX.sub("", subject).strip()
    return subject.lower()


def normalized_key(subject, participants):
    participant_key = ",".join(sorted(p.strip().lower() for p in participants if p))
    return "%s|%s" % (normalize_subject(subject), participant_key)


def resolve_thread(env, account, parsed):
    """Find or create the aypatech.mail.thread this parsed message belongs
    to. `parsed` is the dict returned by services/parser.py.
    """
    Thread = env["aypatech.mail.thread"]
    Message = env["aypatech.mail.message"]

    reference_ids = _extract_reference_ids(parsed)
    if reference_ids:
        existing = Message.search([
            ("account_id", "=", account.id),
            ("message_id", "in", reference_ids),
        ], limit=1, order="date desc")
        if existing and existing.thread_id:
            return existing.thread_id

    participants = _participants(parsed)
    key = normalized_key(parsed.get("subject"), participants)
    lower_bound = None
    if parsed.get("date"):
        lower_bound = parsed["date"] - FALLBACK_TIME_WINDOW
    domain = [("account_id", "=", account.id), ("normalized_key", "=", key)]
    candidate = Thread.search(domain, order="last_message_date desc", limit=1)
    if candidate and (not lower_bound or not candidate.last_message_date or candidate.last_message_date >= lower_bound):
        return candidate

    return Thread.create({
        "account_id": account.id,
        "subject": parsed.get("subject") or "",
        "normalized_key": key,
    })


def _extract_reference_ids(parsed):
    ids = []
    if parsed.get("in_reply_to"):
        ids.append(parsed["in_reply_to"])
    references = parsed.get("references") or ""
    ids.extend(re.findall(r"<[^<>]+>", references))
    # de-duplicate while preserving order
    seen = set()
    unique_ids = []
    for msgid in ids:
        if msgid not in seen:
            seen.add(msgid)
            unique_ids.append(msgid)
    return unique_ids


def _participants(parsed):
    raw = " ".join(filter(None, [parsed.get("email_from"), parsed.get("email_to"), parsed.get("email_cc")]))
    return re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw)
