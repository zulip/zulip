---
orphan: true
---

# Miatsu.co changelog

The Miatsu.co release history — what shipped in each release and the **upgrade
notes** for deploying it. This is the operator-facing log, the fork's analogue of
Zulip's [Version history](../overview/changelog.md); the client-facing **API
changelog** is `api_docs/miatsu-changelog.md` (served at `/api/miatsu-changelog`).

It complements:

- `api_docs/miatsu-changelog.md` — the client-facing API changelog (what changed
  in the API and observable behavior; for client and integration authors).
- [`release-lifecycle.md`](release-lifecycle.md) — the general deploy, rollback,
  and migration process (read once).

Each release records the upstream Zulip base it is built on (see
[What a release is](release-lifecycle.md#what-a-release-is)).

## Miatsu.co 0.1-dev

_Unreleased._ Based on the upstream Zulip 12.x maintenance branch (feature level 499).

### Highlights

- Establishes the fork's versioning, capability-flag, and changelog conventions.
- Adds the owner-settable `can_view_user_direct_messages_group` realm permission —
  the foundation for admin viewing of users' direct messages.

### Upgrade notes

- **Database:** applies migrations `0802`–`0804`, which add the
  `can_view_user_direct_messages_group` column to `zerver_realm` (add nullable →
  backfill to the system "nobody" group → make non-null). No new Python or
  JavaScript dependencies, so no re-provision is required.
- **Rollback:** the new column is `NOT NULL` with no database default, so rolling
  back to a _pre-fork (stock upstream)_ deployment is **not** a clean symlink
  swap — stock code would fail to create new realms (it can't populate the
  column). Reverse the migration or restore a pre-0.1 backup first. Rolling back
  between Miatsu.co releases that both have the column is unaffected. See
  [Rollback](release-lifecycle.md#rollback).
