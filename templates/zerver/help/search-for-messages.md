# Searching for messages

In Zulip, you can find specific messages by using the search bar (highlighted in
red in the image below) at the top of your screen. This feature allows you to
narrow your view to show specific messages using search constraints called
**operators**.

![Search bar](/static/images/help/search-bar.png)

Operators are short phrases in the format `operator:operand` where `operand`
represents the criteria that fits the specified operator. Operators allow you to
instantly find messages that meet the specified criteria, such as messages that
belong to a specific stream or topic.

It is important to note that spaces in `operand` must be replaced with
`+`.  Multiple search operators can be used in a single query by
separating each operator with spaces in your search bar. For example,
a query like `stream:announce topic:zulip near:1` would show the
very oldest messages in a that stream and topic.

By default, search will only display messages that you actually
received.  However, if your search operators include narrowing to a
public stream, you have full access to that stream's history, and thus
can search messages from before you subscribed to the stream (or even
joined your Zulip organization).

## Features and limitations

* Search hits include morphological variants by default; for example, if you
search for messages that contain "walking", you’ll also find messages that
contain "walk", "walks", "walked", etc.
* Searches are case-insensitive.
* Searching by date currently is not possible.
* When pressing space in the search bar, a dropdown menu with autocompletion
  suggestions appears. Clicking on one of its items narrows your search to the
  stream/topic/criterion described by the item.

## Search operators

To see a list of all search operators in Zulip, click the search (<i
class="icon-vector-search"></i>) icon on the left side of the search bar.
You can alternatively click the cog (<i class="icon-vector-cog"></i>) icon
in the top right corner of the right sidebar and choose **Search help**
from the dropdown menu that appears.

![Search help](/static/images/help/search-help.png)

Listed below are all Zulip search operators.

* `stream:foobar` - This operator narrows the view to show only
  messages in the stream `foobar`
* `topic:foo+bar` - This operator narrows the view to show only
  messages with the topic `foo bar`. It is important to note that the
  complete topic name must be entered, if else, no results will be shown.
* `pm-with:foo@bar.com` - This operator narrows the view to show only
  private messages sent from the user with the email address
  `foo@bar.com`.
* `group-pm-with:foo@bar.com` - This operator narrows the view to show all
  private messages from groups that contain both you and the user with
  email address `foo@bar.com`. This operator does not show 1:1 private messages
  between you and the user with email address `foo@bar.com`
* `sender:foo@bar.com` - This operator narrows the view to show all
  messages sent by the user with the email address `foo@bar.com`.
* `sender:me` - This operator narrows the view to show all messages sent by you.
* `near:xxxxx` - This operator narrows the view to show the message
  with the ID `xxxxx` as well as a few messages sent before and after
  the message.
* `id:xxxxx` - This operator narrows the view to show only the message with the
ID `xxxxx`.
* `is:alerted` - This operator narrows the view to show messages with alert
words. You can [add alert words](/help/add-an-alert-word) in the
[Settings](/#settings) page.
* `is:mentioned` - This operator narrows the view to show messages that mention
you.
* `is:private` - This operator narrows the view to show all private messages
that you've received.
* `is:starred` - This operator narrows the view to show all messages that you've
starred.
* `is:unread` - This operator narrows the view to show all messages that you
haven't read.
* `has:link` - This operator narrows the view to show all messages that contain
any links.
* `has:image` - This operator narrows the view to show all messages that contain
any images.
* `has:attachment` - This operator narrows the view to show all messages that
contain any attachments or uploads.
* `keyword` - This operator narrows the view to show all messages containing the
`keyword`.

    !!! warn ""
        **Warning:** Some common words, such as "a", "the", and "or", might be
        handled as [stop words](https://en.wikipedia.org/wiki/Stop_words) — the
        search tool will ignore them because they appear in too many messages to
        be useful. **This can lead to no results being found at all!**

* `key phrase` - This operator narrows the view to show all messages containing
all of the words in `key phrase`.
* `"key phrase"` - This operator narrows the view to show all messages
containing the exact phrase `key phrase`.
(The difference between `keyword`, `key phrase` and `"key phrase"` is better
explained [below](#difference-between-keyword-key-phrase-and-key-phrase)).
* `-operator:operand` - This operator narrows the view to exclude messages with the operator `operand`
    * For example, `-topic:foobar` narrows the view to exclude messages with the topic `foobar`.

### Difference between `keyword`, `key phrase`, and `"key phrase"`

* `keyword` is an operator that consists of one word. It narrows the view to show all the messages that contain
that one word.
* `key phrase` is an operator that consists of multiple words. It narrows the view to show all the messages that
contain all of the words in that phrase, regardless of the order.
* `"key phrase"` is an operator that consists of multiple words surrounded by quotation marks ( `"` ). It narrows
the view to show all the messages that contain the key phrase in the exact same order.

For example, if there are 3 messages containing "Cheese", "I like cheese" and
"Like cheese I":

* the operator `cheese` would show all three messages.
* the operator `I like cheese` would only show the messages containing "I like
    cheese" and "Like cheese I".
* the operator `"I like cheese"` would only show the message containing "I like
    cheese".

## Keyboard shortcuts

Listed below are some Zulip keyboard shortcuts that will aid you in conducting a search.

* **Initiate a search** `/` - This shortcut moves the user's cursor to
  the message search bar at the top of the window to allow them to
  begin searching for messages belonging to a specific topic, stream,
  view, etc. in the organization.
* **Clear a search** `Esc` - This shortcut clears the search bar of
  any search criteria that was previously entered. This action can also be
  achieved by clicking the x (<i class="icon-vector-remove"></i>) icon to the
  right of the search bar or the home (<i class="icon-vector-home"></i>) icon to
  the left of the search bar.
