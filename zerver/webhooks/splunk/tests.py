# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase

class SplunkHookTests(WebhookTestCase):

    STREAM_NAME = 'splunk'
    URL_TEMPLATE = "/api/v1/external/splunk?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'splunk'

    def test_splunk_search_one_result(self) -> None:
        self.url = self.build_webhook_url(topic=u"New Search Alert")

        # define the expected message contents
        expected_subject = u"New Search Alert"
        expected_message = u"Splunk alert from saved search\n[sudo](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)\nhost: myserver\nsource: /var/log/auth.log\n\nraw: Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root"

        # using fixture named splunk_search_one_result, execute this test
        self.send_and_test_stream_message('search_one_result',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_splunk_short_search_name(self) -> None:

        # don't provide a topic so the search name is used instead
        expected_subject = u"This search's name isn't that long"
        expected_message = u"Splunk alert from saved search\n[This search's name isn't that long](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)\nhost: myserver\nsource: /var/log/auth.log\n\nraw: Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root"

        self.send_and_test_stream_message('short_search_name',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_splunk_long_search_name(self) -> None:

        # don't provide a topic so the search name is used instead
        expected_subject = u"this-search's-got-47-words-37-sentences-58-words-we-wanna..."
        expected_message = u"Splunk alert from saved search\n[this-search's-got-47-words-37-sentences-58-words-we-wanna-know-details-of-the-search-time-of-the-search-and-any-other-kind-of-thing-you-gotta-say-pertaining-to-and-about-the-search-I-want-to-know-authenticated-user's-name-and-any-other-kind-of-thing-you-gotta-say](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)\nhost: myserver\nsource: /var/log/auth.log\n\nraw: Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root"

        self.send_and_test_stream_message('long_search_name',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_splunk_missing_results_link(self) -> None:

        self.url = self.build_webhook_url(topic=u"New Search Alert")

        expected_subject = u"New Search Alert"
        expected_message = u"Splunk alert from saved search\n[sudo](Missing results_link)\nhost: myserver\nsource: /var/log/auth.log\n\nraw: Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root"

        self.send_and_test_stream_message('missing_results_link',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_splunk_missing_search_name(self) -> None:

        self.url = self.build_webhook_url(topic=u"New Search Alert")

        expected_subject = u"New Search Alert"
        expected_message = u"Splunk alert from saved search\n[Missing search_name](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)\nhost: myserver\nsource: /var/log/auth.log\n\nraw: Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root"

        self.send_and_test_stream_message('missing_search_name',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_splunk_missing_host(self) -> None:

        self.url = self.build_webhook_url(topic=u"New Search Alert")

        expected_subject = u"New Search Alert"
        expected_message = u"Splunk alert from saved search\n[sudo](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)\nhost: Missing host\nsource: /var/log/auth.log\n\nraw: Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root"

        self.send_and_test_stream_message('missing_host',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_splunk_missing_source(self) -> None:

        self.url = self.build_webhook_url(topic=u"New Search Alert")

        expected_subject = u"New Search Alert"
        expected_message = u"Splunk alert from saved search\n[sudo](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)\nhost: myserver\nsource: Missing source\n\nraw: Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root"

        self.send_and_test_stream_message('missing_source',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_splunk_missing_raw(self) -> None:

        self.url = self.build_webhook_url(topic=u"New Search Alert")

        expected_subject = u"New Search Alert"
        expected_message = u"Splunk alert from saved search\n[sudo](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)\nhost: myserver\nsource: /var/log/auth.log\n\nraw: Missing _raw"

        self.send_and_test_stream_message('missing_raw',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("splunk", fixture_name, file_type="json")
