# Require users to include topics in stream messages

{!admin-only.md!}

By default, users are not required to specify the topics of messages
to streams; if a user sends a message without a topic, the message's
topic is displayed as **(no topic)**.  Any other user can then edit
the topic of such a message to set a topic.

Some organizations prefer to require that every message to a stream
includes a topic.  Organization administrators can choose to enforce
the use of topics in new messages to streams:

{!go-to-the.md!} [Organization settings](/#organization/organization-settings)
{!admin.md!}

2. Select the **Require topics in messages to streams** checkbox under the
**Message feed** section.

{!save-changes.md!} organization settings.

Once this setting is enabled, any users that attempt to send a stream
message without a specified topic will see a warning in the compose
box and will be prevented from sending their message until they
specify a topic.
