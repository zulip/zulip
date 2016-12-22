# Searching

The Zulip search bar allows you to both find single messages in your
streams and filter messages by various criteria.  It is located at the
top of your chat window.

## Searching past messages

### Searching content of messages & topics

* To search for messages containing the word/phrase **example**, enter
  **example** as it is in the search bar. Press *enter* to obtain a
  list of results matching your search.
* Entering multiple words will only return results containing each word.
* The topic of a message is included in the search.

<p align="center"><img src="/static/images/help/search-messages/search-normal.png" width="550"></p>

<p align="center"><img src="/static/images/help/search-messages/search-topic.png" width="550"></p>

* If you are searching from within a stream or topic, the search bar
  will already contain certain *operators*. You can now:
    * add a space and then conduct your search within the scope of the stream/topic.
    * remove the *operators* to conduct a normal search over all streams.

<p align="center"><img src="/static/images/help/search-messages/search-scope.png" width="550"></p>

### Filtering Messages

You can search for messages that match certain criteria, like the author of the message, the stream they were sent in, etc.

* Filter your messages with so-called *operators* of the form `operator:operand`.

* Separate multiple operators by spaces.

* If *operand* contains spaces, replace them with '+'.

* You can combine the *operators* with the keyword search described formerly.

* To see a list of search operators, go to the cog
   (![cog](/static/images/help/cog.png)) in the upper right corner of the right sidebar and choose “Search help” from the drop-down menu:

<p align="center"><img src="/static/images/help/search-messages/search-help.png" width="400"></p>

Here are a few examples on how to use search operators:

* Example 1<p align="top"><img src="/static/images/help/search-messages/search-example-1.png" width="600"></p>
*Explanation*: Search for all messages in the stream *Scotland* that contain a link. <br/><br/>

* Example 2<p align="top"><img src="/static/images/help/search-messages/search-example-2.png" width="600"></p>
*Explanation*: Search for all messages from the user *iago@zulip.com* in the stream *errors* that contain the words *bug* and *code*. <br/><br/>

* Example 3<p align="top"><img src="/static/images/help/search-messages/search-example-3.png" width="600"></p>
*Explanation*: Search for all messages that you starred.

### Features and limitations

* Search hits include morphological variants by default (if you search
  for walking you’ll also get walk, walks, walked, and so on).
* Use quotation marks (") to search for a word/phrase exactly as you
 type it.  For instance, searching for `"a happy rabbit"` will only
 deliver results containing an exact match of `a happy rabbit`.

* Searches are case insensitive.

* Searching by date isn’t currently possible.

* Some common words might be handled as “stop words” — the search tool
will ignore them, because they appear in too many messages to be
useful. **This can lead to no results being found at all!**

* When pressing space in the search bar, a drop-down menu shows
  up. Clicking on one of its items narrows your search to the
  stream/topic/criterion described by the item.
* If you are proceeding from a blank search bar, the items display
  your streams, allowing you to view messages from that stream only.
* If you are proceeding from within a stream, the items display the
  topics of that stream, allowing you to view messages from that topic
  only.

<p align="center"><img src="/static/images/help/search-messages/search-menu.png" width = "550"></p>

* A little *x* is located on the right side of the search
  bar. Clicking on it will clear the search bar and open the *Home*
  chat panel.

### Sidebar Links

Zulip's left sidebar features links for your streams, starred
messages, @-mentions, etc.

* Clicking on one of those links will execute an implicite search,
  e.g. clicking the stream `rabbits` will search for `stream:rabbits`.

* The search executed by clicking on a link is visible in the search bar.

### Learning more

* See the article on [Advanced search for messages](/help/advanced-search-for-messages).
