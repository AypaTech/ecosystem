import { registerThreadAction } from "@mail/core/common/thread_actions";

import { _t } from "@web/core/l10n/translation";

/** Channel header → telegram.conversation form (SPEC §5). */
registerThreadAction("telegram-conversation", {
    condition: ({ owner, store, channel }) =>
        channel?.channel_type === "telegram" &&
        Boolean(channel.telegram_conversation_id) &&
        store.self_user?.share === false &&
        !owner.isDiscussSidebarChannelActions,
    icon: "send",
    name: _t("Open Telegram conversation"),
    open: ({ store, channel }) => {
        store.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "telegram.conversation",
            views: [[false, "form"]],
            res_id: channel.telegram_conversation_id,
            target: "current",
        });
    },
    sequence: 5,
    sequenceGroup: 5,
});
