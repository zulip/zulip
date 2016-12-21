# Viewing information about a message

To view more information about a message, first locate the message you want to learn more about in your view. Click on the name of the user that sent the message; the message sender's name turns blue upon hover.

![Message sender name](/static/images/help/message-info-sender.png)

Upon clicking on the message sender's name, a tooltip will appear with more information about the message.

![Message info](/static/images/help/message-info-default.png)

## Information about a message

![Message info](/static/images/help/message-info.png)

1. The **Message to stream** section describes which stream the message was sent to.

    In this example, the message was sent to the **Denmark** stream.

2. The **Sent by** section displays the username and email address of the message sender.

    In this example, **King Hamlet** sent the messsage. His email address is **hamlet@zulip.com**.

3. This **Timestamp** section shows the exact date and time at which the message was sent.

    In this example, the message was sent at **December 20, 2016** at **8:23:20 A.M. PST (UTC -8)**.

4. Clicking the **Send a private message** link allows you to directly send a private message to the message sender.

    ![Message info private message send](/static/images/help/message-info-private-send.png)

    In this example, clicking on the link transforms your messaging box to send a private message to **King Hamlet**.

5. Clicking the **Narrow to private message** link narrows your view to display all private messages exchanged between the message sender and you by using the search operator `pm-with`.

    ![Message info private message narrow](/static/images/help/message-info-private-narrow.png)

    In this example, clicking on the link transforms your view to show all private messages exchanged between **King Hamlet** and you by using the search operator `pm-with:hamlet@zulip.com`.

6. Clicking the **Narrow to messages sent by** link narrows your view to display all messages the message sender sent to streams that you're subscribed to and private group chats you're both in using the search operator by `sender`.

    ![Message info sender messages](/static/images/help/message-info-messages.png)

    In this example, clicking on the link transforms your view to show all messages sent by **King Hamlet** sent to public streams you're subscribed to as well as private group chats you're both in by using the search operator `sender:hamlet@zulip.com`.
