import { registerThreadAction } from "@mail/core/common/thread_actions";

import { _t } from "@web/core/l10n/translation";

/** Channel header → telegram.conversation form (SPEC §5). */
registerThreadAction("telegram-conversation", {
    condition: ({ owner, store, thread }) =>
        thread?.channel_type === "telegram" &&
        Boolean(thread.telegram_conversation_id) &&
        store.self_partner?.main_user_id?.share === false &&
        !owner.isDiscussSidebarChannelActions,
    icon: "fa fa-fw fa-telegram",
    name: _t("Open Telegram conversation"),
    open: ({ store, thread }) => {
        store.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "telegram.conversation",
            views: [[false, "form"]],
            res_id: thread.telegram_conversation_id,
            target: "current",
        });
    },
    sequence: 5,
    sequenceGroup: 5,
});
