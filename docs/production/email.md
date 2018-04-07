# Outgoing email

Zulip needs to be able to send email so it can confirm new users'
email addresses and send notifications.

## How to configure

1. Identify an outgoing email (SMTP) account where you can have Zulip
   send mail.  If you don't already have one you want to use, see
   [Email services](#email-services) below.

2. Fill out the section of `/etc/zulip/settings.py` headed "Outgoing
   email (SMTP) settings".  This includes the hostname and typically
   the port to reach your SMTP provider, and the username to log into
   it as.

3. Put the password for the SMTP user account in
   `/etc/zulip/zulip-secrets.conf` by setting `email_password`. For
   example: `email_password = abcd1234`.

   Like any other change to the Zulip configuration, be sure to
   [restart the server](settings.html) to make your changes take
   effect.

4. Test that your configuration is working.  See the test command in
   the [Troubleshooting](#troubleshooting) section below.  If it's not
   working, see the suggestions in that section.

## Email services

### Free outgoing email services

For sending outgoing email from your Zulip server, we highly recommend
using a "transactional email" service like
[SendGrid](https://sendgrid.com/docs/API_Reference/SMTP_API/integrating_with_the_smtp_api.html),
[Mailgun](https://documentation.mailgun.com/en/latest/quickstart-sending.html#send-via-smtp),
or, for AWS users,
[Amazon SES](http://docs.aws.amazon.com/ses/latest/DeveloperGuide/send-email-smtp.html).
These services are designed to send email from servers, and are by far
the easiest way to get outgoing email working reliably.

If you don't have an existing outgoing SMTP provider, don't worry!
Each of the options we recommend above (as well as dozens of other
services) have free options.  Once you've signed up, you'll want to
find the service's provided "SMTP credentials", and configure Zulip as
follows:

* The hostname like `EMAIL_HOST = 'smtp.mailgun.org'` in `/etc/zulip/settings.py`
* The username like `EMAIL_HOST_USER = 'username@example.com` in
  `/etc/zulip/settings.py`.
* The TLS setting as `EMAIL_USE_TLS = True` in
  `/etc/zulip/settings.py`, for most providers
* The port as `EMAIL_PORT = 587` in `/etc/zulip/settings.py`, for most
  providers
* The password like `email_password = abcd1234` in `/etc/zulip/zulip-secrets.conf`.

### Using Gmail for outgoing email

We don't recommend using an inbox product like Gmail for outgoing
email, because Gmail's anti-spam measures make this annoying.  But if
you want to use a Gmail account to send outgoing email anyway, here's
how to make it work:
* Create a totally new Gmail account for your Zulip server; you don't
  want Zulip's automated emails to come from your personal email address.
* If you're using 2-factor authentication on the Gmail account, you'll
  need to use an
  [app-specific password](https://support.google.com/accounts/answer/185833).
* If you're not using 2-factor authentication, read this Google
  support answer and configure that account as
  ["less secure"](https://support.google.com/accounts/answer/6010255);
  Gmail doesn't allow servers to send outgoing email by default.
* Note also that the rate limits for Gmail are also quite low
  (e.g. 100 / day), so it's easy to get rate-limited if your server
  has significant traffic.  For more active servers, we recommend
  moving to a free account on a transactional email service.

### Logging outgoing email to a file for prototyping

For prototyping, you might want to proceed without setting up an email
provider.  If you want to see the emails Zulip would have sent, you
can log them to a file instead.

To do so, add these lines to `/etc/zulip/settings.py`:

```
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = '/var/log/zulip/emails'
```

Then outgoing emails that Zulip would have sent will just be written
to files in `/var/log/zulip/emails/`.

Remember to delete this configuration (and restart the server) if you
later set up a real SMTP provider!

## Troubleshooting

You can quickly test your outgoing email configuration using:

```
su zulip
/home/zulip/deployments/current/manage.py send_test_email username@example.com
```

If it doesn't throw an error, it probably worked; you can confirm by
checking your email.

If it doesn't work, check these common failure causes:

* Your hosting provider may block outgoing SMTP traffic in its default
  firewall rules.  Check whether the port `EMAIL_PORT` is blocked in
  your hosting provider's firewall.

* Make sure you set the password in `/etc/zulip/zulip-secrets.conf`.

* Check the username and password for typos.

* Be sure to restart your Zulip server after editing either
  `settings.py` or `zulip-secrets.conf`, using
  `/home/zulip/deployments/current/scripts/restart-server` .
  Note that the `manage.py` command above will read the latest
  configuration from the config files, even if the server is still
  running with an old configuration.

### Advanced troubleshooting

Here are a few final notes on what to look at when debugging why you
aren't receiving emails from Zulip:

* Most transactional email services have an "outgoing email" log where
  you can inspect the emails that reached the service, whether an
  email was flagged as spam, etc.

* Starting with Zulip 1.7, Zulip logs an entry in
  `/var/log/zulip/send_email.log` whenever it attempts to send an
  email.  The log entry includes whether the request succeeded or failed.

* If attempting to send an email throws an exception, a traceback
  should be in `/var/log/zulip/errors.log`, along with any other
  exceptions Zulip encounters.

* Zulip's email sending configuration is based on the standard Django
  [SMTP backend](https://docs.djangoproject.com/en/2.0/topics/email/#smtp-backend)
  configuration.  So if you're having trouble getting your email
  provider working, you may want to search for documentation related
  to using your email provider with Django.

  The one thing we've changed from the Django defaults is that we read
  the email password from the `email_password` entry in the Zulip
  secrets file, as part of our policy of not having any secret
  information in the `/etc/zulip/settings.py` file.  In other words,
  if Django documentation references setting `EMAIL_HOST_PASSWORD`,
  you should instead set `email_password` in
  `/etc/zulip/zulip-secrets.conf`.
