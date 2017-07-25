# Email

This page has developer documentation on the Zulip email system. If you're
trying to configure your server to send email, you might be looking for our
guide to [sending outgoing email](prod-email.html). If you're trying to
configure an email integration to receive incoming email (e.g. so that users
can reply to missed message emails via email), you might be interested in
our instructions for
[setting up an email integration](https://zulipchat.com/integrations/doc/email).

On to the documentation. Zulip's email system is fairly straightforward,
with only a few things you need to know to get started.

* All email templates are in `templates/zerver/emails/`. Each email has three
  template files: `<template_prefix>.subject`, `<template_prefix>.txt`, and
  `<template_prefix>.html`. Email templates, along with all other templates
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
[here](queuing.html).

## Testing

All emails are printed to the console in the development environment. A
great way to see what most of our emails look like (with fixture data) is by
going to `emails/` in the browser.
