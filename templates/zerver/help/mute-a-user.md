# Mute a user

!!! tip ""

    This feature mutes a user from your personal perspective, and does not
    automatically notify anyone.

You can mute any user you do not wish to interact with. Muting someone will
have the following effects:

* All messages sent by a muted user will automatically be [marked as
  read](/help/marking-messages-as-read) for you, and will never
  generate any desktop, email, or mobile push notifications.

* All messages sent by muted users, including the name, profile
  picture, and message content, are hidden behind a **Click here to
  reveal** banner. A revealed message can later be [re-hidden](/help/mute-a-user#re-hide-a-message-that-has-been-revealed).

* Muted users are hidden from [**Private
  messages**](/help/private-messages) in the left sidebar and the list
  of users in the right sidebar. Private messages between you and a
  muted user are excluded from all views, including search, unless you
  [explicitly search](/help/search-for-messages) for `pm-with:<that
  user>`.

* Muted users have their name displayed as "Muted user" for [emoji
  reactions][view-emoji-reactions], [polls](/help/create-a-poll), and
  when displaying the recipients of group private messages.

* Muted users are excluded from the autocomplete for composing a
  private message or [mentioning a user](/help/mention-a-user-or-group).

* Recent topics and other features that display avatars will show a
  generic user symbol in place of a muted user's profile picture.

* To avoid interfering with administration tasks, stream and
  organization settings display muted users' names and other details.

!!! tip ""

    Muting someone does not affect their Zulip experience in any way.


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

### Re-hide a message that has been revealed

{start_tabs}

{!message-actions-menu.md!}

3. Click **Hide muted message again**.

{end_tabs}

### See your list of muted users

{start_tabs}

{settings_tab|muted-users}

{end_tabs}

From there, you can also search for and **unmute** users.

## Related articles

* [Deactivate a user](/help/deactivate-or-reactivate-a-user)
* [Moderating open organizations](/help/moderating-open-organizations)
* [Mute a stream](/help/mute-a-stream)
* [Mute a topic](/help/mute-a-topic)
