---
paths:
  - "web/styles/buttons.css"
  - "web/templates/components/icon_button.hbs"
  - "web/src/buttons.ts"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Rules and foundations live in DESIGN.md at the repo root. -->

# Icon button

A square, icon-only button. Use it where a label would not fit (row
actions, close buttons, toolbars); always give it an `aria-label`, and add a tooltip as well.

- **API** — `{{> components/icon_button intent=… icon=… squared=… id=…
custom_classes=… disabled=… aria-label=… data-tippy-content=…
data-micromodal-close=…}}` renders
  `<button class="icon-button icon-button-<intent> [icon-button-square]">`
  with one `.zulip-icon`. `intent` as for action buttons. `.icon-button`
  without an intent class has no colour and is a bug.
- **Anatomy & size** — font size `--base-font-size-px`; one icon at 1em
  with `line-height: 100%` (`web/icons/template.hbs`), padding
  `--icon-button-padding` (0.375em), `aspect-ratio: 1`, radius 4px →
  1.75em, i.e. 24.5px square at the 14px base (21px at 12px).
  Tokens: `components.icon-button-<intent>` (rest) and
  `icon-button-<intent>-hover`.
- **States**
  - rest → icon at 70% of the intent's text colour, transparent background.
  - hover / focus-visible → icon at 100%; `squared` variants also get a
    tinted background (`background-<intent>-icon-button-square-hover`).
  - active → back to 70% (plain) or tinted-active (squared); 1px clip
    press cue as on action buttons.
  - focus-visible, disabled → same as action button. Banner close buttons
    pull the focus ring 2px inward so it stays inside the banner border.
- **Behaviour** — native button; new uses must pass `aria-label` since
  there is no text (the partial outputs it only when given). Tooltip via
  `data-tippy-content` / `data-tooltip-template-id` — the app's tooltip
  delays are `INSTANT_HOVER_DELAY` (100ms) for toolbars and
  `LONG_HOVER_DELAY` (750ms) for things users tap repeatedly (see
  `tippyjs.ts`). `data-micromodal-close` makes it a modal dismiss button.
- **Don't** — no icon inside an action button as a substitute; no text
  next to the icon (that is an action button); no `font-size` overrides on
  the icon; no `title=` attributes (tooltips are tippy).
- **Accessibility** — `aria-label` is required (no visible text); the icon is
  `aria-hidden`. Tooltip text is not a substitute for the label. Use the
  partial's existing size; don't add new ones. Partials that render an
  icon button without `aria-label` are listed as debt in their own specs
  (banner close, input clear).
- **Code** — `web/styles/buttons.css` (`.icon-button*`),
  `web/templates/components/icon_button.hbs`.
