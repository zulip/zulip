# -*- coding: utf-8 -*-

from urllib.parse import quote, unquote

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.users import get_api_key

class JiraHookTests(WebhookTestCase):
    STREAM_NAME = 'jira'
    URL_TEMPLATE = u"/api/v1/external/jira?api_key={api_key}&stream={stream}"

    def test_custom_stream(self) -> None:
        api_key = get_api_key(self.test_user)
        url = "/api/v1/external/jira?api_key=%s&stream=jira_custom" % (api_key,)
        msg = self.send_json_payload(self.test_user,
                                     url,
                                     self.get_body('created_v2'),
                                     stream_name="jira_custom",
                                     content_type="application/json")
        self.assertEqual(msg.topic_name(), "BUG-15: New bug with hook")
        expected_message = """
Leo Franchi created [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        self.assertEqual(msg.content, expected_message)

    def test_created(self) -> None:
        expected_topic = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi created [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        self.send_and_test_stream_message('created_v1', expected_topic, expected_message)
        self.send_and_test_stream_message('created_v2', expected_topic, expected_message)

    def test_created_with_stream_with_spaces_escaped(self) -> None:
        self.STREAM_NAME = quote('jira alerts')
        self.url = self.build_webhook_url()
        self.subscribe(self.test_user, unquote(self.STREAM_NAME))

        payload = self.get_body('created_v1')
        result = self.client_post(self.url, payload, content_type='application/json')

        self.assert_json_success(result)

        expected_topic = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi created [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        msg = self.get_last_message()
        self.assertEqual(msg.content, expected_message)
        self.assertEqual(msg.topic_name(), expected_topic)

    def test_created_with_stream_with_spaces_double_escaped(self) -> None:
        self.STREAM_NAME = quote(quote('jira alerts'))
        self.url = self.build_webhook_url()
        self.subscribe(self.test_user, unquote(unquote(self.STREAM_NAME)))

        payload = self.get_body('created_v1')
        result = self.client_post(self.url, payload, content_type='application/json')

        self.assert_json_success(result)

        expected_topic = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi created [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        msg = self.get_last_message()
        self.assertEqual(msg.content, expected_message)
        self.assertEqual(msg.topic_name(), expected_topic)

    def test_created_with_topic_with_spaces_double_escaped(self) -> None:
        self.url = self.build_webhook_url(topic=quote(quote('alerts test')))
        expected_topic = "alerts test"
        expected_message = """
Leo Franchi created [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        self.send_and_test_stream_message('created_v1', expected_topic, expected_message)

    def test_created_with_unicode(self) -> None:
        expected_topic = u"BUG-15: New bug with à hook"
        expected_message = """
Leo Franchià created [BUG-15: New bug with à hook](http://lfranchi.com:8080/browse/BUG-15):

* **Priority**: Major
* **Assignee**: no one
""".strip()
        self.send_and_test_stream_message('created_with_unicode_v1', expected_topic, expected_message)
        self.send_and_test_stream_message('created_with_unicode_v2', expected_topic, expected_message)

    def test_created_assignee(self) -> None:
        expected_topic = "TEST-4: Test Created Assignee"
        expected_message = """
Leonardo Franchi [Administrator] created [TEST-4: Test Created Assignee](https://zulipp.atlassian.net/browse/TEST-4):

* **Priority**: Major
* **Assignee**: Leonardo Franchi [Administrator]
""".strip()
        self.send_and_test_stream_message('created_assignee_v1', expected_topic, expected_message)
        self.send_and_test_stream_message('created_assignee_v2', expected_topic, expected_message)

    def test_commented(self) -> None:
        expected_topic = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi commented on [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):

``` quote
Adding a comment. Oh, what a comment it is!
```
""".strip()
        self.send_and_test_stream_message('commented_v1', expected_topic, expected_message)
        self.send_and_test_stream_message('commented_v2', expected_topic, expected_message)

    def test_commented_with_two_full_links(self) -> None:
        expected_topic = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi commented on [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):

``` quote
This is the [first link](https://google.com) and this is the [second link](https://google.com) and this is the end.
```
""".strip()
        self.send_and_test_stream_message('commented_v2_with_two_full_links', expected_topic, expected_message)

    def test_comment_edited(self) -> None:
        expected_topic = "BUG-15: New bug with hook"
        expected_message = """
Leo Franchi edited a comment on [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):

``` quote
Adding a comment. Oh, what a comment it is!
```
""".strip()
        self.send_and_test_stream_message('comment_edited_v2', expected_topic, expected_message)

    def test_comment_deleted(self) -> None:
        expected_topic = "TOM-1: New Issue"
        expected_message = "Tomasz Kolek deleted a comment from [TOM-1: New Issue](https://zuliptomek.atlassian.net/browse/TOM-1) (assigned to **kolaszek@go2.pl**)."
        self.send_and_test_stream_message('comment_deleted_v2', expected_topic, expected_message)

    def test_commented_markup(self) -> None:
        expected_topic = "TEST-7: Testing of rich text"
        expected_message = """Leonardo Franchi [Administrator] commented on [TEST-7: Testing of rich text](https://zulipp.atlassian.net/browse/TEST-7):\n\n``` quote\nThis is a comment that likes to **exercise** a lot of _different_ `conventions` that `jira uses`.\r\n\r\n~~~\n\r\nthis code is not highlighted, but monospaced\r\n\n~~~\r\n\r\n~~~\n\r\ndef python():\r\n    print "likes to be formatted"\r\n\n~~~\r\n\r\n[http://www.google.com](http://www.google.com) is a bare link, and [Google](http://www.google.com) is given a title.\r\n\r\nThanks!\r\n\r\n~~~ quote\n\r\nSomeone said somewhere\r\n\n~~~\n```"""

        self.send_and_test_stream_message('commented_markup_v1', expected_topic, expected_message)
        self.send_and_test_stream_message('commented_markup_v2', expected_topic, expected_message)

    def test_deleted(self) -> None:
        expected_topic = "BUG-15: New bug with hook"
        expected_message = "Leo Franchi deleted [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15)."
        self.send_and_test_stream_message('deleted_v1', expected_topic, expected_message)
        self.send_and_test_stream_message('deleted_v2', expected_topic, expected_message)

    def test_reassigned(self) -> None:
        expected_topic = "BUG-15: New bug with hook"
        expected_message = """Leo Franchi updated [BUG-15: New bug with hook](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):

* Changed assignee to **Othello, the Moor of Venice**"""
        self.send_and_test_stream_message('reassigned_v1', expected_topic, expected_message)
        self.send_and_test_stream_message('reassigned_v2', expected_topic, expected_message)

    def test_priority_updated(self) -> None:
        expected_topic = "TEST-1: Fix That"
        expected_message = """Leonardo Franchi [Administrator] updated [TEST-1: Fix That](https://zulipp.atlassian.net/browse/TEST-1) (assigned to **leo@zulip.com**):

* Changed priority from **Critical** to **Major**"""
        self.send_and_test_stream_message('updated_priority_v1', expected_topic, expected_message)
        self.send_and_test_stream_message('updated_priority_v2', expected_topic, expected_message)

    def test_status_changed(self) -> None:
        expected_topic = "TEST-1: Fix That"
        expected_message = """Leonardo Franchi [Administrator] updated [TEST-1: Fix That](https://zulipp.atlassian.net/browse/TEST-1):

* Changed status from **To Do** to **In Progress**"""
        self.send_and_test_stream_message('change_status_v1', expected_topic, expected_message)
        self.send_and_test_stream_message('change_status_v2', expected_topic, expected_message)

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data('jira', fixture_name)

    def test_comment_event_comment_created(self) -> None:
        expected_topic = "SP-1: Add support for newer format Jira issue comment events"
        expected_message = """Hemanth V. Alluri commented on issue: *"Add support for newer format Jira issue comment events"*\n``` quote\nSounds like it’s pretty important. I’ll get this fixed ASAP!\n```"""
        self.send_and_test_stream_message("comment_created", expected_topic, expected_message)

    def test_comment_event_comment_edited(self) -> None:
        expected_topic = "SP-1: Add support for newer format Jira issue comment events"
        expected_message = """Hemanth V. Alluri updated their comment on issue: *"Add support for newer format Jira issue comment events"*\n``` quote\nThis is a very important issue! I’m on it!\n```"""
        self.send_and_test_stream_message("comment_updated", expected_topic, expected_message)

    def test_comment_event_comment_deleted(self) -> None:
        expected_topic = "SP-1: Add support for newer format Jira issue comment events"
        expected_message = """Hemanth V. Alluri deleted their comment on issue: *"Add support for newer format Jira issue comment events"*\n``` quote\n~~This is a very important issue! I’m on it!~~\n```"""
        self.send_and_test_stream_message("comment_deleted", expected_topic, expected_message)
