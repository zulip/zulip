# Unread counts and the pointer

When you're using Zulip and you reload, or narrow to a stream, how
does Zulip decide where to place you?

Conceptually, Zulip takes you to the place where you left off
(e.g. the first unread message), not the most recent messages, to
facilitate reviewing all the discussions that happened while you were
away from your computer. The scroll position is then set to keep that
message in view and away from both the top and bottom of the visible
section of messages.

But there a lot of details around doing this right, and around
counting unread messages. Here's how Zulip currently decides which
message to select, along with some notes on improvements we'd like to
make to the model.

First a bit of terminology:

- "Narrowing" is the process of filtering to a particular subset of
  the messages the user has access to.

- The blue cursor box (the "pointer") is around is called the
  "selected" message. Zulip ensures that the currently selected
  message is always in-view.

## Pointer logic

### Recipient bar: message you clicked

If you enter a narrow by clicking on a message group's _recipient bar_
(stream/topic or direct message recipient list at the top of a group
of messages), Zulip will select the message you clicked on. This
provides a nice user experience where you get to see the stuff near
what you clicked on, and in fact the message you clicked on stays at
exactly the same scroll position in the window after the narrowing as
it was at before.

### Search, sidebar click, or new tab: unread/recent matching narrow

If you instead narrow by clicking on something in the left sidebar,
typing some terms into the search box, reloading the browser, or any
other method that doesn't encode a specific message to visit, Zulip
will instead select the first unread message matching that narrow, or
if there are none, the most recent messages matching that narrow.

This provides the nice user experience of taking you to the start of
the new stuff (with enough messages you've seen before still in view
at the top to provide you with context), which is usually what you
want. (When finding the "first unread message", Zulip ignores unread
messages in muted streams or in muted topics within non-muted
streams.)

### Unnarrow: previous sequence

When you unnarrow using e.g. the `a` key, you will automatically be
taken to the same message that was selected in the Combined feed view before
you narrowed, unless in the narrow you read new messages, in which
case you will be jumped forward to the first unread and non-muted
message in the Combined feed view (or the bottom of the feed if there is
none). This makes for a nice experience reading threads via the Combined feed
view in sequence.

### Forced reload: state preservation

When the server forces a reload of a browser that's otherwise caught
up (which happens within 30 minutes when a new version of the server
is deployed, usually at a type when the user isn't looking at the
browser), Zulip will preserve the state -- what (if any) narrow the
user was in, the selected message, and even exact scroll position!

For more on the user experience philosophy guiding these decisions,
see [the architectural overview](../overview/architecture-overview.md).

## Unread count logic

How does Zulip decide whether a message has been read by the user?
The algorithm needs to correctly handle a range of ways people might
use the product. The algorithm is as follows:

- Any message which is selected or above a message which is selected
  is marked as read. So messages are marked as read as you scroll
  down the keyboard when the pointer passes over them.

- If the whitespace at the very bottom of the feed is in view, all
  messages in view are marked as read.

These two simple rules, combined with the pointer logic above, end up
matching user expectations well for whether the product should treat
them as having read a set of messages (or not).

One key detail to highlight is that we only mark messages as read
through these processes in views that contain all messages in a
thread; search views will never mark messages as read.

## Testing and development

In a Zulip development environment, you can use
`manage.py mark_all_messages_unread` to set every user's pointer to 0
and all messages as unread, for convenience in testing unread count
related logic.

It can be useful to combine this with `manage.py populate_db -n 3000`
(which rebuilds the database with 3000 initial messages) to ensure a
large number of messages are present.
