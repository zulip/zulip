# About streams and topics

In Zulip, conversations are organized by conversation **streams** and
**topics**.

## About streams
On Zulip, users communicate with each other in group chats by sending
messages to streams, which are similar to conversation threads.

Streams are either:

* **Public** - Public streams are for open discussions. Any Zulip user can
join any public stream in the organization, and they can view the complete
message history of any public stream without joining the stream.
* **Private** - Private streams are for confidential discussions and are
only visible to users who've been invited to subscribe to them. Users who
are not members of a private stream cannot subscribe to the stream, and
they also cannot read or send messages to the stream.

Users are subscribed to specific streams in the organization by default,
such as the #announce stream. Users can easily
[view messages](/help/reading-messages-by-stream-or-topic) from a specific stream;
in addition, they can
[browse](/help/browse-and-subscribe-to-streams#browse-streams) their stream
subscriptions using the Zulip stream browser.

If they wish to read messages from a stream that they're not subscribed to,
users can choose to
[join](/help/browse-and-subscribe-to-streams#subscribing-to-streams) a
stream. Similarly, if they are not interested in the topics being discussed
in a stream, users can choose to
[unsubscribe](/help/unsubscribe-from-a-stream) from a stream.  Users can
also customize their stream settings; they can:

* [pin a stream](/help/pin-a-stream)
* [change the color of streams](/help/change-the-color-of-a-stream)
* [enable desktop notifications for stream](/help/configure-desktop-notifications)
* [muting notification for streams](/help/mute-a-stream)

If enabled by the organization administrators, users can
[create](/help/create-a-stream) streams and
[invite](/help/add-or-remove-users-from-a-stream) other users to a stream.

Only organization administrators can modify a stream; they can:

* [rename a stream](/help/rename-a-stream)
* [delete a stream](/help/delete-a-stream)
* [change the description of a stream](/help/change-the-stream-description)
* [remove users from a stream](/help/add-or-remove-users-from-a-stream#remove-someone-from-a-stream)
* [change the privacy of a stream](/help/change-the-privacy-of-a-stream)

## About topics

In each stream, messages are sorted by topics. Topics are specific,
fine-grained subjects that fit with the overall subject of the stream that
they're sent to. Topics ensure sequential messages about the same thing are
threaded together, allowing for better reception for users.

!!! tip ""
    The best stream topics are short and specific. For example, for a bug
    tracker integration, a good topic would be the bug number; for an
    integration like Nagios, the service would serve as a good topic.

Users can easily [change the topics](/help/change-the-topic-of-a-message) of
the messages that they sent if they sent the message to the wrong topic or
if some messages in a topic have gone off-topic.
