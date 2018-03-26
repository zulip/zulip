# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase


class RaygunHookTests(WebhookTestCase):
    STREAM_NAME = 'raygun'
    URL_TEMPLATE = "/api/v1/external/raygun?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'raygun'

    def test_status_changed_message(self) -> None:
        expected_subject = u"test"
        expected_message = u"[Error](https://app.raygun.com/error-url) " \
                           u"status changed to: Ignored by Emma Cat\n" \
                           u"Timestamp: Wed Jan 28 01:49:36 1970\n" \
                           u"Application details: " \
                           u"[Best App](http://app.raygun.io/application-url)"

        self.send_and_test_stream_message('error_status_changed',
                                          expected_subject,
                                          expected_message,
                                          content_type=
                                          "application/x-www-form-urlencoded")

    def test_comment_added_to_error_message(self) -> None:
        expected_subject = u"test"
        expected_message = u"Anita Peacock left a comment on " \
                           u"[Error](https://app.raygun.com/error-url): " \
                           u"Ignoring these errors\n" \
                           u"Timestamp: Wed Jan 28 01:49:36 1970\n" \
                           u"Application details: " \
                           u"[application name]" \
                           u"(http://app.raygun.io/application-url)"

        self.send_and_test_stream_message('comment_added_to_error',
                                          expected_subject,
                                          expected_message,
                                          content_type=
                                          "application/x-www-form-urlencoded")

    def test_error_assigned_to_user_message(self) -> None:
        expected_subject = u"test"
        expected_message = u"Amy Loondon assigned " \
                           u"[Error](https://app.raygun.com/error-url) " \
                           u"to Kyle Kenny\n" \
                           u"Timestamp: Wed Jan 28 01:49:36 1970\n" \
                           u"Application details: " \
                           u"[application name]" \
                           u"(http://app.raygun.io/application-url)"

        self.send_and_test_stream_message('error_assigned_to_user',
                                          expected_subject,
                                          expected_message,
                                          content_type=
                                          "application/x-www-form-urlencoded")

    def test_one_minute_followup_error_message(self) -> None:
        expected_subject = u"test"
        expected_message = u"One minute " \
                           u"[follow-up error]" \
                           u"(http://app.raygun.io/error-url)\n" \
                           u"First occurred: Wed Jan 28 01:49:36 1970\n" \
                           u"Last occurred: Wed Jan 28 01:49:36 1970\n" \
                           u"1 users affected with 1 total occurrences\n" \
                           u"Application details: " \
                           u"[application name]" \
                           u"(http://app.raygun.io/application-url)"

        self.send_and_test_stream_message('one_minute_followup_error',
                                          expected_subject,
                                          expected_message,
                                          content_type=
                                          "application/x-www-form-urlencoded")

    def test_hourly_followup_error_message(self) -> None:
        expected_subject = u"test"
        expected_message = u"Hourly " \
                           u"[follow-up error]" \
                           u"(http://app.raygun.io/error-url)\n" \
                           u"First occurred: Wed Jan 28 01:49:36 1970\n" \
                           u"Last occurred: Wed Jan 28 01:49:36 1970\n" \
                           u"1 users affected with 1 total occurrences\n" \
                           u"Application details: " \
                           u"[application name]" \
                           u"(http://app.raygun.io/application-url)"

        self.send_and_test_stream_message('hourly_followup_error',
                                          expected_subject,
                                          expected_message,
                                          content_type=
                                          "application/x-www-form-urlencoded")

    def test_new_error_message(self) -> None:
        expected_subject = u"test"
        expected_message = u"**New [Error](http://app.raygun.io/error-url) " \
                           u"occurred!**\n" \
                           u"First occurred: Wed Jan 28 01:49:36 1970\n" \
                           u"Last occurred: Wed Jan 28 01:49:36 1970\n" \
                           u"1 users affected with 1 total occurrences\n" \
                           u"Tags: test, error-page, v1.0.1, env:staging\n" \
                           u"Affected user: a9b7d8...33846\n" \
                           u"pageName: Error Page\n" \
                           u"userLoggedIn: True\n" \
                           u"Application details: " \
                           u"[application name]" \
                           u"(http://app.raygun.io/application-url)"

        self.send_and_test_stream_message('new_error',
                                          expected_subject,
                                          expected_message,
                                          content_type=
                                          "application/x-www-form-urlencoded")

    def test_reoccurred_error_message(self) -> None:
        expected_subject = u"test"
        expected_message = u"[Error](http://app.raygun.io/error-url) " \
                           u"reoccurred.\n" \
                           u"First occurred: Wed Jan 28 01:49:36 1970\n" \
                           u"Last occurred: Wed Jan 28 01:49:36 1970\n" \
                           u"1 users affected with 1 total occurrences\n" \
                           u"Tags: test, error-page, v1.0.1, env:staging\n" \
                           u"Affected user: a9b7d8...33846\n" \
                           u"pageName: Error Page\n" \
                           u"userLoggedIn: True\n" \
                           u"Application details: " \
                           u"[application name]" \
                           u"(http://app.raygun.io/application-url)"

        self.send_and_test_stream_message('reoccurred_error',
                                          expected_subject,
                                          expected_message,
                                          content_type=
                                          "application/x-www-form-urlencoded")

    def test_no_event_type_message(self) -> None:
        expected_subject = u"test"
        expected_message = u"Unsupported event type: new_event_type"

        self.send_and_test_stream_message('no_event_type',
                                          expected_subject,
                                          expected_message,
                                          content_type=
                                          "application/x-www-form-urlencoded")

    def test_unimplemented_notification_feature(self) -> None:
        expected_subject = u"test"
        expected_message = u"Unsupported event_type type: UnimplementedFeature"

        self.send_and_test_stream_message('no_notification_eventType_type',
                                          expected_subject,
                                          expected_message,
                                          content_type=
                                          "application/x-www-form-urlencoded")

    def test_unimplemented_activity_feature(self) -> None:
        expected_subject = u"test"
        expected_message = u"Unsupported event_type type: UnimplementedFeature"

        self.send_and_test_stream_message('no_activity_eventType_type',
                                          expected_subject,
                                          expected_message,
                                          content_type=
                                          "application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("raygun", fixture_name, file_type="json")
