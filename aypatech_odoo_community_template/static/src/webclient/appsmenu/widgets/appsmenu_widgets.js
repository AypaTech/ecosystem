import { Component, onWillStart, signal } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';
import { user } from '@web/core/user';

const TICKETS_MODEL = 'aypatech.helpdesk.ticket';
const TICKETS_ACTION_XMLID = 'aypatech_helpdesk.ticket_action';

/** Dashboard-style widget row shown above the apps grid in the full-screen apps menu. */
export class AppsMenuWidgets extends Component {
    static template = 'aypatech_odoo_community_template.AppsMenuWidgets';
    static props = {};

    setup() {
        this.store = useService('mail.store');
        this.appMenuService = useService('app_menu');
        this.actionService = useService('action');
        this.orm = useService('orm');

        this.calendarApp =
            this.appMenuService
                .getAppsMenuItems()
                .find((app) => app.href === '/odoo/calendar') || null;

        this.today = new Date();

        // null = probing, false = unavailable (hide the card), number = my open count
        this.ticketsCount = signal(null);
        onWillStart(() => this._probeTickets());
    }

    async _probeTickets() {
        try {
            const count = await this.orm.searchCount(TICKETS_MODEL, [
                ['user_id', '=', user.userId],
                ['closed', '=', false],
            ]);
            this.ticketsCount.set(count);
        } catch {
            this.ticketsCount.set(false);
        }
    }

    get activitiesDueCount() {
        return this.store.activityGroups.reduce(
            (total, group) => total + group.today_count + group.overdue_count,
            0,
        );
    }

    get weekdayLabel() {
        return this.today.toLocaleDateString(undefined, { weekday: 'short' });
    }

    get dayNumber() {
        return this.today.getDate();
    }

    get monthLabel() {
        return this.today.toLocaleDateString(undefined, { month: 'short' });
    }

    onClickDate() {
        if (this.calendarApp) {
            this.appMenuService.selectApp(this.calendarApp);
        }
    }

    onClickActivities() {
        this.actionService.doAction('mail.mail_activity_action_my');
    }

    onClickMessages() {
        this.actionService.doAction('mail.action_discuss');
    }

    async onClickTickets() {
        const action = await this.actionService.loadAction(TICKETS_ACTION_XMLID);
        action.domain = [
            ['user_id', '=', user.userId],
            ['closed', '=', false],
        ];
        this.actionService.doAction(action);
    }
}
