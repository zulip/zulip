from zerver.lib.test_classes import ZulipTestCase


class TasksIntegrationTest(ZulipTestCase):
    def test_create_message_task_via_api_then_listed(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(
            hamlet, "Verona", topic_name="int", content="integration body"
        )
        create = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "Api created", "description": "d1"},
        )
        created = self.assert_json_success(create, ignored_parameters=["title", "description"])
        self.assertEqual(created["title"], "Api created")
        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assert_length(listed["tasks"], 1)
        row = listed["tasks"][0]
        self.assertEqual(row["task_id"], created["task_id"])
        self.assertEqual(row["message_id"], message_id)
        self.assertEqual(row["title"], "Api created")

    def test_standalone_task_create_then_listed(self) -> None:
        hamlet = self.example_user("hamlet")
        create = self.api_post(hamlet, "/api/v1/tasks", {"title": "Standalone", "description": "s"})
        created = self.assert_json_success(create)
        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assert_length(listed["tasks"], 1)
        self.assertEqual(listed["tasks"][0]["task_id"], created["task_id"])
        self.assertIsNone(listed["tasks"][0]["message_id"])

    def test_create_on_message_for_other_assignee_then_they_see_it(self) -> None:
        iago = self.example_user("iago")
        othello = self.example_user("othello")
        message_id = self.send_stream_message(iago, "Verona", content="handoff")
        self.assert_json_success(
            self.api_post(
                iago,
                f"/api/v1/messages/{message_id}/tasks",
                {"title": "For Othello", "description": "", "assignee": othello.email},
            ),
            ignored_parameters=["title", "description", "assignee"],
        )
        othello_list = self.assert_json_success(self.api_get(othello, "/api/v1/users/me/tasks"))
        self.assert_length(othello_list["tasks"], 1)
        self.assertEqual(othello_list["tasks"][0]["title"], "For Othello")

    def test_create_then_delete_then_list_empty(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="delete flow")
        created = self.assert_json_success(
            self.api_post(
                hamlet,
                f"/api/v1/messages/{message_id}/tasks",
                {"title": "Tmp", "description": ""},
            ),
            ignored_parameters=["title", "description"],
        )
        task_id = created["task_id"]
        self.assert_json_success(self.api_post(hamlet, f"/api/v1/tasks/{task_id}/delete", {}))
        listed = self.assert_json_success(self.api_get(hamlet, "/api/v1/users/me/tasks"))
        self.assertEqual(listed["tasks"], [])
