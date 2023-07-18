# Email

This page has developer documentation on the Zulip email system. If you're
trying to configure your server to send email, you might be looking for our
guide to [sending outgoing email](../production/email.md). If you're trying to
configure an email integration to receive incoming email (e.g. so that users
can reply to message notification emails via email), you might be interested in
our instructions for
[setting up an email integration](https://zulip.com/integrations/doc/email).

On to the documentation. Zulip's email system is fairly straightforward,
with only a few things you need to know to get started.

- All email templates are in `templates/zerver/emails/`. Each email has three
  template files: `<template_prefix>.subject.txt`, `<template_prefix>.txt`, and
  `<template_prefix>.html`. Email templates, along with all other templates
  in the `templates/` directory, are Jinja2 templates.
- Most of the CSS and HTML layout for emails is in `email_base_default.html`. Note
  that email has to ship with all of its CSS and HTML, so nothing in
  `static/` is useful for an email. If you're adding new CSS or HTML for an
  email, there's a decent chance it should go in `email_base_default.html`.
- All email is eventually sent by `zerver.lib.send_email.send_email`. There
  are several other functions in `zerver.lib.send_email`, but all of them
  eventually call the `send_email` function. The most interesting one is
  `send_future_email`. The `ScheduledEmail` entries are eventually processed
  by a supervisor job that runs `zerver/management/commands/deliver_scheduled_emails.py`.
- Always use `user_profile.delivery_email`, not `user_profile.email`,
  when passing data into the `send_email` library. The
  `user_profile.email` field may not always be valid.
- A good way to find a bunch of example email pathways is to `git grep` for
  `zerver/emails` in the `zerver/` directory.

One slightly complicated decision you may have to make when adding an email
is figuring out how to schedule it. There are 3 ways to schedule email.

- Send it immediately, in the current Django process, e.g. by calling
  `send_email` directly. An example of this is the `confirm_registration`
  email.
- Add it to a queue. An example is the `invitation` email.
- Send it (approximately) at a specified time in the future, using
  `send_future_email`. An example is the `onboarding_zulip_topics` email.

Email takes about a quarter second per email to process and send. Generally
speaking, if you're sending just one email, doing it in the current process
is fine. If you're sending emails in a loop, you probably want to send it
from a queue. Documentation on our queueing system is available
[here](queuing.md).

## Development and testing

All the emails sent in the development environment can be accessed by
visiting `/emails` in the browser. The way that this works is that
we've set the email backend (aka what happens when you call the email
`.send()` method in Django) in the development environment to be our
custom backend, `EmailLogBackEnd`. It does the following:

- Logs any sent emails to `var/log/email_content.log`. This log is
  displayed by the `/emails` endpoint
  (e.g. http://zulip.zulipdev.com:9991/emails).
- Print a friendly message on console advertising `/emails` to make
  this nice and discoverable.

### Testing in a real email client

You can also forward all the emails sent in the development
environment to an email account of your choice by clicking on
**Forward emails to an email account** on the `/emails` page. This
feature can be used for testing how the emails gets rendered by
actual email clients. This is important because web email clients
have limited CSS functionality, autolinkify things, and otherwise
mutate the HTML email one can see previewed on `/emails`.

To do this sort of testing, you need to set up an outgoing SMTP
provider. Our production advice for
[Gmail](../production/email.md#using-gmail-for-outgoing-email) and
[transactional email
providers](../production/email.md#free-outgoing-email-services) are
relevant; you can ignore the Gmail warning as Gmail's rate limits are
appropriate for this sort of low-volume testing.

Once you have the login credentials of the SMTP provider, since there
is not `/etc/zulip/settings.py` in development, configure it using the
following keys in `zproject/dev-secrets.conf`

- `email_host` - SMTP hostname.
- `email_port` - SMTP port.
- `email_host_user` - Username of the SMTP user
- `email_password` - Password of the SMTP user.
- `email_use_tls` - Set to `true` for most providers. Else, don't set any value.

Here is an example of how `zproject/dev-secrets.conf` might look if
you are using Gmail.

```ini
email_host = smtp.gmail.com
email_port = 587
email_host_user = username@gmail.com
email_use_tls = true

# This is different from your Gmail password if you have 2FA enabled for your Google account.
# See the configuring Gmail to send email section above for more details
email_password = gmail_password
```

### Notes

- Images won't be displayed in a real email client unless you change
  the `images_base_url` used for emails to a public URL such as
  `https://chat.zulip.org/static/images/emails` (image links to
  `localhost:9991` aren't allowed by modern email providers). See
  `zproject/email_backends.py` for more details.

- While running the backend test suite, we use
  `django.core.mail.backends.locmem.EmailBackend` as the email
  backend. The `locmem` backend stores messages in a special attribute
  of the django.core.mail module, "outbox". The outbox attribute is
  created when the first message is sent. It’s a list with an
  EmailMessage instance for each message that would be sent.

## Email templates

Zulip's email templates live under `templates/zerver/emails`. Email
templates are a messy problem, because on the one hand, you want nice,
readable markup and styling, but on the other, email clients have very
limited CSS support and generally require us to inject any CSS we're
using in the emails into the email as inline styles. And then you
also need both plain-text and HTML emails. We solve these problems
using a combination of the
[css-inline](https://github.com/Stranger6667/css-inline) library and having
two copies of each email (plain-text and HTML).

So, for each email, there are two source templates: the `.txt` version
(for plain-text format) as well as a `.html` template. The `.txt` version
is used directly, while `.html` is processed by `css-inline`, which injects
the CSS we use for styling our emails (`templates/zerver/emails/email.css`)
into the templates just before sending an email.

While this model is great for the markup side, it isn't ideal for
[translations](../translating/translating.md). The Django
translation system works with exact strings, and having different new
markup can require translators to re-translate strings, which can
result in problems like needing 2 copies of each string (one for
plain-text, one for HTML). Re-translating these strings is
relatively easy in Transifex, but annoying.

So when writing email templates, we try to translate individual
sentences that are shared between the plain-text and HTML content
rather than larger blocks that might contain markup; this allows
translators to not have to deal with multiple versions of each string
in our emails.

One can test whether you did the translating part right by running
`manage.py makemessages` and then searching
for the strings in `locale/en/LC_MESSAGES/django.po`; if there
are multiple copies or they contain CSS colors, you did it wrong.

A final note for translating emails is that strings that are sent to
user accounts (where we know the user's language) are higher-priority
to translate than things sent to an email address (where we don't).
E.g. for password reset emails, it makes sense for the code path for
people with an actual account can be tagged for translation, while the
code path for the "you don't have an account email" might not be,
since we might not know what language to use in the second case.

Future work in this space could be to actually generate the plain-text
versions of emails from the `.html` markup, so that we don't
need to maintain two copies of each email's text.
