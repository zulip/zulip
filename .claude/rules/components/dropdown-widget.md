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
     Generic rules (tokens, focus, motion, accessibility) are in DESIGN.md at
     the repo root; this file only adds what is specific to dropdown widgets. -->

# Dropdown widget

The select control used in settings, modals, the compose box and view
filters: a button showing the current value that opens a filterable list.
One JS class owns opening, filtering, keyboard handling and selection;
callers only supply options.

- **API** — `new dropdown_widget.DropdownWidget({widget_name,
get_options, item_click_callback, $events_container, default_id?,
unique_id_type?, hide_search_box?, text_if_current_value_not_in_options?,
sticky_bottom_option?, tippy_props?, prefer_top_start_placement?,
disable_for_spectators?, focus_target_on_hidden?, …})` then `.setup()`;
  `render(value?)` updates the button, `current_value` reads it. Markup:
  `{{> dropdown_widget}}` (`<button class="dropdown-widget-button">`),
  `{{> dropdown_widget_with_label}}` for settings rows,
  `{{> dropdown_widget_wrapper}}` when the wrapper should take keyboard
  focus instead of the button (`disable_keyboard_focus`). Options are
  `{unique_id, name, description?, stream?, is_direct_message?,
is_setting_disabled?, bold_current_selection?, has_edit_icon?,
has_delete_icon?, has_manage_folder_icon?}`, rendered by
  `dropdown_list.hbs` inside a tippy of theme `dropdown-widget`.
- **Anatomy** — the button shows the value and a `chevron-down` icon.
  The list box holds an optional `.popover-filter-input`, `ul.dropdown-list`
  (capped at `DEFAULT_DROPDOWN_HEIGHT`, simplebar), a "No matching
  results" placeholder and an optional `.sticky-bottom-option-button`.
  Rows are `li.list-item` > `a.dropdown-list-item-common-styles` (label,
  optional description), with optional `.dropdown-list-buttons` (edit /
  manage folder / delete icon buttons) at the right edge. The list box
  stays at the base font size. Sizes are in `app_components.css` and
  `zulip.css`; the box's three-layer shadow is written in the
  `dropdown-widget` theme in `popovers.css`.
- **States**
  - button `:disabled` → `background-disabled-dropdown-widget-button`,
    70% opacity, `not-allowed` cursor (50% with
    `.dropdown-widget-disabled-for-spectators`). The value is italic when
    it's not in the options or is the "Disable" option. No hover style.
  - row hover / focus → `--background-color-active-dropdown-item`, and
    the row buttons appear.
  - `.current_selection` → `--background-color-current-selection-dropdown-item`
    and an `outline-focus` bar on the left edge.
  - `.highlight_value` (the saved setting) →
    `--background-color-current-setting-dropdown-item`.
- **Behaviour** (`dropdown_widget.ts`)
  - Click or Enter opens it below the button, or above when there's not
    enough room (`prefer_top_start_placement` inverts this). Options are
    re-read from `get_options` on every open.
  - The filter input takes focus on open; with `hide_search_box`, the
    list does (and the first row on keyboard open).
  - Up / Down move between rows, wrapping through the filter input and
    the sticky option; Enter or click selects and closes; Escape closes.
    Focus returns to the button on close (`focus_target_on_hidden`,
    default true).
- **Accessibility** — the button is a native `<button>` with `name`;
  rows are `li[role=presentation][tabindex=0]` named by their text; row
  icon buttons carry `aria-label`.
- **For new code**
  - Use `DropdownWidget` for selects, not a custom `<select>` or
    Bootstrap `.dropdown` markup.
  - Keep the list height at `DEFAULT_DROPDOWN_HEIGHT`; the placement
    logic in `dropdown_widget.ts` depends on it.
- **Sanctioned exception** to the no-override rule — the compose
  recipient dropdown (`compose.css`) overrides paddings and the selected
  weight.
- **Known debt**
  - The list isn't a `listbox` and the button has no `aria-expanded`.
  - The box shadow, the `.filter_text_input` border and inset shadow,
    and the `.no-dropdown-items` colour are raw `hsl()`.
  - `--background-color-*`, `--color-dropdown-item` and
    `--color-active-dropdown-item` break the token naming.
  - `.dropdown-widget-button { outline: none }` loses to the legacy
    `button:focus-visible` rule, so keyboard focus shows the legacy ring;
    ID-scoped overrides remove it for the compose recipient widget
    (`compose.css`) and the move-topic and report modals (`popovers.css`).
  - Row buttons don't show on touch screens (DESIGN.md › Focus & keyboard).
- **Code** — `web/src/dropdown_widget.ts`, `web/templates/dropdown_*.hbs`,
  `web/styles/app_components.css` (`.dropdown-widget-button`,
  `.sticky-bottom-option-button`), `web/styles/zulip.css`
  (`.dropdown-list-container`), `web/styles/popovers.css`
  (`.tippy-box[data-theme="dropdown-widget"]`).
