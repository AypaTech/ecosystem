import { _t } from '@web/core/l10n/translation';
import { usePopover } from '@web/core/popover/popover_hook';
import { patch } from '@web/core/utils/patch';

import { Composer } from '@mail/core/common/composer';

import { makeTextComposerAdapter } from '@aypatech_ai_assistant/chatter/composer/adapters';
import { ComposePanel } from '@aypatech_ai_assistant/chatter/composer/compose_panel';

patch(Composer.prototype, {
    setup() {
        super.setup(...arguments);
        this.aypatechAiWritePopover = usePopover(ComposePanel, {
            position: 'top-start',
            popoverClass: 'o-mail-ComposePanel-popover',
            // Clicking away leaves the panel open on purpose: a draft the
            // user is reading is thrown away by the stray click that put the
            // cursor back in the message. Escape and Discard close it.
            closeOnClickAway: false,
        });
    },
    get aypatechAiWriteTitle() {
        return _t('Write with AI');
    },
    /**
     * Staff only, and stated as such: a guest or a portal user has no business
     * with a panel that runs an agent on their behalf.
     */
    get canWriteWithAi() {
        const self = this.store.self;
        return Boolean(self && self.type === 'partner' && self.isInternalUser);
    },
    onClickWriteWithAi() {
        // Anchored on the composer root, which outlives the re-renders typing
        // causes: a popover whose anchor is replaced under it drifts off to a
        // corner of the screen.
        const anchor = this.root?.el || this.inputContainerRef?.el;
        if (!anchor) {
            return;
        }
        this.aypatechAiWritePopover.open(anchor, {
            adapter: makeTextComposerAdapter(this.props.composer, this.ref?.el),
            close: () => this.aypatechAiWritePopover.close(),
        });
    },
});
