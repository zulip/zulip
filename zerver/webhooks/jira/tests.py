from unittest.mock import patch
from urllib.parse import quote, unquote

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.users import get_api_key


class JiraHookTests(WebhookTestCase):
    CHANNEL_NAME = "jira"
    URL_TEMPLATE = "/api/v1/external/jira?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "jira"

    def test_custom_channel(self) -> None:
        api_key = get_api_key(self.test_user)
        self.subscribe(self.test_user, "jira_custom")
        url = f"/api/v1/external/jira?api_key={api_key}&stream=jira_custom"
        msg = self.send_webhook_payload(
            self.test_user,
            url,
            self.get_body("created_v2"),
            content_type="application/json",
        )
        expected_content = """
Leo Franchi created [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        self.assert_channel_message(
            message=msg,
            channel_name="jira_custom",
            topic_name="BUG-15: New bug with hook",
            content=expected_content,
        )

    def test_created(self) -> None:
        expected_topic_name = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi created [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        self.check_webhook("created_v1", expected_topic_name, expected_message)
        self.check_webhook("created_v2", expected_topic_name, expected_message)

    def test_ignored_events(self) -> None:
        ignored_actions = [
            "attachment_created",
            "issuelink_created",
            "issuelink_deleted",
            "jira:version_released",
            "jira:worklog_updated",
            "sprint_closed",
            "sprint_started",
            "worklog_created",
            "worklog_updated",
        ]
        for action in ignored_actions:
            url = self.build_webhook_url()
            payload = dict(webhookEvent=action)
            with patch("zerver.webhooks.jira.view.check_send_webhook_message") as m:
                result = self.client_post(url, payload, content_type="application/json")
            self.assertFalse(m.called)
            self.assert_json_success(result)

    def test_created_with_channel_with_spaces_escaped(self) -> None:
        self.CHANNEL_NAME = quote("jira alerts")
        self.url = self.build_webhook_url()
        self.subscribe(self.test_user, unquote(self.CHANNEL_NAME))

        payload = self.get_body("created_v1")
        result = self.client_post(self.url, payload, content_type="application/json")

        self.assert_json_success(result)

        expected_topic_name = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi created [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        msg = self.get_last_message()
        self.assertEqual(msg.content, expected_message)
        self.assertEqual(msg.topic_name(), expected_topic_name)

    def test_created_with_channel_with_spaces_double_escaped(self) -> None:
        self.CHANNEL_NAME = quote(quote("jira alerts"))
        self.url = self.build_webhook_url()
        self.subscribe(self.test_user, unquote(unquote(self.CHANNEL_NAME)))

        payload = self.get_body("created_v1")
        result = self.client_post(self.url, payload, content_type="application/json")

        self.assert_json_success(result)

        expected_topic_name = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi created [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        msg = self.get_last_message()
        self.assertEqual(msg.content, expected_message)
        self.assertEqual(msg.topic_name(), expected_topic_name)

    def test_created_with_topic_with_spaces_double_escaped(self) -> None:
        self.url = self.build_webhook_url(topic=quote(quote("alerts test")))
        expected_topic_name = "alerts test"
        expected_message = """
Leo Franchi created [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        self.check_webhook("created_v1", expected_topic_name, expected_message)

    def test_created_with_unicode(self) -> None:
        expected_topic_name = "BUG-15: New bug with à hook"
        expected_message = """
Leo Franchià created [BUG-15: New bug with à hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        self.check_webhook("created_with_unicode_v1", expected_topic_name, expected_message)
        self.check_webhook("created_with_unicode_v2", expected_topic_name, expected_message)

    def test_created_assignee(self) -> None:
        expected_topic_name = "TEST-4: Test Created Assignee"
        expected_message = """
Leonardo Franchi [Administrator] created [TEST-4: Test Created Assignee](https://zulipp.atlassian.net/browse/TEST-4):

* **Priority**: Major
* **Assignee**: Leonardo Franchi [Administrator]
""".strip()
        self.check_webhook("created_assignee_v1", expected_topic_name, expected_message)
        self.check_webhook("created_assignee_v2", expected_topic_name, expected_message)

    def test_commented(self) -> None:
        expected_topic_name = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi commented on [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):

``` quote
Adding a comment. Oh, what a comment it is!
```
""".strip()
        self.check_webhook("commented_v1", expected_topic_name, expected_message)
        self.check_webhook("commented_v2", expected_topic_name, expected_message)

    def test_commented_with_two_full_links(self) -> None:
        expected_topic_name = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi commented on [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):

``` quote
This is the [first link](https://google.com) and this is the [second link](https://google.com) and this is the end.
```
""".strip()
        self.check_webhook(
            "commented_v2_with_two_full_links", expected_topic_name, expected_message
        )

    def test_comment_edited(self) -> None:
        expected_topic_name = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi edited a comment on [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):

``` quote
Adding a comment. Oh, what a comment it is!
```
""".strip()
        self.check_webhook("comment_edited_v2", expected_topic_name, expected_message)

    def test_comment_deleted(self) -> None:
        expected_topic_name = "TOM-1: New Issue"
        expected_message = "Tomasz Kolek deleted a comment from [TOM-1: New Issue](https://zuliptomek.atlassian.net/browse/TOM-1) (assigned to **kolaszek@go2.pl**)."
        self.check_webhook("comment_deleted_v2", expected_topic_name, expected_message)

    def test_commented_markup(self) -> None:
        expected_topic_name = "TEST-7: Testing of rich text"
        expected_message = """Leonardo Franchi [Administrator] commented on [TEST-7: Testing of rich text](https://zulipp.atlassian.net/browse/TEST-7):\n\n``` quote\nThis is a comment that likes to **exercise** a lot of _different_ `conventions` that `jira uses`.\r\n\r\n~~~\n\r\nthis code is not highlighted, but monospaced\r\n\n~~~\r\n\r\n~~~\n\r\ndef python():\r\n    print "likes to be formatted"\r\n\n~~~\r\n\r\n[http://www.google.com](http://www.google.com) is a bare link, and [Google](http://www.google.com) is given a title.\r\n\r\nThanks!\r\n\r\n~~~ quote\n\r\nSomeone said somewhere\r\n\n~~~\n```"""

        self.check_webhook("commented_markup_v1", expected_topic_name, expected_message)
        self.check_webhook("commented_markup_v2", expected_topic_name, expected_message)

    def test_deleted(self) -> None:
        expected_topic_name = "BUG-15: New bug with hook"
        expected_message = "Leo Franchi deleted [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15)."
        self.check_webhook("deleted_v1", expected_topic_name, expected_message)
        self.check_webhook("deleted_v2", expected_topic_name, expected_message)

    def test_reassigned(self) -> None:
        expected_topic_name = "BUG-15: New bug with hook"
        expected_message = """Leo Franchi updated [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):

* Changed assignee to **Othello, the Moor of Venice**"""
        self.check_webhook("reassigned_v1", expected_topic_name, expected_message)
        self.check_webhook("reassigned_v2", expected_topic_name, expected_message)

    def test_priority_updated(self) -> None:
        expected_topic_name = "TEST-1: Fix That"
        expected_message = """Leonardo Franchi [Administrator] updated [TEST-1: Fix That](https://zulipp.atlassian.net/browse/TEST-1) (assigned to **leo@zulip.com**):

* Changed priority from **Critical** to **Major**"""
        self.check_webhook("updated_priority_v1", expected_topic_name, expected_message)
        self.check_webhook("updated_priority_v2", expected_topic_name, expected_message)

    def test_status_changed(self) -> None:
        expected_topic_name = "TEST-1: Fix That"
        expected_message = """Leonardo Franchi [Administrator] updated [TEST-1: Fix That](https://zulipp.atlassian.net/browse/TEST-1):

* Changed status from **To Do** to **In Progress**"""
        self.check_webhook("change_status_v1", expected_topic_name, expected_message)
        self.check_webhook("change_status_v2", expected_topic_name, expected_message)

    def test_comment_event_comment_created(self) -> None:
        expected_topic_name = "SP-1: Add support for newer format Jira issue comment events"
        expected_message = """Hemanth V. Alluri commented on issue: *"Add support for newer format Jira issue comment events"*\n``` quote\nSounds like it’s pretty important. I’ll get this fixed ASAP!\n```"""
        self.check_webhook("comment_created", expected_topic_name, expected_message)

    def test_comment_event_comment_created_no_issue_details(self) -> None:
        expected_topic_name = "10000: Upgrade Jira to get the issue title here."
        expected_message = """Hemanth V. Alluri commented on issue: *"Upgrade Jira to get the issue title here."*\n``` quote\nSounds like it’s pretty important. I’ll get this fixed ASAP!\n```"""
        self.check_webhook(
            "comment_created_no_issue_details", expected_topic_name, expected_message
        )

    def test_comment_event_comment_edited(self) -> None:
        expected_topic_name = "SP-1: Add support for newer format Jira issue comment events"
        expected_message = """Hemanth V. Alluri updated their comment on issue: *"Add support for newer format Jira issue comment events"*\n``` quote\nThis is a very important issue! I’m on it!\n```"""
        self.check_webhook("comment_updated", expected_topic_name, expected_message)

    def test_comment_event_comment_deleted(self) -> None:
        expected_topic_name = "SP-1: Add support for newer format Jira issue comment events"
        expected_message = """Hemanth V. Alluri deleted their comment on issue: *"Add support for newer format Jira issue comment events"*\n``` quote\n~~This is a very important issue! I’m on it!~~\n```"""
        self.check_webhook("comment_deleted", expected_topic_name, expected_message)

    def test_anomalous_webhook_payload_error(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                fixture_name="example_anomalous_payload",
                expected_topic="",
                expected_message="",
                expect_noop=True,
            )

        self.assertIn(
            "Unable to parse request: Did Jira generate this event?",
            e.exception.args[0],
        )
