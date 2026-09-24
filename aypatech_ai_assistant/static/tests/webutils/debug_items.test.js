import { after, describe, expect, test } from '@odoo/hoot';
import { translatedTerms, translationLoaded } from '@web/core/l10n/translation';
import { registry } from '@web/core/registry';

import '@aypatech_ai_assistant/webutils/webclient/actions/debug_items';

describe.current.tags('aypatech_web_utils');

/** Let lazy translated terms be read as strings for the rest of the test. */
function allowTranslations() {
    translatedTerms[translationLoaded] = true;
    after(() => {
        translatedTerms[translationLoaded] = false;
    });
}

/**
 * Return the registered ``manageReports`` debug item factory.
 * @returns {Function}
 */
function getManageReports() {
    return registry.category('debug').category('action').get('manageReports');
}

test('no item is offered when the action has no model', async () => {
    expect(getManageReports()({ action: {}, env: {} })).toBe(null);
});

test('the item is placed in the ui section of the debug menu', async () => {
    allowTranslations();
    const item = getManageReports()({ action: { res_model: 'res.partner' }, env: {} });
    expect(item.type).toBe('item');
    expect(String(item.description)).toBe('Reports');
    expect(item.section).toBe('ui');
    expect(item.sequence).toBe(260);
});

test('the callback opens the reports of the current model', async () => {
    const actions = [];
    const env = {
        services: { action: { doAction: (action) => actions.push(action) } },
    };
    const item = getManageReports()({ action: { res_model: 'sale.order' }, env });
    item.callback();
    expect(actions).toHaveLength(1);
    expect(actions[0].res_model).toBe('ir.actions.report');
    expect(actions[0].type).toBe('ir.actions.act_window');
    expect(actions[0].domain).toEqual([['model', '=', 'sale.order']]);
    expect(actions[0].views).toEqual([
        [false, 'list'],
        [false, 'form'],
    ]);
});
