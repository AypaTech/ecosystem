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
        this.actionService = useService('action');
        this.orm = useService('orm');

        this.calendarApp =
            this.appMenuService
                .getAppsMenuItems()
                .find((app) => app.href === '/odoo/calendar') || null;
        this.todoApp =
            this.appMenuService.getAppsMenuItems().find((app) => app.href === '/odoo/to-do') ||
            null;

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
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: TODO_TASK_MODEL,
            res_id: taskId,
            views: [[false, 'form']],
            view_mode: 'form',
            target: 'current',
            context: { form_view_ref: 'project_todo.project_task_view_todo_form' },
        });
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
