# How to write a new integration

Integrations are one of the most important parts of a group chat tool
like Zulip, and we are committed to making integrating with Zulip and
getting you integration merged upstream so everyone else can benefit
from it as easy as possible while maintaining the high quality of the
Zulip integrations library.

Contributions to this guide are very welcome, so if you run into any
issues following these instructions or come up with any tips or tools
that help writing integration, please email
zulip-devel@googlegroups.com, open an issue, or submit a pull request
to share your ideas!

## Types of integrations

We have several different ways that we integrate with 3rd part
products, ordered here by which types we prefer to write:

1. Webhook integrations (examples: Freshdesk, GitHub), where the
third-party service supports posting content to a particular URI on
our site with data about the event.  For these, you usually just need
to add a new handler in `zerver/views/webhooks.py` (plus
test/document/etc.).  An example commit implementing a new webhook is:
https://github.com/zulip/zulip/pull/324.

2. Python script integrations (examples: SVN, Git), where we can get
the service to call our integration (by shelling out or otherwise),
passing in the required data.  Our preferred model for these is to
ship these integrations in our API release tarballs (by writing the
integration in `api/integrations`).

3. Plugin integrations (examples: Jenkins, Hubot, Trac) where the user
needs to install a plugin into their existing software.  These are
often more work, but for some products are the only way to integrate
with the product at all.

## General advice for writing integrations

* Consider using our Zulip markup to make the output from your
  integration especially attractive or useful (e.g.  emoji, markdown
  emphasis, @-mentions, or `!avatar(email)`).

* Use topics effectively to ensure sequential messages about the same
  thing are threaded together; this makes for much better consumption
  by users.  E.g. for a bug tracker integration, put the bug number in
  the topic for all messages; for an integration like Nagios, put the
  service in the topic.

* Integrations that don't match a team's workflow can often be
  uselessly spammy.  Give careful thought to providing options for
  triggering Zulip messages only for certain message types, certain
  projects, or sending different messages to different streams/topics,
  to make it easy for teams to configure the integration to support
  their workflow.

* Consistently capitalize the name of the integration in the
  documentation and the Client name the way the vendor does.  It's OK
  to use all-lower-case in the implementation.

* Sometimes it can be helpful to contact the vendor if it appears they
  don't have an API or webhook we can use -- sometimes the right API
  is just not properly documented.

## Writing Webhook integrations

New Zulip webhook integrations can take just a few hours to write,
including tests and documentation, if you use the right process.
Here's how we recommend doing it:

* First, use http://requestb.in/ or a similar site to capture an
  example webhook payload from the service you're integrating.  You
  can use these captured payloads to create a set of test fixtures for
  your integration under `zerver/fixtures`.

* Then write a draft webhook handler under `zerver/views/webhooks/`;
  there are a lot of examples in that directory.  We recommend
  templating off a short one (like `stash.py` or `zendesk.py`), since
  the longer ones usually just have more complex parsing which can
  obscure what's common to all webhook integrations.  In addition to
  writing the integration itself, you'll need to add an entry in
  `zproject/urls.py` for your webhook; search for `webhook` in that
  file to find the existing ones (and please add yours in the
  alphabetically correct place).

* Then write a test for your fixture in `zerver/tests/test_hooks.py`, and
  you can iterate on the tests and webhooks handler until they work,
  all without ever needing to post directly from the server you're
  integrating to your Zulip development machine.  To run just the
  tests from the test class you wrote, you can use e.g.

  ```
  test-backend zerver.tests.test_hooks.PagerDutyHookTests
  ```

  See
  https://github.com/zulip/zulip/blob/master/README.dev.md#running-the-test-suite
  for more details on the Zulip test runner.

* Once you've gotten your webhook working and passing a test, capture
  payloads for the other common types of posts the service's webhook
  will make, and add tests for them; usually this part of the process
  is pretty fast.  Webhook integration tests should all use fixtures
  (as opposed to contacting the service), since otherwise the tests
  can't run without Internet access and some sort of credentials for
  the service.

* Finally, write documentation for the integration (see below)!

## Writing Python script and plugin integrations integrations

For plugin integrations, usually you will need to consult the
documentation for the third party software in order to learn how to
write the integration.  But we have a few notes on how to do these:

* You should always send messages by POSTing to URLs of the form
`https://zulip.example.com/v1/messages/`, not the legacy
`/api/v1/send_message` message sending API.

* We usually build Python script integration with (at least) 2 files:
`zulip_foo_config.py`` containing the configuration for the
integration including the bots' API keys, plus a script that reads
from this configuration to actually do the work (that way, it's
possible to update the script without breaking users' configurations).

* Be sure to test your integration carefully and document how to
  install it (see notes on documentation below).

* You should specify a clear HTTP User-Agent for your integration. The
user agent should at a minimum identify the integration and version
number, separated by a slash. If possible, you should collect platform
information and include that in `()`s after the version number. Some
examples of ideal UAs are:

```
ZulipDesktop/0.7.0 (Ubuntu; 14.04)
ZulipJenkins/0.1.0 (Windows; 7.2)
ZulipMobile/0.5.4 (Android; 4.2; maguro)
```

## Documenting your integration

Every Zulip integration must be documented in
`templates/zerver/integrations.html`.  Usually, this involves a few
steps:

* Add an `integration-lozenge` class block in the alphabetically
  correct place in the main integration list, using the logo for the
  integrated software.

* Add an `integration-instructions` class block also in the
  alphabetically correct place, explaining all the steps required to
  setup the integration, including what URLs to use, etc.  If there
  are any screens in the product involved, take a few screenshots with
  the input fields filled out with sample values in order to make the
  instructions really easy to follow.  For the screenshots, use
  something like `github-bot@example.com` for the email addresses and
  an obviously fake API key like `abcdef123456790`.

* Finally, generate a message sent by the integration and take a
  screenshot of the message to provide an example message in the
  documentation. If your new integration is a webhook integration,
  you can generate such a message from your test fixtures
  using `send_webhook_fixture_message`:

  ```
  ./manage.py send_webhook_fixture_message \
       --fixture=zerver/fixtures/pingdom/pingdom_imap_down_to_up.json \
       '--url=/api/v1/external/pingdom?stream=stream_name&api_key=api_key'
  ```

  When generating the screenshot of a sample message, give your test
  bot a nice name like "GitHub Bot", use the project's logo as the
  bot's avatar, and take the screenshots showing the stream/topic bar
  for the message, not just the message body.

When writing documentation for your integration, be sure to use the
`{{ external_api_uri }}` template variable, so that your integration
documentation will provide the correct URL for whatever server it is
deployed on.  If special configuration is required to set the SITE
variable, you should document that too, inside an `{% if
api_site_required %}` check.
