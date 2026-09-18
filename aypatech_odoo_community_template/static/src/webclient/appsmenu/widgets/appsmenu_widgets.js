import { Component, onWillStart, signal } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';
import { user } from '@web/core/user';

const TICKETS_MODEL = 'aypatech.helpdesk.ticket';
const TICKETS_ACTION_XMLID = 'aypatech_helpdesk.ticket_action';
const TODO_TASK_MODEL = 'project.task';
const TODO_STAGE_MODEL = 'project.task.type';
// Personal to-do stages are created per-user with a fixed sequence (see
// ProjectTask._get_default_personal_stage_create_vals): 1 Inbox, 2 Today,
// 3 This Week, 4 This Month, 5 Later, 6 Done, 7 Cancelled. The name is
// translated, so match on this stable sequence instead.
const TODO_TODAY_STAGE_SEQUENCE = 2;
const TODO_TASK_DOMAIN_BASE = [
    ['project_id', '=', false],
    ['parent_id', '=', false],
    ['is_template', '=', false],
];

/** Dashboard-style widget row shown above the apps grid in the full-screen apps menu. */
export class AppsMenuWidgets extends Component {
    static template = 'aypatech_odoo_community_template.AppsMenuWidgets';
    static props = {};

    setup() {
        this.store = useService('mail.store');
        this.appMenuService = useService('app_menu');
        this.menuService = useService('menu');
        this.actionService = useService('action');
        this.orm = useService('orm');

        const apps = this.appMenuService.getAppsMenuItems();
        this.calendarApp = apps.find((app) => app.href === '/odoo/calendar') || null;
        this.todoApp = apps.find((app) => app.href === '/odoo/to-do') || null;
        // Helpdesk's own menu carries no clean actionPath (its href is a
        // numeric "/odoo/action-<id>", which isn't stable across databases),
        // so match on the app label instead - "Helpdesk" is the name this
        // module's own module renamed it to.
        this.helpdeskApp = apps.find((app) => app.label === 'Helpdesk') || null;
        this.discussApp = apps.find((app) => app.href === '/odoo/discuss') || null;

        this.today = new Date();

        // null = probing, false = unavailable (hide the card), number = my open count
        this.ticketsCount = signal(null);
        onWillStart(() => this._probeTickets());

        // [] while probing or when there is nothing due today
        this.todosToday = signal([]);
        onWillStart(() => this._probeTodosToday());
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

    async _probeTodosToday() {
        try {
            const stages = await this.orm.searchRead(
                TODO_STAGE_MODEL,
                [
                    ['user_id', '=', user.userId],
                    ['sequence', '=', TODO_TODAY_STAGE_SEQUENCE],
                ],
                ['id'],
                { limit: 1 },
            );
            if (!stages.length) {
                this.todosToday.set([]);
                return;
            }
            const tasks = await this.orm.searchRead(
                TODO_TASK_MODEL,
                [
                    ...TODO_TASK_DOMAIN_BASE,
                    ['user_ids', 'in', [user.userId]],
                    ['personal_stage_type_id', '=', stages[0].id],
                ],
                ['id', 'name'],
                { order: 'priority desc, date_deadline asc, sequence, id desc' },
            );
            this.todosToday.set(tasks);
        } catch {
            this.todosToday.set([]);
        }
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

    onClickTodoApp() {
        if (this.todoApp) {
            this.appMenuService.selectApp(this.todoApp);
        }
    }

    onClickTodoItem(taskId) {
        this.actionService.doAction(
            {
                type: 'ir.actions.act_window',
                res_model: TODO_TASK_MODEL,
                res_id: taskId,
                views: [[false, 'form']],
                view_mode: 'form',
                target: 'main',
                context: { form_view_ref: 'project_todo.project_task_view_todo_form' },
            },
            {
                clearBreadcrumbs: true,
                // doAction() never touches the navbar's "current app" on its
                // own (that's only ever set by menu.selectMenu()), so without
                // this the navbar/sidebar would keep showing whatever app was
                // last selected through an app icon instead of To-Do.
                onActionReady: () => {
                    if (this.todoApp) {
                        this.menuService.setCurrentMenu(this.todoApp);
                    }
                },
            },
        );
    }

    onClickMessages() {
        this.actionService.doAction('mail.action_discuss', {
            clearBreadcrumbs: true,
            onActionReady: () => {
                if (this.discussApp) {
                    this.menuService.setCurrentMenu(this.discussApp);
                }
            },
        });
    }

    async onClickTickets() {
        const action = await this.actionService.loadAction(TICKETS_ACTION_XMLID);
        action.domain = [
            ['user_id', '=', user.userId],
            ['closed', '=', false],
        ];
        action.target = 'main';
        // Force the list view: the kanban view groups by stage_id, which
        // requires read access to the Helpdesk Stage model that a user can
        // otherwise lack even while having access to tickets themselves.
        action.views = [[false, 'list'], ...action.views.filter(([, type]) => type !== 'list')];
        action.view_mode = 'list';
        this.actionService.doAction(action, {
            clearBreadcrumbs: true,
            onActionReady: () => {
                if (this.helpdeskApp) {
                    this.menuService.setCurrentMenu(this.helpdeskApp);
                }
            },
        });
    }
}
