# Writing a new integration

Integrations are one of the most important parts of a group chat tool
like Zulip, and we are committed to making integrating with Zulip and
getting your integration merged upstream so that everyone else can benefit
from it, as easy as possible while maintaining the high quality of the
Zulip integrations library.

On this page you'll find:

* An overview of the different [types of integrations](#types-of-integrations)
  possible with Zulip.
* [General advice](#general-advice) for writing integrations.
* Details about writing [webhook integrations](#webhook-integrations).
* Details about writing [Python script and plugin
  integrations](#python-script-and-plugin-integrations).
* A guide to
  [documenting your integration](integration-docs-guide) is on a
  separate page.

A detailed walkthrough of a simple "Hello World" integration can be
found in the [webhook walkthrough](webhook-walkthrough).

Contributions to this guide are very welcome, so if you run into any
issues following these instructions or come up with any tips or tools
that help writing integration, please email
zulip-devel@googlegroups.com, open an issue, or submit a pull request
to share your ideas!

## Types of integrations

We have several different ways that we integrate with 3rd party
products, ordered here by which types we prefer to write:

1. **[Webhook integrations](#webhook-integrations)** (examples:
   Freshdesk, GitHub), where the third-party service supports posting
   content to a particular URI on our site with data about the event.
   For these, you usually just need to create a new python package in
   the `zerver/webhooks/` directory.  You can easily find recent
   commits adding new integrations to crib from via
   `git log zerver/webhooks/`.

2. **[Python script integrations](#python-script-and-plugin-integrations)**
   (examples: SVN, Git), where we can get the service to call our integration
   (by shelling out or otherwise), passing in the required data.  Our preferred
   model for these is to ship these integrations in the
   [Zulip Python API distribution](https://github.com/zulip/python-zulip-api/tree/master/zulip),
   within the `integrations` directory there.

3. **[Plugin integrations](#python-script-and-plugin-integrations)** (examples:
   Jenkins, Hubot, Trac) where the user needs to install a plugin into their
   existing software.  These are often more work, but for some products are the
   only way to integrate with the product at all.

## General advice

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

* A helpful tool for testing your integration is
  [UltraHook](http://www.ultrahook.com/), which allows you to receive webhook
  calls via your local Zulip development environment. This enables you to do end-to-end
  testing with live data from the service you're integrating and can help you
  spot why something isn't working or if the service is using custom HTTP
  headers.

## Webhook integrations

A webhook allows a third-party service to push data to you when something
happens. It's different from making a REST API call, where you send a request
to the service's API and wait for a response. With a webhook, the third-party
service sends you an HTTP POST when it has something for you. Your webhook
integration defines the URI the service uses to communicate with Zulip, and
handles that incoming data.

New Zulip webhook integrations can take just a few hours to write,
including tests and documentation, if you use the right process.

**For detailed instructions, check out the ["Hello World" webhook walkthrough](
webhook-walkthrough)**.

For a quick guide, read on.

* First, use <http://requestb.in/> or a similar site to capture an
    example webhook payload from the service you're integrating.  You
    can use these captured payloads to create a set of test fixtures
    for your integration under `zerver/webhooks/mywebhook/fixtures/`.

* Then write a draft webhook handler under `zerver/webhooks/`; there
    are a lot of examples in that directory.  We recommend templating
    off a short one (like `stash` or `zendesk`), since the longer ones
    usually just have more complex parsing which can obscure what's
    common to all webhook integrations.  In addition to writing the
    integration itself, you'll need to create `Integration` object and
    add it to `WEBHOOK_INTEGRATIONS` in `zerver/lib/integrations.py;`
    search for `webhook` in that file to find the existing ones (and
    please add yours in the alphabetically correct place).

* Then write a test for your fixture in the `tests.py` file in the
    `zerver/webhooks/mywebhook` directory.  You can now iterate on
    debugging the tests and webhooks handler until they work, all
    without ever needing to post directly from the service you're
    integrating with to your Zulip development machine.  You can run
    just the tests for one integration like this:

    ```
    test-backend zerver/webhooks/pagerduty/
    ```

    *Hint: See
    [this guide](https://zulip.readthedocs.io/en/latest/testing/testing.html)
    for more details on the Zulip test runner.*

* Once you've gotten your webhook working and passing a test, capture
    payloads for the other common types of posts the service's webhook
    will make, and add tests for them; usually this part of the
    process is pretty fast.  Webhook integration tests should all use
    fixtures (as opposed to contacting the service), since otherwise
    the tests can't run without Internet access and some sort of
    credentials for the service.

* Finally, write documentation for the integration; there's a
  [detailed guide](integration-docs-guide).

### Files that need to be created

Select a name for your webhook and use it consistently. The examples below are
for a webhook named 'MyWebHook'.

* `static/images/integrations/logos/mywebhook.svg`: An image to represent
  your integration in the user interface. Generally this should be the logo of the
  platform/server/product you are integrating. See [Documenting your
  integration](integration-docs-guide) for details.
* `static/images/integrations/mywebbook/001.svg`: A screen capture of your
  integration for use in the user interface. You can add as many images as needed
  to effectively document your webhook integration. See [Documenting your
  integration](integration-docs-guide) for details.
* `zerver/webhooks/mywebhook/fixtures/messagetype.json`: Sample json payload data
  used by tests. Add one fixture file per type of message supported by your
  integration. See [Testing and writing tests](
  https://zulip.readthedocs.io/en/latest/testing/testing.html) for details.
* `zerver/webhooks/mywebhook/__init__.py`: Empty file that is obligatory
   part of every python package.  Remember to `git add` it.
* `zerver/webhooks/mywebhook/view.py`: Includes the main webhook integration
  function including any needed helper functions.
* `zerver/webhooks/mywebhook/tests.py`: Add tests for your
  webbook. See [Testing and writing tests](
  https://zulip.readthedocs.io/en/latest/testing/testing.html) for details.
* `zerver/webhooks/mywebhook/doc.html`: Add end-user documentation. See
  [Documenting your integration](integration-docs-guide) for details.

### Files that need to be updated

* `zerver/lib/integrations.py`: Add your integration to
`WEBHOOK_INTEGRATIONS` to register it.  This will automatically
register a url for the webhook of the form `api/v1/external/mywebhook`
and associate with the function called `api_mywebhook_webhook` in
`zerver/webhooks/mywebhook/view.py`.

## Python script and plugin integrations

For plugin integrations, usually you will need to consult the
documentation for the third party software in order to learn how to
write the integration.  But we have a few notes on how to do these:

* You should always send messages by POSTing to URLs of the form
`https://zulip.example.com/v1/messages/`.

* We usually build Python script integration with (at least) 2 files:
`zulip_foo_config.py` containing the configuration for the
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
