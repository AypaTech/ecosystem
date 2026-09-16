
===========================
Aypatech Helpdesk
===========================

| Copyright 2026 - Aypa Tech - www.aypatech.com
| License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)

Aypa Tech's own helpdesk and customer-support ticketing system: tickets,
teams, pipeline stages, categories, and a full customer-facing portal for
submitting and following up on support requests.

Usage
=====
- Submit, assign, categorize and track support tickets through
  configurable pipeline stages, with a customer portal for ticket
  submission, browsing and replies.
- Every ticket tracks whether it's awaiting a customer reply or an agent
  reply, and creates a "reply needed" activity for the assigned agent.
- Urgency score (priority x days open) is recomputed daily; once it
  crosses a team's escalation threshold, the assigned agent is notified.
- Tickets left awaiting a customer reply too long are closed automatically
  (per-team setting, on the Helpdesk Team form; 10 days by default, 0 to
  disable).

Depends
=====
base, mail, portal


