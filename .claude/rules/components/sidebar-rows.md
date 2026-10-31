---
paths:
  - "web/styles/left_sidebar.css"
  - "web/templates/left_sidebar_expanded_view_item.hbs"
  - "web/templates/left_sidebar_primary_condensed_view_item.hbs"
  - "web/templates/stream_sidebar_row.hbs"
  - "web/templates/topic_list_item.hbs"
  - "web/src/stream_list.ts"
  - "web/src/topic_list.ts"
  - "web/src/left_sidebar_navigation_area.ts"
---

<!-- Component spec. Loaded automatically when the files above are edited;
     the /design-review skill also loads it when a diff *uses* this component.
     Rules and foundations live in DESIGN.md at the repo root. -->

# Left sidebar rows

The three row types of the left sidebar: navigation rows (Inbox, Recent
conversations, …), channel rows and topic rows. Direct-message rows follow
the channel row grid with an avatar or presence circle in the icon column.

- **API** — navigation: `left_sidebar_expanded_view_item.hbs`
  (`li.top_left_<view>.top_left_row` > `a.left-sidebar-navigation-label-container`
  with `.filter-icon`, `.left-sidebar-navigation-label`, `.unread_count`,
  optional `.sidebar-menu-icon`); the condensed form
  (`left_sidebar_primary_condensed_view_item.hbs`) keeps only icon and
  count. Channel: `stream_sidebar_row.hbs` (`li.narrow-filter` >
  `.bottom_left_row.channel-header` > `a.subscription_block` with
  `.stream-privacy` icon in the channel colour, `.stream-name`,
  `.left-sidebar-controls` (search topics, new topic),
  `.stream-markers-and-unreads`, `.sidebar-menu-icon`). Topic:
  `topic_list_item.hbs` (`li.bottom_left_row.topic-list-item` > `a.topic-box`
  with `.sidebar-topic-check` (resolved prefix), `.sidebar-topic-name`,
  `.topic-markers-and-unreads` (mention "@" or follow icon + count),
  `.sidebar-menu-icon`). Rows are rendered by `stream_list.ts`,
  `topic_list.ts` and `left_sidebar_navigation_area.ts`.
- **Anatomy** — every row is a grid with the same areas: starting offset
  (`--left-sidebar-toggle-width-offset`, 20px) · icon column
  (`--left-sidebar-icon-column-width`, 1em) · gap
  (`--left-sidebar-icon-content-gap`, 0.4375em) · content (`1fr`) · controls ·
  markers-and-unreads · vdots (`--left-sidebar-vdots-width`, 1.625em) ·
  ending offset. Row height is `--line-height-sidebar-row` (1.5714em, 22px)
  for navigation rows and `--line-height-sidebar-row-prominent` (1.7142em,
  24px) for channel and topic rows; 4px radius; text `text-sidebar-row`.
  Navigation icons use `left-sidebar-navigation-icon`; channel privacy
  icons (`stream_privacy.hbs`: hashtag 0.9286em, lock 0.9286em, globe
  0.8571em, archive) take the channel colour via an inline `style`. Topic
  names clamp to two lines (`--line-height-sidebar-topic-inner`); topic rows
  are indented by the offset and get 5px right padding. Unread counters
  (`normal-count`) sit in markers-and-unreads with a 6.5px right margin
  (`--left-sidebar-unread-offset`) and 5px gaps to the "@" or follow icon.
  The vdots menu (`.sidebar-menu-icon`, 1.0625em `more-vertical`, 3px
  radius, 2px 2px 2px 1px margin) and the channel controls
  (`--left-sidebar-header-icon-width`, 22px each) are `display: none` until
  the row is hovered, focused or highlighted (always shown on touch, in
  `vdots-hint`).
- **States**
  - hover / open menu → `background-hover-narrow-filter` plus a 1px inset
    `shadow-sidebar-row-hover`; vdots and controls appear in `vdots-visible`
    (`vdots-hover` when hovering the icon itself, `sidebar-action-hover` on
    `background-sidebar-action-hover` for the new-topic / search buttons).
  - active (`.active-filter`, `.active-sub-filter`, `.selected-home-view`)
    → `background-active-narrow-filter`, `text-active-narrow-filter`,
    weight 600; hover keeps the active background.
  - keyboard highlight / focus-visible → 2px `outline-focus` inset 2px on
    the hover background.
  - muted channel or topic (`.out_of_home_view`, `.muted_topic`) → the row
    at `--opacity-left-sidebar-muted` (0.55; 0.75 on hover); unmuted or
    followed topics in a muted channel use
    `unmuted-or-followed-topic-list-item`.
  - zero unreads → the counter is hidden (`.zero_count`); new unread in a
    DM or mentions row flashes `background-active-narrow-filter`
    (`.new-unread`, 1s transition).
- **Behaviour** — click navigates (`href="#narrow/…"`); the vdots opens the
  row's popover menu (`popover_menus`); channels toggle their topic list
  when active; keyboard: the sidebar rows are reachable with the arrow keys
  via `.highlighted_row` (`ui_util`, `hotkey.ts`), Enter opens; topic
  filtering happens in the header input, not per row. Long channel names
  ellipsise; long topic names wrap to two lines.
- **Accessibility** — rows are links with visible labels; icons are
  `aria-hidden`; on navigation rows the vdots `<i>` carries an
  `aria-label` (`menu_aria_label`); the follow icon is `role="button"` with
  a label. Gaps: unread counts have no accessible name beyond the number;
  in `stream_sidebar_row.hbs` and `topic_list_item.hbs` the
  `.sidebar-menu-icon` is a `span[tabindex=0]` with no role or label
  (the `<i>` inside is `aria-hidden`); `.channel-search-topics-button` and
  `.channel-new-topic-button` are `div[tabindex=0]` with no role or label
  (only a tooltip).
- **Don't** — no per-row paddings or margins (use the grid areas); no
  colours besides the row tokens and the channel colour on the privacy
  icon; no hover styles that differ from the shared `.top_left_row,
.bottom_left_row` rules; no `title=`.
- **Known debt** — the privacy icon colour is an inline `style`; several
  rules use `!important` (`li.active-sub-filter` weight); the row grid is
  duplicated per row type with slightly different column lists; sidebar
  section headings (`.left-sidebar-title`, small caps) are not covered by
  this spec; the channel and topic vdots and the channel controls lack a
  role and accessible name (see Accessibility).
- **Code** — `web/styles/left_sidebar.css`, templates above,
  `web/src/stream_list.ts`, `web/src/topic_list.ts`,
  `web/src/left_sidebar_navigation_area.ts`.
