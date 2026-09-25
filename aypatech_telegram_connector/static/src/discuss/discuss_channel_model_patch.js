import { DiscussChannel } from "@mail/discuss/core/common/discuss_channel_model";

import { patch } from "@web/core/utils/patch";

patch(DiscussChannel.prototype, {
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
    get allowedToLeaveChannelTypes() {
        return [...super.allowedToLeaveChannelTypes, "telegram"];
    },
    get memberListTypes() {
        return [...super.memberListTypes, "telegram"];
    },
    computeCorrespondent() {
        if (this.isTelegram && this.telegram_partner_id) {
            const customer = this.channel_member_ids.find(
                (member) => member.partner_id?.id === this.telegram_partner_id
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
