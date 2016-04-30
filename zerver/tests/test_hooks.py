# -*- coding: utf-8 -*-
from zerver.lib.test_helpers import AuthedTestCase
from zerver.lib.test_runner import slow
from zerver.models import Message, Recipient

import ujson
from six.moves import urllib

class JiraHookTests(AuthedTestCase):

    def send_jira_message(self, action):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        url = "/api/v1/external/jira?api_key=%s" % (api_key,)
        return self.send_json_payload(email,
                                      url,
                                      self.fixture_data('jira', action),
                                      stream_name="jira",
                                      content_type="application/json")

    def test_unknown(self):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        url = "/api/v1/external/jira?api_key=%s" % (api_key,)

        result = self.client.post(url, self.fixture_data('jira', 'unknown'),
                                  stream_name="jira",
                                  content_type="application/json")

        self.assert_json_error(result, 'Unknown JIRA event type')

    def test_custom_stream(self):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        action = 'created'
        url = "/api/v1/external/jira?api_key=%s&stream=jira_custom" % (api_key,)
        msg = self.send_json_payload(email, url,
                                     self.fixture_data('jira', action),
                                     stream_name="jira_custom",
                                     content_type="application/json")
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **created** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) priority Major, assigned to @**no one**:

> New bug with hook""")

    def test_created(self):
        msg = self.send_jira_message('created')
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **created** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) priority Major, assigned to @**no one**:

> New bug with hook""")

    def test_created_assignee(self):
        msg = self.send_jira_message('created_assignee')
        self.assertEqual(msg.subject, "TEST-4: Test Created Assignee")
        self.assertEqual(msg.content, """Leonardo Franchi [Administrator] **created** [TEST-4](https://zulipp.atlassian.net/browse/TEST-4) priority Major, assigned to @**Leonardo Franchi [Administrator]**:

> Test Created Assignee""")

    def test_commented(self):
        msg = self.send_jira_message('commented')
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **updated** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) (assigned to @**Othello, the Moor of Venice**):


Adding a comment. Oh, what a comment it is!
""")

    def test_commented_markup(self):
        msg = self.send_jira_message('commented_markup')
        self.assertEqual(msg.subject, "TEST-7: Testing of rich text")
        self.assertEqual(msg.content, """Leonardo Franchi [Administrator] **updated** [TEST-7](https://zulipp.atlassian.net/browse/TEST-7):\n\n\nThis is a comment that likes to **exercise** a lot of _different_ `conventions` that `jira uses`.\r\n\r\n~~~\n\r\nthis code is not highlighted, but monospaced\r\n\n~~~\r\n\r\n~~~\n\r\ndef python():\r\n    print "likes to be formatted"\r\n\n~~~\r\n\r\n[http://www.google.com](http://www.google.com) is a bare link, and [Google](http://www.google.com) is given a title.\r\n\r\nThanks!\r\n\r\n~~~ quote\n\r\nSomeone said somewhere\r\n\n~~~\n""")

    def test_deleted(self):
        msg = self.send_jira_message('deleted')
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, "Leo Franchi **deleted** [BUG-15](http://lfranchi.com:8080/browse/BUG-15)!")

    def test_reassigned(self):
        msg = self.send_jira_message('reassigned')
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **updated** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) (assigned to @**Othello, the Moor of Venice**):

* Changed assignee from **None** to @**Othello, the Moor of Venice**
""")

    def test_reopened(self):
        msg = self.send_jira_message('reopened')
        self.assertEqual(msg.subject, "BUG-7: More cowbell polease")
        self.assertEqual(msg.content, """Leo Franchi **updated** [BUG-7](http://lfranchi.com:8080/browse/BUG-7) (assigned to @**Othello, the Moor of Venice**):

* Changed resolution from **Fixed** to **None**
* Changed status from **Resolved** to **Reopened**

Re-opened yeah!
""")

    def test_resolved(self):
        msg = self.send_jira_message('resolved')

        self.assertEqual(msg.subject, "BUG-13: Refreshing the page loses the user's current posi...")
        self.assertEqual(msg.content, """Leo Franchi **updated** [BUG-13](http://lfranchi.com:8080/browse/BUG-13) (assigned to @**Othello, the Moor of Venice**):

* Changed status from **Open** to **Resolved**
* Changed assignee from **None** to @**Othello, the Moor of Venice**
* Changed resolution from **None** to **Fixed**

Fixed it, finally!
""")

    def test_workflow_postfuncion(self):
        msg = self.send_jira_message('postfunction_hook')

        self.assertEqual(msg.subject, "TEST-5: PostTest")
        self.assertEqual(msg.content, """Leo Franchi [Administrator] **transitioned** [TEST-5](https://lfranchi-test.atlassian.net/browse/TEST-5) from Resolved to Reopened""")

    def test_workflow_postfunction(self):
        msg = self.send_jira_message('postfunction_hook')

        self.assertEqual(msg.subject, "TEST-5: PostTest")
        self.assertEqual(msg.content, """Leo Franchi [Administrator] **transitioned** [TEST-5](https://lfranchi-test.atlassian.net/browse/TEST-5) from Resolved to Reopened""")

    def test_workflow_postfunction_started(self):
        msg = self.send_jira_message('postfunction_started')

        self.assertEqual(msg.subject, "TEST-7: Gluttony of Post Functions")
        self.assertEqual(msg.content, """Leo Franchi [Administrator] **transitioned** [TEST-7](https://lfranchi-test.atlassian.net/browse/TEST-7) from Open to Underway""")

    def test_workflow_postfunction_resolved(self):
        msg = self.send_jira_message('postfunction_resolved')

        self.assertEqual(msg.subject, "TEST-7: Gluttony of Post Functions")
        self.assertEqual(msg.content, """Leo Franchi [Administrator] **transitioned** [TEST-7](https://lfranchi-test.atlassian.net/browse/TEST-7) from Open to Resolved""")

    def test_mention(self):
        msg = self.send_jira_message('watch_mention_updated')
        self.assertEqual(msg.subject, "TEST-5: Lunch Decision Needed")
        self.assertEqual(msg.content, """Leonardo Franchi [Administrator] **updated** [TEST-5](https://zulipp.atlassian.net/browse/TEST-5) (assigned to @**Othello, the Moor of Venice**):


Making a comment, @**Othello, the Moor of Venice** is watching this issue
""")

    def test_priority_updated(self):
        msg = self.send_jira_message('updated_priority')
        self.assertEqual(msg.subject, "TEST-1: Fix That")
        self.assertEqual(msg.content, """Leonardo Franchi [Administrator] **updated** [TEST-1](https://zulipp.atlassian.net/browse/TEST-1) (assigned to **leo@zulip.com**):

* Changed priority from **Critical** to **Major**
""")

class BeanstalkHookTests(AuthedTestCase):
    def send_beanstalk_message(self, action):
        email = "hamlet@zulip.com"
        data = {'payload': self.fixture_data('beanstalk', action)}
        return self.send_json_payload(email, "/api/v1/external/beanstalk",
                                      data,
                                      stream_name="commits",
                                      **self.api_auth(email))

    def test_git_single(self):
        msg = self.send_beanstalk_message('git_singlecommit')
        self.assertEqual(msg.subject, "work-test")
        self.assertEqual(msg.content, """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) to branch master

* [e50508d](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df): add some stuff
""")

    @slow(0.20, "lots of queries")
    def test_git_multiple(self):
        msg = self.send_beanstalk_message('git_multiple')
        self.assertEqual(msg.subject, "work-test")
        self.assertEqual(msg.content, """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) to branch master

* [edf529c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7): Added new file
* [c2a191b](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9): Filled in new file with some stuff
* [2009815](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158): More work to fix some bugs
""")

    def test_svn_addremove(self):
        msg = self.send_beanstalk_message('svn_addremove')
        self.assertEqual(msg.subject, "svn r3")
        self.assertEqual(msg.content, """Leo Franchi pushed [revision 3](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/3):

> Removed a file and added another one!""")

    def test_svn_changefile(self):
        msg = self.send_beanstalk_message('svn_changefile')
        self.assertEqual(msg.subject, "svn r2")
        self.assertEqual(msg.content, """Leo Franchi pushed [revision 2](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/2):

> Added some code""")

class GithubV1HookTests(AuthedTestCase):

    push_content = """zbenjamin [pushed](https://github.com/zbenjamin/zulip-test/compare/4f9adc4777d5...b95449196980) to branch master

* [48c329a](https://github.com/zbenjamin/zulip-test/commit/48c329a0b68a9a379ff195ee3f1c1f4ab0b2a89e): Add baz
* [06ebe5f](https://github.com/zbenjamin/zulip-test/commit/06ebe5f472a32f6f31fd2a665f0c7442b69cce72): Baz needs to be longer
* [b954491](https://github.com/zbenjamin/zulip-test/commit/b95449196980507f08209bdfdc4f1d611689b7a8): Final edit to baz, I swear
"""

    def test_spam_branch_is_ignored(self):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        stream = 'commits'
        data = ujson.loads(self.fixture_data('github', 'v1_push'))
        data.update({'email': email,
                     'api-key': api_key,
                     'branches': 'dev,staging',
                     'stream': stream,
                     'payload': ujson.dumps(data['payload'])})
        url = '/api/v1/external/github'

        # We subscribe to the stream in this test, even though
        # it won't get written, to avoid failing for the wrong
        # reason.
        self.subscribe_to_stream(email, stream)

        prior_count = Message.objects.count()

        result = self.client.post(url, data)
        self.assert_json_success(result)

        after_count = Message.objects.count()
        self.assertEqual(prior_count, after_count)


    def basic_test(self, fixture_name, stream_name, expected_subject, expected_content, send_stream=False, branches=None):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        data = ujson.loads(self.fixture_data('github', 'v1_' + fixture_name))
        data.update({'email': email,
                     'api-key': api_key,
                     'payload': ujson.dumps(data['payload'])})
        if send_stream:
            data['stream'] = stream_name
        if branches is not None:
            data['branches'] = branches
        msg = self.send_json_payload(email, "/api/v1/external/github",
                                     data,
                                     stream_name=stream_name)
        self.assertEqual(msg.subject, expected_subject)
        self.assertEqual(msg.content, expected_content)

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

class GithubV2HookTests(AuthedTestCase):

    push_content = """zbenjamin [pushed](https://github.com/zbenjamin/zulip-test/compare/4f9adc4777d5...b95449196980) to branch master

* [48c329a](https://github.com/zbenjamin/zulip-test/commit/48c329a0b68a9a379ff195ee3f1c1f4ab0b2a89e): Add baz
* [06ebe5f](https://github.com/zbenjamin/zulip-test/commit/06ebe5f472a32f6f31fd2a665f0c7442b69cce72): Baz needs to be longer
* [b954491](https://github.com/zbenjamin/zulip-test/commit/b95449196980507f08209bdfdc4f1d611689b7a8): Final edit to baz, I swear
"""

    def test_spam_branch_is_ignored(self):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        stream = 'commits'
        data = ujson.loads(self.fixture_data('github', 'v2_push'))
        data.update({'email': email,
                     'api-key': api_key,
                     'branches': 'dev,staging',
                     'stream': stream,
                     'payload': ujson.dumps(data['payload'])})
        url = '/api/v1/external/github'

        # We subscribe to the stream in this test, even though
        # it won't get written, to avoid failing for the wrong
        # reason.
        self.subscribe_to_stream(email, stream)

        prior_count = Message.objects.count()

        result = self.client.post(url, data)
        self.assert_json_success(result)

        after_count = Message.objects.count()
        self.assertEqual(prior_count, after_count)


    def basic_test(self, fixture_name, stream_name, expected_subject, expected_content, send_stream=False, branches=None):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        data = ujson.loads(self.fixture_data('github', 'v2_' + fixture_name))
        data.update({'email': email,
                     'api-key': api_key,
                     'payload': ujson.dumps(data['payload'])})
        if send_stream:
            data['stream'] = stream_name
        if branches is not None:
            data['branches'] = branches
        msg = self.send_json_payload(email, "/api/v1/external/github",
                                     data,
                                     stream_name=stream_name)
        self.assertEqual(msg.subject, expected_subject)
        self.assertEqual(msg.content, expected_content)

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

class PivotalV3HookTests(AuthedTestCase):

    def send_pivotal_message(self, name):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        return self.send_json_payload(email, "/api/v1/external/pivotal?api_key=%s&stream=%s" % (api_key, "pivotal"),
                                      self.fixture_data('pivotal', name, file_type='xml'),
                                      stream_name="pivotal",
                                      content_type="application/xml")

    def test_accepted(self):
        msg = self.send_pivotal_message('accepted')
        self.assertEqual(msg.subject, 'My new Feature story')
        self.assertEqual(msg.content, 'Leo Franchi accepted "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)')

    def test_commented(self):
        msg = self.send_pivotal_message('commented')
        self.assertEqual(msg.subject, 'Comment added')
        self.assertEqual(msg.content, 'Leo Franchi added comment: "FIX THIS NOW" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)')

    def test_created(self):
        msg = self.send_pivotal_message('created')
        self.assertEqual(msg.subject, 'My new Feature story')
        self.assertEqual(msg.content, 'Leo Franchi added "My new Feature story" \
(unscheduled feature):\n\n~~~ quote\nThis is my long description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)')

    def test_delivered(self):
        msg = self.send_pivotal_message('delivered')
        self.assertEqual(msg.subject, 'Another new story')
        self.assertEqual(msg.content, 'Leo Franchi delivered "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)')

    def test_finished(self):
        msg = self.send_pivotal_message('finished')
        self.assertEqual(msg.subject, 'Another new story')
        self.assertEqual(msg.content, 'Leo Franchi finished "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)')

    def test_moved(self):
        msg = self.send_pivotal_message('moved')
        self.assertEqual(msg.subject, 'My new Feature story')
        self.assertEqual(msg.content, 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)')

    def test_rejected(self):
        msg = self.send_pivotal_message('rejected')
        self.assertEqual(msg.subject, 'Another new story')
        self.assertEqual(msg.content, 'Leo Franchi rejected "Another new story" with comments: \
"Not good enough, sorry" [(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)')

    def test_started(self):
        msg = self.send_pivotal_message('started')
        self.assertEqual(msg.subject, 'Another new story')
        self.assertEqual(msg.content, 'Leo Franchi started "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)')

    def test_created_estimate(self):
        msg = self.send_pivotal_message('created_estimate')
        self.assertEqual(msg.subject, 'Another new story')
        self.assertEqual(msg.content, 'Leo Franchi added "Another new story" \
(unscheduled feature worth 2 story points):\n\n~~~ quote\nSome loong description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)')

    def test_type_changed(self):
        msg = self.send_pivotal_message('type_changed')
        self.assertEqual(msg.subject, 'My new Feature story')
        self.assertEqual(msg.content, 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)')

class PivotalV5HookTests(AuthedTestCase):
    def send_pivotal_message(self, name):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        return self.send_json_payload(email, "/api/v1/external/pivotal?api_key=%s&stream=%s" % (api_key, "pivotal"),
                                      self.fixture_data('pivotal', "v5_" + name, file_type='json'),
                                      stream_name="pivotal",
                                      content_type="application/xml")

    def test_accepted(self):
        msg = self.send_pivotal_message('accepted')
        self.assertEqual(msg.subject, '#63486316: Story of the Year')
        self.assertEqual(msg.content, """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **unstarted** to **accepted**
""")

    def test_commented(self):
        msg = self.send_pivotal_message('commented')
        self.assertEqual(msg.subject, '#63486316: Story of the Year')
        self.assertEqual(msg.content, """Leo Franchi added a comment to [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
~~~quote
A comment on the story
~~~""")

    def test_created(self):
        msg = self.send_pivotal_message('created')
        self.assertEqual(msg.subject, '#63495662: Story that I created')
        self.assertEqual(msg.content, """Leo Franchi created bug: [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story that I created](http://www.pivotaltracker.com/story/show/63495662)
* State is **unscheduled**
* Description is

> What a description""")

    def test_delivered(self):
        msg = self.send_pivotal_message('delivered')
        self.assertEqual(msg.subject, '#63486316: Story of the Year')
        self.assertEqual(msg.content, """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **accepted** to **delivered**
""")

    def test_finished(self):
        msg = self.send_pivotal_message('finished')
        self.assertEqual(msg.subject, '#63486316: Story of the Year')
        self.assertEqual(msg.content, """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **delivered** to **accepted**
""")

    def test_moved(self):
        msg = self.send_pivotal_message('moved')
        self.assertEqual(msg.subject, '#63496066: Pivotal Test')
        self.assertEqual(msg.content, """Leo Franchi moved [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066) from **unstarted** to **unscheduled**""")

    def test_rejected(self):
        msg = self.send_pivotal_message('rejected')
        self.assertEqual(msg.subject, '#63486316: Story of the Year')
        self.assertEqual(msg.content, """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* Comment added:
~~~quote
Try again next time
~~~
* state changed from **delivered** to **rejected**
""")

    def test_started(self):
        msg = self.send_pivotal_message('started')
        self.assertEqual(msg.subject, '#63495972: Fresh Story')
        self.assertEqual(msg.content, """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Fresh Story](http://www.pivotaltracker.com/story/show/63495972):
* state changed from **unstarted** to **started**
""")

    def test_created_estimate(self):
        msg = self.send_pivotal_message('created_estimate')
        self.assertEqual(msg.subject, '#63496066: Pivotal Test')
        self.assertEqual(msg.content, """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066):
* estimate is now **3 points**
""")

    def test_type_changed(self):
        msg = self.send_pivotal_message('type_changed')
        self.assertEqual(msg.subject, '#63496066: Pivotal Test')
        self.assertEqual(msg.content, """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066):
* estimate changed from 3 to **0 points**
* type changed from **feature** to **bug**
""")

class NewRelicHookTests(AuthedTestCase):
    def send_new_relic_message(self, name):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        return self.send_json_payload(email, "/api/v1/external/newrelic?api_key=%s&stream=%s" % (api_key, "newrelic"),
                                      self.fixture_data('newrelic', name, file_type='txt'),
                                      stream_name="newrelic",
                                      content_type="application/x-www-form-urlencoded")

    def test_alert(self):
        msg = self.send_new_relic_message('alert')
        self.assertEqual(msg.subject, "Apdex score fell below critical level of 0.90")
        self.assertEqual(msg.content, 'Alert opened on [application name]: \
Apdex score fell below critical level of 0.90\n\
[View alert](https://rpm.newrelc.com/accounts/[account_id]/applications/[application_id]/incidents/[incident_id])')

    def test_deployment(self):
        msg = self.send_new_relic_message('deployment')
        self.assertEqual(msg.subject, 'Test App deploy')
        self.assertEqual(msg.content, '`1242` deployed by **Zulip Test**\n\
Description sent via curl\n\nChangelog string')

class StashHookTests(AuthedTestCase):
    def test_stash_message(self):
        """
        Messages are generated by Stash on a `git push`.

        The subject describes the repo and Stash "project". The
        content describes the commits pushed.
        """
        email = "hamlet@zulip.com"
        msg = self.send_json_payload(
            email, "/api/v1/external/stash?stream=commits",
            self.fixture_data("stash", "push", file_type="json"),
            stream_name="commits",
            content_type="application/x-www-form-urlencoded",
            **self.api_auth(email))

        self.assertEqual(msg.subject, u"Secret project/Operation unicorn: master")
        self.assertEqual(msg.content, """`f259e90` was pushed to **master** in **Secret project/Operation unicorn** with:

* `f259e90`: Updating poms ...""")

class FreshdeskHookTests(AuthedTestCase):
    def generate_webhook_response(self, fixture):
        """
        Helper function to handle the webhook boilerplate.
        """
        email = "hamlet@zulip.com"
        return self.send_json_payload(
            email, "/api/v1/external/freshdesk?stream=freshdesk",
            self.fixture_data("freshdesk", fixture, file_type="json"),
            stream_name="freshdesk",
            content_type="application/x-www-form-urlencoded",
            **self.api_auth(email))

    def test_ticket_creation(self):
        """
        Messages are generated on ticket creation through Freshdesk's
        "Dispatch'r" service.
        """
        msg = self.generate_webhook_response("ticket_created")
        self.assertEqual(msg.subject, u"#11: Test ticket subject ☃")
        self.assertEqual(msg.content, u"""Requester ☃ Bob <requester-bob@example.com> created [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

~~~ quote
Test ticket description ☃.
~~~

Type: **Incident**
Priority: **High**
Status: **Pending**""")

    def test_status_change(self):
        """
        Messages are generated when a ticket's status changes through
        Freshdesk's "Observer" service.
        """
        msg = self.generate_webhook_response("status_changed")
        self.assertEqual(msg.subject, u"#11: Test ticket subject ☃")
        self.assertEqual(msg.content, """Requester Bob <requester-bob@example.com> updated [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

Status: **Resolved** => **Waiting on Customer**""")

    def test_priority_change(self):
        """
        Messages are generated when a ticket's priority changes through
        Freshdesk's "Observer" service.
        """
        msg = self.generate_webhook_response("priority_changed")
        self.assertEqual(msg.subject, u"#11: Test ticket subject")
        self.assertEqual(msg.content, """Requester Bob <requester-bob@example.com> updated [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

Priority: **High** => **Low**""")

    def note_change(self, fixture, note_type):
        """
        Messages are generated when a note gets added to a ticket through
        Freshdesk's "Observer" service.
        """
        msg = self.generate_webhook_response(fixture)
        self.assertEqual(msg.subject, u"#11: Test ticket subject")
        self.assertEqual(msg.content, """Requester Bob <requester-bob@example.com> added a %s note to [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11).""" % (note_type,))

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
        msg = self.generate_webhook_response("inline_images")
        self.assertEqual(msg.subject, u"#12: Not enough ☃ guinea pigs")
        self.assertIn("[guinea_pig.png](http://cdn.freshdesk.com/data/helpdesk/attachments/production/12744808/original/guinea_pig.png)", msg.content)

class ZenDeskHookTests(AuthedTestCase):

    def generate_webhook_response(self, ticket_title='User can\'t login',
                                  ticket_id=54, message='Message',
                                  stream_name='zendesk'):
        data = {
            'ticket_title': ticket_title,
            'ticket_id': ticket_id,
            'message': message,
            'stream': stream_name,
        }
        email = 'hamlet@zulip.com'
        self.subscribe_to_stream(email, stream_name)
        result = self.client.post('/api/v1/external/zendesk', data,
                                  **self.api_auth(email))
        self.assert_json_success(result)

        # Check the correct message was sent
        msg = self.get_last_message()
        self.assertEqual(msg.sender.email, email)

        return msg

    def test_subject(self):
        msg = self.generate_webhook_response(ticket_id=4, ticket_title="Test ticket")
        self.assertEqual(msg.subject, '#4: Test ticket')

    def test_long_subject(self):
        msg = self.generate_webhook_response(ticket_id=4, ticket_title="Test ticket" + '!' * 80)
        self.assertEqual(msg.subject, '#4: Test ticket' + '!' * 42 + '...')

    def test_content(self):
        msg = self.generate_webhook_response(message='New comment:\n> It is better\n* here')
        self.assertEqual(msg.content, 'New comment:\n> It is better\n* here')


class PagerDutyHookTests(AuthedTestCase):

    def send_webhook(self, data, stream_name, topic=None):
        email = 'hamlet@zulip.com'
        self.subscribe_to_stream(email, stream_name)
        api_key = self.get_api_key(email)
        if topic:
            url = '/api/v1/external/pagerduty?api_key=%s&stream=%s&topic=%s' % (api_key, stream_name, topic)
        else:
            url = '/api/v1/external/pagerduty?api_key=%s&stream=%s' % (api_key, stream_name)
        result = self.client.post(url, ujson.dumps(data), content_type="application/json")
        self.assert_json_success(result)

        # Check the correct message was sent
        msg = self.get_last_message()
        self.assertEqual(msg.sender.email, email)

        return msg

    def test_trigger(self):
        data = ujson.loads(self.fixture_data('pagerduty', 'trigger'))
        msg = self.send_webhook(data, 'pagerduty')
        self.assertEqual(msg.subject, 'incident 3')
        self.assertEqual(
            msg.content,
            ':imp: Incident [3](https://zulip-test.pagerduty.com/incidents/P140S4Y) triggered by [Test service](https://zulip-test.pagerduty.com/services/PIL5CUQ) and assigned to [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>foo'
        )

    def test_unacknowledge(self):
        data = ujson.loads(self.fixture_data('pagerduty', 'unacknowledge'))
        msg = self.send_webhook(data, 'pagerduty')
        self.assertEqual(msg.subject, 'incident 3')
        self.assertEqual(
            msg.content,
            ':imp: Incident [3](https://zulip-test.pagerduty.com/incidents/P140S4Y) unacknowledged by [Test service](https://zulip-test.pagerduty.com/services/PIL5CUQ) and assigned to [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>foo'
        )

    def test_resolved(self):
        data = ujson.loads(self.fixture_data('pagerduty', 'resolved'))
        msg = self.send_webhook(data, 'pagerduty')
        self.assertEqual(msg.subject, 'incident 1')
        self.assertEqual(
            msg.content,
            ':grinning: Incident [1](https://zulip-test.pagerduty.com/incidents/PO1XIJ5) resolved by [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>It is on fire'
        )

    def test_auto_resolved(self):
        data = ujson.loads(self.fixture_data('pagerduty', 'auto_resolved'))
        msg = self.send_webhook(data, 'pagerduty')
        self.assertEqual(msg.subject, 'incident 2')
        self.assertEqual(
            msg.content,
            ':grinning: Incident [2](https://zulip-test.pagerduty.com/incidents/PX7K9J2) resolved\n\n>new'
        )

    def test_acknowledge(self):
        data = ujson.loads(self.fixture_data('pagerduty', 'acknowledge'))
        msg = self.send_webhook(data, 'pagerduty')
        self.assertEqual(msg.subject, 'incident 1')
        self.assertEqual(
            msg.content,
            ':no_good: Incident [1](https://zulip-test.pagerduty.com/incidents/PO1XIJ5) acknowledged by [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>It is on fire'
        )

    def test_no_subject(self):
        data = ujson.loads(self.fixture_data('pagerduty', 'mp_fail'))
        msg = self.send_webhook(data, 'pagerduty')
        self.assertEqual(msg.subject, 'incident 48219')
        self.assertEqual(
            msg.content,
            u':grinning: Incident [48219](https://dropbox.pagerduty.com/incidents/PJKGZF9) resolved\n\n>mp_error_block_down_critical\u2119\u01b4'
        )

    def test_explicit_subject(self):
        data = ujson.loads(self.fixture_data('pagerduty', 'acknowledge'))
        msg = self.send_webhook(data, 'pagerduty', topic="my+cool+topic")
        self.assertEqual(msg.subject, 'my cool topic')
        self.assertEqual(
            msg.content,
            ':no_good: Incident [1](https://zulip-test.pagerduty.com/incidents/PO1XIJ5) acknowledged by [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>It is on fire'
        )

    def test_bad_message(self):
        data = {'messages': [{'type': 'incident.triggered'}]}
        msg = self.send_webhook(data, 'pagerduty')
        self.assertEqual(msg.subject, 'pagerduty')
        self.assertEqual(
            msg.content,
            'Unknown pagerduty message\n``` py\n{u\'type\': u\'incident.triggered\'}\n```'
        )

    def test_unknown_message_type(self):
        data = {'messages': [{'type': 'foo'}]}
        msg = self.send_webhook(data, 'pagerduty')
        self.assertEqual(msg.subject, 'pagerduty')
        self.assertEqual(
            msg.content,
            'Unknown pagerduty message\n``` py\n{u\'type\': u\'foo\'}\n```'
        )

class TravisHookTests(AuthedTestCase):
    def test_travis_message(self):
        """
        Build notifications are generated by Travis after build completes.

        The subject describes the repo and Stash "project". The
        content describes the commits pushed.
        """
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        body = urllib.parse.urlencode({'payload': self.fixture_data("travis", "build", file_type="json")})

        stream = "travis"
        url = "/api/v1/external/travis?stream=%s&topic=builds&api_key=%s" % (stream, api_key)
        self.subscribe_to_stream(email, stream)

        result = self.client.post(url,
                                  body,
                                  stream_name=stream,
                                  content_type="application/x-www-form-urlencoded")
        self.assert_json_success(result)

        msg = self.get_last_message()
        u'Author: josh_mandel\nBuild status: Passed :thumbsup:\nDetails: [changes](https://github.com/hl7-fhir/fhir-svn/compare/6dccb98bcfd9...6c457d366a31), [build log](https://travis-ci.org/hl7-fhir/fhir-svn/builds/92495257)'
        self.assertEqual(msg.subject, u"builds")
        self.assertEqual(msg.content, (u"Author: josh_mandel\nBuild status: Passed :thumbsup:\n"
                                       u"Details: [changes](https://github.com/hl7-fhir/fhir-sv"
                                       u"n/compare/6dccb98bcfd9...6c457d366a31), [build log](ht"
                                       u"tps://travis-ci.org/hl7-fhir/fhir-svn/builds/92495257)"))


class PingdomHookTests(AuthedTestCase):
    STREAM_NAME = 'pingdom'
    TEST_USER_EMAIL = 'hamlet@zulip.com'
    URL_TEMPLATE = "/api/v1/external/pingdom?stream={stream}&api_key={api_key}"

    def setUp(self):
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        self._url = self.URL_TEMPLATE.format(stream=self.STREAM_NAME, api_key=api_key)
        self.subscribe_to_stream(self.TEST_USER_EMAIL, self.STREAM_NAME)

    def test_pingdom_from_up_to_down_http_check_message(self):
        """
        Tests if pingdom http check from up to down is handled correctly
        """
        body = self._get_fixture_data('http_up_to_down')
        self._send_post_request_with_params(body)

        expected_message = u"Service someurl.com changed its HTTP status from UP to DOWN.\nDescription: Non-recoverable failure in name resolution."
        msg = self.get_last_message()
        self.assertEqual(msg.subject, u"Test check status.")
        self.assertEqual(msg.content, expected_message)

    def test_pingdom_from_up_to_down_smtp_check_message(self):
        """
        Tests if pingdom smtp check from up to down is handled correctly
        """
        body = self._get_fixture_data('smtp_up_to_down')
        self._send_post_request_with_params(body)

        expected_message = u"Service smtp.someurl.com changed its SMTP status from UP to DOWN.\nDescription: Connection refused."
        msg = self.get_last_message()
        self.assertEqual(msg.subject, u"SMTP check status.")
        self.assertEqual(msg.content, expected_message)

    def test_pingdom_from_up_to_down_imap_check_message(self):
        """
        Tests if pingdom imap check from up to down is handled correctly
        """
        body = self._get_fixture_data('imap_up_to_down')
        self._send_post_request_with_params(body)

        expected_message = u"Service imap.someurl.com changed its IMAP status from UP to DOWN.\nDescription: Invalid hostname, address or socket."
        msg = self.get_last_message()
        self.assertEqual(msg.subject, u"IMAP check status.")
        self.assertEqual(msg.content, expected_message)

    def test_pingdom_from_down_to_up_imap_check_message(self):
        """
        Tests if pingdom imap check from down to up is handled correctly
        """
        body = self._get_fixture_data('imap_down_to_up')
        self._send_post_request_with_params(body)

        expected_message = u"Service imap.someurl.com changed its IMAP status from DOWN to UP."
        msg = self.get_last_message()
        self.assertEqual(msg.subject, u"IMAP check status.")
        self.assertEqual(msg.content, expected_message)

    def _get_fixture_data(self, name):
        return ujson.dumps(ujson.loads(self.fixture_data('pingdom', name)))

    def _send_post_request_with_params(self, json):
        result = self.client.post(self._url, json, stream_name=self.STREAM_NAME, content_type="application/json")
        self.assert_json_success(result)

class YoHookTests(AuthedTestCase):
    def test_yo_message(self):
        """
        Yo App sends notification whenever user receives a new Yo from another user.
        """
        bot_email = "hamlet@zulip.com"
        api_key = self.get_api_key(bot_email)
        body = ""

        email = "cordelia@zulip.com"
        sender = "IAGO"
        ip = "127.0.0.1"
        url = "/api/v1/external/yo?email=%s&api_key=%s&username=%s&user_ip=%s" % (email, api_key, sender, ip)

        result = self.client.get(url, body,
                                 content_type="application/x-www-form-urlencoded")
        self.assert_json_success(result)

        msg = self.get_last_message()
        self.assertEqual(msg.content, (u"Yo from IAGO"))

class TeamcityHookTests(AuthedTestCase):
    def basic_test(self, type):
        """
        Build notifications are generated by Teamcity after build completes.
        """

        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        body = ujson.dumps(ujson.loads(self.fixture_data("teamcity", type)))

        stream = "teamcity"
        url = "/api/v1/external/teamcity?stream=%s&api_key=%s" % (stream, api_key)
        self.subscribe_to_stream(email, stream)

        result = self.client.post(url,
                                  body,
                                  stream_name=stream,
                                  content_type="application/json")
        self.assert_json_success(result)

        return self.get_last_message()

    def test_teamcity_success(self):
        msg = self.basic_test("success")
        self.assertEqual(msg.subject, u"Project :: Compile")
        self.assertEqual(msg.content, u"Project :: Compile build 5535 - CL 123456 was successful! :thumbsup:\nDetails: [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv), [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)")

    def test_teamcity_broken(self):
        msg = self.basic_test("broken")
        self.assertEqual(msg.subject, u"Project :: Compile")
        self.assertEqual(msg.content, u"Project :: Compile build 5535 - CL 123456 is broken with status Exit code 1 (new)! :thumbsdown:\nDetails: [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv), [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)")

    def test_teamcity_failure(self):
        msg = self.basic_test("failure")
        self.assertEqual(msg.subject, u"Project :: Compile")
        self.assertEqual(msg.content, u"Project :: Compile build 5535 - CL 123456 is still broken with status Exit code 1! :thumbsdown:\nDetails: [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv), [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)")

    def test_teamcity_fixed(self):
        msg = self.basic_test("fixed")
        self.assertEqual(msg.subject, u"Project :: Compile")
        self.assertEqual(msg.content, u"Project :: Compile build 5535 - CL 123456 has been fixed! :thumbsup:\nDetails: [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv), [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)")

    def test_teamcity_personal(self):
        msg = self.basic_test("personal")
        self.assertEqual(msg.recipient.type, Recipient.PERSONAL)
        self.assertEqual(msg.content, u"Your personal build of Project :: Compile build 5535 - CL 123456 is broken with status Exit code 1 (new)! :thumbsdown:\nDetails: [changes](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952&tab=buildChangesDiv), [build log](http://teamcity/viewLog.html?buildTypeId=Project_Compile&buildId=19952)")

class CodeshipHookTests(AuthedTestCase):
    STREAM_NAME = 'codeship'
    TEST_USER_EMAIL = 'hamlet@zulip.com'
    URL_TEMPLATE = "/api/v1/external/codeship?stream={stream}&api_key={api_key}"

    def setUp(self):
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        self._url = self.URL_TEMPLATE.format(stream=self.STREAM_NAME, api_key=api_key)
        self.subscribe_to_stream(self.TEST_USER_EMAIL, self.STREAM_NAME)

    def test_codeship_build_in_testing_status_message(self):
        """
        Tests if codeship testing status is mapped correctly
        """
        body = self._get_fixture_data('testing_build')
        self._send_post_request_with_params(body)

        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch started."
        msg = self.get_last_message()
        self.assertEqual(msg.subject, u"codeship/docs")
        self.assertEqual(msg.content, expected_message)

    def test_codeship_build_in_error_status_message(self):
        """
        Tests if codeship error status is mapped correctly
        """
        body = self._get_fixture_data('error_build')
        self._send_post_request_with_params(body)

        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch failed."
        msg = self.get_last_message()
        self.assertEqual(msg.subject, u"codeship/docs")
        self.assertEqual(msg.content, expected_message)

    def test_codeship_build_in_success_status_message(self):
        """
        Tests if codeship success status is mapped correctly
        """
        body = self._get_fixture_data('success_build')
        self._send_post_request_with_params(body)

        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch succeeded."
        msg = self.get_last_message()
        self.assertEqual(msg.subject, u"codeship/docs")
        self.assertEqual(msg.content, expected_message)

    def test_codeship_build_in_other_status_status_message(self):
        """
        Tests if codeship other status is mapped correctly
        """
        body = self._get_fixture_data('other_status_build')
        self._send_post_request_with_params(body)

        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch has some_other_status status."
        msg = self.get_last_message()
        self.assertEqual(msg.subject, u"codeship/docs")
        self.assertEqual(msg.content, expected_message)

    def _get_fixture_data(self, name):
        return ujson.dumps(ujson.loads(self.fixture_data('codeship', name)))

    def _send_post_request_with_params(self, json):
        result = self.client.post(self._url, json, stream_name=self.STREAM_NAME, content_type="application/json")
        self.assert_json_success(result)
        return result

class TaigaHookTests(AuthedTestCase):

    def send_taiga_message(self, action):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        stream = "taiga"
        topic = "subject"
        mesg = self.fixture_data("taiga", action, file_type="json")
        url = "/api/v1/external/taiga?stream=%s&topic=%s&api_key=%s" % (stream, topic, api_key)
        self.send_json_payload(email, url, mesg, stream_name=stream, content_type="application/json")
        return self.get_last_message()

    def test_taiga_userstory_deleted(self):
        msg = self.send_taiga_message("userstory_deleted")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':x: Antek deleted user story **A newer hope**.\n')

    def test_taiga_userstory_created(self):
        msg = self.send_taiga_message("userstory_created")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':package: Antek created user story **A new hope**.\n')

    def test_taiga_userstory_changed_unblocked(self):
        msg = self.send_taiga_message("userstory_changed_unblocked")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':unlock: Antek unblocked user story **A newer hope**.\n')

    def test_taiga_userstory_changed_subject(self):
        msg = self.send_taiga_message("userstory_changed_subject")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':notebook: Antek renamed user story from A new hope to **A newer hope**.\n')

    def test_taiga_userstory_changed_status(self):
        msg = self.send_taiga_message("userstory_changed_status")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':chart_with_upwards_trend: Antek changed status of user story **A new hope** from New to Done.\n')

    def test_taiga_userstory_changed_reassigned(self):
        msg = self.send_taiga_message("userstory_changed_reassigned")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':busts_in_silhouette: Antek reassigned user story **Great US** from Antek to Han Solo.\n')

    def test_taiga_userstory_changed_points(self):
        msg = self.send_taiga_message("userstory_changed_points")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':game_die: Antek changed estimation of user story **A new hope**.\n')

    def test_taiga_userstory_changed_new_milestone(self):
        msg = self.send_taiga_message("userstory_changed_new_milestone")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':calendar: Antek added user story **A newer hope** to sprint New sprint.\n')

    def test_taiga_userstory_changed_milestone(self):
        msg = self.send_taiga_message("userstory_changed_milestone")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':calendar: Antek changed sprint of user story **A newer hope** from Old sprint to New sprint.\n')

    def test_taiga_userstory_changed_description(self):
        msg = self.send_taiga_message("userstory_changed_description")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':notebook: Antek updated description of user story **A newer hope**.\n')

    def test_taiga_userstory_changed_closed(self):
        msg = self.send_taiga_message("userstory_changed_closed")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':chart_with_upwards_trend: Antek changed status of user story **A newer hope** from New to Done.\n:checkered_flag: Antek closed user story **A newer hope**.\n')

    def test_taiga_userstory_changed_reopened(self):
        msg = self.send_taiga_message("userstory_changed_reopened")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':chart_with_upwards_trend: Antek changed status of user story **A newer hope** from Done to New.\n:package: Antek reopened user story **A newer hope**.\n')

    def test_taiga_userstory_changed_blocked(self):
        msg = self.send_taiga_message("userstory_changed_blocked")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':lock: Antek blocked user story **A newer hope**.\n')

    def test_taiga_userstory_changed_assigned(self):
        msg = self.send_taiga_message("userstory_changed_assigned")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':busts_in_silhouette: Antek assigned user story **Great US** to Antek.\n')

    def test_taiga_task_created(self):
        msg = self.send_taiga_message("task_created")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':clipboard: Antek created task **New task assigned and in progress**.\n')

    def test_taiga_task_changed_status(self):
        msg = self.send_taiga_message("task_changed_status")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':chart_with_upwards_trend: Antek changed status of task **New task assigned and in progress** from Ready for test to New.\n')

    def test_taiga_task_changed_blocked(self):
        msg = self.send_taiga_message("task_changed_blocked")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':lock: Antek blocked task **A new task**.\n')

    def test_taiga_task_changed_unblocked(self):
        msg = self.send_taiga_message("task_changed_unblocked")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':unlock: Antek unblocked task **A new task**.\n')

    def test_taiga_task_changed_assigned(self):
        msg = self.send_taiga_message("task_changed_assigned")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':busts_in_silhouette: Antek assigned task **Aaaa** to Antek.\n')

    def test_taiga_task_changed_reassigned(self):
        msg = self.send_taiga_message("task_changed_reassigned")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':busts_in_silhouette: Antek reassigned task **Aaaa** from Han Solo to Antek.\n')

    def test_taiga_task_changed_subject(self):
        msg = self.send_taiga_message("task_changed_subject")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':notebook: Antek renamed task New task to **Even newer task**.\n')

    def test_taiga_task_changed_description(self):
        msg = self.send_taiga_message("task_changed_description")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':notebook: Antek updated description of task **Even newer task.**.\n')

    def test_taiga_task_changed_us(self):
        msg = self.send_taiga_message("task_changed_us")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':clipboard: Antek moved task **A new task** from user story #3 Great US to #6 Greater US.\n')

    def test_taiga_task_deleted(self):
        msg = self.send_taiga_message("task_deleted")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':x: Antek deleted task **hhh**.\n')

    def test_taiga_milestone_created(self):
        msg = self.send_taiga_message("milestone_created")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':calendar: Antek created sprint **New sprint**.\n')

    def test_taiga_milestone_deleted(self):
        msg = self.send_taiga_message("milestone_deleted")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':x: Antek deleted sprint **Newer sprint**.\n')

    def test_taiga_milestone_changed_time(self):
        msg = self.send_taiga_message("milestone_changed_time")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':calendar: Antek changed estimated finish of sprint **New sprint** from 2016-04-27 to 2016-04-30.\n')

    def test_taiga_milestone_changed_name(self):
        msg = self.send_taiga_message("milestone_changed_name")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':notebook: Antek renamed sprint from New sprint to **Newer sprint**.\n')

    def test_taiga_issue_created(self):
        msg = self.send_taiga_message("issue_created")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':bulb: Antek created issue **A new issue**.\n')

    def test_taiga_issue_deleted(self):
        msg = self.send_taiga_message("issue_deleted")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':x: Antek deleted issue **Aaaa**.\n')

    def test_taiga_issue_changed_assigned(self):
        msg = self.send_taiga_message("issue_changed_assigned")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':busts_in_silhouette: Antek assigned issue **Aaaa** to Antek.\n')

    def test_taiga_issue_changed_reassigned(self):
        msg = self.send_taiga_message("issue_changed_reassigned")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':busts_in_silhouette: Antek reassigned issue **Aaaa** from Antek to Han Solo.\n')

    def test_taiga_issue_changed_subject(self):
        msg = self.send_taiga_message("issue_changed_subject")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':notebook: Antek renamed issue Aaaa to **More descriptive name**.\n')

    def test_taiga_issue_changed_description(self):
        msg = self.send_taiga_message("issue_changed_description")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':notebook: Antek updated description of issue **More descriptive name**.\n')

    def test_taiga_issue_changed_type(self):
        msg = self.send_taiga_message("issue_changed_type")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':bulb: Antek changed type of issue **A new issue** from Bug to Enhancement.\n')

    def test_taiga_issue_changed_status(self):
        msg = self.send_taiga_message("issue_changed_status")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':chart_with_upwards_trend: Antek changed status of issue **A new issue** from New to Rejected.\n')

    def test_taiga_issue_changed_severity(self):
        msg = self.send_taiga_message("issue_changed_severity")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':warning: Antek changed severity of issue **A new issue** from Important to Critical.\n')

    def test_taiga_issue_changed_priority(self):
        msg = self.send_taiga_message("issue_changed_priority")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':rocket: Antek changed priority of issue **A new issue** from Normal to High.\n')

    def test_taiga_userstory_comment_added(self):
        msg = self.send_taiga_message("userstory_changed_comment_added")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':thought_balloon: Han Solo commented on user story **Great US**.\n')

    def test_taiga_task_changed_comment_added(self):
        msg = self.send_taiga_message("task_changed_comment_added")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':thought_balloon: Antek commented on task **New task assigned and in progress**.\n')

    def test_taiga_issue_changed_comment_added(self):
        msg = self.send_taiga_message("issue_changed_comment_added")
        self.assertEqual(msg.subject, u'subject')
        self.assertEqual(msg.content, u':thought_balloon: Antek commented on issue **Aaaa**.\n')
