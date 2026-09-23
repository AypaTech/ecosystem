import { Component, t, useProps } from '@odoo/owl';

/** Popover listing the full set of thread recipients. */
export class RecipientsListPopover extends Component {
    static template = 'aypatech_odoo_community_template.RecipientsListPopover';
    props = useProps({
        recipients: t.array(),
        close: t.function(),
    });
}
