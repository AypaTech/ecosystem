import { registry } from '@web/core/registry';
import { isHtmlEmpty } from '@web/core/utils/html';
import { usePopover } from '@web/core/popover/popover_hook';
import { standardFieldProps } from '@web/views/fields/standard_field_props';

import { Component, signal, t, useProps } from '@odoo/owl';
import { Tooltip } from '@web/core/tooltip/tooltip';

/** Field that displays an icon for textual values and reveals the text in a tooltip. */
export class TextIconField extends Component {
    static template = 'aypatech_ai_assistant.webutils_TextIconField';
    props = useProps({
        ...standardFieldProps,
        icon: t.string().optional('file-text-o'),
    });
    setup() {
        super.setup();
        this.iconRef = signal.ref();
        this.popover = usePopover(Tooltip);
    }
    get hasValue() {
        return !isHtmlEmpty(this.props.record.data[this.props.name] || '');
    }
    showTooltip() {
        this.popover.open(this.iconRef(), {
            template: 'aypatech_ai_assistant.webutils_TextValueTooltip',
            info: {
                value: this.props.record.data[this.props.name],
            },
        });
    }
}

export const textIconField = {
    component: TextIconField,
    listViewWidth: ({ hasLabel }) => (!hasLabel ? 20 : false),
    supportedOptions: [
        {
            label: 'Icon',
            name: 'icon',
            type: 'string',
        },
    ],
    supportedTypes: ['html', 'text', 'char'],
    extractProps: ({ options }) => ({
        icon: options.icon,
    }),
};

registry.category('fields').add('text_icon', textIconField);
