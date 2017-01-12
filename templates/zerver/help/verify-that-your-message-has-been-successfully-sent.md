# Verify that your message has been succesfully sent

When you send a message in a chat tool, depending on where you are
located in relation to the relevant server, it can take a few hundred
milliseconds for your message to transmitted to the server, stored,
and transmitted to active clients by the server.  Like most other chat
tools, Zulip optimizes the experience for the sender by "locally
echoing" the message, i.e. displaying it in your Zulip feed
immediately, even though your browser may only get confirmation that
the message was received by the server a few hundred milliseconds
later.

In Zulip, locally echoed messages are displayed without a visible
timestamp, so that (for debugging purposes) one can visually tell them
apart from messages that have been confirmed by the server.  Once the
client is able to deliver the message to the server, and the server
confirms receipt of the message, Zulip rerenders the message to
display the timestamp.  You can see this in action by using the
following procedure:

1. Disconnect your computer from the Internet.

2. Send a message by following the instructions located
[here](/help/send-a-stream-message) for public streams or
[here](/help/send-a-private-message) for private messages.

3. After you send your message, it will appear below all the previous
messages, but with no timestamp.  If the browser gets an error from
the server or otherwise cannot confirm receipt, it will report an
error in your browser window.

4. Reconnect your computer to the Internet.

5. A few seconds later, your message will be updated to contains the
timestamp on the right side of the message body.

![Message time](/static/images/help/message-exact-time.png)

Zulip is designed to store locally echoed message content in local
storage and replay it when your browser reconnects to the Internet, to
avoid issues where messages users thought they sent are lost.
