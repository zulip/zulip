# Widgets

## What is a widget?

Widgets are special kinds of messages. These include:

- polls
- TODO lists
- `/me` messages
- Trivia bot

Some widgets are used with a leading `/` (like `/poll Tea or coffee?`), similar
to [slash commands](/subsystems/slash-commands.md), but these two concepts
are very different. Slash commands have nothing to do with message sending.

The trivia_quiz_bot does not use `/`'s. Instead, it sends "extra_data"
in messages to invoke **zforms** (which enable button-based UIs in the
messages).

## `/me` messages

These are the least complex. We use our markdown processors to
detect if a message is a `/me` message, plumb the flag through
the message object (as `is_me_message`) and have the clients
format it correctly. Related code (for the web app) lies in
`message_list_view.js` in `_maybe_format_me_message`.

## Polls, todo lists, and games

The most interactive widgets that we built during
2018 are for polls, todo lists, and games. You
launch widgets by sending one of the following messages:

- /poll
- /todo

The web app client provides the "widget experience" by
default. Other clients just show raw messages like
"/poll", and should be adding support
for widgets soon.

Our customers have long requested a poll/survey widget.
See [this issue](https://github.com/zulip/zulip/issues/9736).
There are workaround ways to do polls using things like
emoji reactions, but our poll widget provides a more
interactive experience.

### Data flow

Some important code entities for the widget implementation are:

- `SubMessage` database table
- `/json/submessage` API endpoint
- `web/src/submessage.js`
- `web/src/poll_widget.js`
- `web/src/widgetize.js`
- `web/src/zform.js`
- `web/templates/widgets/`
- `zerver/lib/widget.py`
- `zerver/views/submessage.py`

Both **poll** and **todo** widgets use the "submessage" architecture.
We'll use the poll widget as an example.

The `SubMessage` table, as the name indicates, allows
you to associate multiple submessages to any given
`Message` row. When a message gets sent, there's a
hook inside of `widget.py` that will detect widgets
like "/poll". If a message needs to be
widgetized, an initial `SubMessage` row will be
created with an appropriate `msg_type` (and persisted
to the database). This data will also be included
in the normal Zulip message event payload. Clients
can choose to ignore the submessage-related data, in
which case they'll gracefully degrade to seeing "/poll".
Of course, the web app client actually recognizes the
appropriate widgets.

The web app client will next collect poll options and votes
from users. The web app client has
code in `submessage.js` that dispatches events
to `widgetize.js`, which in turn sends events to
individual widgets. The widgets know how to render
themselves and set up click/input handlers to collect
data. They can then post back to `/json/submessage`
to attach more data to the message (and the
details are encapsulated with a callback). The server
will continue to persist `SubMessage` rows in the
database. These rows are encoded as JSON, and the
schema of the messages is driven by the individual widgets.
Most of the logic is in the client; things are fairly opaque
to the server at this point.

If a client joins Zulip after a message has accumulated
several submessage events, it will see all of those
events the first time it sees the parent message. Clients
need to know how to build/rebuild their state as each
submessage comes in. They also need to tolerate
misformatted data, ideally just dropping data on the floor.
If a widget throws an exception, it's caught before the
rest of the message feed is affected.

As far as rendering is concerned, each widget module
is given a parent `elem` when its `activate` function
is called. This is just a `<div>` inside of the parent
message in the message pane. The widget has access to
jQuery and template.render, and the developer can create
new templates in `web/templates/widgets/`.

A good way to learn the system is to read the code
in `web/src/poll_widget.js`. It is worth noting that
writing a new widget requires only minor backend
changes in the current architecture. This could change
in the future, but for now, a frontend developer mostly
needs to know JS, CSS, and HTML.

It may be useful to think of widgets in terms of a
bunch of clients exchanging peer-to-peer messages. The
server's only real role is to decide who gets delivered
which submessages. It's a lot like a "subchat" system.

### Backward compatibility

Our "submessage" widgets are still evolving, and we want
to have a plan for allowing future progress without
breaking old messages.

Widget developers can revise code to improve a
widget's visual polish without too much concern
for breaking how old messages get widgetized. They will need to
be more cautious if they change the actual data
structures passed around in the submessage payloads.

For significant schema changes, it would be worthwhile to add
some kind of versioning scheme inside of `SubMessages`, either
at the DB level or more at the JSON level within fields.
This has yet to be designed. One thing to consider is that
most widgets are somewhat ephemeral in nature, so it's not
the end of the world if upgrades cause some older messages
to be obsolete, as long as the code degrades gracefully.

Mission-critical widgets should have a deprecation strategy.
For example, you could add optional features for one version
bump and then only make them mandatory for the next version,
as long as you don't radically change the data model. And
if you're truly making radical changes, you can always
write a Django migration for the `SubMessage` data.

### Adding widgets

Right now we don't have a plugin model for the above widgets;
they are served up by the core Zulip server implementation.
Of course, anybody who wishes to build their own widget
has the option of forking the server code and self-hosting,
but we want to encourage folks to submit widget
code to our codebase in PRs. If we get to a critical mass
of contributed widgets, we will want to explore a more
dynamic mechanism for "plugging in" code from outside sources,
but that is not in our immediate roadmap.

This is sort of a segue to the next section of this document.
Suppose you want to write your own custom bot, and you
want to allow users to click buttons to respond to options,
but you don't want to have to modify the Zulip server codebase
to turn on those features. This is where our "zform"
architecture comes to the rescue.

## zform (trivia quiz bot)

This section will describe our "zform" architecture.

For context, imagine a naive trivia bot. The trivia bot
sends a question with the answers labeled as A, B, C,
and D. Folks who want to answer the bot send back an
answer have to send an actual Zulip message with something
like `@trivia_bot answer A to Q01`, which is kind of
tedious to type. Wouldn't it be nice if the bot could
serve up some kind of buttons with canned replies, so
that the user just hits a button?

That is where zforms come in. Zulip's trivia bot sends
the Zulip server a JSON representation of a form it
wants rendered, and then the client renders a generic
"**zform**" with buttons corresponding to `short_name` fields
inside a `choices` list inside of the JSON payload.

Here is what an example payload looks like:

```json
{
    "extra_data": {
        "type": "choices",
        "heading": "05: What color is a blueberry?",
        "choices": [
            {
                "type": "multiple_choice",
                "reply": "answer 05 A",
                "long_name": "red",
                "short_name": "A"
            },
            {
                "type": "multiple_choice",
                "reply": "answer 05 B",
                "long_name": "blue",
                "short_name": "B"
            },
            {
                "type": "multiple_choice",
                "reply": "answer 05 C",
                "long_name": "yellow",
                "short_name": "C"
            },
            {
                "type": "multiple_choice",
                "reply": "answer 05 D",
                "long_name": "orange",
                "short_name": "D"
            }
        ]
    },
    "widget_type": "zform"
}
```

When users click on the buttons, **generic** click
handlers automatically simulate a client reply using
a field called `reply` (in `choices`) as the content
of the message reply. Then the bot sees the reply
and grades the answer using ordinary chat-bot coding.

The beautiful thing is that any third party developer
can enhance bots that are similar to the **trivia_quiz**
bot without touching any Zulip code, because **zforms**
are completely generic.

## Data flow

We can walk through the steps from the bot generating
the **zform** to the client rendering it.

First,
[here](https://github.com/zulip/python-zulip-api/blob/main/zulip_bots/zulip_bots/bots/trivia_quiz/trivia_quiz.py)
is the code that produces the JSON.

```py
def format_quiz_for_widget(quiz_id: str, quiz: Dict[str, Any]) -> str:
    widget_type = 'zform'
    question = quiz['question']
    answers = quiz['answers']

    heading = quiz_id + ': ' + question

    def get_choice(letter: str) -> Dict[str, str]:
        answer = answers[letter]
        reply = 'answer ' + quiz_id + ' ' + letter

        return dict(
            type='multiple_choice',
            short_name=letter,
            long_name=answer,
            reply=reply,
        )

    choices = [get_choice(letter) for letter in 'ABCD']

    extra_data = dict(
        type='choices',
        heading=heading,
        choices=choices,
    )

    widget_content = dict(
        widget_type=widget_type,
        extra_data=extra_data,
    )
    payload = json.dumps(widget_content)
    return payload
```

The above code processes data that is specific to a trivia
quiz, but it follows a generic schema.

The bot sends the JSON payload to the server using the
`send_reply` callback.

The bot framework looks for the optional `widget_content`
parameter in `send_reply` and includes that in the
message payload it sends to the server.

The server validates the schema of `widget_content` using
`check_widget_content`.

Then code inside of `zerver/lib/widget.py` builds a single
`SubMessage` row to contain the **zform** payload, and the
server also sends this payload to all clients who are
recipients of the parent message.

When the message gets to the client, the codepath for **zform**
is actually quite similar to what happens with a more
customized widget like **poll**. (In fact, **zform** is a
sibling of **poll** and **zform** just has a somewhat more
generic job to do.) In `web/src/widgetize.js` you will see
where this code converges, with snippets like this:

```js
widgets.poll = poll_widget;
widgets.todo = todo_widget;
widgets.zform = zform;
```

The code in `web/src/zform.js` renders the form (not
shown here) and then sets up a click handler like below:

```js
    $elem.find('button').on('click', function (e) {
        e.stopPropagation();

        // Grab our index from the markup.
        var idx = $(e.target).attr('data-idx');

        // Use the index from the markup to dereference our
        // data structure.
        var reply_content = data.choices[idx].reply;

        transmit.reply_message({
            message: opts.message,
            content: reply_content,
        });
    });
```

And then we are basically done!
