import { expect, test } from '@odoo/hoot';
import { mountView } from '@web/../tests/web_test_helpers';

import { defineProductModels, listArch } from './helpers/product_model';

import '@aypatech_ai_assistant/webutils/views/fields/selection_icons/selection_icons';

defineProductModels();

test.tags('aypatech_web_utils');
test('selection icons widget displays mapped and default icons', async () => {
    await mountView({
        type: 'list',
        resModel: 'product',
        arch: listArch({
            body: `
                <field
                    name="state"
                    widget="selection_icons"
                    nolabel="1"
                    options="{'icons': {'ready': 'check'}, 'defaultIcon': 'question'}"
                />
            `,
        }),
    });
    expect('.o_list_table tbody tr:nth-child(1) span.fa-check').toHaveCount(1);
    expect('.o_list_table tbody tr:nth-child(2) span.fa-question').toHaveCount(1);
});
