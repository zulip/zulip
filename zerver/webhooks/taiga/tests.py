# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class TaigaHookTests(WebhookTestCase):
    STREAM_NAME = 'taiga'
    TOPIC = "subject"
    URL_TEMPLATE = u"/api/v1/external/taiga?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'taiga'

    def setUp(self) -> None:
        self.url = self.build_webhook_url(topic=self.TOPIC)

    def test_taiga_userstory_deleted(self) -> None:
        message = u'TomaszKolek deleted user story **New userstory**.'
        self.send_and_test_stream_message("userstory_deleted", self.TOPIC, message)

    def test_taiga_userstory_created(self) -> None:
        message = u'TomaszKolek created user story **New userstory**.'
        self.send_and_test_stream_message("userstory_created", self.TOPIC, message)

    def test_taiga_userstory_changed_unblocked(self) -> None:
        message = u'TomaszKolek unblocked user story **UserStory**.'
        self.send_and_test_stream_message("userstory_changed_unblocked", self.TOPIC, message)

    def test_taiga_userstory_changed_subject(self) -> None:
        message = u'TomaszKolek renamed user story from UserStory to **UserStoryNewSubject**.'
        self.send_and_test_stream_message("userstory_changed_subject", self.TOPIC, message)

    def test_taiga_userstory_changed_status(self) -> None:
        message = u'TomaszKolek changed status of user story **UserStory** from Ready to In progress.'
        self.send_and_test_stream_message("userstory_changed_status", self.TOPIC, message)

    def test_taiga_userstory_changed_reassigned(self) -> None:
        message = u'TomaszKolek reassigned user story **UserStory** from TomaszKolek to HanSolo.'
        self.send_and_test_stream_message("userstory_changed_reassigned", self.TOPIC, message)

    def test_taiga_userstory_changed_unassigned(self) -> None:
        message = u'TomaszKolek unassigned user story **UserStory**.'
        self.send_and_test_stream_message("userstory_changed_unassigned", self.TOPIC, message)

    def test_taiga_userstory_changed_points(self) -> None:
        message = u'TomaszKolek changed estimation of user story **UserStory**.'
        self.send_and_test_stream_message("userstory_changed_points", self.TOPIC, message)

    def test_taiga_userstory_changed_new_sprint(self) -> None:
        message = u'TomaszKolek added user story **UserStory** to sprint Sprint1.'
        self.send_and_test_stream_message("userstory_changed_new_sprint", self.TOPIC, message)

    def test_taiga_userstory_changed_sprint(self) -> None:
        message = u'TomaszKolek changed sprint of user story **UserStory** from Sprint1 to Sprint2.'
        self.send_and_test_stream_message("userstory_changed_sprint", self.TOPIC, message)

    def test_taiga_userstory_changed_remove_sprint(self) -> None:
        message = u'TomaszKolek removed user story **UserStory** from sprint Sprint2.'
        self.send_and_test_stream_message("userstory_changed_remove_sprint", self.TOPIC, message)

    def test_taiga_userstory_changed_description(self) -> None:
        message = u'TomaszKolek updated description of user story **UserStory**.'
        self.send_and_test_stream_message("userstory_changed_description", self.TOPIC, message)

    def test_taiga_userstory_changed_closed(self) -> None:
        message = u'TomaszKolek changed status of user story **UserStory** from New to Done.\nTomaszKolek closed user story **UserStory**.'
        self.send_and_test_stream_message("userstory_changed_closed", self.TOPIC, message)

    def test_taiga_userstory_changed_reopened(self) -> None:
        message = u'TomaszKolek changed status of user story **UserStory** from Done to Ready.\nTomaszKolek reopened user story **UserStory**.'
        self.send_and_test_stream_message("userstory_changed_reopened", self.TOPIC, message)

    def test_taiga_userstory_changed_blocked(self) -> None:
        message = u'TomaszKolek blocked user story **UserStory**.'
        self.send_and_test_stream_message("userstory_changed_blocked", self.TOPIC, message)

    def test_taiga_userstory_changed_assigned(self) -> None:
        message = u'TomaszKolek assigned user story **UserStory** to TomaszKolek.'
        self.send_and_test_stream_message("userstory_changed_assigned", self.TOPIC, message)

    def test_taiga_userstory_comment_added(self) -> None:
        message = u'TomaszKolek commented on user story **UserStory**.'
        self.send_and_test_stream_message("userstory_changed_comment_added", self.TOPIC, message)

    def test_taiga_task_created(self) -> None:
        message = u'TomaszKolek created task **New Task**.'
        self.send_and_test_stream_message("task_created", self.TOPIC, message)

    def test_taiga_task_changed_user_stories(self) -> None:
        message = u'Eeshan Garg added task **Get this task done** to sprint Another one.\nEeshan Garg moved task **Get this task done** from user story #7 Yaar ne scirra! to #8 A related user story, which is epic.'
        self.send_and_test_stream_message("task_changed_user_stories", self.TOPIC, message)

    def test_taiga_task_changed_status(self) -> None:
        message = u'TomaszKolek changed status of task **New Task** from New to In progress.'
        self.send_and_test_stream_message("task_changed_status", self.TOPIC, message)

    def test_taiga_task_changed_blocked(self) -> None:
        message = u'TomaszKolek blocked task **New Task**.'
        self.send_and_test_stream_message("task_changed_blocked", self.TOPIC, message)

    def test_taiga_task_changed_unblocked(self) -> None:
        message = u'TomaszKolek unblocked task **New Task**.'
        self.send_and_test_stream_message("task_changed_unblocked", self.TOPIC, message)

    def test_taiga_task_changed_assigned(self) -> None:
        message = u'TomaszKolek assigned task **New Task** to TomaszKolek.'
        self.send_and_test_stream_message("task_changed_assigned", self.TOPIC, message)

    def test_taiga_task_changed_reassigned(self) -> None:
        message = u'TomaszKolek reassigned task **New Task** from HanSolo to TomaszKolek.'
        self.send_and_test_stream_message("task_changed_reassigned", self.TOPIC, message)

    def test_taiga_task_changed_subject(self) -> None:
        message = u'TomaszKolek renamed task New Task to **New Task Subject**.'
        self.send_and_test_stream_message("task_changed_subject", self.TOPIC, message)

    def test_taiga_task_changed_description(self) -> None:
        message = u'TomaszKolek updated description of task **New Task**.'
        self.send_and_test_stream_message("task_changed_description", self.TOPIC, message)

    def test_taiga_task_deleted(self) -> None:
        message = u'TomaszKolek deleted task **New Task**.'
        self.send_and_test_stream_message("task_deleted", self.TOPIC, message)

    def test_taiga_task_changed_comment_added(self) -> None:
        message = u'TomaszKolek commented on task **New Task**.'
        self.send_and_test_stream_message("task_changed_comment_added", self.TOPIC, message)

    def test_taiga_sprint_created(self) -> None:
        message = u'TomaszKolek created sprint **New sprint**.'
        self.send_and_test_stream_message("sprint_created", self.TOPIC, message)

    def test_taiga_sprint_deleted(self) -> None:
        message = u'TomaszKolek deleted sprint **New name**.'
        self.send_and_test_stream_message("sprint_deleted", self.TOPIC, message)

    def test_taiga_sprint_changed_time(self) -> None:
        message = u'TomaszKolek changed estimated finish of sprint **New sprint** from 2017-01-24 to 2017-01-25.'
        self.send_and_test_stream_message("sprint_changed_time", self.TOPIC, message)

    def test_taiga_sprint_changed_name(self) -> None:
        message = u'TomaszKolek renamed sprint from New sprint to **New name**.'
        self.send_and_test_stream_message("sprint_changed_name", self.TOPIC, message)

    def test_taiga_issue_created(self) -> None:
        message = u'TomaszKolek created issue **New issue**.'
        self.send_and_test_stream_message("issue_created", self.TOPIC, message)

    def test_taiga_issue_deleted(self) -> None:
        message = u'TomaszKolek deleted issue **New issue**.'
        self.send_and_test_stream_message("issue_deleted", self.TOPIC, message)

    def test_taiga_issue_changed_assigned(self) -> None:
        message = u'TomaszKolek assigned issue **New issue** to TomaszKolek.'
        self.send_and_test_stream_message("issue_changed_assigned", self.TOPIC, message)

    def test_taiga_issue_changed_reassigned(self) -> None:
        message = u'TomaszKolek reassigned issue **New issue** from TomaszKolek to HanSolo.'
        self.send_and_test_stream_message("issue_changed_reassigned", self.TOPIC, message)

    def test_taiga_issue_changed_subject(self) -> None:
        message = u'TomaszKolek renamed issue New issue to **New issueNewSubject**.'
        self.send_and_test_stream_message("issue_changed_subject", self.TOPIC, message)

    def test_taiga_issue_changed_description(self) -> None:
        message = u'TomaszKolek updated description of issue **New issue**.'
        self.send_and_test_stream_message("issue_changed_description", self.TOPIC, message)

    def test_taiga_issue_changed_type(self) -> None:
        message = u'TomaszKolek changed type of issue **New issue** from Bug to Question.'
        self.send_and_test_stream_message("issue_changed_type", self.TOPIC, message)

    def test_taiga_issue_changed_status(self) -> None:
        message = u'TomaszKolek changed status of issue **New issue** from New to In progress.'
        self.send_and_test_stream_message("issue_changed_status", self.TOPIC, message)

    def test_taiga_issue_changed_severity(self) -> None:
        message = u'TomaszKolek changed severity of issue **New issue** from Normal to Minor.'
        self.send_and_test_stream_message("issue_changed_severity", self.TOPIC, message)

    def test_taiga_issue_changed_priority(self) -> None:
        message = u'TomaszKolek changed priority of issue **New issue** from Normal to Low.'
        self.send_and_test_stream_message("issue_changed_priority", self.TOPIC, message)

    def test_taiga_issue_changed_comment_added(self) -> None:
        message = u'TomaszKolek commented on issue **New issue**.'
        self.send_and_test_stream_message("issue_changed_comment_added", self.TOPIC, message)

    def test_taiga_epic_created(self) -> None:
        message = u'Eeshan Garg created epic **Zulip is awesome!**'
        self.send_and_test_stream_message("epic_created", self.TOPIC, message)

    def test_taiga_epic_changed_assigned(self) -> None:
        message = u'Eeshan Garg assigned epic **Zulip is awesome!** to Eeshan Garg.'
        self.send_and_test_stream_message("epic_changed_assigned", self.TOPIC, message)

    def test_taiga_epic_changed_unassigned(self) -> None:
        message = u'Eeshan Garg unassigned epic **Zulip is awesome!**'
        self.send_and_test_stream_message("epic_changed_unassigned", self.TOPIC, message)

    def test_taiga_epic_changed_reassigned(self) -> None:
        message = u'Eeshan Garg reassigned epic **Zulip is awesome!** from Eeshan Garg to Angela Johnson.'
        self.send_and_test_stream_message("epic_changed_reassigned", self.TOPIC, message)

    def test_taiga_epic_changed_blocked(self) -> None:
        message = u'Eeshan Garg blocked epic **Zulip is awesome!**'
        self.send_and_test_stream_message("epic_changed_blocked", self.TOPIC, message)

    def test_taiga_epic_changed_unblocked(self) -> None:
        message = u'Eeshan Garg unblocked epic **Zulip is awesome!**'
        self.send_and_test_stream_message("epic_changed_unblocked", self.TOPIC, message)

    def test_taiga_epic_changed_status(self) -> None:
        message = u'Eeshan Garg changed status of epic **Zulip is awesome!** from New to In progress.'
        self.send_and_test_stream_message("epic_changed_status", self.TOPIC, message)

    def test_taiga_epic_changed_renamed(self) -> None:
        message = u'Eeshan Garg renamed epic from **Zulip is awesome!** to **Zulip is great!**'
        self.send_and_test_stream_message("epic_changed_renamed", self.TOPIC, message)

    def test_taiga_epic_changed_description(self) -> None:
        message = u'Eeshan Garg updated description of epic **Zulip is great!**'
        self.send_and_test_stream_message("epic_changed_description", self.TOPIC, message)

    def test_taiga_epic_changed_commented(self) -> None:
        message = u'Eeshan Garg commented on epic **Zulip is great!**'
        self.send_and_test_stream_message("epic_changed_commented", self.TOPIC, message)

    def test_taiga_epic_deleted(self) -> None:
        message = u'Eeshan Garg deleted epic **Zulip is great!**'
        self.send_and_test_stream_message("epic_deleted", self.TOPIC, message)

    def test_taiga_relateduserstory_created(self) -> None:
        message = u'Eeshan Garg added a related user story **A related user story** to the epic **This is Epic!**'
        self.send_and_test_stream_message("relateduserstory_created", self.TOPIC, message)

    def test_taiga_relateduserstory_deleted(self) -> None:
        message = u'Eeshan Garg removed a related user story **A related user story, which is epic** from the epic **This is Epic!**'
        self.send_and_test_stream_message("relateduserstory_deleted", self.TOPIC, message)
