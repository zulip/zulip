# Incoming webhook walkthrough

Below, we explain each part of a simple incoming webhook integration,
called **Hello World**.  This integration sends a "hello" message to the `test`
stream and includes a link to the Wikipedia article of the day, which
it formats from json data it receives in the http request.

Use this walkthrough to learn how to write your first webhook
integration.

## Step 0: Create fixtures

The first step in creating an incoming webhook is to examine the data that the
service you want to integrate will be sending to Zulip.

* Use [Zulip's JSON integration](/integrations/doc/json),
<https://webhook.site/>, or a similar tool to capture webhook
payload(s) from the service you are integrating. Examining this data
allows you to do two things:

1. Determine how you will need to structure your webhook code, including what
   message types your integration should support and how.
2. Create fixtures for your webhook tests.

A test fixture is a small file containing test data, one for each test.
Fixtures enable the testing of webhook integration code without the need to
actually contact the service being integrated.

Because `Hello World` is a very simple integration that does one
thing, it requires only one fixture,
`zerver/webhooks/helloworld/fixtures/hello.json`:

```json
{
  "featured_title":"Marilyn Monroe",
  "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe",
}
```

When writing your own incoming webhook integration, you'll want to write a test function
for each distinct message condition your integration supports. You'll also need a
corresponding fixture for each of these tests. Depending on the type of data
the 3rd party service sends, your fixture may contain JSON, URL encoded text, or
some other kind of data. See [Step 5: Create automated tests](#step-5-create-automated-tests) or
[Testing](https://zulip.readthedocs.io/en/latest/testing/testing.html) for further details.

### HTTP Headers

Some third-party webhook APIs, such as GitHub's, don't encode all the
information about an event in the JSON request body.  Instead, they
put key details like the event type in a separate HTTP header
(generally this is clear in their API documentation).  In order to
test Zulip's handling of that integration, you will need to record
which HTTP headers are used with each fixture you capture.

Since this is integration-dependent, Zulip offers a simple API for
doing this, which is probably best explained by looking at the example
for GitHub: `zerver/webhooks/github/view.py`; basically, as part of
writing your integration, you'll write a special function in your
view.py file that maps the filename of the fixture to the set of HTTP
headers to use. This function must be named "fixture_to_headers". Most
integrations will use the same strategy as the GitHub integration:
encoding the third party variable header data (usually just an event
type) in the fixture filename, in such a case, you won't need to
explicitly write the logic for such a special function again,
instead you can just use the same helper method that the GitHub
integration uses.

## Step 1: Initialize your webhook python package

In the `zerver/webhooks/` directory, create new subdirectory that will
contain all of the corresponding code.  In our example it will be
`helloworld`. The new directory will be a python package, so you have
to create an empty `__init__.py` file in that directory via e.g.
`touch zerver/webhooks/helloworld/__init__.py`.

## Step 2: Create main webhook code

The majority of the code for your new integration will be in a single
python file, `zerver/webhooks/mywebhook/view.py`.

The Hello World integration is in `zerver/webhooks/helloworld/view.py`:

```python
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("HelloWorld")
@typed_endpoint
def api_helloworld_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    # construct the body of the message
    body = "Hello! I am happy to be here! :smile:"

    # try to add the Wikipedia article of the day
    body_template = (
        "\nThe Wikipedia featured article for today is **[{featured_title}]({featured_url})**"
    )
    body += body_template.format(
        featured_title=payload["featured_title"].tame(check_string),
        featured_url=payload["featured_url"].tame(check_string),
    )

    topic = "Hello World"

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)
```

The above code imports the required functions and defines the main webhook
function `api_helloworld_webhook`, decorating it with `webhook_view` and
`typed_endpoint`. The `typed_endpoint` decorator allows you to
access request variables with `JsonBodyPayload()`. You can find more about `JsonBodyPayload` and request variables in [Writing views](
https://zulip.readthedocs.io/en/latest/tutorials/writing-views.html#request-variables).

You must pass the name of your integration to the
`webhook_view` decorator; that name will be used to
describe your integration in Zulip's analytics (e.g. the `/stats`
page). Here we have used `HelloWorld`. To be consistent with other
integrations, use the name of the product you are integrating in camel
case, spelled as the product spells its own name (except always first
letter upper-case).

The `webhook_view` decorator indicates that the 3rd party service will
send the authorization as an API key in the query parameters. If your service uses
HTTP basic authentication, you would instead use the `authenticated_rest_api_view`
decorator.

You should name your webhook function as such
`api_webhookname_webhook` where `webhookname` is the name of your
integration and is always lower-case.

At minimum, the webhook function must accept `request` (Django
[HttpRequest](https://docs.djangoproject.com/en/3.2/ref/request-response/#django.http.HttpRequest)
object), and `user_profile` (Zulip's user object). You may also want to
define additional parameters using the `REQ` object.

In the example above, we have defined `payload` which is populated
from the body of the http request, `stream` with a default of `test`
(available by default in the Zulip development environment), and
`topic` with a default of `Hello World`. If your webhook uses a custom stream,
it must exist before a message can be created in it. (See
[Step 4: Create automated tests](#step-5-create-automated-tests) for how to handle this in tests.)

The line that begins `# type` is a mypy type annotation. See [this
page](https://zulip.readthedocs.io/en/latest/testing/mypy.html) for details about
how to properly annotate your webhook functions.

In the body of the function we define the body of the message as `Hello! I am
happy to be here! :smile:`. The `:smile:` indicates an emoji. Then we append a
link to the Wikipedia article of the day as provided by the json payload.

* Sometimes, it might occur that a json payload does not contain all required keys your
  integration checks for. In such a case, any `KeyError` thrown is handled by the server
  backend and will create an appropriate response.

Then we send a message with `check_send_webhook_message`, which will
validate the message and do the following:

* Send a public (stream) message if the `stream` query parameter is
  specified in the webhook URL.
* If the `stream` query parameter isn't specified, it will send a direct
  message to the owner of the webhook bot.

Finally, we return a 200 http status with a JSON format success message via
`json_success(request)`.

## Step 3: Create an API endpoint for the webhook

In order for an incoming webhook to be externally available, it must be mapped
to a URL. This is done in `zerver/lib/integrations.py`.

Look for the lines beginning with:

```python
WEBHOOK_INTEGRATIONS: List[WebhookIntegration] = [
```

And you'll find the entry for Hello World:

```python
  WebhookIntegration("helloworld", ["misc"], display_name="Hello World"),
```

This tells the Zulip API to call the `api_helloworld_webhook` function in
`zerver/webhooks/helloworld/view.py` when it receives a request at
`/api/v1/external/helloworld`.

This line also tells Zulip to generate an entry for Hello World on the Zulip
integrations page using `static/images/integrations/logos/helloworld.svg` as its
icon. The second positional argument defines a list of categories for the
integration.

At this point, if you're following along and/or writing your own Hello World
webhook, you have written enough code to test your integration. There are three
tools which you can use to test your webhook - 2 command line tools and a GUI.

### Webhooks requiring custom configuration

In rare cases, it's necessary for an incoming webhook to require
additional user configuration beyond what is specified in the post
URL.  The typical use case for this is APIs like the Stripe API that
require clients to do a callback to get details beyond an opaque
object ID that one would want to include in a Zulip notification.

These configuration options are declared as follows:

```python
    WebhookIntegration('helloworld', ['misc'], display_name='Hello World',
                       config_options=[('HelloWorld API key', 'hw_api_key', check_string)])
```

`config_options` is a list describing the parameters the user should
configure:
    1. A user-facing string describing the field to display to users.
    2. The field name you'll use to access this from your `view.py` function.
    3. A Validator, used to verify the input is valid.

Common validators are available in `zerver/lib/validators.py`.

## Step 4: Manually testing the webhook

For either one of the command line tools, first, you'll need to get an
API key from the **Bots** section of your Zulip user's **Personal
settings**. To test the webhook, you'll need to [create a
bot](https://zulip.com/help/add-a-bot-or-integration) with the
**Incoming webhook** type. Replace `<api_key>` with your bot's API key
in the examples presented below! This is how Zulip knows that the
request was made by an authorized user.

### Curl

Using curl:
```bash
curl -X POST -H "Content-Type: application/json" -d '{ "featured_title":"Marilyn Monroe", "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe" }' http://localhost:9991/api/v1/external/helloworld\?api_key\=<api_key>
```

After running the above command, you should see something similar to:

```json
{"msg":"","result":"success"}
```

### Management command: send_webhook_fixture_message

Using `manage.py` from within the Zulip development environment:

```console
(zulip-py3-venv) vagrant@vagrant:/srv/zulip$
./manage.py send_webhook_fixture_message \
    --fixture=zerver/webhooks/helloworld/fixtures/hello.json \
    '--url=http://localhost:9991/api/v1/external/helloworld?api_key=<api_key>'
```

After running the above command, you should see something similar to:

```
2016-07-07 15:06:59,187 INFO     127.0.0.1       POST    200 143ms (mem: 6ms/13) (md: 43ms/1) (db: 20ms/9q) (+start: 147ms) /api/v1/external/helloworld (helloworld-bot@zulip.com via ZulipHelloWorldWebhook)
```

Some webhooks require custom HTTP headers, which can be passed using
`./manage.py send_webhook_fixture_message --custom-headers`.  For
example:

    --custom-headers='{"X-Custom-Header": "value"}'

The format is a JSON dictionary, so make sure that the header names do
not contain any spaces in them and that you use the precise quoting
approach shown above.

For more information about `manage.py` command-line tools in Zulip, see
the [management commands][management-commands] documentation.

[management-commands]: https://zulip.readthedocs.io/en/latest/production/management-commands.html

### Integrations Dev Panel
This is the GUI tool.

{start_tabs}

1. Run `./tools/run-dev` then go to http://localhost:9991/devtools/integrations/.

1. Set the following mandatory fields:
**Bot** - Any incoming webhook bot.
**Integration** - One of the integrations.
**Fixture** - Though not mandatory, it's recommended that you select one and then tweak it if necessary.
The remaining fields are optional, and the URL will automatically be generated.

1. Click **Send**!

{end_tabs}

By opening Zulip in one tab and then this tool in another, you can quickly tweak
your code and send sample messages for many different test fixtures.

Note: Custom HTTP Headers must be entered as a JSON dictionary, if you want to use any in the first place that is.
Feel free to use 4-spaces as tabs for indentation if you'd like!

Your sample notification may look like:

<img class="screenshot" src="/static/images/api/helloworld-webhook.png" alt="screenshot" />



## Step 5: Create automated tests

Every webhook integration should have a corresponding test file:
`zerver/webhooks/mywebhook/tests.py`.

The Hello World integration's tests are in `zerver/webhooks/helloworld/tests.py`

You should name the class `<WebhookName>HookTests` and have it inherit from
the base class `WebhookTestCase`. For our HelloWorld webhook, we name the test
class `HelloWorldHookTests`:

```python
class HelloWorldHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/helloworld?&api_key={api_key}&stream={stream}"
    DIRECT_MESSAGE_URL_TEMPLATE = "/api/v1/external/helloworld?&api_key={api_key}"
    WEBHOOK_DIR_NAME = "helloworld"

    # Note: Include a test function per each distinct message condition your integration supports
    def test_hello_message(self) -> None:
        expected_topic = "Hello World"
        expected_message = "Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Marilyn Monroe](https://en.wikipedia.org/wiki/Marilyn_Monroe)**"

        # use fixture named helloworld_hello
        self.check_webhook(
            "hello",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
```

In the above example, `CHANNEL_NAME`, `URL_TEMPLATE`, and `WEBHOOK_DIR_NAME` refer
to class attributes from the base class, `WebhookTestCase`. These are needed by
the helper function `check_webhook` to determine how to execute
your test. `CHANNEL_NAME` should be set to your default stream. If it doesn't exist,
`check_webhook` will create it while executing your test.

If your test expects a stream name from a test fixture, the value in the fixture
and the value you set for `CHANNEL_NAME` must match. The test helpers use `CHANNEL_NAME`
to create the destination stream, and then create the message to send using the
value from the fixture. If these don't match, the test will fail.

`URL_TEMPLATE` defines how the test runner will call your incoming webhook, in the same way
 you would provide a webhook URL to the 3rd party service. `api_key={api_key}` says
that an API key is expected.

When writing tests for your webhook, you'll want to include one test function
(and corresponding fixture) per each distinct message condition that your
integration supports.

If, for example, we added support for sending a goodbye message to our `Hello
World` webhook, we would add another test function to `HelloWorldHookTests`
class called something like `test_goodbye_message`:

```python
    def test_goodbye_message(self) -> None:
        expected_topic = "Hello World"
        expected_message = "Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Goodbye](https://en.wikipedia.org/wiki/Goodbye)**"

        # use fixture named helloworld_goodbye
        self.check_webhook(
            "goodbye",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
```

As well as a new fixture `goodbye.json` in
`zerver/webhooks/helloworld/fixtures/`:

```json
{
  "featured_title":"Goodbye",
  "featured_url":"https://en.wikipedia.org/wiki/Goodbye",
}
```

Also consider if your integration should have negative tests, a test where the
data from the test fixture should result in an error. For details see
[Negative tests](#negative-tests), below.

Once you have written some tests, you can run just these new tests from within
the Zulip development environment with this command:

```console
(zulip-py3-venv) vagrant@vagrant:/srv/zulip$
./tools/test-backend zerver/webhooks/helloworld
```

(Note: You must run the tests from the top level of your development directory.
The standard location in a Vagrant environment is `/srv/zulip`. If you are not
using Vagrant, use the directory where you have your development environment.)

You will see some script output and if all the tests have passed, you will see:

```console
Running zerver.webhooks.helloworld.tests.HelloWorldHookTests.test_goodbye_message
Running zerver.webhooks.helloworld.tests.HelloWorldHookTests.test_hello_message
DONE!
```

## Step 6: Create documentation

Next, we add end-user documentation for our integration.  You
can see the existing examples at <https://zulip.com/integrations>
or by accessing `/integrations` in your Zulip development environment.

There are two parts to the end-user documentation on this page.

The first is the lozenge in the grid of integrations, showing your
integration logo and name, which links to the full documentation.
This is generated automatically once you've registered the integration
in `WEBHOOK_INTEGRATIONS` in `zerver/lib/integrations.py`, and supports
some customization via options to the `WebhookIntegration` class.

Second, you need to write the actual documentation content in
`zerver/webhooks/mywebhook/doc.md`.

```md
Learn how Zulip integrations work with this simple Hello World example!

1.  The Hello World webhook will use the `test` stream, which is created
    by default in the Zulip development environment. If you are running
    Zulip in production, you should make sure that this stream exists.

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1.  To trigger a notification using this example webhook, you can use
    `send_webhook_fixture_message` from a [Zulip development
    environment](https://zulip.readthedocs.io/en/latest/development/overview.html):

    ```
        (zulip-py3-venv) vagrant@vagrant:/srv/zulip$
        ./manage.py send_webhook_fixture_message \
        > --fixture=zerver/tests/fixtures/helloworld/hello.json \
        > '--url=http://localhost:9991/api/v1/external/helloworld?api_key=abcdefgh&stream=stream%20name;'
    ```

    Or, use curl:

    ```
    curl -X POST -H "Content-Type: application/json" -d '{ "featured_title":"Marilyn Monroe", "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe" }' http://localhost:9991/api/v1/external/helloworld\?api_key=abcdefgh&stream=stream%20name;
    ```

{!congrats.md!}

![Hello World integration](/static/images/integrations/helloworld/001.png)

```

`{!create-an-incoming-webhook.md!}` and `{!congrats.md!}` are examples of
a Markdown macro. Zulip has a macro-based Markdown/Jinja2 framework that
includes macros for common instructions in Zulip's webhooks/integrations
documentation.

See
[our guide on documenting an integration][integration-docs-guide]
for further details, including how to easily create the message
screenshot. Mostly you should plan on templating off an existing guide, like
[this one](https://raw.githubusercontent.com/zulip/zulip/main/zerver/webhooks/github/doc.md).

[integration-docs-guide]: https://zulip.readthedocs.io/en/latest/documentation/integrations.html

## Step 7: Preparing a pull request to zulip/zulip

When you have finished your webhook integration, follow these guidelines before
pushing the code to your fork and submitting a pull request to zulip/zulip:

- Run tests including linters and ensure you have addressed any issues they
  report. See [Testing](https://zulip.readthedocs.io/en/latest/testing/testing.html)
  and [Linters](https://zulip.readthedocs.io/en/latest/testing/linters.html) for details.
- Read through [Code styles and conventions](
  https://zulip.readthedocs.io/en/latest/contributing/code-style.html) and take a look
  through your code to double-check that you've followed Zulip's guidelines.
- Take a look at your Git history to ensure your commits have been clear and
  logical (see [Commit discipline](
  https://zulip.readthedocs.io/en/latest/contributing/commit-discipline.html) for tips). If not,
  consider revising them with `git rebase --interactive`. For most incoming webhooks,
  you'll want to squash your changes into a single commit and include a good,
  clear commit message.

If you would like feedback on your integration as you go, feel free to post a
message on the [public Zulip instance](https://chat.zulip.org/#narrow/stream/integrations).
You can also create a [draft pull request](
https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests#draft-pull-requests) while you
are still working on your integration. See the
[Git guide](https://zulip.readthedocs.io/en/latest/git/pull-requests.html#create-a-pull-request)
for more on Zulip's pull request process.

## Advanced topics

More complex implementation or testing needs may require additional code, beyond
what the standard helper functions provide. This section discusses some of
these situations.

### Negative tests

A negative test is one that should result in an error, such as incorrect data.
The helper functions may interpret this as a test failure, when it should instead
be a successful test of an error condition. To correctly test these cases, you
must explicitly code your test's execution (using other helpers, as needed)
rather than call the usual helper function.

Here is an example from the WordPress integration:

```python
def test_unknown_action_no_data(self) -> None:
    # Mimic check_webhook() to manually execute a negative test.
    # Otherwise its call to send_webhook_payload() would assert on the non-success
    # we are testing. The value of result is the error message the webhook should
    # return if no params are sent. The fixture for this test is an empty file.

    # subscribe to the target stream
    self.subscribe(self.test_user, self.CHANNEL_NAME)

    # post to the webhook url
    post_params = {'stream_name': self.CHANNEL_NAME,
                   'content_type': 'application/x-www-form-urlencoded'}
    result = self.client_post(self.url, 'unknown_action', **post_params)

    # check that we got the expected error message
    self.assert_json_error(result, "Unknown WordPress webhook action: WordPress action")
```

In a normal test, `check_webhook` would handle all the setup
and then check that the incoming webhook's response matches the expected result. If
the webhook returns an error, the test fails. Instead, explicitly do the
setup it would have done, and check the result yourself.

Here, `subscribe_to_stream` is a test helper that uses `TEST_USER_EMAIL` and
`CHANNEL_NAME` (attributes from the base class) to register the user to receive
messages in the given stream. If the stream doesn't exist, it creates it.

`client_post`, another helper, performs the HTTP POST that calls the incoming
webhook. As long as `self.url` is correct, you don't need to construct the webhook
URL yourself. (In most cases, it is.)

`assert_json_error` then checks if the result matches the expected error.
If you had used `check_webhook`, it would have called
`send_webhook_payload`, which checks the result with `assert_json_success`.

### Custom query parameters

Custom arguments passed in URL query parameters work as expected in the webhook
code, but require special handling in tests.

For example, here is the definition of a webhook function that gets both `stream`
and `topic` from the query parameters:

```python
def api_querytest_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: str=REQ(argument_type='body'),
                          stream: str=REQ(default='test'),
                          topic: str=REQ(default='Default Alert')):
```

In actual use, you might configure the 3rd party service to call your Zulip
integration with a URL like this:

```
http://myhost/api/v1/external/querytest?api_key=abcdefgh&stream=alerts&topic=queries
```

It provides values for `stream` and `topic`, and the webhook can get those
using `REQ` without any special handling. How does this work in a test?

The new attribute `TOPIC` exists only in our class so far. In order to
construct a URL with a query parameter for `topic`, you can pass the
attribute `TOPIC` as a keyword argument to `build_webhook_url`, like so:

```python
class QuerytestHookTests(WebhookTestCase):

    CHANNEL_NAME = 'querytest'
    TOPIC = "Default topic"
    URL_TEMPLATE = "/api/v1/external/querytest?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'querytest'

    def test_querytest_test_one(self) -> None:
        # construct the URL used for this test
        self.TOPIC = "Query test"
        self.url = self.build_webhook_url(topic=self.TOPIC)

        # define the expected message contents
        expected_topic = "Query test"
        expected_message = "This is a test of custom query parameters."

        self.check_webhook('test_one', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")
```

You can also override `get_body` or `get_payload` if your test data
needs to be constructed in an unusual way.

For more, see the definition for the base class, `WebhookTestCase`
in `zerver/lib/test_classes.py`, or just grep for examples.


### Custom HTTP event-type headers

Some third-party services set a custom HTTP header to indicate the event type that
generates a particular payload. To extract such headers, we recommend using the
`validate_extract_webhook_http_header` function in `zerver/lib/webhooks/common.py`,
like so:

```python
event = validate_extract_webhook_http_header(request, header, integration_name)
```

`request` is the `HttpRequest` object passed to your main webhook function. `header`
is the name of the custom header you'd like to extract, such as `X-Event-Key`, and
`integration_name` is the name of the third-party service in question, such as
`GitHub`.

Because such headers are how some integrations indicate the event types of their
payloads, the absence of such a header usually indicates a configuration
issue, where one either entered the URL for a different integration, or happens to
be running an older version of the integration that doesn't set that header.

If the requisite header is missing, this function sends a direct message to the
owner of the webhook bot, notifying them of the missing header.

### Handling unexpected webhook event types

Many third-party services have dozens of different event types. In
some cases, we may choose to explicitly ignore specific events. In
other cases, there may be events that are new or events that we don't
know about. In such cases, we recommend raising
`UnsupportedWebhookEventTypeError` (found in `zerver/lib/exceptions.py`),
with a string describing the unsupported event type, like so:

```
raise UnsupportedWebhookEventTypeError(event_type)
```

## Related articles

* [Integrations overview](/api/integrations-overview)
* [Incoming webhook integrations](/api/incoming-webhooks-overview)
