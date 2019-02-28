# Roles and permissions

There are several roles in a Zulip organization.

* **Organization Administrator**: Can manage users, public streams,
  organization settings, and billing.

* **Member**: Has access to all public streams. This is the default role for
  most users.

* **Guest**: Can only access streams they've been added to. Cannot create
  new streams.

## Billing and guests

Guests are only available on Zulip on-premise and on paid plans for Zulip
Cloud. There are two kinds of guest for billing purposes:

* **Multi-stream guest**: Has been added to multiple streams. These guests
  are billed the same as regular members.

* **Single-stream guest**: Has been added to only a single stream. If you
  have M paying users, you get 5M free single-stream guests. Similarly, if
  you have G single-stream guests, you'll get charged for G/5 users.

  Example: You have 8 members, 2 multi-stream guests, and 50 single-stream
  guests. You'll get charged for 10 users. Let's say you have 8 members, 2
  multi-stream guests, and 51 single-stream guests. You'll get charged for
  11 users.

  Single-stream guests are a new feature, and their permissions are likely
  to change over time. For example, single-stream guests can currently see
  the list of members in the organization, but we may remove that ability in
  the future.

## Related articles

* [Stream permissions](/help/stream-permissions)
