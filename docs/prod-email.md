# Outgoing email

This page documents everything you need to know about setting up
outgoing email in a Zulip production environment.  It's pretty simple
if you already have an outgoing SMTP provider; just start reading from
[the configuration section](#configuration).

### Free outgoing SMTP

If you don't have an existing outgoing SMTP provider, don't worry!
There are several SMTP providers with free tiers, such as
[Mailgun](https://documentation.mailgun.com/quickstart-sending.html#send-via-smtp)
or
[Amazon SES](http://docs.aws.amazon.com/ses/latest/DeveloperGuide/send-email-smtp.html)
(free for sending email from EC2), and dozens of products have free
tiers as well.  Search the web for "Transactional email" and you'll
find plenty of options to choose from.  Once you've signed up, you'll
want to find your "SMTP credentials" (which can be different from the
credentials for the custom APIs for many email service providers
have).

Using a transactional email service that is designed to send email
from servers is much easier than setting up outgoing email with an
inbox product like Gmail.  If you for whatever reason attempt to use a
Gmail account to send outgoing email, you will need to read this
Google support answer and configure that account as
["less secure"](https://support.google.com/accounts/answer/6010255);
Gmail doesn't allow servers to send outgoing email by default.  Note
also that the rate limits for Gmail are also quite low (e.g. 100 /
day), so it's easy to get rate-limited.

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
`/etc/zulip/settings.py`, including `EMAIL_HOST`, `EMAIL_HOST_USER`,
`DEFAULT_FROM_EMAIL`, and `NOREPLY_EMAIL_ADDRESS`.  You may also need
to set `EMAIL_PORT` if your provider doesn't use the standard
SMTP submission port (587).

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
`/home/zulip/deployments/current/restart-server` so that the running
server is using the latest configuration.

#### Advanced troubleshooting

Zulip's email sending configuration is based on the standard Django
[SMTP backend](https://docs.djangoproject.com/en/1.10/topics/email/#smtp-backend)
configuration.  The one thing we've changed from the defaults is
reading `EMAIL_HOST_PASSWORD` from the `email_password` entry in the
Zulip secrets file, so that secrets don't live in the
`/etc/zulip/settings.py` file.

So if you're having trouble getting your email provider working, you
may want to search for documentation related to using your email
provider with Django.
