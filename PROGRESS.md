# What Did I Miss? — Progress Tracker

> **Project:** AI-powered catch-up feature for Zulip
> **Repository:** [zulip-what-did-i-miss](https://github.com/CtrlAltGiri/zulip-what-did-i-miss)
> **Last Updated:** 2026-02-10

---

## Overall Status

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Backend Foundation | **COMPLETE** |
| **Phase 2** | Extractive Summarization | **COMPLETE** |
| Phase 3 | Frontend — View Infrastructure | Not Started |
| Phase 4 | Frontend — Interactive Features | Not Started |
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

## Phase 3–6: Upcoming

See [PLAN.md](./PLAN.md) for detailed plans for frontend implementation,
interactive features, refinement, and testing/polish.
