import { Message } from "@mail/core/common/message_model";

import { patch } from "@web/core/utils/patch";

patch(Message.prototype, {
    setup() {
        super.setup(...arguments);
        /** @type {"queued"|"sending"|"sent"|"failed"|undefined} set for outbound Telegram replies */
        this.telegram_delivery_state = undefined;
        /** @type {string|false|undefined} */
        this.telegram_delivery_error = undefined;
    },
});
