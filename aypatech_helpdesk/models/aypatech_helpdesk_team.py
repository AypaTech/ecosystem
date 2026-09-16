# Copyright 2026 - Aypa Tech - www.aypatech.com
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)

from odoo import api, fields, models


class AypatechHelpdeskTeam(models.Model):
    _name = 'aypatech.helpdesk.team'
    _description = "Helpdesk Team"
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    member_ids = fields.Many2many('res.users', string="Members")
    ticket_ids = fields.One2many('aypatech.helpdesk.ticket', 'team_id', string="Tickets")
    ticket_count = fields.Integer(compute='_compute_ticket_count')

    auto_close_after_days = fields.Integer(
        string="Auto-close After (days)", default=10,
        help="Tickets awaiting a customer reply for this many days are automatically closed. "
             "Set to 0 to disable.",
    )
    escalation_threshold = fields.Integer(
        string="Escalation Threshold", default=6,
        help="When a ticket's urgency score (priority weight x days open) exceeds this, "
             "its assigned agent gets a reminder to prioritize it.",
    )

    @api.depends('ticket_ids')
    def _compute_ticket_count(self):
        for team in self:
            team.ticket_count = len(team.ticket_ids)

    def action_view_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Tickets",
            'res_model': 'aypatech.helpdesk.ticket',
            'view_mode': 'list,form',
            'domain': [('team_id', '=', self.id)],
            'context': {'default_team_id': self.id},
        }
