import {
    MENU_TABS,
    MessagingMenu,
} from "@mail/core/public_web/messaging_menu/messaging_menu_model";
import { fields } from "@mail/model/export";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

// server side: TelegramMessagingMenuController
MENU_TABS.TELEGRAM = "telegram";

patch(MessagingMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.telegramTab = fields.One("MessagingMenuTab", {
            compute() {
                return {
                    id: MENU_TABS.TELEGRAM,
                    icon: "send",
                    activeIcon: "send",
                    iconClass: "o-telegram-icon",
                    label: _t("Telegram"),
                    sequence: 95,
                    emptyState: { title: _t("No Telegram conversation yet.") },
                    filters: [
                        {
                            id: "telegram_unread",
                            text: _t("Unread"),
                            includesChannel: (c) => c.isUnread,
                        },
                    ],
                    includesChannel: (c) =>
                        c.channel_type === "telegram" &&
                        (c.self_member_id?.is_pinned || c.isLocallyPinned),
                    recordType: "discuss.channel",
                };
            },
            eager: true,
        });
    },
});
