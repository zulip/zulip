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
     Rules and foundations live in DESIGN.md at the repo root. -->

# Input pill

A container that turns typed values into removable chips: recipients,
users and groups in settings, channels/topics in search, filters. One
JS module owns creation, keyboard handling and removal; templates only
decide what a pill shows.

- **API** — `input_pill.create({$container, create_item_from_text,
get_text_from_item, get_display_value_from_item, generate_pill_html?,
on_pill_exit?, split_text_on_comma?, convert_to_pill_on_enter?,
show_outline_on_invalid_input?, pill_config?})` in `web/src/input_pill.ts`
  returns an `InputPillContainer` (`appendValue`, `appendValidatedData`,
  `removePill`, `items`, `clear`, `clear_text`, `onPillCreate`,
  `onPillRemove`). `$container` is a `.pill-container` holding pills and a
  trailing `.input` (`contenteditable`). Typed wrappers exist per domain
  (`user_pill.ts`, `stream_pill.ts`, `user_group_pill.ts`, `search_pill.ts`,
  `pill_typeahead.ts` for the accompanying typeahead).
- **Anatomy** — `.pill-container` (inline-flex, wraps, 1px border
  `border-pill-container`, 4px radius, padding 2px, gap 2px 6px) containing
  `.pill` (`input_pill.hbs`): optional avatar `.pill-image` with a
  `.pill-image-border` overlay, `.pill-label > .pill-value` (nowrap,
  ellipsis) plus optional guest indicator, status emoji, bot icon, member
  count, optional `.expand` and the `.exit` button (`zulip-icon-close`,
  `role="button"`, `aria-label`). Pill height is `--height-input-pill`
  (1.5714em ≈ 22px at 14px), `box-sizing: border-box`; the `.input` line
  height matches so text and pills align.
- **Variants by content** — user (avatar, name, status), user group (name +
  member count), channel (`decorated_channel_name`, privacy icon),
  channel > topic (combined), email (invited name), search operators
  (`search_pill.ts`), display-only pills (`user_display_only_pill.hbs`,
  `user_group_display_only_pill.hbs`) inside `.not-editable` containers.
- **States**
  - rest → `background-input-pill` (violet tint), text inherits.
  - hover → only pills that open a user card (`.view_user_profile`, and
    inside `.person_picker`) get `background-input-pill-hover`. Others
    have no hover.
  - focus (`:focus`, not focus-visible, so mouse + Backspace works) → 1px
    inset ring `focus-outline-input-pill`; avatar border takes the same
    colour. No outline.
  - exit / expand hover → `background-input-pill-exit-hover` behind the
    icon, icon opacity 0.7 → 1.
  - deactivated user → `.deactivated-pill`: muted background, 70% opacity,
    slashed-circle badge over the avatar.
  - container invalid → `.invalid` on `.pill-container`:
    `--color-invalid-input-border` + `--invalid-input-box-shadow` (set by
    `input_pill.ts` when `show_outline_on_invalid_input`).
  - container disabled → `.not-editable-by-user` (grey background, exit
    buttons hidden, `not-allowed` cursor) or `.not-editable` (no border,
    display only).
- **Behaviour** (`input_pill.ts`)
  - Enter (`convert_to_pill_on_enter`, default true) or comma
    (`split_text_on_comma`) turn the typed text into a pill via
    `create_item_from_text`; invalid text stays as text and, if
    configured, marks the container invalid. Blur does not convert
    (`input_pill.ts` has no blur handler).
  - Backspace on an empty input removes the last pill; Backspace on a
    focused pill removes it (Delete does nothing); Left/Right arrows move
    focus between pills and the input; clicking `.exit` removes that pill.
    Removal reports its trigger (`close` | `backspace` | `clear`) to
    `onPillRemove`.
  - Paste of multiple values is split into several pills
    (`split_text_to_form_pills`).
  - Focus on the container puts the caret in the `.input`; the container
    is the click target (`cursor: text`).
- **Accessibility** — pills are `tabindex=0` and focusable; the remove
  control is `role="button"` with `aria-label="Remove"`; the bot icon has an
  `aria-label`. The contenteditable `.input` has no accessible name of its
  own — the surrounding field must provide one. Focus is a 1px inset ring,
  weaker than the button focus ring by design so avatars stay visible.
- **Don't** — no hand-rolled chip markup; no `padding` on `.pill` (height
  is authoritative); no per-page pill colours except through the existing
  compose-recipient tokens; no `title=` on pills.
- **Known debt** — `.not-editable .pill:focus` uses raw
  `hsl(0deg 0% 0% / 15%)` / `7%`; `input_pill.css` mixes `px` (2px, 6px,
  3px margins) with `em`; the compose recipient box overrides the
  container border with its own tokens.
- **Code** — `web/styles/input_pill.css`, `web/templates/input_pill.hbs`,
  `web/src/input_pill.ts`, `web/src/pill_typeahead.ts`.
