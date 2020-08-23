from zerver.lib.test_classes import WebhookTestCase


class SentryHookTests(WebhookTestCase):
    STREAM_NAME = 'sentry'
    URL_TEMPLATE = "/api/v1/external/sentry?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'sentry'

    def test_event_for_exception_golang(self) -> None:
        expected_topic = '*url.Error: Get "bad_url": unsupported protocol scheme ""'
        expected_message = """
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
        self.check_webhook("event_for_exception_golang", expected_topic, expected_message)

    def test_event_for_exception_node(self) -> None:
        expected_topic = "Error: Sample error from node."
        expected_message = """
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
        self.check_webhook("event_for_exception_node", expected_topic, expected_message)

    def test_event_for_exception_python(self) -> None:
        expected_topic = "Exception: Custom exception!"
        expected_message = """
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
        self.check_webhook("event_for_exception_python", expected_topic, expected_message)

    def test_event_for_message_golang(self) -> None:
        expected_topic = "A test message event from golang."
        expected_message = """
**New message event:** [A test message event from golang.](https://sentry.io/organizations/hypro999-personal-organization/issues/1638844654/events/01ecb45633bc4f5ca940ada671124c8f/)
```quote
**level:** info
**timestamp:** 2020-04-30 06:14:13
```"""
        self.check_webhook("event_for_message_golang", expected_topic, expected_message)

    def test_event_for_message_node(self) -> None:
        expected_topic = "Test event from node."
        expected_message = """
**New message event:** [Test event from node.](https://sentry.io/organizations/hypro999-personal-organization/issues/1638840427/events/6886bb1fe7ce4497b7836f6083d5fd34/)
```quote
**level:** info
**timestamp:** 2020-04-30 06:09:56
```"""
        self.check_webhook("event_for_message_node", expected_topic, expected_message)

    def test_event_for_message_python(self) -> None:
        expected_topic = "A simple message-based issue."
        expected_message = """
**New message event:** [A simple message-based issue.](https://sentry.io/organizations/hypro999-personal-organization/issues/1635261062/events/8da63b42375e4d3b803c377fefb062f8/)
```quote
**level:** info
**timestamp:** 2020-04-28 14:05:04
```"""
        self.check_webhook("event_for_message_python", expected_topic, expected_message)

    def test_issue_assigned_to_individual(self) -> None:
        expected_topic = "A test message event from golang."
        expected_message = """\nIssue **A test message event from golang.** has now been assigned to **Hemanth V. Alluri** by **Hemanth V. Alluri**."""
        self.check_webhook("issue_assigned_to_individual", expected_topic, expected_message)

    def test_issue_assigned_to_team(self) -> None:
        expected_topic = "Exception: program has entered an invalid state."
        expected_message = """\nIssue **Exception: program has entered an invalid state.** has now been assigned to **team lone-wolf** by **Hemanth V. Alluri**."""
        self.check_webhook("issue_assigned_to_team", expected_topic, expected_message)

    def test_issue_created_for_exception(self) -> None:
        expected_topic = "Exception: Custom exception!"
        expected_message = """
**New issue created:** Exception: Custom exception!
```quote
**level:** error
**timestamp:** 2020-04-28 13:56:05
**assignee:** No one
```"""
        self.check_webhook("issue_created_for_exception", expected_topic, expected_message)

    def test_issue_created_for_message(self) -> None:
        expected_topic = "A simple message-based issue."
        expected_message = """
**New issue created:** A simple message-based issue.
```quote
**level:** info
**timestamp:** 2020-04-28 14:05:04
**assignee:** No one
```"""
        self.check_webhook("issue_created_for_message", expected_topic, expected_message)

    def test_issue_ignored(self) -> None:
        expected_topic = "Exception: program has entered an invalid state."
        expected_message = """\nIssue **Exception: program has entered an invalid state.** was ignored by **Hemanth V. Alluri**."""
        self.check_webhook("issue_ignored", expected_topic, expected_message)

    def test_issue_resolved(self) -> None:
        expected_topic = "Exception: program has entered an invalid state."
        expected_message = """\nIssue **Exception: program has entered an invalid state.** was marked as resolved by **Hemanth V. Alluri**."""
        self.check_webhook("issue_resolved", expected_topic, expected_message)

    def test_deprecated_exception_message(self) -> None:
        expected_topic = "zulip"
        expected_message = """
New [issue](https://sentry.io/zulip/zulip/issues/156699934/) (level: ERROR):

``` quote
This is an example python exception
```"""
        self.check_webhook("deprecated_exception_message", expected_topic, expected_message)
