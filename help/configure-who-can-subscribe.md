# Configure who can subscribe to a channel

You can give users permission to subscribe to a channel. Everyone other than
[guests](/help/guest-users) can subscribe to any
[public](/help/channel-permissions#public-channels) or
[web-public](/help/channel-permissions#web-public-channels) channel, so this
feature is intended for use with [private
channels](/help/channel-permissions#private-channels). Guests can never
subscribe themselves to a channel.

This permission grants access to channel content: users who are allowed to
subscribe to a channel will also be able to read messages in it without
subscribing.

!!! tip ""

    For example, you can give your team's [user group](/help/user-groups) permission
    to subscribe to each of your team's channels. A designer on the team could then
    follow a [link to a
    conversation](/help/link-to-a-message-or-conversation#link-to-a-topic-within-zulip)
    in the private engineering channel, and read it without subscribing. They could
    subscribe if they need to send a message there, without asking for help.

If you have permission to administer a public channel, you can configure who can
subscribe to it. For [private
channels](/help/channel-permissions#private-channels), you additionally need to
have content access in order to change this configuration.

{start_tabs}

{tab|desktop-web}

{relative|channel|all}

1. Select a channel.

{!select-channel-view-general-advanced.md!}

1. Under **Subscription permissions**, configure **Who can subscribe to this
   channel**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Subscribe to a channel](/help/introduction-to-channels#browse-and-subscribe-to-channels)
* [Channel permissions](/help/channel-permissions)
* [User roles](/help/user-roles)
* [User groups](/help/user-groups)
* [Configure who can subscribe other users to channels](/help/configure-who-can-invite-to-channels)
* [Configure who can unsubscribe anyone from a channel](/help/configure-who-can-unsubscribe-others)
* [Subscribe users to a channel](/help/subscribe-users-to-a-channel)
* [Unsubscribe users from a channel](/help/unsubscribe-users-from-a-channel)
