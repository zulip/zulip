---
paths:
  - "web/styles/user_circles.css"
  - "web/styles/tooltips.css"
  - "web/src/tippyjs.ts"
  - "web/src/loading.ts"
  - "web/templates/loader.hbs"
  - "web/src/unread_ui.ts"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Rules and foundations live in DESIGN.md at the repo root. -->

# Indicators

Four small, non-interactive units that other components embed: the unread
counter, the presence circle, the tooltip and the loading indicator.

## Unread counter

- **API** — `<span class="unread_count [prominent-count|normal-count|quiet-count]">`
  (`unread_ui.ts` / the sidebar templates set the count and the attention
  class; `.unread_mention_info` adds an "@" next to it).
- **Anatomy** — font-size 0.8571em (12px at the 14px base), height and
  line-height 1.3333em of that (16px), padding 0 4px, 4px radius, weight
  normal, floated right in sidebar rows.
- **Levels** — `prominent-count` → `background-unread-counter-prominent`
  with `unread-counter-prominent` (white) text; `normal-count` →
  `background-unread-counter-normal`, `unread-counter-normal` text and a
  1px inset shadow (`--box-shadow-unread-counter-normal`); `quiet-count` →
  transparent, `unread-counter-quiet` text at weight 475. Muted rows use
  `unread-counter-muted`. The bare `.unread_count` (legacy) equals
  prominent.
- **Don't** — no counters outside the three levels; no counter colour per
  view (the condensed views only remove the alpha on hover via
  `--color-background-unread-counter-no-alpha`).

## Presence circle

- **API** — `<span class="zulip-icon zulip-icon-user-circle-<status>
user-circle-<status>">` with status `active`, `idle`, `offline`,
  `deactivated` (`buddy_data.ts` decides the status). Sizes are set by the
  container: 8px in the user card and popover menus
  (`--length-user-status-circle-popover-menu`), the icon's em size in the
  buddy list and compose recipient rows.
- **Colours** — `user-circle-active`, `user-circle-idle` (rendered as a
  gradient over the ring so it reads as a half-filled circle; the SVG
  repeats the same gradient), `user-circle-offline`,
  `user-circle-deactivated`. Over avatars the idle gradient switches to
  `--gradient-user-circle-idle-avatar` so the avatar does not bleed
  through.
- **Don't** — no other status colours; no text-only status without the
  circle (the colour is the only cue today — known accessibility gap).

## Tooltip

- **API** — `data-tippy-content` / `data-tooltip-template-id` on the
  trigger, or `tippy(...)` in `tippyjs.ts`; delays `INSTANT_HOVER_DELAY`
  (100ms), `INTERACTIVE_HOVER_DELAY` (425ms), `LONG_HOVER_DELAY` (750ms),
  `EXTRA_LONG_HOVER_DELAY` (1.5s); never a replacement for a label.
- **Anatomy** — the un-themed `.tippy-box`: `background-tippy-box`, 5px
  radius, min-height 1.7857em (25px), content padding 5px 10px, base font
  size, line-height 1.4286em (20px), white text, arrow scaled to 0.75.
  Optional `.tooltip-hotkey-hints` at the right (10px left margin, 4px
  gap) with `.tooltip-hotkey-hint` chips: 1px border and text in
  `hsl(225deg 100% 84%)` (raw; `--color-hotkey-hint` is the token it
  should use), 3px radius, padding 0 5px.
- **Behaviour** — shown on hover and, with tippy's default trigger, on
  focus (delegates that set `trigger: "mouseenter"` are hover-only, e.g.
  `.tippy-zulip-delayed-tooltip`); on touch devices shown on a 750ms long
  press (`touch: ["hold", 750]` in `setDefaultProps`); hides when the
  reference leaves the viewport (`data-reference-hidden`); text is
  left-aligned when it wraps.
- **Don't** — no HTML from user content; no tooltips on elements that
  already have visible labels unless they add the hotkey; no `title=`.

## Loading indicator

- **API** — `loading.make_indicator($container, {text?, width?, height?})`
  renders `loader.hbs` (an SVG ring, `.uil-ring`) into
  `.loading_indicator_spinner` plus optional `.loading_indicator_text`;
  `destroy_indicator` removes it. Buttons use
  `show_button_loading_indicator` (action button spec) instead.
- **Anatomy** — spinner 2.7143em square (38px), rotating once per second;
  text margin-left 5px, 1.2em, weight 300, line-height 38px.
- **Known debt** — the ring fill is a raw `#444` in `loader.hbs`, so it
  does not adapt to the dark theme unless the container overrides the
  path fill; overrides are per container (`--color-zulip-logo-loading` in
  `recent_view.css`, `currentcolor` for button spinners in `buttons.css`,
  raw `hsl()` in `settings.css` and `modal.css`).
  `.loading_indicator_text` uses a one-off weight 300.
- **Code** — `web/styles/app_components.css` (`.unread_count`,
  `.loading_indicator_*`), `web/styles/user_circles.css`,
  `web/styles/tooltips.css`, `web/src/tippyjs.ts`, `web/src/loading.ts`,
  `web/templates/loader.hbs`.
