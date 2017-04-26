# -*- coding: utf-8 -*-
from mock import patch, MagicMock
from typing import Dict, Text

from zerver.lib.webhooks.git import COMMITS_LIMIT
from zerver.lib.test_classes import WebhookTestCase

class BeanstalkHookTests(WebhookTestCase):
    STREAM_NAME = 'commits'
    URL_TEMPLATE = u"/api/v1/external/beanstalk"

    def test_git_single(self):
        # type: () -> None
        expected_subject = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 1 commit to branch master.

* add some stuff ([e50508d](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df))"""
        self.send_and_test_stream_message('git_singlecommit', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_git_single_filtered_by_branches(self):
        # type: () -> None
        self.url = self.build_webhook_url(branches='master,development')
        expected_subject = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 1 commit to branch master.

* add some stuff ([e50508d](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df))"""
        self.send_and_test_stream_message('git_singlecommit', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_git_multiple_committers(self):
        # type: () -> None
        expected_subject = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 3 commits to branch master. Commits by Leo Franchi (2) and Tomasz Kolek (1).

* Added new file ([edf529c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7))
* Filled in new file with some stuff ([c2a191b](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9))
* More work to fix some bugs ([2009815](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158))"""
        self.send_and_test_stream_message('git_multiple_committers', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_git_multiple_committers_filtered_by_branches(self):
        # type: () -> None
        self.url = self.build_webhook_url(branches='master,development')
        expected_subject = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 3 commits to branch master. Commits by Leo Franchi (2) and Tomasz Kolek (1).

* Added new file ([edf529c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7))
* Filled in new file with some stuff ([c2a191b](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9))
* More work to fix some bugs ([2009815](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158))"""
        self.send_and_test_stream_message('git_multiple_committers', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_git_multiple(self):
        # type: () -> None
        expected_subject = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 3 commits to branch master.

* Added new file ([edf529c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7))
* Filled in new file with some stuff ([c2a191b](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9))
* More work to fix some bugs ([2009815](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158))"""
        self.send_and_test_stream_message('git_multiple', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_git_multiple_filtered_by_branches(self):
        # type: () -> None
        self.url = self.build_webhook_url(branches='master,development')
        expected_subject = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 3 commits to branch master.

* Added new file ([edf529c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7))
* Filled in new file with some stuff ([c2a191b](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9))
* More work to fix some bugs ([2009815](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158))"""
        self.send_and_test_stream_message('git_multiple', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_git_more_than_limit(self):
        # type: () -> None
        commits_info = "* add some stuff ([e50508d](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df))\n"
        expected_subject = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 50 commits to branch master.

{}[and {} more commit(s)]""".format((commits_info * COMMITS_LIMIT), 50 - COMMITS_LIMIT)
        self.send_and_test_stream_message('git_morethanlimitcommits', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_git_more_than_limit_filtered_by_branches(self):
        # type: () -> None
        self.url = self.build_webhook_url(branches='master,development')
        commits_info = "* add some stuff ([e50508d](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df))\n"
        expected_subject = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) 50 commits to branch master.

{}[and {} more commit(s)]""".format((commits_info * COMMITS_LIMIT), 50 - COMMITS_LIMIT)
        self.send_and_test_stream_message('git_morethanlimitcommits', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    @patch('zerver.webhooks.beanstalk.view.check_send_message')
    def test_git_single_filtered_by_branches_ignore(self, check_send_message_mock):
        # type: (MagicMock) -> None
        self.url = self.build_webhook_url(branches='changes,development')
        payload = self.get_body('git_singlecommit')
        result = self.client_post(self.url, payload,
                                  **self.api_auth(self.TEST_USER_EMAIL))
        self.assertFalse(check_send_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.beanstalk.view.check_send_message')
    def test_git_multiple_committers_filtered_by_branches_ignore(
            self, check_send_message_mock):
        # type: (MagicMock) -> None
        self.url = self.build_webhook_url(branches='changes,development')
        payload = self.get_body('git_multiple_committers')
        result = self.client_post(self.url, payload,
                                  **self.api_auth(self.TEST_USER_EMAIL))
        self.assertFalse(check_send_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.beanstalk.view.check_send_message')
    def test_git_multiple_filtered_by_branches_ignore(
            self, check_send_message_mock):
        # type: (MagicMock) -> None
        self.url = self.build_webhook_url(branches='changes,development')
        payload = self.get_body('git_multiple')
        result = self.client_post(self.url, payload,
                                  **self.api_auth(self.TEST_USER_EMAIL))
        self.assertFalse(check_send_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.beanstalk.view.check_send_message')
    def test_git_more_than_limit_filtered_by_branches_ignore(
            self, check_send_message_mock):
        # type: (MagicMock) -> None
        self.url = self.build_webhook_url(branches='changes,development')
        payload = self.get_body('git_morethanlimitcommits')
        result = self.client_post(self.url, payload,
                                  **self.api_auth(self.TEST_USER_EMAIL))
        self.assertFalse(check_send_message_mock.called)
        self.assert_json_success(result)

    def test_svn_addremove(self):
        # type: () -> None
        expected_subject = "svn r3"
        expected_message = """Leo Franchi pushed [revision 3](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/3):

> Removed a file and added another one!"""
        self.send_and_test_stream_message('svn_addremove', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_svn_changefile(self):
        # type: () -> None
        expected_subject = "svn r2"
        expected_message = """Leo Franchi pushed [revision 2](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/2):

> Added some code"""
        self.send_and_test_stream_message('svn_changefile', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def get_body(self, fixture_name):
        # type: (Text) -> Dict[str, Text]
        return {'payload': self.fixture_data('beanstalk', fixture_name)}
