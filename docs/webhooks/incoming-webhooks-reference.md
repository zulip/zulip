# Incoming webhooks reference

This guide provides a detailed reference for developing and configuring
Zulip incoming webhook integrations. For step-by-step guidance, read the
[incoming webhooks walkthrough](incoming-webhooks-walkthrough), before using
this reference guide.

## Custom HTTP headers

Some third-party outgoing webhook APIs, such as GitHub's, don't encode
all of the information about an event in the HTTP request body. Instead,
they put key details like the event type in a separate HTTP header.
Generally, this is clear in the third-party's API documentation that
you will be referencing when creating fixtures.

In order to test Zulip's handling of this data, you will need to record
which HTTP headers are used with each fixture you capture. Since this is
integration-dependent, Zulip offers a simple API for doing this, which is
probably best explained by looking at `default_fixture_to_headers` and
`get_event_header` from `zerver/lib/webhooks/common.py`, and then seeing
how they are used in Zulip's GitHub integration code:
`zerver/webhooks/github/view.py`.

### Custom HTTP event-type headers

Some third-party services set a custom HTTP header to indicate the event
type that generates a particular payload. To extract such headers, we
recommend using the `get_event_header` function in `zerver/lib/webhooks/common.py`,
like so:

```python
event = get_event_header(request, header, integration_name)
```

`request` is the `HttpRequest` object passed to your main webhook
function. `header` is the name of the custom header you'd like to extract,
such as `X-Event-Key`. And `integration_name` is the name of the
third-party service in question, such as `GitHub`.

Because such headers are how some integrations indicate the event types
of their outgoing webhook payloads, the absence of such a header usually
indicates a configuration issue, where one either entered the URL for a
different integration, or happens to be running an older version of the
integration that doesn't set that header.

If the requisite header is missing, this function sends a direct message
to the owner of the webhook bot, notifying them of the missing header.

## Custom URL query parameters

### Registering webhooks requiring custom configuration

In cases where an incoming webhook integration supports optional URL
parameters, one can use the `url_options` feature. It's a field in the
`IncomingWebhookIntegration` class that is used when [generating an
integration URL](https://zulip.com/help/generate-integration-url) (for a
bot) in the web and desktop apps, which encodes the user input for each
parameter in the integration URL.

These URL options can be declared as follows:

```python
    IncomingWebhookIntegration(
        'helloworld',
        ...
        url_options=[
          WebhookUrlOption(
            name='ignore_private_repositories',
            label='Exclude notifications from private repositories',
            validator=check_string
          ),
        ],
    )
```

`url_options` is a list describing the parameters the web app UI should
offer when generating the integration URL:

- `name`: The parameter name that is used to encode the user input in the
  integration's webhook URL.
- `label`: A short descriptive label for this URL parameter in the web
  app UI.
- `validator`: A validator function, which is used to determine the input
  type for this option in the UI, and to indicate how to validate the
  input. Currently, the web app UI only supports these validators:
  - `check_bool` for checkbox/select input.
  - `check_string` for text input.

To add support for other validators, you can update
`web/src/integration_url_modal.ts`. Common validators are available in
`zerver/lib/validator.py`.

In rare cases, it may be necessary for an incoming webhook to require
additional user configuration beyond what is specified in the POST URL.
A typical use case for this would be APIs that require clients to do a
callback to get details beyond an opaque object ID that one would want to
include in a Zulip notification message. The `config_options` field in
the `IncomingWebhookIntegration` class is reserved for this use case.

### WebhookUrlOption presets

The `build_preset_config` method creates `WebhookUrlOption` objects with
pre-configured fields. These preset URL options primarily serve two
purposes:

- To construct common `WebhookUrlOption` objects that are used in various
  incoming webhook integrations.

- To construct `WebhookUrlOption` objects with special UI in the web app
  for [generating incoming webhook URLs](https://zulip.com/help/generate-integration-url).

For other purposes, you can use the `WebhookUrlOption` class directly.

Using a preset URL option with the `build_preset_config` method:

```python
# zerver/lib/integrations.py
from zerver.lib.webhooks.common import PresetUrlOption, WebhookUrlOption
  # -- snip --
    IncomingWebhookIntegration(
        "github",
        # -- snip --
        url_options=[
            WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES),
        ],
    ),
```

The currently configured preset URL options are:

- **`BRANCHES`**: This preset is intended to be used for [version control
  integrations](https://zulip.com/integrations/category/version-control),
  and adds UI for the user to configure which branches of a project's
  repository will trigger Zulip notification messages. When the user
  specifies which branches to receive notifications from, the `branches`
  parameter will be added to the [generated integration
  URL](https://zulip.com/help/generate-integration-url). For example, if
  the user input `main` and `dev` for the branches of their repository,
  then `&branches=main%2Cdev` would be appended to the generated URL.

- **`IGNORE_PRIVATE_REPOSITORIES`**: This preset is intended to be used for
  [version control integrations](https://zulip.com/integrations/category/version-control),
  and adds UI for the user to exclude private repositories from triggering
  Zulip notification messages. When the user selects this option, the
  `ignore_private_repositories` boolean parameter will be added to the
  [generated integration URL](https://zulip.com/help/generate-integration-url).

- **`CHANNEL_MAPPING`**: This preset is intended to be used for [chat-app
  integrations](https://zulip.com/integrations/category/communication)
  (like Slack), and adds a special option, **Matching Zulip channel**, to
  the web app UI for where to send Zulip notification messages. This
  special option maps the notification messages to Zulip channels that
  match the messages' original channel name in the third-party service.
  When selected, this requires setting a single topic for notification
  messages, and adds `&mapping=channels` to the [generated integration
  URL](https://zulip.com/help/generate-integration-url).

### Writing tests for custom URL query parameters

Custom arguments passed in URL query parameters work as expected in the
webhook code, but require special handling in tests.

For example, here is the definition of a webhook function that gets both
`stream` and `topic` from the query parameters:

```python
@typed_endpoint
def api_querytest_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Annotated[str, ApiParamConfig(argument_type_is_body=True)],
                          stream: str = "test",
                          topic: str= "Default Alert":
```

In actual use, you might configure the third-party service to call your
Zulip incoming webhook integration with a URL like this:

```
http://myhost/api/v1/external/querytest?api_key=abcdefgh&stream=alerts&topic=queries
```

It provides values for `stream` and `topic`, and the integration can get
those using `@typed_endpoint` without any special handling. How does this
work in a test?

The new attribute `TOPIC` exists only in our class so far. In order to
construct a URL with a query parameter for `topic`, you can pass the
attribute `TOPIC` as a keyword argument to `build_webhook_url`, like so:

```python
class QuerytestHookTests(WebhookTestCase):

    TOPIC = "Default topic"
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
