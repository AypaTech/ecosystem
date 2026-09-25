# -*- coding: utf-8 -*-
"""Media in/out (SPEC §7 ``TelegramMediaService``, §10, §14 SSRF)."""
import mimetypes

from . import exceptions as exc
from .telegram_api import TelegramAPI

MB = 1024 * 1024
BOT_API_DOWNLOAD_LIMIT = 20 * MB
BOT_API_UPLOAD_LIMIT = 50 * MB
BOT_API_PHOTO_LIMIT = 10 * MB

_PHOTO_MIMETYPES = {"image/jpeg", "image/png", "image/webp"}
_VIDEO_MIMETYPES = {"video/mp4"}
_AUDIO_MIMETYPES = {"audio/mpeg", "audio/mp3", "audio/mp4", "audio/x-m4a", "audio/m4a"}
_VOICE_MIMETYPES = {"audio/ogg", "audio/opus"}


class TelegramMediaService:

    def __init__(self, env, bot, api=None):
        self.env = env
        self.bot = bot.sudo()
        self._api = api

    @property
    def api(self):
        if self._api is None:
            self._api = TelegramAPI.for_bot(self.bot)
        return self._api

    # ------------------------------------------------------------------
    # Limits
    # ------------------------------------------------------------------

    def download_limit(self):
        limit = max(self.bot.max_media_size_mb, 1) * MB
        custom_server = self.env["ir.config_parameter"].sudo().get_str("telegram.api_base_url")
        return limit if custom_server else min(limit, BOT_API_DOWNLOAD_LIMIT)

    def upload_limit(self):
        custom = self.env["ir.config_parameter"].sudo().get_int("telegram.max_upload_mb", 0)
        return custom * MB if custom > 0 else BOT_API_UPLOAD_LIMIT

    # ------------------------------------------------------------------
    # Inbound
    # ------------------------------------------------------------------

    def download_to_attachment(self, file_info, channel):
        """``file_info`` = {file_id, file_size, file_name, mime_type}. Returns an ir.attachment.

        Size is checked from ``file_size`` before downloading and again while streaming.
        Only Telegram's file endpoint for this bot is contacted (``TelegramAPI.download_file``).
        """
        limit = self.download_limit()
        size = file_info.get("file_size") or 0
        if size and size > limit:
            raise exc.TelegramAttachmentError(
                self.env._("File too large (%(size).1f MB, limit %(limit)d MB).",
                           size=size / MB, limit=limit // MB))
        info = self.api.get_file(file_info["file_id"])
        if (info.get("file_size") or 0) > limit:
            raise exc.TelegramAttachmentError(
                self.env._("File too large (limit %d MB).", limit // MB))
        content = self.api.download_file(info.get("file_path"), limit)
        name = file_info.get("file_name") or self._default_name(info.get("file_path"), file_info.get("mime_type"))
        vals = {
            "name": name,
            "raw": content,
            "res_model": "discuss.channel",
            "res_id": channel.id,
        }
        if file_info.get("mime_type"):
            vals["mimetype"] = file_info["mime_type"]
        return self.env["ir.attachment"].sudo().create(vals)

    @staticmethod
    def _default_name(file_path, mimetype):
        base = (file_path or "file").rsplit("/", 1)[-1]
        if "." not in base and mimetype:
            base += mimetypes.guess_extension(mimetype) or ""
        return base

    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------

    def send_method_for(self, attachment):
        """Pick the Bot API method by mimetype. Returns (method_name, kind)."""
        mimetype = (attachment.mimetype or "").lower()
        size = attachment.file_size or 0
        if mimetype in _PHOTO_MIMETYPES and size <= BOT_API_PHOTO_LIMIT:
            return "send_photo", "photo"
        if mimetype in _VIDEO_MIMETYPES:
            return "send_video", "video"
        if mimetype in _VOICE_MIMETYPES:
            return "send_voice", "voice"
        if mimetype in _AUDIO_MIMETYPES:
            return "send_audio", "audio"
        return "send_document", "document"

    def check_outbound(self, attachments):
        """Raise ``TelegramAttachmentError`` for files Telegram will refuse (checked before queueing)."""
        limit = self.upload_limit()
        too_big = attachments.filtered(lambda a: (a.file_size or 0) > limit)
        if too_big:
            raise exc.TelegramAttachmentError(self.env._(
                "%(files)s: Telegram bots can send files up to %(limit)d MB.",
                files=", ".join(too_big.mapped("name")), limit=limit // MB,
            ))

    def send_attachment(self, chat_id, attachment, caption=None):
        method, _kind = self.send_method_for(attachment)
        attachment = attachment.sudo()
        content = bytes(attachment.raw) if attachment.raw else b""  # 20: raw is a lazy BinaryValue
        file_tuple = (attachment.name or "file", content, attachment.mimetype or "application/octet-stream")
        return getattr(self.api, method)(chat_id, file_tuple, caption=caption or None)
