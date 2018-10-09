# Incoming webhook integrations

An incoming webhook allows a third-party service to push data to you when something
happens. It's different from making a REST API call, where you send a request
to the service's API and wait for a response. With an incoming webhook, the third-party
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

* Once you've gotten your incoming webhook working and passing a test, capture
    payloads for the other common types of posts the service's webhook
    will make, and add tests for them; usually this part of the
    process is pretty fast.  Webhook integration tests should all use
    fixtures (as opposed to contacting the service), since otherwise
    the tests can't run without Internet access and some sort of
    credentials for the service.

* Finally, write documentation for the integration; there's a
  [detailed guide][integration-docs-guide].

## Files that need to be created

Select a name for your incoming webhook and use it consistently. The examples
below are for a webhook named 'MyWebHook'.

* `static/images/integrations/logos/mywebhook.svg`: An image to represent
  your integration in the user interface. Generally this should be the logo of the
  platform/server/product you are integrating. See [Documenting your
  integration][integration-docs-guide] for details.
* `static/images/integrations/mywebbook/001.svg`: A screen capture of your
  integration for use in the user interface. You can add as many images as needed
  to effectively document your webhook integration. See [Documenting your
  integration][integration-docs-guide] for details.
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
  [Documenting your integration][integration-docs-guide] for details.

[integration-docs-guide]: https://zulip.readthedocs.io/en/stable/subsystems/integration-docs.html

## Files that need to be updated

* `zerver/lib/integrations.py`: Add your integration to
`WEBHOOK_INTEGRATIONS` to register it.  This will automatically
register a url for the incoming webhook of the form `api/v1/external/mywebhook`
and associate with the function called `api_mywebhook_webhook` in
`zerver/webhooks/mywebhook/view.py`.
