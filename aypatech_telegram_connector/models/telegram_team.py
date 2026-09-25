# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TelegramTeam(models.Model):
    _name = "telegram.team"
    _description = "Telegram Support Team"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company,
    )
    member_ids = fields.Many2many(
        "res.users", "telegram_team_res_users_rel", "team_id", "user_id",
        string="Members", domain="[('share', '=', False)]",
    )
    assignment_method = fields.Selection(
        [("manual", "Manual"), ("round_robin", "Round robin"), ("least_busy", "Least busy")],
        default="manual", required=True,
    )
    # round robin pointer (SPEC §13: "store pointer per team")
    last_assigned_user_id = fields.Many2one("res.users", readonly=True, copy=False)
    conversation_ids = fields.One2many("telegram.conversation", "team_id")
    open_conversation_count = fields.Integer(compute="_compute_open_conversation_count")

    @api.depends("conversation_ids.state")
    def _compute_open_conversation_count(self):
        data = dict(self.env["telegram.conversation"]._read_group(
            [("team_id", "in", self.ids), ("state", "in", self.env["telegram.conversation"]._open_states())],
            ["team_id"], ["__count"],
        ))
        for team in self:
            team.open_conversation_count = data.get(team, 0)
