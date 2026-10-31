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
     Rules and foundations live in DESIGN.md at the repo root. -->

# Banner

The inline message strip for status, warnings and prompts, placed at the
top of its container (compose box, navbar, settings section, modal).

- **API** — from TypeScript, `banners.ts`: `open(banner, $container)`
  (replaces the container's content), `append(banner, $container)`,
  `open_and_close(banner, $container, ms)`, `close($banner)`. `Banner =
{intent, label, buttons: ActionButton[], close_button, custom_classes?}`;
  `AlertBanner` adds `process` (a `data-process` id used by navbar alerts
  and their container queries). From Handlebars, `{{> components/banner
intent=… label=… buttons=… close_button=…}}` or a partial block for rich
  labels. Renders `.banner.banner-<intent>` with `.banner-content >
.banner-label + .banner-action-buttons` and an optional
  `.banner-close-button` (an icon button of the same intent).
- **Anatomy** — 1px border at 40% alpha, 6px radius, tinted background;
  label in `label-md-regular` (1em / 400 / 1.25 — it inherits the body
  weight) with the same 0.25em vertical padding and 1.25
  line-height as buttons so a one-line banner aligns everything on one
  row without vertical centring. Tokens: `components.banner-<intent>` and
  `border-<intent>-banner`. Links inside use `.banner-link` (blue link
  colour, not the intent colour).
- **Layout** — CSS grid; `.banner-label` has `flex: 1 1 60cqw`, so action
  buttons sit beside the label until the label needs more than 60% of the
  banner width, then wrap under it. Under 25em the buttons stack
  full-width. Navbar banners (`.navbar-alert-banner`) drop the radius and
  side borders, centre their content, and switch to the stacked
  (`navbar-alert-medium-banner`) form below 44em (63em for the
  desktop-notifications process).
- **Buttons inside** — action buttons inherit the banner's `intent` unless
  given their own; they are normally `subtle`. A banner has at most two
  actions; the close button is separate and dismisses without side
  effects.
- **Behaviour**
  - Static: no hover state, no click target on the banner itself.
  - Dismiss: `.banner-close-action` click → `banners.close` removes the
    element (delegated in `banners.initialize`). There is no animation and
    no "undo".
  - Timed: `open_and_close` removes after `remove_after` ms; use it for
    confirmations ("Message sent"), never for errors.
  - Compose errors go through `compose_banner.ts` (`update_or_append_banner`,
    `clear_errors`, `clear_validation_errors`, `clear_warnings`): one
    container per textarea, banners keyed by class so a repeated error
    replaces rather than stacks.
  - Settings and popup banners have their own thin wrappers
    (`settings_banner.ts`, `popup_banners.ts`) over the same API.
- **Intent mapping** — `danger` for errors that block the action,
  `warning` for "you can proceed but…", `info` for system notices,
  `success` for completed actions, `brand` for onboarding / upsell,
  `neutral` for everything else.
- **Don't** — no hand-written `.alert`/`.alert-*` markup (Bootstrap
  legacy); no banner as a modal substitute; no more than one visible
  banner per container unless they are of different processes; no colour
  overrides per banner — pick the intent.
- **Known debt** — older alert markup remains in `alerts.css` and some
  settings pages; the close button rendered by `banner.hbs` has no
  `aria-label` (the `icon_button` partial only outputs one when passed).
- **Accessibility** — text and buttons are ordinary DOM, readable in order;
  the close button is an icon-only `icon_button` without an `aria-label`
  (Known debt). Banners are not
  announced (no live region) — known gap, see DESIGN.md Accessibility.
- **Code** — `web/styles/banners.css`, `web/templates/components/banner.hbs`,
  `web/src/banners.ts`, `web/src/compose_banner.ts`.
