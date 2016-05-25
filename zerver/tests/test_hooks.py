# -*- coding: utf-8 -*-
from zerver.lib.test_helpers import AuthedTestCase
from zerver.lib.test_runner import slow
from zerver.models import Message, Recipient

import ujson
from six.moves import urllib

class WebhookTestCase(AuthedTestCase):
    """
    Common for all webhooks tests

    Override below class attributes and run send_and_test_message
    If you create your url in uncommon way you can override build_webhook_url method
    In case that you need modify body or create it without using fixture you can also override get_body method
    """
    STREAM_NAME = None
    TEST_USER_EMAIL = 'webhook-bot@zulip.com'
    URL_TEMPLATE = None
    FIXTURE_DIR_NAME = None

    def setUp(self):
        self.url = self.build_webhook_url()

    def send_and_test_stream_message(self, fixture_name, expected_subject=None,
                                     expected_message=None, content_type="application/json", **kwargs):
        payload = self.get_body(fixture_name)
        if content_type is not None:
            kwargs['content_type'] = content_type
        msg = self.send_json_payload(self.TEST_USER_EMAIL, self.url, payload,
                                     self.STREAM_NAME, **kwargs)
        self.do_test_subject(msg, expected_subject)
        self.do_test_message(msg, expected_message)

        return msg

    def send_and_test_private_message(self, fixture_name, expected_subject=None,
                                      expected_message=None, content_type="application/json", **kwargs):
        payload = self.get_body(fixture_name)
        if content_type is not None:
            kwargs['content_type'] = content_type

        result = self.client.post(self.url, payload, content_type=content_type)
        self.assert_json_success(result)

        msg = self.get_last_message()
        self.do_test_message(msg, expected_message)

    def build_webhook_url(self):
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        return self.URL_TEMPLATE.format(stream=self.STREAM_NAME, api_key=api_key)

    def get_body(self, fixture_name):
        return ujson.dumps(ujson.loads(self.fixture_data(self.FIXTURE_DIR_NAME, fixture_name)))

    def do_test_subject(self, msg, expected_subject):
        if expected_subject is not None:
            self.assertEqual(msg.subject, expected_subject)

    def do_test_message(self, msg, expected_message):
        if expected_message is not None:
            self.assertEqual(msg.content, expected_message)

class JiraHookTests(WebhookTestCase):
    STREAM_NAME = 'jira'
    URL_TEMPLATE = "/api/v1/external/jira?api_key={api_key}"

    def test_unknown(self):
        url = self.build_webhook_url()

        result = self.client.post(url,
                                  self.get_body('unknown'),
                                  stream_name="jira",
                                  content_type="application/json")

        self.assert_json_error(result, 'Unknown JIRA event type')

    def test_custom_stream(self):
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        url = "/api/v1/external/jira?api_key=%s&stream=jira_custom" % (api_key,)
        msg = self.send_json_payload(self.TEST_USER_EMAIL,
                                     url,
                                     self.get_body('created'),
                                     stream_name="jira_custom",
                                     content_type="application/json")
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **created** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) priority Major, assigned to @**no one**:

> New bug with hook""")

    def test_created(self):
        expected_subject = "BUG-15: New bug with hook"
        expected_message = """Leo Franchi **created** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) priority Major, assigned to @**no one**:

> New bug with hook"""
        self.send_and_test_stream_message('created', expected_subject, expected_message)

    def test_created_assignee(self):
        expected_subject = "TEST-4: Test Created Assignee"
        expected_message = """Leonardo Franchi [Administrator] **created** [TEST-4](https://zulipp.atlassian.net/browse/TEST-4) priority Major, assigned to @**Leonardo Franchi [Administrator]**:

> Test Created Assignee"""
        self.send_and_test_stream_message('created_assignee', expected_subject, expected_message)

    def test_commented(self):
        expected_subject = "BUG-15: New bug with hook"
        expected_message = """Leo Franchi **updated** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) (assigned to @**Othello, the Moor of Venice**):


Adding a comment. Oh, what a comment it is!
"""
        self.send_and_test_stream_message('commented', expected_subject, expected_message)

    def test_commented_markup(self):
        expected_subject = "TEST-7: Testing of rich text"
        expected_message = """Leonardo Franchi [Administrator] **updated** [TEST-7](https://zulipp.atlassian.net/browse/TEST-7):\n\n\nThis is a comment that likes to **exercise** a lot of _different_ `conventions` that `jira uses`.\r\n\r\n~~~\n\r\nthis code is not highlighted, but monospaced\r\n\n~~~\r\n\r\n~~~\n\r\ndef python():\r\n    print "likes to be formatted"\r\n\n~~~\r\n\r\n[http://www.google.com](http://www.google.com) is a bare link, and [Google](http://www.google.com) is given a title.\r\n\r\nThanks!\r\n\r\n~~~ quote\n\r\nSomeone said somewhere\r\n\n~~~\n"""
        self.send_and_test_stream_message('commented_markup', expected_subject, expected_message)

    def test_deleted(self):
        expected_subject = "BUG-15: New bug with hook"
        expected_message = "Leo Franchi **deleted** [BUG-15](http://lfranchi.com:8080/browse/BUG-15)!"
        self.send_and_test_stream_message('deleted', expected_subject, expected_message)

    def test_reassigned(self):
        expected_subject = "BUG-15: New bug with hook"
        expected_message = """Leo Franchi **updated** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) (assigned to @**Othello, the Moor of Venice**):

* Changed assignee from **None** to @**Othello, the Moor of Venice**
"""
        self.send_and_test_stream_message('reassigned', expected_subject, expected_message)

    def test_reopened(self):
        expected_subject = "BUG-7: More cowbell polease"
        expected_message = """Leo Franchi **updated** [BUG-7](http://lfranchi.com:8080/browse/BUG-7) (assigned to @**Othello, the Moor of Venice**):

* Changed resolution from **Fixed** to **None**
* Changed status from **Resolved** to **Reopened**

Re-opened yeah!
"""
        self.send_and_test_stream_message('reopened', expected_subject, expected_message)

    def test_resolved(self):
        expected_subject = "BUG-13: Refreshing the page loses the user's current posi..."
        expected_message = """Leo Franchi **updated** [BUG-13](http://lfranchi.com:8080/browse/BUG-13) (assigned to @**Othello, the Moor of Venice**):

* Changed status from **Open** to **Resolved**
* Changed assignee from **None** to @**Othello, the Moor of Venice**
* Changed resolution from **None** to **Fixed**

Fixed it, finally!
"""
        self.send_and_test_stream_message('resolved', expected_subject, expected_message)

    def test_workflow_postfuncion(self):
        expected_subject = "TEST-5: PostTest"
        expected_message = """Leo Franchi [Administrator] **transitioned** [TEST-5](https://lfranchi-test.atlassian.net/browse/TEST-5) from Resolved to Reopened"""
        self.send_and_test_stream_message('postfunction_hook', expected_subject, expected_message)

    def test_workflow_postfunction(self):
        expected_subject = "TEST-5: PostTest"
        expected_message = """Leo Franchi [Administrator] **transitioned** [TEST-5](https://lfranchi-test.atlassian.net/browse/TEST-5) from Resolved to Reopened"""
        self.send_and_test_stream_message('postfunction_hook', expected_subject, expected_message)

    def test_workflow_postfunction_started(self):
        expected_subject = "TEST-7: Gluttony of Post Functions"
        expected_message = """Leo Franchi [Administrator] **transitioned** [TEST-7](https://lfranchi-test.atlassian.net/browse/TEST-7) from Open to Underway"""
        self.send_and_test_stream_message('postfunction_started', expected_subject, expected_message)

    def test_workflow_postfunction_resolved(self):
        expected_subject = "TEST-7: Gluttony of Post Functions"
        expected_message = """Leo Franchi [Administrator] **transitioned** [TEST-7](https://lfranchi-test.atlassian.net/browse/TEST-7) from Open to Resolved"""
        self.send_and_test_stream_message('postfunction_resolved', expected_subject, expected_message)

    def test_mention(self):
        expected_subject = "TEST-5: Lunch Decision Needed"
        expected_message = """Leonardo Franchi [Administrator] **updated** [TEST-5](https://zulipp.atlassian.net/browse/TEST-5) (assigned to @**Othello, the Moor of Venice**):


Making a comment, @**Othello, the Moor of Venice** is watching this issue
"""
        self.send_and_test_stream_message('watch_mention_updated', expected_subject, expected_message)

    def test_priority_updated(self):
        expected_subject = "TEST-1: Fix That"
        expected_message = """Leonardo Franchi [Administrator] **updated** [TEST-1](https://zulipp.atlassian.net/browse/TEST-1) (assigned to **leo@zulip.com**):

* Changed priority from **Critical** to **Major**
"""
        self.send_and_test_stream_message('updated_priority', expected_subject, expected_message)

    def get_body(self, fixture_name):
        return self.fixture_data('jira', fixture_name)

class BeanstalkHookTests(WebhookTestCase):
    STREAM_NAME = 'commits'
    URL_TEMPLATE = "/api/v1/external/beanstalk"

    def test_git_single(self):
        expected_subject = "work-test"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) to branch master

* [e50508d](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df): add some stuff
"""
        self.send_and_test_stream_message('git_singlecommit', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    @slow(0.20, "lots of queries")
    def test_git_multiple(self):
        expected_subject = "work-test"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) to branch master

* [edf529c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7): Added new file
* [c2a191b](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9): Filled in new file with some stuff
* [2009815](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158): More work to fix some bugs
"""
        self.send_and_test_stream_message('git_multiple', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_svn_addremove(self):
        expected_subject = "svn r3"
        expected_message = """Leo Franchi pushed [revision 3](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/3):

> Removed a file and added another one!"""
        self.send_and_test_stream_message('svn_addremove', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_svn_changefile(self):
        expected_subject = "svn r2"
        expected_message = """Leo Franchi pushed [revision 2](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/2):

> Added some code"""
        self.send_and_test_stream_message('svn_changefile', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def get_body(self, fixture_name):
        return {'payload': self.fixture_data('beanstalk', fixture_name)}

class GithubV1HookTests(WebhookTestCase):
    STREAM_NAME = None
    URL_TEMPLATE = "/api/v1/external/github"
    FIXTURE_DIR_NAME = 'github'
    SEND_STREAM = False
    BRANCHES = False

    push_content = """zbenjamin [pushed](https://github.com/zbenjamin/zulip-test/compare/4f9adc4777d5...b95449196980) to branch master

* [48c329a](https://github.com/zbenjamin/zulip-test/commit/48c329a0b68a9a379ff195ee3f1c1f4ab0b2a89e): Add baz
* [06ebe5f](https://github.com/zbenjamin/zulip-test/commit/06ebe5f472a32f6f31fd2a665f0c7442b69cce72): Baz needs to be longer
* [b954491](https://github.com/zbenjamin/zulip-test/commit/b95449196980507f08209bdfdc4f1d611689b7a8): Final edit to baz, I swear
"""

    def test_spam_branch_is_ignored(self):
        self.SEND_STREAM = True
        self.STREAM_NAME = 'commits'
        self.BRANCHES = 'dev,staging'
        data = self.get_body('push')

        # We subscribe to the stream in this test, even though
        # it won't get written, to avoid failing for the wrong
        # reason.
        self.subscribe_to_stream(self.TEST_USER_EMAIL, self.STREAM_NAME)

        prior_count = Message.objects.count()

        result = self.client.post(self.URL_TEMPLATE, data)
        self.assert_json_success(result)

        after_count = Message.objects.count()
        self.assertEqual(prior_count, after_count)

    def get_body(self, fixture_name):
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        data = ujson.loads(self.fixture_data(self.FIXTURE_DIR_NAME, 'v1_' + fixture_name))
        data.update({'email': self.TEST_USER_EMAIL,
                     'api-key': api_key,
                     'payload': ujson.dumps(data['payload'])})
        if self.SEND_STREAM:
            data['stream'] = self.STREAM_NAME

        if self.BRANCHES is not None:
            data['branches'] = self.BRANCHES
        return data

    def basic_test(self, fixture_name, stream_name, expected_subject, expected_content, send_stream=False, branches=None):
        self.STREAM_NAME = stream_name
        self.SEND_STREAM = send_stream
        self.BRANCHES = branches
        self.send_and_test_stream_message(fixture_name, expected_subject, expected_content, content_type=None)

    def test_user_specified_branches(self):
        self.basic_test('push', 'my_commits', 'zulip-test', self.push_content,
                        send_stream=True, branches="master,staging")

    def test_user_specified_stream(self):
        # Around May 2013 the github webhook started to specify the stream.
        # Before then, the stream was hard coded to "commits".
        self.basic_test('push', 'my_commits', 'zulip-test', self.push_content,
                        send_stream=True)

    def test_legacy_hook(self):
        self.basic_test('push', 'commits', 'zulip-test', self.push_content)

    def test_issues_opened(self):
        self.basic_test('issues_opened', 'issues',
                        "zulip-test: issue 5: The frobnicator doesn't work",
                        "zbenjamin opened [issue 5](https://github.com/zbenjamin/zulip-test/issues/5)\n\n~~~ quote\nI tried changing the widgets, but I got:\r\n\r\nPermission denied: widgets are immutable\n~~~")

    def test_issue_comment(self):
        self.basic_test('issue_comment', 'issues',
                        "zulip-test: issue 5: The frobnicator doesn't work",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/issues/5#issuecomment-23374280) on [issue 5](https://github.com/zbenjamin/zulip-test/issues/5)\n\n~~~ quote\nWhoops, I did something wrong.\r\n\r\nI'm sorry.\n~~~")

    def test_issues_closed(self):
        self.basic_test('issues_closed', 'issues',
                        "zulip-test: issue 5: The frobnicator doesn't work",
                        "zbenjamin closed [issue 5](https://github.com/zbenjamin/zulip-test/issues/5)")

    def test_pull_request_opened(self):
        self.basic_test('pull_request_opened', 'commits',
                        "zulip-test: pull request 7: Counting is hard.",
                        "lfaraone opened [pull request 7](https://github.com/zbenjamin/zulip-test/pull/7)\n\n~~~ quote\nOmitted something I think?\n~~~")

    def test_pull_request_closed(self):
        self.basic_test('pull_request_closed', 'commits',
                        "zulip-test: pull request 7: Counting is hard.",
                        "zbenjamin closed [pull request 7](https://github.com/zbenjamin/zulip-test/pull/7)")

    def test_pull_request_synchronize(self):
        self.basic_test('pull_request_synchronize', 'commits',
                        "zulip-test: pull request 13: Even more cowbell.",
                        "zbenjamin synchronized [pull request 13](https://github.com/zbenjamin/zulip-test/pull/13)")

    def test_pull_request_comment(self):
        self.basic_test('pull_request_comment', 'commits',
                        "zulip-test: pull request 9: Less cowbell.",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/pull/9#issuecomment-24771110) on [pull request 9](https://github.com/zbenjamin/zulip-test/pull/9)\n\n~~~ quote\nYeah, who really needs more cowbell than we already have?\n~~~")

    def test_pull_request_comment_user_specified_stream(self):
        self.basic_test('pull_request_comment', 'my_commits',
                        "zulip-test: pull request 9: Less cowbell.",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/pull/9#issuecomment-24771110) on [pull request 9](https://github.com/zbenjamin/zulip-test/pull/9)\n\n~~~ quote\nYeah, who really needs more cowbell than we already have?\n~~~",
                        send_stream=True)

    def test_commit_comment(self):
        self.basic_test('commit_comment', 'commits',
                        "zulip-test: commit 7c994678d2f98797d299abed852d3ff9d0834533",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533#commitcomment-4252302)\n\n~~~ quote\nAre we sure this is enough cowbell?\n~~~")

    def test_commit_comment_line(self):
        self.basic_test('commit_comment_line', 'commits',
                        "zulip-test: commit 7c994678d2f98797d299abed852d3ff9d0834533",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533#commitcomment-4252307) on `cowbell`, line 13\n\n~~~ quote\nThis line adds /unlucky/ cowbell (because of its line number).  We should remove it.\n~~~")

class GithubV2HookTests(WebhookTestCase):
    STREAM_NAME = None
    URL_TEMPLATE = "/api/v1/external/github"
    FIXTURE_DIR_NAME = 'github'
    SEND_STREAM = False
    BRANCHES = False

    push_content = """zbenjamin [pushed](https://github.com/zbenjamin/zulip-test/compare/4f9adc4777d5...b95449196980) to branch master

* [48c329a](https://github.com/zbenjamin/zulip-test/commit/48c329a0b68a9a379ff195ee3f1c1f4ab0b2a89e): Add baz
* [06ebe5f](https://github.com/zbenjamin/zulip-test/commit/06ebe5f472a32f6f31fd2a665f0c7442b69cce72): Baz needs to be longer
* [b954491](https://github.com/zbenjamin/zulip-test/commit/b95449196980507f08209bdfdc4f1d611689b7a8): Final edit to baz, I swear
"""

    def test_spam_branch_is_ignored(self):
        self.SEND_STREAM = True
        self.STREAM_NAME = 'commits'
        self.BRANCHES = 'dev,staging'
        data = self.get_body('push')

        # We subscribe to the stream in this test, even though
        # it won't get written, to avoid failing for the wrong
        # reason.
        self.subscribe_to_stream(self.TEST_USER_EMAIL, self.STREAM_NAME)

        prior_count = Message.objects.count()

        result = self.client.post(self.URL_TEMPLATE, data)
        self.assert_json_success(result)

        after_count = Message.objects.count()
        self.assertEqual(prior_count, after_count)

    def get_body(self, fixture_name):
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        data = ujson.loads(self.fixture_data(self.FIXTURE_DIR_NAME, 'v2_' + fixture_name))
        data.update({'email': self.TEST_USER_EMAIL,
                     'api-key': api_key,
                     'payload': ujson.dumps(data['payload'])})
        if self.SEND_STREAM:
            data['stream'] = self.STREAM_NAME

        if self.BRANCHES is not None:
            data['branches'] = self.BRANCHES
        return data

    def basic_test(self, fixture_name, stream_name, expected_subject, expected_content, send_stream=False, branches=None):
        self.STREAM_NAME = stream_name
        self.SEND_STREAM = send_stream
        self.BRANCHES = branches
        self.send_and_test_stream_message(fixture_name, expected_subject, expected_content, content_type=None)

    def test_user_specified_branches(self):
        self.basic_test('push', 'my_commits', 'zulip-test', self.push_content,
                        send_stream=True, branches="master,staging")

    def test_user_specified_stream(self):
        # Around May 2013 the github webhook started to specify the stream.
        # Before then, the stream was hard coded to "commits".
        self.basic_test('push', 'my_commits', 'zulip-test', self.push_content,
                        send_stream=True)

    def test_legacy_hook(self):
        self.basic_test('push', 'commits', 'zulip-test', self.push_content)

    def test_issues_opened(self):
        self.basic_test('issues_opened', 'issues',
                        "zulip-test: issue 5: The frobnicator doesn't work",
                        "zbenjamin opened [issue 5](https://github.com/zbenjamin/zulip-test/issues/5)\n\n~~~ quote\nI tried changing the widgets, but I got:\r\n\r\nPermission denied: widgets are immutable\n~~~")

    def test_issue_comment(self):
        self.basic_test('issue_comment', 'issues',
                        "zulip-test: issue 5: The frobnicator doesn't work",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/issues/5#issuecomment-23374280) on [issue 5](https://github.com/zbenjamin/zulip-test/issues/5)\n\n~~~ quote\nWhoops, I did something wrong.\r\n\r\nI'm sorry.\n~~~")

    def test_issues_closed(self):
        self.basic_test('issues_closed', 'issues',
                        "zulip-test: issue 5: The frobnicator doesn't work",
                        "zbenjamin closed [issue 5](https://github.com/zbenjamin/zulip-test/issues/5)")

    def test_pull_request_opened(self):
        self.basic_test('pull_request_opened', 'commits',
                        "zulip-test: pull request 7: Counting is hard.",
                        "lfaraone opened [pull request 7](https://github.com/zbenjamin/zulip-test/pull/7)\n\n~~~ quote\nOmitted something I think?\n~~~")

    def test_pull_request_closed(self):
        self.basic_test('pull_request_closed', 'commits',
                        "zulip-test: pull request 7: Counting is hard.",
                        "zbenjamin closed [pull request 7](https://github.com/zbenjamin/zulip-test/pull/7)")

    def test_pull_request_synchronize(self):
        self.basic_test('pull_request_synchronize', 'commits',
                        "zulip-test: pull request 13: Even more cowbell.",
                        "zbenjamin synchronized [pull request 13](https://github.com/zbenjamin/zulip-test/pull/13)")

    def test_pull_request_comment(self):
        self.basic_test('pull_request_comment', 'commits',
                        "zulip-test: pull request 9: Less cowbell.",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/pull/9#issuecomment-24771110) on [pull request 9](https://github.com/zbenjamin/zulip-test/pull/9)\n\n~~~ quote\nYeah, who really needs more cowbell than we already have?\n~~~")

    def test_pull_request_comment_user_specified_stream(self):
        self.basic_test('pull_request_comment', 'my_commits',
                        "zulip-test: pull request 9: Less cowbell.",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/pull/9#issuecomment-24771110) on [pull request 9](https://github.com/zbenjamin/zulip-test/pull/9)\n\n~~~ quote\nYeah, who really needs more cowbell than we already have?\n~~~",
                        send_stream=True)

    def test_commit_comment(self):
        self.basic_test('commit_comment', 'commits',
                        "zulip-test: commit 7c994678d2f98797d299abed852d3ff9d0834533",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533#commitcomment-4252302)\n\n~~~ quote\nAre we sure this is enough cowbell?\n~~~")

    def test_commit_comment_line(self):
        self.basic_test('commit_comment_line', 'commits',
                        "zulip-test: commit 7c994678d2f98797d299abed852d3ff9d0834533",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533#commitcomment-4252307) on `cowbell`, line 13\n\n~~~ quote\nThis line adds /unlucky/ cowbell (because of its line number).  We should remove it.\n~~~")

class PivotalV3HookTests(WebhookTestCase):
    STREAM_NAME = 'pivotal'
    URL_TEMPLATE = "/api/v1/external/pivotal?stream={stream}&api_key={api_key}"

    def test_accepted(self):
        expected_subject = 'My new Feature story'
        expected_message = 'Leo Franchi accepted "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('accepted', expected_subject, expected_message, content_type="application/xml")

    def test_commented(self):
        expected_subject = 'Comment added'
        expected_message = 'Leo Franchi added comment: "FIX THIS NOW" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('commented', expected_subject, expected_message, content_type="application/xml")

    def test_created(self):
        expected_subject = 'My new Feature story'
        expected_message = 'Leo Franchi added "My new Feature story" \
(unscheduled feature):\n\n~~~ quote\nThis is my long description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('created', expected_subject, expected_message, content_type="application/xml")

    def test_delivered(self):
        expected_subject = 'Another new story'
        expected_message = 'Leo Franchi delivered "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('delivered', expected_subject, expected_message, content_type="application/xml")

    def test_finished(self):
        expected_subject = 'Another new story'
        expected_message = 'Leo Franchi finished "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('finished', expected_subject, expected_message, content_type="application/xml")

    def test_moved(self):
        expected_subject = 'My new Feature story'
        expected_message = 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('moved', expected_subject, expected_message, content_type="application/xml")

    def test_rejected(self):
        expected_subject = 'Another new story'
        expected_message = 'Leo Franchi rejected "Another new story" with comments: \
"Not good enough, sorry" [(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('rejected', expected_subject, expected_message, content_type="application/xml")

    def test_started(self):
        expected_subject = 'Another new story'
        expected_message = 'Leo Franchi started "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('started', expected_subject, expected_message, content_type="application/xml")

    def test_created_estimate(self):
        expected_subject = 'Another new story'
        expected_message = 'Leo Franchi added "Another new story" \
(unscheduled feature worth 2 story points):\n\n~~~ quote\nSome loong description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('created_estimate', expected_subject, expected_message, content_type="application/xml")

    def test_type_changed(self):
        expected_subject = 'My new Feature story'
        expected_message = 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('type_changed', expected_subject, expected_message, content_type="application/xml")

    def get_body(self, fixture_name):
        return self.fixture_data('pivotal', fixture_name, file_type='xml')

class PivotalV5HookTests(WebhookTestCase):
    STREAM_NAME = 'pivotal'
    URL_TEMPLATE = "/api/v1/external/pivotal?stream={stream}&api_key={api_key}"

    def test_accepted(self):
        expected_subject = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **unstarted** to **accepted**
"""
        self.send_and_test_stream_message('accepted', expected_subject, expected_message, content_type="application/xml")

    def test_commented(self):
        expected_subject = '#63486316: Story of the Year'
        expected_message = """Leo Franchi added a comment to [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
~~~quote
A comment on the story
~~~"""
        self.send_and_test_stream_message('commented', expected_subject, expected_message, content_type="application/xml")

    def test_created(self):
        expected_subject = '#63495662: Story that I created'
        expected_message = """Leo Franchi created bug: [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story that I created](http://www.pivotaltracker.com/story/show/63495662)
* State is **unscheduled**
* Description is

> What a description"""
        self.send_and_test_stream_message('created', expected_subject, expected_message, content_type="application/xml")

    def test_delivered(self):
        expected_subject = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **accepted** to **delivered**
"""
        self.send_and_test_stream_message('delivered', expected_subject, expected_message, content_type="application/xml")

    def test_finished(self):
        expected_subject = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **delivered** to **accepted**
"""
        self.send_and_test_stream_message('finished', expected_subject, expected_message, content_type="application/xml")

    def test_moved(self):
        expected_subject = '#63496066: Pivotal Test'
        expected_message = """Leo Franchi moved [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066) from **unstarted** to **unscheduled**"""
        self.send_and_test_stream_message('moved', expected_subject, expected_message, content_type="application/xml")

    def test_rejected(self):
        expected_subject = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* Comment added:
~~~quote
Try again next time
~~~
* state changed from **delivered** to **rejected**
"""
        self.send_and_test_stream_message('rejected', expected_subject, expected_message, content_type="application/xml")

    def test_started(self):
        expected_subject = '#63495972: Fresh Story'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Fresh Story](http://www.pivotaltracker.com/story/show/63495972):
* state changed from **unstarted** to **started**
"""
        self.send_and_test_stream_message('started', expected_subject, expected_message, content_type="application/xml")

    def test_created_estimate(self):
        expected_subject = '#63496066: Pivotal Test'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066):
* estimate is now **3 points**
"""
        self.send_and_test_stream_message('created_estimate', expected_subject, expected_message, content_type="application/xml")

    def test_type_changed(self):
        expected_subject = '#63496066: Pivotal Test'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066):
* estimate changed from 3 to **0 points**
* type changed from **feature** to **bug**
"""
        self.send_and_test_stream_message('type_changed', expected_subject, expected_message, content_type="application/xml")

    def get_body(self, fixture_name):
        return self.fixture_data('pivotal', "v5_{}".format(fixture_name), file_type='json')

class NewRelicHookTests(WebhookTestCase):
    STREAM_NAME = 'newrelic'
    URL_TEMPLATE = "/api/v1/external/newrelic?stream={stream}&api_key={api_key}"

    def test_alert(self):
        expected_subject = "Apdex score fell below critical level of 0.90"
        expected_message = 'Alert opened on [application name]: \
Apdex score fell below critical level of 0.90\n\
[View alert](https://rpm.newrelc.com/accounts/[account_id]/applications/[application_id]/incidents/[incident_id])'
        self.send_and_test_stream_message('alert', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")
    def test_deployment(self):
        expected_subject = 'Test App deploy'
        expected_message = '`1242` deployed by **Zulip Test**\n\
Description sent via curl\n\nChangelog string'
        self.send_and_test_stream_message('deployment', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name):
        return self.fixture_data("newrelic", fixture_name, file_type="txt")

class StashHookTests(WebhookTestCase):
    STREAM_NAME = 'stash'
    URL_TEMPLATE = "/api/v1/external/stash?stream={stream}"

    def test_stash_message(self):
        """
        Messages are generated by Stash on a `git push`.

        The subject describes the repo and Stash "project". The
        content describes the commits pushed.
        """
        expected_subject = u"Secret project/Operation unicorn: master"
        expected_message = """`f259e90` was pushed to **master** in **Secret project/Operation unicorn** with:

* `f259e90`: Updating poms ..."""
        self.send_and_test_stream_message('push', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def get_body(self, fixture_name):
        return self.fixture_data("stash", fixture_name, file_type="json")

class FreshdeskHookTests(WebhookTestCase):
    STREAM_NAME = 'freshdesk'
    URL_TEMPLATE = "/api/v1/external/freshdesk?stream={stream}"

    def test_ticket_creation(self):
        """
        Messages are generated on ticket creation through Freshdesk's
        "Dispatch'r" service.
        """
        expected_subject = u"#11: Test ticket subject ☃"
        expected_message = u"""Requester ☃ Bob <requester-bob@example.com> created [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

~~~ quote
Test ticket description ☃.
~~~

Type: **Incident**
Priority: **High**
Status: **Pending**"""
        self.send_and_test_stream_message('ticket_created', expected_subject, expected_message, content_type="application/x-www-form-urlencoded", **self.api_auth(self.TEST_USER_EMAIL))

    def test_status_change(self):
        """
        Messages are generated when a ticket's status changes through
        Freshdesk's "Observer" service.
        """
        expected_subject = u"#11: Test ticket subject ☃"
        expected_message = """Requester Bob <requester-bob@example.com> updated [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

Status: **Resolved** => **Waiting on Customer**"""
        self.send_and_test_stream_message('status_changed', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_priority_change(self):
        """
        Messages are generated when a ticket's priority changes through
        Freshdesk's "Observer" service.
        """
        expected_subject = u"#11: Test ticket subject"
        expected_message = """Requester Bob <requester-bob@example.com> updated [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

Priority: **High** => **Low**"""
        self.send_and_test_stream_message('priority_changed', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def note_change(self, fixture, note_type):
        """
        Messages are generated when a note gets added to a ticket through
        Freshdesk's "Observer" service.
        """
        expected_subject = u"#11: Test ticket subject"
        expected_message = """Requester Bob <requester-bob@example.com> added a {} note to [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11).""".format(note_type)
        self.send_and_test_stream_message(fixture, expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_private_note_change(self):
        self.note_change("private_note", "private")

    def test_public_note_change(self):
        self.note_change("public_note", "public")

    def test_inline_image(self):
        """
        Freshdesk sends us descriptions as HTML, so we have to make the
        descriptions Zulip markdown-friendly while still doing our best to
        preserve links and images.
        """
        expected_subject = u"#12: Not enough ☃ guinea pigs"
        expected_message = u"Requester \u2603 Bob <requester-bob@example.com> created [ticket #12](http://test1234zzz.freshdesk.com/helpdesk/tickets/12):\n\n~~~ quote\nThere are too many cat pictures on the internet \u2603. We need more guinea pigs. Exhibit 1:\n\n  \n\n\n[guinea_pig.png](http://cdn.freshdesk.com/data/helpdesk/attachments/production/12744808/original/guinea_pig.png)\n~~~\n\nType: **Problem**\nPriority: **Urgent**\nStatus: **Open**"
        self.send_and_test_stream_message("inline_images", expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def build_webhook_url(self):
        return self.URL_TEMPLATE.format(stream=self.STREAM_NAME)

    def get_body(self, fixture_name):
        return self.fixture_data("freshdesk", fixture_name, file_type="json")

class ZenDeskHookTests(WebhookTestCase):
    STREAM_NAME = 'zendesk'
    URL_TEMPLATE = "/api/v1/external/zendesk"

    DEFAULT_TICKET_TITLE = 'User can\'t login'
    TICKET_TITLE = DEFAULT_TICKET_TITLE

    DEFAULT_TICKET_ID = 54
    TICKET_ID = DEFAULT_TICKET_ID

    DEFAULT_MESSAGE = 'Message'
    MESSAGE = DEFAULT_MESSAGE

    def get_body(self, fixture_name):
        return {
            'ticket_title': self.TICKET_TITLE,
            'ticket_id': self.TICKET_ID,
            'message': self.MESSAGE,
            'stream': self.STREAM_NAME,
        }

    def do_test(self, expected_subject=None, expected_message=None):
        self.send_and_test_stream_message(None, expected_subject, expected_message,
                                          content_type=None, **self.api_auth(self.TEST_USER_EMAIL))
        self.TICKET_TITLE = self.DEFAULT_TICKET_TITLE
        self.TICKET_ID = self.DEFAULT_TICKET_ID
        self.MESSAGE = self.DEFAULT_MESSAGE

    def test_subject(self):
        self.TICKET_ID = 4
        self.TICKET_TITLE = "Test ticket"
        self.do_test(expected_subject='#4: Test ticket')

    def test_long_subject(self):
        self.TICKET_ID = 4
        self.TICKET_TITLE = "Test ticket" + '!' * 80
        self.do_test(expected_subject='#4: Test ticket' + '!' * 42 + '...')

    def test_content(self):
        self.MESSAGE = 'New comment:\n> It is better\n* here'
        self.do_test(expected_message='New comment:\n> It is better\n* here')

class PagerDutyHookTests(WebhookTestCase):
    STREAM_NAME = 'pagerduty'
    URL_TEMPLATE = "/api/v1/external/pagerduty?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'pagerduty'

    def test_trigger(self):
        expected_message = ':imp: Incident [3](https://zulip-test.pagerduty.com/incidents/P140S4Y) triggered by [Test service](https://zulip-test.pagerduty.com/services/PIL5CUQ) and assigned to [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>foo'
        self.send_and_test_stream_message('trigger', u"incident 3", expected_message)

    def test_unacknowledge(self):
        expected_message = ':imp: Incident [3](https://zulip-test.pagerduty.com/incidents/P140S4Y) unacknowledged by [Test service](https://zulip-test.pagerduty.com/services/PIL5CUQ) and assigned to [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>foo'
        self.send_and_test_stream_message('unacknowledge', u"incident 3", expected_message)

    def test_resolved(self):
        expected_message = ':grinning: Incident [1](https://zulip-test.pagerduty.com/incidents/PO1XIJ5) resolved by [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>It is on fire'
        self.send_and_test_stream_message('resolved', u"incident 1", expected_message)

    def test_auto_resolved(self):
        expected_message = ':grinning: Incident [2](https://zulip-test.pagerduty.com/incidents/PX7K9J2) resolved\n\n>new'
        self.send_and_test_stream_message('auto_resolved', u"incident 2", expected_message)

    def test_acknowledge(self):
        expected_message = ':no_good: Incident [1](https://zulip-test.pagerduty.com/incidents/PO1XIJ5) acknowledged by [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>It is on fire'
        self.send_and_test_stream_message('acknowledge', u"incident 1", expected_message)

    def test_no_subject(self):
        expected_message = u':grinning: Incident [48219](https://dropbox.pagerduty.com/incidents/PJKGZF9) resolved\n\n>mp_error_block_down_critical\u2119\u01b4'
        self.send_and_test_stream_message('mp_fail', u"incident 48219", expected_message)

    def test_bad_message(self):
        expected_message = 'Unknown pagerduty message\n``` py\n{u\'type\': u\'incident.triggered\'}\n```'
        self.send_and_test_stream_message('bad_message_type', u"pagerduty", expected_message)

    def test_unknown_message_type(self):
        expected_message = 'Unknown pagerduty message\n``` py\n{u\'type\': u\'foo\'}\n```'
        self.send_and_test_stream_message('unknown_message_type', u"pagerduty", expected_message)

class TravisHookTests(WebhookTestCase):
    STREAM_NAME = 'travis'
    URL_TEMPLATE = "/api/v1/external/travis?stream={stream}&api_key={api_key}&topic=builds"
    FIXTURE_DIR_NAME = 'travis'

    def test_travis_message(self):
        """
        Build notifications are generated by Travis after build completes.

        The subject describes the repo and Stash "project". The
        content describes the commits pushed.
        """
        expected_message = (u"Author: josh_mandel\nBuild status: Passed :thumbsup:\n"
                            u"Details: [changes](https://github.com/hl7-fhir/fhir-sv"
                            u"n/compare/6dccb98bcfd9...6c457d366a31), [build log](ht"
                            u"tps://travis-ci.org/hl7-fhir/fhir-svn/builds/92495257)")

        self.send_and_test_stream_message(
            'build',
            'builds',
            expected_message,
            content_type="application/x-www-form-urlencoded"
        )

    def get_body(self, fixture_name):
        return urllib.parse.urlencode({'payload': self.fixture_data("travis", fixture_name, file_type="json")})

class PingdomHookTests(WebhookTestCase):
    STREAM_NAME = 'pingdom'
    URL_TEMPLATE = "/api/v1/external/pingdom?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'pingdom'

    def test_pingdom_from_up_to_down_http_check_message(self):
        """
        Tests if pingdom http check from up to down is handled correctly
        """
        expected_message = u"Service someurl.com changed its HTTP status from UP to DOWN.\nDescription: Non-recoverable failure in name resolution."
        self.send_and_test_stream_message('http_up_to_down', u"Test check status.", expected_message)

    def test_pingdom_from_up_to_down_smtp_check_message(self):
        """
        Tests if pingdom smtp check from up to down is handled correctly
        """
        expected_message = u"Service smtp.someurl.com changed its SMTP status from UP to DOWN.\nDescription: Connection refused."
        self.send_and_test_stream_message('smtp_up_to_down', u"SMTP check status.", expected_message)

    def test_pingdom_from_up_to_down_imap_check_message(self):
        """
        Tests if pingdom imap check from up to down is handled correctly
        """
        expected_message = u"Service imap.someurl.com changed its IMAP status from UP to DOWN.\nDescription: Invalid hostname, address or socket."
        self.send_and_test_stream_message('imap_up_to_down', u"IMAP check status.", expected_message)

    def test_pingdom_from_down_to_up_imap_check_message(self):
        """
        Tests if pingdom imap check from down to up is handled correctly
        """
        expected_message = u"Service imap.someurl.com changed its IMAP status from DOWN to UP."
        self.send_and_test_stream_message('imap_down_to_up', u"IMAP check status.", expected_message)

class YoHookTests(WebhookTestCase):
    STREAM_NAME = 'yo'
    URL_TEMPLATE = "/api/v1/external/yo?email={email}&api_key={api_key}&username={username}&user_ip={ip}"
    FIXTURE_DIR_NAME = 'yo'

    def test_yo_message(self):
        """
        Yo App sends notification whenever user receives a new Yo from another user.
        """
        expected_message = u"Yo from IAGO"
        self.send_and_test_private_message('', expected_message=expected_message,
                                           content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name):
        return {}

    def build_webhook_url(self):
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        email = "cordelia@zulip.com"
        username = "IAGO"
        ip = "127.0.0.1"
        return self.URL_TEMPLATE.format(email=email, api_key=api_key, username=username, ip=ip)

class TeamcityHookTests(WebhookTestCase):
    STREAM_NAME = 'teamcity'
    URL_TEMPLATE = "/api/v1/external/teamcity?stream={stream}&api_key={api_key}"
    SUBJECT = u"Project :: Compile"
    FIXTURE_DIR_NAME = 'teamcity'

    def test_teamcity_success(self):
        expected_message = u"Project :: Compile build 5535 - CL 123456 was successful! :thumbsup:\nDetails: [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv), [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)"
        self.send_and_test_stream_message('success', self.SUBJECT, expected_message)

    def test_teamcity_broken(self):
        expected_message = u"Project :: Compile build 5535 - CL 123456 is broken with status Exit code 1 (new)! :thumbsdown:\nDetails: [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv), [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)"
        self.send_and_test_stream_message('broken', self.SUBJECT, expected_message)

    def test_teamcity_failure(self):
        expected_message = u"Project :: Compile build 5535 - CL 123456 is still broken with status Exit code 1! :thumbsdown:\nDetails: [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv), [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)"
        self.send_and_test_stream_message('failure', self.SUBJECT, expected_message)

    def test_teamcity_fixed(self):
        expected_message = u"Project :: Compile build 5535 - CL 123456 has been fixed! :thumbsup:\nDetails: [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv), [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)"
        self.send_and_test_stream_message('fixed', self.SUBJECT, expected_message)

    def test_teamcity_personal(self):
        expected_message = u"Your personal build of Project :: Compile build 5535 - CL 123456 is broken with status Exit code 1 (new)! :thumbsdown:\nDetails: [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv), [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)"
        payload = ujson.dumps(ujson.loads(self.fixture_data(self.FIXTURE_DIR_NAME, 'personal')))
        self.client.post(self.url, payload, content_type="application/json")
        msg = self.get_last_message()

        self.assertEqual(msg.content, expected_message)
        self.assertEqual(msg.recipient.type, Recipient.PERSONAL)

class CodeshipHookTests(WebhookTestCase):
    STREAM_NAME = 'codeship'
    URL_TEMPLATE = "/api/v1/external/codeship?stream={stream}&api_key={api_key}"
    SUBJECT = u"codeship/docs"
    FIXTURE_DIR_NAME = 'codeship'

    def test_codeship_build_in_testing_status_message(self):
        """
        Tests if codeship testing status is mapped correctly
        """
        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch started."
        self.send_and_test_stream_message('testing_build', self.SUBJECT, expected_message)

    def test_codeship_build_in_error_status_message(self):
        """
        Tests if codeship error status is mapped correctly
        """
        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch failed."
        self.send_and_test_stream_message('error_build', self.SUBJECT, expected_message)

    def test_codeship_build_in_success_status_message(self):
        """
        Tests if codeship success status is mapped correctly
        """
        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch succeeded."
        self.send_and_test_stream_message('success_build', self.SUBJECT, expected_message)

    def test_codeship_build_in_other_status_status_message(self):
        """
        Tests if codeship other status is mapped correctly
        """
        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch has some_other_status status."
        self.send_and_test_stream_message('other_status_build', self.SUBJECT, expected_message)

class TaigaHookTests(WebhookTestCase):
    STREAM_NAME = 'taiga'
    TOPIC = "subject"
    URL_TEMPLATE = "/api/v1/external/taiga?stream={stream}&api_key={api_key}&topic={topic}"
    FIXTURE_DIR_NAME = 'taiga'

    def build_webhook_url(self):
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        return self.URL_TEMPLATE.format(stream=self.STREAM_NAME, api_key=api_key, topic=self.TOPIC)

    def test_taiga_userstory_deleted(self):
        message = u':x: Antek deleted user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_deleted", u'subject', message)

    def test_taiga_userstory_created(self):
        message = u':package: Antek created user story **A new hope**.\n'
        self.send_and_test_stream_message("userstory_created", u'subject', message)

    def test_taiga_userstory_changed_unblocked(self):
        message = u':unlock: Antek unblocked user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_unblocked", u'subject', message)

    def test_taiga_userstory_changed_subject(self):
        message = u':notebook: Antek renamed user story from A new hope to **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_subject", u'subject', message)

    def test_taiga_userstory_changed_status(self):
        message = u':chart_with_upwards_trend: Antek changed status of user story **A new hope** from New to Done.\n'
        self.send_and_test_stream_message("userstory_changed_status", u'subject', message)

    def test_taiga_userstory_changed_reassigned(self):
        message = u':busts_in_silhouette: Antek reassigned user story **Great US** from Antek to Han Solo.\n'
        self.send_and_test_stream_message("userstory_changed_reassigned", u'subject', message)

    def test_taiga_userstory_changed_points(self):
        message = u':game_die: Antek changed estimation of user story **A new hope**.\n'
        self.send_and_test_stream_message("userstory_changed_points", u'subject', message)

    def test_taiga_userstory_changed_new_milestone(self):
        message = u':calendar: Antek added user story **A newer hope** to sprint New sprint.\n'
        self.send_and_test_stream_message("userstory_changed_new_milestone", u'subject', message)

    def test_taiga_userstory_changed_milestone(self):
        message = u':calendar: Antek changed sprint of user story **A newer hope** from Old sprint to New sprint.\n'
        self.send_and_test_stream_message("userstory_changed_milestone", u'subject', message)

    def test_taiga_userstory_changed_description(self):
        message = u':notebook: Antek updated description of user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_description", u'subject', message)

    def test_taiga_userstory_changed_closed(self):
        message = u':chart_with_upwards_trend: Antek changed status of user story **A newer hope** from New to Done.\n:checkered_flag: Antek closed user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_closed", u'subject', message)

    def test_taiga_userstory_changed_reopened(self):
        message = u':chart_with_upwards_trend: Antek changed status of user story **A newer hope** from Done to New.\n:package: Antek reopened user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_reopened", u'subject', message)

    def test_taiga_userstory_changed_blocked(self):
        message = u':lock: Antek blocked user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_blocked", u'subject', message)

    def test_taiga_userstory_changed_assigned(self):
        message = u':busts_in_silhouette: Antek assigned user story **Great US** to Antek.\n'
        self.send_and_test_stream_message("userstory_changed_assigned", u'subject', message)

    def test_taiga_task_created(self):
        message = u':clipboard: Antek created task **New task assigned and in progress**.\n'
        self.send_and_test_stream_message("task_created", u'subject', message)

    def test_taiga_task_changed_status(self):
        message = u':chart_with_upwards_trend: Antek changed status of task **New task assigned and in progress** from Ready for test to New.\n'
        self.send_and_test_stream_message("task_changed_status", u'subject', message)

    def test_taiga_task_changed_blocked(self):
        message = u':lock: Antek blocked task **A new task**.\n'
        self.send_and_test_stream_message("task_changed_blocked", u'subject', message)

    def test_taiga_task_changed_unblocked(self):
        message = u':unlock: Antek unblocked task **A new task**.\n'
        self.send_and_test_stream_message("task_changed_unblocked", u'subject', message)

    def test_taiga_task_changed_assigned(self):
        message = u':busts_in_silhouette: Antek assigned task **Aaaa** to Antek.\n'
        self.send_and_test_stream_message("task_changed_assigned", u'subject', message)

    def test_taiga_task_changed_reassigned(self):
        message = u':busts_in_silhouette: Antek reassigned task **Aaaa** from Han Solo to Antek.\n'
        self.send_and_test_stream_message("task_changed_reassigned", u'subject', message)

    def test_taiga_task_changed_subject(self):
        message = u':notebook: Antek renamed task New task to **Even newer task**.\n'
        self.send_and_test_stream_message("task_changed_subject", u'subject', message)

    def test_taiga_task_changed_description(self):
        message = u':notebook: Antek updated description of task **Even newer task.**.\n'
        self.send_and_test_stream_message("task_changed_description", u'subject', message)

    def test_taiga_task_changed_us(self):
        message = u':clipboard: Antek moved task **A new task** from user story #3 Great US to #6 Greater US.\n'
        self.send_and_test_stream_message("task_changed_us", u'subject', message)

    def test_taiga_task_deleted(self):
        message = u':x: Antek deleted task **hhh**.\n'
        self.send_and_test_stream_message("task_deleted", u'subject', message)

    def test_taiga_milestone_created(self):
        message = u':calendar: Antek created sprint **New sprint**.\n'
        self.send_and_test_stream_message("milestone_created", u'subject', message)

    def test_taiga_milestone_deleted(self):
        message = u':x: Antek deleted sprint **Newer sprint**.\n'
        self.send_and_test_stream_message("milestone_deleted", u'subject', message)

    def test_taiga_milestone_changed_time(self):
        message = u':calendar: Antek changed estimated finish of sprint **New sprint** from 2016-04-27 to 2016-04-30.\n'
        self.send_and_test_stream_message("milestone_changed_time", u'subject', message)

    def test_taiga_milestone_changed_name(self):
        message = u':notebook: Antek renamed sprint from New sprint to **Newer sprint**.\n'
        self.send_and_test_stream_message("milestone_changed_name", u'subject', message)

    def test_taiga_issue_created(self):
        message = u':bulb: Antek created issue **A new issue**.\n'
        self.send_and_test_stream_message("issue_created", u'subject', message)

    def test_taiga_issue_deleted(self):
        message = u':x: Antek deleted issue **Aaaa**.\n'
        self.send_and_test_stream_message("issue_deleted", u'subject', message)

    def test_taiga_issue_changed_assigned(self):
        message = u':busts_in_silhouette: Antek assigned issue **Aaaa** to Antek.\n'
        self.send_and_test_stream_message("issue_changed_assigned", u'subject', message)

    def test_taiga_issue_changed_reassigned(self):
        message = u':busts_in_silhouette: Antek reassigned issue **Aaaa** from Antek to Han Solo.\n'
        self.send_and_test_stream_message("issue_changed_reassigned", u'subject', message)

    def test_taiga_issue_changed_subject(self):
        message = u':notebook: Antek renamed issue Aaaa to **More descriptive name**.\n'
        self.send_and_test_stream_message("issue_changed_subject", u'subject', message)

    def test_taiga_issue_changed_description(self):
        message = u':notebook: Antek updated description of issue **More descriptive name**.\n'
        self.send_and_test_stream_message("issue_changed_description", u'subject', message)

    def test_taiga_issue_changed_type(self):
        message = u':bulb: Antek changed type of issue **A new issue** from Bug to Enhancement.\n'
        self.send_and_test_stream_message("issue_changed_type", u'subject', message)

    def test_taiga_issue_changed_status(self):
        message = u':chart_with_upwards_trend: Antek changed status of issue **A new issue** from New to Rejected.\n'
        self.send_and_test_stream_message("issue_changed_status", u'subject', message)

    def test_taiga_issue_changed_severity(self):
        message = u':warning: Antek changed severity of issue **A new issue** from Important to Critical.\n'
        self.send_and_test_stream_message("issue_changed_severity", u'subject', message)

    def test_taiga_issue_changed_priority(self):
        message = u':rocket: Antek changed priority of issue **A new issue** from Normal to High.\n'
        self.send_and_test_stream_message("issue_changed_priority", u'subject', message)

    def test_taiga_userstory_comment_added(self):
        message = u':thought_balloon: Han Solo commented on user story **Great US**.\n'
        self.send_and_test_stream_message("userstory_changed_comment_added", u'subject', message)

    def test_taiga_task_changed_comment_added(self):
        message = u':thought_balloon: Antek commented on task **New task assigned and in progress**.\n'
        self.send_and_test_stream_message("task_changed_comment_added", u'subject', message)

    def test_taiga_issue_changed_comment_added(self):
        message = u':thought_balloon: Antek commented on issue **Aaaa**.\n'
        self.send_and_test_stream_message("issue_changed_comment_added", u'subject', message)

class CircleCiHookTests(WebhookTestCase):
    STREAM_NAME = 'circleci'
    URL_TEMPLATE = "/api/v1/external/circleci?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'circleci'

    def test_circleci_build_in_success_status(self):
        expected_subject = u"RepoName"
        expected_message = u"[Build](https://circleci.com/gh/username/project/build_number) triggered by username on master branch succeeded."
        self.send_and_test_stream_message('build_passed', expected_subject, expected_message)

    def test_circleci_build_in_failed_status(self):
        expected_subject = u"RepoName"
        expected_message = u"[Build](https://circleci.com/gh/username/project/build_number) triggered by username on master branch failed."
        self.send_and_test_stream_message('build_failed', expected_subject, expected_message)

    def test_circleci_build_in_failed_status_when_previous_build_failed_too(self):
        expected_subject = u"RepoName"
        expected_message = u"[Build](https://circleci.com/gh/username/project/build_number) triggered by username on master branch is still failing."
        self.send_and_test_stream_message('build_failed_when_previous_build_failed', expected_subject, expected_message)

    def test_circleci_build_in_success_status_when_previous_build_failed_too(self):
        expected_subject = u"RepoName"
        expected_message = u"[Build](https://circleci.com/gh/username/project/build_number) triggered by username on master branch fixed."
        self.send_and_test_stream_message('build_passed_when_previous_build_failed', expected_subject, expected_message)

class TransifexHookTests(WebhookTestCase):
    STREAM_NAME = 'transifex'
    URL_TEMPLATE = "/api/v1/external/transifex?stream={stream}&api_key={api_key}&{data_template}"
    URL_DATA_TEMPLATE = "project={project}&language={language}&resource={resource}&{method}"
    URL_REVIEWED_METHOD_TEMPLATE = "reviewed=100"
    URL_TRANSLATED_METHOD_TEMPLATE = "translated=100"
    FIXTURE_DIR_NAME = 'transifex'

    PROJECT = 'project-title'
    LANGUAGE = 'en'
    RESOURCE = 'file'
    REVIEWED = True

    def test_transifex_reviewed_message(self):
        self.REVIEWED = True
        expected_subject = "{} in {}".format(self.PROJECT, self.LANGUAGE)
        expected_message = "Resource {} fully reviewed.".format(self.RESOURCE)
        self.url = self.build_webhook_url()
        self.send_and_test_stream_message(None, expected_subject, expected_message)

    def test_transifex_translated_message(self):
        self.REVIEWED = False
        expected_subject = "{} in {}".format(self.PROJECT, self.LANGUAGE)
        expected_message = "Resource {} fully translated.".format(self.RESOURCE)
        self.url = self.build_webhook_url()
        self.send_and_test_stream_message(None, expected_subject, expected_message)
        self.REVIEWED = True

    def build_webhook_url(self):
        url_data = self.URL_DATA_TEMPLATE.format(
            project=self.PROJECT,
            language=self.LANGUAGE,
            resource=self.RESOURCE,
            method=self.URL_REVIEWED_METHOD_TEMPLATE if self.REVIEWED else self.URL_TRANSLATED_METHOD_TEMPLATE
        )
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        return self.URL_TEMPLATE.format(api_key=api_key, stream=self.STREAM_NAME, data_template=url_data)

    def get_body(self, fixture_name):
        return {}

class CrashlyticsHookTests(WebhookTestCase):
    STREAM_NAME = 'crashlytics'
    URL_TEMPLATE = "/api/v1/external/crashlytics?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'crashlytics'

    def test_crashlytics_verification_message(self):
        last_message_before_request = self.get_last_message()
        payload = self.get_body('verification')
        url = self.build_webhook_url()
        result = self.client.post(url, payload, content_type="application/json")
        last_message_after_request = self.get_last_message()
        self.assert_json_success(result)
        self.assertEqual(last_message_after_request.pk, last_message_before_request.pk)

    def test_crashlytics_build_in_success_status(self):
        expected_subject = u"123: Issue Title"
        expected_message = u"[Issue](http://crashlytics.com/full/url/to/issue) impacts at least 16 device(s)."
        self.send_and_test_stream_message('issue_message', expected_subject, expected_message)

class AirbrakeHookTests(WebhookTestCase):
    STREAM_NAME = 'airbrake'
    URL_TEMPLATE = "/api/v1/external/airbrake?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'airbrake'

    def test_airbrake_error_message(self):
        expected_subject = u"ZulipIntegrationTest"
        expected_message = u"[ZeroDivisionError](https://zulip.airbrake.io/projects/125209/groups/1705190192091077626): \"Error message from logger\" occurred."
        self.send_and_test_stream_message('error_message', expected_subject, expected_message)

class UpdownHookTests(WebhookTestCase):
    STREAM_NAME = 'updown'
    URL_TEMPLATE = "/api/v1/external/updown?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'updown'

    def test_updown_check_down_event(self):
        expected_subject = u"https://updown.io"
        expected_message = u"Service is `down`. It returned \"500\" error at 07-02-2016 13:11."
        self.send_and_test_stream_message('check_down_one_event', expected_subject, expected_message)

    def test_updown_check_up_again_event(self):
        expected_subject = u"https://updown.io"
        expected_message = u"Service is `up` again after 4 minutes 25 seconds."
        self.send_and_test_stream_message('check_up_again_one_event', expected_subject, expected_message)

    def test_updown_check_up_event(self):
        expected_subject = u"https://updown.io"
        expected_message = u"Service is `up`."
        self.send_and_test_stream_message('check_up_first_time', expected_subject, expected_message)

    def test_updown_check_up_multiple_events(self):
        first_message_expected_subject = u"https://updown.io"
        first_message_expected_message = u"Service is `up` again after 1 second."

        second_message_expected_subject = u"https://updown.io"
        second_message_expected_message = u"Service is `down`. It returned \"500\" error at 07-02-2016 13:11."

        self.send_and_test_stream_message('check_multiple_events')
        last_message = self.get_last_message()
        self.do_test_subject(last_message, first_message_expected_subject)
        self.do_test_message(last_message, first_message_expected_message)

        second_to_last_message = self.get_second_to_last_message()
        self.do_test_subject(second_to_last_message, second_message_expected_subject)
        self.do_test_message(second_to_last_message, second_message_expected_message)
