# Set default channels for new users

{!admin-only.md!}

When new users join a Zulip organization, they are subscribed to a default
set of channels. Organization administrators can add or remove channels from
that default set.

## Add a new default channel

{start_tabs}

{settings_tab|default-channels-list}

2. Under **Add new default channel**, enter the name of a channel.

3. Click **Add channel**.

{end_tabs}

## Remove a default channel

{start_tabs}

{settings_tab|default-channels-list}

2. Find the channel you would like to remove, and click **Remove from default**.

{end_tabs}

!!! tip ""

    A user with permission to invite other users will be able to subscribe those
    users to these default channel at the time of invitation irrespective of
    whether they have individual permission to subscribe other users to that channel.
    This will only apply at the time of invitation and not once the invited user has
    become a member.

## Related articles

* [User roles](/help/user-roles)
* [User groups](/help/user-groups)
* [Channel permissions](/help/channel-permissions)
* [Create channels for a new organization](/help/create-channels)
