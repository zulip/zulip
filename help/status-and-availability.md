# Status and availability

Status and availability let everyone know roughly how quickly you'll be
responding to messages.

A **status** is a customizable emoji, along with a short message. A typical
status might be "📅 In a meeting" or "🏠 Working remotely". To make it easy to
notice, the status emoji is shown next to your name in the sidebars, message
feed, and compose box.

Your **availability** is a colored dot (like <span class="user-circle user-circle-active zulip-icon zulip-icon-user-circle-active"></span>) that indicates if you're currently active on Zulip, idle,
or offline. You can also [go invisible](#invisible-mode) to appear offline
to other users.

## Statuses

### Set a status

You can set a status emoji, status message, or both.

{start_tabs}

{tab|via-user-card}

{!self-user-card.md!}

{!set-status.md!}

{tab|via-personal-settings}

{!personal-menu.md!}

{!set-status.md!}

{tab|mobile}

Access this feature by following the web app instructions in your
mobile device browser.

Implementation of this feature in the mobile app is tracked [on
GitHub](https://github.com/zulip/zulip-flutter/issues/198). If
you're interested in this feature, please react to the issue's
description with 👍.

{end_tabs}

### Clear a status

{start_tabs}

{tab|via-user-card}

{!self-user-card.md!}

{!clear-status.md!}

{tab|via-personal-settings}

{!personal-menu.md!}

{!clear-status.md!}

{end_tabs}

### View a status

Status emoji are shown next to a user's name in the sidebars, message feed,
and compose box in the web and desktop apps, and next to the user's profile
picture and name in the mobile app.

Status emoji and status messages are also shown on [user cards](/help/user-cards)
in the web and desktop apps.

{start_tabs}

{tab|desktop-web}

1. Hover over a user's name in the right sidebar, or in the **Direct messages**
   section in the left sidebar, to view their status message if they have one
   set.

!!! tip ""

    You can also click on a user's profile picture or name on a message they
    sent to view their status in their **user card**, or configure status text
    to always be shown in the right sidebar.

{tab|mobile}

1. Tap on a user's profile picture or name to view their status message.

1. If they have one set, it will appear under their name on their profile.

{end_tabs}

### Configure how statuses are displayed

You can choose whether or not status text is displayed in the right sidebar.
With the compact option, only status emoji are shown.

{start_tabs}

{tab|desktop-web}

{settings_tab|preferences}

1. Under **Information**, select **Compact** or **Show status and text** for the
   user list style.

!!! tip ""

    You can always hover over a user's name in the right sidebar to view their
    status message if they have one set.

{end_tabs}

## Availability

There are three availability states:

* **Active** (<span class="user-circle user-circle-active zulip-icon
  zulip-icon-user-circle-active"></span>): Zulip is open and in focus on web,
  desktop or mobile, or was in the last 140 seconds.

* **Idle** (<span class="user-circle user-circle-idle zulip-icon
  zulip-icon-user-circle-idle"></span>): Zulip is open on your computer (either
  desktop or web), but you are not active.

* **Offline** (<span class="user-circle user-circle-offline zulip-icon
  zulip-icon-user-circle-offline"></span>): Zulip is not open on your computer,
  or you have turned on invisible mode.

### View availability

{start_tabs}

{tab|desktop-web}

1. View a user's availability on the [user list](/help/user-list) in the right
   sidebar, the [direct messages](/help/direct-messages) list in the left
   sidebar, or their [user card](/help/user-cards). If there is no availability
   indicator, the user is offline.

!!! tip ""

    You can see when someone offline was last active by hovering over their
    name in the left or right sidebar.

{tab|mobile}

1. Tap on a user's profile picture or name. Their availability appears to the
   left of their name on their profile.

{end_tabs}

### Invisible mode

Zulip supports the privacy option of never updating the availability
information for your account. The result is that you will always
appear to other users as **Offline**, regardless of your activity in
Zulip.

With this setting, your "Last active" time displayed to other users in
the UI will be frozen as the approximate time you enabled this setting.
Your activity will still be included in your organization's [statistics](/help/analytics).

!!! tip ""

    Consider also [not
    allowing](/help/read-receipts#configure-whether-zulip-lets-others-see-when-youve-read-messages)
    other users to see when you have read messages.

### Toggle invisible mode

{start_tabs}

{tab|desktop-web}

{!self-user-card.md!}

1. To enable, you'll select **Go invisible**.

1. To disable, you'll select **Turn off invisible mode**.

!!! tip ""

    You can also toggle this setting in the **Account & privacy**
    tab of your **Personal settings** menu.

{tab|mobile}

{!mobile-menu.md!}

1. Tap **My profile**.

1. Toggle **Invisible mode**.

{end_tabs}

## Related articles

* [Typing notifications](/help/typing-notifications)
* [Read receipts](/help/read-receipts)
