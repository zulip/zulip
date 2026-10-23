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
     Rules and foundations live in DESIGN.md at the repo root. -->

# Modal

The dialog used for forms, confirmations and settings sub-flows. One
Micromodal shell (`dialog_widget.hbs`) rendered by `dialog_widget.launch`;
`confirm_dialog.launch` is the same shell preset for yes/no questions.

- **API** — `dialog_widget.launch(conf: DialogWidgetConfig)`
  (`dialog_widget.ts`). Main fields: `modal_title_html? | modal_title_text?`,
  `modal_content_html` (required), `modal_subtitle_html?`, `on_click?`
  (required unless `hide_footer`), `modal_submit_button_text?` (default
  "Save changes"), `modal_exit_button_text?` (default "Cancel"),
  `close_on_submit?`, `focus_submit_on_open?`, `validate_input?`,
  `form_id?`, `loading_spinner?`, `update_submit_disabled_state_on_change?`,
  `dangerous_action?`, `is_compact?`, `has_tab_switcher?`, `hide_footer?`,
  `single_footer_button?`, `footer_minor_text?`, `help_link?`, `id?`,
  `close_on_overlay_click?` (default true), `always_visible_scrollbar?`,
  `post_render?`, `on_show?`, `on_shown?`, `on_hide?`, `on_hidden?`. It
  returns the modal id; `dialog_widget.close()`, `show_dialog_spinner()`,
  `hide_dialog_spinner()`, `submit_api_request()` (does the request,
  shows the spinner, reports errors into `#dialog_error`).
  `confirm_dialog.launch(conf)` is a preset over it: `close_on_submit: true`,
  `focus_submit_on_open: true` and "Confirm" as the submit label, each
  overridable by `conf`. Markup:
  `.micromodal > .modal__overlay > .modal__container[role=dialog][aria-modal]`
  with `.modal__header` (`.modal__header-content` > `h1.modal__title` +
  optional `.modal__subtitle`, optional `.modal__tab-switcher-container`,
  `.modal__close` icon button), `main.modal__content` (simplebar, holds
  `#dialog_error` then the body) and `footer.modal__footer`
  (`.dialog-widget-footer-minor-text`, `.modal__button.dialog_exit_button`,
  `.modal__button.dialog_submit_button` with `.modal__spinner`).
  `is_compact` drops `main.modal__content`, renders `modal_content_html` as
  the subtitle and puts `#dialog_error` in the header.
- **Anatomy** — overlay `background-modal-overlay` (25% black), z-index
  105, centred. Container `background-modal`, 1px `border-modal`,
  **7px radius**, width 37.1428em (520px at 14px), max 96% high /
  `calc(100% - 32px)` wide, `box-sizing: border-box`. Header
  `background-modal-bar` on a grid: 1em side columns, first row 2.75em
  (title + close button), `.modal__header-content` padding 0.625em 0,
  bottom border `border-modal-bar` when there is content. Title
  `heading-modal` (1.25em / 650 / 1.2) in `modal-heading-text`; subtitle
  margin-top 0.875em, line-height 1.25; close = neutral icon button pulled
  right by its own padding. Content padding 0.875em 1em. Footer
  `background-modal-bar`, padding 0.75em 1em, top border `border-modal-bar`
  (0.5em 1em 0.75em and no border when there is no content), buttons
  right-aligned, minor text italic and `smaller` at the left.
- **Buttons** — `.modal__button`: base font size, padding 8px 16px, 4px
  radius, no border, line-height 1.15 (32px tall at 14px). Exit:
  transparent, `text-modal-cancel-button`, hover / active
  `background-modal-cancel-button-hover` / `-active`. Submit: 12px left
  margin, white text, `background-modal-confirm-button` (+ `-hover`,
  `-active`); `dangerous_action` swaps in the danger solid action-button
  backgrounds. `:disabled` → 50% opacity. The spinner replaces the submit
  label while a request runs. Other `.modal__button`s (in bodies) scale
  1.05 on hover / focus — legacy.
- **Behaviour** (`dialog_widget.ts`, `modals.ts`)
  - Open: Micromodal `show` with `disableFocus: true`, so nothing gets
    initial focus unless `focus_submit_on_open` is set (the submit button
    is focused in `on_show`) or the caller focuses something itself
    (e.g. in `on_shown`). Overlay fades in 120ms, container likewise
    (`mmfadeIn`); out in 75ms.
  - Close: Escape, the close icon button, the exit button, overlay click
    (unless `close_on_overlay_click: false`) or `dialog_widget.close()`.
    Micromodal returns focus to the element that was focused when the
    modal opened. A popover open inside a modal closes first (see
    DESIGN.md Focus & keyboard).
  - Submit: `on_click` runs; with `submit_api_request` the button shows
    the spinner and is disabled until the response; errors render in
    `#dialog_error` inside the content (header for compact modals) and the
    modal stays open. Success closes it.
  - Only one modal at a time; opening another closes the current one
    (`modals.ts`).
- **Accessibility** — `role="dialog"`, `aria-modal="true"`,
  `aria-labelledby` pointing at the title; close button `aria-label="Close
modal"`; exit / submit buttons get `aria-label="Close this dialog window"`
  when they dismiss. Micromodal traps Tab inside the modal (`disableFocus`
  only skips focusing its first focusable node) and restores focus on
  close. There is no initial focus by default.
- **For new code**
  - Open dialogs with `dialog_widget.launch`, or `confirm_dialog.launch`
    for a yes/no question.
  - Confirm destructive actions with `confirm_dialog` and
    `dangerous_action: true`.
  - Set initial focus: `focus_submit_on_open` for confirmations, or focus
    the first field in `on_shown` for forms.
  - Send the request with `submit_api_request`, so the spinner, disabled
    submit and `#dialog_error` behave like other modals.
- **Don't** — no bespoke dialogs or `.alert`-style overlays; no per-modal
  widths except through a `.modal__container` override in its own id block
  (existing: read receipts 360px, topic summary 45em, user profile with a
  fixed height); no `title=`; no colour or radius overrides inside modals.
- **Known debt** — 7px radius (everything else is 4/6); `.modal__button`
  background `hsl(0deg 0% 90%)` and the submit's `!important` white text
  are raw; the modal palette lives in `modal.css` `:root` (shared with
  portico and billing) and the legacy `--color-exit-button-*` tokens are
  unused by the dialog widget; `.modal__button` hover scale only applies
  to non-footer buttons.
- **Code** — `web/styles/modal.css`, `web/templates/dialog_widget.hbs`,
  `web/src/dialog_widget.ts`, `web/src/confirm_dialog.ts`, `web/src/modals.ts`.
