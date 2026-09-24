import { t, useProps } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { exprToBoolean } from '@web/core/utils/strings';

import {
    SelectionField,
    selectionField,
    selectionFieldProps,
} from '@web/views/fields/selection/selection_field';

/** Selection field that renders each value as a configurable icon instead of text. */
export class SelectionIconsField extends SelectionField {
    static template = 'aypatech_ai_assistant.webutils_SelectionIconsField';
    props = useProps({
        ...selectionFieldProps,
        icons: t.object(),
        defaultIcon: t.string().optional(),
        noLabel: t.boolean().optional(),
    });
    valueIcon(value) {
        const icon = this.props.icons && this.props.icons[value];
        return icon || this.props.defaultIcon || '';
    }
}

export const selectionIconsField = {
    ...selectionField,
    component: SelectionIconsField,
    supportedTypes: ['selection'],
    listViewWidth: ({ hasLabel }) => (!hasLabel ? 20 : false),
    supportedOptions: [
        {
            label: 'Icons',
            name: 'icons',
            type: 'string',
        },
        {
            label: 'Default Icon',
            name: 'defaultIcon',
            type: 'string',
        },
    ],
    extractProps({ attrs, options }) {
        const props = selectionField.extractProps(...arguments);
        props.noLabel = exprToBoolean(attrs.nolabel);
        props.defaultIcon = options.defaultIcon;
        props.icons = options.icons;
        return props;
    },
};

registry.category('fields').add('selection_icons', selectionIconsField);
