---
paths:
  - "web/styles/popovers.css"
  - "web/src/popover_menus.ts"
  - "web/src/popover_menus_data.ts"
  - "web/templates/popovers/**/*.hbs"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Generic rules (tokens, focus, motion, accessibility) are in DESIGN.md at
     the repo root; this file only adds what is specific to popover menus. -->

# Popover menu

The floating list of actions opened from a trigger (gear, message
actions, sidebar "more", user card). One tippy theme and one set of
`.popover-menu-*` classes; templates under `web/templates/popovers/`
only fill the list.

- **API** — a template renders `<div class="popover-menu" data-simplebar>
  <ul role="menu" class="popover-menu-list">` with `<li role="none"
  class="link-item popover-menu-list-item"><a role="menuitem"
  class="popover-menu-link" tabindex="0">` rows, `<li role="separator"
  class="popover-menu-separator">` between groups, and `.text-item` rows
  for non-interactive text. Opened with `popover_menus.toggle_popover_menu`
  or `tippy` with `default_popover_props` and the `popover-menu` theme.
- **Anatomy** — the tippy box: `background-popover-menu`, 1px
  `border-popover-menu`, 6px radius, `--box-shadow-popover-menu`
  (`--box-shadow-gear-menu` for the gear menu). It sets font-size
  1.0714em, so everything inside is sized against that. A row is an
  optional `.popover-menu-icon`, the `.popover-menu-label` and optional
  `.popover-menu-hotkey-hints` pushed right. Width comes from the longest
  row, capped by `--popover-menu-max-width`. Sizes are in `popovers.css`.
- **States** (`.link-item .popover-menu-link`) — hover
  `background-hover-popover-menu`; focus-visible adds an inset ring in
  `outline-focus`; active `background-active-popover-menu`; `.text-item`
  is grey, selectable and has no hover; separators use
  `border-popover-menu-separator`.
- **Behaviour** — opening, closing and positioning follow DESIGN.md ›
  Floating layers. Arrow keys move between `menuitem`s and Enter
  activates. Selecting an item closes the menu unless it's a setting
  toggle (radio rows).
- **Accessibility** — `role="menu"`, `role="menuitem"` and
  `role="separator"` are required on the list, rows and separators; hotkey
  hints are decorative (the keyboard shortcuts overlay documents them).
- **For new code** — build menus from these classes and roles, opened
  through `popover_menus.ts`, rather than a new floating list.
- **Don't** — no rows without `role`.
- **Sanctioned exception** to the no-override rule — the user card sets
  `--color-text-item` locally.
- **Known debt**
  - `popovers.css` has many `!important`s, including the
    `.popover-menu-link` colour (over Bootstrap) and several focus
    outlines.
  - `--color-popover-hotkey-hint` has no property in its name,
    `--color-text-item` doesn't name its component, and several tokens
    put `-popover-menu` at the end rather than in the middle.
  - `--color-icon-purple` and `--color-outline-focus` have no dark-theme
    value.
- **Code** — `web/styles/popovers.css` (`.tippy-box[data-theme="popover-menu"]`,
  `.popover-menu*`), `web/src/popover_menus.ts`, templates in
  `web/templates/popovers/`.
