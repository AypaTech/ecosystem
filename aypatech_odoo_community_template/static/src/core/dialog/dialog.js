import { session } from '@web/session';
import { patch } from '@web/core/utils/patch';

import { Dialog } from '@web/core/dialog/dialog';

/** Honor the user dialog size preference and add a fullscreen size toggle. */
patch(Dialog.prototype, {
    setup() {
        super.setup();
        if (session.dialog_size === 'maximize') {
            this.dialogSize.set('fs');
        }
    },
    onClickDialogSizeToggle() {
        this.dialogSize.set(this.size === 'fs' ? undefined : 'fs');
    },
});
