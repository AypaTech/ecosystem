Aypatech Odoo Community Template
=================================

Aypa Tech's own backend UI foundation for Odoo Community: everything a plain
Community install is missing compared to the comfort features Aypa Tech
expects on every deployment, built in-house and installed as a single module.

Features
--------

- **App sidebar** — a persistent list of installed apps down the side of the
  screen, similar to the Enterprise home menu. Each user picks a size
  (large, small or hidden) from their preferences, and a company logo can be
  shown at the bottom of the bar.
- **Chatter upgrades** — side or bottom chatter placement per user, a
  resizable side chatter, a show/hide toggle for system notification
  messages, and a clear split between messages sent to the customer and
  internal notes routed only to internal followers.
- **Dialog controls** — a per-user default dialog size and a one-click
  fullscreen toggle on every dialog and select/create popup.
- **Theme & branding settings** — light/dark color pickers for the core
  Odoo palette and for the app sidebar, a company favicon, and a sidebar
  logo, all editable from Settings and resettable to their defaults.
- **View grouping** — "Expand All" / "Collapse All" entries in the cog menu
  of grouped list and kanban views.
- **View refresh** — a manual refresh button in the control panel, an
  optional auto-refresh timer, and a "Reload Views" server action type that
  pushes view refreshes to connected users over the bus (handy from
  automation rules).

Configuration
-------------

Per-user preferences (sidebar size, chatter position, dialog size) are set
on each user's own profile. Colors, the sidebar logo and the favicon are
configured company by company under Settings > General Settings > Theme &
Branding.
