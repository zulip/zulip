# -*- coding: utf-8 -*-
from zerver.lib.test_helpers import WebhookTestCase

class GitlabHookTests(WebhookTestCase):
    STREAM_NAME = 'gitlab'
    URL_TEMPLATE = "/api/v1/external/gitlab?&api_key={api_key}"
    FIXTURE_DIR_NAME = 'gitlab'

    def test_push_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek pushed [2 commits](https://gitlab.com/tomaszkolek0/my-awesome-project/compare/5fcdd5551fc3085df79bece2c32b1400802ac407...eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9) to tomek branch."

        self.send_and_test_stream_message('push', expected_subject, expected_message, HTTP_X_GITLAB_EVENT="Push Hook")

    def test_add_tag_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek pushed xyz tag."

        self.send_and_test_stream_message(
            'add_tag',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Tag Push Hook",
        )

    def test_remove_tag_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek removed xyz tag."

        self.send_and_test_stream_message(
            'remove_tag',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Tag Push Hook"
        )

    def test_create_issue_without_assignee_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek created [Issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)."

        self.send_and_test_stream_message(
            'issue_created_without_assignee',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Issue Hook"
        )

    def test_create_issue_with_assignee_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek created [Issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1) (assigned to Tomasz Kolek)."

        self.send_and_test_stream_message(
            'issue_created_with_assignee',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Issue Hook"
        )

    def test_update_issue_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek updated [Issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)."

        self.send_and_test_stream_message(
            'issue_updated',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Issue Hook"
        )

    def test_close_issue_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek closed [Issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)."

        self.send_and_test_stream_message(
            'issue_closed',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Issue Hook"
        )

    def test_reopen_issue_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek reopened [Issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)."

        self.send_and_test_stream_message(
            'issue_reopened',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Issue Hook"
        )

    def test_note_commit_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek added [comment](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7#note_14169211) to [Commit](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7)."

        self.send_and_test_stream_message(
            'commit_note',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Note Hook"
        )

    def test_note_merge_request_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek added [comment](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/1#note_14171860) to [Merge Request #1](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/1)."

        self.send_and_test_stream_message(
            'merge_request_note',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Note Hook"
        )

    def test_note_issue_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek added [comment](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/2#note_14172057) to [Issue #2](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/2)."

        self.send_and_test_stream_message(
            'issue_note',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Note Hook"
        )

    def test_note_snippet_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek added [comment](https://gitlab.com/tomaszkolek0/my-awesome-project/snippets/2#note_14172058) to [Snippet #2](https://gitlab.com/tomaszkolek0/my-awesome-project/snippets/2)."

        self.send_and_test_stream_message(
            'snippet_note',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Note Hook"
        )

    def test_merge_request_created_without_assignee_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek created [Merge Request #2](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2)."

        self.send_and_test_stream_message(
            'merge_request_created_without_assignee',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_merge_request_created_with_assignee_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek created [Merge Request #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3) (assigned to Tomasz Kolek)."

        self.send_and_test_stream_message(
            'merge_request_created_with_assignee',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_merge_request_closed_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek closed [Merge Request #2](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2)."

        self.send_and_test_stream_message(
            'merge_request_closed',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_merge_request_updated_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek updated [Merge Request #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3)."

        self.send_and_test_stream_message(
            'merge_request_updated',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_merge_request_added_commit_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek added commit to [Merge Request #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3)."

        self.send_and_test_stream_message(
            'merge_request_added_commit',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_merge_request_merged_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek merged [Merge Request #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3)."

        self.send_and_test_stream_message(
            'merge_request_merged',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_wiki_page_opened_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek created [Wiki Page \"how to\"](https://gitlab.com/tomaszkolek0/my-awesome-project/wikis/how-to)."

        self.send_and_test_stream_message(
            'wiki_page_opened',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Wiki Page Hook"
        )

    def test_wiki_page_edited_event_message(self):
        # type: () -> None
        expected_subject = u"Repository: my-awesome-project"
        expected_message = u"Tomasz Kolek updated [Wiki Page \"how to\"](https://gitlab.com/tomaszkolek0/my-awesome-project/wikis/how-to)."

        self.send_and_test_stream_message(
            'wiki_page_edited',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Wiki Page Hook"
        )
