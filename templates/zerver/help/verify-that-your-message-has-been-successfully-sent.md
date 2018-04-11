# Verify that your message has been successfully sent

When you send a message in a chat tool, it can take a few hundred milliseconds
for your message to transmitted to the server, stored, and transmitted to active
clients by the server, depending on where you are located in relation to the
relevant server.

Like most other chat tools, Zulip optimizes the experience for the
sender by "locally echoing" the message, i.e. displaying it in your
Zulip feed immediately, even though your browser may not get
confirmation that the message was received by the server until a few
hundred milliseconds later.

Zulip is designed to store locally echoed message content in local
storage and resend it when your browser reconnects to the Internet.
This helps prevent issues where messages that you thought you had sent
never arrives.  Once the client is able to deliver the message to the
server, and the server confirms receipt of the message, Zulip
rerenders the message to display the timestamp, so you can look for
the timestamp to determine whether a message has been successfully
received by the server.

Follow the following steps to to see this in action.

1. Disconnect your computer from the Internet.

2. Send a message by following the instructions located
[here](/help/send-a-stream-message) for public streams or
[here](/help/send-a-private-message) for private messages.

3. After you send your message, it will appear below all the previous
messages, but with no timestamp.  If the browser gets an error from
the server or otherwise cannot confirm receipt, it will report an
error in your browser window.

4. Reconnect your computer to the Internet.

5. A few seconds later, your message will be updated to contain the
timestamp on the right side of the message body.

    ![Message time](/static/images/help/message-exact-time.png)

Zulip is designed to store locally echoed message content in local
storage and replay it when your browser reconnects to the Internet.
This should ensure that messages that users thought they had sent get
delivered eventually.
