import { describe, expect, test } from '@odoo/hoot';
import { queryFirst } from '@odoo/hoot-dom';
import {
    defineModels,
    fields,
    models,
    mountView,
} from '@web/../tests/web_test_helpers';

import '@aypatech_ai_assistant/webutils/views/fields/json/json';

describe.current.tags('aypatech_web_utils');

class JsonModel extends models.Model {
    _name = 'aypatech_ai_assistant.webutils_json_model';
    payload = fields.Json();
    _records = [
        { id: 1, payload: { b: 2, a: [1, 2] } },
        { id: 2, payload: false },
    ];
}

defineModels([JsonModel]);

test('prettify option renders an indented pre block', async () => {
    await mountView({
        type: 'form',
        resModel: 'aypatech_ai_assistant.webutils_json_model',
        resId: 1,
        arch: `
            <form>
                <field name="payload" options="{'prettify': True}"/>
            </form>`,
    });
    const pretty = queryFirst('pre.ayp_json_pretty');
    expect(pretty).not.toBe(null);
    expect(pretty.textContent).toBe(JSON.stringify({ b: 2, a: [1, 2] }, null, 4));
    expect(pretty.textContent).toInclude('\n    "b": 2');
});

test('without the prettify option the default span is rendered', async () => {
    await mountView({
        type: 'form',
        resModel: 'aypatech_ai_assistant.webutils_json_model',
        resId: 1,
        arch: '<form><field name="payload"/></form>',
    });
    expect('pre.ayp_json_pretty').toHaveCount(0);
    expect('[name="payload"] span').toHaveCount(1);
});

test('prettify falls back to the formatter for an empty value', async () => {
    await mountView({
        type: 'form',
        resModel: 'aypatech_ai_assistant.webutils_json_model',
        resId: 2,
        arch: `
            <form>
                <field name="payload" options="{'prettify': True}"/>
            </form>`,
    });
    expect(queryFirst('pre.ayp_json_pretty').textContent).toBe('');
});
