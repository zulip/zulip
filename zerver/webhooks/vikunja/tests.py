from unittest.mock import patch

from zerver.lib.test_classes import WebhookTestCase


class VikunjaHookTests(WebhookTestCase):
    CHANNEL_NAME = "vikunja"
    URL_TEMPLATE = "/api/v1/external/vikunja?api_key={api_key}&stream={stream}&host_url=https://vikunja.example.com"
    WEBHOOK_DIR_NAME = "vikunja"

    # Task event tests
    def test_vikunja_task_created(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe created [A very important task](https://vikunja.example.com/tasks/673) in [Meeting](https://vikunja.example.com/projects/26) > Agenda."
        self.check_webhook("task_created", expected_topic_name, expected_message)

    def test_vikunja_task_updated(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe updated :purple_circle: [A very important task](https://vikunja.example.com/tasks/539) in [Meeting](https://vikunja.example.com/projects/26) > To Do.\n```spoiler Show details...\n\n:red_circle: `Important`\n---\n:blue_square: Start date: <time:2026-02-01T09:00:00+01:00>\n:red_square: End date: <time:2026-02-28T17:00:00+01:00>\n---\n:exclamation: Priority: High\n---\n:chart: Progress: ████░░░░░░ 40%\n---\n~~~ quote\n# Attention\n\nThis is a task that is very important.\n~~~\n```"
        self.check_webhook("task_updated", expected_topic_name, expected_message)

    def test_vikunja_task_updated_with_tasklist(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe updated [Task with checklist](https://vikunja.example.com/tasks/540) in [Meeting](https://vikunja.example.com/projects/26) > To Do.\n```spoiler Show details...\n\n~~~ quote\nHere are the steps:\n\n```\n[x] First step completed\n[ ] Second step pending\n[ ] Third step pending\n```\n~~~\n```"
        self.check_webhook("task_updated_with_tasklist", expected_topic_name, expected_message)

    def test_vikunja_task_deleted(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe deleted *new task* `#54` from [Meeting](https://vikunja.example.com/projects/26)."
        self.check_webhook("task_deleted", expected_topic_name, expected_message)

    def test_vikunja_task_assignee_created(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe added John Doe to [hallo](https://vikunja.example.com/tasks/674) in [Meeting](https://vikunja.example.com/projects/26) > Agenda."
        self.check_webhook("task_assignee_created", expected_topic_name, expected_message)

    def test_vikunja_task_assignee_deleted(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe removed John Doe from [task](https://vikunja.example.com/tasks/689) in [Meeting](https://vikunja.example.com/projects/26) > Agenda."
        self.check_webhook("task_assignee_deleted", expected_topic_name, expected_message)

    def test_vikunja_task_comment_created(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe commented on [:P](https://vikunja.example.com/tasks/677) in [Meeting](https://vikunja.example.com/projects/26) > Agenda:\n~~~ quote\nHello this is a comment\n~~~"
        self.check_webhook("task_comment_created", expected_topic_name, expected_message)

    def test_vikunja_task_comment_edited(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe edited a comment on [:P](https://vikunja.example.com/tasks/677) in [Meeting](https://vikunja.example.com/projects/26) > Agenda:\n~~~ quote\nComment new\n~~~"
        self.check_webhook("task_comment_edited", expected_topic_name, expected_message)

    def test_vikunja_task_comment_deleted(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe removed this comment by John Doe from [new task](https://vikunja.example.com/tasks/684) in [Meeting](https://vikunja.example.com/projects/26) > Agenda:\n~~~ quote\nhi\n~~~"
        self.check_webhook("task_comment_deleted", expected_topic_name, expected_message)

    def test_vikunja_task_attachment_created(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe added the attachment `image.png` to [:P](https://vikunja.example.com/tasks/677) in [Meeting](https://vikunja.example.com/projects/26) > Agenda."
        self.check_webhook("task_attachment_created", expected_topic_name, expected_message)

    def test_vikunja_task_attachment_deleted(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe removed the attachment `image.png` from [new task](https://vikunja.example.com/tasks/684) in [Meeting](https://vikunja.example.com/projects/26) > Agenda."
        self.check_webhook("task_attachment_deleted", expected_topic_name, expected_message)

    def test_vikunja_task_relation_created(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe set [Task2](https://vikunja.example.com/tasks/680) as a related task of [Task1](https://vikunja.example.com/tasks/679)."
        self.check_webhook("task_relation_created", expected_topic_name, expected_message)

    def test_vikunja_task_relation_deleted(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe removed the relation of [this task](https://vikunja.example.com/tasks/675) as a related task of [task](https://vikunja.example.com/tasks/689)."
        self.check_webhook("task_relation_deleted", expected_topic_name, expected_message)

    # Project event tests
    def test_vikunja_project_updated(self) -> None:
        expected_topic_name = "Test"
        expected_message = (
            "John Doe updated the project [Test](https://vikunja.example.com/projects/35)."
        )
        self.check_webhook("project_updated", expected_topic_name, expected_message)

    def test_vikunja_project_deleted(self) -> None:
        expected_topic_name = "Test"
        expected_message = "John Doe deleted the project *Test* `ID: 35`."
        self.check_webhook("project_deleted", expected_topic_name, expected_message)

    def test_vikunja_project_shared_user(self) -> None:
        expected_topic_name = "Test"
        expected_message = (
            "John Doe shared [Test](https://vikunja.example.com/projects/35) with Admin User."
        )
        self.check_webhook("project_shared_user", expected_topic_name, expected_message)

    def test_vikunja_project_shared_team(self) -> None:
        expected_topic_name = "Test"
        expected_message = "John Doe shared [Test](https://vikunja.example.com/projects/35) with team `IT (OIDC)` consisting of `2` member(s)."
        self.check_webhook("project_shared_team", expected_topic_name, expected_message)

    # Edge case tests
    def test_vikunja_task_updated_priority_out_of_range(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe updated [Task with priority 6](https://vikunja.example.com/tasks/541) in [Meeting](https://vikunja.example.com/projects/26) > To Do.\n```spoiler Show details...\n\n~~~ quote\nThis task has a priority of 6, which is out of the supported range.\n~~~\n```"
        self.check_webhook(
            "task_updated_priority_out_of_range", expected_topic_name, expected_message
        )

    def test_vikunja_task_updated_malformed_tasklist(self) -> None:
        expected_topic_name = "Meeting"
        expected_message = "John Doe updated [Task with malformed checklist](https://vikunja.example.com/tasks/542) in [Meeting](https://vikunja.example.com/projects/26) > To Do.\n```spoiler Show details...\n\n~~~ quote\nHere is a malformed task list:\n\n\n~~~\n```"
        self.check_webhook("task_updated_malformed_tasklist", expected_topic_name, expected_message)

    def test_ignored_event(self) -> None:
        payload = self.get_body("task_ignored_event")
        self.verify_post_is_ignored(payload)

    def verify_post_is_ignored(self, payload: str) -> None:
        with patch("zerver.webhooks.vikunja.view.check_send_webhook_message") as m:
            result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(m.called)
        self.assert_json_success(result)

    def test_unknown_event_type(self) -> None:
        payload = '{"event_name": "unknown_event_type"}'
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_success(result)
        self.assert_in_response(
            "The 'unknown_event_type' event isn't currently supported by the Vikunja webhook; ignoring",
            result,
        )
