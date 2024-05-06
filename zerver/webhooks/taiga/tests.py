from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase


class TaigaHookTests(WebhookTestCase):
    CHANNEL_NAME = "taiga"
    TOPIC_NAME = "subject"
    URL_TEMPLATE = "/api/v1/external/taiga?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "taiga"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.url = self.build_webhook_url(topic=self.TOPIC_NAME)

    def test_taiga_userstory_deleted(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) deleted user story **New userstory**."
        self.check_webhook("userstory_deleted", self.TOPIC_NAME, message)

    def test_taiga_userstory_created(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) created user story **New userstory**."
        self.check_webhook("userstory_created", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_unblocked(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) unblocked user story **UserStory**."
        self.check_webhook("userstory_changed_unblocked", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_subject(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) renamed user story from UserStory to **UserStoryNewSubject**."
        self.check_webhook("userstory_changed_subject", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_status(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) changed status of user story **UserStory** from Ready to In progress."
        self.check_webhook("userstory_changed_status", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_reassigned(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) reassigned user story **UserStory** from TomaszKolek to HanSolo."
        self.check_webhook("userstory_changed_reassigned", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_unassigned(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) unassigned user story **UserStory**."
        self.check_webhook("userstory_changed_unassigned", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_points(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) changed estimation of user story **UserStory**."
        self.check_webhook("userstory_changed_points", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_new_sprint(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) added user story **UserStory** to sprint Sprint1."
        self.check_webhook("userstory_changed_new_sprint", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_sprint(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) changed sprint of user story **UserStory** from Sprint1 to Sprint2."
        self.check_webhook("userstory_changed_sprint", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_remove_sprint(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) removed user story **UserStory** from sprint Sprint2."
        self.check_webhook("userstory_changed_remove_sprint", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_description(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) updated description of user story **UserStory**."
        self.check_webhook("userstory_changed_description", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_closed(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) changed status of user story **UserStory** from New to Done.\n[TomaszKolek](https://tree.taiga.io/profile/kolaszek) closed user story **UserStory**."
        self.check_webhook("userstory_changed_closed", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_reopened(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) changed status of user story **UserStory** from Done to Ready.\n[TomaszKolek](https://tree.taiga.io/profile/kolaszek) reopened user story **UserStory**."
        self.check_webhook("userstory_changed_reopened", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_blocked(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) blocked user story **UserStory**."
        self.check_webhook("userstory_changed_blocked", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_assigned(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) assigned user story **UserStory** to TomaszKolek."
        self.check_webhook("userstory_changed_assigned", self.TOPIC_NAME, message)

    def test_taiga_userstory_comment_added(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) commented on user story **UserStory**."
        self.check_webhook("userstory_changed_comment_added", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_due_date(self) -> None:
        message = (
            "[Aditya Verma](https://tree.taiga.io/profile/orientor) changed due date of user story"
            " [Nice Issue](https://tree.taiga.io/project/orientor-sd/us/54) from 2020-02-15 to"
            " 2020-02-22."
        )
        self.check_webhook("userstory_changed_due_date", self.TOPIC_NAME, message)

    def test_taiga_userstory_changed_new_due_date(self) -> None:
        message = "[Aditya Verma](https://tree.taiga.io/profile/orientor) set due date of user story [random](https://tree.taiga.io/project/orientor-sd/us/58) to 2020-02-15."
        self.check_webhook("userstory_changed_new_due_date", self.TOPIC_NAME, message)

    def test_taiga_task_created(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) created task **New Task**."
        self.check_webhook("task_created", self.TOPIC_NAME, message)

    def test_taiga_task_changed_user_stories(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) added task **Get this task done** to sprint Another one.\n[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) moved task **Get this task done** from user story #7 Yaar ne scirra! to #8 A related user story, which is epic."
        self.check_webhook("task_changed_user_stories", self.TOPIC_NAME, message)

    def test_taiga_task_changed_status(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) changed status of task **New Task** from New to In progress."
        self.check_webhook("task_changed_status", self.TOPIC_NAME, message)

    def test_taiga_task_changed_blocked(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) blocked task **New Task**."
        self.check_webhook("task_changed_blocked", self.TOPIC_NAME, message)

    def test_taiga_task_changed_blocked_link(self) -> None:
        message = "[Aditya Verma](https://tree.taiga.io/profile/orientor) blocked task [nice task](https://tree.taiga.io/project/orientor-sd/task/56)."
        self.check_webhook("task_changed_blocked_link", self.TOPIC_NAME, message)

    def test_taiga_task_changed_unblocked(self) -> None:
        message = (
            "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) unblocked task **New Task**."
        )
        self.check_webhook("task_changed_unblocked", self.TOPIC_NAME, message)

    def test_taiga_task_changed_assigned(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) assigned task **New Task** to TomaszKolek."
        self.check_webhook("task_changed_assigned", self.TOPIC_NAME, message)

    def test_taiga_task_changed_reassigned(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) reassigned task **New Task** from HanSolo to TomaszKolek."
        self.check_webhook("task_changed_reassigned", self.TOPIC_NAME, message)

    def test_taiga_task_changed_subject(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) renamed task New Task to **New Task Subject**."
        self.check_webhook("task_changed_subject", self.TOPIC_NAME, message)

    def test_taiga_task_changed_description(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) updated description of task **New Task**."
        self.check_webhook("task_changed_description", self.TOPIC_NAME, message)

    def test_taiga_task_deleted(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) deleted task **New Task**."
        self.check_webhook("task_deleted", self.TOPIC_NAME, message)

    def test_taiga_task_changed_comment_added(self) -> None:
        message = (
            "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) commented on task **New Task**."
        )
        self.check_webhook("task_changed_comment_added", self.TOPIC_NAME, message)

    def test_taiga_task_changed_due_date(self) -> None:
        message = (
            "[Aditya Verma](https://tree.taiga.io/profile/orientor) changed due date of task"
            " [nice task](https://tree.taiga.io/project/orientor-sd/task/56) from 2020-02-22 to"
            " 2020-02-15."
        )
        self.check_webhook("task_changed_due_date", self.TOPIC_NAME, message)

    def test_taiga_task_changed_new_due_date(self) -> None:
        message = "[Aditya Verma](https://tree.taiga.io/profile/orientor) set due date of task [nice task](https://tree.taiga.io/project/orientor-sd/task/56) to 2020-02-22."
        self.check_webhook("task_changed_new_due_date", self.TOPIC_NAME, message)

    def test_taiga_sprint_created(self) -> None:
        message = (
            "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) created sprint **New sprint**."
        )
        self.check_webhook("sprint_created", self.TOPIC_NAME, message)

    def test_taiga_sprint_deleted(self) -> None:
        message = (
            "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) deleted sprint **New name**."
        )
        self.check_webhook("sprint_deleted", self.TOPIC_NAME, message)

    def test_taiga_sprint_changed_time(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) changed estimated finish of sprint **New sprint** from 2017-01-24 to 2017-01-25."
        self.check_webhook("sprint_changed_time", self.TOPIC_NAME, message)

    def test_taiga_sprint_changed_name(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) renamed sprint from New sprint to **New name**."
        self.check_webhook("sprint_changed_name", self.TOPIC_NAME, message)

    def test_taiga_issue_created(self) -> None:
        message = (
            "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) created issue **New issue**."
        )
        self.check_webhook("issue_created", self.TOPIC_NAME, message)

    def test_taiga_issue_created_link(self) -> None:
        message = "[Aditya Verma](https://tree.taiga.io/profile/orientor) created issue [Issues](https://tree.taiga.io/project/orientor-sd/issue/49)."
        self.check_webhook("issue_created_link", self.TOPIC_NAME, message)

    def test_taiga_issue_deleted(self) -> None:
        message = (
            "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) deleted issue **New issue**."
        )
        self.check_webhook("issue_deleted", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_assigned(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) assigned issue **New issue** to TomaszKolek."
        self.check_webhook("issue_changed_assigned", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_reassigned(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) reassigned issue **New issue** from TomaszKolek to HanSolo."
        self.check_webhook("issue_changed_reassigned", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_subject(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) renamed issue New issue to **New issueNewSubject**."
        self.check_webhook("issue_changed_subject", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_description(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) updated description of issue **New issue**."
        self.check_webhook("issue_changed_description", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_type(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) changed type of issue **New issue** from Bug to Question."
        self.check_webhook("issue_changed_type", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_status(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) changed status of issue **New issue** from New to In progress."
        self.check_webhook("issue_changed_status", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_severity(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) changed severity of issue **New issue** from Normal to Minor."
        self.check_webhook("issue_changed_severity", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_priority(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) changed priority of issue **New issue** from Normal to Low."
        self.check_webhook("issue_changed_priority", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_comment_added(self) -> None:
        message = "[TomaszKolek](https://tree.taiga.io/profile/kolaszek) commented on issue **New issue**."
        self.check_webhook("issue_changed_comment_added", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_blocked(self) -> None:
        message = "[Aditya Verma](https://tree.taiga.io/profile/orientor) blocked issue [Issues](https://tree.taiga.io/project/orientor-sd/issue/49)."
        self.check_webhook("issue_changed_blocked", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_unblocked(self) -> None:
        message = "[Aditya Verma](https://tree.taiga.io/profile/orientor) unblocked issue [Issues](https://tree.taiga.io/project/orientor-sd/issue/49)."
        self.check_webhook("issue_changed_unblocked", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_due_date(self) -> None:
        message = (
            "[Aditya Verma](https://tree.taiga.io/profile/orientor) changed due date of issue"
            " [Issues](https://tree.taiga.io/project/orientor-sd/issue/49) from 2020-03-08 to"
            " 2020-02-22."
        )
        self.check_webhook("issue_changed_due_date", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_new_due_date(self) -> None:
        message = "[Aditya Verma](https://tree.taiga.io/profile/orientor) set due date of issue [Nice Issue](https://tree.taiga.io/project/orientor-sd/issue/53) to 2020-02-22."
        self.check_webhook("issue_changed_new_due_date", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_new_sprint(self) -> None:
        message = "[Aditya Verma](https://tree.taiga.io/profile/orientor) added issue [Nice Issue](https://tree.taiga.io/project/orientor-sd/issue/53) to sprint eres."
        self.check_webhook("issue_changed_new_sprint", self.TOPIC_NAME, message)

    def test_taiga_issue_changed_remove_sprint(self) -> None:
        message = "[Aditya Verma](https://tree.taiga.io/profile/orientor) detached issue [Nice Issue](https://tree.taiga.io/project/orientor-sd/issue/53) from sprint eres."
        self.check_webhook("issue_changed_remove_sprint", self.TOPIC_NAME, message)

    def test_taiga_epic_created(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) created epic **Zulip is awesome!**."
        self.check_webhook("epic_created", self.TOPIC_NAME, message)

    def test_taiga_epic_changed_assigned(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) assigned epic **Zulip is awesome!** to Eeshan Garg."
        self.check_webhook("epic_changed_assigned", self.TOPIC_NAME, message)

    def test_taiga_epic_changed_unassigned(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) unassigned epic **Zulip is awesome!**."
        self.check_webhook("epic_changed_unassigned", self.TOPIC_NAME, message)

    def test_taiga_epic_changed_reassigned(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) reassigned epic **Zulip is awesome!** from Eeshan Garg to Angela Johnson."
        self.check_webhook("epic_changed_reassigned", self.TOPIC_NAME, message)

    def test_taiga_epic_changed_blocked(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) blocked epic **Zulip is awesome!**."
        self.check_webhook("epic_changed_blocked", self.TOPIC_NAME, message)

    def test_taiga_epic_changed_unblocked(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) unblocked epic **Zulip is awesome!**."
        self.check_webhook("epic_changed_unblocked", self.TOPIC_NAME, message)

    def test_taiga_epic_changed_status(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) changed status of epic **Zulip is awesome!** from New to In progress."
        self.check_webhook("epic_changed_status", self.TOPIC_NAME, message)

    def test_taiga_epic_changed_renamed(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) renamed epic from **Zulip is awesome!** to **Zulip is great!**."
        self.check_webhook("epic_changed_renamed", self.TOPIC_NAME, message)

    def test_taiga_epic_changed_description(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) updated description of epic **Zulip is great!**."
        self.check_webhook("epic_changed_description", self.TOPIC_NAME, message)

    def test_taiga_epic_changed_commented(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) commented on epic **Zulip is great!**."
        self.check_webhook("epic_changed_commented", self.TOPIC_NAME, message)

    def test_taiga_epic_deleted(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) deleted epic **Zulip is great!**."
        self.check_webhook("epic_deleted", self.TOPIC_NAME, message)

    def test_taiga_relateduserstory_created(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) added a related user story **A related user story** to the epic **This is Epic!**."
        self.check_webhook("relateduserstory_created", self.TOPIC_NAME, message)

    def test_taiga_relateduserstory_created_link(self) -> None:
        message = (
            "[Aditya Verma](https://tree.taiga.io/profile/orientor) added a related user story"
            " [Nice Issue](https://tree.taiga.io/project/orientor-sd/us/54) to the epic"
            " [ASAS](https://tree.taiga.io/project/orientor-sd/epic/42)."
        )
        self.check_webhook("relateduserstory_created_link", self.TOPIC_NAME, message)

    def test_taiga_relateduserstory_deleted(self) -> None:
        message = "[Eeshan Garg](https://tree.taiga.io/profile/eeshangarg) removed a related user story **A related user story, which is epic** from the epic **This is Epic!**."
        self.check_webhook("relateduserstory_deleted", self.TOPIC_NAME, message)

    def test_taiga_webhook_test(self) -> None:
        message = (
            "[Jan](https://tree.taiga.io/profile/kostek) triggered a test of the Taiga integration."
        )
        self.check_webhook("webhook_test", self.TOPIC_NAME, message)
