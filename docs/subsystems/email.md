# Email

This page has developer documentation on the Zulip email system. If you're
trying to configure your server to send email, you might be looking for our
guide to [sending outgoing email](../production/email.html). If you're trying to
configure an email integration to receive incoming email (e.g. so that users
can reply to missed message emails via email), you might be interested in
our instructions for
[setting up an email integration](https://zulipchat.com/integrations/doc/email).

On to the documentation. Zulip's email system is fairly straightforward,
with only a few things you need to know to get started.

* All email templates are in `templates/zerver/emails/`. Each email has three
  template files: `<template_prefix>.subject.txt`, `<template_prefix>.txt`, and
  `<template_prefix>.source.html`. Email templates, along with all other templates
  in the `templates/` directory, are Jinja2 templates.
* Most of the CSS and HTML layout for emails is in `email_base.html`. Note
  that email has to ship with all of its CSS and HTML, so nothing in
  `static/` is useful for an email. If you're adding new CSS or HTML for an
  email, there's a decent chance it should go in `email_base.html`.
* All email is eventually sent by `zerver.lib.send_email.send_email`. There
  are several other functions in `zerver.lib.send_email`, but all of them
  eventually call the `send_email` function. The most interesting one is
  `send_future_email`. The `ScheduledEmail` entries are eventually processed
  by a supervisor job that runs `zerver/management/commands/deliver_email.py`.
* Always use `user_profile.delivery_email`, not `user_profile.email`,
  when passing data into the `send_email` library.  The
  `user_profile.email` field may not always be valid.
* A good way to find a bunch of example email pathways is to `git grep` for
  `zerver/emails` in the `zerver/` directory.

One slightly complicated decision you may have to make when adding an email
is figuring out how to schedule it. There are 3 ways to schedule email.
* Send it immediately, in the current Django process, e.g. by calling
  `send_email` directly. An example of this is the `confirm_registration`
  email.
* Add it to a queue. An example is the `invitation` email.
* Send it (approximately) at a specified time in the future, using
  `send_future_email`. An example is the `followup_day2` email.

Email takes about a quarter second per email to process and send. Generally
speaking, if you're sending just one email, doing it in the current process
is fine. If you're sending emails in a loop, you probably want to send it
from a queue. Documentation on our queueing system is available
[here](../subsystems/queuing.html).

## Development and testing

All the emails sent in the development environment can be accessed by
visiting `/emails` in the browser.  The way that this works is that
we've set the email backend (aka what happens when you call the email
`.send()` method in Django) in the development environment to be our
our custom backend, `EmailLogBackEnd`.  It does the following:

* Logs any sent emails to `var/log/email_content.log`. This log is
  displayed by the `/emails` endpoint
  (e.g. http://zulip.zulipdev.com:9991/emails).
* Print a friendly message on console advertising `/emails` to make
  this nice and discoverable.

You can also forward all the emails sent in the development environment
to an email id of your choice by clicking on **Forward emails to a mail
account** in `/emails` page. This feature can be used for testing how
emails gets rendered by different email clients. Before enabling this
you have to first configure the following SMTP settings.

* The hostname `EMAIL_HOST` in `zproject/dev_settings.py`
* The username `EMAIL_HOST_USER` in `zproject/dev_settings.py`.
* The password `email_password` in `zproject/dev-secrets.conf`.

See [this](../production/email.html#free-outgoing-email-services)
section for instructions on obtaining SMTP details.

**Note: The base_image_uri of the images in forwarded emails would be replaced
with `https://chat.zulip.org/static/images/emails` inorder for the email clients
to render the images. See `zproject/email_backends.py` for more details.**

While running the backend test suite, we use
`django.core.mail.backends.locmem.EmailBackend` as the email
backend. The `locmem` backend stores messages in a special attribute
of the django.core.mail module, "outbox". The outbox attribute is
created when the first message is sent. It’s a list with an
EmailMessage instance for each message that would be sent.

Other notes:
* After changing any HTML email or `email_base.html`, you need to run
  `tools/inline-email-css` for the changes to be reflected in the dev
  environment. The script generates files like
  `templates/zerver/emails/compiled/<template_prefix>.html`.
## Email templates

Zulip's email templates live under `templates/zerver/emails`.  Email
templates are a messy problem, because on the one hand, you want nice,
readable markup and styling, but on the other, email clients have very
limited CSS support and generaly require us to inject any CSS we're
using in the emails into the email as inline styles.  And then you
also need both plain-text and HTML emails.  We solve these problems
using a combination of the
[premailer](https://github.com/peterbe/premailer) library and having
two copies of each email (plain-text and HTML).

So for each email, there are two source templates: the `.txt` version
(for plain-text format) as well as a `.source.html` template.  The
`.txt` version is used directly; while the `.source.html` template is
processed by `tools/inline-email-css` (generating a `.html` template
under `templates/zerver/emails/compiled`); that tool (powered by
`premailer`) injects the CSS we use for styling our emails
(`templates/zerver/emails/email.css`) into the templates inline.

What this means is that when you're editing emails, **you need to run
`tools/inline-email-css`** after making changes to see the changes
take effect.  Our tooling automatically runs this as part of
`tools/provision` and production deployments; but you should bump
`PROVISION_VERSION` when making changes to emails that change test
behavior, or other developers will get test failures until they
provision.

While this model is great for the markup side, it isn't ideal for
[translations](../translating/translating.html).  The Django
translation system works with exact strings, and having different new
markup can require translators to re-translate strings, which can
result in problems like needing 2 copies of each string (one for
plain-text, one for HTML) and/or needing to re-translate a bunch of
strings after making a CSS tweak.  Re-translating these strings is
relatively easy in Transifex, but annoying.

So when writing email templates, we try to translate individual
sentences that are shared between the plain-text and HTML content
rather than larger blocks that might contain markup; this allows
translators to not have to deal with multiple versions of each string
in our emails.

One can test whether you did the translating part right by running
`tools/inline-email-css && manage.py makemessages` and then searching
for the strings in `static/locale/en/LC_MESSAGES/django.po`; if there
are multiple copies or they contain CSS colors, you did it wrong.

A final note for translating emails is that strings that are sent to
user accounts (where we know the user's language) are higher-priority
to translate than things sent to an email address (where we don't).
E.g. for password reset emails, it makes sense for the code path for
people with an actual account can be tagged for translation, while the
code path for the "you don't have an account email" might not be,
since we might not know what language to use in the second case.

Future work in this space could be to actually generate the plain-text
versions of emails from the `.source.html` markup, so that we don't
need to maintain two copies of each email's text.
