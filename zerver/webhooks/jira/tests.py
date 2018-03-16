# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase

class JiraHookTests(WebhookTestCase):
    STREAM_NAME = 'jira'
    URL_TEMPLATE = u"/api/v1/external/jira?api_key={api_key}&stream={stream}"

    def test_unknown(self) -> None:
        url = self.build_webhook_url()

        result = self.client_post(url,
                                  self.get_body('unknown_v1'),
                                  stream_name="jira",
                                  content_type="application/json")

        self.assert_json_success(result)

        result = self.client_post(url,
                                  self.get_body('unknown_v2'),
                                  stream_name="jira",
                                  content_type="application/json")

        self.assert_json_success(result)

    def test_custom_stream(self) -> None:
        api_key = self.test_user.api_key
        url = "/api/v1/external/jira?api_key=%s&stream=jira_custom" % (api_key,)
        msg = self.send_json_payload(self.test_user,
                                     url,
                                     self.get_body('created_v2'),
                                     stream_name="jira_custom",
                                     content_type="application/json")
        self.assertEqual(msg.topic_name(), "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **created** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) priority Major, assigned to **no one**:

> New bug with hook""")

    def test_created(self) -> None:
        expected_subject = "BUG-15: New bug with hook"
        expected_message = """Leo Franchi **created** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) priority Major, assigned to **no one**:

> New bug with hook"""
        self.send_and_test_stream_message('created_v1', expected_subject, expected_message)
        self.send_and_test_stream_message('created_v2', expected_subject, expected_message)

    def test_created_with_unicode(self) -> None:
            expected_subject = u"BUG-15: New bug with à hook"
            expected_message = u"""Leo Franchià **created** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) priority Major, assigned to **no one**:

> New bug with à hook"""
            self.send_and_test_stream_message('created_with_unicode_v1', expected_subject, expected_message)
            self.send_and_test_stream_message('created_with_unicode_v2', expected_subject, expected_message)

    def test_created_assignee(self) -> None:
        expected_subject = "TEST-4: Test Created Assignee"
        expected_message = """Leonardo Franchi [Administrator] **created** [TEST-4](https://zulipp.atlassian.net/browse/TEST-4) priority Major, assigned to **Leonardo Franchi [Administrator]**:

> Test Created Assignee"""
        self.send_and_test_stream_message('created_assignee_v1', expected_subject, expected_message)
        self.send_and_test_stream_message('created_assignee_v2', expected_subject, expected_message)

    def test_commented(self) -> None:
        expected_subject = "BUG-15: New bug with hook"
        expected_message = """Leo Franchi **added comment to** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):


Adding a comment. Oh, what a comment it is!"""
        self.send_and_test_stream_message('commented_v1', expected_subject, expected_message)
        self.send_and_test_stream_message('commented_v2', expected_subject, expected_message)

    def test_comment_edited(self) -> None:
            expected_subject = "BUG-15: New bug with hook"
            expected_message = """Leo Franchi **edited comment on** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):


Adding a comment. Oh, what a comment it is!"""
            self.send_and_test_stream_message('comment_edited_v2', expected_subject, expected_message)

    def test_comment_deleted(self) -> None:
        expected_subject = "TOM-1: New Issue"
        expected_message = "Tomasz Kolek **deleted comment from** [TOM-1](https://zuliptomek.atlassian.net/browse/TOM-1) (assigned to **kolaszek@go2.pl**)"
        self.send_and_test_stream_message('comment_deleted_v2', expected_subject, expected_message)

    def test_commented_markup(self) -> None:
        expected_subject = "TEST-7: Testing of rich text"
        expected_message = """Leonardo Franchi [Administrator] **added comment to** [TEST-7](https://zulipp.atlassian.net/browse/TEST-7):\n\n\nThis is a comment that likes to **exercise** a lot of _different_ `conventions` that `jira uses`.\r\n\r\n~~~\n\r\nthis code is not highlighted, but monospaced\r\n\n~~~\r\n\r\n~~~\n\r\ndef python():\r\n    print "likes to be formatted"\r\n\n~~~\r\n\r\n[http://www.google.com](http://www.google.com) is a bare link, and [Google](http://www.google.com) is given a title.\r\n\r\nThanks!\r\n\r\n~~~ quote\n\r\nSomeone said somewhere\r\n\n~~~"""
        self.send_and_test_stream_message('commented_markup_v1', expected_subject, expected_message)
        self.send_and_test_stream_message('commented_markup_v2', expected_subject, expected_message)

    def test_deleted(self) -> None:
        expected_subject = "BUG-15: New bug with hook"
        expected_message = "Leo Franchi **deleted** [BUG-15](http://lfranchi.com:8080/browse/BUG-15)!"
        self.send_and_test_stream_message('deleted_v1', expected_subject, expected_message)
        self.send_and_test_stream_message('deleted_v2', expected_subject, expected_message)

    def test_reassigned(self) -> None:
        expected_subject = "BUG-15: New bug with hook"
        expected_message = """Leo Franchi **updated** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):

* Changed assignee to **Othello, the Moor of Venice**"""
        self.send_and_test_stream_message('reassigned_v1', expected_subject, expected_message)
        self.send_and_test_stream_message('reassigned_v2', expected_subject, expected_message)

    def test_priority_updated(self) -> None:
        expected_subject = "TEST-1: Fix That"
        expected_message = """Leonardo Franchi [Administrator] **updated** [TEST-1](https://zulipp.atlassian.net/browse/TEST-1) (assigned to **leo@zulip.com**):

* Changed priority from **Critical** to **Major**"""
        self.send_and_test_stream_message('updated_priority_v1', expected_subject, expected_message)
        self.send_and_test_stream_message('updated_priority_v2', expected_subject, expected_message)

    def test_status_changed(self) -> None:
            expected_subject = "TEST-1: Fix That"
            expected_message = """Leonardo Franchi [Administrator] **updated** [TEST-1](https://zulipp.atlassian.net/browse/TEST-1):

* Changed status from **To Do** to **In Progress**"""
            self.send_and_test_stream_message('change_status_v1', expected_subject, expected_message)
            self.send_and_test_stream_message('change_status_v2', expected_subject, expected_message)

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data('jira', fixture_name)
