# Resolve a topic

Zulip's [topics](/help/introduction-to-topics) are very
helpful for customer support, answering questions, investigating
issues and production errors, as well as other workflows.
Resolving topics makes it easy to track the status of each question,
investigation, or notification.

Marking a topic as resolved:

* Puts a ✔ at the beginning of the topic name, e.g. `example topic`
  becomes `✔ example topic`.
* Triggers an automated notice from the [notification
  bot](/help/configure-automated-notices) indicating that
  you resolved the topic. This message will be marked as unread
  only for users who had participated in the topic.
* Changes whether the topic appears when using the `is:resolved` and
  `-is:resolved` [search filters](/help/search-for-messages#search-filters).

Marking a topic as unresolved removes the ✔ and also triggers an
automated notice from the notification bot.

It's often helpful to define a policy for when to resolve topics that
fits how topics are used in a given channel. Here are some common
approaches for deciding when to mark a topic as resolved:

* **Support**: When the support interaction is complete. Resolving
  topics is particularly useful for internal support teams that might
  not need a dedicated support ticket tracker.
* **Issues, errors and production incidents**: When investigation or
  incident response is complete, and any follow-up work has been
  transferred to the appropriate tracker.
* **Workflow management**: When the work described in the topic is
  complete and any follow-ups have been transcribed.
* **Answering questions**: When the question has been fully answered,
  and follow-ups would be best discussed in a new topic.

Users can resolve and unresolve a topic if they have permission to edit
topics. Organization administrators can [configure who can edit
topics](/help/restrict-moving-messages).

## Mark a topic as resolved

{start_tabs}

{tab|desktop-web}

{!topic-actions.md!}

1. Select **Mark as resolved**.

!!! tip ""

    You can also click on the **✔** icon in the message recipient bar to
    mark an unresolved topic as resolved.

{tab|mobile}

{!topic-long-press-menu.md!}

1. Tap **Resolve topic**.

{!topic-long-press-menu-tip.md!}

{end_tabs}

## Mark a topic as unresolved

{start_tabs}

{tab|desktop-web}

{!topic-actions.md!}

1. Select **Mark as unresolved**.

!!! tip ""

    You can also click on the **✔** icon in the message recipient bar to
    mark a resolved topic as unresolved.

{tab|mobile}

{!topic-long-press-menu.md!}

1. Tap **Unresolve topic**.

{!topic-long-press-menu-tip.md!}

{end_tabs}

## Details

* Resolving a topic works by moving the messages to a new topic.
* Like with all topic editing, Zulip clients update instantly, so
  human users will likely only send messages to the resolved topic.
* [Integrations](/integrations/) will usually send new messages to the
  original topic (`example topic`) after a topic is resolved. This is
  useful for alerting integrations, where a repeating alert might have a
  different cause. You can mark the topic resolved (as normal) once
  you've investigated the situation.
* Users can still send messages to a resolved topic; this
  is important for _"thank you"_ messages and to discuss whether
  the topic was incorrectly marked as resolved.

## Related articles

* [Rename a topic](/help/rename-a-topic)
* [Move content to another topic](/help/move-content-to-another-topic)
* [Restrict topic editing](/help/restrict-moving-messages)
* [API documentation for resolving topics](/api/update-message)
