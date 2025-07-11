# Marking messages as read

Zulip automatically keeps track of which messages you have and haven't read.
Unread messages have a line along the left side, which fades when the message
gets marked as read.

Zulip offers tools to manually mark one or more messages as read, and you can
configure whether messages are marked as read automatically when you scroll.

## Configure whether messages are automatically marked as read

You can choose how messages are automatically marked as read in the Zulip web
and mobile apps. You can configure the mobile app differently from the
web/desktop app.

- **Always**: Messages are marked as read whenever you scroll through them in
  the app. You may be used to this from other chat applications.
- **Only in conversation views**: In Zulip, a **conversation** is a [direct
  message](/help/direct-messages) thread (one-on-one or with a group), or a
  [topic in a channel](/help/introduction-to-topics). This option makes it
  convenient to preview new messages in a channel, or skim [Combined
  feed](/help/combined-feed), and later read each topic in detail.
- **Never**: Messages are marked as read only manually. For example,
  if you often need to follow up on messages at your computer after
  reading them in the mobile app, you can choose this option for the
  mobile app.

{start_tabs}

{tab|desktop-web}

{settings_tab|preferences}

1. Under **Navigation**, click on the **Automatically mark messages as
   read** dropdown, and select **Always**, **Never** or **Only in
   [conversation](/help/reading-conversations) views**.

{tab|mobile}

{!mobile-settings.md!}

1. Tap **Mark messages as read on scroll**.

1. Select **Always**, **Never** or **Only in
   [conversation](/help/reading-conversations) views**.

{end_tabs}

## Configure whether resolved topic notices are marked as read

Zulip lets you automatically mark as read [notification
bot](/help/configure-automated-notices) notices indicating that someone
[resolved or unresolved](/help/resolve-a-topic) a topic, or do so just for
topics you don't follow.

{start_tabs}

{tab|desktop-web}

{settings_tab|notifications}

1. Under **Topic notifications**, configure **Automatically mark resolved topic
   notices as read**.

{end_tabs}

## Mark a message as read

{start_tabs}

{tab|desktop-web}

1. Select the message using the **blue box** to mark it as read. You can scroll
   the **blue box** using the mouse, or with [keyboard navigation
   shortcuts](/help/keyboard-shortcuts#navigation).

{end_tabs}

## Mark all messages in a channel or topic as read

{start_tabs}

{tab|via-left-sidebar}

1. Hover over a channel or topic in the left sidebar.

1. Click on the **ellipsis** (<i class="zulip-icon zulip-icon-more-vertical"></i>).

1. Click **Mark all messages as read**.

!!! tip ""

    You can also mark all messages in your current view as read by
    jumping to the bottom with the **Scroll to bottom**
    (<i class="fa fa-chevron-down"></i>) button or the <kbd>End</kbd> shortcut.

{tab|via-inbox-view}

{!go-to-inbox.md!}

1. Click on an unread messages counter to mark all messages in that topic or
   channel as read.

{tab|via-recent-conversations}

{!go-to-recent-conversations.md!}

1. Click on an unread messages counter in the **Topic** column to mark all
   messages in that topic as read.

{tab|mobile}

1. Press and hold a channel or topic until the long-press menu appears.

1. Tap **Mark channel as read** or **Mark topic as read**.

!!! tip ""

    You can also scroll down to the bottom of a message view, and tap **Mark
    all messages as read**.

{end_tabs}

## Mark messages in multiple topics and channels as read

In the web and desktop apps, you can mark all messages as read, or just messages
in muted topics or topics you don't follow.

{start_tabs}

{tab|desktop-web}

1. Hover over your [home view](/help/configure-home-view) in the left sidebar.

1. Click on the **ellipsis** (<i class="zulip-icon zulip-icon-more-vertical"></i>).

1. Select the desired option from the dropdown, and click **Confirm**.

!!! tip ""

    You can also mark all messages in your current view as read by
    jumping to the bottom with the **Scroll to bottom**
    (<i class="fa fa-chevron-down"></i>) button or the <kbd>End</kbd> shortcut.

{tab|mobile}

1. Tap the **Combined feed**
   (<i class="zulip-icon zulip-icon-all-messages mobile-help"></i>) tab.

1. Scroll down to the bottom of the message view, and tap **Mark all messages
   as read**.

{end_tabs}

## Related articles

* [Marking messages as unread](/help/marking-messages-as-unread)
* [Configure where you land in message feeds](/help/configure-where-you-land)
* [Reading strategies](/help/reading-strategies)
* [Read receipts](/help/read-receipts)
