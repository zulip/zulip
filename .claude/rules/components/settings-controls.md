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
     Rules and foundations live in DESIGN.md at the repo root. -->

# Settings controls

The building blocks of the settings, channel and group panels: the
checkbox, the tab switcher, the settings row (label + control) and the
subsection header with its save / discard controls.

## Checkbox

- **API** — `{{> settings/settings_checkbox setting_name=… label=…
is_checked=… is_disabled=… help_link=… help_icon_tooltip_text=…
show_reset_button=… label_parens_text=…}}` renders `.input-group.settings-checkbox-wrapper > label.checkbox > input[type=checkbox] + .rendered-checkbox`
  followed by the text `<label for=…>`. Hand-written
  forms use the same `label.checkbox` + `.rendered-checkbox` pair
  (`components.css`, shared with portico).
- **Anatomy** — the native input is visually hidden; `.rendered-checkbox`
  is a 10px box with 2px padding and a 1px `border-rendered-checkbox`
  (16px outer), 4px radius, 5px right margin, nudged up 2px to sit on the
  text baseline. Checked: the `checkbox.svg` mark (black at 60% —
  `checkbox-dark-mode.svg` in the dark theme) at 85% of the box. Label
  text is body text; `label_parens_text` renders in italics inside
  parentheses; help link / info icon / reset icon button follow the label.
- **States** — unchecked, checked, `:disabled` (box at 50% opacity,
  `not-allowed`; `.control-label-disabled` greys the label), focus
  (`input:focus ~ .rendered-checkbox` outline, `zulip.css`). No hover.
- **Behaviour** — toggling a `.prop-element` marks the subsection dirty and
  reveals the save / discard controls (`settings_components.ts`); nothing is
  saved until "Save changes".
- **Don't** — no native checkbox without `.rendered-checkbox`; no
  `title=`; no colour overrides (the todo-widget checkbox has its own
  tokens and is a different component).

## Tab switcher

- **API** — `components.toggle({html_class?, values: [{label, key}],
selected?, callback(label, key), child_wants_focus?})` returns
  `{get, value, goto, disable_tab, enable_tab, maybe_go_left/right, …}` and
  renders `.tab-switcher > .ind-tab.first|middle|last[.selected][.disabled]`
  with `tabindex=0` and `data-tab-key`. Used in modals
  (`.modal__tab-switcher-container`), settings headers and view filters.
- **Anatomy** — inline-block, 2px 4px margin; each tab 90px wide, padding
  3px 10px, centred, ellipsised, `background-tab-switcher-ind-tab`, 1px
  `border-tab-switcher-ind-tab`, tabs overlap by 0.5px so borders merge;
  outer corners 5px (`.first` left, `.last` right). `.large` tabs fill
  their container.
- **States** — rest; `.selected` → `background-tab-switcher-ind-tab-selected`,
  white text, `border-tab-switcher-ind-tab-selected`, raised above
  neighbours; `.disabled` → `text-tab-switcher-ind-tab-disabled` and
  `border-tab-switcher-ind-tab-disabled`, no pointer; focus-visible → 1px
  `outline-focus` inset 2px.
- **Behaviour** — click or Enter selects; Left / Right arrows on a
  focused tab move the selection to the next enabled tab (`components.ts`
  wires them with `keydown_util.handle`; some callers, e.g.
  `settings_panel_menu.ts`, also bind `maybe_go_left` / `maybe_go_right` to
  their own keys); `callback` fires on every change with the new key.
- **Don't** — no more than four tabs; no tab switcher as a form control
  for a setting that saves on change (use a dropdown widget or radio
  rows); no per-tab widths.

## Settings row

- **API** — every setting is an `.input-group`: a `<label class="…_label">`
  (or `.settings-field-label` above dropdowns) carrying the setting name,
  optional `(parens text)`, help link (`help_link_widget`), info icon
  (`.settings-info-icon`, tooltip) and reset icon button, then the control:
  checkbox (inline with the label), `dropdown_widget_with_label`
  (`.settings-field-label` + `.dropdown_widget_with_label_wrapper`),
  `settings_numeric_input` / text (`.settings_text_input`), textarea,
  pill container. The `.prop-element` carries `data-setting-widget-type`
  so `settings_components.ts` can read and write the value.
- **Anatomy** — `.input-group` has a 1.25em bottom margin;
  `.settings-field-label` a 3px bottom margin and `fit-content` width;
  info icon at 70% opacity (100% on hover), 3px left padding.
  `.settings_text_input` is the legacy input: `--modal-input-width`
  (23.2142em = 325px) via a calc that subtracts its own padding and border,
  padding `--input-vertical-padding` / `--input-horizontal-padding`
  (4px 6px), 1px raw `hsl(0deg 0% 80%)` border. `settings.css` also
  declares a 4px radius, a raw inset shadow and a 10px bottom margin, but
  `input.settings_text_input` in `app_components.css` wins on specificity,
  so the effective values are a 5px radius, no shadow at rest and no
  margin — see the text-input spec's known debt.
- **States** — `.control-label-disabled` (label + control greyed,
  `not-allowed`); dependent rows are hidden or disabled by their parent
  setting (`settings_components.ts` `set_up_dependent_settings`).
- **Don't** — no `<label>` without `for` or wrapping; no controls outside
  an `.input-group`; no new `.settings_text_input` where `input_wrapper`
  works.

## Subsection header and save / discard

- **API** — `.subsection-header` holds the `.settings-subsection-title`
  (1.5em / 400 / 1.5) and, from `settings_save_discard_widget.hbs`,
  `.save-button-controls` (solid brand "Save changes" `.save-button` +
  subtle neutral "Discard" `.discard-button`, 0.3125em apart) and the
  `.alert-notification` status text ("Saving…", "Saved", errors).
- **Behaviour** — the controls are `.hide` until a `.prop-element` in the
  `.settings-subsection-parent` changes (`settings_components.ts`
  `save_discard_widget_status_handler`); Save sends the changed values,
  shows "Saving…" then "Saved" (`data-status`, pointer-events off), then
  hides again; Discard restores the rendered values from the server data.
  Errors stay in `.alert-notification` and the controls remain visible.
- **Known debt** — `.alert-notification` colour is raw `hsl(156deg 30% 50%)`
  with `!important` sizing; subsection titles use 1.5em / 1.4em
  (`.settings-section-title`) without a token.
- **Code** — `web/styles/settings.css`, `web/styles/components.css`
  (checkbox), `web/styles/app_components.css` (`.tab-switcher`,
  `.subsection-header`, `.save-button-controls`), `web/src/components.ts`,
  `web/src/settings_components.ts`, `web/templates/settings/`.
