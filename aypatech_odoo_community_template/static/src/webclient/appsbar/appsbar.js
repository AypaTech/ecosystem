import { url } from '@web/core/utils/urls';
import { useService } from '@web/core/utils/hooks';

import { Component, onWillUnmount } from '@odoo/owl';

/**
 * Sidebar listing the installed apps, with an optional company footer image,
 * kept in sync with the active app via the menu-changed bus event.
 */
export class AppsBar extends Component {
    static template = 'aypatech_odoo_community_template.AppsBar';
    static props = {};
    setup() {
        this.appMenuService = useService('app_menu');
        const company = useService('company').currentCompany;
        if (company.has_appsbar_image) {
            this.sidebarImageUrl = url('/web/image', {
                model: 'res.company',
                field: 'appbar_image',
                id: company.id,
            });
        }
        const renderAfterMenuChange = () => {
            this.render();
        };
        this.env.bus.addEventListener('MENUS:APP-CHANGED', renderAfterMenuChange);
        onWillUnmount(() => {
            this.env.bus.removeEventListener(
                'MENUS:APP-CHANGED',
                renderAfterMenuChange,
            );
        });
    }
    _onAppClick(app) {
        return this.appMenuService.selectApp(app);
    }
}
