# Incoming email integration

Zulip's incoming email gateway integration makes it possible to send
messages into Zulip by sending an email. It's highly recommended
because it enables:

- When users reply to one of Zulip's message notification emails
  from their email client, the reply can go directly
  into Zulip.
- Integrating third-party services that can send email notifications
  into Zulip. See the [integration
  documentation](https://zulip.com/integrations/doc/email) for
  details.

Once this integration is configured, each stream will have a special
email address displayed on the stream settings page. Emails sent to
that address will be delivered into the stream.

There are two ways to configure Zulip's email gateway:

1. Local delivery (recommended): A postfix server runs on the Zulip
   server and passes the emails directly to Zulip.
1. Polling: A cron job running on the Zulip server checks an IMAP
   inbox (`username@example.com`) every minute for new emails.

The local delivery configuration is preferred for production because
it supports nicer looking email addresses and has no cron delay. The
polling option is convenient for testing/developing this feature
because it doesn't require a public IP address, setting up MX
records in DNS, or adjusting firewalls.

:::{note}
Incoming emails are rate-limited, with the following limits:

- 50 emails per minute.
- 120 emails per 5 minutes.
- 600 emails per hour.

:::

## Local delivery setup

Zulip's Puppet configuration provides everything needed to run this
integration; you just need to enable and configure it as follows.

The main decision you need to make is what email domain you want to
use for the gateway; for this discussion we'll use
`emaildomain.example.com`. The email addresses used by the gateway
will look like `foo@emaildomain.example.com`, so we recommend using
`EXTERNAL_HOST` here.

We will use `hostname.example.com` as the hostname of the Zulip server
(this will usually also be the same as `EXTERNAL_HOST`, unless you are
using an [HTTP reverse proxy][reverse-proxy]).

1. Using your DNS provider, create a DNS MX (mail exchange) record
   configuring email for `emaildomain.example.com` to be processed by
   `hostname.example.com`. You can check your work using this command:

   ```console
   $ dig +short emaildomain.example.com -t MX
   1 hostname.example.com
   ```

1. If you have a network firewall enabled, configure it to allow incoming access
   to port 25 on the Zulip server from the public internet. Other mail servers
   will need to use it to deliver emails to Zulip.

1. Log in to your Zulip server; the remaining steps all happen there.

1. Add `, zulip::postfix_localmail` to `puppet_classes` in
   `/etc/zulip/zulip.conf`. A typical value after this change is:

   ```ini
   puppet_classes = zulip::profile::standalone, zulip::postfix_localmail
   ```

1. If `hostname.example.com` is different from
   `emaildomain.example.com`, add a section to `/etc/zulip/zulip.conf`
   on your Zulip server like this:

   ```ini
   [postfix]
   mailname = emaildomain.example.com
   ```

   This tells postfix to expect to receive emails at addresses ending with
   `@emaildomain.example.com`, overriding the default of
   `@hostname.example.com`. It will also identify itself as
   `emaildomain.example.com` on any outgoing emails it sends.

1. Run `/home/zulip/deployments/current/scripts/zulip-puppet-apply`
   (and answer `y`) to apply your new `/etc/zulip/zulip.conf`
   configuration to your Zulip server.

1. Edit `/etc/zulip/settings.py`, and set `EMAIL_GATEWAY_PATTERN`
   to `"%s@emaildomain.example.com"`.

1. Restart your Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

Congratulations! The integration should be fully operational.

[reverse-proxy]: deployment.md#putting-the-zulip-application-behind-a-reverse-proxy

## Polling setup

1. Create an email account dedicated to Zulip's email gateway
   messages. We assume the address is of the form
   `username@example.com`. The email provider needs to support the
   standard model of delivering emails sent to
   `username+stuff@example.com` to the `username@example.com` inbox.

1. Edit `/etc/zulip/settings.py`, and set `EMAIL_GATEWAY_PATTERN` to
   `"username+%s@example.com"`.

1. Set up IMAP for your email account and obtain the authentication details.
   ([Here's how it works with Gmail](https://support.google.com/mail/answer/7126229?hl=en))

1. Configure IMAP access in the appropriate Zulip settings:

   - Login and server connection details in `/etc/zulip/settings.py`
     in the email gateway integration section (`EMAIL_GATEWAY_LOGIN` and others).
   - Password in `/etc/zulip/zulip-secrets.conf` as `email_gateway_password`.

1. Test your configuration by sending emails to the target email
   account and then running the Zulip tool to poll that inbox:

   ```bash
   su zulip -c '/home/zulip/deployments/current/manage.py email_mirror'
   ```

1. Once everything is working, install the cron job which will poll
   the inbox every minute for new messages using the tool you tested
   in the last step:
   ```bash
   cd /home/zulip/deployments/current/
   sudo cp puppet/zulip/files/cron.d/email-mirror /etc/cron.d/
   ```

Congratulations! The integration should be fully operational.
