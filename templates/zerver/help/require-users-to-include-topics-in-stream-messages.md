# Require users to include topics in stream messages

{!admin-only.md!}

By default, users are not required to specify the topics of their stream
messages; if a user sends a message without a topic, the message's topic is
displayed as **(no topic)**.

Organization administrators can choose to enforce the inclusion of topics in
stream messages by following the following steps.

{!go-to-the.md!} [Organization permissions](/#organization/organization-permissions)
{!admin.md!}

2. Select the **Require topics in messages to streams** checkbox.

{!save-changes.md!} organization settings.

Once this setting is enabled, any users that attempt to send a stream message
without a specified topic will see a warning in the compose box and will be
prevented from sending their message.
