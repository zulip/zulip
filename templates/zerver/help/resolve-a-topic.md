# Resolve a topic

Zulip's topics are ideal for discussing workflow, including support,
issues, production errors, and much more.

Resolving topics can support workflow in a variety of ways, and it's
common to have different policies on using it for different streams
even within an organization. A common approach is support contexts is
to mark topics as resolved when one would close a support ticket,
either because the question was answered, or because investigation is
complete and remaining work has been transferred to an external issue
tracker.

Marking a topic as resolved renames it (`example topic` becomes `✔
example topic`) and triggers an automated message from Notification
Bot explaining that you resolved the topic.

Users can resolve/unresolve topics when they have permission to edit
the topic.  Organization administrators can [configure who can edit
topics](/help/configure-who-can-edit-topics), or turn off message
editing entirely. See the [guide to message and topic
editing](/help/configure-message-editing-and-deletion) for the details
on when topic editing is allowed.

## Mark a topic as resolved

{start_tabs}

{!topic-actions.md!}

1. Select **Mark as resolved**.

{end_tabs}

## Mark a topic as unresolved

{start_tabs}

{!topic-actions.md!}

1. Select **Mark as unresolved**.

{end_tabs}

Marking a topic as unresolved edits its name to remove the `✔ ` and
triggers an automated message from Notification Bot explaining that
you unresolved the topic.

## Details

* Resolving a topic works by moving the messages to a new topic.
* Like with all topic editing, Zulip clients update instantly, so
  human users will likely only send messages to the resolved topic.
* [Integrations](/integrations) will usually send new messages to the
  original topic (`example topic`) after a topic is resolved. This is
  useful for alerting integrations, where a repeat alert might have a
  different cause. You can mark the topic as resolved as normal once
  you've investigated the situation.
* Users can still send messages to a topic after it is resolved; this
  is important for thank you messages as well as to discuss whether
  the topic was incorrectly marked as resolved.

## Related articles

* [Rename a topic](/help/rename-a-topic)
* [API documentation for resolving topics](/api/update-message)
