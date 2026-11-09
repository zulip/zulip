# ADR 001: Transactional explicit mention notifications

Status: backend, concurrency, Node and migration validation passed. Browser
integration and human review remain pending.
Updated: 2026-11-09.

## Context and decision

An author may want to notify someone without changing their subscriptions.
The existing subscribe action is independent and retains its permissions.
Notify is offered only in the new web composer. A toggle button's `aria-pressed`
state on its recipient/channel banner stores intent. Removing the banner clears
intent; input revalidates mentions, recipient changes deselect, and composer
clear/cancel hooks remove banners. An invalidation generation prevents an old
subscriber fetch from restoring a warning after a composer reset.

The selected IDs travel with `POST /messages` in `notify_mentioned_user_ids`.
Local echo copies the request, retaining its recipient selection for a retry of
that message rather than consulting the current composer. Selection is not saved
in drafts or scheduled messages. Editing does not create notifications.

The existing authenticated send path authorizes and persists the original.
For a nonempty Notify selection, the send endpoint opens a durable transaction.
Inside it, `notify_unsubscribed_mention` locks that
original and checks its author, active same-organization human recipient,
unsubscribed status, canonical individual Markdown mention, join permission,
and access to the specific message. Guests are excluded using current rules.
Public/web-public channels allow non-guests; private channels additionally
require the recipient's own content-access group permission and history access,
using `is_user_in_groups_granting_content_access` (`can_subscribe_group` or
`can_add_subscribers_group`).
Permission to add other subscribers is not notification eligibility.

Ineligible recipients are silently skipped; the ordinary message still succeeds.
This covers changes between selection and delivery. Authorization is evaluated
at delivery, with existing access helpers; no new permission policy is added.
Policy mutations racing after those reads retain existing Zulip transaction
semantics; this increment does not serialize all organization policy writes.

## Atomicity and duplicates

Migration `0816_mentionnotification` adds a unique `(message, recipient)` record.
The original row lock serializes competing deliveries on separate connections;
the unique constraint is the durable backstop. The delivery record and the
Notification Bot DM are created in the same transaction. A raised exception or
a helper returning no DM rolls back the record and original too. Existing
message events are emitted on commit, so a rollback exposes neither message.
There is no new asynchronous consumer or callback-only delivery guarantee.

Repeated delivery of the same persisted original produces no second DM.
Two distinct originals can each produce one DM, even if their content matches.
This does not make POST /messages itself idempotent after a lost response.
Deleting an original cascades its delivery records; originals are not recreated
with the same primary key through this feature.

The transaction is conditional because the ordinary send path deliberately
persists some bot-owner error notices before rejecting an original send.
Wrapping every request rolled those notices back. The existing
`test_message_to_stream_with_nonexistent_id` caught that regression. Requests
without selected recipients retain their existing transaction boundaries.

## Alternatives and risks

A follow-up browser request permits lost intent after successful send and requires
additional authorization on client-provided message IDs. An asynchronous outbox
requires a worker, durable intent, retry handling, and another permission check.
The synchronous transaction is smaller but adds rendering and DM latency to send;
load testing remains pending. The quote uses the existing quote composer and
escaped link-label helper, not text supplied separately by the client.

The migration is additive; applying it and validating its state on supported
PostgreSQL remains required before acceptance. No destructive schema change or
new deployment service is required.

## Verification

`zerver/tests/test_mention_notification.py` covers opt-in, canonical mentions,
eligibility, unchanged subscriptions, subscribed-user regression, rollback,
sequential deduplication, and a two-thread/two-connection delivery race using
`ZulipTransactionTestCase`. Web banner tests extend `compose_validate.test.cjs`.
The PostgreSQL backend run passed 134 tests with transaction tests included.
The full Node suite and migration consistency check passed. Browser integration
is being verified with `web/e2e-tests/mention-notification.test.ts`. See
[AV2 evidence](../evidence/av2.md) for exact blockers and remaining checks.
