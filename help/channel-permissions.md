# Private, public, and web-public channels

{!channels-intro.md!}

There are three types of channels in Zulip:

* [Private channels](#private-channels) (indicated by <i class="zulip-icon
  zulip-icon-lock"></i>), where only subscribers can access messages and
  subscribe other users. You can choose whether new subscribers can see messages
  sent before they were subscribed.

* [Public channels](#public-channels) (indicated by <i class="zulip-icon
  zulip-icon-hashtag"></i>), which are open to everyone in your organization
  other than guests.

* [Web-public channels](#web-public-channels) (indicated by <i class="zulip-icon
  zulip-icon-globe"></i>), where anyone on the Internet can see messages without
  creating an account.

In addition, you can configure the following permissions for each channel,
regardless of its type:

* [Who can send messages](/help/channel-posting-policy)
* [Who can administer the channel](/help/configure-who-can-administer-a-channel)
* [Who can unsubscribe other users](/help/configure-who-can-unsubscribe-others)

For the organization as a whole, you can:

* [Restrict channel creation](/help/configure-who-can-create-channels)
* [Restrict who can add users to channels](/help/configure-who-can-invite-to-channels)

Any permission, including whether a channel is private, public, or web-public,
can be modified after the channel is created.

## Private channels

[Private channels](#private-channels) (indicated by <i class="zulip-icon
zulip-icon-lock"></i>) are for conversations that should be accessible only to
users who are specifically added to the channel. There are two types of private
channels in Zulip:

- In private channels with **shared history**, new subscribers can access the
  channel's full message history. For example, a newly added team member can get
  ramped up on a secret project by seeing prior discussions.
- In private channels with **protected history**, new subscribers can only see
  messages sent after they join. For example, a new manager would not be able to
  see past discussions regarding their own hiring process or performance management.

Organization administrators can see information about all private channels and
manage some configurations. However, they cannot access messages in private
channels that they are not subscribed to, or subscribe themselves to private
channels.

Organization administrators and [channel
administrators](/help/configure-who-can-administer-a-channel) can always:

- See and modify the channel's [name](/help/rename-a-channel) and [description](/help/change-the-channel-description).
- See who is subscribed to the channel, and [unsubscribe](/help/add-or-remove-users-from-a-channel#remove-users-from-a-channel) them.
- See the channel's permissions settings.
- See how much message traffic the channel gets (but not its contents).
- [Archive](/help/archive-a-channel) the channel.

However, only users who have the relevant permissions *and are subscribed to the
channel* can:

- See messages or topics.
- Subscribe other users.
- Modify the channel's permissions settings, including settings that control who
  can see messages in the channel (public vs. private, shared history vs.
  protected history).

Administrators can [export](/help/export-your-organization) messages in private
channels only if [granted permission to do
so](/help/export-your-organization#configure-whether-administrators-can-export-your-private-data)
by a subscriber.

Users who do not have special permissions (they are not organization
administrators, and have not been granted access to the channel) cannot easily
see which private channels exist. They can find out that a channel exists only
by attempting to create a channel with the same name, if they have [permission
to create channels](/help/configure-who-can-create-channels). They can't get any
other information about private channels they are not subscribed to.

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

Guest users can't see public (or private) channels, unless they have been specifically added to the channel.

## Web-public channels

{!web-public-channels-intro.md!}

Web-public channels are indicated with a **globe** (<i class="zulip-icon
zulip-icon-globe"></i>) icon.

## Related articles

* [User roles](/help/user-roles)
* [Guest users](/help/guest-users)
* [User groups](/help/user-groups)
* [Public access option](/help/public-access-option)
* [Channel posting policy](/help/channel-posting-policy)
* [Restrict channel creation](/help/configure-who-can-create-channels)
* [Configure who can administer a channel](/help/configure-who-can-administer-a-channel)
* [Restrict who can subscribe others](/help/configure-who-can-invite-to-channels)
* [Configure who can unsubscribe others](/help/configure-who-can-unsubscribe-others)
