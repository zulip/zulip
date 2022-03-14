# Status and availability

Status and availability let everyone know roughly how quickly you'll be
responding to messages.

A **status** is a customizable emoji, along with a short message. A typical
status might be "📅 In a meeting" or "🏠 Working remotely". To make them easy to
notice, status emoji are shown next to your name in the sidebars, message feed,
and compose box.

Your **availability** is a colored dot (like <span class="indicator green
solid"></span>) that indicates if you're currently active on Zulip, idle,
offline, or unavailable.

## Statuses

### Set a status

You can set a status emoji, status message, or both.

{start_tabs}

1. Hover over your name in the right sidebar.

1. Click the ellipsis (<i class="zulip-icon zulip-icon-ellipsis-v-solid"></i>) to the right.

1. Click **Set a status**.

1. Click to select one of the common statuses, *or* choose any emoji and/or
   write a short message.

1. Click **Save**.

{end_tabs}

### View a status

Status emoji are shown next to a user's name in the sidebars, message feed,
and compose box.

You can view status messages by hovering over your or anyone else's name in the
left or right sidebar, or by clicking the user's name or avatar in the main
message feed. If someone hasn't set a message as part of their status, then no
status message will appear.

## Availability

There are four possible availabilities:

* **Active** (<span class="indicator green solid"></span>): Zulip is
  open and in focus on web, desktop or mobile, or was in the last 140
  seconds.

* **Idle** (<span class="indicator orange"></span>): Zulip is open on
  your computer (either desktop or web), but you are not active.

* **Offline** (<span class="indicator grey"></span>): Zulip is not
  open on your computer.

* **Unavailable** (<span class="indicator grey-line"></span>): You can
  always manually set your availability to unavailable.


You can see when someone was last recorded as active by hovering over
their name in the left or right sidebar (even if the user is marked as
unavailable).

### Set yourself as unavailable

{start_tabs}

1. Hover over your name in the right sidebar.

1. Click the ellipsis (<i class="zulip-icon zulip-icon-ellipsis-v-solid"></i>) to the right.

1. Click **Set yourself as unavailable**.

{end_tabs}

You can use the same menu to mark yourself available again as well.

### Disable updating availability

Zulip supports the privacy option of never updating the availability
information for your account.  The result is that you will always
appear to other users as **Offline** (or **Unavailable**, if you've
set an appropriate status), regardless of your activity in Zulip.

With this setting, your "Last active" time displayed to other users in
the UI will be frozen as the time you enabled this setting.

{start_tabs}

{settings_tab|account-and-privacy}

1. Under **Privacy**, toggle **Display my availability to other users**.

{end_tabs}

Note that because this setting works by making your availability stop
updating, you'll still appear to other users as active for a few
minutes after disabling updates to your availability.

## Typing notifications

Zulip displays typing notifications when viewing a private message or
group private message conversation to which one of the other
participants is currently composing a message.

Typing notifications are only sent while one is actively editing text
in the compose box, and they disappear if typing is paused for about
15 seconds.  Just having the compose box open will not send a typing
notification.

### Disable typing notifications

If you'd prefer that others not know whether you're typing, you can
configure Zulip to not send typing notifications.

{start_tabs}

{settings_tab|account-and-privacy}

1. Under **Privacy**, toggle **Let recipients see when I'm typing
   private messages**.

{end_tabs}
