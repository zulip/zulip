---
paths:
  - "web/styles/buttons.css"
  - "web/templates/components/action_button.hbs"
  - "web/src/buttons.ts"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Rules and foundations live in DESIGN.md at the repo root. -->

# Action button

The standard text button. For new code, every button with a label should be
one; existing exceptions are under Known debt.

- **API** — `{{> components/action_button variant=… intent=… label=… icon=…
id=… custom_classes=… disabled=… aria-label=… data-tippy-content=…}}`
  renders `<button class="action-button action-button-<variant>-<intent>">`
  with an optional `.zulip-icon` and `.action-button-label`. From TypeScript,
  render the same partial (`render_action_button`) — never build the markup
  by hand. Types: `ActionButton`, `ActionButtonVariant` in `web/src/buttons.ts`;
  `ComponentIntent` in `web/src/types.ts`.
- **Axes** — `variant` ∈ `solid` | `subtle` | `text` (how much attention);
  `intent` ∈ `neutral` | `brand` | `info` | `success` | `warning` | `danger`
  (what it means). 18 combinations, all styled in `web/styles/buttons.css`.
  Most template uses are `subtle`, and most are `brand` or `neutral`.
  Rule of thumb: one `solid` per view or dialog (the primary action);
  everything else `subtle`; `text` for inline, low-emphasis actions.
- **Anatomy** — optional leading icon (`zulip-icon-<name>`, 1em, gap
  0.75ch), label (`.action-button-label`, max 32ch, ellipsis). Label or
  icon may be omitted, not both. Tokens: `components.action-button-<variant>-<intent>`.
- **Size** — one size: `label-md` (1em / 500 / 1.25 line-height), padding
  0.25em 0.625em, radius 4px → 24.5px tall at the default 14px base (28px
  at 16px). There is no small/large; do not add size classes. The only
  other button size in the app is the legacy modal footer button
  (`.modal__button`: 1em / 1.15, padding 8px 16px → 32px), used for the
  confirm and cancel buttons of dialogs — see known debt.
- **States**
  - rest → tokens above; `subtle` adds a 0.5px inset hairline
    (`inner-shadow-action-button`).
  - hover / focus-visible → `background-…-hover`; transition 0.1s ease-out
    (0.05s ease-in on leave).
  - active → `background-…-active` and the button clips 1px inward
    (`clip-path: inset(1px round 4px)`) as a press cue.
  - focus-visible → 1.5px solid `outline-button-focus` (black / white),
    offset 0, `!important` to beat the global `button:focus` rule.
    Plain `:focus` shows nothing.
  - disabled → `opacity: 0.5`, `pointer-events: none`, cursor default.
    Disabled buttons cannot show a tooltip; wrap them (see
    `tippyjs.ts: .add-users-button-wrapper`) if the reason must be shown.
  - loading → `buttons.ts: show_button_loading_indicator($button)` hides
    icon and label (visibility, so width is kept) and overlays a spinner in
    `currentcolor`; `hide_button_loading_indicator` restores and
    re-enables. Add `button-hide-loading-indicator-on-hover` when the label
    should reappear on hover (e.g., a "Retry" that is currently retrying).
- **Behaviour**
  - Native `<button type="button">`; Enter/Space activate it; no custom key
    handling. `tabindex="0"` is set by the partial.
  - Changing look at runtime: `buttons.ts: modify_action_button_style($button,
{variant, intent})` and `modify_button_icon`. Never `addClass`/`removeClass`
    the variant/intent classes directly — the class must always be the full
    `action-button-<variant>-<intent>` pair.
  - Disable while an async action is in flight, then show loading; do not
    change the label to "Saving…".
  - Destructive actions use `intent="danger"` and go through a confirmation
    dialog (`confirm_dialog.ts`), never a bare danger button.
- **Don't** — no `.button` (the portico and email button class) in the
  web app; no inline `style`; no px padding; no
  `font-weight` overrides; no button inside a button (use an icon button
  beside it).
- **Known debt** — the app's primary call to action is not an action
  button: the compose send button (`#compose-send-button`, 74×28, icon only)
  and the modal confirm button (`.dialog_submit_button`) share
  `--color-background-modal-confirm-button` from `modal.css`, a violet
  (`hsl(240deg 80% 66%)`) distinct from the brand purple; the modal cancel
  button is a neutral text button at the modal size. `.action-button` without a variant class renders as
  subtle-neutral minus the hairline, which hides mistakes (see
  `user_group_edit.ts`, which toggles to a non-existent
  `action-button-neutral`). Modal footer buttons (`dialog_submit_button`)
  and many generic `class="…button…"` usages predate this component.
  Light-theme solid `neutral`/`brand`/`info` are at 4.25–4.46:1 contrast,
  below AA.
- **Accessibility** — native `<button>`, so name comes from the label; icon-only
  use requires `aria-label` (the partial outputs it only when given). Icon
  is `aria-hidden`.
  Focus ring per Focus & keyboard; disabled uses the `disabled` attribute, not
  a class, so assistive tech sees it.
- **Code** — `web/styles/buttons.css` (`.action-button*`),
  `web/templates/components/action_button.hbs`, `web/src/buttons.ts`;
  reference render: `/devtools/buttons/`.
