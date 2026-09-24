import { threadActionsRegistry } from "@mail/core/common/thread_actions";

import { _t } from "@web/core/l10n/translation";

/** Channel header → telegram.conversation form (SPEC §5). */
threadActionsRegistry.add("telegram-conversation", {
    condition(component) {
        const thread = component.thread;
        return (
            thread?.channel_type === "telegram" &&
            Boolean(thread.telegram_conversation_id) &&
            thread.store.self?.type === "partner" &&
            thread.store.self.isInternalUser
        );
    },
    icon: "fa fa-fw fa-telegram",
    name: _t("Open Telegram conversation"),
    open(component) {
        const thread = component.thread;
        thread.store.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "telegram.conversation",
            views: [[false, "form"]],
            res_id: thread.telegram_conversation_id,
            target: "current",
        });
    },
    sequence: 5,
});
