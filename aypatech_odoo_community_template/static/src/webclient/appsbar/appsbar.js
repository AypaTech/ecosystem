import { url } from '@web/core/utils/urls';
import { useService } from '@web/core/utils/hooks';
import { user } from '@web/core/user';
import { render } from '@web/owl2/utils';

import { Component, useListener } from '@odoo/owl';

/**
 * Sidebar listing the installed apps, with an optional company footer image,
 * kept in sync with the active app via the menu-changed bus event.
 */
export class AppsBar extends Component {
    static template = 'aypatech_odoo_community_template.AppsBar';
    setup() {
        this.appMenuService = useService('app_menu');
        if (user.activeCompany.has_appsbar_image) {
            this.sidebarImageUrl = url('/web/image', {
                model: 'res.company',
                field: 'appbar_image',
                id: user.activeCompany.id,
            });
        }
        // Owl 3 dropped Component#render(); same pattern as core NavBar.
        useListener(this.env.bus, 'MENUS:APP-CHANGED', () => render(this));
    }
    _onAppClick(app) {
        return this.appMenuService.selectApp(app);
    }
}
