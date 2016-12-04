# -*- coding: utf-8 -*-
from typing import Text
from zerver.lib.webhooks.git import COMMITS_LIMIT
from zerver.lib.test_classes import WebhookTestCase

class BeanstalkHookTests(WebhookTestCase):
    STREAM_NAME = 'commits'
    URL_TEMPLATE = u"/api/v1/external/beanstalk"

    def test_git_single(self):
        # type: () -> None
        expected_subject = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) to branch master

* [e50508d](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df): add some stuff"""
        self.send_and_test_stream_message('git_singlecommit', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_git_multiple(self):
        # type: () -> None
        expected_subject = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) to branch master

* [edf529c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7): Added new file
* [c2a191b](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9): Filled in new file with some stuff
* [2009815](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158): More work to fix some bugs"""
        self.send_and_test_stream_message('git_multiple', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

    def test_git_more_than_limit(self):
        # type: () -> None
        commits_info = "* [e50508d](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df): add some stuff\n"
        expected_subject = "work-test / master"
        expected_message = """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) to branch master

{}[and {} more commit(s)]""".format((commits_info * COMMITS_LIMIT), 50 - COMMITS_LIMIT)
        self.send_and_test_stream_message('git_morethanlimitcommits', expected_subject, expected_message,
                                          content_type=None,
                                          **self.api_auth(self.TEST_USER_EMAIL))

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
