# AypaTech AI Assistant

Agentic AI assistant for Odoo. Chat with agents from the backend, let them
work on your records through tools, mention them in chatter, run them from
automation rules or on a schedule, and expose Odoo to external AI clients
through the built-in MCP server.

- **Author:** AypaTech – https://aypatech.com
- **License:** Odoo Proprietary License v1.0 (OPL-1), see `LICENSE`
- **Odoo:** 20.0 (Community and Enterprise)

## Layout

The module is split into feature packages. Each one has its own models,
views and data, and they are all loaded from the root `__init__.py` and
`__manifest__.py`.

| Package      | What it does                                                        |
|--------------|---------------------------------------------------------------------|
| `webutils`   | Small web client helpers and widgets shared by the other packages   |
| `mcp`        | MCP server (`/mcp`), API keys, tool registry, logs and playground   |
| `ai`         | Providers, models, agents, spaces, sessions and the chat client     |
| `skills`     | Reusable skills that users or agents can switch into                |
| `chatter`    | @mentions, the AI composer and session boxes in chatter             |
| `automation` | Run agents from server actions and automation rules                 |
| `schedule`   | Recurring agent runs, pause and resume                              |

Frontend code lives under `static/src/<package>` and the Python tests for
all packages are in `tests/`.

## Requirements

Everything comes with Odoo except `croniter`, which the scheduler uses to
parse cron expressions:

```bash
pip install croniter
```

## Setup

1. Install the module.
2. Go to *AypaTech AI > Configuration > Providers*, set the API key of the
   provider you want to use and pick its default model.
3. Open the chat from the systray.

To let an external client such as Claude Desktop or ChatGPT talk to Odoo,
open *Settings > AI Assistant* and use **Connect AI**. The wizard shows a
ready-to-paste config for each client and can generate a personal API key.

## Adding a provider

Providers live in `ai/providers`. Subclass `ProviderBase`, implement the
request and response mapping, and add the class to `REGISTRY` in
`ai/providers/__init__.py`. The three built-in providers are good examples
to start from.

## Adding MCP tools

Inherit `aypatech_mcp.mixin` and decorate a method with `mcp_tool`:

```python
from odoo import api, models

from odoo.addons.aypatech_ai_assistant.mcp.core.tool import mcp_tool


class MCPMixin(models.AbstractModel):
    _inherit = 'aypatech_mcp.mixin'

    @api.model
    @mcp_tool(
        name='count_open_tasks',
        description='Count the open tasks of a project.',
        input_schema={
            'type': 'object',
            'properties': {
                'project_id': {'type': 'integer', 'description': 'Project ID.'},
            },
            'required': ['project_id'],
        },
        category='read',
    )
    def _mcp_count_open_tasks(self, project_id: int) -> int:
        return self.env['project.task'].search_count([
            ('project_id', '=', project_id),
            ('is_closed', '=', False),
        ])
```

The tool is picked up on the next registry load and becomes available to
both the internal agents and external MCP clients, always running with the
access rights of the calling user.

## Tests

```bash
odoo-bin -d test_db -i aypatech_ai_assistant --test-tags /aypatech_ai_assistant --stop-after-init
```

The JavaScript unit tests run through the same command via the `test_*_js`
cases, or directly in the browser at `/web/tests?tag=aypatech_ai`.
