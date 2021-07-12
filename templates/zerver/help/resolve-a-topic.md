# Resolve a topic

Zulip's [topics](/help/about-streams-and-topics) are ideal for discussing
workflow, including support, issues, production errors, and much more.

Resolving topics can support workflow in several ways, and it's
common to have various policies on using it for different streams
within an organization. A common approach in support contexts is to
mark topics as resolved when an agent closes a support ticket. For
example, you solve it because you answered the question or because
your investigation is complete and you have transferred the remaining
work to an external issue tracker.

Marking a topic as resolved renames it (`example topic` becomes `✔
example topic`) and triggers an automated message from Notification
Bot explaining that you resolved the topic.

Users can resolve and unresolve a topic if they have permission to edit
topics. Organization administrators can [configure who can edit
topics](/help/configure-who-can-edit-topics) or turn off message
editing entirely. See the [guide to message and topic
editing](/help/configure-message-editing-and-deletion) for the details
on when topic editing is allowed.

## Mark a topic as resolved

Marking a topic as resolved edits its name to add the `✔ ` and
triggers an automated message from Notification Bot explaining that
you resolved the topic.

### Via the message topic bar

{start_tabs}

1. Hover over a topic in the message recipient pane.

2. Click on the **✔** icon to mark it as resolved.

{end_tabs}

### Via the left sidebar

{start_tabs}

{!topic-actions.md!}

1. Select **Mark as resolved**.

{end_tabs}

## Mark a topic as unresolved

Marking a topic as unresolved edits its name to remove the `✔ ` and
triggers an automated message from Notification Bot explaining that
you unresolved the topic.

### Via the message topic bar

{start_tabs}

1. Hover over a topic in the message recipient pane.

2. Click on the **✔** icon to mark it as unresolved.

{end_tabs}

### Via the left sidebar

{start_tabs}

{!topic-actions.md!}

1. Select **Mark as unresolved**.

{end_tabs}


## Details

* Resolving a topic works by moving the messages to a new topic.
* Like with all topic editing, Zulip clients update instantly, so
  human users will likely only send messages to the resolved topic.
* [Integrations](/integrations) will usually send new messages to the
  original topic (`example topic`) after a topic is resolved. This is
  useful for alerting integrations, where a repeating alert might have a
  different cause. You can mark the resolved topic as normal once
  you've investigated the situation.
* Users can still send messages to a resolved topic; this
  is important for _"thank you"_ messages and to discuss whether
  the topic was incorrectly marked as resolved.

## Related articles

* [Rename a topic](/help/rename-a-topic)
* [API documentation for resolving topics](/api/update-message)
