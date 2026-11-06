---
paths:
  - "web/styles/settings.css"
  - "web/styles/components.css"
  - "web/src/components.ts"
  - "web/src/settings_components.ts"
  - "web/templates/settings/settings_checkbox.hbs"
  - "web/templates/settings/settings_numeric_input.hbs"
  - "web/templates/settings/settings_save_discard_widget.hbs"
  - "web/templates/dropdown_widget_with_label.hbs"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Generic rules (tokens, focus, motion, accessibility) are in DESIGN.md at
     the repo root; this file only adds what is specific to settings controls. -->

# Settings controls

The building blocks of the settings, channel and group panels: the
checkbox, the tab switcher, the settings row (label + control) and the
subsection header with its save / discard controls.

## Checkbox

- **API** — `{{> settings/settings_checkbox setting_name=… label=…
is_checked=… is_disabled=… help_link=… help_icon_tooltip_text=…
show_reset_button=… label_parens_text=…}}` renders
  `.input-group.settings-checkbox-wrapper > label.checkbox >
input[type=checkbox] + .rendered-checkbox`, then the text
  `<label for=…>`. Hand-written forms use the same `label.checkbox` +
  `.rendered-checkbox` pair (`components.css`, shared with portico).
- **Anatomy** — the native input is visually hidden; `.rendered-checkbox`
  draws the box (`border-rendered-checkbox`) and, when checked, the
  `checkbox.svg` mark (`checkbox-dark-mode.svg` in the dark theme). Sizes
  are in `components.css`. `label_parens_text` renders in italics in
  parentheses; help link, info icon and reset button follow the label.
- **States** — unchecked, checked, `:disabled` (box at 50% opacity,
  `not-allowed` cursor; `.control-label-disabled` greys the label), and
  focus via the legacy ring. No hover.
- **Behaviour** — toggling a `.prop-element` marks the subsection changed
  and shows the save / discard controls (`settings_components.ts`).
- **For new code** — no native checkbox without `.rendered-checkbox`.
  (The todo widget's checkbox is a different component with its own
  tokens.)

## Tab switcher

- **API** — `components.toggle({html_class?, values: [{label, key}],
selected?, callback(label, key), child_wants_focus?})` returns
  `{get, value, goto, disable_tab, enable_tab, maybe_go_left/right, …}` and
  renders `.tab-switcher > .ind-tab.first|middle|last[.selected][.disabled]`
  with `tabindex=0` and `data-tab-key`. Used in modals
  (`.modal__tab-switcher-container`), settings headers and view filters.
- **Anatomy** — equal-width tabs (`background-tab-switcher-ind-tab`,
  `border-tab-switcher-ind-tab`) whose borders overlap so they merge;
  `.large` tabs fill their container. Sizes in `app_components.css`.
- **States** — `.selected` → `background-tab-switcher-ind-tab-selected`,
  white text, `border-tab-switcher-ind-tab-selected`; `.disabled` →
  `text-tab-switcher-ind-tab-disabled` and
  `border-tab-switcher-ind-tab-disabled`, no pointer; focus-visible is an
  inset `outline-focus` ring.
- **Behaviour** — click or Enter selects; Left / Right on a focused tab
  move to the next enabled tab (`components.ts`, `keydown_util.handle`;
  some callers, e.g. `settings_panel_menu.ts`, bind `maybe_go_left` /
  `maybe_go_right` to their own keys); `callback` fires on every change.
- **Don't** — no tab switcher for a setting that saves on change (use a
  dropdown widget or radio rows); no per-tab widths.
- **Known debt** — the 5px outer corners.

## Settings row

- **API** — every setting is an `.input-group`: a label (or
  `.settings-field-label` above dropdowns) with the setting name, optional
  parens text, help link (`help_link_widget`), info icon
  (`.settings-info-icon`) and reset button, then the control: checkbox,
  `dropdown_widget_with_label`, `settings_numeric_input` or text
  (`.settings_text_input`), textarea, or pill container. The
  `.prop-element` carries `data-setting-widget-type` so
  `settings_components.ts` can read and write the value.
- **Anatomy** — spacing between rows and labels is on `.input-group` and
  `.settings-field-label` in `settings.css`. Text fields use the legacy
  `.settings_text_input` (text input spec, Known debt).
- **States** — `.control-label-disabled` (label and control greyed,
  `not-allowed` cursor); dependent rows are hidden or disabled by their
  parent setting (`settings_org.ts` `update_dependent_subsettings`,
  `settings_ui.disable_sub_setting_onchange`).
- **For new code** — every control sits in an `.input-group` with its
  label.

## Subsection header and save / discard

- **API** — `.subsection-header` holds the `.settings-subsection-title`
  and, from `settings_save_discard_widget.hbs`, `.save-button-controls`
  (solid brand "Save changes" `.save-button` + subtle neutral "Discard"
  `.discard-button`) and the `.alert-notification` status text.
- **Behaviour** — the controls are `.hide` until a `.prop-element` in
  the `.settings-subsection-parent` changes
  (the `save_discard_*_widget_status_handler` functions in
  `settings_components.ts`). Save sends the changed values,
  shows "Saving…" then "Saved", then hides again; Discard restores the
  saved values. Errors stay in `.alert-notification` and the controls
  stay visible.
- **Known debt** — `.alert-notification` colour is a raw `hsl()` with
  `!important` sizing; subsection and section titles have one-off sizes
  without a token.

- **Code** — `web/styles/settings.css`, `web/styles/components.css`
  (checkbox), `web/styles/app_components.css` (`.tab-switcher`,
  `.subsection-header`, `.save-button-controls`), `web/src/components.ts`,
  `web/src/settings_components.ts`, `web/templates/settings/`.
