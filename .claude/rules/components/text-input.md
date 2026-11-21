---
paths:
  - "web/styles/inputs.css"
  - "web/templates/components/input_wrapper.hbs"
  - "web/templates/components/showroom/filter_input.hbs"
  - "web/src/inputs.ts"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Generic rules (tokens, focus, motion, accessibility) are in DESIGN.md at
     the repo root; this file only adds what is specific to text inputs. -->

# Text input

The single-line text field, with optional leading icon and trailing icon
button. The component is the `input_wrapper` partial around an
`.input-element`; the legacy `.settings_text_input` / `.modal_text_input`
classes still carry most settings and modal forms.

- **API** — `{{#> components/input_wrapper input_type=… icon=…
input_button_icon=… id=… custom_classes=…}}<input class="input-element"
…>{{/components/input_wrapper}}`. Renders `.input-element-wrapper`
  (`has-input-icon`, `has-input-button` as needed) with an optional
  `.input-icon`, the block content and an optional trailing squared
  neutral icon button `.input-button`. `input_type="filter-input"` makes
  it a filter field: the trailing button becomes
  `.input-close-filter-button` and clears the field (`inputs.ts`). The
  block may also hold a `.pill-container` (`has-input-pills`).
- **Anatomy** — a CSS grid with named columns for icon, content and
  button (`--input-icon-*`, `--input-button-*` in `app_variables.css`);
  the input's own padding covers the icon and button columns, so they
  overlay the field. Optional uniform row height via
  `--input-element-row-height`. Type is the Label, regular style; padding
  and radius are on `.input-element` in `inputs.css`. The border is a 1px
  outline with `outline-offset: -1px`.
- **States** — rest `text-input` on `background-input` with
  `outline-input`; hover `outline-input-hover`; focus
  `.input-active-styles` (`background-input-focus`, `outline-input-focus`
  and a glow in `--color-box-shadow-input-focus`), which filter inputs
  also keep while they hold text; placeholder `--color-text-placeholder`.
  An empty filter hides its clear button. There is no invalid or disabled
  rule on `.input-element` yet.
- **Behaviour**
  - Native `<input>`; no custom key handling. Escape in a filter is
    handled by the view (e.g. `ui_util.ts` for the left sidebar search).
  - Search and filter inputs pair with a typeahead or live filtering; the
    input itself never debounces or fetches.
- **Accessibility** — the wrapper adds no label (DESIGN.md › Accessibility
  › Names); the leading icon is `aria-hidden`.
- **For new code**
  - Use `input_wrapper` + `.input-element` where it fits (existing:
    sidebars, inbox, recent conversations, the topics filter, the GIF
    picker); not a new `.settings_text_input`.
  - Clear a filter through its clear button or `.val("").trigger("input")`,
    so the view's filter logic runs.
  - For an invalid state, use `--color-invalid-input-border` and
    `--invalid-input-box-shadow` (existing: `input_pill.css`,
    `modal.css`).
- **Don't** — no `border` on `.input-element` (use the outline); no
  `height` in px; no hand-built icon-inside-input markup with absolute
  positioning.
- **Known debt**
  - `.settings_text_input` and `.modal_text_input` are the old form:
    content-box, `border` instead of outline, a raw `hsl(0deg 0% 80%)`
    border, width computed by subtracting padding and border (so
    `max-width: 100%` still overflows), and a 0.2s transition.
    `.modal_text_input` adds a raw inset shadow; on `.settings_text_input`
    the `settings.css` radius, shadow and margin are overridden by
    `input.settings_text_input` in `app_components.css` (a 5px radius),
    while its `:focus` rule adds an inset shadow and a raw blue glow.
  - The global `input:not(.input-element)[type=…]` rule in `zulip.css`
    styles every other input with legacy tokens; disabled legacy inputs
    use `--background-color-readonly-modal-input` and
    `--opacity-readonly-modal-input`.
  - The clear / trailing button from `input_wrapper.hbs` has no
    `aria-label`, and the partial has no parameter to pass one.
- **Code** — `web/styles/inputs.css`, `web/templates/components/input_wrapper.hbs`,
  `web/src/inputs.ts`; showroom `/devtools/inputs/`.
