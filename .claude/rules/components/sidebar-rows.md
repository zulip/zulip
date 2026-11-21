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
     Generic rules (tokens, focus, motion, accessibility) are in DESIGN.md at
     the repo root; this file only adds what is specific to left sidebar rows. -->

# Left sidebar rows

The three row types of the left sidebar: navigation rows (Inbox, Recent
conversations, …), channel rows and topic rows. Direct-message rows follow
the channel row grid with an avatar or presence circle in the icon column.

- **API** — navigation: `left_sidebar_expanded_view_item.hbs`
  (`li.top_left_<view>.top_left_row` > `a.left-sidebar-navigation-label-container`
  with `.filter-icon`, `.left-sidebar-navigation-label`, `.unread_count`,
  optional `.sidebar-menu-icon`); the condensed form
  (`left_sidebar_primary_condensed_view_item.hbs`) keeps icon and count.
  Channel: `stream_sidebar_row.hbs` (`li.narrow-filter` >
  `.bottom_left_row.channel-header` > `a.subscription_block` with the
  `.stream-privacy` icon, `.stream-name`, `.left-sidebar-controls`,
  `.stream-markers-and-unreads`, `.sidebar-menu-icon`). Topic:
  `topic_list_item.hbs` (`li.bottom_left_row.topic-list-item` >
  `a.topic-box` with `.sidebar-topic-check`, `.sidebar-topic-name`,
  `.topic-markers-and-unreads`, `.sidebar-menu-icon`). Rendered by
  `stream_list.ts`, `topic_list.ts` and `left_sidebar_navigation_area.ts`.
- **Anatomy** — every row is a grid with the same areas: starting offset ·
  icon · gap · content · controls · markers-and-unreads · vdots · ending
  offset, sized by the `--left-sidebar-*` variables. Row heights are
  `--line-height-sidebar-row` (navigation) and
  `--line-height-sidebar-row-prominent` (channels and topics); text
  `text-sidebar-row`. Channel names ellipsise; topic names clamp to two
  lines. Unread counters are `normal-count`.
- **States**
  - hover / open menu → `background-hover-narrow-filter` and an inset
    `shadow-sidebar-row-hover`; the vdots and controls appear.
  - active (`.active-filter`, `.active-sub-filter`, `.selected-home-view`)
    → `background-active-narrow-filter`, `text-active-narrow-filter`,
    weight 600.
  - keyboard highlight / focus-visible → inset `outline-focus` ring.
  - muted (`.out_of_home_view`, `.muted_topic`) → `--opacity-left-sidebar-muted`;
    unmuted or followed topics in a muted channel use
    `unmuted-or-followed-topic-list-item`.
  - zero unreads hide the counter (`.zero_count`); a new unread in a DM or
    mentions row flashes `background-active-narrow-filter` (`.new-unread`).
- **Behaviour** — click navigates; the vdots opens the row's popover menu;
  an active channel shows its topic list. The rows are reachable with the
  arrow keys via `.highlighted_row` (`hotkey.ts`), and Enter opens.
  Topic filtering is in the header input, not per row.
- **Accessibility** — rows are links with visible labels; on navigation
  rows the vdots `<i>` has an `aria-label` (`menu_aria_label`); the
  follow icon is `role="button"` with a label.
- **For new code** — new row types use the shared grid areas and the
  shared `.top_left_row, .bottom_left_row` hover rules.
- **Don't** — no per-row paddings or margins (use the grid areas).
- **Known debt**
  - The privacy icon takes the channel colour through an inline `style`
    (also the sanctioned colour exception).
  - Some rules use `!important` (`li.active-sub-filter` weight).
  - The grid is repeated per row type with slightly different columns.
  - In `stream_sidebar_row.hbs` and `topic_list_item.hbs` the
    `.sidebar-menu-icon` is a `span[tabindex=0]` with no role or label;
    `.channel-search-topics-button` and `.channel-new-topic-button` are
    `div[tabindex=0]` with only a tooltip; unread counts have no name
    beyond the number.
  - Sidebar section headings (`.left-sidebar-title`) aren't covered by
    this spec; their opacity transition is 140ms.
- **Code** — `web/styles/left_sidebar.css`, templates above,
  `web/src/stream_list.ts`, `web/src/topic_list.ts`,
  `web/src/left_sidebar_navigation_area.ts`.
