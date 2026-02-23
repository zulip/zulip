# Writing an incoming webhook

This guide goes through the process of creating a simple incoming webhook
integration, using the [Zulip Hello World](https://zulip.com/integrations/helloworld)
integration as an example.

The example integration receives an HTTP POST request with JSON data
about Wikipedia's featured article of the day from a fictional
third-party service, formats that data into a "hello" message, and sends
that message to the specified conversation in Zulip.

Before you get started, you'll want to set up the [Zulip development
environment](../development/overview.md).

## Step 0: Create fixtures

The first step in creating an incoming webhook integration is to examine
the data that the third-party service you're working with will send to
Zulip.

Use [Zulip's JSON integration](https://zulip.com/integrations/json),
<https://webhook.site/>, or a similar tool to capture outgoing webhook
payload(s) from the service. Examining this data allows you to:

- Determine how you will structure your webhook integration code,
  including what event types your integration should support and how.
- Create fixtures. A test fixture is a small file containing test data,
  generally one for each event type. Fixtures enable the testing of
  webhook integration code without the need to actually contact the
  service being integrated.

You'll want to write a test for each distinct event type your incoming
webhook integration supports, and you'll need a corresponding fixture
for each of these tests. Depending on the type of data the third-party
service sends, your fixtures may contain JSON, URL encoded text, or
some other kind of data. [Step 5: Create automated tests](#step-5-create-automated-tests)
and [our testing documentation](../testing/testing.md) have further
details about writing tests and using test fixtures.

Because the Zulip Hello World is very simple and does only one thing,
it requires only one fixture,
`zerver/webhooks/helloworld/fixtures/hello.json`.

```json
{
  "featured_title":"Marilyn Monroe",
  "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe",
}
```

For integrations that send the event type or other important information as
part of the HTTP header, you will need to record the header value for each
fixture. Refer to
[the section on custom HTTP headers](incoming-webhooks-reference.md#custom-http-headers)
in the reference guide for more details.

## Step 1: Initialize the python package

In the `zerver/webhooks/` directory, create new subdirectory for the
incoming webhook integration. In our example, it is `helloworld`. The new
directory will be a python package, so you should also create an empty
`__init__.py` file in that directory via, for
example, `touch zerver/webhooks/helloworld/__init__.py`.

## Step 2: Write the main webhook code

The majority of the code for your new integration will be in a single
python file named `view.py`. The Zulip Hello World integration code is
found in `zerver/webhooks/helloworld/view.py`:

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

    topic_name = "Hello World"

    # send the message
    check_send_webhook_message(request, user_profile, topic_name, body)

    return json_success(request)
```

The above code imports the required functions and defines the main
webhook handler, `api_helloworld_webhook`, decorating it with
`webhook_view` and `typed_endpoint`.

### Decorators

The `typed_endpoint` decorator allows the integration to access request
variables with `JsonBodyPayload[WildValue]`. You can find more about
`JsonBodyPayload` and request variables in [the tutorial on writing
views](../tutorials/writing-views.md#request-variables).

You must pass the name of the integration to the `webhook_view` decorator.
That name will be used to describe the integration in Zulip's analytics
pages. In the example, the integration's name is `HelloWorld`. To be
consistent with other incoming webhook integrations, you should use the
name of the third-party service in camel case, spelled as the service
spells its own name, with the exception that the first letter should be
upper case even if it's lower case in the service's name/brand.

The `webhook_view` decorator indicates that the third-party service will
send the authorization as an API key in the query parameters. If the
third-party service uses HTTP basic authentication, you would instead use
the `authenticated_rest_api_view` decorator.

### Main webhook handler

The webhook function should be named as in the example above,
`api_helloworld_webhook`, replacing `helloworld` with the name of the
integration, in lower case.

At minimum, the webhook function must accept `request` (Django
[HttpRequest](https://docs.djangoproject.com/en/5.0/ref/request-response/#django.http.HttpRequest)
object), and `user_profile` (Zulip's user object). You can also define
additional parameters using the `typed_endpoint` decorator.

In the Zulip Hello World example above, there is also a `payload`
parameter, which is populated from the body of the HTTP POST request.

The main function defines the body of the message using [Zulip's message
formatting](https://zulip.com/api/message-formatting). For example,
`:smile:` in the initial sentence of the message body indicates an emoji.
The data from the JSON payload is used for the link to the Wikipedia
featured article of the day.

Sometimes, it may occur that a JSON payload does not contain all the
required keys that an integration checks for. In such a case, any
`KeyError` that is thrown is handled by the Zulip server's backend, which
will create an appropriate response.

A default topic name should be defined for cases when the [webhook
URL](incoming-webhooks-overview.md#url-specification) specifies a
channel recipient, via the `stream` query parameter, but does not specify
a topic.

The formatted message is sent with `check_send_webhook_message`, which
will validate the message and do the following:

- Send a channel message if the `stream` query parameter is specified in
  the [webhook URL](incoming-webhooks-overview.md#url-specification).
- Send a direct message to the owner of the webhook bot if the `stream`
  query parameter isn't specified.

Finally, a response is sent with a 200 HTTP status with a JSON format
success message via `json_success(request)`.

## Step 3: Create an API endpoint for the webhook

In order for an incoming webhook integration to be externally available,
it must be mapped to a URL. This "registration" is done in
`zerver/lib/integrations.py`.

Look for the lines beginning with:

```python
INCOMING_WEBHOOK_INTEGRATIONS: List[IncomingWebhookIntegration] = [
```

In that list, find the entry for the example Hello World integration:

```python
    IncomingWebhookIntegration(
        "helloworld", ["misc"], [WebhookScreenshotConfig("hello.json")], display_name="Hello World"
    ),
```

This tells the Zulip API to call the `api_helloworld_webhook` function in
`zerver/webhooks/helloworld/view.py` when it receives a request at
`/api/v1/external/helloworld`.

This entry also adds the example Hello World integration to Zulip's main
[integrations documentation](https://zulip.com/integrations/). The second
argument defines the categories that include the integration in said
documentation. The third argument defines the configuration for
generating (and updating) the example screenshot included in the
integration's documentation page. And the final argument defines the
display name for the integration in the documentation. [Step 6: Create
documentation](#step-6-document-the-integration) has more details about
creating end-user documentation.

In cases where an incoming webhook integration supports optional URL
parameters, use the `url_options` argument described in
[the custom URL parameters section](incoming-webhooks-reference.md#custom-url-query-parameters)
of the reference guide to create the corresponding UI element in the modal
for [generating an integration URL](https://zulip.com/help/generate-integration-url).

## Step 4: Manually test the webhook

You'll want to manually test your webhook implementation in the Zulip
development environment. There are two command line tools you can use,
as well as a GUI tool.

For either one of the command line tools, you'll need to [get an API
key](https://zulip.com/api/api-keys) for an [incoming webhook
bot](https://zulip.com/help/add-a-bot-or-integration) in your Zulip
development environment. Replace `<api_key>` with the bot's API key in
the examples below. This is how the server knows that the request was
made by an authorized user.

### curl

Using curl, with the Zulip development server running in a separate
console window:

```bash
curl -X POST -H "Content-Type: application/json" -d '{ "featured_title":"Marilyn Monroe", "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe" }' http://localhost:9991/api/v1/external/helloworld\?api_key\=<api_key>
```

After running the above command, you should see something similar to:

```json
{"msg":"","result":"success"}
```

And if you log-in to the web app as the bot's owner, you should see a new
direct message from the bot.

### `send_webhook_fixture_message` management command

Using `manage.py` from within the Zulip development environment:

```console
(zulip-server) vagrant@vagrant:/srv/zulip$
./manage.py send_webhook_fixture_message \
    --fixture=zerver/webhooks/helloworld/fixtures/hello.json \
    '--url=http://localhost:9991/api/v1/external/helloworld?api_key=<api_key>'
```

After running the above command, you should see something similar to:

```
2016-07-07 15:06:59,187 INFO     127.0.0.1       POST    200 143ms (mem: 6ms/13) (md: 43ms/1) (db: 20ms/9q) (+start: 147ms) /api/v1/external/helloworld (helloworld-bot@zulip.com via ZulipHelloWorldWebhook)
```

Some webhooks require custom HTTP headers, which can be passed using
`./manage.py send_webhook_fixture_message --custom-headers`. For
example:

    --custom-headers='{"X-Custom-Header": "value"}'

The format is a JSON dictionary, so make sure that the header names do
not contain any spaces in them and that you use the precise quoting
approach shown above.

For more information about `manage.py` command-line tools in Zulip, see
the [management commands](../production/management-commands.md)
documentation.

### Integrations dev panel

This is a GUI tool that you can use to test your webhook in the Zulip
development environment.

1. Run `./tools/run-dev`, and use a web browser to go to
   `http://localhost:9991/devtools/integrations/`.
1. Select a bot, an integration and a fixture from the dropdown menus.
1. Click **Send**. The webhook notification message will be sent to the
   default Zulip organization in your development environment.

By having Zulip open in one browsre tab and this tool in another, you can
quickly tweak your webhook code and send sample messages for different
test fixtures.

Custom HTTP headers must be entered as a JSON dictionary, if you want to
use any. Feel free to use 4-spaces as tabs for indentation if you'd like.

## Step 5: Create automated tests

Every incoming webhook integration should have a corresponding `tests.py`
file. The Hello World integration's tests are in
`zerver/webhooks/helloworld/tests.py`.

The test class should be named `<WebhookName>HookTests`, and it should
inherit the `WebhookTestCase` base class. For Zulip's Hello World
integration, the test class is `HelloWorldHookTests`.

```python
class HelloWorldHookTests(WebhookTestCase):
    DIRECT_MESSAGE_URL_TEMPLATE = "/api/v1/external/helloworld?&api_key={api_key}"

    # Note: Include a test function per each distinct message condition your integration supports
    def test_hello_message(self) -> None:
        expected_topic_name = "Hello World"
        expected_message = "Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Marilyn Monroe](https://en.wikipedia.org/wiki/Marilyn_Monroe)**"

        # use fixture named helloworld_hello
        self.check_webhook(
            "hello",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_pm_to_bot_owner(self) -> None:
        # Note that this is really just a test for check_send_webhook_message
        self.url_template = self.DIRECT_MESSAGE_URL_TEMPLATE
        self.url = self.build_webhook_url()
        expected_message = "Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Goodbye](https://en.wikipedia.org/wiki/Goodbye)**"

        self.send_and_test_private_message(
            "goodbye",
            expected_message=expected_message,
            content_type="application/x-www-form-urlencoded",
        )
```

When writing tests, you'll want to include one test function (and a
corresponding test fixture) for each distinct event type and condition
that the integration supports.

If, for example, we added support for sending a goodbye message to the
Hello World webhook, then we would add another test function to
`HelloWorldHookTests` class called something like `test_goodbye_message`:

```python
    def test_goodbye_message(self) -> None:
        expected_topic_name = "Hello World"
        expected_message = "Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Goodbye](https://en.wikipedia.org/wiki/Goodbye)**"

        # use fixture named helloworld_goodbye
        self.check_webhook(
            "goodbye",
            expected_topic_name,
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

Also, consider if the integration should have negative tests, i.e., tests
where the data from the test fixture should result in an error. For
details, see [negative tests](#negative-tests) below.

Once you have written some tests, you can run just these new tests from
within the Zulip development environment with this command:

```console
./tools/test-backend zerver/webhooks/helloworld
```

You will see some script output in the console. And if all the tests have
passed, you will see:

```console
Running zerver.webhooks.helloworld.tests.HelloWorldHookTests.test_goodbye_message
Running zerver.webhooks.helloworld.tests.HelloWorldHookTests.test_hello_message
DONE!
```

## Step 6: Document the integration

In order for an incoming webhook integration to be used, there needs to
be documentation for end-users. All incoming webhooks are included in
Zulip's main [integrations documentation](https://zulip.com/integrations).

There are two parts to the user-facing integrations documentation.

The first is the lozenge in the grid of integrations, which shows the
integration logo and name, and is a link to the detailed documentation
for each integration.

Each integration needs a square, svg logo of the third-party service that
has been integrated with Zulip, which is saved in the
`static/images/integrations/logos` directory. The Zulip Hello World logo
can be found at `static/images/integrations/logos/helloworld.svg`.

The lozenge is generated automatically once the integration is added to
`INCOMING_WEBHOOK_INTEGRATIONS` in `zerver/lib/integrations.py`, which
supports some customization via options to the `IncomingWebhookIntegration`
class.

Second, is the detailed documentation content for the integration, which
is in a file named `doc.md` in the integration's directory. The Zulip
Hello World documentation can be found at `zerver/webhooks/helloworld/doc.md`.

Zulip has a macro-based Markdown/Jinja2 framework that includes macros for
common instructions in Zulip's webhooks/integrations documentation (e.g.,
`{!create-an-incoming-webhook.md!}` and `{!congrats.md!}`).

See [the guide on documenting an integration](../documentation/integrations.md)
for further details, including how to easily create the example
screenshot for the documentation page.

## Step 7: Prepare a pull request

When you have finished your incoming webhook integration, follow these
guidelines before pushing the code to your Zulip fork and submitting a
pull request to [zulip/zulip](https://github.com/zulip/zulip):

- Run tests, including linters, to ensure you have addressed any issues
  they report. See [testing](../testing/testing.md) and
  [linters](../testing/linters.md) for details.
- Read through [code styles and conventions](../contributing/code-style.md)
  and review your code to double-check that you've followed Zulip's
  guidelines.
- Take a look at your Git history to ensure your commits have been clear
  and logical (see [commit discipline](../contributing/commit-discipline.md)
  for tips). If not, consider revising them with `git rebase --interactive`.
  For most incoming webhook integrations, you'll want to submit a pull
  request with a single commit that has a good, clear commit message.

If you would like feedback on your integration as you go, feel free to
post a message in the [Zulip development community][czo-integrations-channel]
You can also create a [draft pull request][github-draft-pull-requests]
while you are still working on your integration. See the [git
guide](../git/pull-requests.md#create-a-pull-request) for more on Zulip's
pull request process.

[czo-integrations-channel]: https://chat.zulip.org/#narrow/channel/integrations
[github-draft-pull-requests]: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests#draft-pull-requests

## Advanced topics

More complex implementation or testing needs may require additional code,
beyond what the standard helper functions provide. This section discusses
some of these situations.

### Negative tests

A negative test is one that should result in an error, such as incorrect
data from the third-party's payload or headers. To correctly test these
cases, you must explicitly code your test's execution (using other test
helpers, as needed) rather than calling the usual `check_webhook` test
helper function.

Here is an example from the WordPress integration:

```python
def test_unknown_action_no_data(self) -> None:
    # Mimic check_webhook() to manually execute a negative test.
    # Otherwise its call to send_webhook_payload() would assert on the non-success
    # we are testing. The value of result is the error message the webhook should
    # return if no params are sent. The fixture for this test is an empty file.

    # subscribe to the target channel
    self.subscribe(self.test_user, self.channel_name)

    # post to the webhook url
    post_params = {'stream_name': self.channel_name,
                   'content_type': 'application/x-www-form-urlencoded'}
    result = self.client_post(self.url, 'unknown_action', **post_params)

    # check that we got the expected error message
    self.assert_json_error(result, "Unknown WordPress webhook action: WordPress action")
```

In a normal test, `check_webhook` would handle all the setup and then
check that the incoming webhook's response matches the expected success
result. If the webhook returns an error, the test fails. Instead, you can
explicitly do the test setup it would have done, and check the error
result yourself.

Here, `subscribe` is a test helper that uses `test_user` and `channel_name`
(attributes from the base class) to register the user to receive messages
in the given channel. If the channel doesn't exist, it creates it.

`client_post`, another helper function, performs the HTTP POST that calls
the incoming webhook. As long as `self.url` is correct, you don't need to
construct the webhook URL yourself. (In most cases, it is.)

`assert_json_error` then checks if the result matches the expected error.
If you had used `check_webhook`, it would have called
`send_webhook_payload`, which checks the result with `assert_json_success`.

### Handling unexpected webhook event types

Many third-party services have dozens of different event types. In some
cases, we may choose to explicitly ignore specific events. In other cases,
there may be events that are new or events that we don't know about. In
such cases, we recommend raising `UnsupportedWebhookEventTypeError`
(found in `zerver/lib/exceptions.py`), with a string describing the
unsupported event type, like so:

```
raise UnsupportedWebhookEventTypeError(event_type)
```
