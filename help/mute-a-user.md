# Mute a user

!!! tip ""

    This feature mutes a user from your personal perspective, and does not
    automatically notify anyone.

You can mute any user you do not wish to interact with. Muting someone will
have the following effects:

* Combined feed sent by a muted user will automatically be [marked as
  read](/help/marking-messages-as-read) for you, and will never
  generate any desktop, email, or mobile push notifications.

* Combined feed sent by muted users, including the name, profile
  picture, and message content, are hidden behind a **Click here to
  reveal** banner. A revealed message can later be [re-hidden](/help/mute-a-user#re-hide-a-message-that-has-been-revealed).

* Muted users are hidden from [**Direct
  messages**](/help/direct-messages) in the left sidebar and the list
  of users in the right sidebar. Direct messages between you and a
  muted user are excluded from all views, including search, unless you
  [explicitly search](/help/search-for-messages) for `dm-with:<that
  user>`.

* Muted users have their name displayed as "Muted user" for [emoji
  reactions][view-emoji-reactions], [polls](/help/create-a-poll), and
  when displaying the recipients of group direct messages.

* Muted users are excluded from the autocomplete for composing a
  direct message or [mentioning a user](/help/mention-a-user-or-group).

* Muted users are excluded from [read receipts](/help/read-receipts)
  for all messages. Zulip never shares whether or not you have read
  a message with a user you've muted.

* **Recent conversations** and other features that display avatars will
  show a generic user symbol in place of a muted user's profile picture.

* To avoid interfering with administration tasks, channel and
  organization settings display muted users' names and other details.

!!! tip ""

    Muting someone does not affect their Zulip experience in any way.


[view-emoji-reactions]: /help/emoji-reactions#view-who-reacted-to-a-message

## Mute a user

{start_tabs}

{!user-card-three-dot-menu.md!}

1. Click **Mute this user**.

1. On the confirmation popup, click **Confirm**.

!!! Tip ""

    You can also click on a user's profile picture or name on a
    message they sent to open their **user card**, and skip to
    step 3.

{end_tabs}

## Re-hide a message that has been revealed

{start_tabs}

{!message-actions-menu.md!}

3. Click **Hide muted message again**.

{end_tabs}

## See your list of muted users

{start_tabs}

{settings_tab|muted-users}

{end_tabs}

From there, you can also search for and **unmute** users.

## Related articles

* [Deactivate a user](/help/deactivate-or-reactivate-a-user)
* [Moderating open organizations](/help/moderating-open-organizations)
* [Mute or unmute a channel](/help/mute-a-channel)
* [Mute or unmute a topic](/help/mute-a-topic)
