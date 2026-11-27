---
paths:
  - "web/styles/buttons.css"
  - "web/templates/components/icon_button.hbs"
  - "web/src/buttons.ts"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Generic rules (tokens, focus, motion, accessibility) are in DESIGN.md at
     the repo root; this file only adds what is specific to icon buttons. -->

# Icon button

A square, icon-only button for places where a label would not fit (row
actions, close buttons, toolbars).

- **API** — `{{> components/icon_button intent=… icon=… squared=… id=…
custom_classes=… disabled=… aria-label=… data-tippy-content=…
data-micromodal-close=…}}` renders
  `<button class="icon-button icon-button-<intent> [icon-button-square]">`
  with one `.zulip-icon`. `intent` as for action buttons;
  `data-micromodal-close` makes it a modal dismiss button.
- **Anatomy** — one icon at 1em, square (`aspect-ratio: 1`), padding
  `--icon-button-padding`; sizes are on `.icon-button` in `buttons.css`.
- **States** — rest: icon at 70% of the intent's text colour, no
  background. Hover and focus-visible: icon at 100%; `squared` also gets a
  tinted background (`background-<intent>-icon-button-square-hover`).
  Active: back to 70% (or the active tint), with the action button's
  press cue. Focus and disabled as on action buttons. Banner close
  buttons pull the ring 2px inward to stay inside the banner border.
- **Behaviour** — native button. Tooltip via `data-tippy-content` or
  `data-tooltip-template-id` (delays in the indicators spec).
- **Accessibility** — `aria-label` is required, since there is no visible
  text; the partial outputs it only when given, and the tooltip doesn't
  replace it.
- **For new code**
  - Always pass `aria-label`, and add a tooltip with the same text.
  - Tooltip delay: `INSTANT_HOVER_DELAY` for toolbars,
    `LONG_HOVER_DELAY` for controls users click repeatedly (existing: both
    are used in `tippyjs.ts`).
- **Don't** — no text next to the icon (that's an action button); no
  `font-size` overrides on the icon; no `.icon-button` without an intent
  class (it has no colour).
- **Known debt** — partials that render an icon button without
  `aria-label` (banner close, input clear) are listed in their specs.
- **Code** — `web/styles/buttons.css` (`.icon-button*`),
  `web/templates/components/icon_button.hbs`.
