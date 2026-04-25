from django.utils.timezone import now
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.messages import Task, TaskTimeLog


class TasksViewTest(ZulipTestCase):
    def _assert_my_tasks_payload_shape(self, task: dict[str, object]) -> None:
        self.assertEqual(
            set(task.keys()),
            {
                "task_id",
                "title",
                "description",
                "completed",
                "completed_at",
                "due_date",
                "message_id",
                "stream_id",
                "topic",
                "creator_email",
                "creator_full_name",
                "created_at",
                "total_time_seconds",
                "total_time_formatted",
                "active_timer",
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

    def test_list_my_tasks_includes_time_tracking_fields(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(iago, "Verona", topic_name="time", content="Track time")
        task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Time tracking task",
            description="Test time tracking",
        )

        # Create some time logs
        TaskTimeLog.objects.create(
            task=task,
            user=hamlet,
            start_time=now(),
            end_time=now(),
            duration_seconds=3600,  # 1 hour
        )
        TaskTimeLog.objects.create(
            task=task,
            user=hamlet,
            start_time=now(),
            end_time=None,  # Active timer
            duration_seconds=0,
        )

        result = self.api_get(hamlet, "/api/v1/users/me/tasks")
        data = self.assert_json_success(result)

        self.assert_length(data["tasks"], 1)
        task_data = data["tasks"][0]

        self.assertEqual(task_data["task_id"], task.id)
        self.assertEqual(task_data["total_time_seconds"], 3600)
        self.assertEqual(task_data["total_time_formatted"], "1h 0m")
        self.assertTrue(task_data["active_timer"])

    def test_start_time_tracking(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(iago, "Verona", content="Start timer")
        task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Timer test task",
        )

        result = self.api_post(hamlet, f"/api/v1/tasks/{task.id}/time/start", {})
        data = self.assert_json_success(result)

        self.assertEqual(data["task_id"], task.id)
        self.assertTrue(data["is_active"])
        self.assertIsNotNone(data["start_time"])

        # Verify the time log was created
        time_log = TaskTimeLog.objects.get(task=task, user=hamlet)
        self.assertIsNotNone(time_log.start_time)
        self.assertIsNone(time_log.end_time)

    def test_stop_time_tracking(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(iago, "Verona", content="Stop timer")
        task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Timer stop test",
        )

        # Start timer first (use a past start_time to guarantee duration > 0)
        from datetime import timedelta
        start_time = now() - timedelta(seconds=5)
        TaskTimeLog.objects.create(
            task=task,
            user=hamlet,
            start_time=start_time,
            end_time=None,
        )

        result = self.api_post(hamlet, f"/api/v1/tasks/{task.id}/time/stop", {})
        data = self.assert_json_success(result)

        self.assertEqual(data["task_id"], task.id)
        self.assertIsNotNone(data["end_time"])
        self.assertGreater(data["duration_seconds"], 0)
        self.assertIn("duration_formatted", data)

        # Verify the time log was updated
        time_log = TaskTimeLog.objects.get(task=task, user=hamlet)
        self.assertIsNotNone(time_log.end_time)
        self.assertGreater(time_log.duration_seconds, 0)

    def test_get_task_time_logs(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(iago, "Verona", content="Time logs")
        task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Time logs test",
        )

        # Create time logs
        TaskTimeLog.objects.create(
            task=task,
            user=hamlet,
            start_time=now(),
            end_time=now(),
            duration_seconds=1800,  # 30 minutes
            description="First session",
        )
        TaskTimeLog.objects.create(
            task=task,
            user=hamlet,
            start_time=now(),
            end_time=None,  # Active
            duration_seconds=0,
            description="Active session",
        )

        result = self.api_get(hamlet, f"/api/v1/tasks/{task.id}/time/logs")
        data = self.assert_json_success(result)

        self.assertEqual(data["task_id"], task.id)
        self.assertEqual(data["total_time_seconds"], 1800)
        self.assertEqual(data["total_time_formatted"], "30m 0s")
        self.assertEqual(data["active_timer_count"], 1)
        self.assert_length(data["time_logs"], 2)

    # ------------------------------------------------------------------ #
    # update_task (completion toggle) tests
    # ------------------------------------------------------------------ #

    def test_update_task_completion_by_assignee(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(iago, "Verona", content="Please do this")
        task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Complete me",
        )
        self.assertFalse(task.completed)

        result = self.api_post(hamlet, f"/api/v1/tasks/{task.id}", {"completed": "true"})
        data = self.assert_json_success(result)

        self.assertTrue(data["completed"])
        task.refresh_from_db()
        self.assertTrue(task.completed)
        self.assertIsNotNone(task.completed_at)

    def test_update_task_completion_unmarks_by_assignee(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(iago, "Verona", content="Already done")
        task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Unmark me",
            completed=True,
        )

        result = self.api_post(hamlet, f"/api/v1/tasks/{task.id}", {"completed": "false"})
        data = self.assert_json_success(result)

        self.assertFalse(data["completed"])
        task.refresh_from_db()
        self.assertFalse(task.completed)
        self.assertIsNone(task.completed_at)

    def test_update_task_completion_by_creator(self) -> None:
        """Task creator (who is not the assignee) can also toggle completion."""
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(hamlet, "Verona", content="Do this")
        task = Task.objects.create(
            message_id=message_id,
            assignee=iago,
            creator=hamlet,
            title="Creator toggles",
        )

        result = self.api_post(hamlet, f"/api/v1/tasks/{task.id}", {"completed": "true"})
        self.assert_json_success(result)
        task.refresh_from_db()
        self.assertTrue(task.completed)

    def test_update_task_completion_denied_for_third_party(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")

        message_id = self.send_stream_message(iago, "Verona", content="Private task")
        task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Deny third party",
        )

        result = self.api_post(cordelia, f"/api/v1/tasks/{task.id}", {"completed": "true"})
        self.assert_json_error(result, "Permission denied")
        task.refresh_from_db()
        self.assertFalse(task.completed)

    # ------------------------------------------------------------------ #
    # delete_task tests
    # ------------------------------------------------------------------ #

    def test_delete_task_by_assignee_succeeds(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(iago, "Verona", content="Delete me")
        task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="To be deleted",
        )
        task_id = task.id

        result = self.api_post(hamlet, f"/api/v1/tasks/{task_id}/delete", {})
        self.assert_json_success(result)
        self.assertFalse(Task.objects.filter(id=task_id).exists())

    def test_delete_task_by_creator_succeeds(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        message_id = self.send_stream_message(hamlet, "Verona", content="Creator deletes")
        task = Task.objects.create(
            message_id=message_id,
            assignee=iago,
            creator=hamlet,
            title="Creator-initiated delete",
        )
        task_id = task.id

        result = self.api_post(hamlet, f"/api/v1/tasks/{task_id}/delete", {})
        self.assert_json_success(result)
        self.assertFalse(Task.objects.filter(id=task_id).exists())

    def test_delete_task_denied_for_third_party(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")

        message_id = self.send_stream_message(iago, "Verona", content="Deny delete")
        task = Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Third party cannot delete",
        )

        result = self.api_post(cordelia, f"/api/v1/tasks/{task.id}/delete", {})
        self.assert_json_error(result, "Permission denied")
        self.assertTrue(Task.objects.filter(id=task.id).exists())

    def test_delete_task_not_found(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.api_post(hamlet, "/api/v1/tasks/999999/delete", {})
        self.assert_json_error(result, "Task not found")

    def test_get_my_time_stats(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")

        # Create tasks and time logs
        message_id1 = self.send_stream_message(iago, "Verona", content="Stats test 1")
        task1 = Task.objects.create(
            message_id=message_id1,
            assignee=hamlet,
            creator=iago,
            title="Stats task 1",
        )

        message_id2 = self.send_stream_message(iago, "Verona", content="Stats test 2")
        task2 = Task.objects.create(
            message_id=message_id2,
            assignee=hamlet,
            creator=iago,
            title="Stats task 2",
        )

        # Add time logs
        TaskTimeLog.objects.create(
            task=task1,
            user=hamlet,
            start_time=now(),
            end_time=now(),
            duration_seconds=3600,  # 1 hour
        )
        TaskTimeLog.objects.create(
            task=task2,
            user=hamlet,
            start_time=now(),
            end_time=now(),
            duration_seconds=1800,  # 30 minutes
        )
        TaskTimeLog.objects.create(
            task=task1,
            user=hamlet,
            start_time=now(),
            end_time=None,  # Active
            duration_seconds=0,
        )

        result = self.api_get(hamlet, "/api/v1/users/me/time/stats")
        data = self.assert_json_success(result)

        self.assertEqual(data["total_time_seconds"], 5400)  # 1.5 hours
        self.assertEqual(data["total_time_formatted"], "1h 30m")
        self.assertEqual(data["completed_sessions"], 2)
        self.assertEqual(data["active_sessions"], 1)
        self.assert_length(data["task_breakdown"], 2)

        # Check task breakdown
        task_breakdown = {task["task_id"]: task for task in data["task_breakdown"]}
        self.assertEqual(task_breakdown[task1.id]["total_formatted"], "1h 0m")
        self.assertEqual(task_breakdown[task2.id]["total_formatted"], "30m 0s")
