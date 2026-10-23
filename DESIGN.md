# Zulip Web App — DESIGN.md (v0, describes the implementation)

## Overview

Zulip is a team chat app for organizations that live in it for years. The UI
is dense, text-first and utilitarian: a three-pane layout (left sidebar,
message feed, right sidebar) with a persistent compose box. It should feel
calm and precise rather than playful; colour is used sparingly to mark
intent (brand, info, success, warning, danger) and unread state, never as
decoration. Both a light and a dark theme are first-class, and the base font
size is a user setting, so everything scales in `em`.

This file is descriptive: it captures what `web/styles/` implements today so
that agents and reviewers can check new UI against it. Where the
implementation is inconsistent, the file says so instead of inventing a rule.
The normative source for every value is `web/styles/app_variables.css`.

## Colors

Two layers exist in the code:

- **Primitive ramps** — seven hues (`grey`, `purple`, `violet`, `blue`,
  `green`, `orange`, `red`), 21 stops each from `0` (lightest) to `1000`
  (darkest). Two blue-violet families are in use. Action-button `brand` tokens sit on
  the **purple** ramp (`purple-500`, #7f63ee; the solid brand button is
  `hsl(254deg 99% 68%)`, nearest stop `purple-500`). The primary
  call-to-action — the compose send button and the modal confirm button
  (`dialog_submit_button`), via `--color-background-modal-confirm-button`
  in `modal.css` — is `hsl(240deg 80% 66%)`, nearest the **violet** ramp
  (`violet-500`, #6e69f3). Whether these should be one hue is an open
  decision; today brand-intent action buttons use the purple values and
  the send and confirm buttons the violet ones. The ramps are the intended
  foundation; most semantic tokens still carry raw `hsl()` values, and
  consolidating them onto the ramps is an ongoing, per-component effort
  (see Do's and Don'ts).
- **Semantic tokens** — several hundred `--color-*` custom properties.
  Almost all live in the first `:root` block of `app_variables.css`, most
  defined once with `light-dark(light, dark)`; some are theme-invariant
  (e.g. `--color-outline-focus`), and a few are redefined in the
  `%dark-theme` block instead. `modal.css` defines more in its own `:root`
  block (modal surfaces, confirm/cancel/exit buttons), which the compose
  send button also uses. Naming is
  `--color-<property>-<intent>-<attention>-<component>[-<state>]`, e.g.,
  `--color-background-brand-solid-action-button-hover`. For new code,
  component CSS references semantic tokens only and contains no raw
  colour; existing component stylesheets still have many raw `hsl()`
  values (e.g. `modal.css`, `settings.css`, `zulip.css`, the dropdown
  widget shadow in `popovers.css`), which are debt. A few older tokens
  break the naming pattern (`--background-color-active-dropdown-item`,
  `--color-dropdown-item`, `--color-input-pill-close`) and must not be
  copied. `--color-invalid-input-border` and `--invalid-input-box-shadow`
  are the shared invalid-state tokens; reuse them for invalid inputs.

Intents, in the order the code uses them: `neutral`, `brand`, `info`,
`success`, `warning`, `danger`. Each intent has three attention levels for
buttons — `solid` (filled), `subtle` (tinted; in the light theme 12% of
the intent colour, 17% on hover, 22% on active for `neutral`, `brand` and
`info`, a few points more for `success`, `danger` and `warning`), `text` (transparent, 5–10% tint on
hover). Subtle and text variants of the _same_ intent on the _same_ surface
are the norm for secondary actions; solid is reserved for the primary action
of a view or dialog.

Surfaces: app background `hsl(0 0% 94%)` / dark `hsl(0 0% 11%)`; popovers
are white / `hsl(0 0% 17%)`, modals `hsl(0 0% 93%)` / `hsl(0 0% 14%)`,
inputs white / `hsl(225 6% 10%)`; popovers rely on shadow rather than
border in the light theme. Links are blue (`hsl(210 94% 42%)`), not
brand violet, so brand colour stays reserved for actions.

Dark theme: tokens define their own dark value (mostly via `light-dark()`,
a few in `%dark-theme`); there is no global inversion. For new code, add
tokens to the first `:root` block of `app_variables.css` with a
`light-dark()` value, not to `%dark-theme`. `web/styles/dark_theme.css`
still holds legacy overrides that predate `light-dark()`; new code must not
add to it.

## Typography

One family, **Source Sans 3 VF**, with **Source Code Pro** for code. The
base size is the user's setting (`--base-font-size-px`, default 14px), so
all sizes are expressed relative to it (`em`), and line-heights are
unitless.

- **Body** — 1em / 400 / 1.214. Message text, lists, settings.
- **Label** — 1em / 500 / 1.25, +0.02ch tracking. Buttons only.
- **Label, regular** — 1em / 400 / 1.25. Banner labels and text inputs,
  which inherit the body weight. They share the button's padding and
  line-height so a banner label and its action buttons align on one row
  without flex-centring.
- **Modal title** — 1.25em / 650.
- **Sidebar action heading** — 1.0625em / 370, small caps
  (`c2sc`, `smcp`), +0.0469em tracking, shared by the sidebar and inbox
  headings via `--letter-spacing-sidebar-heading`. Other letter-spacing
  and small-caps uses exist in isolated places (e.g. `message_header.css`,
  `message_row.css`, `popovers.css`).

Weights in use: 400 (body, banner labels, inputs), 500 (button labels),
600 (sidebar headings, emphasis), 650 (modal titles), 700/`bold` in many
places. The variable font also makes 300/350/370/450/475/550 appear in
isolated places; do not introduce new intermediate weights.

There is no consolidated type scale: dozens of distinct `font-size` values
exist.
When adding UI, copy the size of the nearest analogous element rather than
choosing a new one. Two containers change the base for everything inside
them: popover menus render at 1.0714em (15px at the default) via the
`popover-menu` tippy theme, unread counters at 0.8571em; dropdown widget
boxes, tooltips and modals stay at the base size.

## Layout

Three-pane desktop layout: left sidebar (`--left-sidebar-width`), message
feed, right sidebar (`--right-sidebar-width`), with a navbar on top and the
compose box docked at the bottom of the feed. Sidebars collapse at the
`md`/`xl` breakpoints (defined in `web/src/css_variables.ts`, used in
`app_variables.css`); the feed is always present.

Spacing has no scale. Components set padding in `em` fractions with the px
equivalent noted in a trailing comment (`0.25em 0.625em; /* 4px 10px at
16px/1em */`). The recurring values are 0.25em, 0.375em, 0.5em, 0.625em,
0.75em and 1em. Grid (`grid-template-areas`) is preferred over flex for
row layouts with fixed columns (sidebar rows, banners, input wrappers).

Everything must survive the base font size changing (12–20px), 1.5×-longer
translated strings, RTL, and widths from 480px to 1920px.

## Elevation & Depth

Flat by default; hierarchy comes from surface tone (94% grey page, white
cards/inputs) and 1px outlines, not shadows. Shadows are reserved for
floating layers:

- **Popover / gear menu** — a six-layer black shadow stack from
  `0 2.78px 4.11px / 6%` up to `0 41px 80px / 13%` (dark theme: 10–20%).
  Use `--box-shadow-popover-menu`; never hand-write a shadow.
- **Overlay (dark theme only)** — `0 0 30px hsl(212 32% 7%)`.
- **Subtle buttons** carry a 0.5px inset shadow at 20% black as a hairline
  border substitute.
- **Focused inputs** get `0 0 5px` of `--color-box-shadow-input-focus`.
- **Dropdown widget boxes** use a three-layer shadow (7/13, 5/8, 2/4 px at
  15/12/10%, darker in the dark theme) written inline in the
  `dropdown-widget` tippy theme; reuse it rather than adding a fourth
  variant.

Many other distinct `box-shadow` values exist in the CSS; the ones above
are the ones to reuse.

## Shapes

4px radius on every interactive element (buttons, inputs, pills, popover
items). 6px on banners and popover containers. Circles (`50%`) for
avatars and presence dots. 3px, 5px and 7px radii appear in legacy code (3px on hotkey hints and
sidebar menu icons, 5px on the tab switcher and tooltips, 7px on the modal
container) and should be normalised to 4/6 when touched. Borders are 1px; outlines on
inputs are 1px inset (`outline-offset: -1px`) so focus does not shift
layout.

## Components

Shared components are Handlebars partials in `web/templates/components/`
or, where there is no partial, the TS entry points in the table below; new
UI uses them rather than hand-written markup. The dev
server shows them at `/devtools/buttons/`, `/devtools/banners/` and
`/devtools/inputs/`.

Each component with a full spec has its own file under
`.claude/rules/components/`, loaded automatically when its CSS, template or
JS is edited, and loaded by `/design-review` when a diff _uses_ it. Specs
cover API, anatomy, size, states, behaviour, accessibility, don'ts, known
debt and code; section order varies, and some files cover several
components.

| Component         | Partial / entry point                                                  | Spec                                            |
| ----------------- | ---------------------------------------------------------------------- | ----------------------------------------------- |
| Action button     | `components/action_button` → `.action-button-<variant>-<intent>`       | `.claude/rules/components/action-button.md`     |
| Icon button       | `components/icon_button` → `.icon-button-<intent>`                     | `.claude/rules/components/icon-button.md`       |
| Banner            | `components/banner`, `banners.ts` → `.banner-<intent>`                 | `.claude/rules/components/banner.md`            |
| Text input        | `components/input_wrapper` → `.input-element-wrapper > .input-element` | `.claude/rules/components/text-input.md`        |
| Input pill        | `input_pill.ts` → `.pill-container > .pill`                            | `.claude/rules/components/input-pill.md`        |
| Dropdown widget   | `dropdown_widget.ts` (no partial)                                      | `.claude/rules/components/dropdown-widget.md`   |
| Popover menu      | `popover_menus.ts`, `.popover-menu-link`                               | `.claude/rules/components/popover-menu.md`      |
| Modal             | `dialog_widget.ts`, Micromodal                                         | `.claude/rules/components/modal.md`             |
| Loading indicator | `loader.hbs`, `.loading_indicator_spinner`                             | `.claude/rules/components/indicators.md`        |
| Unread counter    | `.unread_count.prominent-count\|normal-count\|quiet-count`             | `.claude/rules/components/indicators.md`        |
| Presence circle   | `.user-circle-<status>` (`user_circles.css`)                           | `.claude/rules/components/indicators.md`        |
| Tooltip           | `tippyjs.ts`, un-themed `.tippy-box`                                   | `.claude/rules/components/indicators.md`        |
| Sidebar row       | `.top_left_row`, `.bottom_left_row` (`left_sidebar.css`)               | `.claude/rules/components/sidebar-rows.md`      |
| Settings row      | label + control + dependent input in `settings.css`                    | `.claude/rules/components/settings-controls.md` |
| Checkbox          | `label.checkbox > .rendered-checkbox` (`components.css`)               | `.claude/rules/components/settings-controls.md` |
| Tab switcher      | `components.ts` `toggle()` → `.tab-switcher > .ind-tab`                | `.claude/rules/components/settings-controls.md` |
| Icons             | SVGs in `web/icons/` → `zulip-icon-<file-name>`                        | naming rule only                                |

Until a component has a spec, the rule is: copy the nearest existing use,
and match its states in both themes.

## Floating layers

Popovers, menus, dropdown widgets, tooltips and typeaheads all float
above the page. The sanctioned stack is **tippy.js + Popper** configured
through `popover_menus.ts: default_popover_props`; new floating UI extends
that, it does not add a positioning library or hand-rolled absolute
positioning.

- **Positioning** — Popper `flip` and `preventOverflow` keep the layer in
  the viewport; on scroll and resize the layer _repositions_. It is hidden
  only when its reference element is hidden, leaves the viewport, or (in
  the message feed) is covered by the navbar, compose box or sticky header
  (`destroy-popover-if-reference-hidden` modifier). Never hide a layer on
  raw `scroll` events.
- **Opening** — `trigger: "click"`, `interactive: true`, `hideOnClick:
true`, `appendTo: document.body`, no delay. Tooltips show on hover and
  focus (tippy's default trigger; some tooltips override it to hover
  only) and on a 750ms long press on touch (`touch: ["hold", 750]`), with
  `INSTANT_HOVER_DELAY` (100ms), `LONG_HOVER_DELAY` (750ms),
  `EXTRA_LONG_HOVER_DELAY` (1.5s) or `INTERACTIVE_HOVER_DELAY` (425ms)
  from `tippyjs.ts`.
- **Closing** — click outside, Escape (see Focus & keyboard), selecting an
  item, or the reference disappearing. If opened via keyboard, focus
  returns to the reference on close (`popover_menus.ts`, `opened_via_keyboard`).
- **Layers** — z-index by layer: popovers 106 (inside modals), modals 105,
  typeahead 1051, tooltips above all. Pick the existing value for the
  layer; do not add a new z-index.
- **Content** — never `allowHTML`; render a Handlebars template and pass
  it through `parse_html`. Menus are lists of `.popover-menu-link` rows;
  dropdown widgets (`dropdown_widget.ts`) add a filter input and keyboard
  navigation.
- **Known debt** — the compose/search typeahead is a modified Bootstrap
  component (`bootstrap_typeahead.ts`) with its own Popper instance and
  `refreshPosition` event; it predates the tippy convention.

## Focus & keyboard

- Two focus rings exist:
  - **Component ring** — `.action-button` and `.icon-button`
    (`buttons.css`) show a ring on `:focus-visible` only: 1.5px solid
    black (white in dark theme), offset 0, drawn _outside_ via a negative
    `clip-path` inset so it is never clipped by the parent. Plain `:focus`
    shows nothing. For new code, get focus styling from the partials.
  - **Legacy global ring** — `zulip.css` draws a 2px
    `--color-outline-focus` outline on `a:not(:active):focus`,
    `button:focus-visible`, the rendered checkbox, `i.fa:focus`,
    `i.zulip-icon:focus-visible` and `[role="button"]:focus` (overridden
    to `hsl(0deg 0% 67%)` in `dark_theme.css`). It still applies to
    links, `role=button` elements on plain `:focus` and other controls
    that are not partials; the left sidebar, tab switcher and popovers
    use `--color-outline-focus` too.
- Escape unwinds the topmost layer in this order (`hotkey.ts:
process_escape_key`): view-specific focus (recent, inbox) → feedback
  widget → GIF picker → popovers → modals → overlays → compose. A popover
  open inside a modal closes alone (`modals.ts`). Then, and only if
  nothing was open, Escape navigates home when the user setting
  `web_escape_navigates_to_home_view` is on.
- Modals are Micromodal, opened with `disableFocus: true` (`modals.ts`),
  which only skips focusing the first focusable node. Nothing is focused
  on open unless the caller passes `focus_submit_on_open` to
  `dialog_widget.launch` or focuses an element itself. Micromodal still
  traps Tab inside the modal and returns focus to the previously focused
  element on close.
- For new code, app-wide shortcuts are declared in `hotkey.ts`;
  component-local keys (dropdown widgets, input pills, the tab switcher)
  stay in the component's own `keydown` handler. Many other components
  also have their own `keydown` listeners. Lists (sidebars, menus, typeaheads) support
  arrow keys and Enter; they scroll the focused row into their own
  container with `scroll_util.scroll_element_into_container`, never
  `scrollIntoView` (which would scroll ancestors).
- Buttons are real `<button>` elements; clickable non-buttons need
  `role`, `tabindex="0"` and a key handler — prefer a button.

## Accessibility

Target is WCAG 2.x AA, per `docs/subsystems/accessibility.md` (keyboard
operability, alt text, contrast, appropriate ARIA). The rules below are
mostly implemented, with known gaps noted; a change must not regress them.

- Contrast: text 4.5:1, icons and control boundaries 3:1, in both themes.
  Known debt: light-theme solid `neutral`/`brand`/`info` buttons sit at
  4.25–4.46:1.
- Keyboard: every action reachable by Tab / arrows / Enter; focus rings as
  in Focus & keyboard; Escape unwinds the topmost layer; no focus traps
  other than modals (Micromodal traps Tab). App-wide shortcuts live in
  `hotkey.ts`.
- Names: every icon-only control carries an `aria-label`. The
  `icon_button` partial passes one through only if the caller gives it.
  Known gaps: the banner close button (`banner.hbs`), the input clear
  button (`input_wrapper.hbs`) and the channel/topic sidebar menu icons
  (`stream_sidebar_row.hbs`, `topic_list_item.hbs`) have none. For new
  code, images carry `alt` and `title=` is not used (a few templates
  still have both gaps); tooltips are tippy and do not replace a label.
- Semantics: native `<button>`, `<a>`, `<input>` first; `role=` only when no
  native element fits; decorative icons are `aria-hidden="true"` (the
  partials do this).
- Motion: new animations should honour `prefers-reduced-motion`. Today
  only the `.slider` transition (`app_components.css`) and the
  top-of-feed loading line (`zulip.css`) do; the other keyframe
  animations ignore it.
- Text scaling: the base font size is a user setting; layouts are sized in
  `em` and must hold at 12–20px.

Open questions, not rules yet: only the message list is a live region, so
banners and status messages are not announced; the `high_contrast_mode`
setting has no CSS behind it; colour-only state carriers (presence dots)
are unaudited.

## Feedback

- **Inline, persistent** → banner (above). Errors that block an action
  use `danger` and are placed in the container the action belongs to
  (compose box, modal, settings section), not globally.
- **Inline, transient** → `banners.open_and_close` with `success`.
- **Blocking** → confirmation dialog (`confirm_dialog.ts`) for anything
  destructive or irreversible; the confirm button is a `.modal__button`
  with `dangerous_action_button`, which borrows the solid danger
  action-button background tokens, and the modal's submit goes through `dialog_widget.ts`
  (which handles loading state and error display in the modal footer).
- **In-progress** → `show_button_loading_indicator` on the triggering
  button; no full-screen spinners, no disabled overlays.
- **Validation** → for compose, `compose_banner` error classes; for forms,
  `.invalid` on the input (`--color-invalid-input-border`) plus a message
  below.
- No toasts, no `alert()`, no browser `confirm()`.

## Motion

- The button/input pattern uses two speeds: **0.05s ease-in** when a
  state is entered on hover start / leave, **0.1s ease-out** on
  hover/focus; property list is always explicit (`transition-property:
background-color, clip-path`). Inputs use `0.1s linear` for outline and
  shadow. New components use these. Other speeds exist in older code (e.g.
  `.modal__button` 0.25s, the left sidebar 140ms, `.settings_text_input`
  0.2s).
- For new code, layout does not animate (no `height`/`width`/`top`
  transitions); `stylelint` enforces
  `plugin/no-low-performance-animation-properties`. A few existing
  transitions disable it per line (`components.css`, `progress_bar.css`).
- New animations should honour `prefers-reduced-motion` (see
  Accessibility); `animate.css` is legacy and not to be extended.

## Do's and Don'ts

- Do use the component partials above. Don't write a new `<button>` or
  banner markup by hand, and don't use the portico `.button` class.
- For new code, do reference a `--color-*` semantic token for every colour.
  Don't write `hsl()`/`#hex` outside `app_variables.css` (stylelint already
  rejects hex and `rgb()`; existing raw `hsl()` in component CSS is debt).
  If no token fits, add one to the first `:root` block of
  `app_variables.css` (not `%dark-theme`) with a `light-dark()` value and
  the naming pattern above; don't copy the legacy
  `--background-color-*` or property-less names, and don't start another
  `:root` block in a component stylesheet.
- Do prefer aliasing a primitive ramp stop (`var(--violet-500)`) when adding
  a new semantic token; only fall back to a raw value with a comment saying
  which ramp stop it should become.
- Do size in `em` with the px equivalent in a trailing comment. Don't use
  `px` for anything that should scale with the user's font size.
- Do check both themes for any change that touches colour, and both the
  `/devtools/` showroom pages and the real screen for any change to a
  shared component.
- Do use `light-dark()` in `app_variables.css` for theme values. Don't add
  rules to `dark_theme.css`.
- Do reuse an existing `--box-shadow-*` token and 4px/6px radii. Don't
  invent shadows, radii, z-indexes (pick the layer's existing one) or font
  weights.
- Do check `git grep` for every selector you touch; CSS changes leak across
  pages. Don't scope with bare tag or attribute selectors.
- Do use `!important` only to override Bootstrap or third-party styles, with
  a comment. Over a hundred exist; don't add more for any other reason.
- Don't put `style=""` in templates (the existing colour/font inline styles
  are debt).
- Do keep links blue, and don't introduce a new accent hue. Whether brand
  purple and CTA violet should merge is open (see Colors).
