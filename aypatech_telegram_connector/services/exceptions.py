# -*- coding: utf-8 -*-
"""Typed Telegram errors (SPEC §12).

Every exception message is built from already-sanitized text: callers must
pass descriptions through ``utils.mask_secrets`` before raising.
"""

ERROR_AUTH = "auth"
ERROR_BLOCKED = "blocked"
ERROR_BAD_REQUEST = "bad_request"
ERROR_RATE_LIMIT = "rate_limit"
ERROR_TRANSIENT = "transient"
ERROR_NOT_FOUND = "not_found"
ERROR_ATTACHMENT = "attachment"
ERROR_CONFLICT = "conflict"
ERROR_INTERNAL = "internal"

ERROR_CLASSES = [
    (ERROR_AUTH, "Authentication"),
    (ERROR_BLOCKED, "Blocked by user"),
    (ERROR_BAD_REQUEST, "Bad request"),
    (ERROR_RATE_LIMIT, "Rate limit"),
    (ERROR_TRANSIENT, "Transient"),
    (ERROR_NOT_FOUND, "Chat not found"),
    (ERROR_ATTACHMENT, "Attachment"),
    (ERROR_CONFLICT, "Conflict"),
    (ERROR_INTERNAL, "Internal"),
]

# Classes for which a new attempt may succeed.
RETRYABLE_CLASSES = {ERROR_RATE_LIMIT, ERROR_TRANSIENT, ERROR_INTERNAL}


class TelegramError(Exception):
    """Base class. ``description`` is safe to show (no token)."""

    error_class = ERROR_INTERNAL

    def __init__(self, description="", *, status_code=None, error_code=None, retry_after=None):
        super().__init__(description)
        self.description = description
        self.status_code = status_code
        self.error_code = error_code
        self.retry_after = retry_after

    @property
    def retryable(self):
        return self.error_class in RETRYABLE_CLASSES

    def __str__(self):
        prefix = f"[{self.error_class}"
        if self.error_code:
            prefix += f" {self.error_code}"
        return f"{prefix}] {self.description}"


class TelegramAuthError(TelegramError):
    error_class = ERROR_AUTH


class TelegramBlockedError(TelegramError):
    error_class = ERROR_BLOCKED


class TelegramBadRequest(TelegramError):
    error_class = ERROR_BAD_REQUEST


class TelegramRateLimit(TelegramError):
    error_class = ERROR_RATE_LIMIT


class TelegramTransientError(TelegramError):
    error_class = ERROR_TRANSIENT


class TelegramNotFound(TelegramError):
    error_class = ERROR_NOT_FOUND


class TelegramAttachmentError(TelegramError):
    error_class = ERROR_ATTACHMENT


class TelegramConflict(TelegramError):
    """409: getUpdates while a webhook is set, or two pollers."""

    error_class = ERROR_CONFLICT
