---
paths:
  - "web/styles/popovers.css"
  - "web/src/popover_menus.ts"
  - "web/src/popover_menus_data.ts"
  - "web/templates/popovers/**/*.hbs"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Rules and foundations live in DESIGN.md at the repo root. -->

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
  / `tippy` using `default_popover_props` (`popover_menus.ts`) and the
  `popover-menu` theme; content goes through `parse_html`, never
  `allowHTML`.
- **Anatomy** — the tippy box: `background-popover-menu`, 1px
  `border-popover-menu`, 6px radius, `--box-shadow-popover-menu`
  (six layers; the gear menu uses `--box-shadow-gear-menu`), font-size
  1.0714em (15px at the 14px base — everything inside is em of 15px). The
  list has 4px vertical padding. A row is `flex` with a 5px gap: optional
  `.popover-menu-icon` (16px, `icon-purple`), `.popover-menu-label`
  (`max-content`, grows), optional `.popover-menu-hotkey-hints` pushed
  right (4px gap, 5px left padding) holding `.popover-menu-hotkey-hint`
  chips (14px/500, 1em line-height, min-width 1.4285em, padding 2px 4px,
  3px radius, 1px `border-popover-hotkey-hint`, text
  `popover-hotkey-hint`). Row padding 0.2em 0.6666em (3px 10px),
  line-height 1.0667em (16px), min-height 1.625em.
- **States** (`.link-item .popover-menu-link`)
  - rest → `text-popover-menu` on the menu background.
  - hover → `background-hover-popover-menu` (5% tint).
  - focus-visible → hover background plus a 1px inset box-shadow in
    `outline-focus` and a 4px radius (inset, so the menu's
    `overflow-x: hidden` cannot clip it).
  - active → `background-active-popover-menu` (7% tint).
  - `.text-item` → `text-item` (grey), selectable, no hover.
  - separator → 1px `border-popover-menu-separator`, 4px margins.
- **Behaviour** — see DESIGN.md "Floating layers": click trigger,
  `hideOnClick`, `appendTo: document.body`, Popper flip/preventOverflow,
  `destroy-popover-if-reference-hidden`. Arrow keys move between
  `menuitem`s, Enter activates, Escape closes and returns focus to the
  trigger when opened via keyboard (`opened_via_keyboard`). Selecting an
  item closes the menu unless it is a setting toggle (radio rows).
- **Accessibility** — `role="menu"` / `role="menuitem"` / `role="separator"`
  are required on the list, rows and separators; icons are `aria-hidden`;
  hotkey hints are decorative (the hotkey is documented in the keyboard
  shortcuts overlay). The menu's width comes from its longest row
  (`width: min-content`), capped by `--popover-menu-max-width` / 97vw.
- **Don't** — no ad-hoc positioning or a second popover library; no
  `allowHTML`; no rows without `role`; no colour overrides per popover
  (the user card sets `--color-text-item` locally and is the one sanctioned
  exception); no new `!important` (`popovers.css` already has many,
  including the `.popover-menu-link` colour and several focus outlines).
- **Known debt** — `.popover-menu-link { color … !important }` overrides
  Bootstrap; the compose/search typeahead is a Bootstrap component with
  its own Popper; `--color-popover-hotkey-hint` has no property in its
  name and `--color-text-item` doesn't name its component;
  `--color-icon-purple` and `--color-outline-focus` are single values with
  no dark-theme variant; several tokens carry the
  `-popover-menu` suffix rather than the component-in-the-middle pattern.
- **Code** — `web/styles/popovers.css` (`.tippy-box[data-theme="popover-menu"]`,
  `.popover-menu*`), `web/src/popover_menus.ts`, templates in
  `web/templates/popovers/`.
