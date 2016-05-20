# Writing a new integration

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

### Files that need to be updated

* `templates/zerver/integrations.html`: Edit to add end-user documentation and
  integration icon. See [Documenting your
  integration](#documenting-your-integration) for details.
* `zerver/test_hooks.py`: Edit to include tests for your webbook. See [Testing
  and writing tests](testing.html) for details.
* `zproject/urls.py`: Edit to add externally available url of the webhook and
  associate with the function added to `zerver/views/webhooks/mywebhook.py`

### Files that need to be created

Select a name for your webhook and use it consistently. The examples below are
for a webhook named 'mywebhook'.

* `static/images/integrations/logos/mywebhook.png`: An image to represent
  your integration in the user interface. Generally this Should be the logo of the
  platform/server/product you are integrating. See [Documenting your
  integration](#documenting-your-integration) for details.
* `static/images/integrations/mywebbook/001.png`: A screen capture of your
  integration for use in the user interface. You can add as many images as needed
  to effectively document your webhook integration. See [Documenting your
  integration](#documenting-your-integration) for details.
* `zerver/fixtures/mywebhook/mywebhook_build.json`: Sample json payload data
  used by tests. Can add multiple files. See [Testing and writing
  tests](testing.html) for details.
* `zerver/views/webhooks/mywebhook.py`: Includes the main webhook integration
  function including any needed helper functions.

### Walkthrough of `Hello World` webhook

Below explains each part of a simple webhook integration, called **Hello
World**. This webhook sends a "hello" message to the `test` stream and includes
a link to the Wikipedia article of the day, which it formats from json data it
receives in the http request.

Use this walkthrough to learn how to write your first webhook
integration.

#### Step 1: Main webhook code

The majority of the code for your webhook integration will be in a single
python file in `zerver/views/webhooks/`. The Hello World integration is in
`zerver/views/webhooks/helloworld.py`.

```
from __future__ import absolute_import
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view

@api_key_only_webhook_view('HelloWorld')
@has_request_variables
def api_helloworld_webhook(request, user_profile, client,
        payload=REQ(argument_type='body'), stream=REQ(default='test'),
        topic=REQ(default='Hello World')):

  # construct the body of the message
  body = ('Hello! I am happy to be here! :smile: ')

  # add a wikipedia link if there is one in the payload
  if ('type' in payload and payload['type'] == 'wikipedia'):
      body += '\nThe Wikipedia featured article for today is **[%s](%s)**' % (payload['featured_title'], payload['featured_url'])

  # send the message
  check_send_message(user_profile, client, 'stream', [stream], topic, body)

  # return json result
  return json_success()

```

The above code imports the required functions, defines the main webhook
function, decorating it `api_hey_only_webhook_view` and
`has_request_variables`.

You must pass the name of your webhook to the `api_key_only_webhook_view`
decorator. Here we have used `HelloWorld`.

You may name your webhook function whatever you like, though it's a good idea
to be consistent with other webhook integrations. We recommend following the
format `api_webhookname_webhook`.

At minimum, the webhook function must accept `request`, `user_profile`, and
`client`. You may also want to define additional parameters using the `REQ`
object.

In the example above, we have defined `payload` which is populated from the
body of the http request, `stream` with a default of `test` (available by
default in Zulip dev environment), and `topic` with a default of `Hello World`.

In the body of the function we define the body of the message as `Hello! I am
happy to be here! :smile: `. The `:smile:` indicates an emoji. Then we append a
link to the Wikipedia article of the day as provided by the json payload.

Then we send a public (stream) message with `check_send_message`.  Finally, we
return `json_success()`.

#### Step 2: Create an api endpoint for the webhook

In order for a webhook to be externally available, it must be mapped to a url.
This is done in `zproject/urls.py`. Look for the lines:

```
# Incoming webhook URLs
urls += [
    # Sorted integration-specific webhook callbacks.
```

And you'll find the entry for Hello World:

```
url(r'^api/v1/external/helloworld$',  'zerver.views.webhooks.helloworld.api_helloworld_webhook'),
```

This tells the Zulip api to call the `api_helloworld_webhook` function in
`zerver/views/webhooks/helloworld.py` when it receives a request at
`/api/v1/external/helloworld`.

At this point, if you're following along and/or writing your own Hello World
webhook, you have written enough code to test your integration.  You can do so
by using curl on the command line:

```
curl -X POST -H "Content-Type: application/json" -d '{ "type":"wikipedia", "day":"Wed, 6/1", "featured_title":"Marilyn Monroe", "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe" }' http://localhost:9991/api/v1/external/helloworld\?api_key\=<api_key>
```

After which you should see:
```
{"msg":"","result":"success"}
```

And a message in Zulip. TODO: add screen shot.

#### Step 3: Create tests and fixtures

Every webhook integraton should have a corresponding test class in
`zerver/tests/test_hooks.py`.

You should name the class <WebhookName>HookTests and this class should accept
`WebhookTestCase`. For our HelloWorld webhook, we name the test class
`HelloWorldHookTests`:

```
class HelloWorldHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/helloworld?&api_key={api_key}"
    FIXTURE_DIR_NAME = 'hello'

    def test_hello_message(self):
        expected_subject = u"Hello World";
        expected_message = u"Hello! I am happy to be here! :smile: \nThe Wikipedia featured article for today is **[Marilyn Monroe](https://en.wikipedia.org/wiki/Marilyn_Monroe)**";
        self.send_and_test_stream_message('hello', expected_subject, expected_message,content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name):
        return self.fixture_data("helloworld", fixture_name, file_type="json")

```

And to simulate the post data of a real request, we add the fixture `zerver/fixtures/helloworld/hello_world.json` with this data:

```
{
  "type":"wikipedia",
  "day":"Wed, 6/1",
  "featured_title":"Marilyn Monroe",
  "featured_url":"https://en.wikipedia.org/wiki/Marilyn_Monroe",
}
```

Now you can run these tests from within the Zulip dev environment with this
command:

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

#### Step 4: Create documentation

Next, we add end-user documentation for our webhook integration to
`templates/zerver/integrations.html`.

First, add a `div` that displays the logo of your integration and a link to its
documentation:

```
 <div class="integration-lozenge integration-helloworld">
   <a class="integration-link integration-helloworld" href="#helloworld">
      <img class="integration-logo" src="/static/images/integrations/logos/helloworld.png" alt="Hello World logo" />
      <span class="integration-label">Hello World</span>
   </a>
 </div>
```

And second, a div with the usage instructions:

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

    <p><b>Congratulations! You're done!</b><br /> Your messages may look like:</p>

    <img class="screenshot" src="/static/images/integrations/helloworld/001.png" />
</div>
```

Both blocks should fall alphabetically so we add these two divs between the
blocks for Github and Hubot, respectively.

See [Documenting your integration](#documenting-your-integration) for further
details.

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
