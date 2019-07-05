# Incoming email integration

Zulip's incoming email gateway integration makes it possible to send
messages into Zulip by sending an email.  It's highly recommended
because it enables:

* When users reply to one of Zulip's missed message email
  notifications from their email client, the message is .
* Integrating third-party services that can send email notifications
  into Zulip.  See the [integration
  documentation](https://zulipchat.com/integrations/doc/email) for
  details.

Once this integration is configured, each stream will have an email
address documented on the stream settings page and emails sent to that
address will be delivered into the stream.

There are two ways to configure email mirroring in Zulip:

  1. Local delivery (recommended): A postfix server runs on the Zulip
    server and passes the emails directly to Zulip.
  1. Polling: A cron job running on the Zulip server checks an IMAP
    inbox (`username@example.com`) every minute for new emails.

The local delivery configuration is preferred for production because
it supports nicer looking email addresses and has no cron delay.  The
polling option is convenient for testing/developing this feature
because it doesn't require a public IP address or setting up MX
records in DNS.

## Local delivery setup

In this discussion, we assume your Zulip server has a hostname of
`hostname.example.com`, and EXTERNAL_HOST is `zulip.example.com`
(for most installations `hostname` and `zulip` will be the same, but
if you are using an [HTTP reverse proxy][reverse-proxy], they may not be).

1. Using your DNS provider, configure a DNS MX (mail exchange) record.
   The record should cause email for `zulip.example.com` to be
   processed by `hostname.example.com`.  If you did this correctly,
   the output of `dig -t MX zulip.example.com` should look like this:

    ```
    tabbott@coset:~$ dig zulip.example.com -t MX | grep 'IN.*MX'
    ;zulip.example.com.     IN  MX
    zulip.example.com.      82  IN  MX  1  hostname.example.com.
    ```

1. Login to your Zulip server; the remaining steps are all done there.

1.  If `hostname` is different from `zulip`, add a section to
   `/etc/zulip/zulip.conf` on your Zulip server like this:

    ```
    [postfix]
    mailname = zulip.example.com
    ```

    This tells postfix to expect to receive emails at addresses ending
    with `@zulip.example.com`, overriding the default of
    `@hostname.example.com`.

1. Add `, zulip::postfix_localmail` to `puppet_classes` in
   `/etc/zulip/zulip.conf`.  A typical value after this change is:
   ```
   puppet_classes = zulip::voyager, zulip::postfix_localmail
   ```

1. Run `/home/zulip/deployments/current/scripts/zulip-puppet-apply`
   (and answer `y`) to apply your new `/etc/zulip/zulip.conf`
   configuration to your Zulip server.

1. Configure the email address pattern (`EMAIL_GATEWAY_PATTERN` in
   `/etc/zulip/settings.py`), setting it to `%s@zulip.example.com`.

1. Restart your Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

Congratulations!  The integration should be fully operational.

[reverse-proxy]: ../production/deployment.html#putting-the-zulip-application-behind-a-reverse-proxy

## Polling setup

  1. Set up an email account dedicated to Zulip email gateway messages.
    We assume the address is of the form `username@example.com`.

  1. Configure the email address pattern (`EMAIL_GATEWAY_PATTERN` in
   `/etc/zulip/settings.py`), setting it to `username+%s@example.com`.
   You want to make sure your email provider will deliver emails to
   addresses of this form to your `username@example.com` inbox. This
   is a default with major providers like Gmail.

  1. Set up IMAP for your email account and obtain the authentication details.
    ([Here's how it works with Gmail](https://support.google.com/mail/answer/7126229?hl=en))

  1. Configure IMAP access in the appropriate Zulip settings:

      * Login and server connection details in `/etc/zulip/settings.py`
        in the email gateway integration section (`EMAIL_GATEWAY_LOGIN` and others).
      * Password in `/etc/zulip/zulip-secrets.conf` as `email_gateway_password`.

  1. Set up a cron job to run `./manage.py email_mirror`, which will check the inbox
    and batch-process any new messages.
    (See `puppet/zulip/files/cron.d/email-mirror` for an example)
