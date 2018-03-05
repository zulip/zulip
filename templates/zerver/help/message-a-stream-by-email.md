# Message a stream by email

You can send a message to a stream by email by following the following steps.

{!subscriptions.md!}
{!filter-streams.md!}

2. Select the stream that you want to message by email in the
{{ subscriptions_html|safe }}; {!stream-settings.md!}

3. To send a message to a stream by email, simply send an email to the stream's
email address displayed in the **Email address** section. Your email subject
will become the message's topic, and your email body will become the message's
contents.

4. After you send an email to the stream's email address, your email will be
forwarded to the stream and sent as a message.

!!! tip ""
    This feature requires server-level configuration in the
    **EMAIL GATEWAY INTEGRATION** section of `/etc/zulip/settings.py`.
    On a server that hasn't configured this feature, the **Email address**
    section will not be displayed.
