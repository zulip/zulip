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

* "Narrowing" is the process of filtering to a particular subset of
  the messages the user has access to.

* The blue cursor box (the "pointer") is around is called the
  "selected" message.  Zulip ensures that the currently selected
  message is always in-view.

## Pointer logic

### Recipient bar: message you clicked

If you enter a narrow by clicking on a message group's *recipient bar*
(stream/topic or private message recipient list at the top of a group
of messages), Zulip will select the the message you clicked on. This
provides a nice user experience where you get to see the stuff near
what you clicked on, and in fact the message you clicked on stays at
exactly the same scroll position in the window after the narrowing as
it was at before.

### Search or sidebar click: unread/recent matching narrow

If you instead narrow by clicking on something in the left sidebar or
typing some terms into the search box, Zulip will instead selected on
the first unread message matching that narrow, or if there are none,
the most recent messages matching that narrow. This provides the nice
user experience of taking you to the start of the new stuff (with
enough messages you'ev seen before still in view at the top to provide
you with context), which is usually what you want. (When finding the
"first unread message", Zulip ignores unread messages in muted streams
or in muted topics within non-muted streams.)

### Unnarrow: previous sequence

When you unnarrow using e.g. the escape key, you will automatically be
taken to the same message that was selected in the home view before
you narrowed, unless in the narrow you read new messages, in which
case you will be jumped forward to the first unread and non-muted
message in the home view (or the bottom of the feed if there is
none). This makes for a nice experience reading threads via the home
view in sequence.

### New home view: "high watermark"

When you open a new browser window or tab to the home view (a.k.a. the
interleaved view you get if you visit `/`), Zulip will select the
furthest down that your cursor has ever reached in the home
view. Because of the logic around unnarrowing in the last bullet, this
is usually just before the first unread message in the home view, but
if you never go to the home view, or you leave messages unread on some
streams in your home view, this can lag.

We plan to change this to automatically advance the pointer in a way
similar to the unnarrow logic.

### Narrow in a new tab: closest to pointer

When you load a new browser tab or window to a narrowed view, Zulip
will select the message closest to your pointer, which is what you
would have got had you loaded the browser window to your home view and
then clicked on the nearest message matching your narrow (which might
have been offscreen).

We plan to change this to match the Search/sidebar behavior.

### Forced reload: state preservation

When the server forces a reload of a browser that's otherwise caught
up (which happens within 30 minutes when a new version of the server
is deployed, usually at a type when the user isn't looking at the
browser), Zulip will preserve the state -- what (if any) narrow the
user was in, the selected message, and even exact scroll position!

For more on the user experience philosophy guiding these decisions,
see [the architectural overview](architecture-overview.html).

## Unread count logic

How does Zulip decide whether a message has been read by the user?
The algorithm needs to correctly handle a range of ways people might
use the product.  The algorithm is as follows:

* Any message which is selected or above a message which is selected
  is marked as read.  So messages are marked as read as you scroll
  down the keyboard when the pointer passes over them.

* If the whitspace at the very bottom of the feed is in view, all
  messages in view are marked as read.

These two simple rules, combined with the pointer logic above, end up
matching user expectations well for whether the product should treat
them as having read a set of messages (or not).
