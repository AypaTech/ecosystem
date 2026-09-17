import { patch } from '@web/core/utils/patch';

import { Thread } from '@mail/core/common/thread';

/** Optionally hide notification messages from the displayed thread. */
patch(Thread.prototype, {
    get orderedMessages() {
        const messages = super.orderedMessages;
        if (this.props.showNotificationMessages === false) {
            return messages.filter(
                (msg) =>
                    !['user_notification', 'notification'].includes(msg.message_type),
            );
        }
        return messages;
    },
});
