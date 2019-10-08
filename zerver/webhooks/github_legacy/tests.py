from typing import Dict, Optional

import ujson

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.users import get_api_key
from zerver.lib.webhooks.git import COMMITS_LIMIT
from zerver.models import Message

class GithubV1HookTests(WebhookTestCase):
    STREAM_NAME = None  # type: Optional[str]
    URL_TEMPLATE = u"/api/v1/external/github"
    FIXTURE_DIR_NAME = 'github_legacy'
    SEND_STREAM = False
    BRANCHES = None  # type: Optional[str]

    push_content = u"""zbenjamin [pushed](https://github.com/zbenjamin/zulip-test/compare/4f9adc4777d5...b95449196980) 3 commits to branch master.

* Add baz ([48c329a](https://github.com/zbenjamin/zulip-test/commit/48c329a0b68a9a379ff195ee3f1c1f4ab0b2a89e))
* Baz needs to be longer ([06ebe5f](https://github.com/zbenjamin/zulip-test/commit/06ebe5f472a32f6f31fd2a665f0c7442b69cce72))
* Final edit to baz, I swear ([b954491](https://github.com/zbenjamin/zulip-test/commit/b95449196980507f08209bdfdc4f1d611689b7a8))"""

    def test_spam_branch_is_ignored(self) -> None:
        self.SEND_STREAM = True
        self.STREAM_NAME = 'commits'
        self.BRANCHES = 'dev,staging'
        data = self.get_body('push')

        # We subscribe to the stream in this test, even though
        # it won't get written, to avoid failing for the wrong
        # reason.
        self.subscribe(self.test_user, self.STREAM_NAME)

        prior_count = Message.objects.count()

        result = self.client_post(self.URL_TEMPLATE, data)
        self.assert_json_success(result)

        after_count = Message.objects.count()
        self.assertEqual(prior_count, after_count)

    def get_body(self, fixture_name: str) -> Dict[str, str]:
        api_key = get_api_key(self.test_user)
        data = ujson.loads(self.webhook_fixture_data(self.FIXTURE_DIR_NAME, 'v1_' + fixture_name))
        data.update({'email': self.TEST_USER_EMAIL,
                     'api-key': api_key,
                     'payload': ujson.dumps(data['payload'])})
        if self.SEND_STREAM:
            data['stream'] = self.STREAM_NAME

        if self.BRANCHES is not None:
            data['branches'] = self.BRANCHES
        return data

    def basic_test(self, fixture_name: str, stream_name: str,
                   expected_topic: str, expected_content: str,
                   send_stream: bool=False, branches: Optional[str]=None) -> None:
        self.STREAM_NAME = stream_name
        self.SEND_STREAM = send_stream
        self.BRANCHES = branches
        self.send_and_test_stream_message(fixture_name, expected_topic, expected_content, content_type=None)

    def test_user_specified_branches(self) -> None:
        self.basic_test('push', 'my_commits', 'zulip-test / master', self.push_content,
                        send_stream=True, branches="master,staging")

    def test_user_specified_stream(self) -> None:
        """Around May 2013 the github webhook started to specify the stream.
        Before then, the stream was hard coded to "commits"."""
        self.basic_test('push', 'my_commits', 'zulip-test / master', self.push_content,
                        send_stream=True)

    def test_legacy_hook(self) -> None:
        self.basic_test('push', 'commits', 'zulip-test / master', self.push_content)

    def test_push_multiple_commits(self) -> None:
        commit_info = "* Add baz ([48c329a](https://github.com/zbenjamin/zulip-test/commit/48c329a0b68a9a379ff195ee3f1c1f4ab0b2a89e))\n"
        expected_topic = "zbenjamin [pushed](https://github.com/zbenjamin/zulip-test/compare/4f9adc4777d5...b95449196980) 50 commits to branch master.\n\n{}[and {} more commit(s)]".format(
            commit_info * COMMITS_LIMIT,
            50 - COMMITS_LIMIT,
        )
        self.basic_test('push_commits_more_than_limit', 'commits', 'zulip-test / master', expected_topic)

    def test_issues_opened(self) -> None:
        self.basic_test('issues_opened', 'issues',
                        "zulip-test / Issue #5 The frobnicator doesn't work",
                        "zbenjamin opened [Issue #5](https://github.com/zbenjamin/zulip-test/issues/5)\n\n~~~ quote\nI tried changing the widgets, but I got:\r\n\r\nPermission denied: widgets are immutable\n~~~")

    def test_issue_comment(self) -> None:
        self.basic_test('issue_comment', 'issues',
                        "zulip-test / Issue #5 The frobnicator doesn't work",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/issues/5#issuecomment-23374280) on [Issue #5](https://github.com/zbenjamin/zulip-test/issues/5)\n\n~~~ quote\nWhoops, I did something wrong.\r\n\r\nI'm sorry.\n~~~")

    def test_issues_closed(self) -> None:
        self.basic_test('issues_closed', 'issues',
                        "zulip-test / Issue #5 The frobnicator doesn't work",
                        "zbenjamin closed [Issue #5](https://github.com/zbenjamin/zulip-test/issues/5)")

    def test_pull_request_opened(self) -> None:
        self.basic_test('pull_request_opened', 'commits',
                        "zulip-test / PR #7 Counting is hard.",
                        "lfaraone opened [PR #7](https://github.com/zbenjamin/zulip-test/pull/7)(assigned to lfaraone)\nfrom `patch-2` to `master`\n\n~~~ quote\nOmitted something I think?\n~~~")

    def test_pull_request_closed(self) -> None:
        self.basic_test('pull_request_closed', 'commits',
                        "zulip-test / PR #7 Counting is hard.",
                        "zbenjamin closed [PR #7](https://github.com/zbenjamin/zulip-test/pull/7)")

    def test_pull_request_synchronize(self) -> None:
        self.basic_test('pull_request_synchronize', 'commits',
                        "zulip-test / PR #13 Even more cowbell.",
                        "zbenjamin synchronized [PR #13](https://github.com/zbenjamin/zulip-test/pull/13)")

    def test_pull_request_comment(self) -> None:
        self.basic_test('pull_request_comment', 'commits',
                        "zulip-test / PR #9 Less cowbell.",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/pull/9#issuecomment-24771110) on [PR #9](https://github.com/zbenjamin/zulip-test/pull/9)\n\n~~~ quote\nYeah, who really needs more cowbell than we already have?\n~~~")

    def test_pull_request_comment_user_specified_stream(self) -> None:
        self.basic_test('pull_request_comment', 'my_commits',
                        "zulip-test / PR #9 Less cowbell.",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/pull/9#issuecomment-24771110) on [PR #9](https://github.com/zbenjamin/zulip-test/pull/9)\n\n~~~ quote\nYeah, who really needs more cowbell than we already have?\n~~~",
                        send_stream=True)

    def test_commit_comment(self) -> None:
        self.basic_test('commit_comment', 'commits',
                        "zulip-test",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533#commitcomment-4252302) on [7c99467](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533)\n~~~ quote\nAre we sure this is enough cowbell?\n~~~")

    def test_commit_comment_line(self) -> None:
        self.basic_test('commit_comment_line', 'commits',
                        "zulip-test",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533#commitcomment-4252307) on [7c99467](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533)\n~~~ quote\nThis line adds /unlucky/ cowbell (because of its line number).  We should remove it.\n~~~")

class GithubV2HookTests(WebhookTestCase):
    STREAM_NAME = None  # type: Optional[str]
    URL_TEMPLATE = u"/api/v1/external/github"
    FIXTURE_DIR_NAME = 'github_legacy'
    SEND_STREAM = False
    BRANCHES = None  # type: Optional[str]

    push_content = """zbenjamin [pushed](https://github.com/zbenjamin/zulip-test/compare/4f9adc4777d5...b95449196980) 3 commits to branch master.

* Add baz ([48c329a](https://github.com/zbenjamin/zulip-test/commit/48c329a0b68a9a379ff195ee3f1c1f4ab0b2a89e))
* Baz needs to be longer ([06ebe5f](https://github.com/zbenjamin/zulip-test/commit/06ebe5f472a32f6f31fd2a665f0c7442b69cce72))
* Final edit to baz, I swear ([b954491](https://github.com/zbenjamin/zulip-test/commit/b95449196980507f08209bdfdc4f1d611689b7a8))"""

    def test_spam_branch_is_ignored(self) -> None:
        self.SEND_STREAM = True
        self.STREAM_NAME = 'commits'
        self.BRANCHES = 'dev,staging'
        data = self.get_body('push')

        # We subscribe to the stream in this test, even though
        # it won't get written, to avoid failing for the wrong
        # reason.
        self.subscribe(self.test_user, self.STREAM_NAME)

        prior_count = Message.objects.count()

        result = self.client_post(self.URL_TEMPLATE, data)
        self.assert_json_success(result)

        after_count = Message.objects.count()
        self.assertEqual(prior_count, after_count)

    def get_body(self, fixture_name: str) -> Dict[str, str]:
        api_key = get_api_key(self.test_user)
        data = ujson.loads(self.webhook_fixture_data(self.FIXTURE_DIR_NAME, 'v2_' + fixture_name))
        data.update({'email': self.TEST_USER_EMAIL,
                     'api-key': api_key,
                     'payload': ujson.dumps(data['payload'])})
        if self.SEND_STREAM:
            data['stream'] = self.STREAM_NAME

        if self.BRANCHES is not None:
            data['branches'] = self.BRANCHES
        return data

    def basic_test(self, fixture_name: str, stream_name: str,
                   expected_topic: str, expected_content: str,
                   send_stream: bool=False, branches: Optional[str]=None) -> None:
        self.STREAM_NAME = stream_name
        self.SEND_STREAM = send_stream
        self.BRANCHES = branches
        self.send_and_test_stream_message(fixture_name, expected_topic, expected_content, content_type=None)

    def test_user_specified_branches(self) -> None:
        self.basic_test('push', 'my_commits', 'zulip-test / master', self.push_content,
                        send_stream=True, branches="master,staging")

    def test_user_specified_stream(self) -> None:
        """Around May 2013 the github webhook started to specify the stream.
        Before then, the stream was hard coded to "commits"."""
        self.basic_test('push', 'my_commits', 'zulip-test / master', self.push_content,
                        send_stream=True)

    def test_push_multiple_commits(self) -> None:
        commit_info = "* Add baz ([48c329a](https://github.com/zbenjamin/zulip-test/commit/48c329a0b68a9a379ff195ee3f1c1f4ab0b2a89e))\n"
        expected_topic = "zbenjamin [pushed](https://github.com/zbenjamin/zulip-test/compare/4f9adc4777d5...b95449196980) 50 commits to branch master.\n\n{}[and {} more commit(s)]".format(
            commit_info * COMMITS_LIMIT,
            50 - COMMITS_LIMIT,
        )
        self.basic_test('push_commits_more_than_limit', 'commits', 'zulip-test / master', expected_topic)

    def test_push_multiple_committers(self) -> None:
        commit_info = "* Add baz ([48c329a](https://github.com/zbenjamin/zulip-test/commit/48c329a0b68a9a379ff195ee3f1c1f4ab0b2a89e))\n"
        expected_topic = "zbenjamin [pushed](https://github.com/zbenjamin/zulip-test/compare/4f9adc4777d5...b95449196980) 6 commits to branch master. Commits by tomasz (3), baxthehacker (2) and zbenjamin (1).\n\n{}* Add baz ([48c329a](https://github.com/zbenjamin/zulip-test/commit/48c329a0b68a9a379ff195ee3f1c1f4ab0b2a89e))".format(commit_info * 5)
        self.basic_test('push_multiple_committers', 'commits', 'zulip-test / master', expected_topic)

    def test_push_multiple_committers_with_others(self) -> None:
        commit_info = "* Final edit to baz, I swear ([b954491](https://github.com/zbenjamin/zulip-test/commit/b95449196980507f08209bdfdc4f1d611689b7a8))\n"
        expected_topic = "zbenjamin [pushed](https://github.com/zbenjamin/zulip-test/compare/4f9adc4777d5...b95449196980) 10 commits to branch master. Commits by baxthehacker (4), James (3), Tomasz (2) and others (1).\n\n{}* Final edit to baz, I swear ([b954491](https://github.com/zbenjamin/zulip-test/commit/b95449196980507f08209bdfdc4f1d611689b7a8))".format(commit_info * 9)
        self.basic_test('push_multiple_committers_with_others', 'commits', 'zulip-test / master', expected_topic)

    def test_legacy_hook(self) -> None:
        self.basic_test('push', 'commits', 'zulip-test / master', self.push_content)

    def test_issues_opened(self) -> None:
        self.basic_test('issues_opened', 'issues',
                        "zulip-test / Issue #5 The frobnicator doesn't work",
                        "zbenjamin opened [Issue #5](https://github.com/zbenjamin/zulip-test/issues/5)\n\n~~~ quote\nI tried changing the widgets, but I got:\r\n\r\nPermission denied: widgets are immutable\n~~~")

    def test_issue_comment(self) -> None:
        self.basic_test('issue_comment', 'issues',
                        "zulip-test / Issue #5 The frobnicator doesn't work",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/issues/5#issuecomment-23374280) on [Issue #5](https://github.com/zbenjamin/zulip-test/issues/5)\n\n~~~ quote\nWhoops, I did something wrong.\r\n\r\nI'm sorry.\n~~~")

    def test_issues_closed(self) -> None:
        self.basic_test('issues_closed', 'issues',
                        "zulip-test / Issue #5 The frobnicator doesn't work",
                        "zbenjamin closed [Issue #5](https://github.com/zbenjamin/zulip-test/issues/5)")

    def test_pull_request_opened(self) -> None:
        self.basic_test('pull_request_opened', 'commits',
                        "zulip-test / PR #7 Counting is hard.",
                        "lfaraone opened [PR #7](https://github.com/zbenjamin/zulip-test/pull/7)(assigned to lfaraone)\nfrom `patch-2` to `master`\n\n~~~ quote\nOmitted something I think?\n~~~")

    def test_pull_request_closed(self) -> None:
        self.basic_test('pull_request_closed', 'commits',
                        "zulip-test / PR #7 Counting is hard.",
                        "zbenjamin closed [PR #7](https://github.com/zbenjamin/zulip-test/pull/7)")

    def test_pull_request_synchronize(self) -> None:
        self.basic_test('pull_request_synchronize', 'commits',
                        "zulip-test / PR #13 Even more cowbell.",

                        "zbenjamin synchronized [PR #13](https://github.com/zbenjamin/zulip-test/pull/13)")

    def test_pull_request_comment(self) -> None:
        self.basic_test('pull_request_comment', 'commits',
                        "zulip-test / PR #9 Less cowbell.",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/pull/9#issuecomment-24771110) on [PR #9](https://github.com/zbenjamin/zulip-test/pull/9)\n\n~~~ quote\nYeah, who really needs more cowbell than we already have?\n~~~")

    def test_pull_request_comment_user_specified_stream(self) -> None:
        self.basic_test('pull_request_comment', 'my_commits',
                        "zulip-test / PR #9 Less cowbell.",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/pull/9#issuecomment-24771110) on [PR #9](https://github.com/zbenjamin/zulip-test/pull/9)\n\n~~~ quote\nYeah, who really needs more cowbell than we already have?\n~~~",
                        send_stream=True)

    def test_commit_comment(self) -> None:
        self.basic_test('commit_comment', 'commits',
                        "zulip-test",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533#commitcomment-4252302) on [7c99467](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533)\n~~~ quote\nAre we sure this is enough cowbell?\n~~~")

    def test_commit_comment_line(self) -> None:
        self.basic_test('commit_comment_line', 'commits',
                        "zulip-test",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533#commitcomment-4252307) on [7c99467](https://github.com/zbenjamin/zulip-test/commit/7c994678d2f98797d299abed852d3ff9d0834533)\n~~~ quote\nThis line adds /unlucky/ cowbell (because of its line number).  We should remove it.\n~~~")
