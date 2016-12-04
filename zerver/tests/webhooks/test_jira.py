# -*- coding: utf-8 -*-
from typing import Text
from zerver.lib.test_classes import WebhookTestCase

class JiraHookTests(WebhookTestCase):
    STREAM_NAME = 'jira'
    URL_TEMPLATE = u"/api/v1/external/jira?api_key={api_key}"

    def test_unknown(self):
        # type: () -> None
        url = self.build_webhook_url()

        result = self.client_post(url,
                                  self.get_body('unknown'),
                                  stream_name="jira",
                                  content_type="application/json")

        self.assert_json_error(result, 'Unknown JIRA event type')

    def test_custom_stream(self):
        # type: () -> None
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        url = "/api/v1/external/jira?api_key=%s&stream=jira_custom" % (api_key,)
        msg = self.send_json_payload(self.TEST_USER_EMAIL,
                                     url,
                                     self.get_body('created'),
                                     stream_name="jira_custom",
                                     content_type="application/json")
        self.assertEqual(msg.topic_name(), "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **created** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) priority Major, assigned to **no one**:

> New bug with hook""")

    def test_created(self):
        # type: () -> None
        expected_subject = "BUG-15: New bug with hook"
        expected_message = """Leo Franchi **created** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) priority Major, assigned to **no one**:

> New bug with hook"""
        self.send_and_test_stream_message('created', expected_subject, expected_message)

    def test_created_assignee(self):
        # type: () -> None
        expected_subject = "TEST-4: Test Created Assignee"
        expected_message = """Leonardo Franchi [Administrator] **created** [TEST-4](https://zulipp.atlassian.net/browse/TEST-4) priority Major, assigned to **Leonardo Franchi [Administrator]**:

> Test Created Assignee"""
        self.send_and_test_stream_message('created_assignee', expected_subject, expected_message)

    def test_commented(self):
        # type: () -> None
        expected_subject = "BUG-15: New bug with hook"
        expected_message = """Leo Franchi **updated** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):


Adding a comment. Oh, what a comment it is!
"""
        self.send_and_test_stream_message('commented', expected_subject, expected_message)

    def test_commented_markup(self):
        # type: () -> None
        expected_subject = "TEST-7: Testing of rich text"
        expected_message = """Leonardo Franchi [Administrator] **updated** [TEST-7](https://zulipp.atlassian.net/browse/TEST-7):\n\n\nThis is a comment that likes to **exercise** a lot of _different_ `conventions` that `jira uses`.\r\n\r\n~~~\n\r\nthis code is not highlighted, but monospaced\r\n\n~~~\r\n\r\n~~~\n\r\ndef python():\r\n    print "likes to be formatted"\r\n\n~~~\r\n\r\n[http://www.google.com](http://www.google.com) is a bare link, and [Google](http://www.google.com) is given a title.\r\n\r\nThanks!\r\n\r\n~~~ quote\n\r\nSomeone said somewhere\r\n\n~~~\n"""
        self.send_and_test_stream_message('commented_markup', expected_subject, expected_message)

    def test_deleted(self):
        # type: () -> None
        expected_subject = "BUG-15: New bug with hook"
        expected_message = "Leo Franchi **deleted** [BUG-15](http://lfranchi.com:8080/browse/BUG-15)!"
        self.send_and_test_stream_message('deleted', expected_subject, expected_message)

    def test_reassigned(self):
        # type: () -> None
        expected_subject = "BUG-15: New bug with hook"
        expected_message = """Leo Franchi **updated** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) (assigned to **Othello, the Moor of Venice**):

* Changed assignee from **None** to **Othello, the Moor of Venice**
"""
        self.send_and_test_stream_message('reassigned', expected_subject, expected_message)

    def test_reopened(self):
        # type: () -> None
        expected_subject = "BUG-7: More cowbell polease"
        expected_message = """Leo Franchi **updated** [BUG-7](http://lfranchi.com:8080/browse/BUG-7) (assigned to **Othello, the Moor of Venice**):

* Changed resolution from **Fixed** to **None**
* Changed status from **Resolved** to **Reopened**

Re-opened yeah!
"""
        self.send_and_test_stream_message('reopened', expected_subject, expected_message)

    def test_resolved(self):
        # type: () -> None
        expected_subject = "BUG-13: Refreshing the page loses the user's current posi..."
        expected_message = """Leo Franchi **updated** [BUG-13](http://lfranchi.com:8080/browse/BUG-13) (assigned to **Othello, the Moor of Venice**):

* Changed status from **Open** to **Resolved**
* Changed assignee from **None** to **Othello, the Moor of Venice**
* Changed resolution from **None** to **Fixed**

Fixed it, finally!
"""
        self.send_and_test_stream_message('resolved', expected_subject, expected_message)

    def test_workflow_postfuncion(self):
        # type: () -> None
        expected_subject = "TEST-5: PostTest"
        expected_message = """Leo Franchi [Administrator] **transitioned** [TEST-5](https://lfranchi-test.atlassian.net/browse/TEST-5) from Resolved to Reopened"""
        self.send_and_test_stream_message('postfunction_hook', expected_subject, expected_message)

    def test_workflow_postfunction(self):
        # type: () -> None
        expected_subject = "TEST-5: PostTest"
        expected_message = """Leo Franchi [Administrator] **transitioned** [TEST-5](https://lfranchi-test.atlassian.net/browse/TEST-5) from Resolved to Reopened"""
        self.send_and_test_stream_message('postfunction_hook', expected_subject, expected_message)

    def test_workflow_postfunction_started(self):
        # type: () -> None
        expected_subject = "TEST-7: Gluttony of Post Functions"
        expected_message = """Leo Franchi [Administrator] **transitioned** [TEST-7](https://lfranchi-test.atlassian.net/browse/TEST-7) from Open to Underway"""
        self.send_and_test_stream_message('postfunction_started', expected_subject, expected_message)

    def test_workflow_postfunction_resolved(self):
        # type: () -> None
        expected_subject = "TEST-7: Gluttony of Post Functions"
        expected_message = """Leo Franchi [Administrator] **transitioned** [TEST-7](https://lfranchi-test.atlassian.net/browse/TEST-7) from Open to Resolved"""
        self.send_and_test_stream_message('postfunction_resolved', expected_subject, expected_message)

    def test_mention(self):
        # type: () -> None
        expected_subject = "TEST-5: Lunch Decision Needed"
        expected_message = """Leonardo Franchi [Administrator] **updated** [TEST-5](https://zulipp.atlassian.net/browse/TEST-5) (assigned to **Othello, the Moor of Venice**):


Making a comment, **Othello, the Moor of Venice** is watching this issue
"""
        self.send_and_test_stream_message('watch_mention_updated', expected_subject, expected_message)

    def test_priority_updated(self):
        # type: () -> None
        expected_subject = "TEST-1: Fix That"
        expected_message = """Leonardo Franchi [Administrator] **updated** [TEST-1](https://zulipp.atlassian.net/browse/TEST-1) (assigned to **leo@zulip.com**):

* Changed priority from **Critical** to **Major**
"""
        self.send_and_test_stream_message('updated_priority', expected_subject, expected_message)

    def get_body(self, fixture_name):
        # type: (Text) -> Text
        return self.fixture_data('jira', fixture_name)
