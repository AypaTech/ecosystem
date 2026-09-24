import { fields } from "@mail/core/common/record";
import { DiscussApp } from "@mail/core/public_web/discuss_app_model";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(DiscussApp.prototype, {
    setup() {
        super.setup(...arguments);
        /** Sidebar category holding every channel_type === "telegram" thread. */
        this.telegramCategory = fields.One("DiscussAppCategory", {
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
            eager: true,
        });
    },
});
