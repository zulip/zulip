# Configure who can add bots

{!admin-only.md!}

By default, any user in your Zulip organization can add bots corresponding to
an [outside integration](/integrations/) or [custom software development](/api/).

Organization administrators can change who is allowed to add bots.

{settings_tab|organization-permissions}

2. Under **Organization permissions**, configure **Who can add bots**.

{!save-changes.md!}

!!! warn ""
    These settings only effect new bots. Existing bots will not be
    disabled, even if the bots' owners can no longer add new bots.

## Related articles

[Deactivate or reactivate a bot](/help/deactivate-or-reactivate-a-bot)
