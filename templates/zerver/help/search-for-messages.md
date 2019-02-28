# Searching for messages

Zulip has a powerful search engine under its hood. Search for messages using
the search bar at the top of the screen.

## Example

* `stream:design has:link is:starred new logo`

Searches for messages in `#design` that have a link, that you starred, and
that have the words `new` and `logo`.

The permalink for that search (web only) will look something like
`https://your-zulip-url/#narrow/stream/123-design/has/link/is/starred/search/new.20logo`.

## List of operators

As you start typing, Zulip will suggest possible operator completions.
Operators can be used with keywords, or on their own. For example,

* `stream:design logo` will search for the word `logo` within `#design`
* `stream:design` will navigate to `#design`

Here is the **full list of search operators**.

* `stream:design`: Search within the stream `#design`.
* `stream:design topic:emoji+picker`: Search within the topic `emoji picker`.
* `is:private`: Search all your private messages.
* `pm-with:ada@zulip.com`: Search 1-on-1 messages with Ada.
* `group-pm-with:ada@zulip.com`: Search group private messages that
  include Ada.
* `sender:ada@zulip.com`: Search messages sent by Ada.
* `sender:me`: Search sent messages.
* `near:12345`: Show messages around the message with ID `12345`.
* `id:12345`: Show only message `12345`.

* `is:alerted`: See [alert words](/help/add-an-alert-word).
* `is:mentioned`: See [mentions](/help/mention-a-user-or-group).
* `is:starred`: See [starred messages](/help/star-a-message).
* `is:unread`
* `has:link`
* `has:image`
* `has:attachment`

## Words and phrases

Most searches consist of a list of operators followed by a list of keywords.

* `new logo`: Search for messages with both `new` and `logo`.
* `"new logo"`: Search for messages with the phrase `"new logo"`.

Zulip does some basic stemming, so `wave` will match `waves` and
`waving`. Keywords are case-insensitive, so `wave` will also match `Wave`.

Emoji are included in searches, so if you search for `octopus` it will
include messages with
<img src="/static/generated/emoji/images-google-64/1f419.png" alt="octopus"
class="emoji-small"/>.


Note that Zulip ignores common words like `a`, `the`, and about 100
others. A quirk in Zulip's current implementation means that if all of your
keywords are ignored, we'll return 0 search results.

## Other notes

* By default, search only displays messages that you actually
  received. However, if your search is restricted to a stream where you have
  [access to stream history](/help/stream-permissions), you can search for
  messages from before you subscribed to the stream (or even joined your
  Zulip organization).

* To see the list of search operators in-app, click the **gear** (<i
  class="fa fa-cog"></i>) icon in the upper right, and select
  **Search operators**.
