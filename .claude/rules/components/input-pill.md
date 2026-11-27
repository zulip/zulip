---
paths:
  - "web/styles/input_pill.css"
  - "web/templates/input_pill.hbs"
  - "web/templates/search_user_pill.hbs"
  - "web/templates/user_display_only_pill.hbs"
  - "web/templates/user_group_display_only_pill.hbs"
  - "web/src/input_pill.ts"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Generic rules (tokens, focus, motion, accessibility) are in DESIGN.md at
     the repo root; this file only adds what is specific to input pills. -->

# Input pill

A container that turns typed values into removable chips: recipients,
users and groups in settings, channels and topics in search, filters. One
JS module owns creation, keyboard handling and removal; templates only
decide what a pill shows.

- **API** — `input_pill.create({$container, create_item_from_text,
get_text_from_item, get_display_value_from_item, generate_pill_html?,
on_pill_exit?, split_text_on_comma?, convert_to_pill_on_enter?,
show_outline_on_invalid_input?, pill_config?})` in `web/src/input_pill.ts`
  returns an `InputPillContainer` (`appendValue`, `appendValidatedData`,
  `removePill`, `items`, `clear`, `clear_text`, `onPillCreate`,
  `onPillRemove`). Typed wrappers exist per domain (`user_pill.ts`,
  `stream_pill.ts`, `user_group_pill.ts`, `search_pill.ts`; typeahead in
  `pill_typeahead.ts`).
- **Anatomy** — `.pill-container` (wraps; border `border-pill-container`)
  holding `.pill`s and a trailing contenteditable `.input`. A pill
  (`input_pill.hbs`): optional avatar `.pill-image`, `.pill-label >
.pill-value` (one line, ellipsis) with optional guest indicator, status
  emoji, bot icon or member count, then optional `.expand` and the
  `.exit` button. Height is `--height-input-pill` and the `.input` line
  height matches it; spacing is in `input_pill.css`.
- **Variants by content** — user, user group, channel, channel > topic,
  email, search operators (`search_pill.ts`), and display-only pills
  (`user_display_only_pill.hbs`, `user_group_display_only_pill.hbs`)
  inside `.not-editable` containers.
- **States**
  - rest `background-input-pill`; hover `background-input-pill-hover`
    only on pills that open a user card; exit / expand hover
    `background-input-pill-exit-hover`.
  - focus on plain `:focus` (so mouse + Backspace works): a 1px inset
    ring `focus-outline-input-pill`, also on the avatar border.
  - `.deactivated-pill`: muted background, reduced opacity, a slashed
    badge over the avatar.
  - container `.invalid` (set when `show_outline_on_invalid_input`):
    `--color-invalid-input-border` + `--invalid-input-box-shadow`.
  - container disabled: `.not-editable-by-user` (grey, exit buttons
    hidden, `not-allowed` cursor) or `.not-editable` (no border, display
    only).
- **Behaviour** (`input_pill.ts`)
  - Enter (`convert_to_pill_on_enter`, default true) or comma
    (`split_text_on_comma`) turns typed text into a pill via
    `create_item_from_text`; invalid text stays as text. Blur doesn't
    convert.
  - Backspace on an empty input removes the last pill, and on a focused
    pill removes it; Left / Right move focus between pills and the input;
    `.exit` removes its pill. `onPillRemove` gets the trigger (`close` |
    `backspace` | `clear`).
  - Pasting several values splits them into pills
    (`split_text_to_form_pills`). Clicking the container focuses the
    `.input`.
- **Accessibility** — pills are `tabindex=0`; `.exit` is
  `role="button"` with `aria-label="Remove"`; the bot icon has an
  `aria-label`. The `.input` has no name of its own, so the surrounding
  field must label it.
- **For new code** — create pills through `input_pill.create` or a typed
  wrapper, and show invalid input with `show_outline_on_invalid_input`
  rather than custom styling.
- **Don't** — no `padding` on `.pill` (height is authoritative).
- **Known debt**
  - `.not-editable .pill:focus` uses raw `hsl()` alphas.
  - `input_pill.css` mixes `px` with `em`.
  - `--color-input-pill-close` has no property in its name.
  - The compose recipient box overrides the container border with its
    own tokens (the sanctioned colour exception).
- **Code** — `web/styles/input_pill.css`, `web/templates/input_pill.hbs`,
  `web/src/input_pill.ts`, `web/src/pill_typeahead.ts`.
