# -*- coding: utf-8 -*-
import re

from odoo import modules

# Bot tokens look like "123456789:AAH...". Match them anywhere in a string,
# including inside https://api.telegram.org/bot<token>/method URLs.
_TOKEN_RE = re.compile(r"\d{5,}:[A-Za-z0-9_-]{20,}")


def mask_token(token):
    """Return a display-safe version of a bot token: ``123456:ABC…xyz``."""
    if not token:
        return ""
    if ":" not in token or len(token) < 12:
        return "…"
    bot_id, secret = token.split(":", 1)
    return f"{bot_id}:{secret[:3]}…{secret[-3:]}"


def mask_secrets(text, *secrets):
    """Remove bot tokens and the given secrets from ``text``."""
    if not text:
        return text or ""
    text = str(text)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return _TOKEN_RE.sub(lambda m: mask_token(m.group(0)), text)


def truncate(text, limit=500):
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def is_testing():
    return bool(modules.module.current_test)


def maybe_commit(env):
    """Commit the current transaction unless running tests (core ``mail.mail`` does the same)."""
    if not is_testing():
        env.cr.commit()
