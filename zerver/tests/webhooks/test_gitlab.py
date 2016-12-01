# -*- coding: utf-8 -*-
from zerver.lib.webhooks.git import COMMITS_LIMIT
from zerver.lib.test_classes import WebhookTestCase

class GitlabHookTests(WebhookTestCase):
    STREAM_NAME = 'gitlab'
    URL_TEMPLATE = "/api/v1/external/gitlab?&api_key={api_key}"
    FIXTURE_DIR_NAME = 'gitlab'

    def test_push_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / tomek"
        expected_message = u"Tomasz Kolek [pushed](https://gitlab.com/tomaszkolek0/my-awesome-project/compare/5fcdd5551fc3085df79bece2c32b1400802ac407...eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9) to branch tomek\n\n* [66abd2d](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7): b\n* [eb6ae1e](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9): c"
        self.send_and_test_stream_message('push', expected_subject, expected_message, HTTP_X_GITLAB_EVENT="Push Hook")

    def test_push_commits_more_than_limit_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / tomek"
        commits_info = u'* [66abd2d](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7): b\n'
        expected_message = u"Tomasz Kolek [pushed](https://gitlab.com/tomaszkolek0/my-awesome-project/compare/5fcdd5551fc3085df79bece2c32b1400802ac407...eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9) to branch tomek\n\n{}[and {} more commit(s)]".format(
            commits_info * COMMITS_LIMIT,
            50 - COMMITS_LIMIT,
        )
        self.send_and_test_stream_message('push_commits_more_than_limit', expected_subject, expected_message, HTTP_X_GITLAB_EVENT="Push Hook")

    def test_remove_branch_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / tomek"
        expected_message = u"Tomasz Kolek deleted branch tomek"

        self.send_and_test_stream_message('remove_branch', expected_subject, expected_message, HTTP_X_GITLAB_EVENT="Push Hook")

    def test_add_tag_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project"
        expected_message = u"Tomasz Kolek pushed tag xyz"

        self.send_and_test_stream_message(
            'add_tag',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Tag Push Hook",
        )

    def test_remove_tag_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project"
        expected_message = u"Tomasz Kolek removed tag xyz"

        self.send_and_test_stream_message(
            'remove_tag',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Tag Push Hook"
        )

    def test_create_issue_without_assignee_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / Issue #1 Issue title"
        expected_message = u"Tomasz Kolek created [Issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)\n\n~~~ quote\nIssue description\n~~~"

        self.send_and_test_stream_message(
            'issue_created_without_assignee',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Issue Hook"
        )

    def test_create_issue_with_assignee_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / Issue #1 Issue title"
        expected_message = u"Tomasz Kolek created [Issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)(assigned to Tomasz Kolek)\n\n~~~ quote\nIssue description\n~~~"

        self.send_and_test_stream_message(
            'issue_created_with_assignee',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Issue Hook"
        )

    def test_update_issue_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / Issue #1 Issue title_new"
        expected_message = u"Tomasz Kolek updated [Issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)"

        self.send_and_test_stream_message(
            'issue_updated',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Issue Hook"
        )

    def test_close_issue_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / Issue #1 Issue title_new"
        expected_message = u"Tomasz Kolek closed [Issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)"

        self.send_and_test_stream_message(
            'issue_closed',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Issue Hook"
        )

    def test_reopen_issue_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / Issue #1 Issue title_new"
        expected_message = u"Tomasz Kolek reopened [Issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)"

        self.send_and_test_stream_message(
            'issue_reopened',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Issue Hook"
        )

    def test_note_commit_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project"
        expected_message = u"Tomasz Kolek [commented](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7#note_14169211) on [66abd2d](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7)\n~~~ quote\nnice commit\n~~~"

        self.send_and_test_stream_message(
            'commit_note',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Note Hook"
        )

    def test_note_merge_request_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / MR #1 Tomek"
        expected_message = u"Tomasz Kolek [commented](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/1#note_14171860) on [MR #1](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/1)\n\n~~~ quote\nNice merge request!\n~~~"

        self.send_and_test_stream_message(
            'merge_request_note',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Note Hook"
        )

    def test_note_issue_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / Issue #2 abc"
        expected_message = u"Tomasz Kolek [commented](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/2#note_14172057) on [Issue #2](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/2)\n\n~~~ quote\nNice issue\n~~~"

        self.send_and_test_stream_message(
            'issue_note',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Note Hook"
        )

    def test_note_snippet_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / Snippet #2 test"
        expected_message = u"Tomasz Kolek [commented](https://gitlab.com/tomaszkolek0/my-awesome-project/snippets/2#note_14172058) on [Snippet #2](https://gitlab.com/tomaszkolek0/my-awesome-project/snippets/2)\n\n~~~ quote\nNice snippet\n~~~"

        self.send_and_test_stream_message(
            'snippet_note',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Note Hook"
        )

    def test_merge_request_created_without_assignee_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / MR #2 NEW MR"
        expected_message = u"Tomasz Kolek created [MR #2](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2)\nfrom `tomek` to `master`\n\n~~~ quote\ndescription of merge request\n~~~"

        self.send_and_test_stream_message(
            'merge_request_created_without_assignee',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_merge_request_created_with_assignee_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / MR #3 New Merge Request"
        expected_message = u"Tomasz Kolek created [MR #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3)(assigned to Tomasz Kolek)\nfrom `tomek` to `master`\n\n~~~ quote\ndescription of merge request\n~~~"
        self.send_and_test_stream_message(
            'merge_request_created_with_assignee',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_merge_request_closed_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / MR #2 NEW MR"
        expected_message = u"Tomasz Kolek closed [MR #2](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2)"

        self.send_and_test_stream_message(
            'merge_request_closed',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_merge_request_updated_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / MR #3 New Merge Request"
        expected_message = u"Tomasz Kolek updated [MR #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3)(assigned to Tomasz Kolek)\nfrom `tomek` to `master`\n\n~~~ quote\nupdated desc\n~~~"
        self.send_and_test_stream_message(
            'merge_request_updated',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_merge_request_added_commit_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / MR #3 New Merge Request"
        expected_message = u"Tomasz Kolek added commit(s) to [MR #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3)"
        self.send_and_test_stream_message(
            'merge_request_added_commit',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_merge_request_merged_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / MR #3 New Merge Request"
        expected_message = u"Tomasz Kolek merged [MR #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3)"

        self.send_and_test_stream_message(
            'merge_request_merged',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Merge Request Hook"
        )

    def test_wiki_page_opened_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project"
        expected_message = u"Tomasz Kolek created [Wiki Page \"how to\"](https://gitlab.com/tomaszkolek0/my-awesome-project/wikis/how-to)."

        self.send_and_test_stream_message(
            'wiki_page_opened',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Wiki Page Hook"
        )

    def test_wiki_page_edited_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project"
        expected_message = u"Tomasz Kolek updated [Wiki Page \"how to\"](https://gitlab.com/tomaszkolek0/my-awesome-project/wikis/how-to)."

        self.send_and_test_stream_message(
            'wiki_page_edited',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Wiki Page Hook"
        )

    def test_build_created_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / master"
        expected_message = u"Build job_name from test stage was created."

        self.send_and_test_stream_message(
            'build_created',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Build Hook"
        )

    def test_build_started_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / master"
        expected_message = u"Build job_name from test stage started."

        self.send_and_test_stream_message(
            'build_started',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Build Hook"
        )

    def test_build_succeeded_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / master"
        expected_message = u"Build job_name from test stage changed status to success."

        self.send_and_test_stream_message(
            'build_succeeded',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Build Hook"
        )

    def test_pipeline_succeeded_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / master"
        expected_message = u"Pipeline changed status to success with build(s):\n* job_name2 - success\n* job_name - success."

        self.send_and_test_stream_message(
            'pipeline_succeeded',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Pipeline Hook"
        )

    def test_pipeline_started_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / master"
        expected_message = u"Pipeline started with build(s):\n* job_name - running\n* job_name2 - pending."

        self.send_and_test_stream_message(
            'pipeline_started',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Pipeline Hook"
        )

    def test_pipeline_pending_event_message(self):
        # type: () -> None
        expected_subject = u"my-awesome-project / master"
        expected_message = u"Pipeline was created with build(s):\n* job_name2 - pending\n* job_name - created."

        self.send_and_test_stream_message(
            'pipeline_pending',
            expected_subject,
            expected_message,
            HTTP_X_GITLAB_EVENT="Pipeline Hook"
        )
