---
paths:
  - "web/styles/inputs.css"
  - "web/templates/components/input_wrapper.hbs"
  - "web/templates/components/showroom/filter_input.hbs"
  - "web/src/inputs.ts"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Rules and foundations live in DESIGN.md at the repo root. -->

# Text input

The single-line text field, with optional leading icon and trailing icon
button. The sanctioned form is the `input_wrapper` partial around an
`.input-element`; the legacy `.settings_text_input` / `.modal_text_input`
classes still carry most settings and modal forms.

- **API** — `{{#> components/input_wrapper input_type=… icon=…
input_button_icon=… id=… custom_classes=…}}<input class="input-element"
…>{{/components/input_wrapper}}`. Renders `.input-element-wrapper`
  (`has-input-icon`, `has-input-button` added as needed) containing an
  optional `.input-icon` (`aria-hidden`), the block content, and an
  optional trailing squared neutral icon button `.input-button`.
  `input_type="filter-input"` makes it a filter field: the trailing button
  becomes `.input-close-filter-button` and clears the field
  (`inputs.ts`, delegated on `body`: `val("")`, `trigger("input")`, blur).
  The block may also hold a `.pill-container` (`has-input-pills`) for
  recipient-style inputs.
- **Anatomy** — CSS grid with named columns: icon offset 0.5em, icon 1em,
  gap 0.4375em, content `minmax(0, 1fr)`, gap 0.25em, button 1.5em, end
  offset 0.125em (`--input-icon-*`, `--input-button-*` in
  `app_variables.css`). The input's own padding grows to cover the icon and
  button columns, so they overlay the field rather than sit beside it.
  Optional uniform row height via `--input-element-row-height`.
- **Size** — one size: `label-md-regular` (1em / 400 / 1.25 line-height), padding 0.25em
  0.5em, `box-sizing: border-box`, 4px radius. Border is a 1px _outline_
  with `outline-offset: -1px`, so state changes never shift layout.
- **States**
  - rest → `text-input` on `background-input`, outline `outline-input`
    (30% of `hsl(229deg 22% 10%)` in light, 20% white in dark).
  - hover → `outline-input-hover` (60%). Transition 0.1s linear on
    outline-color and box-shadow.
  - focus → `.input-active-styles`: `background-input-focus`,
    `outline-input-focus` (80%), plus glow `0 0 5px box-shadow-input-focus`.
    Filter inputs also take the active styles whenever they hold text
    (`:not(:placeholder-shown)`), so a filled filter reads as "active".
  - placeholder → `--color-text-placeholder`; pill inputs emulate it with
    `data-placeholder` on an empty contenteditable.
  - filter, empty → trailing clear button hidden (`visibility: hidden`)
    and right padding collapses to 0.5em; it reappears as soon as there is
    text.
  - invalid → no rule on `.input-element` yet. Elsewhere `.invalid` /
    `.invalid-input` set `--color-invalid-input-border` and
    `--invalid-input-box-shadow` (`input_pill.css`, `app_components.css`,
    `modal.css`, `popovers.css`, `compose.css`); use the same two tokens
    when adding one.
  - disabled → no rule on `.input-element` yet; legacy inputs use
    `--background-color-readonly-modal-input` + `--opacity-readonly-modal-input`.
- **Behaviour**
  - Native `<input>`; no custom key handling. Escape inside a filter is
    handled by the view (`ui_util.ts` triggers the clear button for the
    left sidebar search), not by the component.
  - Clearing a filter must fire `input` so the view's filter logic runs;
    always go through the clear button or `.val("").trigger("input")`.
  - Search/filter inputs pair with a typeahead or live filtering; the
    input itself never debounces or fetches.
- **Accessibility** — the field needs a visible label or `aria-label`
  (the wrapper adds none; `placeholder` is not a label). The leading icon
  is decorative (`aria-hidden`); the trailing `icon_button` that
  `input_wrapper.hbs` renders has no `aria-label` (Known debt). Focus is
  shown by the outline + glow, not the global button ring.
- **Don't** — no `border` on `.input-element` (use the outline); no
  `hsl()` in input rules; no `height` in px; no hand-built
  icon-inside-input markup with absolute positioning; no `title=`.
- **Known debt** — `.settings_text_input` and
  `.modal_text_input` (both widely used) are the old form: content-box, `border`
  instead of outline, raw `hsl(0deg 0% 80%)` border, width computed by
  subtracting padding and border. `.modal_text_input` also has a 4px
  radius and a raw `hsl(0deg 0% 0% / 7.5%)` inset shadow; on
  `.settings_text_input` those values from `settings.css` are overridden
  by `input.settings_text_input` in `app_components.css` (5px radius, no
  shadow at rest, no margin), while its `:focus` rule still adds the inset
  shadow and a raw blue glow. Because they are content-box,
  `max-width: 100%` on them still overflows by padding + border. The
  global `input:not(.input-element)[type=…]` rule in `zulip.css` styles
  everything else (`height: 1.4em`, legacy colour tokens). `input_wrapper`
  is used in a few templates (sidebars, inbox, recent, topics filter, GIF
  picker) — settings and modals have not been migrated. No `.invalid` or
  `:disabled` state on the new input yet. The clear / trailing button
  rendered by `input_wrapper.hbs` has no `aria-label`, and the partial
  offers no parameter to pass one.
- **Code** — `web/styles/inputs.css`, `web/templates/components/input_wrapper.hbs`,
  `web/src/inputs.ts`; showroom section `showroom_component_inputs`
  (`zerver/views/development/showroom.py`).
