# Status and availability

Status and availability let everyone know roughly how quickly you'll be
responding to messages.

A **status** is a customizable emoji, along with a short message. A typical
status might be "📅 In a meeting" or "🏠 Working remotely". To make it easy to
notice, the status emoji is shown next to your name in the sidebars, message
feed, and compose box.

Your **availability** is a colored dot (like <span class="indicator green
solid"></span>) that indicates if you're currently active on Zulip, idle,
offline, or unavailable.

## Statuses

### Set a status

You can set a status emoji, status message, or both.

{start_tabs}

{tab|desktop-web}

{!self-user-actions-menu.md!}

1. Click **Set a status**.

1. Click to select one of the common statuses, *or* choose any emoji and/or
   write a short message.

1. Click **Save**.

{tab|mobile}

{!mobile-profile-menu.md!}

1. Tap **Set a status**.

1. Tap to select one of the common statuses, *or* choose any emoji and/or
   write a short message.

1. Tap **Save**.

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

{tab|desktop-web}

{!self-user-actions-menu.md!}

1. Click **Set yourself as unavailable**.

{tab|mobile}

{!mobile-profile-menu.md!}

1. Toggle **Set yourself to away**.

{end_tabs}

!!! tip ""

    You can also use the same menu to mark yourself as available again.

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

## Related articles

* [Typing notifications](/help/typing-notifications)
