---
paths:
  - "web/styles/modal.css"
  - "web/templates/dialog_widget.hbs"
  - "web/src/dialog_widget.ts"
  - "web/src/confirm_dialog.ts"
  - "web/src/modals.ts"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Generic rules (tokens, focus, motion, accessibility) are in DESIGN.md at
     the repo root; this file only adds what is specific to modals. -->

# Modal

The dialog used for forms, confirmations and settings sub-flows. One
Micromodal shell (`dialog_widget.hbs`) rendered by `dialog_widget.launch`;
`confirm_dialog.launch` is the same shell preset for yes/no questions,
and the one to use for destructive or irreversible actions (DESIGN.md ›
Feedback).

- **API** — `dialog_widget.launch(conf: DialogWidgetConfig)`
  (`dialog_widget.ts`; the type lists every option). The ones that change
  behaviour most: `modal_title_html | modal_title_text`,
  `modal_content_html`, `on_click` (required unless `hide_footer`),
  `close_on_submit`, `focus_submit_on_open`, `validate_input`, `form_id`,
  `dangerous_action`, `is_compact`, `close_on_overlay_click` (default
  true) and the `on_show` / `on_shown` / `on_hide` / `on_hidden` hooks.
  Helpers: `dialog_widget.close()` and `submit_api_request()` (sends the
  request, shows the spinner, reports errors into `#dialog_error`).
  `confirm_dialog.launch(conf)` presets `close_on_submit: true`,
  `focus_submit_on_open: true` and a "Confirm" label, each overridable.
- **Anatomy** — `.modal__overlay > .modal__container[role=dialog]` with
  `.modal__header` (title, optional subtitle or tab switcher, close icon
  button), `main.modal__content` (`#dialog_error`, then the body) and
  `footer.modal__footer` (optional minor text, exit and submit buttons).
  `is_compact` drops `main.modal__content`, renders `modal_content_html`
  as the subtitle and puts `#dialog_error` in the header. Sizes, paddings
  and the default width are on these classes in `modal.css`; the title
  (`.modal__title`) is the Modal title type style (DESIGN.md ›
  Typography).
- **Footer buttons** — `.modal__button`, not action buttons. The exit
  button is transparent; the submit button uses
  `--color-background-modal-confirm-button` (the violet CTA colour, see
  DESIGN.md › Colors), and `dangerous_action` swaps in the solid danger
  action-button backgrounds. While `submit_api_request` runs, the spinner
  replaces the submit label and the button is disabled.
- **Behaviour**
  - Open: nothing is focused unless `focus_submit_on_open` is set or the
    caller focuses an element (Micromodal is opened with
    `disableFocus: true` in `modals.ts`).
  - Close: Escape, the close button, the exit button, an overlay click
    (unless `close_on_overlay_click: false`) or `dialog_widget.close()`.
    Micromodal traps Tab while open and returns focus to the previously
    focused element on close; a popover open inside a modal closes first
    (DESIGN.md › Focus & keyboard).
  - Submit: with `submit_api_request`, errors render in `#dialog_error`
    and the modal stays open; success closes it unless its
    `close_on_success` argument is false. `close_on_submit` instead closes
    the modal as soon as submit is clicked.
  - Only one modal at a time; opening another closes the current one
    (`modals.ts`).
- **Accessibility** — `role="dialog"`, `aria-modal="true"` and
  `aria-labelledby` on the title come from the shell; the close button has
  `aria-label="Close modal"`, and exit / submit buttons that dismiss get
  `aria-label="Close this dialog window"`.
- **For new code**
  - Open dialogs with `dialog_widget.launch`, or `confirm_dialog.launch`
    for a yes/no question.
  - Confirm destructive actions with `confirm_dialog` and
    `dangerous_action: true`, unless the action is already inside a modal;
    then confirm with a banner in that modal (DESIGN.md › Feedback).
  - Set initial focus: `focus_submit_on_open` for confirmations, or focus
    the first field in `on_shown` for forms.
  - Send the request with `submit_api_request`, so the spinner, disabled
    submit and `#dialog_error` behave like other modals.
  - Change the width only with a `.modal__container` override in the
    modal's own id block (existing: read receipts, topic summary, user
    profile).
- **Don't** — no bespoke dialogs or `.alert`-style overlays.
- **Known debt**
  - The container has a 7px radius (DESIGN.md › Shapes uses 4px and 6px).
  - `.modal__button` has a raw `hsl(0deg 0% 90%)` background, the submit
    text is white with `!important`, and it transitions `transform` over
    0.25s (DESIGN.md › Motion); `.modal__button`s outside the footer also
    scale up on hover and focus.
  - The modal palette lives in its own `:root` block in `modal.css`, which
    portico and billing pages also load; the `--color-exit-button-*`
    tokens there are not used by the dialog widget.
- **Code** — `web/styles/modal.css`, `web/templates/dialog_widget.hbs`,
  `web/src/dialog_widget.ts`, `web/src/confirm_dialog.ts`,
  `web/src/modals.ts`.
