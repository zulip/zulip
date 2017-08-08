# Navigation and unread counts

## Unread messages

Zulip is carefully designed to automatically track which messages
you've read to produce the ideal reading experience, where you can
always start reading where you left off:

* Messages are automatically marked as read only when you're likely to
have actually read them.

* When you open a view in Zulip, it takes you to the first unread
message in that view, if any.

These goals are achieved through the following behaviors:

* Unread counts will be displayed on the left sidebar, next to the
stream/topic name. In the main view, unread messages will have a
dark line along their left side, which will fade as the message
gets marked as read.

* Essentially, Zulip will consider a message read when the message is
selected (the blue cursor box passes over it). Any message which is
selected or above a message which is selected will be marked as read.

* Whenever you're in a view where the whitespace at the bottom of that
view is visible, Zulip marks all the messages in that view as read.
    * If you're in a longer view where the bottom whitespace isn't
    visible, Zulip marks messages as read as you scroll past them.
    * If you're navigating with the keyboard, a message is marked as
    read when the blue cursor box that you are controlling passes over
    it.
    * If you're navigating with the mouse, Zulip automatically advances
    the blue cursor box to the next message as you approach the top of
    the screen when you're scrolling through the feed. This results in
    messages being marked as read as they disappear from your view while
    scrolling.

* When a user has been off Zulip for several days and has hundreds of
unread messages, they will be prompted for whether they want to mark
all their unread messages as read.

## Navigation

Zulip will always take you to the place you left off (your first
unread message) to make it more easy for you to catch up with all the
discussions that happened while you were away from your computer.

Here is a more detailed overview of the navigation behavior:

* When you click on a topic's name or the recipient list at the top of
a group of messages, Zulip will narrow you to that conversation and
Zulip will select the message you were previously focused on in that
conversation.

* If you narrow into a conversation by using the left sidebar or the
search box, Zulip will instead select the first unread message
matching that narrow, or if there are none, the most recent message
matching that narrow.

* When you narrow to the All messages view, you will automatically be
taken to the same message that was selected in that view before
you narrowed. If you read new messages in your previous narrow, you
will be fast-forwarded to the first unread message in the All messages view.

* When you open a new browser window or tab to the All messages view, Zulip
will select the lowest message in that view, which is usually
just before the first unread message.

* When you load a new browser tab or window to a narrowed view, Zulip
will exhibit behavior similar to when you narrow to that view after
loading the browser window to your All messages view.
