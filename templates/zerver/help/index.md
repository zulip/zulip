# Zulip User Documentation (draft)

Zulip is a chat app. Its most distinctive characteristic is that
conversation among a group of people can be divided according to
subject “**streams**” and further subdivided into “**topics**”, so
much finer-grained conversations are possible than with IRC or other
chat tools.

Most people use Zulip on the Web. There are also mobile apps for
Android/iOS, and desktop apps for Mac/Linux/Windows, as well as a
cross-platform version and a version for Platform 9. See
[the documentation on apps](/apps) for more information.

One Zulip account, associated with a particular group or organization, is known
as a **organization**.

---

# Using Zulip
## Basics
* [The Zulip browser window](/help/the-zulip-browser-window)
- [Zulip glossary](/help/zulip-glossary)
## Account Basics
* [Change your name](/help/change-your-name)
* [Change your password](/help/change-your-password)
* Change your email address (not implemented)
* [Change your settings](/help/edit-settings)
* [Change your avatar](/help/change-your-avatar)
* [Change your language](/help/change-your-language)
* [Change the date and time format](/help/change-the-date-and-time-format)
* [Move the users list to the left sidebar](/help/move-the-users-list-to-the-left-sidebar)
* Join a Zulip organization
* [Signing in](/help/signing-in)
* [Signing out](/help/signing-out)
* Find your Zulip organization (not implemented)
* Set up two-factor authentication (not implemented)
* [Deactivate your account](/help/deactivate-your-account)

## Messages
### Sending
* [Send a stream message](/help/send-a-stream-message)
* [Send a private message](/help/send-a-private-message)
* [Format your message using Markdown](/help/format-your-message-using-markdown)
* [Preview your message before sending](/help/preview-your-message-before-sending)
* [Add emoji](/help/add-emoji)
* [Upload and share files](/help/upload-and-share-files)
* [Restore the last unsent message](/help/restore-the-last-unsent-message)
* Automatically link to an external issue tracker (improve wording)
* Add a link preview
* [Enable or disable pressing enter to send](/help/enable-or-disable-pressing-enter-to-send)
* Verify that your message has been successfully sent
* What to do if the server returns an error
* [Send a status message](/help/send-a-status-message)
* [@-mention a team member](/help/at-mention-a-team-member) (needs a
  note that you can't @mention when editing messages, since they may
  have already read the message / not clear how to notif them)
* [Make an announcement](/help/make-an-announcement)
* Send a message in a different language
* [Reply to a message](/help/reply-to-a-message)
### Reading
* [View the Markdown source of a message](/help/view-the-markdown-source-of-a-message)
* [View information about a message](/help/view-information-about-a-message)
* [View the exact time a message was sent](/help/view-the-exact-time-a-message-was-sent)
* [View an image at full size](/help/view-an-image-at-full-size)
* [Collapse a message](/help/collapse-a-message)
* [Star a message](/help/star-a-message)
* Share a message or conversation (permanent link)
### Editing
* [Edit or delete a message](/help/edit-or-delete-a-message)
* [Change the topic of a message](/help/change-the-topic-of-a-message)
### Searching
* [Search messages](/help/search-messages)
* [Advanced search for messages](/help/advanced-search-for-messages)

## People
* [Check whether someone is here or away](/help/check-whether-someone-is-here-or-away)
* [Invite a friend to Zulip](/help/invite-a-friend-to-zulip)
* Send someone a private message
* [Send a group of people a private message](/help/send-a-group-of-people-a-private-message)

## Streams & Topics
* [About streams and topics](/help/about-streams-and-topics)
* [Browse and join streams](/help/browse-and-join-streams)
* [Create a stream](/help/create-a-stream)
* [View your current stream subscriptions](/help/browse-and-join-streams#browse-streams)
* [View messages from a stream](/help/view-messages-from-a-stream)
* [View messages from a topic](/help/view-messages-from-a-topic)
* [View messages from a user](/help/view-messages-from-a-user)
* [The #announce stream](/help/the-announce-stream)
* [Add or invite someone to a stream](/help/add-or-invite-someone-to-a-stream)
* [Change the stream description](/help/change-the-stream-description)
* [Rename a stream](/help/rename-a-stream)
* Preview a stream (not implemented)
* [Unsubscribe from a stream](/help/unsubscribe-from-a-stream)
* [Change who can join a stream](/help/change-who-can-join-a-stream)
* [Pin a stream](/help/pin-a-stream)
* [Change the color of a stream](/help/change-the-color-of-a-stream)
* [Message a stream by email](/help/message-a-stream-by-email)
* Convert a group PM to a private stream (not implemented)
* [Remove someone from a stream (admin only)](/help/remove-someone-from-a-stream)
* [Delete a stream (admin only)](/help/delete-a-stream)

## Notifications
* [Mute a stream](/help/mute-a-stream)
* [Mute a topic](/help/mute-a-topic)
* Set notifications for a single stream
* [Configure desktop notifications](/help/configure-desktop-notifications)
* [Configure audible notifications](/help/configure-audible-notifications)
* Configure email notifications
* Configure mobile push notifications
* [Add an alert word](/help/alert-words)

## Tools & Customization
* [Keyboard shortcuts](/help/keyboard-shortcuts)
* Add a bot or integration

## Apps
* Zulip on Mac OS
* Zulip on Linux
* Zulip on Windows
* [Zulip on Android](/help/zulip-on-android)
* Zulip on iOS
* Zulip in a terminal
* Connect to Zulip over IRC/etc (not implemented?)

# Administering a Zulip organization

## Organization Settings
* [Change your administrator settings](/help/edit-administrator-settings)
* [Change your organization's name](/help/change-your-organizations-name)
* Restrict user email addresses to certain domains
* [Allow anyone to join without an invitation](/help/allow-anyone-to-join-without-an-invitation)
* [Only allow admins to invite new users](/help/only-allow-admins-to-invite-new-users)
* Only allow admins to create new streams
* [Restrict editing of old messages and topics](/help/restrict-editing-of-old-messages-and-topics)
* [Change the default language for your organization](/help/change-the-default-language-for-your-organization)
* [Add custom emoji](/help/add-custom-emoji)
* Configure authentication methods
* [Add a custom linkification filter](/help/add-a-custom-linkification-filter)
* Delete your organization (not implemented)

## Users & Bots
* [Deactivate or reactivate a user](/help/deactivate-or-reactivate-a-user)
* [Deactivate or reactivate a bot](/help/deactivate-or-reactivate-a-bot)
* [Make a user an administrator](/help/make-a-user-an-administrator)
* [Change a user's name](/help/change-a-users-name)
* [View all bots in your organization (admin only)](/help/view-all-bots-in-your-organization)

## Streams
* [Delete a stream](/help/delete-a-stream)
* [Set default streams for new users](/help/set-default-streams-for-new-users)
* [Rename a stream](/help/rename-a-stream)
* [Change a stream's description](/help/change-the-stream-description)
* [Make a public stream private](/help/change-who-can-join-a-stream#make-a-public-stream-private)
* [Add someone to a stream](/help/add-or-invite-someone-to-a-stream)
* [Remove someone from a stream](/help/remove-someone-from-a-stream)

---

# Include Zulip

* [Chat with zulip button](/help/chat-with-zulip-button)
