import json
from mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase

class ClubhouseWebhookTest(WebhookTestCase):
    STREAM_NAME = 'clubhouse'
    URL_TEMPLATE = "/api/v1/external/clubhouse?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'clubhouse'

    def test_story_create(self) -> None:
        expected_message = u"New story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) of type **feature** was created."
        self.send_and_test_stream_message(
            'story_create', "Add cool feature!",
            expected_message
        )

    def test_story_delete(self) -> None:
        expected_message = u"The story **New random story** was deleted."
        self.send_and_test_stream_message("story_delete", "New random story",
                                          expected_message)

    def test_epic_story_create(self) -> None:
        expected_message = u"New story [An epic story!](https://app.clubhouse.io/zulip/story/23) was created and added to the epic **New Cool Epic!**."
        self.send_and_test_stream_message(
            'epic_create_story', "An epic story!",
            expected_message
        )

    def test_epic_delete(self) -> None:
        expected_message = u"The epic **Clubhouse Fork** was deleted."
        self.send_and_test_stream_message("epic_delete", "Clubhouse Fork",
                                          expected_message)

    def test_story_archive(self) -> None:
        expected_message = u"The story [Story 2](https://app.clubhouse.io/zulip/story/9) was archived."
        self.send_and_test_stream_message('story_archive', "Story 2", expected_message)

    def test_epic_archive(self) -> None:
        expected_message = u"The epic **Zulip is epic!** was archived."
        self.send_and_test_stream_message('epic_archive', 'Zulip is epic!',
                                          expected_message)

    def test_story_unarchive(self) -> None:
        expected_message = u"The story [Story 2](https://app.clubhouse.io/zulip/story/9) was unarchived."
        self.send_and_test_stream_message('story_unarchive', "Story 2", expected_message)

    def test_epic_create(self) -> None:
        expected_message = u"New epic **New Epic!**(to do) was created."
        self.send_and_test_stream_message('epic_create', "New Epic!", expected_message)

    def test_epic_update_add_comment(self) -> None:
        expected_message = u"New comment added to the epic **New Cool Epic!**:\n``` quote\nAdded a comment on this Epic!\n```"
        self.send_and_test_stream_message('epic_update_add_comment',
                                          "New Cool Epic!", expected_message)

    def test_story_update_add_comment(self) -> None:
        expected_message = u"New comment added to the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11):\n``` quote\nJust leaving a comment here!\n```"
        self.send_and_test_stream_message('story_update_add_comment',
                                          "Add cool feature!",
                                          expected_message)

    def test_epic_update_add_description(self) -> None:
        expected_message = u"New description added to the epic **New Cool Epic!**:\n``` quote\nAdded a description!\n```"
        self.send_and_test_stream_message('epic_update_add_description',
                                          "New Cool Epic!", expected_message)

    def test_epic_update_remove_description(self) -> None:
        expected_message = u"Description for the epic **New Cool Epic!** was removed."
        self.send_and_test_stream_message('epic_update_remove_description',
                                          "New Cool Epic!", expected_message)

    def test_epic_update_change_description(self) -> None:
        expected_message = u"Description for the epic **New Cool Epic!** was changed from:\n``` quote\nAdded a description!\n```\nto\n``` quote\nChanged a description!\n```"
        self.send_and_test_stream_message('epic_update_change_description',
                                          "New Cool Epic!", expected_message)

    def test_story_update_add_description(self) -> None:
        expected_message = u"New description added to the story [Story 2](https://app.clubhouse.io/zulip/story/9):\n``` quote\nAdded a description.\n```"
        self.send_and_test_stream_message('story_update_add_description',
                                          "Story 2", expected_message)

    def test_story_update_remove_description(self) -> None:
        expected_message = u"Description for the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was removed."
        self.send_and_test_stream_message('story_update_remove_description',
                                          "Add cool feature!", expected_message)

    def test_story_update_change_description(self) -> None:
        expected_message = u"Description for the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was changed from:\n``` quote\nWe should probably add this cool feature!\n```\nto\n``` quote\nWe should probably add this cool feature! Just edited this. :)\n```"
        self.send_and_test_stream_message('story_update_description',
                                          "Add cool feature!", expected_message)

    def test_epic_update_change_state(self) -> None:
        expected_message = u"State of the epic **New Cool Epic!** was changed from **to do** to **in progress**."
        self.send_and_test_stream_message('epic_update_change_state',
                                          "New Cool Epic!", expected_message)

    def test_story_update_change_state(self) -> None:
        expected_message = u"State of the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was changed from **Unscheduled** to **Ready for Review**."
        self.send_and_test_stream_message('story_update_change_state',
                                          "Add cool feature!", expected_message)

    def test_epic_update_change_name(self) -> None:
        expected_message = u"The name of the epic **New Cool Epic!** was changed from:\n``` quote\nNew Epic!\n```\nto\n``` quote\nNew Cool Epic!\n```"
        self.send_and_test_stream_message('epic_update_change_title', "New Cool Epic!",
                                          expected_message)

    def test_story_update_change_name(self) -> None:
        expected_message = u"The name of the story [Add super cool feature!](https://app.clubhouse.io/zulip/story/11) was changed from:\n``` quote\nAdd cool feature!\n```\nto\n``` quote\nAdd super cool feature!\n```"
        self.send_and_test_stream_message('story_update_change_title', "Add super cool feature!",
                                          expected_message)

    def test_story_update_add_owner(self) -> None:
        expected_message = u"New owner added to the story [A new story by Shakespeare!](https://app.clubhouse.io/zulip/story/26)."
        self.send_and_test_stream_message('story_update_add_owner', 'A new story by Shakespeare!',
                                          expected_message)

    def test_story_task_created(self) -> None:
        expected_message = u"Task **Added a new task** was added to the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11)."
        self.send_and_test_stream_message('story_task_create', "Add cool feature!",
                                          expected_message)

    def test_story_task_deleted(self) -> None:
        expected_message = u"Task **Added a new task** was removed from the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11)."
        self.send_and_test_stream_message('story_task_delete', "Add cool feature!",
                                          expected_message)

    def test_story_task_completed(self) -> None:
        expected_message = u"Task **A new task for this story** ([Add cool feature!](https://app.clubhouse.io/zulip/story/11)) was completed. :tada:"
        self.send_and_test_stream_message('story_task_complete', "Add cool feature!",
                                          expected_message)

    @patch('zerver.lib.webhooks.common.check_send_webhook_message')
    def test_story_task_incomplete_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        payload = self.get_body('story_task_not_complete')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_story_epic_changed(self) -> None:
        expected_message = (u"The story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was moved from **Release 1.9**"
                            u" to **Clubhouse Fork**.")
        self.send_and_test_stream_message('story_update_change_epic', "Add cool feature!",
                                          expected_message)

    def test_story_epic_added(self) -> None:
        expected_message = u"The story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was added to the epic **Release 1.9**."
        self.send_and_test_stream_message('story_update_add_epic', "Add cool feature!",
                                          expected_message)

    def test_story_epic_removed(self) -> None:
        expected_message = u"The story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was removed from the epic **Release 1.9**."
        self.send_and_test_stream_message('story_update_remove_epic', "Add cool feature!",
                                          expected_message)

    def test_story_estimate_changed(self) -> None:
        expected_message = u"The estimate for the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was set to 4 points."
        self.send_and_test_stream_message('story_update_change_estimate', "Add cool feature!",
                                          expected_message)

    def test_story_estimate_added(self) -> None:
        expected_message = u"The estimate for the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was set to 4 points."
        self.send_and_test_stream_message('story_update_add_estimate', "Add cool feature!",
                                          expected_message)

    def test_story_estimate_removed(self) -> None:
        expected_message = u"The estimate for the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was set to *Unestimated*."
        self.send_and_test_stream_message('story_update_remove_estimate', "Add cool feature!",
                                          expected_message)

    def test_story_file_attachment_added(self) -> None:
        expected_message = u"A file attachment `zuliprc` was added to the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11)."
        self.send_and_test_stream_message('story_update_add_attachment', "Add cool feature!",
                                          expected_message)

    @patch('zerver.lib.webhooks.common.check_send_webhook_message')
    def test_story_file_attachment_removed_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        payload = self.get_body('story_update_remove_attachment')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_story_label_added(self) -> None:
        expected_message = u"The label **mockup** was added to the story [An epic story!](https://app.clubhouse.io/zulip/story/23)."
        self.send_and_test_stream_message('story_update_add_label', "An epic story!",
                                          expected_message)

    def test_story_label_added_label_name_in_actions(self) -> None:
        expected_message = u"The label **sad** was added to the story [An emotional story!](https://app.clubhouse.io/zulip/story/28)."
        self.send_and_test_stream_message('story_update_add_label_name_in_action',
                                          'An emotional story!',
                                          expected_message)

    @patch('zerver.lib.webhooks.common.check_send_webhook_message')
    def test_story_label_removed_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        payload = self.get_body('story_update_remove_label')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_story_update_project(self) -> None:
        expected_message = u"The story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was moved from the **Backend** project to **Devops**."
        self.send_and_test_stream_message('story_update_change_project', "Add cool feature!",
                                          expected_message)

    def test_story_update_type(self) -> None:
        expected_message = u"The type of the story [Add cool feature!](https://app.clubhouse.io/zulip/story/11) was changed from **feature** to **bug**."
        self.send_and_test_stream_message('story_update_change_type', "Add cool feature!",
                                          expected_message)

    def test_story_update_add_github_pull_request(self) -> None:
        expected_message = u"New GitHub PR [#10](https://github.com/eeshangarg/Scheduler/pull/10) opened for story [Testing pull requests with Story](https://app.clubhouse.io/zulip/story/28) (Unscheduled -> Ready for Review)."
        self.send_and_test_stream_message('story_update_add_github_pull_request',
                                          'Testing pull requests with Story',
                                          expected_message)

    def test_story_update_add_github_branch(self) -> None:
        expected_message = "New GitHub branch [eeshangarg/ch27/testing-pull-requests-with-story](https://github.com/eeshangarg/scheduler/tree/eeshangarg/ch27/testing-pull-requests-with-story) associated with story [Testing pull requests with Story](https://app.clubhouse.io/zulip/story/27) (Unscheduled -> In Development)."
        self.send_and_test_stream_message('story_update_add_github_branch',
                                          'Testing pull requests with Story',
                                          expected_message)

    @patch('zerver.lib.webhooks.common.check_send_webhook_message')
    def test_empty_post_request_body_ignore(self, check_send_webhook_message_mock: MagicMock) -> None:
        payload = json.dumps(None)
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.lib.webhooks.common.check_send_webhook_message')
    def test_story_comment_updated_ignore(self, check_send_webhook_message_mock: MagicMock) -> None:
        payload = self.get_body('story_comment_updated')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)
