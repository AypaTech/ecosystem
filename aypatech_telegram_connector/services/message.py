# -*- coding: utf-8 -*-
"""Inbound/outbound message bookkeeping (SPEC §7 ``TelegramMessageService``)."""
import logging

from markupsafe import Markup, escape

from odoo.exceptions import UserError

from . import exceptions as exc
from .formatter import plain_to_html, telegram_to_html
from .media import TelegramMediaService

_logger = logging.getLogger(__name__)


def parse_telegram_message(msg):
    """Normalize a Telegram ``Message`` into a channel-agnostic dict.

    Returns {kind, html (Markup), text (plain, for routing), file (dict|None), placeholder}.
    """
    text = msg.get("text") or msg.get("caption") or ""
    entities = msg.get("entities") or msg.get("caption_entities") or []
    result = {"kind": "text", "text": text, "html": telegram_to_html(text, entities), "file": None}

    if msg.get("photo"):
        photo = msg["photo"][-1]  # biggest size
        result.update(kind="photo", file={
            "file_id": photo["file_id"], "file_size": photo.get("file_size"),
            "file_name": f"photo_{photo.get('file_unique_id', 'telegram')}.jpg", "mime_type": "image/jpeg",
        })
    elif msg.get("video") or msg.get("video_note") or msg.get("animation"):
        video = msg.get("video") or msg.get("video_note") or msg.get("animation")
        result.update(kind="video", file={
            "file_id": video["file_id"], "file_size": video.get("file_size"),
            "file_name": video.get("file_name"), "mime_type": video.get("mime_type") or "video/mp4",
        })
    elif msg.get("voice"):
        voice = msg["voice"]
        result.update(kind="voice", file={
            "file_id": voice["file_id"], "file_size": voice.get("file_size"),
            "file_name": "voice.ogg", "mime_type": voice.get("mime_type") or "audio/ogg",
        })
    elif msg.get("audio"):
        audio = msg["audio"]
        result.update(kind="audio", file={
            "file_id": audio["file_id"], "file_size": audio.get("file_size"),
            "file_name": audio.get("file_name") or (audio.get("title") and f"{audio['title']}.mp3"),
            "mime_type": audio.get("mime_type") or "audio/mpeg",
        })
    elif msg.get("document"):
        doc = msg["document"]
        result.update(kind="document", file={
            "file_id": doc["file_id"], "file_size": doc.get("file_size"),
            "file_name": doc.get("file_name"), "mime_type": doc.get("mime_type"),
        })
    elif msg.get("sticker"):
        sticker = msg["sticker"]
        emoji = sticker.get("emoji") or ""
        result.update(kind="sticker", text=emoji)
        if not sticker.get("is_animated") and not sticker.get("is_video"):
            result["file"] = {
                "file_id": sticker["file_id"], "file_size": sticker.get("file_size"),
                "file_name": "sticker.webp", "mime_type": "image/webp",
            }
            result["html"] = escape(emoji)
        else:
            result["html"] = escape(f"[sticker] {emoji}".strip())
    elif msg.get("location") or msg.get("venue"):
        venue = msg.get("venue") or {}
        loc = venue.get("location") or msg.get("location") or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
        label = " — ".join(p for p in (venue.get("title"), venue.get("address")) if p)
        result.update(kind="location", text=label, html=Markup(
            '📍 %s <a href="%s" target="_blank" rel="noopener noreferrer">%s, %s</a>'
        ) % (label or "Location", url, lat, lon))
    elif msg.get("contact"):
        contact = msg["contact"]
        name = " ".join(p for p in (contact.get("first_name"), contact.get("last_name")) if p)
        result.update(kind="contact", html=Markup("👤 %s<br/>📞 %s") % (name, contact.get("phone_number") or ""))
    elif not text:
        other = next((k for k in ("poll", "dice", "game", "story", "invoice") if msg.get(k)), "message")
        result.update(kind="other", html=escape(f"[unsupported {other}]"))
    return result


class TelegramMessageService:

    def __init__(self, env):
        self.env = env

    # ------------------------------------------------------------------
    # Inbound
    # ------------------------------------------------------------------

    def create_inbound(self, conversation, msg, update_id=None, edited=False):
        """Post a customer message into the channel as the customer partner."""
        conversation = conversation.sudo()
        bot = conversation.bot_id
        channel = conversation.channel_id
        parsed = parse_telegram_message(msg)
        attachments = self.env["ir.attachment"]
        body = parsed["html"]

        if parsed["file"]:
            if bot.store_media:
                try:
                    attachments = TelegramMediaService(self.env, bot).download_to_attachment(parsed["file"], channel)
                except exc.TelegramAttachmentError as e:
                    body = body + (Markup("<br/>") if body else Markup("")) + Markup("<i>%s</i>") % (
                        self.env._("[%(kind)s not downloaded: %(reason)s]", kind=parsed["kind"], reason=e.description))
                    bot._log("warning", "media", str(e))
            else:
                body = body + (Markup("<br/>") if body else Markup("")) + Markup("<i>%s</i>") % (
                    self.env._("[%s received — media storage is disabled for this bot]", parsed["kind"]))

        if edited:
            body = Markup("<i>%s</i><br/>") % self.env._("✏️ Customer edited a message:") + body

        if not body and not attachments:
            body = Markup("<i>%s</i>") % f"[{parsed['kind']}]"

        post_kwargs = {
            "author_id": conversation.partner_id.id,
            "body": body,
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_comment",
            "attachment_ids": attachments.ids,
        }
        parent = self._find_parent(conversation, msg, edited)
        if parent:
            post_kwargs["parent_id"] = parent.id
        mail_message = channel.with_context(telegram_inbound=True).sudo().message_post(**post_kwargs)

        tg_vals = {
            "bot_id": bot.id,
            "conversation_id": conversation.id,
            "mail_message_id": mail_message.id,
            "direction": "inbound",
            "message_kind": parsed["kind"],
            "update_id": str(update_id) if update_id else False,
            "state": "received",
            "attachment_ids": [(6, 0, attachments.ids)],
        }
        if not edited:
            tg_vals["telegram_message_id"] = str(msg.get("message_id"))
        tg_message = self.env["telegram.message"].sudo().create(tg_vals)
        return tg_message, parsed

    def _find_parent(self, conversation, msg, edited):
        """Map a Telegram reply (or the edited message) to the Odoo message."""
        ref_id = msg.get("message_id") if edited else (msg.get("reply_to_message") or {}).get("message_id")
        if not ref_id:
            return self.env["mail.message"]
        ref_id = str(ref_id)
        candidates = self.env["telegram.message"].sudo().search([
            ("bot_id", "=", conversation.bot_id.id),
            ("chat_telegram_id", "=", conversation.chat_id.telegram_chat_id),
            "|", ("telegram_message_id", "=", ref_id), ("extra_telegram_message_ids", "ilike", ref_id),
        ], limit=5)
        match = candidates.filtered(lambda m: ref_id in m._get_all_telegram_ids())[:1]
        return match.mail_message_id

    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------

    def create_outbound(self, conversation, mail_message):
        """Queue a customer-visible reply. Durable records only; sending happens in the cron."""
        conversation = conversation.sudo()
        bot = conversation.bot_id
        attachments = mail_message.sudo().attachment_ids
        media = TelegramMediaService(self.env, bot)
        try:
            media.check_outbound(attachments)
        except exc.TelegramAttachmentError as e:
            # SPEC §12 "attachment": the agent is told before anything is sent (post is rolled back)
            raise UserError(e.description) from None
        kind = "text"
        if attachments:
            kind = media.send_method_for(attachments.sorted("id")[:1])[1]
        tg_message = self.env["telegram.message"].sudo().create({
            "bot_id": bot.id,
            "conversation_id": conversation.id,
            "mail_message_id": mail_message.id,
            "direction": "outbound",
            "message_kind": kind,
            "state": "queued",
            "attachment_ids": [(6, 0, attachments.ids)],
        })
        self.env["telegram.delivery"].sudo().create({"message_id": tg_message.id, "state": "queued"})
        self.env.ref("aypatech_telegram_connector.ir_cron_telegram_delivery").sudo()._trigger()
        return tg_message

    def post_bot_reply(self, conversation, text):
        """Post an automatic reply (welcome/privacy) as OdooBot and queue it for Telegram."""
        conversation = conversation.sudo()
        odoobot = self.env.ref("base.partner_root")
        mail_message = conversation.channel_id.with_context(telegram_inbound=True).sudo().message_post(
            author_id=odoobot.id,
            body=plain_to_html(text),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        return self.create_outbound(conversation, mail_message)
