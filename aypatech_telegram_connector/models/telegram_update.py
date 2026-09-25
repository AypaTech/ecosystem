# -*- coding: utf-8 -*-
import hashlib
import json
import logging

from odoo import api, fields, models

from ..services.gateway import TelegramGateway
from ..services.utils import is_testing, maybe_commit

_logger = logging.getLogger(__name__)


class TelegramUpdate(models.Model):
    """Inbox of raw updates (SPEC §4 rule 2). Unique (bot, update_id) = idempotency."""

    _name = "telegram.update"
    _description = "Telegram Update (inbox)"
    _order = "id desc"

    bot_id = fields.Many2one("telegram.bot", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="bot_id.company_id", store=True, index=True)
    update_id = fields.Char(required=True, readonly=True)
    update_type = fields.Char(readonly=True)
    received_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    processed_at = fields.Datetime(readonly=True)
    state = fields.Selection(
        [("pending", "Pending"), ("done", "Done"), ("ignored", "Ignored"), ("error", "Error")],
        default="pending", required=True, index=True,
    )
    attempts = fields.Integer(default=0, readonly=True)
    error = fields.Text(readonly=True)
    payload = fields.Text(readonly=True, help="Raw JSON; deleted by the retention job.")
    payload_hash = fields.Char(readonly=True)
    source = fields.Selection([("webhook", "Webhook"), ("polling", "Polling")], readonly=True)

    _bot_update_unique = models.Constraint(
        "UNIQUE(bot_id, update_id)", "This update was already received.",
    )
    _pending_idx = models.Index("(id) WHERE state = 'pending'")

    MAX_ATTEMPTS = 3

    @api.model
    def _store(self, bot, update, source):
        """Insert one raw update. Returns the record, or an empty recordset for a duplicate.

        The insert is done inside a savepoint with ON CONFLICT DO NOTHING so a duplicate
        never breaks the surrounding transaction (SPEC §8.5).
        """
        update_id = str(update["update_id"])
        raw = json.dumps(update, separators=(",", ":"), ensure_ascii=False)
        update_type = next((k for k in update if k != "update_id"), False)
        self.env.cr.execute(
            """
            INSERT INTO telegram_update
                (bot_id, company_id, update_id, update_type, received_at, state, attempts, payload,
                 payload_hash, source, create_uid, write_uid, create_date, write_date)
            VALUES (%s, %s, %s, %s, now() at time zone 'UTC', 'pending', 0, %s, %s, %s,
                    %s, %s, now() at time zone 'UTC', now() at time zone 'UTC')
            ON CONFLICT (bot_id, update_id) DO NOTHING
            RETURNING id
            """,
            (bot.id, bot.company_id.id, update_id, update_type, raw,
             hashlib.sha256(raw.encode()).hexdigest(), source, self.env.uid, self.env.uid),
        )
        row = self.env.cr.fetchone()
        return self.browse(row[0]) if row else self.browse()

    @api.model
    def _cron_process(self, batch_size=100):
        """Process pending updates with row locking (SKIP LOCKED), one savepoint each."""
        processed = 0
        last_id = 0  # never retry a failed update within the same run
        while True:
            # the raw select below must see states written earlier in this transaction
            self.flush_model(["state"])
            self.env.cr.execute(
                """
                SELECT id FROM telegram_update
                 WHERE state = 'pending' AND id > %s
                 ORDER BY id
                 LIMIT %s
                 FOR UPDATE SKIP LOCKED
                """,
                (last_id, batch_size),
            )
            ids = [r[0] for r in self.env.cr.fetchall()]
            if not ids:
                break
            last_id = ids[-1]
            for update in self.browse(ids):
                update._process_one()
                processed += 1
            if is_testing():
                break
            remaining = self.env["ir.cron"]._commit_progress(len(ids))
            if remaining <= 0:
                break
        return processed

    def _process_one(self):
        self.ensure_one()
        gateway = TelegramGateway(self.env, self.bot_id.sudo())
        try:
            payload = json.loads(self.payload or "{}")
            with self.env.cr.savepoint():
                result = gateway.handle(payload)
            self.write({
                "state": "ignored" if result == "ignored" else "done",
                "processed_at": fields.Datetime.now(),
                "error": False,
                "attempts": self.attempts + 1,
            })
        except Exception as e:  # noqa: BLE001 - one bad update must never block the inbox
            _logger.exception("Telegram update %s (bot %s) failed", self.update_id, self.bot_id.id)
            attempts = self.attempts + 1
            self.write({
                "state": "error" if attempts >= self.MAX_ATTEMPTS else "pending",
                "attempts": attempts,
                "error": str(e)[:1000],
                "processed_at": fields.Datetime.now(),
            })
            self.bot_id._log("error", "inbound", f"Update {self.update_id}: {e}")

    def action_reprocess(self):
        self.filtered(lambda u: u.state in ("error", "ignored")).write({"state": "pending", "attempts": 0})
        self.env.ref("aypatech_telegram_connector.ir_cron_telegram_process_updates")._trigger()
        return True

    @api.model
    def _cron_poll(self):
        """Polling mode: getUpdates for every bot configured for polling."""
        from ..services.gateway import TelegramPoller
        bots = self.env["telegram.bot"].sudo().search([
            ("connection_mode", "=", "polling"), ("active", "=", True),
            ("state", "in", ("connected", "error")), ("auth_failed", "=", False),
        ])
        stored = 0
        for bot in bots:
            stored += TelegramPoller(self.env, bot).poll()
            maybe_commit(self.env)
        if stored:
            self.env.ref("aypatech_telegram_connector.ir_cron_telegram_process_updates")._trigger()
        return stored
