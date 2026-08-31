# Implementation Report: LLM-Enabled Features for Zulip
**Course:** 17-445/17-645/17-745 Machine Learning in Production  
**Assignment:** Individual Assignment 1: Building LLM-enabled Features for a Product  

---

## Demo Video Links
- **Feature 1 (Message Recap) & Feature 2 (Topic Title Improver) Video:** [(Google Drive Link to Demo Video)](https://drive.google.com/drive/folders/1aSEvk1AmbyjFEE37krOTLbl6MXHnUGPj?usp=drive_link)

---

## Feature 1: Message Recap

### 1. Overview & Objective
Zulip organizes communication into channels (streams) and topics. When users return after being away, reviewing dozens or hundreds of unread messages across multiple topics is time-consuming. The **Message Recap** feature generates a concise, multi-conversation summary of all unread messages for the user on a single page, complete with clickable deep-links directly navigating to original messages.

---

### 2. Backend Implementation

#### Key Files & Code Pointers:
- [**`zerver/views/message_recap.py`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/views/message_recap.py): Contains the API endpoint [`get_messages_recap`](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/views/message_recap.py#L15). Handles authentication, AI permission verification (`can_summarize_topics()`), monthly AI credit limit enforcement, and error reporting.
- [**`zerver/actions/message_recap.py`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/message_recap.py): Implements the core business logic [`do_generate_recap()`](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/message_recap.py#L108):
  - Fetches all unread messages for the user using [`get_raw_unread_data()`](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/message_recap.py#L114).
  - Retrieves full message contents and metadata via [`messages_for_ids()`](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/message_recap.py#L131).
  - Groups messages by conversation (Stream + Topic or DM participants) in [`format_messages_for_recap_prompt()`](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/message_recap.py#L60).
  - Calls the configured OpenAI-compatible LLM endpoint (Groq / Gemini / OpenAI) using `client.chat.completions.create()`.
  - Tracks token usage and AI inference runtime using Zulip's [`ai_stats_start()`](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/message_recap.py#L149) / [`ai_stats_finish()`](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/message_recap.py#L167) and increments [`COUNT_STATS["ai_credit_usage::day"]`](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/message_recap.py#L170).
  - Converts the returned CommonMark text to safe rendered HTML via [`markdown_convert()`](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/message_recap.py#L199).
- [**`zproject/urls.py`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/zproject/urls.py): Registers the route `messages/recap` for `GET` requests (mapped to both `/api/v1/messages/recap` and `/json/messages/recap`).
- [**`zerver/tests/test_message_recap.py`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/tests/test_message_recap.py): Automated test suite verifying recap generation, link generation, permission checks, and AI credit limits.

#### How Message Links are Created:
To ensure the LLM outputs 100% valid navigation links, the backend pre-computes relative Zulip narrow URLs before invoking the model:
1. For channel/stream messages, [`get_message_link()`](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/message_recap.py#L45) calls `stream_message_url(realm=None, message=msg, include_base_url=False)`, producing:
   `#narrow/channel/{stream_id}-{stream_name}/topic/{encoded_topic}/near/{message_id}`
2. For direct messages, it calls `encode_user_ids()` to construct:
   `#narrow/dm/{user_ids_slug}/near/{message_id}`
3. The prompt explicitly feeds each message with its corresponding URL (`- [Message 101] Alice: "..." (Link: #narrow/...)`) and instructs the LLM to embed Markdown reference links in its summary bullets.
4. When clicked in the frontend single-page application, these `#narrow` fragments trigger Zulip's native hash routing and jump directly to the target message in its conversation context.

---

### 3. Frontend Integration
- [**`web/src/message_recap.ts`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/web/src/message_recap.ts): Launches the interactive `dialog_widget` modal with a live loading spinner (`loading.make_indicator`), fetches `/json/messages/recap`, renders the returned HTML, and hooks click handlers to dismiss the modal and jump directly to messages when links are clicked.
- [**`web/templates/message_recap.hbs`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/web/templates/message_recap.hbs): Handlebars template using the `{{rendered_markdown recap_markdown}}` helper.
- [**`web/src/click_handlers.ts`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/web/src/click_handlers.ts#L1164): Global delegated click listener on `.message-recap-button` to open the recap modal from anywhere in the UI.
- [**`web/templates/left_sidebar.hbs`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/web/templates/left_sidebar.hbs#L43): "Message recap" navigation item with magic-wand icon in the left sidebar under Views.
- [**`web/templates/inbox_view/inbox_view.hbs`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/web/templates/inbox_view/inbox_view.hbs#L12): "Recap" button added directly into the Inbox search/filter header bar.

---

## Feature 2: Topic Title Improver

### 1. Overview & Objective
In Zulip, topic threads frequently evolve away from their original titles as discussions progress (e.g. an initial thread titled *"Server Deployment"* transitions into a deep technical debate on *"Database Index Optimization"*). The **Topic Title Improver** feature uses an LLM to detect topic drift soon after it occurs—specifically when a user posts a message—and suggests an improved, representative topic title with a 1-click action to update the topic.

---

### 2. Backend Implementation

#### Key Files & Code Pointers:
- [**`zerver/views/topic_drift.py`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/views/topic_drift.py): Exposes `POST /json/topics/check_drift` (and `POST /api/v1/topics/check_drift`). Validates authentication, channel permissions, and user credit quotas.
- [**`zerver/actions/topic_drift.py`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/topic_drift.py): Implements [`do_check_topic_drift()`](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/actions/topic_drift.py#L48):
  - Fetches the last up to 15 messages in the topic using `messages_for_topic()`.
  - Analyzes the semantic alignment between the conversation messages and current topic title.
  - Queries the LLM with a system prompt instructing compact structured JSON output (`{"has_drift": bool, "suggested_title": str | null}`).
  - Tracks token usage and AI inference runtime using `ai_stats_start()` / `ai_stats_finish()`.
- [**`zproject/urls.py`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/zproject/urls.py): Registers the `topics/check_drift` route.
- [**`zerver/tests/test_topic_drift.py`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/zerver/tests/test_topic_drift.py): Automated test suite covering drift detection, on-topic negative cases, short topic skipping, permission denial, and credit limits.

---

### 3. Latency, Cost, and Scalability Considerations

1. **Short Topic Thresholding (< 2 Messages)**:
   - Threads with fewer than 2 messages skip LLM inference entirely (`len(messages) < 2`), returning `has_drift: False` instantly with 0ms LLM latency and zero API cost.
2. **In-Memory Cooldown & Debounce Caching**:
   - To handle rapid bursts of chat activity without redundant LLM calls, an in-memory cache `_drift_cache` keys evaluations by `(stream_id, topic_name)` with a 30-second cooldown. If multiple messages are posted in succession without changing context, cached results are returned immediately.
3. **Bounded Context & Compact Output (Token Optimization)**:
   - We bound input history to the `MAX_MESSAGES_FOR_DRIFT = 15` most recent messages and constrain the LLM completion to `max_tokens = 150` with JSON output mode. By requesting only `{"has_drift": bool, "suggested_title": str}`, we eliminate verbose explanatory text, reducing output token consumption by ~60-70% per call while maintaining low inference latency.
4. **Scalability in Production**:
   - In high-throughput production deployments with thousands of concurrent channels, drift detection calls can be dispatched asynchronously to background Celery workers (`zerver/worker/`) or event queues (RabbitMQ), notifying the client over the server-sent events stream (`/json/events`) to decouple message transmission from LLM latency.

---

### 4. Frontend Integration

#### Key Files & Code Pointers:
- [**`web/src/topic_drift.ts`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/web/src/topic_drift.ts):
  - `check_topic_drift_for_sent_message(stream_id, topic_name, message_id)`: Asynchronously evaluates drift when a message is posted.
  - `show_topic_drift_banner(data)`: Renders an interactive warning compose banner using `render_compose_banner` with the drift reason and a 1-click **"Rename topic to '[suggested_title]'"** action button.
  - `rename_topic_to_suggested(stream_id, old_title, new_title, message_id)`: Invokes `channel.patch(/json/messages/<id>)` with `propagate_mode: "change_all"` to update the topic title across all messages in the thread.
  - `improve_topic_title_interactive(stream_id, topic_name)`: On-demand modal dialog for manual evaluation with a live spinner, editable title input, and "Update Topic Title" action button.
- [**`web/src/compose.ts`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/web/src/compose.ts#L143): Triggers `check_topic_drift_for_sent_message()` immediately in `send_message_success` when a user posts a message to a stream topic.
- [**`web/src/compose_banner.ts`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/web/src/compose_banner.ts#L43): Added `topic_drift_suggestion` class to banner manager.
- [**`web/templates/popovers/left_sidebar/left_sidebar_topic_actions_popover.hbs`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/web/templates/popovers/left_sidebar/left_sidebar_topic_actions_popover.hbs#L50): Added **"Improve topic title (AI)"** option in the topic actions popover menu for manual on-demand triggers.
- [**`web/src/topic_popover.ts`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/web/src/topic_popover.ts#L310): Click handler for manual topic title improvement from the sidebar menu.
