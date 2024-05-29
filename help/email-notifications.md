# Email notifications

## Message notification emails

Zulip can be configured to send message notification emails for [DMs
and mentions](/help/dm-mention-alert-notifications), as well as
[channel messages](/help/channel-notifications).

{start_tabs}

{settings_tab|notifications}

1. Toggle the checkboxes for **Channels** and **DMs, mentions, and alerts**
   in the **Email** column of the **Notification triggers** table.

{end_tabs}

You can [respond to Zulip messages directly][reply-from-email] by
replying to message notification emails, unless you are connecting to
a self-hosted Zulip server whose system administrator has not
configured the [incoming email gateway][incoming-email-gateway].

[incoming-email-gateway]: https://zulip.readthedocs.io/en/stable/production/email-gateway.html

### Delay before sending emails

To reduce the number of emails you receive, Zulip
delays sending message notification emails for a configurable period
of time (default: 2 minutes).  The delay
helps in a few ways:

* No email is sent if you return to Zulip and read the message before
  the email would go out.
* Edits made by the sender soon after sending a message will be
  reflected in the email.
* Multiple messages in the same Zulip [conversation](/help/reading-conversations)
  are combined into a single email. (Different conversations will always be in
  separate emails, so that you can [respond directly from your
  email](/help/using-zulip-via-email)).

To configure the delay for message notification emails:

{start_tabs}

{settings_tab|notifications}

1. Under **Email message notifications**, select the desired time period from the
   **Delay before sending message notification emails** dropdown.

{end_tabs}


### Include organization name in subject line

You can configure whether the name of your Zulip organization is included in the
subject of message notification emails.

Zulip offers a convenient **Automatic** configuration option, which includes the
name of the organization in the subject only if you have accounts in multiple
Zulip Cloud organizations, or in multiple organizations on the same Zulip server.

{start_tabs}

{settings_tab|notifications}

1. Under **Email message notifications**, configure
   **Include organization name in subject of message notification emails**.

{end_tabs}

### Hide message content

For security or compliance reasons, you may want to hide the content of your
Zulip messages from your email. Organization admins can do this at an
[organization-wide level](/help/hide-message-content-in-emails), but you can
also do this just for the messages you receive.

This setting also blocks message topics, channel names, and user names from
being sent through your email.

{start_tabs}

{settings_tab|notifications}

1. Under **Email message notifications**, toggle
   **Include message content in message notification emails**.

{end_tabs}

## New login emails

By default, Zulip sends an email whenever you log in to Zulip. These emails
help you protect your account; if you see a login email at a time or from a
device you don't recognize, you should
[change your password](/help/change-your-password) right away.

In typical usage, these emails are sent infrequently, since all Zulip apps
(web, mobile, desktop, and terminal) keep you logged in to any organization
you've interacted with in the last 1-2 weeks.

However, there are situations (usually due to corporate security policy) in
which you may have to log in every day, and where getting login emails can
feel excessive.

### Disable new login emails

{start_tabs}

{settings_tab|notifications}

1. Under **Other emails**, toggle
   **Send email notifications for new logins to my account**.

{end_tabs}

## Low-traffic newsletter

Zulip sends out a low-traffic newsletter (expect 2-4 emails a year)
to Zulip Cloud users announcing major changes in Zulip.

### Managing your newsletter subscription

{start_tabs}

{tab|zulip-cloud}

{settings_tab|notifications}

1. Under **Other emails**, toggle
   **Send me Zulip's low-traffic newsletter (a few emails a year)**.

{end_tabs}

## Related articles

* [Using Zulip via email](/help/using-zulip-via-email)
* [Message a channel by email](/help/message-a-channel-by-email)
* [Channel notifications](/help/channel-notifications)
* [Hide message content in emails (for organizations)](/help/hide-message-content-in-emails)
