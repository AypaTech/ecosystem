# -*- coding: utf-8 -*-
"""Routing and assignment (SPEC §13)."""


class TelegramRoutingService:

    def __init__(self, env, bot):
        self.env = env
        self.bot = bot.sudo()

    def match_route(self, text="", language_code="", is_new_customer=False):
        routes = self.env["telegram.route"].sudo().search(
            [("bot_id", "=", self.bot.id), ("active", "=", True)], order="sequence, id",
        )
        text_lower = (text or "").lower()
        lang = (language_code or "").lower()
        for route in routes:
            values = [v.strip().lower() for v in (route.condition_value or "").split(",") if v.strip()]
            if route.condition_type == "always":
                return route
            if route.condition_type == "keyword" and any(v in text_lower for v in values):
                return route
            if route.condition_type == "language" and lang and any(
                    lang == v or lang.split("-")[0] == v for v in values):
                return route
            if route.condition_type == "new_customer" and is_new_customer:
                return route
        return self.env["telegram.route"]

    def route(self, conversation, text="", language_code="", is_new_customer=False):
        """Apply the first matching route, fallback to bot defaults. Returns the assignee."""
        route = self.match_route(text, language_code, is_new_customer)
        team = route.team_id or self.bot.team_id
        user = route.user_id or self.pick_user(team) or self.bot.default_user_id
        vals = {}
        if team:
            vals["team_id"] = team.id
        if route.tag_ids:
            vals["tag_ids"] = [(4, tag.id) for tag in route.tag_ids]
        if vals:
            conversation.sudo().write(vals)
        if user:
            conversation.sudo()._assign(user)
        return user

    def pick_user(self, team):
        if not team or team.assignment_method == "manual":
            return self.env["res.users"]
        members = team.member_ids.filtered(lambda u: u.active and not u.share).sorted("id")
        if not members:
            return self.env["res.users"]
        if team.assignment_method == "round_robin":
            # serialize concurrent assignments on the same team
            self.env.cr.execute("SELECT id FROM telegram_team WHERE id = %s FOR UPDATE", (team.id,))
            team.invalidate_recordset(["last_assigned_user_id"])
            last = team.last_assigned_user_id
            nxt = members.filtered(lambda u: last and u.id > last.id)[:1] or members[:1]
            team.sudo().last_assigned_user_id = nxt
            return nxt
        if team.assignment_method == "least_busy":
            Conversation = self.env["telegram.conversation"].sudo()
            counts = dict(Conversation._read_group(
                [("user_id", "in", members.ids), ("state", "in", Conversation._open_states())],
                ["user_id"], ["__count"],
            ))
            return min(members, key=lambda u: (counts.get(u, 0), u.id))
        return self.env["res.users"]
