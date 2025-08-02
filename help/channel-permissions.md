# Channel permissions

{!channels-intro.md!}

{!channel-privacy-types.md!}

## Configure channel permissions

You can configure the following permissions for each channel,
regardless of its type.

Subscription permissions:

* [Who can administer the channel](/help/configure-who-can-administer-a-channel)
* [Who can subscribe themselves](/help/configure-who-can-subscribe)
* [Who can subscribe anyone](/help/configure-who-can-invite-to-channels#configure-who-can-subscribe-anyone-to-a-specific-channel)
* [Who can unsubscribe anyone](/help/configure-who-can-unsubscribe-others)

Messaging permissions:

* [Who can send messages](/help/channel-posting-policy)
* [Whether topics are required](/help/require-topics)

Moderation permissions:

* [Who can move messages](/help/restrict-moving-messages)
* [Who can resolve topics](/help/restrict-resolving-topics)
* [Who can delete messages](/help/restrict-message-editing-and-deletion)

For the organization as a whole, you can:

* [Restrict channel creation](/help/configure-who-can-create-channels)
* [Restrict who can subscribe others to channels](/help/configure-who-can-invite-to-channels#configure-who-can-subscribe-others-to-channels-in-general)

Any permission, including whether a channel is private, public, or web-public,
can be modified after the channel is created.

## Private channels

[Private channels](#private-channels) (indicated by <i class="zulip-icon
zulip-icon-lock"></i>) are for conversations that should be visible to users who
are specifically granted access. There are two types of private channels in
Zulip:

- In private channels with **shared history**, new subscribers can access the
  channel's full message history. For example, a newly added team member can get
  ramped up on a secret project by seeing prior discussions.
- In private channels with **protected history**, new subscribers can only see
  messages sent after they join. For example, a new manager would not be able to
  see past discussions regarding their own hiring process or performance management.

{!channel-admin-permissions.md!}

Administrators can [export](/help/export-your-organization) messages in private
channels only if [granted permission to do
so](/help/export-your-organization#configure-whether-administrators-can-export-your-private-data)
by a subscriber.

Users who do not have special permissions (they are not organization
administrators, and have not been granted access to channel metadata) cannot
easily see which private channels exist. They can find out that a channel exists
only by attempting to create a channel with the same name, if they have
[permission to create channels](/help/configure-who-can-create-channels). They
can't get any other information about private channels they are not subscribed
to.

!!! warn ""

    If you create a [bot](/help/bots-overview) that is allowed to read messages
    in a private channel (e.g., a **generic bot**, *not* an **incoming webhook bot**,
    which is more limited), an administrator can in theory gain access to messages
    in the channel by making themselves the bot's owner.

## Public channels

Public channels (indicated by <i class="zulip-icon
  zulip-icon-hashtag"></i>) are open to all members of your organization other than
[guests](/help/guest-users). Anyone who is not a guest can:

- See information about the channel, including its name, description, permission
  settings, and subscribers.
- Subscribe or unsubscribe themselves to the channel.
- See all messages and topics, whether or not they are subscribed.

You can configure other permissions for public channels, such as [who is allowed
to post](/help/channel-posting-policy).

Guest users can't see public (or private) channels, unless they have been specifically
subscribed to the channel.

## Web-public channels

{!web-public-channels-intro.md!}

Web-public channels are indicated with a **globe** (<i class="zulip-icon
zulip-icon-globe"></i>) icon.

## Related articles

* [User roles](/help/user-roles)
* [Guest users](/help/guest-users)
* [User groups](/help/user-groups)
* [Public access option](/help/public-access-option)
* [Restrict channel creation](/help/configure-who-can-create-channels)
* [Configure who can administer a channel](/help/configure-who-can-administer-a-channel)
