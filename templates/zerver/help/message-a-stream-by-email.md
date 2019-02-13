# Message a stream by email

This can be useful if you want to copy an email into Zulip. If you're
planning on doing this in an automated way, consider using our
[send message API](/api/send-message).

{start_tabs}

{relative|stream|subscribed}

1. Select a stream.

1. Copy the email address under **Email address**.

1. Send an email to that email address.

{end_tabs}

The email subject will become the Zulip topic, and the email body will
become the Zulip message.

!!! warn ""
    If you don't see the **Email address** section, most likely your server
    administrator has not configured the **EMAIL GATEWAY INTEGRATION** section
    of `/etc/zulip/settings.py`.
