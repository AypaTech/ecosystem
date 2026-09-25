# Discuss integration notes (Phase 0 spike)

Source studied: `odoo/odoo` branch **19.0** (see `DECISIONS.md` — target moved from 18.0 to 19.0).
Files read: `addons/mail/models/discuss/discuss_channel.py`, `addons/mail/security/mail_security.xml`,
`addons/im_livechat/models/discuss_channel.py`, `addons/im_livechat/security/im_livechat_channel_security.xml`,
`addons/im_livechat/static/src/core/{public_web,web}/*`, `addons/mail/static/src/discuss/core/public_web/*`,
`addons/mail/static/src/core/public_web/discuss_app_model.js`, `odoo/addons/base/models/ir_cron.py`,
`odoo/orm/table_objects.py`.

## 1. channel_type

`im_livechat` does exactly what SPEC §5 proposes:

```python
channel_type = fields.Selection(selection_add=[('livechat', 'Livechat Conversation')],
                                ondelete={'livechat': 'cascade'})
```

We add `('telegram', 'Telegram Conversation')` with `ondelete={'telegram': 'cascade'}` in
`models/discuss_channel.py`. Custom channel types are fully supported; nothing in core refuses an
unknown type. Relevant core behaviour for a non-`channel`/`group`/`chat` type:

| Core code | Behaviour for `telegram` | Consequence |
| --- | --- | --- |
| `_group_public_id_check` constraint | `group_public_id` must stay empty | We never set it. |
| `write()` | `channel_type` cannot be changed after create | Always create with `channel_type='telegram'`. |
| `_add_members(post_joined_message=True)` | posts "joined the channel" notification for non-`channel` types | We pass `post_joined_message=False` when adding the customer/agents. |
| `_action_unfollow` | posts "left the channel" | Acceptable for agents leaving. |
| `_get_channels_as_member()` | non channel/group types are loaded only when the member **is pinned** | Members are pinned by default (`unpin_dt` empty). |
| `_lazy_load_members_channel_types()` = `channel, group` | telegram channels send full member list | Good: correspondent (customer) is known on the client. |
| `_notify_get_recipients` | members get `notif='web_push'` only, emails only for explicit `partner_ids` | The customer partner never receives an email; we additionally drop the customer from recipients (`_notify_get_recipients` override) to be safe. |
| `_types_allowing_unfollow()` | `channel, group` | Agents cannot "leave" by default in the UI; we add `telegram` so an agent can leave a conversation. |

## 2. Access rules

Core rule `ir_rule_discuss_channel_all`: for non-`channel` types the user must be a member
(`is_member`). Livechat adds a group rule `[('channel_type','=','livechat')]` (read only) and a
matching rule on `discuss.channel.member`.

We do the same, scoped to what SPEC §14 requires:

* `discuss.channel` stores `telegram_conversation_id` (Many2one, set at creation).
* Rule for `group_telegram_user` (read/write, no create/unlink):
  `channel_type = 'telegram'` and (conversation assignee = user, or user in conversation team,
  or conversation has no team). Company is enforced through `telegram_conversation_id.company_id`.
* Rule for `group_telegram_manager`: all telegram channels of allowed companies.
* Same pair of rules on `discuss.channel.member` (read) so the client can load members.
* `discuss.channel._mail_post_access = 'read'` in core, so read access is enough to reply. The
  `/mail/message/post` controller resolves the thread with `has_access('read')`, which honours
  our group rules.

## 3. Outbound hook

`discuss.channel.message_post()` → `mail.thread.message_post()` → `_message_post_after_hook(message, msg_vals)`.
The Discuss composer uses `/mail/message/post` which calls `thread.sudo().message_post(...)`: `env.su`
is True but `env.user` is still the real user.

We override `_message_post_after_hook` on `discuss.channel` (narrowest hook with the final
`mail.message` record) and queue outbound only if:

* `channel_type == 'telegram'` and the context key `telegram_inbound` is not set,
* `message.message_type == 'comment'`,
* `not message.is_internal` and not `message.subtype_id.internal`,
* the author partner has an internal (non-share) user.

Inbound customer messages are posted with `author_id = customer partner` (share partner, no user)
so they can never be re-sent.

## 4. Sidebar category (frontend)

`im_livechat/static/src/core/public_web/discuss_app_model_patch.js` defines a category record on
`DiscussApp`:

```js
this.defaultLivechatCategory = fields.One("DiscussAppCategory", {
    compute() { return { extraClass, hideWhenEmpty: true, icon, id, name, sequence }; },
    eager: true,
});
```

and `thread_model_patch.js` overrides `Thread._computeDiscussAppCategory()` to return it for
`channel_type === "livechat"`. Other hooks used by livechat and reused by us:

* `Thread.allowedToLeaveChannelTypes` / `allowedToUnpinChannelTypes` getters.
* `Thread.hasMemberList`, `Thread.computeCorrespondent()` (core returns `undefined` only for
  `channel`/`group`, so the single non-self member — our customer — is already the correspondent).
* `Thread.avatarUrl` / `displayName`.
* `ThreadIcon.defaultChatIcon` (`@mail/core/common/thread_icon`).
* `DiscussAppCategory.sortThreads()` for ordering by `lastInterestDt`.

Files we add (all under `static/src/discuss/`, bundle `web.assets_backend`):

* `discuss_app_model_patch.js` — `telegramCategory` (id `telegram.category`, icon `fa fa-telegram`,
  sequence 22, `hideWhenEmpty`).
* `discuss_app_category_model_patch.js` — sort telegram threads by last interest.
* `thread_model_patch.js` — category, leave/unpin types, member list, avatar = customer avatar.
* `thread_icon_patch.js` — Telegram icon.
* `telegram_discuss.scss` — icon colour.
* failed-delivery indicator: `message_model_patch.js` + `message_patch.xml` read
  `telegram_delivery_state` sent via `mail.message._to_store_defaults` (see §5).

## 5. Message status (failed indicator)

`mail.message._to_store_defaults(target)` returns a field list; we extend it on `mail.message`
with `telegram_delivery_state` (computed, non-stored) for messages of telegram channels and patch
the `Message` component to show a red exclamation with a tooltip when it is `failed`.
When a delivery changes state we push `Store(bus_channel=channel).add(message, ['telegram_delivery_state']).bus_send()`.

## 6. Cron/queue APIs (19.0)

* `ir.cron._trigger(at=None)` creates an `ir.cron.trigger` row in the current transaction →
  naturally fires only after commit.
* `ir.cron._commit_progress(processed, remaining=...)` commits and returns remaining seconds;
  outside a cron it just commits. `_notify_progress` is deprecated.
* Tests forbid `cr.commit()`; core uses `odoo.modules.module.current_test` to skip commits
  (`mail_mail.py`). Our services do the same via `services/utils.py:maybe_commit()`.

## 7. Other 19.0 API facts used

* SQL constraints: `models.Constraint("UNIQUE(...)", msg)`, `models.Index(...)`,
  `models.UniqueIndex("(...) WHERE ...")` — `_sql_constraints` is gone.
* Groups: `res.groups.privilege` + `privilege_id`; users are `user_ids` / `group_ids`.
* `@route(type='json')` is a deprecated alias of `type='jsonrpc'`.
* Views: `<list>`, `<chatter/>`, kanban `t-name="card"`, settings `<app>/<block>/<setting>`.
