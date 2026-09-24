# -*- coding: utf-8 -*-
"""Thin HTTP client around the Telegram Bot API (SPEC §7).

The token only ever appears in the request URL. Every error string produced
here goes through ``mask_secrets`` so it can be logged or stored safely.
"""
import json
import logging
import re

import requests

from . import exceptions as exc
from .utils import mask_secrets, truncate

_logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.telegram.org"
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 30
ALLOWED_UPDATES = ["message", "edited_message", "my_chat_member"]
# file_path values returned by getFile look like "photos/file_12.jpg".
_FILE_PATH_RE = re.compile(r"^[A-Za-z0-9_\-./]+$")


class TelegramAPI:
    """Bot API client. Build it with ``TelegramAPI.for_bot(bot)`` or ``TelegramAPI(token)``."""

    def __init__(self, token, base_url=None, session=None):
        if not token:
            raise exc.TelegramAuthError("No bot token configured.")
        self._token = token.strip()
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._session = session or requests

    @classmethod
    def for_bot(cls, bot):
        bot = bot.sudo()
        base_url = bot.env["ir.config_parameter"].sudo().get_param("telegram.api_base_url")
        return cls(bot.token, base_url=base_url)

    # ------------------------------------------------------------------
    # Low level
    # ------------------------------------------------------------------

    def _mask(self, text):
        return mask_secrets(text, self._token)

    def _call(self, method, params=None, files=None, read_timeout=READ_TIMEOUT):
        url = f"{self._base_url}/bot{self._token}/{method}"
        params = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            if files:
                # multipart: nested structures must be JSON encoded
                data = {
                    k: json.dumps(v) if isinstance(v, (dict, list)) else v
                    for k, v in params.items()
                }
                response = self._session.post(
                    url, data=data, files=files, timeout=(CONNECT_TIMEOUT, read_timeout)
                )
            else:
                response = self._session.post(
                    url, json=params, timeout=(CONNECT_TIMEOUT, read_timeout)
                )
        except requests.Timeout as e:
            raise exc.TelegramTransientError(self._mask(f"Timeout calling {method}: {e}")) from None
        except requests.RequestException as e:
            raise exc.TelegramTransientError(
                self._mask(f"Connection error calling {method}: {e}")
            ) from None
        return self._parse_response(method, response)

    def _parse_response(self, method, response):
        status = response.status_code
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict) and payload.get("ok"):
            return payload.get("result")

        description = ""
        error_code = status
        retry_after = None
        if isinstance(payload, dict):
            description = payload.get("description") or ""
            error_code = payload.get("error_code") or status
            retry_after = (payload.get("parameters") or {}).get("retry_after")
        else:
            description = truncate(getattr(response, "text", "") or "", 200)
        description = self._mask(truncate(f"{method}: {description}", 500))
        raise self._classify(error_code, description, retry_after)

    @staticmethod
    def _classify(error_code, description, retry_after=None):
        lower = (description or "").lower()
        kwargs = {"status_code": error_code, "error_code": error_code}
        if error_code == 401 or "unauthorized" in lower:
            return exc.TelegramAuthError(description, **kwargs)
        if error_code == 404:
            # Telegram answers 404 "Not Found" for a malformed/revoked token.
            return exc.TelegramAuthError(description, **kwargs)
        if error_code == 403:
            return exc.TelegramBlockedError(description, **kwargs)
        if error_code == 409:
            return exc.TelegramConflict(description, **kwargs)
        if error_code == 429:
            return exc.TelegramRateLimit(description, retry_after=int(retry_after or 5), **kwargs)
        if error_code == 400:
            if "chat not found" in lower or "user not found" in lower:
                return exc.TelegramNotFound(description, **kwargs)
            if "too big" in lower or "too large" in lower:
                return exc.TelegramAttachmentError(description, **kwargs)
            return exc.TelegramBadRequest(description, **kwargs)
        if isinstance(error_code, int) and error_code >= 500:
            return exc.TelegramTransientError(description, **kwargs)
        return exc.TelegramBadRequest(description, **kwargs)

    # ------------------------------------------------------------------
    # Bot / webhook
    # ------------------------------------------------------------------

    def get_me(self):
        return self._call("getMe")

    def set_webhook(self, url, secret_token, allowed_updates=None, drop_pending_updates=False):
        return self._call("setWebhook", {
            "url": url,
            "secret_token": secret_token,
            "allowed_updates": allowed_updates,
            "drop_pending_updates": drop_pending_updates,
        })

    def delete_webhook(self, drop_pending_updates=False):
        return self._call("deleteWebhook", {"drop_pending_updates": drop_pending_updates})

    def get_webhook_info(self):
        return self._call("getWebhookInfo")

    def get_updates(self, offset=None, limit=100, timeout=0, allowed_updates=None):
        return self._call(
            "getUpdates",
            {"offset": offset, "limit": limit, "timeout": timeout, "allowed_updates": allowed_updates},
            read_timeout=READ_TIMEOUT + timeout,
        )

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def send_message(self, chat_id, text, parse_mode="HTML", reply_to_message_id=None,
                     disable_web_page_preview=None):
        params = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_to_message_id:
            params["reply_parameters"] = {
                "message_id": int(reply_to_message_id),
                "allow_sending_without_reply": True,
            }
        if disable_web_page_preview:
            params["link_preview_options"] = {"is_disabled": True}
        return self._call("sendMessage", params)

    def _send_file(self, method, field, chat_id, file_tuple, caption=None, parse_mode="HTML"):
        """``file_tuple`` = (filename, bytes, mimetype)."""
        params = {"chat_id": chat_id, "caption": caption or None}
        if caption:
            params["parse_mode"] = parse_mode
        return self._call(method, params, files={field: file_tuple}, read_timeout=READ_TIMEOUT * 4)

    def send_photo(self, chat_id, file_tuple, caption=None, parse_mode="HTML"):
        return self._send_file("sendPhoto", "photo", chat_id, file_tuple, caption, parse_mode)

    def send_document(self, chat_id, file_tuple, caption=None, parse_mode="HTML"):
        return self._send_file("sendDocument", "document", chat_id, file_tuple, caption, parse_mode)

    def send_video(self, chat_id, file_tuple, caption=None, parse_mode="HTML"):
        return self._send_file("sendVideo", "video", chat_id, file_tuple, caption, parse_mode)

    def send_audio(self, chat_id, file_tuple, caption=None, parse_mode="HTML"):
        return self._send_file("sendAudio", "audio", chat_id, file_tuple, caption, parse_mode)

    def send_voice(self, chat_id, file_tuple, caption=None, parse_mode="HTML"):
        return self._send_file("sendVoice", "voice", chat_id, file_tuple, caption, parse_mode)

    def send_chat_action(self, chat_id, action="typing"):
        return self._call("sendChatAction", {"chat_id": chat_id, "action": action})

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    def get_file(self, file_id):
        return self._call("getFile", {"file_id": file_id})

    def download_file(self, file_path, max_bytes):
        """Download a file from Telegram's file endpoint for this bot only (no SSRF).

        ``file_path`` must come from ``getFile``. Raises ``TelegramAttachmentError``
        when the file is bigger than ``max_bytes``.
        """
        if not file_path or ".." in file_path or not _FILE_PATH_RE.match(file_path):
            raise exc.TelegramBadRequest("Invalid file path returned by Telegram.")
        url = f"{self._base_url}/file/bot{self._token}/{file_path}"
        try:
            response = self._session.get(url, stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT * 4))
        except requests.Timeout as e:
            raise exc.TelegramTransientError(self._mask(f"Timeout downloading file: {e}")) from None
        except requests.RequestException as e:
            raise exc.TelegramTransientError(self._mask(f"Error downloading file: {e}")) from None
        try:
            if response.status_code != 200:
                raise self._classify(response.status_code, f"download: HTTP {response.status_code}")
            length = response.headers.get("Content-Length")
            if length and length.isdigit() and int(length) > max_bytes:
                raise exc.TelegramAttachmentError("File is larger than the configured limit.")
            chunks, size = [], 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise exc.TelegramAttachmentError("File is larger than the configured limit.")
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            response.close()
