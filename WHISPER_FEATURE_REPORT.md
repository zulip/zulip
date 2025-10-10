## Whisper Side-Chat Feature — Technical Report

This document describes the whisper side-chat feature implemented in this repository: goals, data model, core logic, REST API endpoints, request/response examples, permissions and rate limiting rules, testing guidance, and next steps for full integration (messages, real-time events, and UI).

### 1) Problem Statement and Workflow

- Goal: Allow a subset of users within an existing group conversation (public stream, private stream, or group DM) to talk privately while remaining in the group context. This opens a small side-chat visible only to selected participants.
- Workflow:
  1. A participant in a parent conversation sends a whisper request to one or more users who also have access to that parent conversation.
  2. The recipients accept or decline.
  3. Upon acceptance, a whisper conversation is created and a side-chat opens, accessible only to its participants, scoped to the parent conversation.
  4. Participants can join/leave; the conversation auto-closes when participants drop below 2.

Key constraints:
- Everyone in the whisper must have permission to read the parent conversation.
- Whisper conversations are logically scoped under a specific parent `Recipient` (stream or group DM).
- A participant hash identifies unique sets of participants within a parent conversation to avoid duplicate conversations.

### 2) Data Model

Defined in `zerver/models/whispers.py`:

- `WhisperConversation`
  - Fields: `id`, `parent_recipient` (FK to `Recipient`), `realm`, `created_by`, `created_at`, `is_active`, `participants_hash` (SHA1 of sorted participant IDs).
  - Indexes for efficient lookups by realm/parent and participants hash.
  - Helper: `get_participant_ids()` returns active participant user IDs.

- `WhisperRequest`
  - Fields: `id`, `requester`, `recipient`, `parent_recipient`, `realm`, `created_at`, `status` (`PENDING`, `ACCEPTED`, `DECLINED`, `EXPIRED`), `whisper_conversation` (nullable FK).
  - Indexes for recipient/status, requester/status, realm/created_at.
  - Unique constraint to avoid duplicates in the same context.

- `WhisperParticipant`
  - Fields: `id`, `whisper_conversation`, `user_profile`, `joined_at`, `left_at`, `is_active`.
  - Indexes for active lookups by conversation and by user.
  - Unique constraint `(whisper_conversation, user_profile)`.

Recipient and message support:
- `Recipient.WHISPER = 4` with optional `parent_recipient` pointer to the parent conversation (`zerver/models/recipients.py`).
- `Message` supports optional FK `whisper_conversation` to tag messages belonging to a whisper (`zerver/models/messages.py`).

### 3) Core Library Logic

Implemented in `zerver/lib/whispers.py`:

- Validation and permissions
  - `validate_whisper_participants(requesting_user, participant_user_ids, parent_recipient)` ensures all participants are active and have access to the parent conversation; validates reasonable participant limits; prevents self-only.
  - `has_access_to_recipient(user, recipient)` checks stream subscriptions or DM group membership.

- Conversation management
  - `create_whisper_conversation(requesting_user, participant_user_ids, parent_recipient)` validates and creates a conversation and participant rows atomically, reusing an existing active conversation when the participant hash matches.
  - `add_participant_to_whisper(...)`, `remove_participant_from_whisper(...)`, `is_whisper_participant(...)`.
  - `get_active_whisper_conversation(parent_recipient, user_ids)`, `get_whisper_participants_hash(user_ids)`, `update_whisper_participants_hash(...)`.

- Requests workflow
  - `create_whisper_request(requester, recipient, parent_recipient, proposed_participants)` prevents duplicates and checks existing conversations.
  - `respond_to_whisper_request(whisper_request, responding_user, accept, additional_participants=None)` updates status and creates the conversation on accept.
  - `get_pending_whisper_requests_for_user(user)`, `get_sent_whisper_requests_for_user(user)`, `get_whisper_request_by_id(id, user)`, `cancel_whisper_request(...)`.

- Cleanup and stats
  - `cleanup_expired_whisper_requests(realm, hours=24)`, `cleanup_inactive_whisper_conversations(realm, days=7)`.
  - `bulk_expire_whisper_requests_for_conversation(conversation)`, `get_whisper_request_stats_for_user(user)`.

### 4) REST API Endpoints

Views defined in `zerver/views/whispers.py` and routed in `zproject/urls.py` via `rest_path`.

- Requests
  - `POST /json/whispers/requests` → `create_whisper_request_backend`
    - Body: `{ "recipient_id": number, "parent_recipient_id": number, "proposed_participants": number[] }`
    - Returns: `{ request: WhisperRequest }`
  - `GET /json/whispers/requests` → `list_pending_whisper_requests_backend`
    - Returns: `{ requests: WhisperRequest[] }` (pending for current user)
  - `GET /json/whispers/requests/sent` → `list_sent_whisper_requests_backend`
    - Returns: `{ requests: WhisperRequest[] }` (sent by current user)
  - `POST /json/whispers/requests/<request_id>` → `respond_whisper_request_backend`
    - Body: `{ "accept": boolean, "additional_participants"?: number[] }`
    - Returns: `{ request: WhisperRequest, conversation?: WhisperConversation }`
  - `DELETE /json/whispers/requests/<request_id>` → `cancel_whisper_request_backend`
    - Returns: `{ request: WhisperRequest }`

- Conversations
  - `GET /json/whispers/conversations` → `list_whisper_conversations_backend`
    - Optional query: `parent_recipient_id=<id>`
    - Returns: `{ conversations: WhisperConversation[] }` for current user
  - `POST /json/whispers/conversations` → `create_whisper_conversation_backend`
    - Body: `{ "participant_user_ids": number[], "parent_recipient_id": number }`
    - Returns: `{ conversation: WhisperConversation }`
  - `GET /json/whispers/conversations/<conversation_id>/participants` → `list_whisper_conversation_participants_backend`
    - Returns: `{ participants: User[] }`
  - `POST /json/whispers/conversations/<conversation_id>/participants` → `add_whisper_participant_backend`
    - Body: `{ "participant_id": number }`
    - Returns: `{ participant: User }`
  - `DELETE /json/whispers/conversations/<conversation_id>/participants` → `remove_whisper_participant_backend`
    - Body: `{ "participant_id"?: number }` (if omitted, the requester leaves)
    - Returns: `{ active: boolean }` (false if conversation closed)

Serialization helpers in `zerver/views/whispers.py` return concise JSON for `UserProfile`, `Recipient`, `WhisperRequest`, and `WhisperConversation`.

### 5) Example Requests

Create a whisper request:
```bash
curl -s -u you@example.com:API_KEY -X POST \
  -H "Content-Type: application/json" \
  -d '{"recipient_id": 12, "parent_recipient_id": 345, "proposed_participants":[1,12]}' \
  http://localhost:9991/json/whispers/requests
```

Accept a request (with an additional participant):
```bash
curl -s -u you@example.com:API_KEY -X POST \
  -H "Content-Type: application/json" \
  -d '{"accept": true, "additional_participants":[34]}' \
  http://localhost:9991/json/whispers/requests/REQ_ID
```

List your whisper conversations:
```bash
curl -s -u you@example.com:API_KEY \
  http://localhost:9991/json/whispers/conversations
```

Manage participants:
```bash
# Add
curl -s -u you@example.com:API_KEY -X POST -H "Content-Type: application/json" \
  -d '{"participant_id": 56}' \
  http://localhost:9991/json/whispers/conversations/CONV_ID/participants

# Remove
curl -s -u you@example.com:API_KEY -X DELETE -H "Content-Type: application/json" \
  -d '{"participant_id": 56}' \
  http://localhost:9991/json/whispers/conversations/CONV_ID/participants
```

### 6) Permissions and Rate Limiting

- Permissions enforced via library:
  - All participants (including requester and recipient) must have access to the parent `Recipient` (stream subscription or DM group membership).
  - Only whisper participants can add/remove participants; removing others is restricted to the conversation creator.
  - Conversations auto-close if active participants ≤ 1.

- Rate Limiting:
  - `validate_whisper_request_rate_limit(requester, recipient, time_window_minutes=60, max_requests=5)` provides basic controls (extendable).

### 7) Testing

- Quick tests (no full setup):
  - `python zulip/test_whisper_simple.py` — 6/6 checks pass.
  - `python zulip/test_whisper_standalone.py` — validates structures; may require dev dependencies (e.g., `django_stubs_ext`) when run outside full dev environment.

- Full backend tests (after dev setup and migrations):
```bash
cd zulip
python manage.py migrate
./tools/test-backend zerver.tests.test_whispers
./tools/test-backend zerver.tests.test_whisper_lib
./tools/test-backend zerver.tests.test_whisper_requests
```

Reference docs: `zulip/WHISPER_TESTING_GUIDE.md`.

### 8) Integration Plan (Next Steps)

- Message integration
  - Allow composing messages with `whisper_conversation_id`; set `Message.whisper_conversation` and ensure delivery only to whisper participants.
  - Enforce visibility in message fetch endpoints so only participants see whisper-tagged messages.

- Real-time events
  - Emit events for whisper request create/accept/decline/cancel and for whisper conversation messages.
  - Update Tornado event queues and clients to subscribe to whisper events per conversation.

- Frontend UI
  - Request flow (send/accept/decline), conversation list, side-pane/thread UI in parent conversation, participant management.
  - Indicators in parent conversation when a whisper exists for current user.

- Security & policy
  - Org-level settings (enable/disable whisper, participant caps, rate limits, audit logs).

### 9) Known Limitations

- REST API present, but message-level enforcement and UI are pending.
- Real-time notifications/events not yet wired.
- Admin moderation tooling not yet specified (could be added based on policy decisions).

### 10) File Inventory (Key Files)

- Models: `zerver/models/whispers.py`
- Library/Logic: `zerver/lib/whispers.py`
- Views/API: `zerver/views/whispers.py`
- Routes: `zproject/urls.py`
- Tests: `zerver/tests/test_whispers.py`, `zerver/tests/test_whisper_lib.py`, `zerver/tests/test_whisper_requests.py`
- Guides: `WHISPER_TESTING_GUIDE.md`, `test_whisper_simple.py`, `test_whisper_standalone.py`

— End of Report —


