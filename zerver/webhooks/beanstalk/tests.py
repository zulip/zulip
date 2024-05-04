from typing import Dict
from unittest.mock import MagicMock, patch

from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.webhooks.git import COMMITS_LIMIT


class BeanstalkHookTests(WebhookTestCase):
    CHANNEL_NAME = "commits"
    URL_TEMPLATE = "/api/v1/external/beanstalk?stream={stream}"

    def test_git_single(self) -> None:
        expected_topic_name = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 1 commit to branch master.

* add some stuff ([e50508df24c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df))"""
        self.api_channel_message(
            self.test_user,
            "git_singlecommit",
            expected_topic_name,
            expected_message,
            content_type=None,
        )

    def test_git_single_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        expected_topic_name = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 1 commit to branch master.

* add some stuff ([e50508df24c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df))"""
        self.api_channel_message(
            self.test_user,
            "git_singlecommit",
            expected_topic_name,
            expected_message,
            content_type=None,
        )

    def test_git_multiple_committers(self) -> None:
        expected_topic_name = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 3 commits to branch master. Commits by Leo Franchi (2) and Tomasz Kolek (1).

* Added new file ([edf529c7a64](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7))
* Filled in new file with some stuff ([c2a191b9e79](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9))
* More work to fix some bugs ([20098158e20](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158))"""
        self.api_channel_message(
            self.test_user,
            "git_multiple_committers",
            expected_topic_name,
            expected_message,
            content_type=None,
        )

    def test_git_multiple_committers_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        expected_topic_name = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 3 commits to branch master. Commits by Leo Franchi (2) and Tomasz Kolek (1).

* Added new file ([edf529c7a64](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7))
* Filled in new file with some stuff ([c2a191b9e79](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9))
* More work to fix some bugs ([20098158e20](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158))"""
        self.api_channel_message(
            self.test_user,
            "git_multiple_committers",
            expected_topic_name,
            expected_message,
            content_type=None,
        )

    def test_git_multiple(self) -> None:
        expected_topic_name = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 3 commits to branch master.

* Added new file ([edf529c7a64](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7))
* Filled in new file with some stuff ([c2a191b9e79](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9))
* More work to fix some bugs ([20098158e20](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158))"""
        self.api_channel_message(
            self.test_user, "git_multiple", expected_topic_name, expected_message, content_type=None
        )

    def test_git_multiple_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        expected_topic_name = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 3 commits to branch master.

* Added new file ([edf529c7a64](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7))
* Filled in new file with some stuff ([c2a191b9e79](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9))
* More work to fix some bugs ([20098158e20](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158))"""
        self.api_channel_message(
            self.test_user, "git_multiple", expected_topic_name, expected_message, content_type=None
        )

    def test_git_more_than_limit(self) -> None:
        commits_info = "* add some stuff ([e50508df24c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df))\n"
        expected_topic_name = "work-test / master"
        expected_message = f"""Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 50 commits to branch master.

{(commits_info * COMMITS_LIMIT)}[and {50 - COMMITS_LIMIT} more commit(s)]"""
        self.api_channel_message(
            self.test_user,
            "git_morethanlimitcommits",
            expected_topic_name,
            expected_message,
            content_type=None,
        )

    def test_git_more_than_limit_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        commits_info = "* add some stuff ([e50508df24c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df))\n"
        expected_topic_name = "work-test / master"
        expected_message = f"""Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 50 commits to branch master.

{(commits_info * COMMITS_LIMIT)}[and {50 - COMMITS_LIMIT} more commit(s)]"""
        self.api_channel_message(
            self.test_user,
            "git_morethanlimitcommits",
            expected_topic_name,
            expected_message,
            content_type=None,
        )

    @patch("zerver.webhooks.beanstalk.view.check_send_webhook_message")
    def test_git_single_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_payload("git_singlecommit")
        result = self.api_post(self.test_user, self.url, payload)
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.beanstalk.view.check_send_webhook_message")
    def test_git_multiple_committers_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_payload("git_multiple_committers")
        result = self.api_post(self.test_user, self.url, payload)
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.beanstalk.view.check_send_webhook_message")
    def test_git_multiple_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_payload("git_multiple")
        result = self.api_post(self.test_user, self.url, payload)
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.beanstalk.view.check_send_webhook_message")
    def test_git_more_than_limit_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_payload("git_morethanlimitcommits")
        result = self.api_post(self.test_user, self.url, payload)
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_svn_addremove(self) -> None:
        expected_topic_name = "svn r3"
        expected_message = """Leo Franchi pushed [revision 3](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/3):

> Removed a file and added another one!"""
        self.api_channel_message(
            self.test_user,
            "svn_addremove",
            expected_topic_name,
            expected_message,
            content_type=None,
        )

    def test_svn_changefile(self) -> None:
        expected_topic_name = "svn r2"
        expected_message = """Leo Franchi pushed [revision 2](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/2):

> Added some code"""
        self.api_channel_message(
            self.test_user,
            "svn_changefile",
            expected_topic_name,
            expected_message,
            content_type=None,
        )

    @override
    def get_payload(self, fixture_name: str) -> Dict[str, str]:
        return {"payload": self.webhook_fixture_data("beanstalk", fixture_name)}
