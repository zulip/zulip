# Writing a new integration

Integrations are one of the most important parts of a group chat tool
like Zulip, and we are committed to making integrating with Zulip and
getting you integration merged upstream so everyone else can benefit
from it as easy as possible while maintaining the high quality of the
Zulip integrations library.

On this page you'll find:

* An overvew of the different [types of integrations](#types-of-integrations)
  possible with Zulip.
* [General advice](#general-advice) for writing integrations.
* Details about writing [webhook integrations](#webhook-integrations).
* Details about writing [Python script and plugin
  integrations](#python-script-and-plugin-integrations).
* A guide to [documenting your integration](#documenting-your-integration).
* A [detailed walkthrough](#hello-world-webhook-walkthrough) of a simple "Hello
  World" integration.

Contributions to this guide are very welcome, so if you run into any
issues following these instructions or come up with any tips or tools
that help writing integration, please email
zulip-devel@googlegroups.com, open an issue, or submit a pull request
to share your ideas!

## Types of integrations

We have several different ways that we integrate with 3rd part
products, ordered here by which types we prefer to write:

1. **[Webhook integrations](#webhook-integrations)** (examples: Freshdesk,
   GitHub), where the third-party service supports posting content to a
   particular URI on our site with data about the event.  For these, you
   usually just need to add a new handler in `zerver/views/webhooks.py` (plus
   test/document/etc.).  An example commit implementing a new webhook is:
   https://github.com/zulip/zulip/pull/324.

2. **[Python script integrations](#python-script-and-plugin-integrations)**
   (examples: SVN, Git), where we can get the service to call our integration
   (by shelling out or otherwise), passing in the required data.  Our preferred
   model for these is to ship these integrations in our API release tarballs
   (by writing the integration in `api/integrations`).

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
  calls via your local Zulip dev environment. This enables you to do end-to-end
  testing with live data from the service you're integrating and can help you
  spot why something isn't working or if the service is using custom HTTP
  headers.

## Webhook integrations

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
  writing the integration itself, you'll need to create `Integration`
  object and add it to `WEBHOOK_INTEGRATIONS` in
  `zerver/lib/integrations.py'; search for `webhook` in that
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

  See [this guide](testing.html) for more details on the Zulip test
  runner.

* Once you've gotten your webhook working and passing a test, capture
  payloads for the other common types of posts the service's webhook
  will make, and add tests for them; usually this part of the process
  is pretty fast.  Webhook integration tests should all use fixtures
  (as opposed to contacting the service), since otherwise the tests
  can't run without Internet access and some sort of credentials for
  the service.

* Finally, write documentation for the integration; there's a
  [detailed guide](#documenting-your-integration) below.

See the [Hello World webhook Walkthrough](#hello-world-webhook-walkthrough)
below for a detailed look at how to write a simple webhook.

### Files that need to be created

Select a name for your webhook and use it consistently. The examples below are
for a webhook named 'MyWebHook'.

* `static/images/integrations/logos/mywebhook.png`: An image to represent
  your integration in the user interface. Generally this Should be the logo of the
  platform/server/product you are integrating. See [Documenting your
  integration](#documenting-your-integration) for details.
* `static/images/integrations/mywebbook/001.png`: A screen capture of your
  integration for use in the user interface. You can add as many images as needed
  to effectively document your webhook integration. See [Documenting your
  integration](#documenting-your-integration) for details.
* `zerver/fixtures/mywebhook/mywebhook_messagetype.json`: Sample json payload data
  used by tests. Add one fixture file per type of message supported by your
  integration. See [Testing and writing tests](testing.html) for details.
* `zerver/views/webhooks/mywebhook.py`: Includes the main webhook integration
  function including any needed helper functions.

### Files that need to be updated

* `templates/zerver/integrations.html`: Edit to add end-user documentation. See
  [Documenting your integration](#documenting-your-integration) for details.
* `zerver/test_hooks.py`: Edit to include tests for your webbook. See [Testing
  and writing tests](testing.html) for details.
* `zerver/lib/integrations.py`: Add your integration to
`WEBHOOK_INTEGRATIONS` to register it.  This will automatically
register a url for the webhook of the form `api/v1/external/mywebhook`
and associate with the function called `api_mywebhook_webhook` in
`zerver/views/webhooks/mywebhook.py`.

## Python script and plugin integrations

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

* Make sure you've added your integration to
  `zerver/lib/integrations.py`; this results in your integration
  appearing on the `/integrations` page.  You'll need to add a logo
  image for your integration under the
  `static/images/integrations/logos/<name>.png`, where `<name>` is the
  name of the integration, all in lower case.

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

## `Hello World` webhook Walkthrough

Below explains each part of a simple webhook integration, called **Hello
World**. This webhook sends a "hello" message to the `test` stream and includes
a link to the Wikipedia article of the day, which it formats from json data it
receives in the http request.

Use this walkthrough to learn how to write your first webhook
integration.

### Step 0: Create fixtures

The first step in creating a webhook is to examine the data that the
service you want to integrate will be sending to Zulip.

You can use [requestb.in](http://requestb.in/) or a similar tool to capture
webook payload(s) from the service you are integrating. Examining this
data allows you to do two things:

1. Determine how you will need to structure your webook code, including what
   message types your integration should support and how; and,
2. Create fixtures for your webook tests.

Fixtures enable the testing of webhook integration code without the need to
actually contact the service being integrated.

Because `Hello World` is a very simple webhook that does one thing, it requires
only one fixture, `zerver/fixtures/helloworld/helloworld_hello.json`:

```
{
  "featured_title":"Marilyn Monroe",
  "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe",
}
```

When writing your own webhook integration, you'll want to write a test function
for each distinct message condition your webhook supports. You'll also need a
corresponding fixture for each of these tests. See [Step 3: Create
tests](#step-3-create-tests) or [Testing](testing.html) for further details.

### Step 1: Create main webhook code

The majority of the code for your webhook integration will be in a single
python file in `zerver/views/webhooks/`. The name of this file should be the
name of your webhook, all lower-case, with file extension `.py`:
`mywebhook.py`.

The Hello World integration is in `zerver/views/webhooks/helloworld.py`:

```
from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string

from zerver.models import Client, UserProfile

from django.http import HttpRequest, HttpResponse
from six import text_type
from typing import Dict, Any, Iterable, Optional

@api_key_only_webhook_view('HelloWorld')
@has_request_variables
def api_helloworld_webhook(request, user_profile, client,
                           payload=REQ(argument_type='body'),
                           stream=REQ(default='test'),
                           topic=REQ(default='Hello World')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Iterable[Dict[str, Any]]], text_type, Optional[text_type]) -> HttpResponse

  # construct the body of the message
  body = 'Hello! I am happy to be here! :smile:'

  # try to add the Wikipedia article of the day
  # return appropriate error if not successful
  try:
      body_template = '\nThe Wikipedia featured article for today is **[{featured_title}]({featured_url})**'
      body += body_template.format(**payload)
  except KeyError as e:
      return json_error(_("Missing key {} in JSON").format(str(e)))

  # send the message
  check_send_message(user_profile, client, 'stream', [stream], topic, body)

  # return json result
  return json_success()

```

The above code imports the required functions and defines the main webhook
function `api_helloworld_webook`, decorating it with `api_key_only_webhook_view` and
`has_request_variables`.

You must pass the name of your webhook to the `api_key_only_webhook_view`
decorator. Here we have used `HelloWorld`. To be consistent with Zulip code
style, use the name of the product you are integrating in camel case, spelled
as the product spells its own name (except always first letter upper-case).

You should name your webhook function as such `api_webhookname_webhook` where
`webhookname` is the name of your webhook and is always lower-case.

At minimum, the webhook function must accept `request` (Django
[HttpRequest](https://docs.djangoproject.com/en/1.8/ref/request-response/#django.http.HttpRequest)
object), `user_profile` (Zulip's user object), and `client` (Zulip's analogue
of UserAgent). You may also want to define additional parameters using the
`REQ` object.

In the example above, we have defined `payload` which is populated from the
body of the http request, `stream` with a default of `test` (available by
default in Zulip dev environment), and `topic` with a default of `Hello World`.

The line that begins `# type` is a mypy type annotation. See [this
page](mypy.html) for details about how to properly annotate your webhook
functions.

In the body of the function we define the body of the message as `Hello! I am
happy to be here! :smile:`. The `:smile:` indicates an emoji. Then we append a
link to the Wikipedia article of the day as provided by the json payload. If
the json payload does not include data for `featured_title` and `featured_url`
we catch a `KeyError` and use `json_error` to return the appropriate
information: a 400 http status code with relevant details.

Then we send a public (stream) message with `check_send_message` which will
validate the message and then send it.

Finally, we return a 200 http status with a JSON format success message via
`json_success()`.

### Step 2: Create an api endpoint for the webhook

In order for a webhook to be externally available, it must be mapped to a url.
This is done in `zerver/lib/integrations.py`.

Look for the lines beginning with:

```
WEBHOOK_INTEGRATIONS = [
```

And you'll find the entry for Hello World:

```
  WebhookIntegration('helloworld', display_name='Hello World'),
```

This tells the Zulip api to call the `api_helloworld_webhook` function in
`zerver/views/webhooks/helloworld.py` when it receives a request at
`/api/v1/external/helloworld`.

This line also tells Zulip to generate an entry for Hello World on the Zulip
integrations page using `static/images/integrations/logos/helloworld.png` as its
icon.

At this point, if you're following along and/or writing your own Hello World
webhook, you have written enough code to test your integration.

You can do so by using Zulip itself or curl on the command line.

Using `manage.py` from within Zulip Dev environment:

```
(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:/srv/zulip$
./manage.py send_webhook_fixture_message \
> --fixture=zerver/fixtures/helloworld/helloworld_hello.json \
> '--url=http://localhost:9991/api/v1/external/helloworld?api_key=<api_key>'
```
After which you should see something similar to:

```
2016-07-07 15:06:59,187 INFO     127.0.0.1       POST    200 143ms (mem: 6ms/13) (md: 43ms/1) (db: 20ms/9q) (+start: 147ms) /api/v1/external/helloworld (helloworld-bot@zulip.com via ZulipHelloWorldWebhook)
```

Using curl:

```
curl -X POST -H "Content-Type: application/json" -d '{ "featured_title":"Marilyn Monroe", "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe" }' http://localhost:9991/api/v1/external/helloworld\?api_key\=<api_key>
```

After which you should see:
```
{"msg":"","result":"success"}
```

Using either method will create a message in Zulip:

![Image of Hello World webhook message](images/helloworld-webhook.png)

### Step 3: Create tests

Every webhook integraton should have a corresponding test class in
`zerver/tests/test_hooks.py`.

You should name the class `<WebhookName>HookTests` and this class should accept
`WebhookTestCase`. For our HelloWorld webhook, we name the test class
`HelloWorldHookTests`:

```
class HelloWorldHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/helloworld?&api_key={api_key}"
    FIXTURE_DIR_NAME = 'helloworld'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_hello_message(self):
        # type: () -> None
        expected_subject = u"Hello World";
        expected_message = u"Hello! I am happy to be here! :smile: \nThe Wikipedia featured article for today is **[Marilyn Monroe](https://en.wikipedia.org/wiki/Marilyn_Monroe)**";

        # use fixture named helloworld_hello
        self.send_and_test_stream_message('hello', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name):
        # type: (text_type) -> text_type
        return self.fixture_data("helloworld", fixture_name, file_type="json")

```

When writing tests for your webook, you'll want to include one test function
(and corresponding fixture) per each distinct message condition that your
integration supports.

If, for example, we added support for sending a goodbye message to our `Hello
World` webook, we would add another test function to `HelloWorldHookTests`
class called something like `test_goodbye_message`:

```
    def test_goodbye_message(self):
        # type: () -> None
        expected_subject = u"Hello World";
        expected_message = u"Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Goodbye](https://en.wikipedia.org/wiki/Goodbye)**";

        # use fixture named helloworld_goodbye
        self.send_and_test_stream_message('goodbye', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")
```

As well as a new fixture `helloworld_goodbye.json` in
`zerver/fixtures/helloworld/`:

```
{
  "featured_title":"Goodbye",
  "featured_url":"https://en.wikipedia.org/wiki/Goodbye",
}
```

Once you have written some tests, you can run just these new tests from within
the Zulip dev environment with this command:

```
(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:/srv/zulip$
./tools/test-backend zerver.tests.test_hooks.HelloWorldHookTests
```

(Note: You must run the tests from `/srv/zulip` directory.)

You will see some script output and if all the tests have passed, you will see:

```
Running zerver.tests.test_hooks.HelloWorldHookTests.test_hello_message
DONE!
```

### Step 4: Create documentation

Next, we add end-user documentation for our webhook integration to
`templates/zerver/integrations.html`.

There are two parts to the end-user documentation on this page.

The first is a `div` with class `integration-lozenge` for each integration.
This div shows the logo of your webhook, its name, and a link to its
installation and usage instructions.

Because there is an entry for the Hello World webhook in WEBHOOK_INTEGRATIONS
in `zerver/lib/integratins.py`, this div will be generated automatically.

The second part is a `div` with the webhook's usage instructions:

```
<div id="helloworld" class="integration-instructions">

    <p>Learn how Zulip integrations work with this simple Hello World example!</p>

    <p>The Hello World webhook will use the <code>test<code> stream, which is
    created by default in the Zulip dev environment. If you are running
    Zulip in production, you should make sure this stream exists.</p>

    <p>Next, on your <a href="/#settings" target="_blank">Zulip
    settings page</a>, create a Hello World bot.  Construct the URL for
    the Hello World bot using the API key and stream name:
      <code>{{ external_api_uri }}/v1/external/helloworld?api_key=abcdefgh&amp;stream=test</code>
    </p>

    <p>To trigger a notication using this webhook, use `send_webhook_fixture_message` from the Zulip command line:</p>
    <div class="codehilite">
      <pre>(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:/srv/zulip$
./manage.py send_webhook_fixture_message \
> --fixture=zerver/fixtures/helloworld/helloworld_hello.json \
> '--url=http://localhost:9991/api/v1/external/helloworld?api_key=<api_key>'</pre>
    </div>

    <p>Or, use curl:</p>
    <div class="codehilite">
      <pre>curl -X POST -H "Content-Type: application/json" -d '{ "featured_title":"Marilyn Monroe", "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe" }' http://localhost:9991/api/v1/external/helloworld\?api_key\=<api_key></pre>
    </div>

    <p><b>Congratulations! You're done!</b><br /> Your messages may look like:</p>

    <img class="screenshot" src="/static/images/integrations/helloworld/001.png" />
</div>
```

These documentation blocks should fall alphabetically. For the
`integration-lozenge` div this happens automatically when the html is
generated. For the `integration-instructions` div, we have added the div
between the blocks for Github and Hubot, respectively.

See [Documenting your integration](#documenting-your-integration) for further
details, including how to easily create the message screenshot.

### Step 5: Preparing a pull request to zulip/zulip

When you have finished your webhook integration and are ready for it to be
available in the Zulip product, follow these steps to prepare your pull
request:

1. Run tests including linters and ensure you have addressed any issues they
   report. See [Testing](testing.html) for details.
2. Read through [Code styles and conventions](code-style.html) and take a look
   through your code to double-check that you've followed Zulip's guidelines.
3. Take a look at your git history to ensure your commits have been clear and
   logical (see [Version Control](version-control.html) for tips). If not,
   consider revising them with `git rebase --interactive`. For most webhooks,
   you'll want to squash your changes into a single commit and include a good,
   clear commit message.
4. Push code to your fork.
5. Submit a pull request to zulip/zulip.

If you would like feedback on your integration as you go, feel free to submit
pull requests as you go, prefixing them with `[WIP]`.


