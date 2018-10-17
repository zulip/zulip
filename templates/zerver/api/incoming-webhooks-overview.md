# Incoming webhook integrations

An incoming webhook allows a third-party service to push data to Zulip when
something happens. The third-party service `POST`s to a special URL when it
has something for you, and then your webhook integration handles that
incoming data.

New Zulip webhook integrations can take just a few hours to write,
including tests and documentation, if you use the right process.

## Quick guide

* Set up the
  [Zulip development environment](https://zulip.readthedocs.io/en/latest/development/overview.html).

* Use <https://webhook.site/> or a similar site to capture an example
  webhook payload from the third-party service. Create a
  `zerver/webhooks/<mywebhook>/fixtures/` directory, and add the captured
  payload as a test fixture.

* Create an `Integration` object, and add it to `WEBHOOK_INTEGRATIONS` in
  `zerver/lib/integrations.py`. Search for `webhook` in that file to find an
  existing one to copy.

* Write a draft webhook handler under `zerver/webhooks/`. There are a lot of
  examples in that directory that you can copy. We recommend templating off
  a short one, like `stash` or `zendesk`.

* Add a test for your fixture at `zerver/webhooks/<mywebhook>/tests.py`.
  Run the tests for your integration like this:

    ```
    tools/test-backend zerver/webhooks/<mywebhook>/
    ```

    Iterate on debugging the test and webhooks handler until it all
    works.

* Capture payloads for the other common types of `POST`s the third-party
  service will make, and add tests for them; usually this part of the
  process is pretty fast.

* Document the integration (required for getting it merged into Zulip). You
  can template off an existing guide, like
  [this one](https://raw.githubusercontent.com/zulip/zulip/master/zerver/webhooks/github/doc.md).
  This should not take more than 15 minutes, even if you don't speak English
  as a first language (we'll clean up the text before merging).

## Hello world walkthrough

Check out the [detailed walkthrough](incoming-webhooks-walkthrough) for step-by-step
instructions.

## Checklist

### Files that need to be created

Select a name for your incoming webhook and use it consistently. The examples
below are for a webhook named `MyWebHook`.

* `zerver/webhooks/mywebhook/__init__.py`: Empty file that is an obligatory
   part of every python package.  Remember to `git add` it.
* `zerver/webhooks/mywebhook/view.py`: The main webhook integration function
  as well as any needed helper functions.
* `zerver/webhooks/mywebhook/fixtures/messagetype.json`: Sample json payload data
  used by tests. Add one fixture file per type of message supported by your
  integration.
* `zerver/webhooks/mywebhook/tests.py`: Tests for your webbook.
* `zerver/webhooks/mywebhook/doc.html`: End-user documentation explaining
  how to add the integration.
* `static/images/integrations/logos/mywebhook.svg`: A square logo for the
  platform/server/product you are integrating. Used on the documentation
  pages as well as the sender's avatar for messages sent by the integration.
* `static/images/integrations/mywebbook/001.svg`: A screenshot of a message
  sent by the integration, used on the documenation page.

### Files that need to be updated

* `zerver/lib/integrations.py`: Add your integration to
  `WEBHOOK_INTEGRATIONS`. This will automatically register a
  URL for the incoming webhook of the form `api/v1/external/mywebhook` and
  associate it with the function called `api_mywebhook_webhook` in
  `zerver/webhooks/mywebhook/view.py`.

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
  don't have an API or webhook we can use; sometimes the right API
  is just not properly documented.

* A helpful tool for testing your integration is
  [UltraHook](http://www.ultrahook.com/), which allows you to receive webhook
  calls via your local Zulip development environment. This enables you to do end-to-end
  testing with live data from the service you're integrating and can help you
  spot why something isn't working or if the service is using custom HTTP
  headers.
