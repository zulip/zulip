# Require topics in stream messages

{!admin-only.md!}

By default, users are not required to specify a topic in stream messages; if
a user sends a message without a topic, the message's topic is displayed as
**(no topic)**.

If [message editing](/help/configure-message-editing-and-deletion) is
enabled, any other user can then edit the topic of messages without a
topic to set a topic, regardless of the value of the [topic editing
policy](/help/configure-who-can-edit-topics).

You can instead choose to require a topic for new stream messages.

### Require topics in stream messages

{start_tabs}

{settings_tab|organization-settings}

2. Under **Message feed**, select **Require topics in messages to streams**.

{!save-changes.md!}

{end_tabs}
