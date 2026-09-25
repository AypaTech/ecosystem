# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

OPEN_STATES = ["new", "open", "pending_customer", "pending_internal"]

# Allowed manual/automatic transitions (SPEC §6 / §21 "resolve, reopen").
TRANSITIONS = {
    "new": {"open", "pending_customer", "pending_internal", "resolved", "closed"},
    "open": {"pending_customer", "pending_internal", "resolved", "closed"},
    "pending_customer": {"open", "pending_internal", "resolved", "closed"},
    "pending_internal": {"open", "pending_customer", "resolved", "closed"},
    "resolved": {"open", "closed"},
    "closed": {"open"},
}


class TelegramConversation(models.Model):
    _name = "telegram.conversation"
    _description = "Telegram Conversation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, last_customer_message_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True)
    bot_id = fields.Many2one("telegram.bot", required=True, index=True, ondelete="restrict", check_company=True)
    # not required: "Forget identity" (SPEC §15) removes the chat mapping but keeps the conversation
    chat_id = fields.Many2one("telegram.chat", index=True, ondelete="set null")
    contact_id = fields.Many2one("telegram.contact", index=True, ondelete="set null")
    partner_id = fields.Many2one("res.partner", string="Customer", index=True, tracking=True)
    channel_id = fields.Many2one("discuss.channel", string="Discuss Channel", index=True, ondelete="set null", copy=False)
    team_id = fields.Many2one("telegram.team", index=True, tracking=True, check_company=True)
    user_id = fields.Many2one(
        "res.users", string="Assignee", index=True, tracking=True, domain="[('share', '=', False)]",
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("open", "Open"),
            ("pending_customer", "Waiting for customer"),
            ("pending_internal", "Waiting internally"),
            ("resolved", "Resolved"),
            ("closed", "Closed"),
        ],
        default="new", required=True, index=True, tracking=True, group_expand="_group_expand_states",
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Medium"), ("2", "High"), ("3", "Urgent")],
        default="0", tracking=True,
    )
    tag_ids = fields.Many2many("telegram.tag", string="Tags")
    last_customer_message_date = fields.Datetime(readonly=True, index=True)
    last_agent_message_date = fields.Datetime(readonly=True)
    message_count = fields.Integer("Telegram Messages", readonly=True, default=0)
    telegram_message_ids = fields.One2many("telegram.message", "conversation_id")
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company,
    )
    is_blocked = fields.Boolean(related="contact_id.blocked")
    failed_delivery_count = fields.Integer(compute="_compute_failed_delivery_count")

    @api.model
    def _open_states(self):
        return list(OPEN_STATES)

    @api.model
    def _group_expand_states(self, states, domain):
        return [key for key, _label in self._fields["state"].selection]

    def _compute_failed_delivery_count(self):
        data = dict(self.env["telegram.delivery"]._read_group(
            [("conversation_id", "in", self.ids), ("state", "=", "failed_permanent")],
            ["conversation_id"], ["__count"],
        ))
        for conv in self:
            conv.failed_delivery_count = data.get(conv, 0)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _set_state(self, new_state, force=False):
        for conv in self:
            if conv.state == new_state:
                continue
            if not force and new_state not in TRANSITIONS.get(conv.state, set()):
                raise UserError(self.env._(
                    "A conversation cannot go from %(old)s to %(new)s.",
                    old=dict(self._fields["state"].selection)[conv.state],
                    new=dict(self._fields["state"].selection)[new_state],
                ))
            conv.state = new_state
        return True

    def action_open(self):
        return self._set_state("open")

    def action_pending_customer(self):
        return self._set_state("pending_customer")

    def action_pending_internal(self):
        return self._set_state("pending_internal")

    def action_resolve(self):
        return self._set_state("resolved")

    def action_close(self):
        return self._set_state("closed")

    def action_reopen(self):
        return self._set_state("open")

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def action_assign_to_me(self):
        if self.env.user.share:
            raise UserError(self.env._("Only internal users can be assigned."))
        self._assign(self.env.user)
        return True

    def _assign(self, user):
        """Assign ``user``; add them to the channel (SPEC §13)."""
        remove_previous = self.env["ir.config_parameter"].sudo().get_bool(
            "telegram.remove_previous_assignee")
        for conv in self:
            previous = conv.user_id
            if previous == user:
                continue
            conv.user_id = user
            channel = conv.channel_id.sudo()
            if not channel:
                continue
            if user:
                channel._add_members(users=user, post_joined_message=False)
            if remove_previous and previous and previous != user:
                member = channel.channel_member_ids.filtered(lambda m: m.partner_id == previous.partner_id)
                member.unlink()
            if user and conv.state == "new":
                conv.state = "open"

    def write(self, vals):
        if "user_id" in vals and not self.env.context.get("telegram_skip_assign"):
            user = self.env["res.users"].browse(vals.pop("user_id"))
            res = super().write(vals) if vals else True
            self.with_context(telegram_skip_assign=True)._assign(user)
            return res
        return super().write(vals)

    @api.model
    def _cron_auto_resolve(self):
        """Resolve conversations without customer activity for N days (0 = disabled)."""
        days = self.env["ir.config_parameter"].sudo().get_int("telegram.auto_resolve_days", 0)
        if days <= 0:
            return 0
        limit = fields.Datetime.now() - timedelta(days=days)
        conversations = self.sudo().search([
            ("state", "in", ["open", "pending_customer"]),
            "|", ("last_customer_message_date", "<", limit),
            "&", ("last_customer_message_date", "=", False), ("create_date", "<", limit),
        ], limit=500)
        conversations._set_state("resolved")
        return len(conversations)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def action_open_chat(self):
        self.ensure_one()
        if not self.channel_id:
            raise UserError(self.env._("This conversation has no Discuss channel."))
        return {
            "type": "ir.actions.client",
            "tag": "mail.action_discuss",
            "context": {"active_id": self.channel_id.id},
        }

    def action_open_failed_deliveries(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("aypatech_telegram_connector.action_telegram_delivery_failed")
        action["domain"] = [("conversation_id", "=", self.id), ("state", "=", "failed_permanent")]
        return action
