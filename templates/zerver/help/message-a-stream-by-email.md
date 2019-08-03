# Message a stream by email

You can send emails to Zulip streams. This can be useful

* If you have an email that you want to discuss on Zulip

* For mirroring mailing list traffic

* For integrating a third-party app that can send emails, but which does not
  easily lend itself to a more direct integration

If you're planning on doing this in an automated way, and have some
programming experience, another option is to use our [send message
API](/api/send-message).

### Message a stream by email

{start_tabs}

{relative|stream|subscribed}

1. Select a stream.

1. Copy the stream email address under **Email address**.

1. Send an email to that address.

!!! warn ""
    If you don't see the **Email address** section, most likely your server
    administrator has not configured an
    [email gateway](https://zulip.readthedocs.io/en/latest/production/email-gateway.html).

{end_tabs}

The email subject will become the Zulip topic, and the email body will
become the Zulip message.

Note that it may take up to one minute for the message to show
up in Zulip.

## Configuration options

The options below control which parts of the email are included in the
Zulip message.  To add a configuration option, add it right before the `@`
in the email address.

For example, if the stream email address is
`general.abcd1234@example.zulipchat.com`, you can add the first two options
below by sending email to
`general.abcd1234.show-sender.include-footer@example.zulipchat.com` instead.

* **.show-sender**: Adds `From: <Sender email address>` to
  the top of the Zulip message.

* **.include-footer**: By default, Zulip tries to automatically remove some footer
  text (like signatures). With this option, Zulip will include all footers.

* **.include-quotes**: In many email clients, when you reply to a message
  (e.g. a missed message email), a copy of the original message is
  automatically added to the bottom of your reply. By default, Zulip tries
  to remove that copied message. With this option, Zulip will include it.
