import { describe, expect, test } from '@odoo/hoot';

import {
    defineModels,
    fields,
    models,
    mountView,
    onRpc,
} from '@web/../tests/web_test_helpers';

import '@aypatech_ai_assistant/webutils/views/fields/module_link/module_link';
import '@aypatech_ai_assistant/webutils/webclient/settings/form_label_addon';

describe.current.tags('aypatech_web_utils');

class ResConfigSettings extends models.Model {
    _name = 'res.config.settings';
    module_aypatech_present = fields.Boolean({ string: 'Present Module' });
    module_aypatech_missing = fields.Boolean({ string: 'Missing Module' });
    plain_setting = fields.Boolean({ string: 'Plain Setting' });
}

class IrModuleModule extends models.Model {
    _name = 'ir.module.module';
    name = fields.Char();
    _records = [{ id: 1, name: 'aypatech_present' }];
}

defineModels([ResConfigSettings, IrModuleModule]);

const SETTINGS_ARCH = `
    <form js_class="base_settings">
        <app string="AypaTech" name="aypatech">
            <setting string="Present Module">
                <field name="module_aypatech_present" widget="module_link"
                       options="{'module': 'aypatech_present'}"/>
            </setting>
            <setting string="Missing Module">
                <field name="module_aypatech_missing" widget="module_link"
                       options="{'module': 'aypatech_missing'}"/>
            </setting>
            <setting string="Plain Setting">
                <field name="plain_setting"/>
            </setting>
        </app>
    </form>`;

// ----------------------------------------------------------
// Tests

test('the add-on badge marks only the labels of unavailable modules', async () => {
    onRpc('/base_setup/demo_active', () => true);
    await mountView({
        type: 'form',
        resModel: 'res.config.settings',
        arch: SETTINGS_ARCH,
    });
    expect(
        '.o_setting_box:contains(Missing Module) .badge:contains(Add-on)',
    ).toHaveCount(1);
    expect(
        '.o_setting_box:contains(Present Module) .badge:contains(Add-on)',
    ).toHaveCount(0);
    expect(
        '.o_setting_box:contains(Plain Setting) .badge:contains(Add-on)',
    ).toHaveCount(0);
});

test('a module_link field without a module option gets no badge', async () => {
    onRpc('/base_setup/demo_active', () => true);
    await mountView({
        type: 'form',
        resModel: 'res.config.settings',
        arch: `
            <form js_class="base_settings">
                <app string="AypaTech" name="aypatech">
                    <setting string="No Option">
                        <field name="module_aypatech_missing" widget="module_link"/>
                    </setting>
                </app>
            </form>`,
    });
    expect('.o_setting_box:contains(No Option)').toHaveCount(1);
    expect('.o_setting_box .badge:contains(Add-on)').toHaveCount(0);
});
