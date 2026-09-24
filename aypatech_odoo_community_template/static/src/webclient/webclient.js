import { patch } from '@web/core/utils/patch';

import { WebClient } from '@web/webclient/webclient';
import { AppsBar } from '@aypatech_odoo_community_template/webclient/appsbar/appsbar';

/** Register the AppsBar so the web client renders the sidebar. */
patch(WebClient, {
    components: {
        ...WebClient.components,
        AppsBar,
    },
});
