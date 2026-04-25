from django.utils.timezone import now
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.messages import Task


class TasksViewTest(ZulipTestCase):
    def _assert_my_tasks_payload_shape(self, task: dict[str, object]) -> None:
        self.assertEqual(
            set(task.keys()),
            {
                "task_id",
                "title",
                "completed",
                "due_date",
                "message_id",
                "stream_id",
                "topic",
                "creator_email",
                "created_at",
            },
        )

    def test_list_my_tasks_empty(self) -> None:
        hamlet = self.example_user("hamlet")

        result = self.api_get(hamlet, "/api/v1/users/me/tasks")
        data = self.assert_json_success(result)
        self.assertIn("tasks", data)
        self.assertEqual(data["tasks"], [])

    def test_list_my_tasks_returns_only_assigned_tasks(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        stream_message_id = self.send_stream_message(cordelia, "Verona", content="Please fix this")
        dm_message_id = self.send_personal_message(cordelia, hamlet, "Please follow up")

        Task.objects.create(
            message_id=stream_message_id,
            assignee=hamlet,
            creator=cordelia,
            title="Fix bug",
            description="There is a bug in the code",
        )
        Task.objects.create(
            message_id=dm_message_id,
            assignee=hamlet,
            creator=cordelia,
            title="Follow up",
            description="Ask for update",
        )
        Task.objects.create(
            message_id=stream_message_id,
            assignee=othello,
            creator=cordelia,
            title="other assignee",
            description="",
        )

        result = self.api_get(hamlet, "/api/v1/users/me/tasks")
        data = self.assert_json_success(result)

        tasks = data["tasks"]
        self.assert_length(tasks, 2)
        self.assertCountEqual([task["title"] for task in tasks], ["Fix bug", "Follow up"])

    def test_list_my_tasks_stream_message_includes_navigation_fields(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        message_id = self.send_stream_message(cordelia, "Verona", topic_name="deploy", content="Deploy this")
        due_date = now()
        created_task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=cordelia,
            title="Deploy fix",
            description="Ship the change",
            due_date=due_date,
            completed=True,
        )

        result = self.api_get(hamlet, "/api/v1/users/me/tasks")
        data = self.assert_json_success(result)

        self.assert_length(data["tasks"], 1)
        task = data["tasks"][0]

        self.assertEqual(task["task_id"], created_task.id)
        self.assertEqual(task["title"], "Deploy fix")
        self.assertTrue(task["completed"])
        self.assertEqual(task["due_date"], due_date.isoformat())
        self.assertEqual(task["message_id"], message_id)
        self.assertEqual(task["topic"], "deploy")
        self.assertEqual(task["creator_email"], cordelia.email)
        self.assertIsNotNone(task["stream_id"])
        self.assertIsNotNone(task["created_at"])

    def test_list_my_tasks_dm_message_has_no_stream_metadata(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        message_id = self.send_personal_message(othello, hamlet, "Follow up on this")
        Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=othello,
            title="Follow up",
            description="Ask for update",
        )
        result = self.api_get(hamlet, "/api/v1/users/me/tasks")
        data = self.assert_json_success(result)

        self.assert_length(data["tasks"], 1)
        task = data["tasks"][0]

        self.assertIsNone(task["stream_id"])
        self.assertIsNone(task["topic"])
        self.assertEqual(task["message_id"], message_id)
        self.assertEqual(task["title"], "Follow up")
        self.assertFalse(task["completed"])
        self.assertEqual(task["creator_email"], othello.email)
        self.assertIsNotNone(task["created_at"])

    def test_list_my_tasks_visibility_by_assignee_across_members(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        iago = self.example_user("iago")

        stream_message_id = self.send_stream_message(iago, "Verona", content="Track these tasks")
        dm_message_id = self.send_personal_message(iago, hamlet, "Need follow-up")

        hamlet_stream_task = Task.objects.create(
            message_id=stream_message_id,
            assignee=hamlet,
            creator=iago,
            title="Hamlet stream task",
        )
        hamlet_dm_task = Task.objects.create(
            message_id=dm_message_id,
            assignee=hamlet,
            creator=iago,
            title="Hamlet DM task",
        )
        Task.objects.create(
            message_id=stream_message_id,
            assignee=othello,
            creator=iago,
            title="Othello task",
        )

        hamlet_result = self.api_get(hamlet, "/api/v1/users/me/tasks")
        hamlet_data = self.assert_json_success(hamlet_result)
        self.assertCountEqual(
            [task["task_id"] for task in hamlet_data["tasks"]],
            [hamlet_stream_task.id, hamlet_dm_task.id],
        )

        othello_result = self.api_get(othello, "/api/v1/users/me/tasks")
        othello_data = self.assert_json_success(othello_result)
        self.assert_length(othello_data["tasks"], 1)
        self.assertEqual(othello_data["tasks"][0]["title"], "Othello task")

    def test_list_my_tasks_includes_creator_when_assigned_by_other_member(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")

        message_id = self.send_stream_message(iago, "Verona", topic_name="triage", content="Please triage")
        Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=cordelia,
            title="Triaged by Cordelia",
            completed=False,
        )

        result = self.api_get(hamlet, "/api/v1/users/me/tasks")
        data = self.assert_json_success(result)
        self.assert_length(data["tasks"], 1)

        task = data["tasks"][0]
        self._assert_my_tasks_payload_shape(task)
        self.assertEqual(task["creator_email"], cordelia.email)
        self.assertEqual(task["topic"], "triage")
        self.assertIsNotNone(task["stream_id"])

    def test_list_my_tasks_same_message_multiple_assignees(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(iago, "Verona", topic_name="release", content="Ship this")
        hamlet_task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Hamlet release task",
        )
        Task.objects.create(
            message_id=message_id,
            assignee=othello,
            creator=iago,
            title="Othello release task",
        )

        result = self.api_get(hamlet, "/api/v1/users/me/tasks")
        data = self.assert_json_success(result)
        self.assert_length(data["tasks"], 1)
        task = data["tasks"][0]

        self.assertEqual(task["task_id"], hamlet_task.id)
        self.assertEqual(task["title"], "Hamlet release task")
        self.assertEqual(task["message_id"], message_id)

    def test_list_my_tasks_excludes_tasks_created_by_user_for_others(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(iago, "Verona", topic_name="assign", content="Assign this")
        Task.objects.create(
            message_id=message_id,
            assignee=othello,
            creator=hamlet,
            title="Created by hamlet, assigned to othello",
        )

        result = self.api_get(hamlet, "/api/v1/users/me/tasks")
        data = self.assert_json_success(result)
        self.assertEqual(data["tasks"], [])

    def test_list_my_tasks_group_dm_has_no_stream_metadata(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        iago = self.example_user("iago")

        message_id = self.send_group_direct_message(iago, [hamlet, othello], "Group follow-up")
        Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Group DM task",
        )

        result = self.api_get(hamlet, "/api/v1/users/me/tasks")
        data = self.assert_json_success(result)
        self.assert_length(data["tasks"], 1)
        task = data["tasks"][0]

        self._assert_my_tasks_payload_shape(task)
        self.assertIsNone(task["stream_id"])
        self.assertIsNone(task["topic"])
        self.assertEqual(task["title"], "Group DM task")

    def test_list_my_tasks_mixed_completion_and_due_date_serialization(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(iago, "Verona", topic_name="status", content="Track statuses")
        due_date = now()
        completed_task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Completed task",
            completed=True,
            due_date=due_date,
        )
        incomplete_task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Incomplete task",
            completed=False,
            due_date=None,
        )

        result = self.api_get(hamlet, "/api/v1/users/me/tasks")
        data = self.assert_json_success(result)
        self.assert_length(data["tasks"], 2)

        task_by_id = {task["task_id"]: task for task in data["tasks"]}
        self.assertEqual(task_by_id[completed_task.id]["completed"], True)
        self.assertEqual(task_by_id[completed_task.id]["due_date"], due_date.isoformat())
        self.assertEqual(task_by_id[incomplete_task.id]["completed"], False)
        self.assertIsNone(task_by_id[incomplete_task.id]["due_date"])
        self._assert_my_tasks_payload_shape(task_by_id[completed_task.id])
        self._assert_my_tasks_payload_shape(task_by_id[incomplete_task.id])
