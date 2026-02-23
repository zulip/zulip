# What Did I Miss? — Progress Tracker

> **Project:** AI-powered catch-up feature for Zulip
> **Repository:** [zulip-what-did-i-miss](https://github.com/CtrlAltGiri/zulip-what-did-i-miss)
> **Last Updated:** 2026-02-17

---

## Overall Status

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Backend Foundation | **COMPLETE** |
| **Phase 2** | Extractive Summarization | **COMPLETE** |
| **Phase 3** | Frontend — View Infrastructure | **COMPLETE** |
| **Phase 4** | Frontend — Interactive Features | **COMPLETE** |
| **Phase 4.5** | Runtime Bug Fixes | **COMPLETE** |
| Phase 5 | Refinement & User Preferences | Not Started |
| Phase 6 | Testing & Polish | Not Started |

---

## Phase 1: Backend Foundation

**Status: COMPLETE**
**Completed: 2026-02-10**

### What was built

The full backend API for the catch-up feature, including inactivity detection,
message aggregation across subscribed streams, importance scoring, and two REST
endpoints.

### Files Created

#### `zerver/lib/catch_up.py` — Core Business Logic

The main library module containing all the catch-up data processing logic.

**Key functions:**

| Function | Purpose |
|----------|---------|
| `get_last_active_time(user_profile)` | Detects user's last activity timestamp. Checks `UserPresence.last_active_time` first, falls back to `UserActivityInterval`, then defaults to 4 hours ago. |
| `clamp_since_time(since)` | Caps the absence period at `MAX_ABSENCE_DAYS` (7 days) to prevent overwhelming queries. |
| `get_subscribed_stream_map(user_profile, include_muted)` | Returns `{stream_id: stream_name}` for the user's active, non-deactivated subscriptions. Excludes muted streams by default. |
| `get_muted_topics_for_user(user_profile)` | Returns the set of `(stream_id, topic_name)` pairs the user has muted. |
| `get_catch_up_messages(user_profile, since, stream_map, include_muted)` | Queries messages since the given time across all subscribed streams, groups them by `(stream_id, topic_name)`, collects sender info and sample messages. Uses the `zerver_message_realm_recipient_date_sent` index. Caps at `MAX_CATCH_UP_MESSAGES` (1000). |
| `annotate_mention_flags(user_profile, topics, since)` | Checks `UserMessage` flags to identify topics where the user was `@`-mentioned, wildcard-mentioned, or group-mentioned. Modifies `CatchUpTopic` objects in-place. |
| `annotate_reaction_counts(topics, since, realm_id)` | Counts reactions per topic by querying the `Reaction` model. Modifies `CatchUpTopic` objects in-place. |
| `rank_topics(topics, max_topics)` | Scores and ranks topics by importance, returns top N. |

**Key data structures:**

- `CatchUpTopic` dataclass — Holds aggregated data for a single stream/topic
  - `score(now)` method computes importance using weighted factors:
    - Direct `@`-mention: weight 5.0
    - Wildcard mention (`@all`): weight 3.0
    - Group mention: weight 2.0
    - Sender diversity: weight 1.5 per unique sender
    - Message count: weight 1.0 per message
    - Reaction count: weight 0.5 per reaction
    - Recency bonus: 0–0.5 (higher for more recent activity)
  - `to_dict(now)` serializes the topic for the API response

#### `zerver/actions/catch_up.py` — Action Layer

Orchestrator that coordinates the library functions. Follows Zulip's
views → actions → models separation of concerns.

| Function | Purpose |
|----------|---------|
| `do_get_catch_up_data(user_profile, since, max_topics, include_muted)` | Main orchestrator: detect inactivity → get subscriptions → aggregate messages → annotate mentions/reactions → rank → return structured dict. |
| `do_get_catch_up_summary(user_profile, stream_id, topic_name)` | Generates an AI summary for a specific topic by constructing a `channel+topic` narrow and calling the existing `do_summarize_narrow()`. |

#### `zerver/views/catch_up.py` — API Endpoints

Two REST endpoints registered under `v1_api_and_json_patterns`:

**`GET /json/catch-up`** (or `/api/v1/catch-up`)

Main catch-up data endpoint.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `since` | ISO 8601 string | auto-detected | Override the last-active timestamp |
| `max_topics` | int | 20 | Max topics to return (1–100) |
| `include_muted` | bool | false | Include muted streams/topics |

Returns: `last_active_time`, `catch_up_period_hours`, `total_messages`, `total_topics`, `topics[]` (each with stream/topic info, score, senders, mentions, reactions, sample messages).

**`GET /json/catch-up/summary`** (or `/api/v1/catch-up/summary`)

Per-topic AI summary endpoint. Reuses existing topic summarization infrastructure.

| Parameter | Type | Description |
|-----------|------|-------------|
| `stream_id` | int | The stream containing the topic |
| `topic_name` | str | The topic to summarize |

Returns: `summary` (rendered HTML). Requires `TOPIC_SUMMARIZATION_MODEL` to be configured.

#### `zerver/tests/test_catch_up.py` — Test Suite

17 test cases across 4 test classes:

| Test Class | Tests | What's Covered |
|------------|-------|----------------|
| `GetLastActiveTimeTest` | 3 | Presence-based detection, activity interval fallback, default time |
| `GetSubscribedStreamMapTest` | 3 | Returns subscribed streams, excludes muted by default, includes muted when requested |
| `GetCatchUpMessagesTest` | 4 | Groups messages by topic, respects time range, only subscribed streams, tracks senders |
| `ImportanceScoringTest` | 4 | Mentions score highest, sender diversity factor, reaction factor, top-N ranking |
| `CatchUpEndpointTest` | 6 | Success response, `since` param, invalid params, unauthenticated access, empty results, score ordering, response structure validation |

### Files Modified

#### `zproject/urls.py`

- Added import: `from zerver.views.catch_up import get_catch_up, get_catch_up_summary`
- Registered two `rest_path` entries for `catch-up` and `catch-up/summary` (marked `intentionally_undocumented` for now)

### Architecture Decisions Made

1. **Reuses existing infrastructure:** UserPresence/UserActivityInterval for inactivity detection, Message model indexes for time-range queries, existing `do_summarize_narrow()` for AI summaries.
2. **No new database models:** All data is derived from existing tables — no migrations needed.
3. **Follows Zulip patterns:** views → actions → lib separation, `@typed_endpoint` decorator, `json_success()` responses, `ZulipTestCase` testing.
4. **Importance scoring is heuristic-based:** Weighted formula with direct mentions as the strongest signal, inspired by `digest.py`'s `get_hot_topics()` approach.
5. **AI summaries are on-demand:** Not pre-generated. The main endpoint returns only extractive data (sample messages); AI summaries are fetched separately per topic to save cost and latency.

---

## Phase 2: Extractive Summarization

**Status: COMPLETE**
**Completed: 2026-02-10**

### What was built

An extractive summarization system that selects the most important messages from
each topic using heuristic scoring, plus keyword extraction. This works without
any AI model — it's always available and produces transparent, source-linked
summaries.

### Files Created

#### `zerver/lib/catch_up_summarizer.py` — Extractive Summarization Engine

**Key components:**

| Component | Purpose |
|-----------|---------|
| `ScoredMessage` dataclass | A message with importance score and semantic tags |
| `extract_key_messages()` | Main function: fetches messages for a topic, scores each by mentions/reactions/position/content patterns, returns top N in chronological order |
| `extract_keywords()` | Lightweight keyword extraction: counts non-stopword terms across messages, returns most frequent |

**Message scoring weights:**

| Signal | Weight | Description |
|--------|--------|-------------|
| Direct `@`-mention | 10.0 | User was personally mentioned |
| Wildcard mention | 5.0 | `@all` / `@everyone` mention |
| Reactions | 2.0 per reaction | More reactions = more engagement |
| First message in topic | 3.0 | Sets context for the conversation |
| Last message in topic | 2.0 | Shows where conversation ended |
| Action item detected | 2.0 | Regex patterns: TODO, deadline, assigned to, etc. |
| Decision detected | 2.0 | Regex patterns: decided, agreed, going with, etc. |
| Question detected | 1.5 | Ends with `?` or contains question phrases |
| New sender (diversity) | 1.0 | First message from a unique sender |

**Content pattern detection:**

- Action items: `TODO`, `action item`, `assigned to`, `deadline`, `please do/review/fix`, etc.
- Decisions: `decided`, `agreed`, `conclusion`, `let's go with`, `approved`, `merged`
- Questions: trailing `?`, `does anyone`, `any thoughts`, `what do you think`

Each key message includes `tags` (list of `"mention"`, `"action_item"`, `"decision"`, `"question"`) so the frontend can render badges.

#### Keyword extraction

Strips code blocks, filters stopwords, counts 3+ character terms. Returns top 8 keywords by frequency. Gives users an at-a-glance sense of what a topic is about.

### Files Modified

#### `zerver/lib/catch_up.py`

- Added `key_messages` and `keywords` fields to `CatchUpTopic` dataclass
- Updated `to_dict()` to conditionally include `key_messages` and `keywords` when populated

#### `zerver/actions/catch_up.py`

- Added `include_extractive_summary` parameter to `do_get_catch_up_data()`
- Added `_annotate_extractive_summaries()` helper that calls `extract_key_messages()` and `extract_keywords()` for each ranked topic

#### `zerver/views/catch_up.py`

- Added `include_extractive_summary` parameter to `GET /json/catch-up` endpoint
- Default is `false` (no extractive summary) to keep default responses fast

#### `zerver/tests/test_catch_up.py`

Added 9 new test cases across 3 new test classes:

| Test Class | Tests | Coverage |
|------------|-------|----------|
| `ExtractKeyMessagesTest` | 6 | Message extraction, first/last position preference, reaction preference, action item tagging, question tagging, empty topic handling |
| `ExtractKeywordsTest` | 2 | Frequent term extraction, stopword filtering |
| `CatchUpWithExtractiveSummaryEndpointTest` | 2 | Endpoint returns key_messages/keywords when requested, omits them by default |

### Updated API

**`GET /json/catch-up`** — new parameter:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_extractive_summary` | bool | false | When true, each topic includes `key_messages` (scored important messages with tags) and `keywords` (frequent terms) |

**Example `key_messages` entry:**
```json
{
    "id": 12345,
    "sender_full_name": "Alice",
    "content": "TODO: update the deployment docs by Friday",
    "date_sent": "2026-02-10T14:30:00+00:00",
    "tags": ["action_item"],
    "reaction_count": 3
}
```

### Architecture Decisions

1. **Extractive, not abstractive:** Key messages are real messages, not generated text. Transparent and auditable.
2. **On-demand via parameter:** Extractive summaries add DB queries per topic, so they're opt-in. The frontend will request them when the user views the catch-up dashboard.
3. **Two summarization tiers:** Extractive (always available, fast) + AI (optional, richer). Frontend can show extractive immediately and offer an "AI Summary" button.
4. **Chronological output:** After scoring and selecting top N messages, results are re-sorted chronologically so the summary reads as a coherent narrative.
5. **Semantic tagging:** Messages are tagged with `action_item`, `decision`, `question`, `mention` to enable rich frontend rendering (badges, icons, filtering).

---

## Summary of All Files

### New Files (Phases 1–2)

| File | Lines | Purpose |
|------|-------|---------|
| `zerver/lib/catch_up.py` | ~455 | Core business logic: inactivity detection, message aggregation, importance scoring |
| `zerver/lib/catch_up_summarizer.py` | ~280 | Extractive summarization: key message selection, keyword extraction |
| `zerver/actions/catch_up.py` | ~155 | Action layer: orchestrates catch-up data + extractive summaries |
| `zerver/views/catch_up.py` | ~90 | API endpoints: `GET /json/catch-up`, `GET /json/catch-up/summary` |
| `zerver/tests/test_catch_up.py` | ~690 | 26 test cases across 7 test classes |

### Modified Files

| File | Change |
|------|--------|
| `zproject/urls.py` | Added imports + 2 `rest_path` registrations |

---

## Phase 3: Frontend — View Infrastructure

**Status: COMPLETE**
**Completed: 2026-02-10**

### What was built

A complete frontend view infrastructure for the catch-up feature, including
a new sidebar navigation item, hash-based URL routing, a view module with
show/hide/render lifecycle, data fetching via the backend API, Handlebars
templates for the dashboard and topic cards, and full CSS styling.

### Files Created

#### `web/src/catch_up_data.ts` — Data/API Module

Manages fetch calls to the backend and caches the current catch-up data.

| Export | Purpose |
|--------|---------|
| `CatchUpTopic` type | TypeScript type for a single topic's data (stream info, scores, messages, keywords) |
| `CatchUpData` type | TypeScript type for the full API response |
| `get_current_data()` | Returns the currently cached catch-up data |
| `clear_data()` | Clears cached data (called when view is hidden) |
| `fetch_catch_up_data(include_extractive_summary)` | Calls `GET /json/catch-up` and caches the result |
| `fetch_topic_summary(stream_id, topic_name)` | Calls `GET /json/catch-up/summary` for AI-generated summary |

Both functions use `channel.get()` (Zulip's standard HTTP wrapper) and return Promises.

#### `web/src/catch_up_ui.ts` — View Module

Main UI module following the `inbox_ui.ts` / `recent_view_ui.ts` pattern.

| Export | Purpose |
|--------|---------|
| `is_visible()` | Whether the catch-up view is currently shown |
| `show()` | Hides other views (inbox, recent), calls `views_util.show()` with catch-up config |
| `hide()` | Hides catch-up view, clears cached data |
| `complete_rerender()` | Fetches data from API, renders loading → content or empty state |

**Internal functions:**

| Function | Purpose |
|----------|---------|
| `format_period_display(hours)` | Converts `catch_up_period_hours` to human-readable string |
| `prepare_topic_for_render(topic)` | Enriches topic data with stream color, topic URL, formatted sender list |
| `render_loading()` / `render_empty()` / `render_data()` | Render respective states into `#catch-up-pane` |
| `setup_event_handlers()` | Attaches click handler on "AI Summary" buttons |

**AI Summary flow:** Clicking "AI Summary" on a topic card shows a loading spinner,
calls `fetch_topic_summary()`, and inserts the result (or error) into the card's
summary container.

#### `web/templates/catch_up_view/catch_up_view.hbs` — Main Template

Three states:
- **Loading:** Spinner with "Loading catch-up data…" text
- **Empty:** Check icon with "You're all caught up!" message
- **Data:** Header (title, period, stats) + scrollable list of topic cards

#### `web/templates/catch_up_view/catch_up_topic_card.hbs` — Topic Card Partial

Each card shows:
- Stream name (colored) → Topic name with separator
- Badges: @mention, @all, reaction count, message count
- Sender list
- Key messages (with sender, content, tags) or sample messages (fallback)
- Keywords as pill-shaped chips
- Actions: "Open topic" link + "AI Summary" button
- Summary container (hidden until AI summary is fetched)

#### `web/styles/catch_up.css` — Styles

Full CSS for the catch-up view including:
- Container layout (max-width 900px, centered)
- Loading/empty states
- Header with stats
- Topic cards with hover shadow
- Badge styling (mention red, wildcard orange, reactions blue)
- Key message display with tag pills
- Keyword chips
- AI summary container with left border accent
- Responsive layout for narrow screens (≤750px)

### Files Modified

#### `web/src/navigation_views.ts`

Added `catch_up` entry to the navigation views dictionary:
- `fragment: "catch-up"` — URL hash
- `icon: "zulip-icon-clock"` — sidebar icon
- `css_class_suffix: "catch_up"` — generates `.top_left_catch_up` CSS class
- `hidden_for_spectators: true` — not shown to spectators

#### `web/src/hashchange.ts`

Added `#catch-up` case in the hash routing switch that calls `catch_up_ui.show()`.
Added import for `catch_up_ui`.

#### `web/src/left_sidebar_navigation_area.ts`

Added `highlight_catch_up_view()` function following the exact pattern of
`highlight_inbox_view()` and `highlight_recent_view()`:
- Calls `select_top_left_corner_item(".top_left_catch_up")`
- Triggers `resize.resize_stream_filters_container()` in setTimeout

#### `templates/zerver/app/index.html`

Added the catch-up view container div between the inbox view and message feed:
```html
<div id="catch-up-view">
    <div id="catch-up-pane"></div>
</div>
```

#### `web/src/ui_init.js`

- Added import for `catch_up_ui`
- Updated `recent_view_ui.initialize()` and `inbox_ui.initialize()` to also call
  `catch_up_ui.hide()` in their `hide_other_views` callbacks, ensuring all three
  views properly hide each other on navigation

#### `web/src/bundles/app.ts`

Added CSS import: `import "../../styles/catch_up.css"`

#### `web/templates/tooltip_templates.hbs`

Added tooltip template for the catch-up sidebar item:
```html
<template id="catch-up-tooltip-template">
    <div class="views-tooltip-container" data-view-code="catch_up">
        <div>Catch up — What did I miss?</div>
    </div>
</template>
```

### Architecture Decisions

1. **Follows existing view patterns:** Uses `views_util.show()` / `views_util.hide()` exactly
   as inbox and recent views do. Same `show()` / `hide()` / `complete_rerender()` lifecycle.
2. **Direct view hiding:** Instead of a callback-based pattern, `catch_up_ui.show()` directly
   calls `inbox_ui.hide()` and `recent_view_ui.hide()`. The existing views are updated to also
   hide catch-up via their `hide_other_views` callbacks.
3. **Async data loading:** `complete_rerender()` shows a loading state immediately, fetches data
   from the API, then renders data or empty state. The view remains responsive during fetch.
4. **Extractive summaries by default:** `fetch_catch_up_data(true)` requests extractive summaries
   (key messages + keywords) by default, since they're fast and add significant value.
5. **AI summaries on demand:** AI summaries are fetched per-topic only when the user clicks the
   "AI Summary" button, avoiding unnecessary API credit usage.

---

## Summary of All Files

### New Files (Phases 1–3)

| File | Lines | Purpose |
|------|-------|---------|
| `zerver/lib/catch_up.py` | ~455 | Core business logic: inactivity detection, message aggregation, importance scoring |
| `zerver/lib/catch_up_summarizer.py` | ~280 | Extractive summarization: key message selection, keyword extraction |
| `zerver/actions/catch_up.py` | ~155 | Action layer: orchestrates catch-up data + extractive summaries |
| `zerver/views/catch_up.py` | ~90 | API endpoints: `GET /json/catch-up`, `GET /json/catch-up/summary` |
| `zerver/tests/test_catch_up.py` | ~690 | 26 test cases across 7 test classes |
| `web/src/catch_up_data.ts` | ~100 | Frontend data/API module |
| `web/src/catch_up_ui.ts` | ~155 | Frontend view module (show/hide/render) |
| `web/templates/catch_up_view/catch_up_view.hbs` | ~45 | Main dashboard Handlebars template |
| `web/templates/catch_up_view/catch_up_topic_card.hbs` | ~55 | Topic card Handlebars partial |
| `web/styles/catch_up.css` | ~310 | Full CSS styling for catch-up view |

### Modified Files

| File | Change |
|------|--------|
| `zproject/urls.py` | Added imports + 2 `rest_path` registrations |
| `web/src/navigation_views.ts` | Added `catch_up` navigation view entry |
| `web/src/hashchange.ts` | Added `#catch-up` hash routing + import |
| `web/src/left_sidebar_navigation_area.ts` | Added `highlight_catch_up_view()` |
| `templates/zerver/app/index.html` | Added `#catch-up-view` container div |
| `web/src/ui_init.js` | Added catch_up_ui import + updated hide callbacks |
| `web/src/bundles/app.ts` | Added CSS import for `catch_up.css` |
| `web/templates/tooltip_templates.hbs` | Added catch-up tooltip template |

---

## Phase 4: Frontend — Interactive Features

**Status: COMPLETE**
**Completed: 2026-02-10**

### What was built

Full interactivity for the catch-up view: client-side filtering (by type and
channel), keyboard navigation with arrow keys / Enter, and collapsible
topic cards with expand/collapse animation.

### Features Implemented

#### 1. Filter Bar

Three filter buttons and a channel dropdown, placed between the header and the
topic cards list:

| Filter | Behavior |
|--------|----------|
| **All** (default) | Shows all topics |
| **Mentions** | Only topics where user was @-mentioned or wildcard-mentioned |
| **Important** | Topics with importance score ≥ 5.0 (mentions, high engagement) |

Channel dropdown lists all channels that appear in the catch-up data, sorted
alphabetically. Selecting a channel restricts the view to topics from that channel.
Both filters compose — e.g., "Mentions" + a specific channel shows only mentioned
topics in that channel.

A "No topics match your current filters" message appears when filters hide
everything.

#### 2. Expand/Collapse Topic Cards

- Cards start **collapsed** — showing only the header (stream/topic name, badges,
  senders) and hiding the body (key messages, keywords, actions, AI summary)
- Click the card header or the chevron button to **expand** and reveal full content
- Chevron icon rotates between ▼ (collapsed) and ▲ (expanded)
- Smooth CSS `max-height` transition animation (0.25s ease)
- Left/Right arrow keys also toggle expand/collapse on the focused card

#### 3. Keyboard Navigation

Integrated with Zulip's existing `hotkey.ts` system:

| Key | Action |
|-----|--------|
| ↓ / j | Move focus to next topic card |
| ↑ / k | Move focus to previous card (or back to filters from first card) |
| → / l | Expand focused card |
| ← / h | Collapse focused card |
| Enter | Open the focused topic (navigates to the topic narrow) |
| Page Down | Jump 5 cards forward |
| Page Up | Jump 5 cards back |
| ← / → on filters | Navigate between filter buttons and channel dropdown |
| ↓ from filters | Move focus to the first topic card |
| Enter on filter | Activate the focused filter button |

Focus management:
- Cards have `tabindex="0"` and `role="article"` for accessibility
- Focused card gets a visible blue outline (`focus-visible`)
- Smooth scroll-into-view on keyboard navigation
- `is_in_focus()` check prevents hotkey conflicts with other views

### Files Modified

#### `web/src/catch_up_ui.ts`

Major expansion from ~170 lines to ~350 lines:

| Addition | Purpose |
|----------|---------|
| `FilterMode` type | `"all" \| "mentions" \| "important"` |
| `current_filter`, `current_stream_filter` | Filter state variables |
| `card_focus` | Index of currently keyboard-focused card |
| `IMPORTANT_SCORE_THRESHOLD` | Score cutoff for "Important" filter (5.0) |
| `is_in_focus()` | Whether the catch-up view owns keyboard focus |
| `get_unique_streams()` | Extracts deduplicated, sorted channel list from topic data |
| `apply_filters()` | Shows/hides cards based on current filter + channel selection |
| `toggle_card_expansion()` | Toggles `.expanded` class and chevron icon |
| `change_focused_element(input_key)` | Arrow key handler (called from hotkey.ts) |
| `handle_enter_key()` | Enter key handler — activates filter or opens topic |
| `focus_card(index)` / `focus_filters()` | Focus management helpers |

#### `web/templates/catch_up_view/catch_up_view.hbs`

Added filter bar between header and topics list:
- Three `<button class="catch-up-filter-btn">` elements (All, Mentions, Important)
- `<select id="catch-up-stream-filter">` for channel filtering
- `<div id="catch-up-no-filter-results">` empty state message

#### `web/templates/catch_up_view/catch_up_topic_card.hbs`

Restructured for expand/collapse:
- Added `data-has-mention`, `data-has-wildcard`, `data-score` attributes for
  client-side filtering
- Added `tabindex="0"` and `role="article"` for keyboard accessibility
- Added expand/collapse chevron button in the header badges
- Wrapped key messages, keywords, and actions in a new `.catch-up-card-body`
  div that is collapsed by default

#### `web/styles/catch_up.css`

Added ~100 lines of new styles:
- `.catch-up-filters` — flexbox filter bar layout
- `.catch-up-filter-btn` — filter button styling with `.active` state (blue)
- `.catch-up-stream-filter` — native select dropdown styling
- `.catch-up-no-filter-results` — empty filter state
- `.catch-up-expand-btn` — chevron toggle button
- `.catch-up-card-body` — collapse/expand with `max-height` transition
- `:focus-visible` outlines on cards and filter controls
- Responsive additions for filters on narrow screens

#### `web/src/hotkey.ts`

- Added import for `catch_up_ui`
- Added arrow key routing block: when `catch_up_ui.is_in_focus()`,
  routes `up/down/left/right/page_up/page_down/vim_*` to
  `catch_up_ui.change_focused_element()`
- Added Enter key handling: when `catch_up_ui.is_in_focus()`,
  calls `catch_up_ui.handle_enter_key()`

---

## Summary of All Files

### New Files (Phases 1–4)

| File | Lines | Purpose |
|------|-------|---------|
| `zerver/lib/catch_up.py` | ~455 | Core business logic: inactivity detection, message aggregation, importance scoring |
| `zerver/lib/catch_up_summarizer.py` | ~280 | Extractive summarization: key message selection, keyword extraction |
| `zerver/actions/catch_up.py` | ~155 | Action layer: orchestrates catch-up data + extractive summaries |
| `zerver/views/catch_up.py` | ~90 | API endpoints: `GET /json/catch-up`, `GET /json/catch-up/summary` |
| `zerver/tests/test_catch_up.py` | ~690 | 26 test cases across 7 test classes |
| `web/src/catch_up_data.ts` | ~100 | Frontend data/API module |
| `web/src/catch_up_ui.ts` | ~350 | Frontend view module with filtering and keyboard navigation |
| `web/templates/catch_up_view/catch_up_view.hbs` | ~60 | Main dashboard template with filter bar |
| `web/templates/catch_up_view/catch_up_topic_card.hbs` | ~70 | Expandable topic card template |
| `web/styles/catch_up.css` | ~500 | Full CSS with filters, expand/collapse, focus states |

### Modified Files

| File | Change |
|------|--------|
| `zproject/urls.py` | Added imports + 2 `rest_path` registrations |
| `web/src/navigation_views.ts` | Added `catch_up` navigation view entry |
| `web/src/hashchange.ts` | Added `#catch-up` hash routing + import |
| `web/src/left_sidebar_navigation_area.ts` | Added `highlight_catch_up_view()` |
| `templates/zerver/app/index.html` | Added `#catch-up-view` container div |
| `web/src/ui_init.js` | Added catch_up_ui import + updated hide callbacks |
| `web/src/bundles/app.ts` | Added CSS import for `catch_up.css` |
| `web/templates/tooltip_templates.hbs` | Added catch-up tooltip template |
| `web/src/hotkey.ts` | Added catch_up_ui import + keyboard routing |

---

## Phase 4.5: Runtime Bug Fixes

**Status: COMPLETE**
**Completed: 2026-02-17**

### What was fixed

First-run testing of the catch-up view revealed several runtime errors caused by
incompatibilities with Zulip's strict Handlebars mode, incorrect Django ORM
BitField lookups, and a missing view registration in the narrow title system.

### Bug 1: Assertion failure in `narrow_title.ts`

**Symptom:** Opening `#catch-up` immediately crashed with `Error: Assertion failed`
at `compute_narrow_title`.

**Root cause:** `compute_narrow_title()` handles views without a message feed
(`filter === undefined`). It checked for recent view, then asserted inbox must be
visible. The catch-up view is neither, so the assertion failed.

**Fix:** Added a `catch_up_ui.is_visible()` check before the inbox assertion,
returning `"Catch up"` as the page title.

**File:** `web/src/narrow_title.ts`

### Bug 2: `flags__and` BitField lookup error (HTTP 500)

**Symptom:** `GET /json/catch-up` returned 500 with `FieldError: Unsupported lookup
'and' for BitField`.

**Root cause:** `annotate_mention_flags()` used `Q(flags__and=UserMessage.flags.mentioned)`
which is not a valid Django BitField lookup. Zulip's BitField uses `andnz` (AND non-zero)
with `.mask`.

**Fix:** Changed all BitField queries to use `flags__andnz=UserMessage.flags.<flag>.mask`
pattern, matching how the rest of the Zulip codebase queries UserMessage flags
(see `zerver/models/messages.py`).

**Files:** `zerver/lib/catch_up.py`, `zerver/lib/catch_up_summarizer.py`

### Bug 3: Handlebars strict mode — arrays in `{{#if}}`

**Symptom:** `BlueslipError: Cannot test a value of type object in a Zulip Handlebars template`

**Root cause:** Zulip's custom `Handlebars.Utils.isEmpty` override (in `templates.ts`)
rejects arrays in `{{#if}}` tests. The templates used `{{#if key_messages}}`,
`{{#if sample_messages}}`, `{{#if keywords}}`, and `{{#if streams}}` — all arrays.

**Fix:** Added boolean flags in `prepare_topic_for_render()` and `render_data()`:
`has_key_messages`, `has_sample_messages`, `has_keywords`, `has_streams`. Updated
both templates to use these boolean flags instead of testing arrays directly.

**Files:** `web/src/catch_up_ui.ts`, `web/templates/catch_up_view/catch_up_view.hbs`,
`web/templates/catch_up_view/catch_up_topic_card.hbs`

### Bug 4: Handlebars strict mode — partial context

**Symptom:** `"stream_id" not defined in undefined – 1:51`

**Root cause:** Zulip's webpack config uses `explicitPartialContext: true`, which
means partials don't automatically inherit the parent context. The template used
`{{> catch_up_topic_card }}` without passing context.

**Fix:** Changed to `{{> catch_up_topic_card this}}` to explicitly pass the loop
context to the partial.

**File:** `web/templates/catch_up_view/catch_up_view.hbs`

### Bug 5: Handlebars strict mode — booleans in data attributes

**Symptom:** `BlueslipError: Cannot use a value of type boolean in a Zulip Handlebars template`

**Root cause:** Zulip's custom `escapeExpression` override rejects boolean values
rendered as text. The template used `data-has-mention="{{has_mention}}"` and
`data-has-wildcard="{{has_wildcard_mention}}"` — both booleans rendered into
HTML attributes.

**Fix:** Added string-converted versions (`data_has_mention`, `data_has_wildcard`)
in `prepare_topic_for_render()` using `String()`. Updated template data attributes
to use the string versions while keeping the original booleans for `{{#if}}` conditionals.

**Files:** `web/src/catch_up_ui.ts`, `web/templates/catch_up_view/catch_up_topic_card.hbs`

### Bug 6: Handlebars strict mode — numbers in `{{#if}}`

**Symptom:** `BlueslipError: Cannot test a value of type number in a Zulip Handlebars template`

**Root cause:** Zulip's custom `{{#if}}` helper rejects numbers. The template used
`{{#if reaction_count}}` where `reaction_count` is a number.

**Fix:** Added `has_reactions` boolean flag in `prepare_topic_for_render()`. Updated
template to use `{{#if has_reactions}}` instead.

**Files:** `web/src/catch_up_ui.ts`, `web/templates/catch_up_view/catch_up_topic_card.hbs`

### Dev testing note

`get_last_active_time()` in `zerver/lib/catch_up.py` has a temporary early return
(`return timezone_now() - timedelta(hours=24)`) to force a 24-hour lookback for
development testing. This **must be removed** before committing — it bypasses the
real presence-based inactivity detection.

### Summary of all changes

| File | Changes |
|------|---------|
| `web/src/narrow_title.ts` | Added `catch_up_ui` import + `is_visible()` check for catch-up page title |
| `zerver/lib/catch_up.py` | Fixed `flags__and` → `flags__andnz` with `.mask` in `annotate_mention_flags()` |
| `zerver/lib/catch_up_summarizer.py` | Fixed `flags__and` → `flags__andnz` with `.mask` in mention flag query |
| `web/src/catch_up_ui.ts` | Added boolean flags (`has_key_messages`, `has_sample_messages`, `has_keywords`, `has_reactions`, `has_streams`), string conversions (`data_has_mention`, `data_has_wildcard`) for Handlebars strict mode |
| `web/templates/catch_up_view/catch_up_view.hbs` | `{{#if streams}}` → `{{#if has_streams}}`, `{{> catch_up_topic_card }}` → `{{> catch_up_topic_card this}}` |
| `web/templates/catch_up_view/catch_up_topic_card.hbs` | `{{#if key_messages}}` → `{{#if has_key_messages}}`, `{{#if sample_messages}}` → `{{#if has_sample_messages}}`, `{{#if keywords}}` → `{{#if has_keywords}}`, `{{#if reaction_count}}` → `{{#if has_reactions}}`, `{{has_mention}}` → `{{data_has_mention}}`, `{{has_wildcard_mention}}` → `{{data_has_wildcard}}` |

### Lessons learned

1. **Zulip Handlebars is strict:** No arrays/objects in `{{#if}}`, no booleans in text output, no numbers in `{{#if}}`, partials need explicit context. Always use boolean flags for conditionals and string conversions for data attributes.
2. **Django BitField lookups:** Use `flags__andnz=<flag>.mask`, not `flags__and=<flag>`.
3. **Vagrant/Docker file sync:** Host-side edits may not be detected by file watchers inside the container. Restart `run-dev` after making changes to ensure they take effect.
4. **Dev testing presence:** Since the user is actively browsing, `get_last_active_time()` returns "right now" — making catch-up data empty. A temporary override or the `since` API parameter is needed for testing.

---

## Phase 5–6: Upcoming

See [PLAN.md](./PLAN.md) for detailed plans for refinement
and testing/polish.
