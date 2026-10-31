---
paths:
  - "web/src/dropdown_widget.ts"
  - "web/templates/dropdown_widget.hbs"
  - "web/templates/dropdown_widget_wrapper.hbs"
  - "web/templates/dropdown_widget_with_label.hbs"
  - "web/templates/dropdown_list.hbs"
  - "web/templates/dropdown_list_container.hbs"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Rules and foundations live in DESIGN.md at the repo root. -->

# Dropdown widget

The select control used in settings, modals, the compose box and view
filters: a button showing the current value that opens a filterable list.
One JS class owns opening, filtering, keyboard handling and selection;
callers only supply options.

- **API** — `new dropdown_widget.DropdownWidget({widget_name,
get_options, item_click_callback, $events_container, default_id?,
unique_id_type?, hide_search_box?, text_if_current_value_not_in_options?,
sticky_bottom_option?, tippy_props?, prefer_top_start_placement?,
disable_for_spectators?, …})` then `.setup()`; `render(value?)` updates
  the button, `current_value` reads it. Markup: `{{> dropdown_widget}}`
  (`<button class="dropdown-widget-button">` with `.dropdown_widget_value`
  and a `zulip-icon-chevron-down`), `{{> dropdown_widget_with_label}}` for
  settings rows (`.input-group` + `.settings-field-label` + `.prop-element`),
  `{{> dropdown_widget_wrapper}}` when the button must not take keyboard
  focus itself. Options are `{unique_id, name, description?, stream?,
is_direct_message?, is_setting_disabled?, bold_current_selection?,
has_edit_icon?, has_delete_icon?, has_manage_folder_icon?}` rendered by
  `dropdown_list.hbs`; the list lives in `dropdown_list_container.hbs`
  inside a tippy of theme `dropdown-widget`.
- **Anatomy** — button: `--width-dropdown-widget-button` (206px), padding
  4px 6px, 1px `border-dropdown-widget-button`,
  `background-dropdown-widget-button`, 4px radius, `text-default`, value
  left, chevron right (`space-between`). List box: `background-dropdown-widget`,
  1px `border-dropdown-widget`, 6px radius, three-layer shadow (7/13, 5/8,
  2/4 at 15/12/10% — 35/32/20% dark), sized in the base font (not the
  popover's 15px). Inside: `.popover-filter-input` (margin 4px 4px 2px,
  `background-widget-input`, `text-dropdown-input`; the `.filter_text_input`
  border and inset shadow are raw `hsl()`), 4px viewport padding, `ul.dropdown-list`
  (min-width 14.285em, max-height 210px = `DEFAULT_DROPDOWN_HEIGHT`, simplebar),
  "No matching results" placeholder, optional `.sticky-bottom-option-button`
  (full width, padding 7px 14px, neutral subtle button background).
  Rows: `li.list-item` (margin 0 4px, 4px radius) > `a.dropdown-list-item-common-styles`
  (grid: label row + optional description row, padding 5px 6px, line-height
  1.214, `dropdown-item` colour). Label variants: plain text
  (`.dropdown-list-text-neutral`), bold current selection
  (`.dropdown-list-text-selected`, 600), channel (`decorated_channel_name`),
  direct message (`users` icon), disabled option (`deactivated-circle` icon,
  italic), channel mapping (`hashtag` icon); icons at 0.9375em with a
  0.3125em gap. Optional `.dropdown-list-buttons` (neutral edit / manage
  folder, danger delete icon buttons) sit at the row's right edge and are
  `visibility: hidden` until the row is hovered or focused.
- **States**
  - button: rest; `:disabled` → `background-disabled-dropdown-widget-button`,
    70% opacity, `not-allowed` cursor (50% when
    `.dropdown-widget-disabled-for-spectators`). The value is italic when
    it is not in the options (`.dropdown-current-value-not-in-options`) or
    is the "Disable" option (`.setting-disabled-option`). No hover style.
    Focus: `.dropdown-widget-button { outline: none }` (specificity 0,1,0)
    loses to the global `button:focus-visible` rule in `zulip.css`
    (0,1,1), so keyboard focus shows the 2px `outline-focus` ring; ID-scoped
    overrides remove it again for the compose recipient widget
    (`#compose_select_recipient_widget`, `compose.css`) and the move-topic / report modal
    widgets (`popovers.css`). The wrapper carries focus when
    `disable_keyboard_focus` is set.
  - row hover / focus → `background-color-active-dropdown-item` (5% tint),
    control buttons become visible.
  - current selection (`.current_selection`, also the focused row) → 2%
    tint (`background-color-current-selection-dropdown-item`) and a 3px
    `outline-focus` bar on the left edge; hover on it is transparent.
  - current setting (`.highlight_value`, the option equal to the saved
    setting) → `background-color-current-setting-dropdown-item` (purple
    13%) with `current-setting-dropdown-item` text.
  - empty filter result → `.no-dropdown-items` shown (raw `hsl(0 0% 60%)`).
- **Behaviour** (`dropdown_widget.ts`)
  - Click or Enter on the button opens the tippy (`trigger: click`,
    `interactive`, `hideOnClick`, `appendTo: body`); placement is
    `bottom-start` unless there is less than 210px below (then `top-start`;
    `prefer_top_start_placement` inverts this). The list re-renders from
    `get_options` on every open.
  - Typing filters by name (`sort_list_by_filter_value` optional); the
    filter input is focused on open unless `hide_search_box`, in which case
    the container takes focus and, on keyboard open, the first row.
  - Up/Down move between rows, wrapping into the filter input and the
    sticky option; Enter or click selects (`item_click_callback` receives
    the event, the tippy instance and the widget) and closes; Escape
    closes and returns focus to the button.
  - `render()` writes the selected name into `.dropdown_widget_value`,
    falling back to `text_if_current_value_not_in_options` (italic) or the
    empty string.
- **Accessibility** — the button is a native `<button>` with `name`; rows
  are `li[role=presentation][tabindex=0]` with the text as their accessible
  name; control icon buttons carry `aria-label`. The list is not a
  `listbox` and the button has no `aria-expanded` — known gap.
- **Don't** — no custom `<select>` styling or Bootstrap `.dropdown` markup
  for new selects; no per-widget colours (the compose recipient dropdown
  overrides paddings and the selected weight in `compose.css` and is the
  sanctioned exception); no `title=`; no `max-height` other than
  `DEFAULT_DROPDOWN_HEIGHT` without syncing `dropdown_widget.ts`.
- **Known debt** — `.filter_text_input` border, inset shadow and
  `.no-dropdown-items` colour are raw `hsl()`; `--background-color-*` and
  `--color-dropdown-item` / `--color-active-dropdown-item` break the
  `--color-<property>-…` naming; the button has no hover style, its
  focus ring is the legacy global one, and its own `outline: none` has no
  effect on keyboard focus (only the ID-scoped repeats do);
  `.settings_text_input`-era spacing in `settings.css` still wraps
  most instances.
- **Code** — `web/src/dropdown_widget.ts`, `web/templates/dropdown_*.hbs`,
  `web/styles/app_components.css` (`.dropdown-widget-button`,
  `.sticky-bottom-option-button`), `web/styles/zulip.css`
  (`.dropdown-list-container`, `.popover-filter-input-wrapper`),
  `web/styles/popovers.css` (`.tippy-box[data-theme="dropdown-widget"]`).
