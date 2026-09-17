import { patch } from '@web/core/utils/patch';
import { browser } from '@web/core/browser/browser';

import { Chatter } from '@mail/chatter/web_portal/chatter';
import { RecipientsList } from '@aypatech_odoo_community_template/core/recipients_list/recipients_list';

/** Restore the notification-message toggle from local storage and persist it. */
patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        const showNotificationMessages = browser.localStorage.getItem(
            'aypatech_odoo_community_template.notifications',
        );
        this.state.showNotificationMessages =
            showNotificationMessages != null
                ? JSON.parse(showNotificationMessages)
                : true;
        this.state.notifyInternalFollowers = false;
    },
    onClickNotificationsToggle() {
        const showNotificationMessages = !this.state.showNotificationMessages;
        browser.localStorage.setItem(
            'aypatech_odoo_community_template.notifications',
            showNotificationMessages,
        );
        this.state.showNotificationMessages = showNotificationMessages;
    },
});

Object.assign(Chatter.components, {
    RecipientsList,
});
