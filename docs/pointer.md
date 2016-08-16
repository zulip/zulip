# Pointer and unread counts

When you're using Zulip and you reload, or narrow to a stream, how
does Zulip decide where to place you?

In general, Zulip takes you to the place where you left off (e.g. the
first unread message), not the most recent messages, to facilitate
reviewing all the discussions that happened while you were away from
your computer. The scroll position is then set to keep that message in
view and away from both the top and bottom of the visible section of
messages.

But there a lot of details around doing this right, and around
counting unread messages. Here's how Zulip decides which message to
select.

## Recipient bar: message you clicked

If you enter a narrow by clicking on a message group's *recipient bar*
(stream/topic or private message recipient list at the top of a group
of messages), Zulip will center the new narrow around the message you
clicked on. This provides a nice user experience where you get to see
the stuff near what you clicked on.

## Search or sidebar click: unread/recent matching narrow

If you instead narrow by clicking on something in the left sidebar or
typing some terms into the search box, Zulip will instead focus on the
first unread message matching that narrow, or if there are none, the
most recent messages matching that narrow. This provides the nice user
experience of taking you to the start of the new stuff (with maybe a
bit of old stuff still in view at the top), which is usually what you
want. (When finding the "first unread message", Zulip ignores unread
messages in muted streams or in muted topics within non-muted
streams.)

## Unnarrow: previous sequence

When you unnarrow using e.g. the escape key, you will automatically be
taken to the same message that was selected in the home view before
you narrowed, unless in the narrow you read new messages, in which
case you will be jumped forward to the first unread and non-muted
message in the home view (or the bottom of the feed if there is
none). This makes for a nice experience reading threads via the home
view in sequence.

## New home view: "high watermark"

When you open a new browser window or tab to the home view (a.k.a. the
interleaved view you get if you visit `/`), Zulip will take you to the
highest message ID (a.k.a. "high watermark") that your cursor has ever
reached in the home view (called the *"pointer"* in the Zulip
API). Because of the logic around unnarrowing in the last bullet, this
is usually the same as the first unread message in the home view, but
if you never go to the home view, or you leave messages unread on some
streams in your home view, this can lag.

## Narrow in a new tab: closest to pointer

When you load a new browser tab or window to a narrowed view, Zulip
will take you to the message closest to your pointer, which is what
you would have got had you loaded the browser window to your home view
and then clicked on the nearest message matching your narrow (which
might have been offscreen).

## Forced reload: historical recreation

When the server forces a reload of a browser that's otherwise caught
up (which happens within 30 minutes when a new version of the server
is deployed), Zulip will try to take the user back to the exact same
place where you were before the server-initiated reload, in every way
(same selected message, and even the same exact scroll position!).

For more on the user experience philosophy guiding these decisions,
see [the architectural overview](architecture-overview.html).
