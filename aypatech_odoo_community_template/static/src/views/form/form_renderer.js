import { proxy, useRef } from '@odoo/owl';
import { patch } from '@web/core/utils/patch';
import { browser } from '@web/core/browser/browser';

import { FormRenderer } from '@web/views/form/form_renderer';

/** Track and persist the side chatter width and wire its drag-resize handle. */
patch(FormRenderer.prototype, {
    setup() {
        super.setup();
        this.chatterState = proxy({
            width: browser.localStorage.getItem(
                'aypatech_odoo_community_template.chatter_width',
            ),
        });
        this.chatterContainer = useRef('chatterContainer');
    },
    onStartChatterResize(ev) {
        if (ev.button !== 0) {
            return;
        }
        const initialX = ev.pageX;
        const chatterElement = this.chatterContainer.el;
        const initialWidth = chatterElement.offsetWidth;
        const resizeStoppingEvents = ['keydown', 'mousedown', 'mouseup'];
        const resizePanel = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            const newWidth = Math.min(
                Math.max(50, initialWidth - (ev.pageX - initialX)),
                Math.max(chatterElement.parentElement.offsetWidth - 250, 250),
            );
            browser.localStorage.setItem(
                'aypatech_odoo_community_template.chatter_width',
                newWidth,
            );
            this.chatterState.width = newWidth;
        };
        const stopResize = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            if (ev.type === 'mousedown' && ev.button === 0) {
                return;
            }
            document.removeEventListener('mousemove', resizePanel, true);
            resizeStoppingEvents.forEach((stoppingEvent) => {
                document.removeEventListener(stoppingEvent, stopResize, true);
            });
            document.activeElement.blur();
        };
        document.addEventListener('mousemove', resizePanel, true);
        resizeStoppingEvents.forEach((stoppingEvent) => {
            document.addEventListener(stoppingEvent, stopResize, true);
        });
    },
    onDoubleClickChatterResize() {
        browser.localStorage.removeItem(
            'aypatech_odoo_community_template.chatter_width',
        );
        this.chatterState.width = false;
    },
});
