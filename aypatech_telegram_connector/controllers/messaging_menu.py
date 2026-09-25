# -*- coding: utf-8 -*-
from odoo.fields import Domain

from odoo.addons.mail.controllers.discuss.messaging_menu import DiscussMessagingMenuController


class TelegramMessagingMenuController(DiscussMessagingMenuController):
    """Discuss "Telegram" tab (see static/src/discuss/messaging_menu_model_patch.js)."""

    def _get_menu_tab_domain(self, tab_id):
        if tab_id != "telegram":
            return super()._get_menu_tab_domain(tab_id)
        return Domain([("channel_type", "=", "telegram"), ("self_member_id.is_pinned", "=", True)])

    def _get_menu_tab_filter_domain(self, tab_id, filter_id):
        if (tab_id, filter_id) == ("telegram", "telegram_unread"):
            return Domain("self_member_id.is_unread", "=", True)
        return super()._get_menu_tab_filter_domain(tab_id, filter_id)
