import { registry } from '@web/core/registry';
import { patch } from '@web/core/utils/patch';

import { JsonField, jsonField } from '@web/views/fields/jsonb/jsonb';

/** Pretty-print the JSON value with indentation when the ``prettify`` option is set. */
patch(JsonField.prototype, {
    get formattedValue() {
        const value = this.props.record.data[this.props.name];
        if (value && this.props.prettify) {
            return JSON.stringify(value, null, 4);
        }
        return super.formattedValue;
    },
});

patch(JsonField, {
    props: {
        ...JsonField.props,
        prettify: { type: Boolean, optional: true },
    },
    defaultProps: {
        ...JsonField.defaultProps,
        prettify: false,
    },
});

patch(jsonField, {
    extractProps: ({ options }) => ({
        prettify: !!options.prettify,
    }),
});

// Odoo 18 only registers this widget for jsonb columns, while ``fields.Json``
// asks for "json" and would otherwise render as an empty default field.
const fieldRegistry = registry.category('fields');
if (!fieldRegistry.contains('json')) {
    fieldRegistry.add('json', { ...jsonField, supportedTypes: ['json'] });
}
