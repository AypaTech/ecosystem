import { ThreadIcon } from "@mail/core/common/thread_icon";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(ThreadIcon.prototype, {
    get defaultChatIcon() {
        if (this.props.thread.channel_type === "telegram") {
            return { class: "fa fa-telegram o-telegram-icon", title: _t("Telegram") };
        }
        return super.defaultChatIcon;
    },
});
