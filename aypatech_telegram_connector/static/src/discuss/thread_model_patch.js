import { Thread } from "@mail/core/common/thread_model";

import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    setup() {
        super.setup(...arguments);
        /** @type {number|undefined} id of the telegram.conversation (plain id, no client model) */
        this.telegram_conversation_id = undefined;
        /** @type {number|undefined} res.partner id of the Telegram customer */
        this.telegram_partner_id = undefined;
    },
    get isTelegram() {
        return this.channel_type === "telegram";
    },
    _computeDiscussAppCategory() {
        if (this.isTelegram) {
            return this.store.discuss.telegramCategory;
        }
        return super._computeDiscussAppCategory(...arguments);
    },
    get canLeave() {
        if (this.isTelegram) {
            return !this.message_needaction_counter && this.store.self?.type === "partner";
        }
        return super.canLeave;
    },
    get hasMemberList() {
        return this.isTelegram || super.hasMemberList;
    },
    computeCorrespondent() {
        if (this.isTelegram && this.telegram_partner_id) {
            const customer = this.channelMembers.find(
                (member) => member.persona?.id === this.telegram_partner_id
            );
            if (customer) {
                return customer;
            }
        }
        return super.computeCorrespondent(...arguments);
    },
    get avatarUrl() {
        if (this.isTelegram && this.correspondent) {
            return this.correspondent.avatarUrl;
        }
        return super.avatarUrl;
    },
});
