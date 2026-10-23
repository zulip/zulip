---
paths:
  - "web/styles/buttons.css"
  - "web/templates/components/action_button.hbs"
  - "web/src/buttons.ts"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Generic rules (tokens, focus, motion, accessibility) are in DESIGN.md at
     the repo root; this file only adds what is specific to action buttons. -->

# Action button

The standard text button. For new code, every button with a label is one;
existing exceptions are under Known debt.

- **API** — `{{> components/action_button variant=… intent=… label=… icon=…
id=… custom_classes=… disabled=… aria-label=… data-tippy-content=…}}`
  renders `<button class="action-button action-button-<variant>-<intent>">`
  with an optional `.zulip-icon` and `.action-button-label`. From
  TypeScript, render the same partial (`render_action_button`). Types:
  `ActionButton`, `ActionButtonVariant` in `web/src/buttons.ts`;
  `ComponentIntent` in `web/src/types.ts`.
- **Axes** — `variant` ∈ `solid` | `subtle` | `text` and `intent` ∈
  `neutral` | `brand` | `info` | `success` | `warning` | `danger`
  (DESIGN.md › Colors), every combination styled in `buttons.css`. Most
  uses are `subtle` `brand` or `neutral`; `text` is for inline,
  low-emphasis actions. Subtle backgrounds are a percentage of the intent
  colour that steps up on hover and active (the steps are slightly larger
  for `success`, `warning` and `danger`).
- **Anatomy** — optional leading icon, then the label
  (`.action-button-label`, capped width, ellipsis). Label or icon may be
  omitted, not both. Type is the Label style (DESIGN.md › Typography);
  padding, gap and radius are on `.action-button` in `buttons.css`.
  `subtle` adds an inset hairline (`--color-inner-shadow-action-button`).
- **States** — hover and focus-visible share `background-…-hover`;
  active uses `background-…-active` and clips the button 1px inward as a
  press cue. Focus is the component ring (DESIGN.md › Focus & keyboard).
  Disabled: `opacity: 0.5`, `pointer-events: none`, default cursor, so
  a disabled button can't show a tooltip; wrap it (`tippyjs.ts`,
  `.add-users-button-wrapper`) if the reason must be shown.
- **Behaviour**
  - Native `<button type="button">`; no custom key handling.
  - Loading: `buttons.ts` `show_button_loading_indicator($button)` hides
    icon and label (keeping the width) and overlays a spinner in
    `currentcolor`; `hide_button_loading_indicator` restores and
    re-enables it. `button-hide-loading-indicator-on-hover` brings the
    label back on hover.
  - Changing look at runtime: `modify_action_button_style($button,
{variant, intent})` and `modify_button_icon`.
- **Accessibility** — the name comes from the label; icon-only use needs
  `aria-label` (the partial outputs it only when given). Disabled uses the
  `disabled` attribute, not a class, so assistive tech sees it.
- **For new code**
  - One `solid` button per view or dialog, for the primary action;
    secondary actions `subtle` (existing: the settings "Save changes" /
    "Discard" pair).
  - Change variant or intent only through `modify_action_button_style`,
    so the class is always the full `action-button-<variant>-<intent>`
    pair.
  - While an async action runs, show the loading indicator rather than
    changing the label to "Saving…".
- **Don't** — no button inside a button (put an icon button beside it).
- **Known debt**
  - The primary call to action isn't an action button: the compose send
    button (`#compose-send-button`) and the modal confirm button use
    `--color-background-modal-confirm-button` (DESIGN.md › Colors); modal
    footer buttons are `.modal__button` (modal spec).
  - `.action-button` without a variant class renders as subtle neutral
    without the hairline, which hides mistakes (`user_group_edit.ts`
    toggles a non-existent `action-button-neutral`).
  - Many generic `class="…button…"` uses predate this component.
  - In the light theme, solid `neutral`, `brand` and `info` text is
    below 4.5:1 contrast.
- **Code** — `web/styles/buttons.css` (`.action-button*`),
  `web/templates/components/action_button.hbs`, `web/src/buttons.ts`;
  reference render `/devtools/buttons/`.
