# Restrict wildcard mentions

{!admin-only.md!}

Organization administrators can configure who is allowed to use [wildcard
mentions](/help/dm-mention-alert-notifications#wildcard-mentions) that affect a
large number of users. In particular, an organization can restrict who is
allowed to use `@all` (and, equivalently, `@everyone` and `@channel`) in channels
with more than 15 subscribers, and `@topic` in topics with more than 15
participants.

This permission can be granted to any combination of [roles](/help/user-roles),
[groups](/help/user-groups), and individual [users](/help/introduction-to-users).

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Channel permissions**, configure **Who can notify a large number of
   users with a wildcard mention**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [DMs, mentions, and alerts](/help/dm-mention-alert-notifications)
