# -*- coding: utf-8 -*-
from typing import Text
from zerver.lib.test_classes import WebhookTestCase

class TaigaHookTests(WebhookTestCase):
    STREAM_NAME = 'taiga'
    TOPIC = "subject"
    URL_TEMPLATE = u"/api/v1/external/taiga?stream={stream}&api_key={api_key}&topic={topic}"
    FIXTURE_DIR_NAME = 'taiga'

    def build_webhook_url(self):
        # type: () -> Text
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        return self.URL_TEMPLATE.format(stream=self.STREAM_NAME, api_key=api_key, topic=self.TOPIC)

    def test_taiga_userstory_deleted(self):
        # type: () -> None
        message = u':x: Antek deleted user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_deleted", u'subject', message)

    def test_taiga_userstory_created(self):
        # type: () -> None
        message = u':package: Antek created user story **A new hope**.\n'
        self.send_and_test_stream_message("userstory_created", u'subject', message)

    def test_taiga_userstory_changed_unblocked(self):
        # type: () -> None
        message = u':unlock: Antek unblocked user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_unblocked", u'subject', message)

    def test_taiga_userstory_changed_subject(self):
        # type: () -> None
        message = u':notebook: Antek renamed user story from A new hope to **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_subject", u'subject', message)

    def test_taiga_userstory_changed_status(self):
        # type: () -> None
        message = u':chart_with_upwards_trend: Antek changed status of user story **A new hope** from New to Done.\n'
        self.send_and_test_stream_message("userstory_changed_status", u'subject', message)

    def test_taiga_userstory_changed_reassigned(self):
        # type: () -> None
        message = u':busts_in_silhouette: Antek reassigned user story **Great US** from Antek to Han Solo.\n'
        self.send_and_test_stream_message("userstory_changed_reassigned", u'subject', message)

    def test_taiga_userstory_changed_points(self):
        # type: () -> None
        message = u':game_die: Antek changed estimation of user story **A new hope**.\n'
        self.send_and_test_stream_message("userstory_changed_points", u'subject', message)

    def test_taiga_userstory_changed_new_milestone(self):
        # type: () -> None
        message = u':calendar: Antek added user story **A newer hope** to sprint New sprint.\n'
        self.send_and_test_stream_message("userstory_changed_new_milestone", u'subject', message)

    def test_taiga_userstory_changed_milestone(self):
        # type: () -> None
        message = u':calendar: Antek changed sprint of user story **A newer hope** from Old sprint to New sprint.\n'
        self.send_and_test_stream_message("userstory_changed_milestone", u'subject', message)

    def test_taiga_userstory_changed_description(self):
        # type: () -> None
        message = u':notebook: Antek updated description of user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_description", u'subject', message)

    def test_taiga_userstory_changed_closed(self):
        # type: () -> None
        message = u':chart_with_upwards_trend: Antek changed status of user story **A newer hope** from New to Done.\n:checkered_flag: Antek closed user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_closed", u'subject', message)

    def test_taiga_userstory_changed_reopened(self):
        # type: () -> None
        message = u':chart_with_upwards_trend: Antek changed status of user story **A newer hope** from Done to New.\n:package: Antek reopened user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_reopened", u'subject', message)

    def test_taiga_userstory_changed_blocked(self):
        # type: () -> None
        message = u':lock: Antek blocked user story **A newer hope**.\n'
        self.send_and_test_stream_message("userstory_changed_blocked", u'subject', message)

    def test_taiga_userstory_changed_assigned(self):
        # type: () -> None
        message = u':busts_in_silhouette: Antek assigned user story **Great US** to Antek.\n'
        self.send_and_test_stream_message("userstory_changed_assigned", u'subject', message)

    def test_taiga_task_created(self):
        # type: () -> None
        message = u':clipboard: Antek created task **New task assigned and in progress**.\n'
        self.send_and_test_stream_message("task_created", u'subject', message)

    def test_taiga_task_changed_status(self):
        # type: () -> None
        message = u':chart_with_upwards_trend: Antek changed status of task **New task assigned and in progress** from Ready for test to New.\n'
        self.send_and_test_stream_message("task_changed_status", u'subject', message)

    def test_taiga_task_changed_blocked(self):
        # type: () -> None
        message = u':lock: Antek blocked task **A new task**.\n'
        self.send_and_test_stream_message("task_changed_blocked", u'subject', message)

    def test_taiga_task_changed_unblocked(self):
        # type: () -> None
        message = u':unlock: Antek unblocked task **A new task**.\n'
        self.send_and_test_stream_message("task_changed_unblocked", u'subject', message)

    def test_taiga_task_changed_assigned(self):
        # type: () -> None
        message = u':busts_in_silhouette: Antek assigned task **Aaaa** to Antek.\n'
        self.send_and_test_stream_message("task_changed_assigned", u'subject', message)

    def test_taiga_task_changed_reassigned(self):
        # type: () -> None
        message = u':busts_in_silhouette: Antek reassigned task **Aaaa** from Han Solo to Antek.\n'
        self.send_and_test_stream_message("task_changed_reassigned", u'subject', message)

    def test_taiga_task_changed_subject(self):
        # type: () -> None
        message = u':notebook: Antek renamed task New task to **Even newer task**.\n'
        self.send_and_test_stream_message("task_changed_subject", u'subject', message)

    def test_taiga_task_changed_description(self):
        # type: () -> None
        message = u':notebook: Antek updated description of task **Even newer task.**.\n'
        self.send_and_test_stream_message("task_changed_description", u'subject', message)

    def test_taiga_task_changed_us(self):
        # type: () -> None
        message = u':clipboard: Antek moved task **A new task** from user story #3 Great US to #6 Greater US.\n'
        self.send_and_test_stream_message("task_changed_us", u'subject', message)

    def test_taiga_task_deleted(self):
        # type: () -> None
        message = u':x: Antek deleted task **hhh**.\n'
        self.send_and_test_stream_message("task_deleted", u'subject', message)

    def test_taiga_milestone_created(self):
        # type: () -> None
        message = u':calendar: Antek created sprint **New sprint**.\n'
        self.send_and_test_stream_message("milestone_created", u'subject', message)

    def test_taiga_milestone_deleted(self):
        # type: () -> None
        message = u':x: Antek deleted sprint **Newer sprint**.\n'
        self.send_and_test_stream_message("milestone_deleted", u'subject', message)

    def test_taiga_milestone_changed_time(self):
        # type: () -> None
        message = u':calendar: Antek changed estimated finish of sprint **New sprint** from 2016-04-27 to 2016-04-30.\n'
        self.send_and_test_stream_message("milestone_changed_time", u'subject', message)

    def test_taiga_milestone_changed_name(self):
        # type: () -> None
        message = u':notebook: Antek renamed sprint from New sprint to **Newer sprint**.\n'
        self.send_and_test_stream_message("milestone_changed_name", u'subject', message)

    def test_taiga_issue_created(self):
        # type: () -> None
        message = u':bulb: Antek created issue **A new issue**.\n'
        self.send_and_test_stream_message("issue_created", u'subject', message)

    def test_taiga_issue_deleted(self):
        # type: () -> None
        message = u':x: Antek deleted issue **Aaaa**.\n'
        self.send_and_test_stream_message("issue_deleted", u'subject', message)

    def test_taiga_issue_changed_assigned(self):
        # type: () -> None
        message = u':busts_in_silhouette: Antek assigned issue **Aaaa** to Antek.\n'
        self.send_and_test_stream_message("issue_changed_assigned", u'subject', message)

    def test_taiga_issue_changed_reassigned(self):
        # type: () -> None
        message = u':busts_in_silhouette: Antek reassigned issue **Aaaa** from Antek to Han Solo.\n'
        self.send_and_test_stream_message("issue_changed_reassigned", u'subject', message)

    def test_taiga_issue_changed_subject(self):
        # type: () -> None
        message = u':notebook: Antek renamed issue Aaaa to **More descriptive name**.\n'
        self.send_and_test_stream_message("issue_changed_subject", u'subject', message)

    def test_taiga_issue_changed_description(self):
        # type: () -> None
        message = u':notebook: Antek updated description of issue **More descriptive name**.\n'
        self.send_and_test_stream_message("issue_changed_description", u'subject', message)

    def test_taiga_issue_changed_type(self):
        # type: () -> None
        message = u':bulb: Antek changed type of issue **A new issue** from Bug to Enhancement.\n'
        self.send_and_test_stream_message("issue_changed_type", u'subject', message)

    def test_taiga_issue_changed_status(self):
        # type: () -> None
        message = u':chart_with_upwards_trend: Antek changed status of issue **A new issue** from New to Rejected.\n'
        self.send_and_test_stream_message("issue_changed_status", u'subject', message)

    def test_taiga_issue_changed_severity(self):
        # type: () -> None
        message = u':warning: Antek changed severity of issue **A new issue** from Important to Critical.\n'
        self.send_and_test_stream_message("issue_changed_severity", u'subject', message)

    def test_taiga_issue_changed_priority(self):
        # type: () -> None
        message = u':rocket: Antek changed priority of issue **A new issue** from Normal to High.\n'
        self.send_and_test_stream_message("issue_changed_priority", u'subject', message)

    def test_taiga_userstory_comment_added(self):
        # type: () -> None
        message = u':thought_balloon: Han Solo commented on user story **Great US**.\n'
        self.send_and_test_stream_message("userstory_changed_comment_added", u'subject', message)

    def test_taiga_task_changed_comment_added(self):
        # type: () -> None
        message = u':thought_balloon: Antek commented on task **New task assigned and in progress**.\n'
        self.send_and_test_stream_message("task_changed_comment_added", u'subject', message)

    def test_taiga_issue_changed_comment_added(self):
        # type: () -> None
        message = u':thought_balloon: Antek commented on issue **Aaaa**.\n'
        self.send_and_test_stream_message("issue_changed_comment_added", u'subject', message)
