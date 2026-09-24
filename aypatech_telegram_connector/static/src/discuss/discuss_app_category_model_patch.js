import { DiscussAppCategory } from "@mail/discuss/core/public_web/discuss_app_category_model";
import { compareDatetime } from "@mail/utils/common/misc";

import { patch } from "@web/core/utils/patch";

patch(DiscussAppCategory.prototype, {
    /**
     * Most recent Telegram conversations first.
     *
     * @param {import("models").Thread} t1
     * @param {import("models").Thread} t2
     */
    sortThreads(t1, t2) {
        if (this.eq(this.app?.telegramCategory)) {
            return compareDatetime(t2.lastInterestDt, t1.lastInterestDt) || t2.id - t1.id;
        }
        return super.sortThreads(t1, t2);
    },
});
