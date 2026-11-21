---
paths:
  - "web/styles/banners.css"
  - "web/templates/components/banner.hbs"
  - "web/src/banners.ts"
  - "web/src/compose_banner.ts"
  - "web/src/popup_banners.ts"
  - "web/src/settings_banner.ts"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Generic rules (tokens, focus, motion, accessibility) are in DESIGN.md at
     the repo root; this file only adds what is specific to banners. -->

# Banner

The inline message strip for status, warnings and prompts, placed at the
top of its container (compose box, navbar, settings section, modal).

- **API** — from TypeScript, `banners.ts`: `open(banner, $container)`
  (replaces the container's content), `append(banner, $container)`,
  `open_and_close(banner, $container, ms)`, `close($banner)`. `Banner =
{intent, label, buttons: ActionButton[], close_button, custom_classes?}`;
  `AlertBanner` adds `process` (a `data-process` id used by navbar
  alerts). From Handlebars, `{{> components/banner intent=… label=…
buttons=… close_button=…}}` or a partial block for rich labels.
  `settings_banner.ts` and `popup_banners.ts` are thin wrappers over the
  same API.
- **Anatomy** — `.banner.banner-<intent>` > `.banner-content` >
  `.banner-label` + `.banner-action-buttons`, plus an optional
  `.banner-close-button` (an icon button of the same intent). Border,
  radius and padding are on `.banner` in `banners.css`; tokens are
  `background-<intent>-banner`, `text-<intent>-banner` and
  `border-<intent>-banner`. The label uses the Label, regular style with
  the button's vertical padding, so a one-line banner and its buttons
  align without centring. Links inside use `.banner-link` (link blue).
- **Layout** — CSS grid; action buttons sit beside the label until the
  label needs more than 60% of the width, then wrap under it, and stack
  full-width in narrow banners. Navbar banners (`.navbar-alert-banner`)
  drop the radius and side borders, centre their content and switch to
  the stacked form (`navbar-alert-medium-banner`) when narrow.
- **Behaviour**
  - Static: no hover state, no click target on the banner itself.
  - The close button (`.banner-close-action`, delegated in
    `banners.initialize`) removes the banner; no animation, no undo.
  - `open_and_close` removes the banner after the given time.
  - Compose banners go through `compose_banner.ts`
    (`update_or_append_banner`, `clear_errors`, `clear_warnings`), keyed
    by class so a repeated error replaces rather than stacks.
- **Accessibility** — text and buttons are ordinary DOM, read in order.
  Banners aren't announced (DESIGN.md › Accessibility, open questions).
- **For new code**
  - Intent: `danger` for errors that block the action, `warning` for
    "you can proceed, but…", `info` for system notices, `success` for
    completed actions, `brand` for onboarding and upsell, `neutral`
    otherwise.
  - Action buttons inherit the banner's intent and are `subtle`; at most
    two, with the close button separate and free of side effects.
  - `open_and_close` only for confirmations ("Message sent"), never for
    errors.
- **Don't** — no hand-written `.alert` / `.alert-*` markup; no banner in
  place of a modal; no more than one visible banner per container unless
  they belong to different processes.
- **Known debt**
  - Older alert markup remains in `alerts.css` and some settings pages.
  - The banners inside modals in `web/templates/modal_banner/` use the
    legacy `modal_banner` partial (`.main-view-banner`), not this one.
  - The close button rendered by `banner.hbs` has no `aria-label`.
- **Code** — `web/styles/banners.css`, `web/templates/components/banner.hbs`,
  `web/src/banners.ts`, `web/src/compose_banner.ts`.
