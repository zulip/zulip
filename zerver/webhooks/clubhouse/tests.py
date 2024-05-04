import json
from unittest.mock import MagicMock, call, patch

from zerver.lib.test_classes import WebhookTestCase


class ClubhouseWebhookTest(WebhookTestCase):
    CHANNEL_NAME = "clubhouse"
    URL_TEMPLATE = "/api/v1/external/clubhouse?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "clubhouse"

    def test_story_create(self) -> None:
        expected_message = "New story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) of type **feature** was created."
        self.check_webhook(
            "story_create",
            "Add cool feature!",
            expected_message,
        )

    def test_story_delete(self) -> None:
        expected_message = "The story **New random story** was deleted."
        self.check_webhook("story_delete", "New random story", expected_message)

    def test_epic_story_create(self) -> None:
        expected_message = "New story [An epic story!](https://app.clubhouse.io/zulip/story/23) was created and added to the epic **New Cool Epic!**."
        self.check_webhook(
            "epic_create_story",
            "An epic story!",
            expected_message,
        )

    def test_epic_delete(self) -> None:
        expected_message = "The epic **Clubhouse Fork** was deleted."
        self.check_webhook("epic_delete", "Clubhouse Fork", expected_message)

    def test_story_archive(self) -> None:
        expected_message = (
            "The story [Story 2](https://app.clubhouse.io/zulip/story/9) was archived."
        )
        self.check_webhook("story_archive", "Story 2", expected_message)

    def test_epic_archive(self) -> None:
        expected_message = "The epic **Zulip is epic!** was archived."
        self.check_webhook("epic_archive", "Zulip is epic!", expected_message)

    def test_story_unarchive(self) -> None:
        expected_message = (
            "The story [Story 2](https://app.clubhouse.io/zulip/story/9) was unarchived."
        )
        self.check_webhook("story_unarchive", "Story 2", expected_message)

    def test_epic_create(self) -> None:
        expected_message = "New epic **New Epic!**(to do) was created."
        self.check_webhook("epic_create", "New Epic!", expected_message)

    def test_epic_update_add_comment(self) -> None:
        expected_message = "New comment added to the epic **New Cool Epic!**:\n``` quote\nAdded a comment on this Epic!\n```"
        self.check_webhook("epic_update_add_comment", "New Cool Epic!", expected_message)

    def test_story_update_add_comment(self) -> None:
        expected_message = "New comment added to the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11):\n``` quote\nJust leaving a comment here!\n```"
        self.check_webhook("story_update_add_comment", "Add cool feature!", expected_message)

    def test_epic_update_add_description(self) -> None:
        expected_message = "New description added to the epic **New Cool Epic!**:\n``` quote\nAdded a description!\n```"
        self.check_webhook("epic_update_add_description", "New Cool Epic!", expected_message)

    def test_epic_update_remove_description(self) -> None:
        expected_message = "Description for the epic **New Cool Epic!** was removed."
        self.check_webhook("epic_update_remove_description", "New Cool Epic!", expected_message)

    def test_epic_update_change_description(self) -> None:
        expected_message = "Description for the epic **New Cool Epic!** was changed from:\n``` quote\nAdded a description!\n```\nto\n``` quote\nChanged a description!\n```"
        self.check_webhook("epic_update_change_description", "New Cool Epic!", expected_message)

    def test_story_update_add_description(self) -> None:
        expected_message = "New description added to the story [Story 2](https://app.clubhouse.io/zulip/story/9):\n``` quote\nAdded a description.\n```"
        self.check_webhook("story_update_add_description", "Story 2", expected_message)

    def test_story_update_remove_description(self) -> None:
        expected_message = "Description for the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was removed."
        self.check_webhook("story_update_remove_description", "Add cool feature!", expected_message)

    def test_story_update_change_description(self) -> None:
        expected_message = "Description for the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was changed from:\n``` quote\nWe should probably add this cool feature!\n```\nto\n``` quote\nWe should probably add this cool feature! Just edited this. :)\n```"
        self.check_webhook("story_update_description", "Add cool feature!", expected_message)

    def test_epic_update_change_state(self) -> None:
        expected_message = (
            "State of the epic **New Cool Epic!** was changed from **to do** to **in progress**."
        )
        self.check_webhook("epic_update_change_state", "New Cool Epic!", expected_message)

    def test_story_update_change_state(self) -> None:
        expected_message = "State of the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was changed from **Unscheduled** to **Ready for Review**."
        self.check_webhook("story_update_change_state", "Add cool feature!", expected_message)

    def test_epic_update_change_name(self) -> None:
        expected_message = "The name of the epic **New Cool Epic!** was changed from:\n``` quote\nNew Epic!\n```\nto\n``` quote\nNew Cool Epic!\n```"
        self.check_webhook("epic_update_change_title", "New Cool Epic!", expected_message)

    def test_story_update_change_name(self) -> None:
        expected_message = "The name of the story [Add super cool feature!](https://app.clubhouse.io/zulip/story/11) was changed from:\n``` quote\nAdd cool feature!\n```\nto\n``` quote\nAdd super cool feature!\n```"
        self.check_webhook("story_update_change_title", "Add super cool feature!", expected_message)

    def test_story_update_add_owner(self) -> None:
        expected_message = "New owner added to the story [A new story by Shakespeare!](https://app.clubhouse.io/zulip/story/26)."
        self.check_webhook(
            "story_update_add_owner", "A new story by Shakespeare!", expected_message
        )

    def test_story_task_created(self) -> None:
        expected_message = "Task **Added a new task** was added to the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11)."
        self.check_webhook("story_task_create", "Add cool feature!", expected_message)

    def test_story_task_deleted(self) -> None:
        expected_message = "Task **Added a new task** was removed from the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11)."
        self.check_webhook("story_task_delete", "Add cool feature!", expected_message)

    def test_story_task_completed(self) -> None:
        expected_message = "Task **A new task for this story** ([Add cool feature!](https://app.clubhouse.io/zulip/story/11)) was completed. :tada:"
        self.check_webhook("story_task_complete", "Add cool feature!", expected_message)

    @patch("zerver.webhooks.clubhouse.view.check_send_webhook_message")
    def test_story_task_incomplete_ignore(self, check_send_webhook_message_mock: MagicMock) -> None:
        payload = self.get_body("story_task_not_complete")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_story_epic_changed(self) -> None:
        expected_message = (
            "The story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was moved from **Release 1.9**"
            " to **Clubhouse Fork**."
        )
        self.check_webhook("story_update_change_epic", "Add cool feature!", expected_message)

    def test_story_epic_added(self) -> None:
        expected_message = "The story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was added to the epic **Release 1.9**."
        self.check_webhook("story_update_add_epic", "Add cool feature!", expected_message)

    def test_story_epic_removed(self) -> None:
        expected_message = "The story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was removed from the epic **Release 1.9**."
        self.check_webhook("story_update_remove_epic", "Add cool feature!", expected_message)

    def test_story_estimate_changed(self) -> None:
        expected_message = "The estimate for the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was set to 4 points."
        self.check_webhook("story_update_change_estimate", "Add cool feature!", expected_message)

    def test_story_estimate_added(self) -> None:
        expected_message = "The estimate for the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was set to 4 points."
        self.check_webhook("story_update_add_estimate", "Add cool feature!", expected_message)

    def test_story_estimate_removed(self) -> None:
        expected_message = "The estimate for the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was set to *Unestimated*."
        self.check_webhook("story_update_remove_estimate", "Add cool feature!", expected_message)

    def test_story_file_attachment_added(self) -> None:
        expected_message = "A file attachment `zuliprc` was added to the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11)."
        self.check_webhook("story_update_add_attachment", "Add cool feature!", expected_message)

    @patch("zerver.webhooks.clubhouse.view.check_send_webhook_message")
    def test_story_file_attachment_removed_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        payload = self.get_body("story_update_remove_attachment")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_story_label_added(self) -> None:
        expected_message = "The label **mockup** was added to the story [An epic story!](https://app.clubhouse.io/zulip/story/23)."
        self.check_webhook("story_update_add_label", "An epic story!", expected_message)

    def test_story_label_multiple_added(self) -> None:
        expected_message = "The labels **mockup**, **label** were added to the story [An epic story!](https://app.clubhouse.io/zulip/story/23)."
        self.check_webhook("story_update_add_multiple_labels", "An epic story!", expected_message)

    def test_story_label_added_label_name_in_actions(self) -> None:
        expected_message = "The label **sad** was added to the story [An emotional story!](https://app.clubhouse.io/zulip/story/28)."
        self.check_webhook(
            "story_update_add_label_name_in_action", "An emotional story!", expected_message
        )

    @patch("zerver.webhooks.clubhouse.view.check_send_webhook_message")
    def test_story_label_removed_ignore(self, check_send_webhook_message_mock: MagicMock) -> None:
        payload = self.get_body("story_update_remove_label")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_story_update_project(self) -> None:
        expected_message = "The story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was moved from the **Backend** project to **Devops**."
        self.check_webhook("story_update_change_project", "Add cool feature!", expected_message)

    def test_story_update_type(self) -> None:
        expected_message = "The type of the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was changed from **feature** to **bug**."
        self.check_webhook("story_update_change_type", "Add cool feature!", expected_message)

    def test_story_update_add_github_pull_request(self) -> None:
        expected_message = "New GitHub PR [#10](https://github.com/eeshangarg/Scheduler/pull/10) opened for story [Testing pull requests with Story](https://app.clubhouse.io/zulip/story/28) (Unscheduled -> Ready for Review)."
        self.check_webhook(
            "story_update_add_github_pull_request",
            "Testing pull requests with Story",
            expected_message,
        )

    def test_story_update_add_github_pull_request_without_workflow_state(self) -> None:
        expected_message = "New GitHub PR [#10](https://github.com/eeshangarg/Scheduler/pull/10) opened for story [Testing pull requests with Story](https://app.clubhouse.io/zulip/story/28)."
        self.check_webhook(
            "story_update_add_github_pull_request_without_workflow_state",
            "Testing pull requests with Story",
            expected_message,
        )

    @patch("zerver.webhooks.clubhouse.view.check_send_webhook_message")
    def test_story_update_add_github_multiple_pull_requests(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        payload = self.get_body("story_update_add_github_multiple_pull_requests")
        self.client_post(self.url, payload, content_type="application/json")
        expected_message = "New GitHub PR [#2](https://github.com/PIG208/test-clubhouse/pull/2) opened for story [{name}]({url}) (Unscheduled -> In Development)."
        request, user_profile = (
            check_send_webhook_message_mock.call_args_list[0][0][0],
            check_send_webhook_message_mock.call_args_list[0][0][1],
        )
        expected_list = [
            call(
                request,
                user_profile,
                "Story1",
                expected_message.format(
                    name="Story1", url="https://app.clubhouse.io/pig208/story/17"
                ),
                "pull-request_create",
            ),
            call(
                request,
                user_profile,
                "Story2",
                expected_message.format(
                    name="Story2", url="https://app.clubhouse.io/pig208/story/18"
                ),
                "pull-request_create",
            ),
        ]
        self.assertEqual(check_send_webhook_message_mock.call_args_list, expected_list)

    def test_story_update_add_github_pull_request_with_comment(self) -> None:
        expected_message = "Existing GitHub PR [#2](https://github.com/PIG208/test-clubhouse/pull/2) associated with story [asd2](https://app.clubhouse.io/pig208/story/15)."
        self.check_webhook(
            "story_update_add_github_pull_request_with_comment",
            "asd2",
            expected_message,
        )

    @patch("zerver.webhooks.clubhouse.view.check_send_webhook_message")
    def test_story_update_add_github_multiple_pull_requests_with_comment(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        payload = self.get_body("story_update_add_github_multiple_pull_requests_with_comment")
        self.client_post(self.url, payload, content_type="application/json")
        expected_message = "Existing GitHub PR [#1](https://github.com/PIG208/test-clubhouse/pull/1) associated with story [{name}]({url}) (Unscheduled -> In Development)."
        request, user_profile = (
            check_send_webhook_message_mock.call_args_list[0][0][0],
            check_send_webhook_message_mock.call_args_list[0][0][1],
        )
        expected_list = [
            call(
                request,
                user_profile,
                "new1",
                expected_message.format(
                    name="new1", url="https://app.clubhouse.io/pig208/story/26"
                ),
                "pull-request_comment",
            ),
            call(
                request,
                user_profile,
                "new2",
                expected_message.format(
                    name="new2", url="https://app.clubhouse.io/pig208/story/27"
                ),
                "pull-request_comment",
            ),
        ]
        self.assertEqual(check_send_webhook_message_mock.call_args_list, expected_list)

    def test_story_update_add_github_branch(self) -> None:
        expected_message = "New GitHub branch [eeshangarg/ch27/testing-pull-requests-with-story](https://github.com/eeshangarg/scheduler/tree/eeshangarg/ch27/testing-pull-requests-with-story) associated with story [Testing pull requests with Story](https://app.clubhouse.io/zulip/story/27) (Unscheduled -> In Development)."
        self.check_webhook(
            "story_update_add_github_branch", "Testing pull requests with Story", expected_message
        )

    @patch("zerver.webhooks.clubhouse.view.check_send_webhook_message")
    def test_story_update_batch(self, check_send_webhook_message_mock: MagicMock) -> None:
        payload = self.get_body("story_update_everything_at_once")
        self.client_post(self.url, payload, content_type="application/json")
        expected_message = "The story [{name}]({url}) was moved from Epic **epic** to **testeipc**, Project **Product Development** to **test2**, and changed from type **feature** to **bug**, and added with the new label **low priority** (In Development -> Ready for Review)."
        request, user_profile = (
            check_send_webhook_message_mock.call_args_list[0][0][0],
            check_send_webhook_message_mock.call_args_list[0][0][1],
        )
        expected_list = [
            call(
                request,
                user_profile,
                "asd4",
                expected_message.format(
                    name="asd4", url="https://app.clubhouse.io/pig208/story/17"
                ),
                "story_update_batch",
            ),
            call(
                request,
                user_profile,
                "new1",
                expected_message.format(
                    name="new1", url="https://app.clubhouse.io/pig208/story/26"
                ),
                "story_update_batch",
            ),
            call(
                request,
                user_profile,
                "new2",
                expected_message.format(
                    name="new2", url="https://app.clubhouse.io/pig208/story/27"
                ),
                "story_update_batch",
            ),
        ]
        self.assertEqual(check_send_webhook_message_mock.call_args_list, expected_list)

    @patch("zerver.webhooks.clubhouse.view.check_send_webhook_message")
    def test_story_update_batch_skip_removed_labels(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        payload = self.get_body("story_update_everything_at_once_skip_removed_labels")
        self.client_post(self.url, payload, content_type="application/json")
        expected_message = "The story [{name}]({url}) was moved from Epic **epic** to **testeipc**, Project **Product Development** to **test2**, and changed from type **feature** to **bug** (In Development -> Ready for Review)."
        request, user_profile = (
            check_send_webhook_message_mock.call_args_list[0][0][0],
            check_send_webhook_message_mock.call_args_list[0][0][1],
        )
        expected_list = [
            call(
                request,
                user_profile,
                "asd4",
                expected_message.format(
                    name="asd4", url="https://app.clubhouse.io/pig208/story/17"
                ),
                "story_update_batch",
            ),
            call(
                request,
                user_profile,
                "new1",
                expected_message.format(
                    name="new1", url="https://app.clubhouse.io/pig208/story/26"
                ),
                "story_update_batch",
            ),
            call(
                request,
                user_profile,
                "new2",
                expected_message.format(
                    name="new2", url="https://app.clubhouse.io/pig208/story/27"
                ),
                "story_update_batch",
            ),
        ]
        self.assertEqual(check_send_webhook_message_mock.call_args_list, expected_list)

    @patch("zerver.webhooks.clubhouse.view.check_send_webhook_message")
    def test_story_update_batch_each_with_one_change(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        payload = self.get_body("story_update_multiple_at_once")
        self.client_post(self.url, payload, content_type="application/json")
        expected_messages = [
            (
                "asd4",
                "The type of the story [asd4](https://app.clubhouse.io/pig208/story/17) was changed from **feature** to **bug**.",
            ),
            (
                "new1",
                "The story [new1](https://app.clubhouse.io/pig208/story/26) was moved from **epic** to **testeipc**.",
            ),
            (
                "new2",
                "The label **low priority** was added to the story [new2](https://app.clubhouse.io/pig208/story/27).",
            ),
            (
                "new3",
                "State of the story [new3](https://app.clubhouse.io/pig208/story/28) was changed from **In Development** to **Ready for Review**.",
            ),
            (
                "new4",
                "The story [new4](https://app.clubhouse.io/pig208/story/29) was moved from the **Product Development** project to **test2**.",
            ),
        ]
        request, user_profile = (
            check_send_webhook_message_mock.call_args_list[0][0][0],
            check_send_webhook_message_mock.call_args_list[0][0][1],
        )
        expected_list = [
            call(
                request,
                user_profile,
                expected_message[0],
                expected_message[1],
                "story_update_batch",
            )
            for expected_message in expected_messages
        ]
        self.assertEqual(check_send_webhook_message_mock.call_args_list, expected_list)

    @patch("zerver.webhooks.clubhouse.view.check_send_webhook_message")
    def test_story_update_batch_not_supported_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        payload = self.get_body("story_update_multiple_not_supported")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.clubhouse.view.check_send_webhook_message")
    def test_empty_post_request_body_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        payload = json.dumps(None)
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.clubhouse.view.check_send_webhook_message")
    def test_story_comment_updated_ignore(self, check_send_webhook_message_mock: MagicMock) -> None:
        payload = self.get_body("story_comment_updated")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)
