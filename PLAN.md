# What Did I Miss? — Implementation Plan

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Backend Implementation](#3-backend-implementation)
4. [Frontend Implementation](#4-frontend-implementation)
5. [NLP / Summarization Pipeline](#5-nlp--summarization-pipeline)
6. [File-by-File Change Map](#6-file-by-file-change-map)
7. [Implementation Phases](#7-implementation-phases)
8. [Testing Strategy](#8-testing-strategy)
9. [Open Questions & Decisions](#9-open-questions--decisions)

---

## 1. Executive Summary

**Goal:** Build an AI-powered catch-up feature that summarizes important activity
since a user's last active session, organized by stream and topic, with importance
ranking and direct links to original messages.

**Key Insight — Leverage Existing Infrastructure:** Zulip already has several
systems we can build on:

| Existing System | How We Use It |
|---|---|
| `UserPresence` model (`last_active_time`, `last_connected_time`) | Detect when a user returns after inactivity |
| `UserActivityInterval` model | Determine precise absence windows |
| `fetch_messages()` in `zerver/lib/narrow.py` | Query messages by time range and subscriptions |
| `message_summary.py` + `do_summarize_narrow()` | Existing AI summarization pipeline (LiteLLM) |
| `digest.py` (`DigestTopic`, `get_hot_topics()`) | Importance scoring heuristics (diversity + length) |
| `navigation_views.ts` + `views_util.ts` | Add a new sidebar navigation view |
| `hashchange.ts` routing system | URL routing for `#catch-up` |

**What's New:**
- A new backend endpoint that aggregates messages across all subscribed streams
  since last activity, groups them by stream/topic, scores importance, and
  optionally generates AI summaries
- A new frontend "Catch-Up" view accessible from the left sidebar
- Importance scoring algorithm combining mentions, replies, reactions, and volume

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (TypeScript)                    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Navigation    │  │ Catch-Up     │  │ Summary Card      │  │
│  │ Sidebar Entry │→ │ Dashboard    │→ │ Components        │  │
│  │ (#catch-up)   │  │ (main view)  │  │ (per stream/topic)│  │
│  └──────────────┘  └──────┬───────┘  └───────────────────┘  │
│                           │                                  │
│                    API calls to:                              │
│              GET /json/catch-up                               │
│              GET /json/catch-up/summary                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      Backend (Python/Django)                  │
│                                                              │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Inactivity      │  │ Message      │  │ Importance     │  │
│  │ Detector        │→ │ Aggregator   │→ │ Scorer         │  │
│  │ (presence data) │  │ (by stream/  │  │ (mentions,     │  │
│  │                 │  │  topic)      │  │  reactions,    │  │
│  │                 │  │              │  │  volume, etc.) │  │
│  └─────────────────┘  └──────┬───────┘  └───────┬────────┘  │
│                              │                   │           │
│                    ┌─────────▼───────────────────▼────────┐  │
│                    │ NLP Summarizer                       │  │
│                    │ (reuses do_summarize_narrow /        │  │
│                    │  extractive fallback)                │  │
│                    └─────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Implementation

### 3.1 Inactivity Detection

**Approach:** Use existing presence data rather than building a new tracking system.

**Data sources (in priority order):**
1. `UserPresence.last_active_time` — most recent user interaction timestamp
2. `UserActivityInterval` — 15-minute activity buckets (more reliable, not affected
   by `presence_enabled` setting)

**Logic:**
```python
def get_last_active_time(user_profile: UserProfile) -> datetime:
    """
    Returns the user's last active timestamp.
    
    Strategy:
    1. Check UserPresence.last_active_time
    2. Cross-reference with UserActivityInterval for accuracy
    3. Fall back to a configurable default (e.g., 24 hours ago)
    """
    try:
        presence = UserPresence.objects.get(user_profile=user_profile)
        if presence.last_active_time:
            return presence.last_active_time
    except UserPresence.DoesNotExist:
        pass
    
    # Fallback: most recent UserActivityInterval
    latest_interval = UserActivityInterval.objects.filter(
        user_profile=user_profile
    ).order_by('-end').first()
    
    if latest_interval:
        return latest_interval.end
    
    # Default: 24 hours ago
    return timezone_now() - timedelta(hours=24)
```

**Where to add this:**
- New file: `zerver/lib/catch_up.py` — core catch-up business logic

### 3.2 Message Aggregation

**Approach:** Query messages across all subscribed streams since last activity,
grouped by stream and topic.

**Key considerations:**
- Use existing `Subscription` model to find subscribed streams
- Use existing database indexes (`zerver_message_realm_recipient_date_sent`)
- Respect stream permissions and muting preferences
- Cap at a configurable maximum (e.g., 1000 messages) for performance

**Core query pattern (adapted from `digest.py`):**
```python
def get_catch_up_messages(
    user_profile: UserProfile,
    since: datetime,
    max_messages: int = 1000,
) -> dict[tuple[int, str], list[Message]]:
    """
    Returns messages grouped by (stream_id, topic_name) since the given time.
    """
    # Get subscribed, unmuted stream IDs
    subscribed_stream_ids = Subscription.objects.filter(
        user_profile=user_profile,
        recipient__type=Recipient.STREAM,
        active=True,
        is_muted=False,
    ).values_list('recipient__type_id', flat=True)
    
    messages = Message.objects.filter(
        realm_id=user_profile.realm_id,
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=subscribed_stream_ids,
        date_sent__gt=since,
    ).select_related('sender', 'recipient').order_by('id')[:max_messages]
    
    # Group by (stream_id, topic)
    grouped = defaultdict(list)
    for msg in messages:
        key = (msg.recipient.type_id, msg.topic_name())
        grouped[key].append(msg)
    
    return grouped
```

**Where to add this:**
- `zerver/lib/catch_up.py` — message aggregation functions

### 3.3 Importance Scoring

**Approach:** Heuristic-based scoring, inspired by `digest.py`'s `get_hot_topics()`,
but more granular.

**Scoring factors:**

| Factor | Weight | Description |
|---|---|---|
| Direct mentions (`@user`) | 5.0 | Messages that `@`-mention the user |
| Wildcard mentions (`@all`) | 3.0 | `@all` / `@everyone` mentions |
| Reply count | 1.0 | Number of messages in the topic (conversation depth) |
| Sender diversity | 1.5 | Number of unique human senders |
| Reactions count | 0.5 | Total reactions on messages in the topic |
| Recency | 0.5 | Boost for more recent activity |

**Implementation:**
```python
@dataclass
class TopicScore:
    stream_id: int
    stream_name: str
    topic_name: str
    score: float
    message_count: int
    sender_count: int
    has_mention: bool
    has_wildcard_mention: bool
    reaction_count: int
    latest_message_id: int
    sample_messages: list[dict]  # First few messages for preview

def score_topics(
    user_profile: UserProfile,
    grouped_messages: dict[tuple[int, str], list[Message]],
) -> list[TopicScore]:
    """Score and rank topics by importance."""
    ...
```

**Where to add this:**
- `zerver/lib/catch_up.py` — scoring logic

### 3.4 API Endpoints

#### Endpoint 1: `GET /json/catch-up` (Main catch-up data)

Returns aggregated, scored topic data since last activity.

**Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `since` | ISO datetime (optional) | auto-detected | Override last-active timestamp |
| `max_topics` | int | 20 | Maximum number of topics to return |
| `include_muted` | bool | false | Include muted streams/topics |

**Response:**
```json
{
    "result": "success",
    "msg": "",
    "last_active_time": "2025-02-10T08:00:00Z",
    "catch_up_period_hours": 14.5,
    "total_messages": 347,
    "total_topics": 42,
    "topics": [
        {
            "stream_id": 5,
            "stream_name": "engineering",
            "topic_name": "deploy plan Q1",
            "score": 18.5,
            "message_count": 23,
            "sender_count": 5,
            "senders": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "has_mention": true,
            "has_wildcard_mention": false,
            "reaction_count": 7,
            "latest_message_id": 98765,
            "first_message_id": 98700,
            "sample_messages": [
                {
                    "id": 98700,
                    "sender_full_name": "Alice",
                    "content": "I think we should target March 1...",
                    "date_sent": "2025-02-10T09:15:00Z"
                }
            ]
        }
    ]
}
```

**Implementation file:** `zerver/views/catch_up.py`

```python
@typed_endpoint
def get_catch_up(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    since: str | None = None,
    max_topics: Json[int] = 20,
    include_muted: Json[bool] = False,
) -> HttpResponse:
    ...
    return json_success(request, data={...})
```

#### Endpoint 2: `GET /json/catch-up/summary` (AI summary for a topic)

Generates an AI summary for a specific stream/topic within the catch-up period.
This reuses the existing `do_summarize_narrow()` infrastructure.

**Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `stream_id` | int | The stream to summarize |
| `topic_name` | str | The topic to summarize |
| `since` | ISO datetime (optional) | Start of catch-up period |

**Response:**
```json
{
    "result": "success",
    "msg": "",
    "summary": "<p>Alice proposed targeting March 1 for deployment...</p>"
}
```

**Implementation file:** `zerver/views/catch_up.py`

```python
@typed_endpoint
def get_catch_up_summary(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    stream_id: Json[int],
    topic_name: str,
    since: str | None = None,
) -> HttpResponse:
    # Reuse do_summarize_narrow() with a channel+topic narrow
    ...
```

#### URL Registration in `zproject/urls.py`

```python
# In v1_api_and_json_patterns:
rest_path("catch-up", GET=get_catch_up),
rest_path("catch-up/summary", GET=get_catch_up_summary),
```

### 3.5 Actions Layer

Following Zulip's separation of concerns (views → actions → models):

**New file:** `zerver/actions/catch_up.py`

```python
def do_get_catch_up_data(
    user_profile: UserProfile,
    since: datetime | None,
    max_topics: int,
    include_muted: bool,
) -> dict:
    """
    Main business logic for catch-up data.
    1. Determine last_active_time
    2. Aggregate messages since then
    3. Score and rank topics
    4. Return structured data
    """
    ...
```

---

## 4. Frontend Implementation

### 4.1 Navigation Entry (Left Sidebar)

**Add to `web/src/navigation_views.ts`:**

```typescript
catch_up: {
    fragment: "catch-up",
    name: $t({defaultMessage: "Catch up"}),
    is_pinned: true,
    icon: "zulip-icon-catch-up",  // New icon needed, or use existing one
    css_class_suffix: "catch_up",
    tooltip_template_id: "catch-up-tooltip-template",
    has_unread_count: false,
    unread_count_type: "",
    supports_masked_unread: false,
    hidden_for_spectators: true,
    menu_icon_class: "",
    menu_aria_label: "",
    home_view_code: "",
    prioritize_in_condensed_view: false,
},
```

### 4.2 URL Routing

**Modify `web/src/hashchange.ts`:**

Add to `do_hashchange_normal()` switch statement:
```typescript
case "#catch-up":
    catch_up_ui.show();
    break;
```

Add to the overlay hash check list (if catch-up should block overlay hashes):
```typescript
case "#catch-up":
    blueslip.error("overlay logic skipped for: " + hash[0]);
    break;
```

**Modify `web/src/hash_parser.ts`:**
- Ensure `#catch-up` is recognized as a valid normal (non-overlay) hash.

### 4.3 View Module

**New file: `web/src/catch_up_ui.ts`**

Following the pattern of `inbox_ui.ts` and `recent_view_ui.ts`:

```typescript
import * as views_util from "./views_util.ts";
import * as channel_data from "./channel_data.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";

let is_catch_up_visible = false;

export function show(): void {
    views_util.show({
        highlight_view_in_left_sidebar() {
            left_sidebar_navigation_area.highlight_catch_up_view();
        },
        $view: $("#catch-up-view"),
        update_compose: compose_closed_ui.update_buttons,
        is_visible: () => is_catch_up_visible,
        set_visible: (value: boolean) => { is_catch_up_visible = value; },
        complete_rerender,
    });
}

export function hide(): void {
    views_util.hide({
        $view: $("#catch-up-view"),
        set_visible: (value: boolean) => { is_catch_up_visible = value; },
    });
}

async function complete_rerender(): Promise<void> {
    // 1. Call GET /json/catch-up
    // 2. Render the catch-up dashboard with topic cards
    // 3. Set up event handlers for "summarize" buttons
}
```

**New file: `web/src/catch_up_data.ts`** (data/state management)

```typescript
export type CatchUpTopic = {
    stream_id: number;
    stream_name: string;
    topic_name: string;
    score: number;
    message_count: number;
    sender_count: number;
    senders: string[];
    has_mention: boolean;
    has_wildcard_mention: boolean;
    reaction_count: number;
    latest_message_id: number;
    first_message_id: number;
    sample_messages: SampleMessage[];
    summary?: string;  // Populated lazily when user clicks "Summarize"
};

export type CatchUpData = {
    last_active_time: string;
    catch_up_period_hours: number;
    total_messages: number;
    total_topics: number;
    topics: CatchUpTopic[];
};

let current_data: CatchUpData | undefined;

export async function fetch_catch_up_data(): Promise<CatchUpData> { ... }
export async function fetch_topic_summary(
    stream_id: number, topic_name: string
): Promise<string> { ... }
```

### 4.4 Templates

**New directory: `web/templates/catch_up_view/`**

**`catch_up_view.hbs`** — Main dashboard template:
```handlebars
<div id="catch-up-view" class="catch-up-view" style="display: none;">
    <div class="catch-up-header">
        <h1>{{t "What did I miss?"}}</h1>
        <p class="catch-up-subtitle">
            {{t "Here's what happened while you were away"}}
            ({{catch_up_period_display}})
        </p>
        <div class="catch-up-stats">
            <span>{{total_messages}} {{t "messages"}}</span>
            <span>{{total_topics}} {{t "topics"}}</span>
        </div>
    </div>
    <div class="catch-up-topics-container">
        {{#each topics}}
            {{> catch_up_topic_card}}
        {{/each}}
    </div>
</div>
```

**`catch_up_topic_card.hbs`** — Individual topic card:
```handlebars
<div class="catch-up-topic-card" data-stream-id="{{stream_id}}" data-topic="{{topic_name}}">
    <div class="catch-up-card-header">
        <span class="catch-up-stream-name">{{stream_name}}</span>
        <span class="catch-up-topic-separator">›</span>
        <span class="catch-up-topic-name">{{topic_name}}</span>
        {{#if has_mention}}
            <span class="catch-up-mention-badge">@</span>
        {{/if}}
        <span class="catch-up-message-count">{{message_count}} msgs</span>
    </div>
    <div class="catch-up-card-meta">
        <span class="catch-up-senders">{{sender_list}}</span>
    </div>
    <div class="catch-up-card-preview">
        {{#each sample_messages}}
            <div class="catch-up-preview-message">
                <strong>{{sender_full_name}}:</strong> {{content}}
            </div>
        {{/each}}
    </div>
    <div class="catch-up-card-actions">
        <a class="catch-up-open-topic" href="{{topic_url}}">{{t "Open topic"}}</a>
        <button class="catch-up-summarize-btn">{{t "Summarize"}}</button>
    </div>
    <div class="catch-up-summary-container" style="display: none;">
        <!-- Populated dynamically when "Summarize" is clicked -->
    </div>
</div>
```

### 4.5 Styles

**New file: `web/styles/catch_up.css`**

```css
/* Main catch-up view container, topic cards, importance badges,
   summary sections, responsive layout, dark theme support */
```

Import in `web/src/bundles/app.ts` or via webpack CSS imports.

### 4.6 Left Sidebar Integration

**Modify `web/src/left_sidebar_navigation_area.ts`:**
- Add `highlight_catch_up_view()` function
- Add catch-up entry to sidebar rendering

**Add tooltip template:** `web/templates/catch_up_tooltip.hbs`

---

## 5. NLP / Summarization Pipeline

### 5.1 Approach: Hybrid (Extractive + AI)

The system will support two summarization modes:

1. **Extractive (no AI required):** Select representative messages based on
   importance signals (mentions, reactions, replies). Always available.
2. **AI-powered (optional):** Reuse existing `do_summarize_narrow()` with LiteLLM.
   Only available when `TOPIC_SUMMARIZATION_MODEL` is configured.

### 5.2 Extractive Summarization (MVP)

**New file: `zerver/lib/catch_up_summarizer.py`**

```python
def extractive_summary(
    messages: list[Message],
    user_profile: UserProfile,
    max_sentences: int = 5,
) -> list[dict]:
    """
    Select the most important messages as an extractive summary.
    
    Strategy:
    1. Messages that @-mention the user (highest priority)
    2. Messages with the most reactions
    3. Messages that start new sub-threads (replies to previous)
    4. First and last messages in the topic (for context)
    """
    ...
```

### 5.3 AI Summarization (Reuse Existing)

For AI summaries, we construct a narrow for the specific stream+topic and call
the existing `do_summarize_narrow()`:

```python
from zerver.actions.message_summary import do_summarize_narrow

def ai_summarize_topic(
    user_profile: UserProfile,
    stream_id: int,
    topic_name: str,
) -> str | None:
    narrow = [
        NarrowParameter(operator="channel", operand=str(stream_id), negated=False),
        NarrowParameter(operator="topic", operand=topic_name, negated=False),
    ]
    return do_summarize_narrow(user_profile, narrow)
```

### 5.4 Future Enhancements (Post-MVP)

- **Action item detection:** Regex/NLP patterns for "TODO", "action item",
  "assigned to", task-like language
- **Decision detection:** Keywords like "decided", "agreed", "conclusion",
  "going with"
- **spaCy/NLTK integration:** For named entity recognition and keyword extraction

---

## 6. File-by-File Change Map

### New Files

| File | Purpose |
|---|---|
| **Backend** | |
| `zerver/lib/catch_up.py` | Core business logic: inactivity detection, message aggregation, importance scoring |
| `zerver/lib/catch_up_summarizer.py` | Extractive summarization logic |
| `zerver/actions/catch_up.py` | Action layer: orchestrates catch-up data generation |
| `zerver/views/catch_up.py` | API endpoint handlers |
| `zerver/tests/test_catch_up.py` | Backend tests |
| **Frontend** | |
| `web/src/catch_up_ui.ts` | View module: show/hide/render catch-up dashboard |
| `web/src/catch_up_data.ts` | Data fetching and state management |
| `web/templates/catch_up_view/catch_up_view.hbs` | Main dashboard template |
| `web/templates/catch_up_view/catch_up_topic_card.hbs` | Topic card template |
| `web/templates/catch_up_tooltip.hbs` | Sidebar tooltip template |
| `web/styles/catch_up.css` | Styles for catch-up view |
| `web/tests/catch_up_data.test.cjs` | Frontend unit tests |

### Modified Files

| File | Change |
|---|---|
| **Backend** | |
| `zproject/urls.py` | Register `catch-up` and `catch-up/summary` REST endpoints |
| **Frontend** | |
| `web/src/navigation_views.ts` | Add `catch_up` to `built_in_views_meta_data` |
| `web/src/hashchange.ts` | Add `#catch-up` case to `do_hashchange_normal()` and overlay hash list |
| `web/src/hash_parser.ts` | Recognize `#catch-up` as a valid hash (if needed) |
| `web/src/left_sidebar_navigation_area.ts` | Add `highlight_catch_up_view()` function |
| `web/src/bundles/app.ts` | Import catch-up CSS |
| `web/templates/left_sidebar.hbs` | Add catch-up entry (if not auto-generated from `navigation_views.ts`) |
| `static/assets/icons/` | Add catch-up icon (if a new icon is needed) |

---

## 7. Implementation Phases

### Phase 1: Backend Foundation (Sprint 2 — Weeks 3-4)

**Goal:** Working API endpoint that returns catch-up data.

1. **Create `zerver/lib/catch_up.py`**
   - `get_last_active_time(user_profile)` — inactivity detection
   - `get_catch_up_messages(user_profile, since, max_messages)` — message aggregation
   - `score_topics(user_profile, grouped_messages)` — importance scoring
   - `build_catch_up_response(user_profile, ...)` — assemble API response

2. **Create `zerver/actions/catch_up.py`**
   - `do_get_catch_up_data(user_profile, since, max_topics, include_muted)` — orchestrator

3. **Create `zerver/views/catch_up.py`**
   - `get_catch_up()` — main endpoint
   - `get_catch_up_summary()` — per-topic AI summary endpoint

4. **Register endpoints in `zproject/urls.py`**

5. **Create `zerver/tests/test_catch_up.py`**
   - Test inactivity detection
   - Test message aggregation across streams
   - Test importance scoring
   - Test API endpoint responses
   - Test permission checks

### Phase 2: Extractive Summarization (Sprint 3 — Weeks 5-6)

**Goal:** Basic summarization without requiring AI model configuration.

1. **Create `zerver/lib/catch_up_summarizer.py`**
   - Extractive summarization (select most important messages)
   - Keyword extraction (most frequent non-stopword terms)

2. **Integrate with catch-up endpoint**
   - Add `include_extractive_summary` parameter
   - Return selected key messages per topic

3. **Integrate AI summarization (reuse existing)**
   - Wire `get_catch_up_summary` endpoint to `do_summarize_narrow()`
   - Handle credit checking and permissions

### Phase 3: Frontend — View Infrastructure (Sprint 4 — Weeks 7-8)

**Goal:** Working catch-up view accessible from sidebar.

1. **Create navigation entry**
   - Add to `navigation_views.ts`
   - Add to left sidebar
   - Add icon

2. **Create routing**
   - Add `#catch-up` hash handling in `hashchange.ts`

3. **Create view module**
   - `catch_up_ui.ts` — show/hide/render
   - `catch_up_data.ts` — API calls and state

4. **Create templates**
   - `catch_up_view.hbs` — main layout
   - `catch_up_topic_card.hbs` — topic cards

5. **Create styles**
   - `catch_up.css` — responsive layout, cards, badges

### Phase 4: Frontend — Interactive Features (Sprint 4 continued)

**Goal:** Full interactivity — summarize buttons, topic links, filtering.

1. **"Summarize" button per topic**
   - Calls `GET /json/catch-up/summary`
   - Shows loading state, then rendered summary

2. **Topic links**
   - "Open topic" links to `#narrow/channel/ID/topic/NAME`

3. **Filtering**
   - Filter by stream
   - Filter by "mentions only" / "high importance"

4. **Keyboard navigation**
   - Arrow keys to navigate between topic cards
   - Enter to expand/open topic

### Phase 5: Refinement (Sprint 5 — Weeks 9-10)

1. **Improve importance scoring** based on testing feedback
2. **Add user preferences** (configurable inactivity threshold)
3. **Performance optimization** (caching, query optimization)
4. **Usability testing** and UI refinements

### Phase 6: Testing & Polish (Sprint 6 — Weeks 11-12)

1. **Comprehensive test suite** (backend + frontend)
2. **Edge cases** (no messages, very long absence, new user)
3. **Dark theme** support
4. **Accessibility** (screen reader, keyboard nav)
5. **Documentation**

---

## 8. Testing Strategy

### Backend Tests (`zerver/tests/test_catch_up.py`)

```python
class CatchUpTest(ZulipTestCase):
    def test_get_last_active_time_from_presence(self) -> None: ...
    def test_get_last_active_time_fallback_to_activity_interval(self) -> None: ...
    def test_get_last_active_time_default(self) -> None: ...
    
    def test_message_aggregation_respects_subscriptions(self) -> None: ...
    def test_message_aggregation_excludes_muted_streams(self) -> None: ...
    def test_message_aggregation_respects_time_range(self) -> None: ...
    def test_message_aggregation_caps_at_max_messages(self) -> None: ...
    
    def test_importance_scoring_mentions_highest(self) -> None: ...
    def test_importance_scoring_diversity_factor(self) -> None: ...
    def test_importance_scoring_reaction_factor(self) -> None: ...
    
    def test_catch_up_endpoint_success(self) -> None: ...
    def test_catch_up_endpoint_with_since_param(self) -> None: ...
    def test_catch_up_endpoint_unauthenticated(self) -> None: ...
    def test_catch_up_endpoint_no_messages(self) -> None: ...
    
    def test_catch_up_summary_endpoint(self) -> None: ...
    def test_catch_up_summary_requires_ai_enabled(self) -> None: ...
```

**Testing patterns** (follow Zulip conventions):
- Use `self.example_user("hamlet")` for test users
- Use `self.client_get("/json/catch-up", {...})` for endpoint tests
- Use `self.assert_json_success(result)` / `self.assert_json_error(result, msg)` for assertions
- Use `self.subscribe(user, "stream_name")` to set up subscriptions
- Use `self.send_stream_message(sender, "stream_name", topic_name="topic", content="...")` for test messages

### Frontend Tests (`web/tests/catch_up_data.test.cjs`)

- Test data transformation/formatting
- Test importance score sorting
- Test filtering logic

---

## 9. Open Questions & Decisions

### 9.1 Design Decisions to Make

| Question | Options | Recommendation |
|---|---|---|
| **Where in sidebar?** | Top-level pinned view vs. collapsible section | Top-level pinned view (like Inbox) — most visible |
| **Trigger mechanism?** | Auto-popup on return vs. manual navigation | Manual navigation (sidebar click) — less intrusive. Consider a subtle notification badge when catch-up data is available. |
| **Inactivity threshold?** | Fixed (e.g., 4 hours) vs. configurable | Start with configurable, default 4 hours. Store in user settings or use a sensible heuristic. |
| **AI summaries?** | Per-topic on-demand vs. pre-generated | On-demand (user clicks "Summarize") — saves AI credits, faster initial load |
| **Summary approach?** | Only AI vs. only extractive vs. hybrid | Hybrid: always show extractive (key messages), offer AI summary button when available |
| **Direct messages?** | Include DMs in catch-up vs. streams only | Start with streams only (MVP), add DMs in Phase 5 |
| **Max absence period?** | No limit vs. cap at N days | Cap at 7 days to prevent overwhelming data loads |

### 9.2 Dependencies on Existing Configuration

| Dependency | Required? | Notes |
|---|---|---|
| `TOPIC_SUMMARIZATION_MODEL` | No (for MVP) | Only needed for AI summaries; extractive works without it |
| `TOPIC_SUMMARIZATION_API_KEY` | No (for MVP) | Same as above |
| User `presence_enabled` | No | We fall back to `UserActivityInterval` |
| Stream permissions | Yes | Must respect private stream access |

### 9.3 Performance Considerations

- **Database queries:** Use existing indexes. The `zerver_message_realm_recipient_date_sent` index is ideal for time-range + stream queries.
- **Message cap:** Limit to 1000 messages per catch-up request. If exceeded, show "showing top N topics" message.
- **Lazy loading:** Don't generate AI summaries upfront. Load them on-demand per topic.
- **Caching:** Consider caching catch-up results for a short TTL (e.g., 5 minutes) since the data doesn't change rapidly.
- **Target:** < 5 seconds for catch-up data with up to 500 messages.

### 9.4 Privacy & Security

- All processing is server-side within Zulip's existing security model
- No messages sent to external services (except AI model if configured)
- Existing stream permission checks are reused
- Guest user access is properly restricted via subscription checks
- AI summaries respect `can_summarize_topics()` permission
