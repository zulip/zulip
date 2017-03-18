# Zulip glossary
Exclusive Zulip terminology may be used in Zulip conversations. Here are some
common terms that you should know.

### administrator

**Administrators** have special privileges that allow them to control the settings
and [customizations](#customization) of the organizations that they own,
including the ability to deactivate and reactivate other human and [bot](#bot)
users, delete [streams](#stream), add/remove administrator privileges, as well
as change configurations for the overall organization (e.g. whether an
invitation is required to join the organization).

### bot

Zulip **bots** are often used for [integrations](#integration) to send automated
messages to users and can do everything a normal user in the organization can do
with a few exceptions (e.g. a bot cannot login to the web application or create
other bots).

### compose box

The **compose box** is the area where you input the content of your message when
you send stream or private messages. The compose box features several features
that can help you compose your message, such as the **Emojis**, **Attach files**,
**Formatting**, and **Preview** features.

### customization

**Customization** is the process of modifying Zulip's settings to fit a user's
set of personal preferences. Users can customize their Zulip settings by
clicking the cog (<i class="icon-vector-cog"></i>) icon in the upper right
corner of the right sidebar and choose **Settings** from the dropdown menu.

### down chevron

A **down chevron** is a small downward-facing arrow (<i
class="icon-vector-chevron-down"></i>) icon next to a message’s
[timestamp](#timestamp) that appears upon hover, offering contextual options
when clicked on, such as **View source**, **Reply**, **Collapse**,
**Mute [this topic]**, and **Link to this conversation**.

### emoji

An **emoji** is a small image used to express an idea or emotion in a
conversation. Emojis can be included in Zulip messages by enclosing an emoji
phrase (a complete list of emojis can be found
[here](http://www.webpagefx.com/tools/emoji-cheat-sheet/)) in colons or clicking
the **smiley face** (<i class="icon-vector-smile"></i>) icon below the
[compose box](#compose-box).

### emoji reaction

**Emoji reactions** are small [emoji](#emoji) icons that appear below messages.
Although they are generally used to show reactions to a message, they can be
used for various other purposes, such as [voting](/static/images/help/emoji-react-vote.png)
or [checking off items in a to-do list](/static/images/help/emoji-react-checklist.png).

### filter

Also known as a [view](#view), a **filter** is one of the options for viewing
different kinds of messages, listed in the upper left corner of the Zulip
browser window, such as **Home**, **Private messages**, **Starred messages**,
and **@-mentions**.

### group PM

Shorthand for **group private message**, a **group PM** is a
[private message](#private-message) sent directly to two or more other
users rather than through a [stream](#stream).

### home

**Home** is a specific [view](#view) (or [filter](#filter)) that shows all
messages to the user's [subscribed](#subscribing) [streams](#stream) and all of
the user's private messages in chronological order. This view is accessible by
clicking the **Home** link, Zulip logo in the upper left sidebar, home (<i
class="icon-vector-home"></i>) icon to the left of the search bar, or pressing
the escape key.

### integration

An **integration** is a tool that combines Zulip with another service or
application. Zulip offers a variety of integrations for version control, issue
tracker, CI system, monitoring tools, and other tools used for development. The
three types of integrations that Zulip supports are webhook integrations, Python
script integrations, and plugin integrations.

### mention

To **mention** users in Zulip, you have to type `@` and their email addresses or
usernames for auto-completions in your [compose box](#compose-box). The users
will be mentioned in your message as `@**username**`, and they will be notified
of your message. Users can see all messages they've been mentioned in through
the **@-mentions** link in the left sidebar or by using **is:mentioned** as a
[filter](#filter) or a search constraint.

### /me

`/me` is a reference to one's one name, often used to send status messages to
Zulip by prepending status messages with `/me`. Status messages are usually
written in third person and notify other users about the status of a user, such
as if a user is away from the keyboard or busy.

### message editing

If enabled by an administrator, users can utilize **message editing** for a few
minutes after posting a message to edit the content of their recently-posted
message by hovering to the right of their message's [timestamp](#timestamp) and
clicking the pencil (<i class="icon-vector-pencil"></i>) icon that appears.
Zulip labels edited messages with **(EDITED)** next to the username of the
message writer.

### message table

The **message table** is the current [view](#view) of messages in the middle
pane of an open browser window. Depending on a user's search settings, the
message table can show all messages in a particular [topic](#topic) or
[stream](#stream).

### muting

**Muting** a [topic](#topic) or [stream](#stream) allows a user to stop being
notified of messages sent to the specified topic or stream. This can be
activated by clicking the corresponding chevron of the stream or topic and
selecting **Mute the [stream/topic] [stream/topic name]** from the dropdown that
appears.

### narrowing

**Narrowing** a [topic](#topic) or [stream](#stream) will cause you to only see
the messages of that particular stream or topic. This can be activated by
clicking the corresponding chevron of the stream or topic and selecting
**Narrow to [stream/topic] [stream/topic name]** from the dropdown that appears
or clicking the stream or topic of a set of messages.

### notification

**Notifications** are messages that appear notifying Zulip users about important
events in the organization, such as being [mentioned](#mention) in another
user's message or the creation of a [stream](#stream). Notifications can be sent
as emails or browser/desktop notifications, often accompanied by an alert sound.

### pinning

**Pinning** a [stream](#stream) will move that particular stream above other
streams in the Streams section in the left sidebar. You can pin a stream by
clicking the chevron of the corresponding stream and clicking **Pin stream
[stream] to top** from the dropdown the appears.

### private message

**Private messages** are either **one-on-one** or **group**
conversations, and are only visible to recipients of that message.
The exception to this is that in corporate organizations,
[organization administrators](#administrator) may be able to access to
private messages via compliance exports.  In community organizations,
even organization cannot access private messages unless they are
listed recipients of the message.

### private stream

**Private streams** are for confidential discussions and are only
visible to users who've been invited to [subscribe](#subscribing) to them.

### public stream

**Public streams** are for open discussions. All users can [subscribe](#subscribing)
to public streams and discuss there.

### organization

An **organization**  is a private chamber hosted on Zulip with its own users,
[streams](#stream), [customizations](#customization), etc. [Administrators](#administrator)
manage the organization, controlling the specific settings of the organizations
that they own.

### recipient bar

The **recipient bar** is a visual indication of the context of a message or
group of messages, displaying the [stream](#stream) and [topic](#topic) or
private message recipient list, at the top of a group of messages.

### starring

Zulip allows users to mark any important messages they receive as **starred** by
hovering over the area next to the message's [timestamp](#timestamp) and
clicking the star (<i class="icon-vector-star-empty"></i>) icon that appears. A
user can easily access messages they’ve starred through the **Starred messages**
link in the left sidebar or use **is:starred** as a [filter](#filter) or a
search constraint.

### stream

A **stream** is a channel of [topics](#topic) expected to fall within a certain
scope of content. Streams are located on the left sidebar. Streams are either
**public** (used for open discussions) or **private** (invite-only).

### subscribing

When a user **subscribes** to a [stream](#stream), the user is choosing to
receive all messages from the stream that they subscribed to.

### timestamp

A **timestamp** shows you the exact time when a message was posted. It is
located to the right of a message.

### topic

**Topics** are similar to conversation threads. Topics are used to describe the
general subject of the messages a user sends. Topics effectively ensure
sequential messages about the same thing are threaded together, allowing for
better consumption by users. The topics of messages can be edited as well as the
content of the message.

### unsubscribing

When a user **unsubscribes** from a [stream](#stream), the user is choosing to
stop receiving all messages from the stream that they unsubscribed from.

### view

Also known as [filter](#filter), a **view** is an option for viewing different
kinds of messages, listed in the upper left sidebar, including sections
**Home**, **Private messages**, **Starred messages**, and **@-mentions**.
