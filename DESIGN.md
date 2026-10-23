# Zulip Web App — DESIGN.md (v0, describes the implementation)

## Overview

Zulip is a team chat app for organizations that live in it for years. The UI
is dense, text-first and utilitarian: a three-pane layout (left sidebar,
message feed, right sidebar) with a persistent compose box. It should feel
calm and precise rather than playful; colour is used sparingly to mark
intent (brand, info, success, warning, danger) and unread state, never as
decoration. Both a light and a dark theme are first-class, and the base font
size is a user setting, so everything scales in `em`.

This file describes what `web/styles/` implements today so that agents and
reviewers can check new UI against it. Where the implementation is
inconsistent, it says so and lists the exception as known debt; where one
existing pattern should be followed from now on, the rule is marked "for new
code". Open design questions are named as open, not decided here.
The normative source for every value is `web/styles/app_variables.css`.

## Colors

Two layers exist in the code:

- **Primitive ramps** — seven hues (`grey`, `purple`, `violet`, `blue`,
  `green`, `orange`, `red`), 21 stops each from `0` (lightest) to `1000`
  (darkest). Two blue-violet families are in use: `brand` action buttons
  sit nearest **purple** (`purple-500`), and the primary call-to-action
  buttons (compose send, modal confirm) nearest **violet** (`violet-500`).
  Whether these should be one hue is an open decision. The ramps are the intended
  foundation; most semantic tokens still carry raw `hsl()` values, and
  consolidating them onto the ramps is an ongoing, per-component effort
  (see Do's and Don'ts).
- **Semantic tokens** — several hundred `--color-*` custom properties.
  Almost all live in the first `:root` block of `app_variables.css`, most
  defined once with `light-dark(light, dark)`; some are theme-invariant
  (e.g. `--color-outline-focus`), and a few are redefined in the
  `%dark-theme` block instead. `modal.css` has its own `:root` block (see
  the modal spec). Naming is
  `--color-<property>-<intent>-<attention>-<component>[-<state>]`, e.g.,
  `--color-background-brand-solid-action-button-hover`. For new code,
  component CSS references semantic tokens only and contains no raw
  colour; existing component stylesheets still have many raw `hsl()`
  values (e.g. `modal.css`, `settings.css`, `zulip.css`), which are debt.
  A few older tokens break the naming pattern (the specs name them) and
  must not be copied. `--color-invalid-input-border` and `--invalid-input-box-shadow`
  are the shared invalid-state tokens; reuse them for invalid inputs.

Intents, in the order the code uses them: `neutral`, `brand`, `info`,
`success`, `warning`, `danger`. Each intent has three attention levels for
buttons — `solid` (filled), `subtle` (tinted), `text` (transparent,
tinted on hover). Subtle and text variants of the _same_ intent on the _same_ surface
are the norm for secondary actions; solid is reserved for the primary action
of a view or dialog.

Surfaces (app background, popovers, modals, inputs) each have their own
background token, named in the component's spec. Links are blue, not
brand violet, so brand colour stays reserved for actions.

List rows that highlight (popover menu items, dropdown widget rows) use a
light neutral tint on hover and a slightly stronger one on active, from
their component's tokens; new lists reuse those tokens rather than
picking a new tint.

Dark theme: tokens define their own dark value (mostly via `light-dark()`,
a few in `%dark-theme`); there is no global inversion. For new code, add
tokens to the first `:root` block of `app_variables.css` with a
`light-dark()` value, not to `%dark-theme`. `web/styles/dark_theme.css`
still holds legacy overrides that predate `light-dark()`; new code must not
add to it.

The message feed and compose box have no spec yet; their colour debt is
listed here:

- `--color-text-sender-name` is defined only in `%dark-theme`, so in the
  light theme sender names inherit the body colour.
- Raw greys: `.message-reminders`, `.y-animated-dot` and
  `.message_edit_countdown_timer` (and its `.expired` red) in
  `message_row.css`; the `textarea.new_message_textarea` `scrollbar-color`
  and the `.message_header` background in `compose.css`.
- `#compose-content` has a `box-shadow` with no offset, blur or spread, so
  it draws nothing.
- `--color-compose-recipient-box-text-color` and
  `--color-message-reaction-button-background` are set to `inherit`
  rather than a colour.

## Typography

One family, **Source Sans 3 VF**, with **Source Code Pro** for code. The
base size is the user's setting (`--base-font-size-px`, default 14px), so
all sizes are expressed relative to it (`em`), and line-heights are
unitless.

- **Body** — 1em / 400 / 1.214. Message text, lists, settings.
- **Label** — 1em / 500 / 1.25, +0.02ch tracking. Buttons only.
- **Label, regular** — 1em / 400 / 1.25. Banner labels and text inputs,
  which inherit the body weight.
- **Modal title** — `.modal__title`, 1.25em / 650 / 1.2.
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
choosing a new one. Some containers change the `em` base for everything
inside them (popover menus, unread counters); check the container's spec
before sizing something inside it.

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

Text that can grow (user content, translations) has a defined overflow:
an ellipsis on one line (action button labels, pill values, tabs, channel
names) or a line clamp (topic names in the left sidebar).

Everything must survive the base font size changing (12–20px), 1.5×-longer
translated strings, RTL, and widths from 480px to 1920px.

## Elevation & Depth

Flat by default; hierarchy comes from surface tone (94% grey page, white
cards/inputs) and 1px outlines, not shadows. Shadows are reserved for
floating layers:

- **Popover menus** — `--box-shadow-popover-menu` (`--box-shadow-gear-menu`
  for the gear menu).
- **Overlay (dark theme only)** — `0 0 30px hsl(212 32% 7%)`.
- Component shadows (the subtle button hairline, the input focus glow, the
  dropdown widget box) are described in their specs.

Many other distinct `box-shadow` values exist in the CSS. Reuse an
existing `--box-shadow-*` token or a component's shadow; never hand-write
a new one.

## Shapes

4px radius on every interactive element (buttons, inputs, pills, popover
items). 6px on banners and popover containers. Circles (`50%`) for
avatars and presence dots. Other radii appear in legacy code and should
be normalised to 4/6 when touched; the specs list them for their
components, and in the message feed and compose box they are: 7px on the
recipient bar's top corners and the last message row's bottom corners
(`message_header.css`), 5px on `.recipient_row`, 9px on the top corners
of `#compose-content`, 3px on the compose textarea and formatting row,
2px on `.compose-new-recipient-button`, 8px on `#compose_close` and 21px
on reaction pills (`reactions.css`).
Borders are 1px. State changes don't shift layout: inputs draw their
border as an inset outline, and focus rings are outlines or shadows, not
borders.

## Components

Shared components are Handlebars partials in `web/templates/components/`
or, where there is no partial, the TS entry points in the table below; new
UI uses them rather than hand-written markup. The dev
server shows them at `/devtools/buttons/`, `/devtools/banners/` and
`/devtools/inputs/`.

Each component with a full spec has its own file under
`.claude/rules/components/`, loaded automatically when its CSS, template or
JS is edited, and loaded by `/design-review` when a diff _uses_ it. A spec
adds only what is specific to its component (API, anatomy, behaviour,
accessibility, rules for new code, don'ts, known debt and code) and refers
back to this file for the generic rules; some files cover several
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

Across components:

- **One size** — each component has one size (the modal footer button is
  the only second button size). For new code, don't add size classes.
- **Disabled** — treatments differ per component (opacity, cursor,
  whether pointer events are kept); each spec states its own. Whether
  they should be unified is an open decision. For new code, use the
  component's existing disabled class or attribute; don't add a new
  treatment.
- **Hotkey hints** — two parallel chips exist, `.tooltip-hotkey-hint` and
  `.popover-menu-hotkey-hint` (both decorative, both with the legacy 3px
  radius). For new code, use the one that belongs to the container.

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
true`, `appendTo: document.body`, no delay. Tooltips open on hover and
  focus with their own delays (see the indicators spec).
- **Closing** — click outside, Escape (see Focus & keyboard), selecting an
  item, or the reference disappearing. Popover menus return focus to the
  reference when they were opened via keyboard (`opened_via_keyboard`);
  dropdown widgets always do (`focus_target_on_hidden`).
- **Layers** — z-index by layer: popovers 106 (inside modals), modals 105,
  typeahead 1051, tooltips above all. Pick the existing value for the
  layer; do not add a new z-index.
- **Content** — never `allowHTML`; render a Handlebars template and pass
  it through `parse_html`.
- **Known debt** — the compose/search typeahead is a modified Bootstrap
  component (`bootstrap_typeahead.ts`) with its own Popper instance and
  `refreshPosition` event; it predates the tippy convention.

## Focus & keyboard

- Two focus rings exist:
  - **Component ring** — `.action-button` and `.icon-button`
    (`buttons.css`) show a ring on `:focus-visible` only: a 1.5px solid
    outline in `--color-outline-button-focus` (black, white in dark
    theme), offset 0, marked `!important` to beat the legacy rule; the
    button's own `clip-path` is widened by the ring's width so the ring
    shows. Plain `:focus` shows nothing. For new code, get focus styling
    from the partials.
  - **Legacy global ring** — `zulip.css` draws a 2px
    `--color-outline-focus` outline on `a:not(:active):focus`,
    `button:focus-visible`, the rendered checkbox, `i.fa:focus`,
    `i.zulip-icon:focus-visible` and `[role="button"]:focus` (overridden
    to `hsl(0deg 0% 67%)` in `dark_theme.css`). It still applies to
    links, `role=button` elements on plain `:focus` and other controls
    that are not partials; the left sidebar, tab switcher and popovers
    use `--color-outline-focus` too.
- Rows and items inside a scrolling or clipped container draw the ring
  inside themselves, with a negative `outline-offset` or an inset
  `box-shadow`, so the container can't clip it (popover menu items,
  sidebar rows, tab switcher tabs). Inputs show focus with their outline
  and glow instead of a ring, and input pills with a thin inset ring on
  plain `:focus` (see their specs).
- Controls that appear on row hover also appear when the row has focus,
  and are shown by default on touch screens (`@media (hover: none)`), as
  the left sidebar's row menus do. For new code, follow that pattern; the
  dropdown widget's row buttons don't yet show on touch.
- Escape unwinds the topmost layer in this order (`hotkey.ts:
process_escape_key`): view-specific focus (recent, inbox) → feedback
  widget → GIF picker → popovers → modals → overlays → compose. A popover
  open inside a modal closes alone (`modals.ts`). Then, and only if
  nothing was open, Escape navigates home when the user setting
  `web_escape_navigates_to_home_view` is on.
- Modals are the only focus trap: they keep Tab inside while open and
  return focus to the previously focused element on close. Initial focus
  is up to the caller (see the modal spec).
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
  Known debt: some light-theme solid action buttons fall short (see the
  action button spec).
- Keyboard: every action reachable by Tab / arrows / Enter; focus rings as
  in Focus & keyboard; Escape unwinds the topmost layer; no focus traps
  other than modals (Micromodal traps Tab). App-wide shortcuts live in
  `hotkey.ts`.
- Names: every icon-only control carries an `aria-label`; the specs list
  the known gaps. Every form field has a visible `<label>` (with `for` or
  wrapping the control) or an `aria-label`; `placeholder` is not a label.
  For new code, images carry `alt` and `title=` is not used (a few
  templates still have both gaps); tooltips are tippy and do not replace
  a label.
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

- **Inline, persistent** → banner (`banner.md`). Errors that block an action
  use `danger` and are placed in the container the action belongs to
  (compose box, modal, settings section), not globally.
- **Inline, transient** → `banners.open_and_close` with `success`.
- **Blocking** → confirmation dialog (`confirm_dialog.ts`) for anything
  destructive or irreversible, with errors shown inside the modal (see
  the modal spec).
- **Inside a modal** → modals don't stack (opening one closes the current
  one, `modals.ts`), so a warning or confirmation about an action in a
  modal is a banner inside that modal, not a second dialog. Existing
  examples are the move-topic and invite modals
  (`web/templates/modal_banner/`). For new code, use the `banner`
  component partial there.
- **In-progress** → `show_button_loading_indicator` on the triggering
  button; no full-screen spinners, no disabled overlays.
- **Validation** → for compose, `compose_banner` error classes; for forms,
  `.invalid` on the input (`--color-invalid-input-border`) plus a message
  below.
- No toasts, no `alert()`, no browser `confirm()`.

## Motion

- Buttons transition in **0.1s ease-out** when hover or focus starts and
  **0.05s ease-in** when it ends; inputs use **0.1s linear** (see their
  specs). The property list is always explicit (`transition-property:
background-color, clip-path`). New components use these speeds; other
  speeds in older code are listed as known debt in the specs.
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
- Don't override a component's colours or radius for one instance; pick
  an intent or variant. The few sanctioned exceptions are named in the
  component's spec.
- Don't use `title=`; tooltips are tippy (`data-tippy-content` or
  `data-tooltip-template-id`).
- Do check `git grep` for every selector you touch; CSS changes leak across
  pages. Don't scope with bare tag or attribute selectors.
- Do use `!important` only to override Bootstrap or third-party styles, with
  a comment. Over a hundred exist; don't add more for any other reason.
- Don't put `style=""` in templates (the existing colour/font inline styles
  are debt).
- Do keep links blue, and don't introduce a new accent hue. Whether brand
  purple and CTA violet should merge is open (see Colors).
