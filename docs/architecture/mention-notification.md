# Explicit notifications for unsubscribed mentions

CoreX AV2 implementation for [Zulip #7719](https://github.com/zulip/zulip/issues/7719).
See [ADR 001](adr-001-mention-notification.md) and [execution evidence](../evidence/av2.md).
The reported `docs/architecture/context.md` C4 Level 1 diagram was absent in
this checkout. No existing context diagram was replaced.

```mermaid
sequenceDiagram
    actor Author
    participant UI as Web compose
    participant Server as Zulip send endpoint
    participant DB as PostgreSQL
    participant Bot as Internal Notification Bot
    participant Events as Existing Zulip event delivery
    actor Recipient
    Author->>UI: Mention an individual
    UI-->>Author: Warning, Notify them, separate Subscribe them
    Author->>UI: Explicitly select Notify them
    Note over UI: Draft banner stores selection until send
    Author->>UI: Send
    UI->>Server: Message content and selected recipient IDs
    rect rgb(235, 240, 245)
        Note over Server,DB: One durable transaction for explicit Notify
        Server->>Server: Existing authenticated send authorization
        alt Original send fails
            Server->>DB: Roll back
            Server-->>UI: Existing send error with no DM
        else Original send succeeds
            Server->>DB: Persist original message
            Server->>DB: Lock persisted original with SELECT FOR UPDATE
            Server->>Server: Check author, active same-realm recipient, individual Markdown mention
            Server->>DB: Check subscription, current join permission and message access
            alt Ineligible or authorization revoked
                Note over Server: Skip recipient without disclosing metadata
            else Eligible
                Server->>DB: Get or create unique message-recipient delivery row
                alt Repeated delivery
                    DB-->>Server: Existing row, skip DM
                else First delivery
                    Server->>Server: Build link and quoted content from persisted message
                    Server->>Bot: Existing internal private-message helper
                    Bot->>DB: Persist DM and recipient receipt
                    Note over Server,DB: Any delivery exception rolls back original, record and DM
                end
            end
            Server->>DB: Commit original and any DM together
            opt Commit included a bot DM
                Server->>Events: Existing on-commit message events
                Events-->>Recipient: Expose Notification Bot DM
            end
            Server-->>UI: Successful original message response
        end
    end
```

No new queue, worker, bot account, or external service is introduced. Existing
message events and external-notification jobs retain Zulip's on-commit behavior.
The database uniqueness constraint and original-message row lock apply across
processes; this is not a browser-only deduplication flag.

Mermaid syntax and SVG rendering were verified with Mermaid CLI 12.2.0 inside
the Linux test container on 2026-11-09. The editable sequence above is the source.
