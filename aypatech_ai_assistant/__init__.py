from __future__ import annotations

from odoo.api import Environment

from . import webutils
from . import mcp
from . import ai
from . import skills
from . import chatter
from . import automation
from . import schedule


def _post_init_hook(env: Environment) -> None:
    provider_id = env.ref('aypatech_ai_assistant.ai_provider_openai').id
    agent_id = env.ref('aypatech_ai_assistant.ai_agent_general').id
    companies = env['res.company'].sudo().search([
        '|',
        ('default_ai_provider_id', '=', False),
        ('default_ai_agent_id', '=', False),
    ])
    for company in companies:
        vals = {}
        if not company.default_ai_provider_id:
            vals['default_ai_provider_id'] = provider_id
        if not company.default_ai_agent_id:
            vals['default_ai_agent_id'] = agent_id
        if vals:
            company.write(vals)

    # Every agent posts in chatter through its own partner, so make sure
    # the ones created before this hook ran have one too.
    env['aypatech_ai.agent'].with_context(active_test=False).search(
        [('partner_id', '=', False)]
    )._provision_partners()
