# Mute a user

!!! tip ""
    This feature mutes a user from your personal perspective, and does not
    automatically notify anyone. Consider also reporting abusive behavior to
    organization [owners and administrators](/help/roles-and-permissions),
    who can take organization-level actions like
    [deactivating a user](/help/deactivate-or-reactivate-a-user).

You can mute any user you do not wish to interact with. Muting someone will
have the following effects:

* All messages sent by a muted user will automatically be [marked as
  read](/help/marking-messages-as-read) for you, and will never
  generate any desktop, email, or mobile push notifications.

* Muted users are hidden from [**Private
  messages**](/help/private-messages) in the left sidebar and the list
  of users in the right sidebar. Private messages between you and a
  muted user will only be visible if you [explicitly
  search](/help/search-for-messages) for your private messages with
  the user.

* All stream messages and group private messages sent by muted users
  are hidden behind a **Click to reveal** banner. This allows you to
  understand whether other users' messages are responses to messages
  sent by a muted user, while seeing the muted user's name, profile
  picture, or message content only for those messages which you have opted
  into reading.

* Muted users have their name displayed as "Muted user" for [emoji
  reactions][view-emoji-reactions], [polls](/help/create-a-poll), and
  when displaying the recipients of group private messages sent by
  unmuted users.

* Muted users are excluded from the autocomplete for composing a
  private message or [mentioning a user](/help/mention-a-user-or-group).

* Areas in Zulip which show users' avatars will now show a generic user symbol
  in place of a muted user's profile picture.

* To avoid interfering with administration tasks, parts of the
  settings UI (such as the list of subscribers to a stream, or members
  of the organization) will display muted users' names and other
  details as normal.

!!! tip ""
    Zulip offers no way to distinguish a user
    that has muted you from a user that is ignoring you.


[view-emoji-reactions]: /help/emoji-reactions#see-who-reacted-to-a-message

### From the message view

{start_tabs}

1. Click on a user's profile picture or [mention](/help/mention-a-user-or-group).

1. Click **Mute this user**.

1. On the confirmation popup, click **Confirm**.

{end_tabs}

### Via the right sidebar

{start_tabs}

1. Hover over a user's name in the right sidebar.

1. Click on the ellipsis (<i class="zulip-icon zulip-icon-ellipsis-v-solid"></i>) to
  the right of their name.

1. Click **Mute this user**.

1. On the confirmation popup, click **Confirm**.

{end_tabs}

### See your list of muted users

{start_tabs}

{settings_tab|muted-users}

{end_tabs}

From there, you can also search for and **unmute** users.

## Related articles

* [Mute a stream](/help/mute-a-stream)
* [Mute a topic](/help/mute-a-topic)
