# -*- coding: utf-8 -*-
from odoo import fields, models


class AypatechMailThread(models.Model):
    """A resolved conversation: one thread groups every reply in a chain,
    even across several Reply/Reply-All rounds, so the UI can show a single
    entry per conversation instead of one row per raw message.

    Deliberately named aypatech.mail.thread (not mail.thread) to avoid any
    collision with Odoo's own mail.thread abstract mixin.
    """
    _name = "aypatech.mail.thread"
    _description = "Email Conversation"
    _order = "last_message_date desc"

    subject = fields.Char()
    normalized_key = fields.Char(
        index=True,
        help="Fallback correlation key: normalized subject + sorted participants + time bucket, "
             "used only when no Message-ID/References chain is available.",
    )
    account_id = fields.Many2one("aypatech.mail.account", required=True, ondelete="cascade", index=True)

    message_ids = fields.One2many("aypatech.mail.message", "thread_id", string="Messages")
    message_count = fields.Integer(compute="_compute_message_stats", store=True)
    last_message_date = fields.Datetime(compute="_compute_message_stats", store=True)
    has_unread = fields.Boolean(compute="_compute_message_stats", store=True)

    # Business object links (section 37 of the spec): kept generic through
    # res_model/res_id rather than one field per Odoo module, so no
    # per-module hard-coded logic is needed here.
    linked_record_ids = fields.One2many("aypatech.mail.thread.link", "thread_id", string="Linked Records")

    def _compute_message_stats(self):
        for thread in self:
            messages = thread.message_ids
            thread.message_count = len(messages)
            thread.last_message_date = max(messages.mapped("date")) if messages else False
            thread.has_unread = bool(messages.filtered(lambda m: not m.is_read))

    def link_to_record(self, model, res_id):
        self.ensure_one()
        Link = self.env["aypatech.mail.thread.link"]
        existing = Link.search([
            ("thread_id", "=", self.id), ("res_model", "=", model), ("res_id", "=", res_id),
        ], limit=1)
        if existing:
            return existing
        return Link.create({"thread_id": self.id, "res_model": model, "res_id": res_id})


class AypatechMailThreadLink(models.Model):
    """Generic (res_model, res_id) link between a conversation and any
    Odoo business record - Contact, CRM Lead, Sales Order, Helpdesk
    Ticket, Project Task, Purchase Order, or anything else. A user can
    attach one email to several records without duplicating message data.
    """
    _name = "aypatech.mail.thread.link"
    _description = "Email Thread <-> Business Record Link"
    _order = "create_date desc"

    thread_id = fields.Many2one("aypatech.mail.thread", required=True, ondelete="cascade", index=True)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Many2oneReference(model_field="res_model", required=True, index=True)
    record_name = fields.Char(compute="_compute_record_name")

    _thread_record_uniq = models.Constraint(
        "UNIQUE (thread_id, res_model, res_id)", "This conversation is already linked to this record.",
    )

    def _compute_record_name(self):
        for link in self:
            record_name = False
            if link.res_model and link.res_id and link.res_model in self.env:
                record = self.env[link.res_model].browse(link.res_id)
                if record.exists():
                    record_name = record.display_name
            link.record_name = record_name
