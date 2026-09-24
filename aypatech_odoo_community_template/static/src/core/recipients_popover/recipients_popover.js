import { Component } from '@odoo/owl';

/** Popover listing the full set of thread recipients. */
export class RecipientsListPopover extends Component {
    static template = 'aypatech_odoo_community_template.RecipientsListPopover';
    static props = {
        recipients: { type: Array },
        close: { type: Function, required: true },
    };
}
