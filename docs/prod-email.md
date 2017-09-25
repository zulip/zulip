# Outgoing email

This page documents everything you need to know about setting up
outgoing email in a Zulip production environment.  It's pretty simple
if you already have an outgoing SMTP provider; just start reading from
[the configuration section](#configuration).

### Free outgoing email services

For sending outgoing email from your Zulip server, we highly recommend
using a "transactional email" service like
[Mailgun](https://documentation.mailgun.com/en/latest/quickstart-sending.html#send-via-smtp)
or for AWS users,
[Amazon SES](http://docs.aws.amazon.com/ses/latest/DeveloperGuide/send-email-smtp.html).
These services are designed to send email from servers, and are by far
the easiest way to get outgoing email working reliably.

If you don't have an existing outgoing SMTP provider, don't worry!
Both of the options we recommend above (as well as dozens of other
services) have free options; we recommend Mailgun as the easiest to
get setup with.  Once you've signed up, you'll want to find the
service's provided "SMTP credentials", and configure Zulip as follows:

* The hostname as `EMAIL_HOST = 'smtp.mailgun.org'` in `/etc/zulip/settings.py`
* The username as `EMAIL_HOST_USER = 'username@example.com` in
  `/etc/zulip/settings.py`.
* The password as `email_password = abcd1234` in `/etc/zulip/zulip-secrets.conf`.

### Using Gmail for outgoing email

We don't recommend using an inbox product like Gmail for outgoing
email, because Gmail's anti-spam measures make this annoying.  But if
you want to use a Gmail account to send outgoing email anyway, here's
how to make it work:
* Create a totally new Gmail account for your Zulip server.
* Read this Google support answer and configure that account as
["less secure"](https://support.google.com/accounts/answer/6010255);
Gmail doesn't allow servers to send outgoing email by default.
* Note also that the rate limits for Gmail are also quite low
(e.g. 100 / day), so it's easy to get rate-limited.

### Logging outgoing email to a file for prototyping

If for prototyping, you don't want to bother setting up an email
provider, you can add to `/etc/zulip/settings.py` the following:

```
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = '/var/log/zulip/emails'
```

Outgoing emails that Zulip would have sent will just be written to
files in `/var/log/zulip/emails/`.  This is enough to get you through
initial user registration without an SMTP provider.

Remember to delete this configuration and restart the server if you
later setup a real SMTP provider!

### Configuration

To configure outgoing SMTP, you will need to complete the following steps:

1. Fill out the outgoing email sending configuration block in
`/etc/zulip/settings.py`, including `EMAIL_HOST`, and
`EMAIL_HOST_USER`.  You may also need to set `EMAIL_PORT` if your
provider doesn't use the standard SMTP submission port (587).

2. Put the SMTP password for `EMAIL_HOST_USER` in
`/etc/zulip/zulip-secrets.conf` as `email_password = yourPassword`.

#### Testing and troubleshooting

You can quickly test your outgoing email configuration using:

```
su zulip
/home/zulip/deployments/current/manage.py send_test_email username@example.com
```

If it doesn't throw an error, it probably worked; you can confirm by
checking your email.

It's important to test, because outgoing email often doesn't work the
first time.  Common causes of failures are:

* Your hosting provider blocking outgoing SMTP traffic in its
default firewall rules.  Check whether `EMAIL_PORT` is blocked in your
hosting provider's firewall.
* Forgetting to put the password in `/etc/zulip/zulip-secrets.conf`.
* Typos in transcribing the username or password.

Once you have it working from the management command, remember to
restart your Zulip server using
`/home/zulip/deployments/current/scripts/restart-server` so that the running
server is using the latest configuration.

#### Advanced troubleshooting

Here are a few final notes on what to look at when debugging why you
aren't receiving emails from Zulip:

* Most transactional email services have an "outgoing email" log where
  you can inspect the emails that reached the service, whether it was
  flagged as spam, etc.
* Starting with Zulip 1.7, Zulip logs an entry in
  `/var/log/zulip/send_email.log` whenever it attempts to send an
  email, including whether the request succeeded or failed.
* If attempting to send an email throws an exception, a traceback
  should be in `/var/log/zulip/errors.log`, along with any other
  exceptions Zulip encounters.
* Zulip's email sending configuration is based on the standard Django
  [SMTP backend](https://docs.djangoproject.com/en/1.10/topics/email/#smtp-backend)
  configuration.  The one thing we've changed from the defaults is
  reading `EMAIL_HOST_PASSWORD` from the `email_password` entry in the
  Zulip secrets file, so that secrets don't live in the
  `/etc/zulip/settings.py` file.  So if you're having trouble getting
  your email provider working, you may want to search for
  documentation related to using your email provider with Django.
