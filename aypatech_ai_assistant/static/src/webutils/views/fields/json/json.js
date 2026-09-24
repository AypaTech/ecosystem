import { t, useProps } from '@odoo/owl';

import { registry } from '@web/core/registry';
import { standardFieldProps } from '@web/views/fields/standard_field_props';

import { JsonField, jsonField } from '@web/views/fields/json/json_field';

/** Json field that can pretty-print its value with the ``prettify`` option. */
export class PrettyJsonField extends JsonField {
    props = useProps({
        ...standardFieldProps,
        prettify: t.boolean().optional(false),
    });

    get formattedValue() {
        const value = this.props.record.data[this.props.name];
        if (value && this.props.prettify) {
            return JSON.stringify(value, null, 4);
        }
        return super.formattedValue;
    }
}

registry.category('fields').add(
    'json',
    {
        ...jsonField,
        component: PrettyJsonField,
        extractProps: ({ options }) => ({
            prettify: !!options.prettify,
        }),
    },
    { force: true },
);
