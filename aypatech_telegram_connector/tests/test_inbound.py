# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import TelegramCase, load_fixture


@tagged("post_install", "-at_install", "telegram")
class TestInbound(TelegramCase):

    def test_text_creates_identity_conversation_and_channel(self):
        self.receive(self.make_update(1, "Hello <b>there</b>"))
        contact = self.env["telegram.contact"].search([("bot_id", "=", self.bot.id), ("telegram_user_id", "=", "111111")])
        self.assertEqual(len(contact), 1)
        self.assertEqual(contact.name, "Ali Rezaei")
        self.assertTrue(contact.partner_id)
        conv = self.conversation_for()
        self.assertEqual(conv.partner_id, contact.partner_id)
        self.assertEqual(conv.team_id, self.team)
        self.assertEqual(conv.user_id, self.agent, "bot default agent assigned")
        self.assertEqual(conv.message_count, 1)
        channel = conv.channel_id
        self.assertEqual(channel.channel_type, "telegram")
        self.assertEqual(channel.telegram_conversation_id, conv)
        self.assertEqual(channel.name, "Ali Rezaei · @AcmeSupportBot")
        members = channel.channel_member_ids.partner_id
        self.assertIn(contact.partner_id, members)
        self.assertIn(self.agent.partner_id, members)
        self.assertNotIn(self.env.ref("base.partner_root"), members, "OdooBot must not be a member")
        message = channel.message_ids[:1]
        self.assertEqual(message.author_id, contact.partner_id)
        self.assertEqual(message.message_type, "comment")
        self.assertIn("&lt;b&gt;", str(message.body), "customer HTML is escaped")
        tg = self.env["telegram.message"].search([("mail_message_id", "=", message.id)])
        self.assertEqual((tg.direction, tg.message_kind, tg.telegram_message_id), ("inbound", "text", "1"))
        update = self.env["telegram.update"].search([("bot_id", "=", self.bot.id), ("update_id", "=", "1")])
        self.assertEqual(update.state, "done")

    def test_customer_message_never_queued(self):
        with self.assertQueued(0):
            self.receive(self.make_update(1, "Hi"))

    def test_second_message_same_conversation_and_identity(self):
        self.receive(self.make_update(1, "Hi"))
        self.receive(self.make_update(2, "Again"))
        conv = self.conversation_for()
        self.assertEqual(len(self.env["telegram.conversation"].search([("bot_id", "=", self.bot.id)])), 1)
        self.assertEqual(conv.message_count, 2)
        self.assertEqual(len(self.env["telegram.contact"].search([("bot_id", "=", self.bot.id)])), 1)
        self.assertEqual(len(self.env["res.partner"].search([("telegram_contact_ids.bot_id", "=", self.bot.id)])), 1)

    def test_duplicate_update_processed_once(self):
        update = self.make_update(7, "Once")
        self.receive(update)
        self.assertFalse(self.env["telegram.update"].sudo()._store(self.bot, update, "webhook"))
        self.env["telegram.update"].sudo()._cron_process()
        conv = self.conversation_for()
        self.assertEqual(len(conv.channel_id.message_ids.filtered(lambda m: m.message_type == "comment")), 1)

    def test_photo_is_downloaded_with_caption(self):
        self.api.files["AgACAgQAAxkBAAIBbig"] = ("photos/file_1.jpg", b"\xff\xd8\xff jpeg")
        self.receive(self.make_update(3, None, **load_fixture("message_photo")))
        conv = self.conversation_for()
        message = conv.channel_id.message_ids[:1]
        self.assertEqual(len(message.attachment_ids), 1)
        self.assertEqual(message.attachment_ids.mimetype, "image/jpeg")
        self.assertIn("<b>My</b>", str(message.body))
        self.assertIn("&lt;order&gt;", str(message.body))
        self.assertEqual(self.api.sent("get_file")[0][1], ("AgACAgQAAxkBAAIBbig",), "biggest size downloaded")
        tg = self.env["telegram.message"].search([("mail_message_id", "=", message.id)])
        self.assertEqual(tg.message_kind, "photo")

    def test_document_is_downloaded(self):
        self.api.files["BQACAgQAAxkBAAIBdoc"] = ("documents/file_2.pdf", b"%PDF-1.4")
        self.receive(self.make_update(4, None, **load_fixture("message_document")))
        message = self.conversation_for().channel_id.message_ids[:1]
        self.assertEqual(message.attachment_ids.name, "invoice.pdf")
        self.assertEqual(bytes(message.attachment_ids.raw), b"%PDF-1.4")

    @mute_logger("odoo.addons.aypatech_telegram_connector.models.telegram_log")
    def test_too_big_media_is_not_downloaded(self):
        doc = load_fixture("message_document")
        doc["document"]["file_size"] = 30 * 1024 * 1024
        self.receive(self.make_update(5, None, **doc))
        message = self.conversation_for().channel_id.message_ids[:1]
        self.assertFalse(message.attachment_ids)
        self.assertIn("not downloaded", str(message.body))
        self.assertFalse(self.api.sent("get_file"), "size checked before calling getFile")

    def test_location_and_sticker(self):
        self.receive(self.make_update(6, None, location={"latitude": 35.7, "longitude": 51.4}))
        body = str(self.conversation_for().channel_id.message_ids[:1].body)
        self.assertIn("openstreetmap.org", body)
        self.receive(self.make_update(8, None, sticker={
            "file_id": "st", "file_unique_id": "u", "emoji": "😀", "is_animated": True, "is_video": False,
            "width": 512, "height": 512, "type": "regular"}))
        self.assertIn("[sticker]", str(self.conversation_for().channel_id.message_ids[:1].body))

    def test_group_chats_are_ignored(self):
        update = self.make_update(9, "hi group")
        update["message"]["chat"] = {"id": -100123, "type": "supergroup", "title": "G"}
        record = self.receive(update)
        self.assertEqual(record.state, "ignored")
        self.assertFalse(self.env["telegram.conversation"].search([("bot_id", "=", self.bot.id)]))

    def test_start_queues_welcome_and_privacy(self):
        self.bot.write({"welcome_message": "Welcome!", "privacy_notice": "We store your name."})
        with self.assertQueued(1):
            self.receive(self.make_update(10, "/start"))
        delivery = self.env["telegram.delivery"].search([], order="id desc", limit=1)
        body = str(delivery.message_id.mail_message_id.body)
        self.assertIn("Welcome!", body)
        self.assertIn("We store your name.", body)
        self.assertEqual(delivery.message_id.mail_message_id.author_id, self.env.ref("base.partner_root"))

    def test_edited_message_posts_note(self):
        self.receive(self.make_update(11, "Helo"))
        update = self.make_update(12, "Hello", message_id=11)
        update["edited_message"] = update.pop("message")
        self.receive(update)
        channel = self.conversation_for().channel_id
        last = channel.message_ids[:1]
        self.assertIn("edited", str(last.body))
        self.assertEqual(last.parent_id, channel.message_ids[1:2])

    def test_blocked_by_my_chat_member(self):
        self.receive(self.make_update(13, "hi"))
        self.receive(load_fixture("update_my_chat_member"))
        contact = self.env["telegram.contact"].search([("telegram_user_id", "=", "111111"), ("bot_id", "=", self.bot.id)])
        self.assertTrue(contact.blocked)
        self.receive(self.make_update(14, "I'm back"))
        self.assertFalse(contact.blocked)

    def test_shared_phone_links_unique_partner_when_enabled(self):
        existing = self.env["res.partner"].create({"name": "Ali Existing", "phone": "+98 912 345 6789"})
        self.bot.auto_link_partner = True
        self.receive(self.make_update(15, "hi"))
        auto_partner = self.conversation_for().partner_id
        self.assertNotEqual(auto_partner, existing, "never merged without an explicit phone")
        self.receive(self.make_update(16, None, contact={
            "phone_number": "989123456789", "first_name": "Ali", "user_id": 111111}))
        conv = self.conversation_for()
        self.assertEqual(conv.partner_id, existing)
        self.assertIn(existing, conv.channel_id.channel_member_ids.partner_id)
        self.assertNotIn(auto_partner, conv.channel_id.channel_member_ids.partner_id)

    def test_shared_phone_of_someone_else_is_not_linked(self):
        self.env["res.partner"].create({"name": "Other", "phone": "+98 912 000 1111"})
        self.bot.auto_link_partner = True
        self.receive(self.make_update(17, None, contact={
            "phone_number": "989120001111", "first_name": "Other", "user_id": 222222}))
        self.assertNotEqual(self.conversation_for().partner_id.name, "Other")

    def test_ambiguous_phone_is_not_linked(self):
        self.env["res.partner"].create([{"name": "A", "phone": "+98 912 777 8888"},
                                        {"name": "B", "phone": "09127778888"}])
        self.bot.auto_link_partner = True
        self.receive(self.make_update(18, None, contact={
            "phone_number": "989127778888", "first_name": "Ali", "user_id": 111111}))
        self.assertNotIn(self.conversation_for().partner_id.name, ("A", "B"))

    def test_multi_bot_isolation(self):
        other_company = self.env["res.company"].create({"name": "Other Co"})
        bot2 = self.env["telegram.bot"].create({"name": "B2", "token": "222:BBBBBBBBBBBBBBBBBBBBBBBBBB", "company_id": other_company.id})
        self.receive(self.make_update(20, "to bot 1"))
        self.receive(self.make_update(20, "to bot 2"), bot=bot2)
        conv1, conv2 = self.conversation_for(), self.conversation_for(bot=bot2)
        self.assertNotEqual(conv1, conv2)
        self.assertNotEqual(conv1.contact_id, conv2.contact_id)
        self.assertEqual(conv2.company_id, other_company)
