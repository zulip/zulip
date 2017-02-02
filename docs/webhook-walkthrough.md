# Webhook walkthrough

Below explains each part of a simple webhook integration, called **Hello
World**. This webhook sends a "hello" message to the `test` stream and includes
a link to the Wikipedia article of the day, which it formats from json data it
receives in the http request.

Use this walkthrough to learn how to write your first webhook
integration.

## Step 0: Create fixtures

The first step in creating a webhook is to examine the data that the
service you want to integrate will be sending to Zulip.

You can use [requestb.in](http://requestb.in/) or a similar tool to capture
webhook payload(s) from the service you are integrating. Examining this
data allows you to do two things:

1. Determine how you will need to structure your webhook code, including what
   message types your integration should support and how; and,
2. Create fixtures for your webhook tests.

A test fixture is a small file containing test data, one for each test.
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
tests](#step-4-create-tests) or [Testing](testing.html) for further details.

## Step 1: Initialize your webhook python package

In the `zerver/webhooks/` directory, create new subdirectory that will
contain all of corresponding code.  In our example it will be
`helloworld`. The new directory will be a python package, so you have
to create an empty `__init__.py` file in that directory via e.g. `touch
zerver/webhooks/helloworld/__init__.py`.

## Step 2: Create main webhook code

The majority of the code for your webhook integration will be in a single
python file, `zerver/webhooks/mywebhook/view.py`.

The Hello World integration is in `zerver/webhooks/helloworld/view.py`:

```
from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string

from zerver.models import Client, UserProfile

from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Iterable, Optional, Text

@api_key_only_webhook_view('HelloWorld')
@has_request_variables
def api_helloworld_webhook(request, user_profile, client,
                           payload=REQ(argument_type='body'),
                           stream=REQ(default='test'),
                           topic=REQ(default='Hello World')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Iterable[Dict[str, Any]]], Text, Optional[Text]) -> HttpResponse

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
function `api_helloworld_webhook`, decorating it with `api_key_only_webhook_view` and
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

In the example above, we have defined `payload` which is populated
from the body of the http request, `stream` with a default of `test`
(available by default in the Zulip development environment), and
`topic` with a default of `Hello World`.

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

## Step 3: Create an api endpoint for the webhook

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
`zerver/webhooks/helloworld/view.py` when it receives a request at
`/api/v1/external/helloworld`.

This line also tells Zulip to generate an entry for Hello World on the Zulip
integrations page using `static/images/integrations/logos/helloworld.png` as its
icon.

At this point, if you're following along and/or writing your own Hello World
webhook, you have written enough code to test your integration.

First, get an API key from the Your bots section of your Zulip user's Settings
page. If you haven't created a bot already, you can do that there. Then copy
its API key and replace the placeholder "<api_key>" in the examples with
your real key. This is how Zulip knows the request is from an authorized user.

Now you can test using Zulip itself, or curl on the command line.

Using `manage.py` from within the Zulip development environment:

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

## Step 4: Create tests

Every webhook integration should have a corresponding test file:
`zerver/webhooks/mywebhook/tests.py`.

The Hello World integration's tests are in zerver/webhooks/helloworld/tests.py

You should name the class `<WebhookName>HookTests` and have it inherit from
the base class `WebhookTestCase`. For our HelloWorld webhook, we name the test
class `HelloWorldHookTests`:

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
        # type: (Text) -> Text
        return self.fixture_data("helloworld", fixture_name, file_type="json")

```

In the above example, `STREAM_NAME`, `URL_TEMPLATE`, and `FIXTURE_DIR_NAME` refer
to class attributes from the base class, `WebhookTestCase`. These are needed by
`send_and_test_stream_message` to determine how to execute your test.

When writing tests for your webhook, you'll want to include one test function
(and corresponding fixture) per each distinct message condition that your
integration supports.

If, for example, we added support for sending a goodbye message to our `Hello
World` webhook, we would add another test function to `HelloWorldHookTests`
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
the Zulip development environment with this command:

```
(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:/srv/zulip$
./tools/test-backend zerver/webhooks/helloworld
```

(Note: You must run the tests from the top level of your development directory.
The standard location in a Vagrant environment is `/srv/zulip`. If you are not
using Vagrant, use the directory where you have your development environment.)

You will see some script output and if all the tests have passed, you will see:

```
Running zerver.webhooks.helloworld.tests.HelloWorldHookTests.test_goodbye_message
Running zerver.webhooks.helloworld.tests.HelloWorldHookTests.test_hello_message
DONE!
```

## Step 5: Create documentation

Next, we add end-user documentation for our webhook integration.  You
can see the existing examples at
[https://zulipchat.com/integrations](https://zulipchat.com/integrations)
or by accessing `/integrations` in your Zulip development environemtn.

There are two parts to the end-user documentation on this page.

The first is the lozenge in the grid of integrations, showing your
integration logo and name, which links to the full documentation.
This is generated automatically once you've registered the integration
in WEBHOOK_INTEGRATIONS in `zerver/lib/integrations.py`, and supports
some customization via options to the `WebhookIntegration` class.

Second, you need to write the actual documentation content in
`zerver/webhooks/mywebhook/doc.html`.

```
<p>Learn how Zulip integrations work with this simple Hello World example!</p>

<p>The Hello World webhook will use the <code>test<code> stream, which is
created by default in the Zulip development environment. If you are running
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
```

These documentation blocks should fall alphabetically. For the
`integration-lozenge` div this happens automatically when the html is
generated. For the `integration-instructions` div, we have added the div
between the blocks for GitHub and Hubot, respectively.

See [Documenting your integration](integration-guide.html#documenting-your-integration) for further
details, including how to easily create the message screenshot.

## Step 5: Preparing a pull request to zulip/zulip

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
