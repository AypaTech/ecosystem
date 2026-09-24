import { Record } from "@mail/core/common/record";
import { DiscussApp } from "@mail/core/public_web/discuss_app_model";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(DiscussApp.prototype, {
    setup(env) {
        super.setup(env);
        /** Sidebar category holding every channel_type === "telegram" thread. */
        this.telegramCategory = Record.one("DiscussAppCategory", {
            compute() {
                return {
                    extraClass: "o-telegram-DiscussSidebarCategory",
                    hideWhenEmpty: true,
                    icon: "fa fa-telegram",
                    id: "aypatech_telegram_connector.category",
                    name: _t("Telegram"),
                    sequence: 22,
                };
            },
        });
    },
});
