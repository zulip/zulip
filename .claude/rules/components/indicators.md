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
     Generic rules (tokens, focus, motion, accessibility) are in DESIGN.md at
     the repo root; this file only adds what is specific to indicators. -->

# Indicators

Four small, non-interactive units that other components embed: the unread
counter, the presence circle, the tooltip and the loading indicator.

## Unread counter

- **API** — `<span class="unread_count [prominent-count|normal-count|quiet-count]">`;
  `unread_ui.ts` and the sidebar templates set the count and level, and
  `.unread_mention_info` adds an "@" beside it.
- **Anatomy** — sets font-size 0.8571em, so its padding and height are
  sized against that; sizes are on `.unread_count` in `app_components.css`.
- **Levels** — `prominent-count` → `background-unread-counter-prominent`
  with `unread-counter-prominent` text; `normal-count` →
  `background-unread-counter-normal`, `unread-counter-normal` text and
  `--box-shadow-unread-counter-normal`; `quiet-count` → transparent,
  `unread-counter-quiet` text. Muted rows use `unread-counter-muted`. A
  bare `.unread_count` looks like prominent.
- **For new code** — use one of the three levels; the condensed views'
  hover (`--color-background-unread-counter-no-alpha`) is the only
  per-view change.

## Presence circle

- **API** — `<span class="zulip-icon zulip-icon-user-circle-<status>
user-circle-<status>">` with status `active`, `idle`, `offline` or
  `deactivated` (`buddy_data.ts` decides). The container sets the size
  (`--length-user-status-circle-popover-menu` in the user card and
  popover menus, the icon's em size elsewhere).
- **Colours** — `user-circle-<status>`; idle is a gradient that reads as
  a half-filled ring, switching to `--gradient-user-circle-idle-avatar`
  over avatars.
- **Don't** — no other status colours.
- **Known debt** — colour is the only cue for status (DESIGN.md ›
  Accessibility, open questions).

## Tooltip

- **API** — `data-tippy-content` / `data-tooltip-template-id` on the
  trigger, or a delegate in `tippyjs.ts`. Delays: `INSTANT_HOVER_DELAY`,
  `INTERACTIVE_HOVER_DELAY`, `LONG_HOVER_DELAY`, `EXTRA_LONG_HOVER_DELAY`
  (`tippyjs.ts` comments say which elements each is for).
- **Anatomy** — the un-themed `.tippy-box` (`background-tippy-box`, white
  text, base font size; sizes in `tooltips.css`), with optional
  `.tooltip-hotkey-hints` chips at the right.
- **Behaviour** — opens on hover and focus (delegates with `trigger:
"mouseenter"` are hover-only, e.g. `.tippy-zulip-delayed-tooltip`) and
  on a long press on touch (`touch: ["hold", 750]`); hides when the
  reference leaves the viewport.
- **For new code** — add a tooltip to an element with a visible label
  only to show its hotkey.
- **Known debt** — the 5px radius; `.tooltip-hotkey-hint` uses a raw
  `hsl()` for its border and text instead of `--color-hotkey-hint`.

## Loading indicator

- **API** — `loading.make_indicator($container, {text?, width?, height?})`
  renders `loader.hbs` into `.loading_indicator_spinner`, with optional
  `.loading_indicator_text`; `destroy_indicator` removes it. Buttons use
  `show_button_loading_indicator` (action button spec).
- **Anatomy** — an SVG ring rotating once per second; sizes on
  `.loading_indicator_*` in `app_components.css`.
- **Known debt** — the ring fill is a raw `#444` in `loader.hbs`, so it
  doesn't adapt to the dark theme unless the container overrides it
  (`recent_view.css`, `buttons.css`, and raw `hsl()` in `settings.css`
  and `modal.css`); `.loading_indicator_text` uses a one-off weight 300.

- **Code** — `web/styles/app_components.css` (`.unread_count`,
  `.loading_indicator_*`), `web/styles/user_circles.css`,
  `web/styles/tooltips.css`, `web/src/tippyjs.ts`, `web/src/loading.ts`,
  `web/templates/loader.hbs`.
