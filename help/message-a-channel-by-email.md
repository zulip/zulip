# Message a channel by email

!!! tip ""

    This feature is not available on self-hosted Zulip servers where
    the [incoming email gateway][email-gateway] has not been
    configured by a system administrator.
    [email-gateway]: https://zulip.readthedocs.io/en/stable/production/email-gateway.html

You can send emails to Zulip channels. This can be useful:

* If you have an email that you want to discuss on Zulip

* For mirroring mailing list traffic

* For integrating a third-party app that can send emails, but which does not
  easily lend itself to a more direct integration

If you're planning on doing this in an automated way, and have some
programming experience, another option is to use our [send message
API](/api/send-message).

### Message a channel by email

{start_tabs}

{relative|gear|channel-settings}

1. Select a channel.

{!select-channel-view-general.md!}

1. Click **Generate email address** under **Email address**.

1. Toggle the configuration options as desired.

1. Click **Copy address** to add the channel email address to your clipboard.

1. Send an email to that address.

{end_tabs}

The email subject will become the Zulip topic, and the email body will
become the Zulip message.

Note that it may take up to one minute for the message to show
up in Zulip.

## Configuration options

The options below control which parts of the email are included in the
Zulip message.

* **The sender's email address**: Adds `From: <Sender email address>` to
  the top of the Zulip message.

* **Email footers**: By default, Zulip tries to automatically remove some footer
  text (like signatures). With this option enabled, Zulip will include all footers.

* **Quoted original email**: In many email clients, when you reply to a message
  (e.g. a message notification email), a copy of the original message is
  automatically added to the bottom of your reply. By default, Zulip tries
  to remove that copied message. With this option enabled, Zulip will include it.

* **Use html encoding**: The body of an email is typically encoded using
  one or both of two common formats: plain text (`text/plain`) and
  HTML (`text/html`).  Zulip supports constructing the Zulip message
  content using either (converting HTML to Markdown for the HTML
  format).  By default, Zulip will prefer using the plain text version
  of an email over the converted HTML version if both are present.
  Enabling this option overrides that behavior to prefer the HTML version
  instead.

## Related articles

* [Using Zulip via email](/help/using-zulip-via-email)
