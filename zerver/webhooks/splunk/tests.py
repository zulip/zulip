from zerver.lib.test_classes import WebhookTestCase


class SplunkHookTests(WebhookTestCase):
    CHANNEL_NAME = "splunk"
    URL_TEMPLATE = "/api/v1/external/splunk?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "splunk"

    def test_splunk_search_one_result(self) -> None:
        self.url = self.build_webhook_url(topic="New Search Alert")

        # define the expected message contents
        expected_topic_name = "New Search Alert"
        expected_message = """
Splunk alert from saved search:
* **Search**: [sudo](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)
* **Host**: myserver
* **Source**: `/var/log/auth.log`
* **Raw**: `Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root`
""".strip()

        # using fixture named splunk_search_one_result, execute this test
        self.check_webhook(
            "search_one_result",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_splunk_short_search_name(self) -> None:
        # don't provide a topic so the search name is used instead
        expected_topic_name = "This search's name isn't that long"
        expected_message = """
Splunk alert from saved search:
* **Search**: [This search's name isn't that long](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)
* **Host**: myserver
* **Source**: `/var/log/auth.log`
* **Raw**: `Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root`
""".strip()

        self.check_webhook(
            "short_search_name",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_splunk_long_search_name(self) -> None:
        # don't provide a topic so the search name is used instead
        expected_topic_name = "this-search's-got-47-words-37-sentences-58-words-we-wanna..."
        expected_message = """
Splunk alert from saved search:
* **Search**: [this-search's-got-47-words-37-sentences-58-words-we-wanna-know-details-of-the-search-time-of-the-search-and-any-other-kind-of-thing-you-gotta-say-pertaining-to-and-about-the-search-I-want-to-know-authenticated-user's-name-and-any-other-kind-of-thing-you-gotta-say](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)
* **Host**: myserver
* **Source**: `/var/log/auth.log`
* **Raw**: `Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root`
""".strip()

        self.check_webhook(
            "long_search_name",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_splunk_missing_results_link(self) -> None:
        self.url = self.build_webhook_url(topic="New Search Alert")

        expected_topic_name = "New Search Alert"
        expected_message = """
Splunk alert from saved search:
* **Search**: [sudo](Missing results_link)
* **Host**: myserver
* **Source**: `/var/log/auth.log`
* **Raw**: `Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root`
""".strip()

        self.check_webhook(
            "missing_results_link",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_splunk_missing_search_name(self) -> None:
        self.url = self.build_webhook_url(topic="New Search Alert")

        expected_topic_name = "New Search Alert"
        expected_message = """
Splunk alert from saved search:
* **Search**: [Missing search_name](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)
* **Host**: myserver
* **Source**: `/var/log/auth.log`
* **Raw**: `Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root`
""".strip()

        self.check_webhook(
            "missing_search_name",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_splunk_missing_host(self) -> None:
        self.url = self.build_webhook_url(topic="New Search Alert")

        expected_topic_name = "New Search Alert"
        expected_message = """
Splunk alert from saved search:
* **Search**: [sudo](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)
* **Host**: Missing host
* **Source**: `/var/log/auth.log`
* **Raw**: `Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root`
""".strip()

        self.check_webhook(
            "missing_host",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_splunk_missing_source(self) -> None:
        self.url = self.build_webhook_url(topic="New Search Alert")

        expected_topic_name = "New Search Alert"
        expected_message = """
Splunk alert from saved search:
* **Search**: [sudo](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)
* **Host**: myserver
* **Source**: `Missing source`
* **Raw**: `Jan  4 11:14:32 myserver sudo: pam_unix(sudo:session): session closed for user root`
""".strip()

        self.check_webhook(
            "missing_source",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_splunk_missing_raw(self) -> None:
        self.url = self.build_webhook_url(topic="New Search Alert")

        expected_topic_name = "New Search Alert"
        expected_message = """
Splunk alert from saved search:
* **Search**: [sudo](http://example.com:8000/app/search/search?q=%7Cloadjob%20rt_scheduler__admin__search__sudo_at_1483557185_2.2%20%7C%20head%201%20%7C%20tail%201&earliest=0&latest=now)
* **Host**: myserver
* **Source**: `/var/log/auth.log`
* **Raw**: `Missing _raw`
""".strip()

        self.check_webhook(
            "missing_raw",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
