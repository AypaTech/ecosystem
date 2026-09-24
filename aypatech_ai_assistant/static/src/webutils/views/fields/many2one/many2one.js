import { session } from '@web/session';
import { patch } from '@web/core/utils/patch';

import { many2OneField } from '@web/views/fields/many2one/many2one_field';

/**
 * Disable quick-create on many2one fields when the session flag is set and
 * the field does not explicitly opt out.
 *
 * The widgets built on top of it (avatar, barcode, ...) call
 * ``many2OneField.extractProps`` at runtime, so they follow along.
 */
patch(many2OneField, {
    extractProps({ options }) {
        const result = super.extractProps(...arguments);
        if (session.disable_quick_create && options.no_quick_create == null) {
            result.canQuickCreate = false;
        }
        return result;
    },
});
