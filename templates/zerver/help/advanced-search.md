# Advanced search for messages
![Search bar](/static/images/help/search-bar.png)

In Zulip, you can find specific messages by using the search bar (highlighted in red in the previous image) at the top of your screen. This feature allows you to narrow your view to show specific messages using search constraints called **operators**.

Operators are short phrases in the format `operator:operand` where `operand` represents the criteria that fits the specified operator. Operators allow you to instantly find messages that meet the specified criteria, such as messages that belong to a specific stream or topic.

It is important to note that spaces in `operand` must be replaced with `+`. In addition, multiple search operators can be used in a single query by separating each operator with spaces in your search bar. Most importantly, you can search an individual stream for results from before you joined, but search results will only include messages from after you first joined Zulip if you search the entire realm.

## Search operators
Listed below are all Zulip search operators.

* `stream:foobar` - This operator narrows the view to show only messages in the stream `foobar`
* `topic:foo+bar` - This operator narrows the view to show only messages with the topic `foo bar`. It is important to note that the complete topic name must be entered, or no results will be shown.
* `pm-with:foo@bar.com` - This operator narrows the view to show only private messages sent from the user with the email address `foo@bar.com`.
* `sender:foo@bar.com` - This operator narrows the view to show all messages sent by the user with the email address `foo@bar.com`.
* `sender:me` -This operator narrows the view to show all messages sent by you.
* `near:xxxxx` - This operator narrows the view to show the message with the ID `xxxxx` as well as a few messages sent before and after the message.
* `id:xxxxx` - This operator narrows the view to show only the message with the ID `xxxxx`.
* `is:alerted` - This operator narrows the view to show messages with alert words. You can add custom alert words in the **Settings** tab.
* `is:mentioned` - This operator narrows the view to show messages that mention you.
* `is:private` - This operator narrows the view to show all private messages that you've received.
* `is:starred` - This operator narrows the view to show all messages that you've starred.
* `has:link` - This operator narrows the view to show all messages that contain any links.
* `has:image` - This operator narrows the view to show all messages that contain any images.
* `has:attachment` - This operator narrows the view to show all messages that contain any attachments or uploads.
* `keyword` - This operator narrows the view to show all messages containing the word or phrase `keyword`.
* `"keyword"` - This operator narrows the view to show all messages containing the exact word or phrase `keyword`.
* `-topic:foobar` - This operator narrows the view to exclude messages with the topic `foobar`

## Keyboard shortcuts
Listed below are some Zulip keyboard shortcuts that will aid you in conducting a search.

* **Initiate a search** `/` - This shortcut moves the user's cursor to the message search bar at the top of the window to allow them to begin searching for messages belonging to a specific topic, stream, view, etc. in the realm.
* **Clear a search** `Esc` - This shortcut clears the search bar of any search criteria that was previously entered. This action can also be achieved by clicking the **x** (![x](/static/images/help/x.png)) icon in the right side of the search bar.
