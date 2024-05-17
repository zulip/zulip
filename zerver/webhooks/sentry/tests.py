from zerver.lib.test_classes import WebhookTestCase


class SentryHookTests(WebhookTestCase):
    CHANNEL_NAME = "sentry"
    URL_TEMPLATE = "/api/v1/external/sentry?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "sentry"

    def test_event_for_exception_golang(self) -> None:
        expected_topic_name = '*url.Error: Get "bad_url": unsupported protocol scheme ""'
        expected_message = """\
**New exception:** [*url.Error: Get "bad_url": unsupported protocol scheme ""](https://sentry.io/organizations/hypro999-personal-organization/issues/1637164584/events/80777a9cc30e4d0eb8904333d5c298b0/)
```quote
**level:** error
**timestamp:** 2020-04-29 11:23:45
**filename:** trigger-exception.go
```

Traceback:
```go
         // Set the timeout to the maximum duration the program can afford to wait.
         defer sentry.Flush(2 * time.Second)

         resp, err := http.Get(os.Args[1])
         if err != nil {
--->         sentry.CaptureException(err)
             log.Printf("reported to Sentry: %s", err)
             return
         }
         defer resp.Body.Close()

```"""
        self.check_webhook("event_for_exception_golang", expected_topic_name, expected_message)

    def test_event_for_exception_node(self) -> None:
        expected_topic_name = "Error: Sample error from node."
        expected_message = """\
**New exception:** [Error: Sample error from node.](https://sentry.io/organizations/hypro999-personal-organization/issues/1638852747/events/f9cb0f2afff74a5aa92e766fb7ac3fe3/)
```quote
**level:** error
**timestamp:** 2020-04-30 06:19:33
**filename:** /home/hemanth/Desktop/sentry/trigger-exception.js
```

Traceback:
```javascript
       dsn: 'https://redacted.ingest.sentry.io/5216640',
     });

     Sentry.withScope(function(scope) {
       scope.addEventProcessor(function(event, hint) {
         return event;
       });
--->   Sentry.captureException(new Error('Sample error from node.'));
     });


```"""
        self.check_webhook("event_for_exception_node", expected_topic_name, expected_message)

    def test_event_for_exception_python(self) -> None:
        expected_topic_name = "Exception: Custom exception!"
        expected_message = """\
**New exception:** [Exception: Custom exception!](https://sentry.io/organizations/hypro999-personal-organization/issues/1635244907/events/599349254a1447a99774b5310711c1a8/)
```quote
**level:** error
**timestamp:** 2020-04-28 13:56:05
**filename:** trigger-exception.py
```

Traceback:
```python3


     if __name__ == "__main__":
         sentry_sdk.init(dsn=SECRET_DSN)
         try:
--->         raise Exception("Custom exception!")
         except Exception as e:
             sentry_sdk.capture_exception(e)

```"""
        self.check_webhook("event_for_exception_python", expected_topic_name, expected_message)

    def test_event_for_exception_rails(self) -> None:
        expected_topic_name = "ZeroDivisionError: divided by 0"
        expected_message = """\
**New exception:** [ZeroDivisionError: divided by 0](https://sentry.io/organizations/nitk-46/issues/4213933362/events/49b528e13e45497ab9adc3173fd2ed34/)
```quote
**level:** error
**timestamp:** 2023-05-29 10:12:33
**filename:** app/controllers/articles_controller.rb
```

Traceback:
```ruby
     class ArticlesController < ApplicationController

       def index

         begin

--->       132312 / 0

         rescue ZeroDivisionError => exception

           Sentry.capture_exception(exception)

         end

```"""
        self.check_webhook("event_for_exception_rails", expected_topic_name, expected_message)

    def test_event_for_exception_vue(self) -> None:
        expected_topic_name = "TypeError: Cannot read properties of null (reading 'inser..."
        expected_message = """\
**New exception:** [TypeError: Cannot read properties of null (reading 'insertBefore')](https://sentry.io/organizations/nitk-46/issues/4214010673/events/292f78454e774e62999506f759ad791d/)
```quote
**level:** error
**timestamp:** 2023-05-29 11:08:30
**filename:** /node_modules/.vite/deps/chunk-G4DFXOZZ.js
```"""
        self.check_webhook("event_for_exception_vue", expected_topic_name, expected_message)

    def test_webhook_event_for_exception_python(self) -> None:
        expected_topic_name = "ValueError: new sentry error."
        expected_message = """\
**New exception:** [ValueError: new sentry error.](https://sentry.io/organizations/bar-foundation/issues/1972208801/events/c916dccfd58e41dcabaebef0091f0736/)
```quote
**level:** error
**timestamp:** 2020-10-21 23:25:11
**filename:** trigger-exception.py
```

Traceback:
```python3


     if __name__ == "__main__":
         sentry_sdk.init(dsn=DSN_SECRET)
         try:
--->         raise ValueError("new sentry error.")
         except Exception as e:
             sentry_sdk.capture_exception(e)
```"""
        self.check_webhook(
            "webhook_event_for_exception_python", expected_topic_name, expected_message
        )

    def test_webhook_event_for_exception_javascript(self) -> None:
        expected_topic_name = 'TypeError: can\'t access property "bar", x.foo is undefined'
        expected_message = """\
**New exception:** [TypeError: can't access property "bar", x.foo is undefined](https://sentry.io/organizations/foo-bar-org/issues/1982047746/events/f3bf5fc4e354451db9e885a69b2a2b51/)
```quote
**level:** error
**timestamp:** 2020-10-26 16:39:54
**filename:** None
```"""
        self.check_webhook(
            "webhook_event_for_exception_javascript", expected_topic_name, expected_message
        )

    def test_event_for_exception_js(self) -> None:
        expected_topic_name = "Error: Something external broke."
        expected_message = """\
**New exception:** [Error: Something external broke.](https://sentry.io/organizations/hypro999-personal-organization/issues/1731239773/events/355c3b2a142046629dd410db2fdda003/)
```quote
**level:** error
**timestamp:** 2020-06-17 14:42:54
**filename:** /mnt/data/Documents/Stuff%20for%20Zulip/Repos/sentry/js/external.js
```"""
        self.check_webhook("event_for_exception_js", expected_topic_name, expected_message)

    def test_event_for_message_golang(self) -> None:
        expected_topic_name = "A test message event from golang."
        expected_message = """\
**New message event:** [A test message event from golang.](https://sentry.io/organizations/hypro999-personal-organization/issues/1638844654/events/01ecb45633bc4f5ca940ada671124c8f/)
```quote
**level:** info
**timestamp:** 2020-04-30 06:14:13
```"""
        self.check_webhook("event_for_message_golang", expected_topic_name, expected_message)

    def test_event_for_message_node(self) -> None:
        expected_topic_name = "Test event from node."
        expected_message = """\
**New message event:** [Test event from node.](https://sentry.io/organizations/hypro999-personal-organization/issues/1638840427/events/6886bb1fe7ce4497b7836f6083d5fd34/)
```quote
**level:** info
**timestamp:** 2020-04-30 06:09:56
```"""
        self.check_webhook("event_for_message_node", expected_topic_name, expected_message)

    def test_event_for_message_python(self) -> None:
        expected_topic_name = "A simple message-based issue."
        expected_message = """\
**New message event:** [A simple message-based issue.](https://sentry.io/organizations/hypro999-personal-organization/issues/1635261062/events/8da63b42375e4d3b803c377fefb062f8/)
```quote
**level:** info
**timestamp:** 2020-04-28 14:05:04
```"""
        self.check_webhook("event_for_message_python", expected_topic_name, expected_message)

    def test_issue_assigned_to_individual(self) -> None:
        expected_topic_name = "A test message event from golang."
        expected_message = """Issue **A test message event from golang.** has now been assigned to **Hemanth V. Alluri** by **Hemanth V. Alluri**."""
        self.check_webhook("issue_assigned_to_individual", expected_topic_name, expected_message)

    def test_issue_assigned_to_team(self) -> None:
        expected_topic_name = "Exception: program has entered an invalid state."
        expected_message = """Issue **Exception: program has entered an invalid state.** has now been assigned to **team lone-wolf** by **Hemanth V. Alluri**."""
        self.check_webhook("issue_assigned_to_team", expected_topic_name, expected_message)

    def test_issue_created_for_exception(self) -> None:
        expected_topic_name = "Exception: Custom exception!"
        expected_message = """\
**New issue created:** Exception: Custom exception!
```quote
**level:** error
**timestamp:** 2020-04-28 13:56:05
**assignee:** No one
```"""
        self.check_webhook("issue_created_for_exception", expected_topic_name, expected_message)

    def test_issue_created_for_message(self) -> None:
        expected_topic_name = "A simple message-based issue."
        expected_message = """\
**New issue created:** A simple message-based issue.
```quote
**level:** info
**timestamp:** 2020-04-28 14:05:04
**assignee:** No one
```"""
        self.check_webhook("issue_created_for_message", expected_topic_name, expected_message)

    def test_issue_ignored(self) -> None:
        expected_topic_name = "Exception: program has entered an invalid state."
        expected_message = """Issue **Exception: program has entered an invalid state.** was ignored by **Hemanth V. Alluri**."""
        self.check_webhook("issue_ignored", expected_topic_name, expected_message)

    def test_issue_resolved(self) -> None:
        expected_topic_name = "Exception: program has entered an invalid state."
        expected_message = """Issue **Exception: program has entered an invalid state.** was marked as resolved by **Hemanth V. Alluri**."""
        self.check_webhook("issue_resolved", expected_topic_name, expected_message)

    def test_deprecated_exception_message(self) -> None:
        expected_topic_name = "zulip"
        expected_message = """\
New [issue](https://sentry.io/zulip/zulip/issues/156699934/) (level: ERROR):

``` quote
This is an example python exception
```"""
        self.check_webhook("deprecated_exception_message", expected_topic_name, expected_message)

    def test_sample_event_through_alert(self) -> None:
        expected_topic_name = "This is an example Python exception"
        expected_message = """\
**New message event:** [This is an example Python exception](https://sentry.io/organizations/nitk-46/issues/4218258981/events/b6eff1a49b1f4132850b1238d968da70/)
```quote
**level:** error
**timestamp:** 2023-05-31 11:06:16
```"""
        self.check_webhook("sample_event_through_alert", expected_topic_name, expected_message)

    def test_sample_event_through_plugin(self) -> None:
        expected_topic_name = "This is an example Python exception"
        expected_message = """\
**New message event:** [This is an example Python exception](https://nitk-46.sentry.io/issues/4218258981/events/4dc4fc2858aa450eb658be9e5b8ad149/)
```quote
**level:** error
**timestamp:** 2023-07-09 20:41:24
```"""
        self.check_webhook("sample_event_through_plugin", expected_topic_name, expected_message)

    def test_raven_sdk_python_event(self) -> None:
        payload = self.get_body("raven_sdk_python_event")
        result = self.client_post(
            self.url,
            payload,
            content_type="application/json",
        )
        self.assert_json_success(result)
        self.assert_in_response(
            "The 'Raven SDK' event isn't currently supported by the Sentry webhook; ignoring",
            result,
        )
