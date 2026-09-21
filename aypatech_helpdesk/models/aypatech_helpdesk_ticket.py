# Copyright 2026 - Aypa Tech - www.aypatech.com
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)

import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

PRIORITY_WEIGHT = {'0': 1, '1': 2, '2': 2, '3': 3}


class AypatechHelpdeskTicket(models.Model):
    _name = 'aypatech.helpdesk.ticket'
    _description = "Helpdesk Ticket"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'priority desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string="Subject", required=True, tracking=True)
    number = fields.Char(string="Ticket Number", readonly=True, copy=False, default="/")
    description = fields.Html()

    partner_id = fields.Many2one('res.partner', string="Contact", tracking=True)
    partner_name = fields.Char(string="Contact Name")
    partner_email = fields.Char(string="Contact Email")

    team_id = fields.Many2one('aypatech.helpdesk.team', string="Team", tracking=True)
    category_id = fields.Many2one('aypatech.helpdesk.category', string="Category")
    user_id = fields.Many2one('res.users', string="Assigned To", tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    stage_id = fields.Many2one(
        'aypatech.helpdesk.stage', string="Stage", tracking=True, index=True,
        group_expand='_read_group_stage_ids', default=lambda self: self._default_stage_id(),
    )
    closed = fields.Boolean(related='stage_id.closed', store=True)
    last_stage_update = fields.Datetime(default=fields.Datetime.now, readonly=True)

    priority = fields.Selection([
        ('0', "Low"),
        ('1', "Medium"),
        ('2', "High"),
        ('3', "Urgent"),
    ], default='0', tracking=True)

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    attachment_ids = fields.One2many(
        'ir.attachment', 'res_id', string="Attachments",
        domain=[('res_model', '=', 'aypatech.helpdesk.ticket')],
    )

    # ─── "Whose turn is it" tracking ───────────────────────────────
    awaiting_customer_since = fields.Datetime(
        string="Awaiting Customer Reply Since", readonly=True, copy=False,
        help="Set when an agent replies; cleared when the customer replies. "
             "The daily cron auto-closes tickets left here too long.",
    )
    awaiting_agent_since = fields.Datetime(
        string="Awaiting Our Reply Since", readonly=True, copy=False,
        help="Set when the customer replies (i.e. it's our turn); cleared when an agent replies.",
    )
    unread_by_customer = fields.Boolean(
        string="Unread Reply (Customer)", default=False, copy=False,
        help="True when an agent just replied; cleared when the customer opens or replies to the ticket.",
    )

    # ─── Urgency scoring & escalation ──────────────────────────────
    urgency_score = fields.Integer(
        string="Urgency Score", default=0, copy=False,
        help="Priority weight (Low=1, Medium/High=2, Urgent=3) times the number of days the "
             "ticket has been open. Recomputed daily by a cron.",
    )
    escalation_notified = fields.Boolean(
        string="Escalation Notified", default=False, copy=False,
        help="Set the first time the urgency score crosses the team's escalation threshold, "
             "so the reminder is only sent once.",
    )

    @api.model
    def _default_stage_id(self):
        return self.env['aypatech.helpdesk.stage'].search([], order='sequence', limit=1).id

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """Always show every active stage as a kanban column, even empty ones."""
        return stages.search([], order='sequence')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('number', '/') == '/':
                vals['number'] = self.env['ir.sequence'].next_by_code('aypatech.helpdesk.ticket') or '/'
        return super().create(vals_list)

    def _compute_access_url(self):
        super()._compute_access_url()
        for ticket in self:
            ticket.access_url = '/my/tickets/%s' % ticket.id

    # ─── "Whose turn is it" tracking + freelance-style hook ────────
    def message_post(self, **kwargs):
        """Update the "whose turn" timers whenever a comment is posted, based on whether the
        author is the ticket's own contact or an internal agent.

        Automated notes (auto-close, escalation, or anything posted by a module extending this
        one) are posted via ``.with_context(_system_note=True)`` so this logic — and
        ``_notify_partner_of_reply`` — is skipped for them, since they aren't really "a reply"
        from either side.
        """
        message = super().message_post(**kwargs)

        # NOTE: attachments are intentionally left non-public here.
        # ir.attachment._can_return_content() lets a portal user read a
        # non-public attachment via /web/content as long as they have read
        # access to the record it's linked to (see ticket_rule_portal_own_only
        # in security/ir.access.csv) — public=True is not required for that.
        # Forcing public=True instead makes ticket images show up in the
        # website builder's "Select a media" image library (its domain OR's
        # in every public attachment regardless of res_model), which is
        # exactly what we don't want.

        if self.env.context.get('_system_note'):
            return message

        author_id = message.author_id.id if message and message.author_id else False
        for ticket in self:
            if not author_id or ticket.stage_id.closed:
                continue
            is_from_customer = ticket.partner_id and author_id == ticket.partner_id.id
            author_user = self.env['res.users'].sudo().search([('partner_id', '=', author_id)], limit=1)
            is_from_agent = bool(author_user) and author_user.has_group('base.group_user') and not is_from_customer

            if is_from_customer:
                ticket.sudo().write({
                    'awaiting_customer_since': False,
                    'awaiting_agent_since': fields.Datetime.now(),
                })
                ticket.sudo()._schedule_agent_reply_activity()
            elif is_from_agent:
                ticket.sudo().write({
                    'awaiting_customer_since': fields.Datetime.now(),
                    'awaiting_agent_since': False,
                    'unread_by_customer': True,
                })
                ticket.sudo()._notify_partner_of_reply()
        return message

    def _schedule_agent_reply_activity(self):
        """Create a "reply needed" activity for the assigned agent."""
        self.ensure_one()
        if not self.user_id:
            return
        existing = self.activity_ids.filtered(
            lambda a: a.summary == 'Customer is waiting for a reply' and a.user_id == self.user_id)
        if existing:
            return
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            summary='Customer is waiting for a reply',
            note='The customer replied on this ticket — please respond.',
            user_id=self.user_id.id,
        )

    def _notify_partner_of_reply(self):
        """Hook: override to plug in a custom notification channel when an agent replies.
        No-op by default (the standard Odoo mail notification from message_post already covers
        the base case)."""
        return

    def action_close_from_portal(self, stage_id):
        """Let a portal user close their own ticket by moving it to a given closing stage."""
        self.ensure_one()
        stage = self.env['aypatech.helpdesk.stage'].browse(stage_id)
        if not stage.exists() or not stage.closed:
            raise ValidationError("Invalid closing stage.")
        self.stage_id = stage.id

    @api.model
    def _cron_auto_close_stale_tickets(self):
        """Close tickets that have been awaiting a customer reply longer than their team's
        `auto_close_after_days` (a team with it set to 0 is excluded)."""
        close_stage = self.env['aypatech.helpdesk.stage'].sudo().search(
            [('closed', '=', True)], limit=1, order='sequence desc')
        if not close_stage:
            return

        for team in self.env['aypatech.helpdesk.team'].sudo().search([('auto_close_after_days', '>', 0)]):
            deadline = fields.Datetime.now() - timedelta(days=team.auto_close_after_days)
            stale_tickets = self.sudo().search([
                ('team_id', '=', team.id),
                ('awaiting_customer_since', '!=', False),
                ('awaiting_customer_since', '<=', deadline),
                ('stage_id.closed', '=', False),
            ])
            for ticket in stale_tickets:
                ticket.with_context(_system_note=True).message_post(
                    body="This ticket was automatically closed after %d days without a "
                         "response. Reply to it or open a new one if you still need help." % team.auto_close_after_days,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
                ticket.write({
                    'stage_id': close_stage.id,
                    'awaiting_customer_since': False,
                    'awaiting_agent_since': False,
                })

    @api.model
    def _cron_update_urgency_scores(self):
        """Daily: recompute every open ticket's urgency score and escalate the ones that just
        crossed their team's threshold."""
        today = fields.Date.today()
        default_threshold = 6
        for ticket in self.sudo().search([('stage_id.closed', '=', False)]):
            create_date = ticket.create_date.date() if ticket.create_date else today
            days_open = max(1, (today - create_date).days + 1)
            weight = PRIORITY_WEIGHT.get(ticket.priority, 1)
            ticket.urgency_score = weight * days_open

            threshold = ticket.team_id.escalation_threshold if ticket.team_id else default_threshold
            if ticket.urgency_score > threshold and not ticket.escalation_notified:
                ticket._escalate()
                ticket.escalation_notified = True

    def _escalate(self):
        self.ensure_one()
        priority_label = dict(self._fields['priority'].selection).get(self.priority)
        self.with_context(_system_note=True).message_post(
            body="⚠️ Urgency score is now %d (priority: %s) — this ticket needs attention." % (
                self.urgency_score, priority_label),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        if self.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary="Escalated: urgency score above threshold",
                note="This ticket's urgency score reached %d. Please prioritize it." % self.urgency_score,
                user_id=self.user_id.id,
            )
