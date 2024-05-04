from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.webhooks.git import COMMITS_LIMIT


class GitlabHookTests(WebhookTestCase):
    CHANNEL_NAME = "gitlab"
    URL_TEMPLATE = "/api/v1/external/gitlab?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "gitlab"

    def test_push_event_specified_topic(self) -> None:
        self.url = self.build_webhook_url("topic=Specific%20topic")
        expected_topic_name = "Specific topic"
        expected_message = "[[my-awesome-project](https://gitlab.com/tomaszkolek0/my-awesome-project)] Tomasz Kolek [pushed](https://gitlab.com/tomaszkolek0/my-awesome-project/-/compare/5fcdd5551fc3085df79bece2c32b1400802ac407...eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9) 2 commits to branch tomek.\n\n* b ([66abd2da288](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7))\n* c ([eb6ae1e591e](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9))"
        self.check_webhook("push_hook", expected_topic_name, expected_message)

    def test_push_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / tomek"
        expected_message = "Tomasz Kolek [pushed](https://gitlab.com/tomaszkolek0/my-awesome-project/-/compare/5fcdd5551fc3085df79bece2c32b1400802ac407...eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9) 2 commits to branch tomek.\n\n* b ([66abd2da288](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7))\n* c ([eb6ae1e591e](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9))"
        self.check_webhook("push_hook", expected_topic_name, expected_message)

    def test_push_local_branch_without_commits(self) -> None:
        expected_topic_name = "my-awesome-project / changes"
        expected_message = "Eeshan Garg [pushed](https://gitlab.com/eeshangarg/my-awesome-project/-/compare/0000000000000000000000000000000000000000...68d7a5528cf423dfaac37dd62a56ac9cc8a884e3) the branch changes."
        self.check_webhook(
            "push_hook__push_local_branch_without_commits", expected_topic_name, expected_message
        )

    def test_push_event_message_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,tomek")
        expected_topic_name = "my-awesome-project / tomek"
        expected_message = "Tomasz Kolek [pushed](https://gitlab.com/tomaszkolek0/my-awesome-project/-/compare/5fcdd5551fc3085df79bece2c32b1400802ac407...eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9) 2 commits to branch tomek.\n\n* b ([66abd2da288](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7))\n* c ([eb6ae1e591e](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9))"
        self.check_webhook("push_hook", expected_topic_name, expected_message)

    def test_push_multiple_committers(self) -> None:
        expected_topic_name = "my-awesome-project / tomek"
        expected_message = "Tomasz Kolek [pushed](https://gitlab.com/tomaszkolek0/my-awesome-project/-/compare/5fcdd5551fc3085df79bece2c32b1400802ac407...eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9) 2 commits to branch tomek. Commits by Ben (1) and Tomasz Kolek (1).\n\n* b ([66abd2da288](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7))\n* c ([eb6ae1e591e](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9))"
        self.check_webhook(
            "push_hook__push_multiple_committers", expected_topic_name, expected_message
        )

    def test_push_multiple_committers_with_others(self) -> None:
        expected_topic_name = "my-awesome-project / tomek"
        commit_info = "* b ([eb6ae1e591e](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9))\n"
        expected_message = f"Tomasz Kolek [pushed](https://gitlab.com/tomaszkolek0/my-awesome-project/-/compare/5fcdd5551fc3085df79bece2c32b1400802ac407...eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9) 7 commits to branch tomek. Commits by Ben (3), baxterthehacker (2), James (1) and others (1).\n\n{commit_info * 6}* b ([eb6ae1e591e](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9))"
        self.check_webhook(
            "push_hook__push_multiple_committers_with_others", expected_topic_name, expected_message
        )

    def test_push_commits_more_than_limit_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / tomek"
        commits_info = "* b ([66abd2da288](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7))\n"
        expected_message = f"Tomasz Kolek [pushed](https://gitlab.com/tomaszkolek0/my-awesome-project/-/compare/5fcdd5551fc3085df79bece2c32b1400802ac407...eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9) 50 commits to branch tomek.\n\n{commits_info * COMMITS_LIMIT}[and {50 - COMMITS_LIMIT} more commit(s)]"
        self.check_webhook(
            "push_hook__push_commits_more_than_limit", expected_topic_name, expected_message
        )

    def test_push_commits_more_than_limit_message_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,tomek")
        expected_topic_name = "my-awesome-project / tomek"
        commits_info = "* b ([66abd2da288](https://gitlab.com/tomaszkolek0/my-awesome-project/commit/66abd2da28809ffa128ed0447965cf11d7f863a7))\n"
        expected_message = f"Tomasz Kolek [pushed](https://gitlab.com/tomaszkolek0/my-awesome-project/-/compare/5fcdd5551fc3085df79bece2c32b1400802ac407...eb6ae1e591e0819dc5bf187c6bfe18ec065a80e9) 50 commits to branch tomek.\n\n{commits_info * COMMITS_LIMIT}[and {50 - COMMITS_LIMIT} more commit(s)]"
        self.check_webhook(
            "push_hook__push_commits_more_than_limit", expected_topic_name, expected_message
        )

    def test_remove_branch_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / tomek"
        expected_message = "Tomasz Kolek deleted branch tomek."

        self.check_webhook("push_hook__remove_branch", expected_topic_name, expected_message)

    def test_add_tag_event_message(self) -> None:
        expected_topic_name = "my-awesome-project"
        expected_message = "Tomasz Kolek pushed tag xyz."

        self.check_webhook(
            "tag_push_hook__add_tag",
            expected_topic_name,
            expected_message,
            HTTP_X_GITLAB_EVENT="Tag Push Hook",
        )

    def test_remove_tag_event_message(self) -> None:
        expected_topic_name = "my-awesome-project"
        expected_message = "Tomasz Kolek removed tag xyz."

        self.check_webhook("tag_push_hook__remove_tag", expected_topic_name, expected_message)

    def test_create_issue_without_assignee_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / issue #1 Issue title"
        expected_message = "Tomasz Kolek created [issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1):\n\n~~~ quote\nIssue description\n~~~"

        self.check_webhook(
            "issue_hook__issue_created_without_assignee", expected_topic_name, expected_message
        )

    def test_create_confidential_issue_without_assignee_event_message(self) -> None:
        expected_subject = "testing / issue #1 Testing"
        expected_message = "Joe Bloggs created [issue #1](https://gitlab.example.co.uk/joe.bloggs/testing/issues/1):\n\n~~~ quote\nTesting\n~~~"

        self.check_webhook(
            "issue_hook__confidential_issue_created_without_assignee",
            expected_subject,
            expected_message,
        )

    def test_create_issue_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "[[my-awesome-project](https://gitlab.com/tomaszkolek0/my-awesome-project)] Tomasz Kolek created [issue #1 Issue title](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1):\n\n~~~ quote\nIssue description\n~~~"

        self.check_webhook(
            "issue_hook__issue_created_without_assignee", expected_topic_name, expected_message
        )

    def test_create_issue_with_assignee_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / issue #1 Issue title"
        expected_message = "Tomasz Kolek created [issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1) (assigned to Tomasz Kolek):\n\n~~~ quote\nIssue description\n~~~"

        self.check_webhook(
            "issue_hook__issue_created_with_assignee", expected_topic_name, expected_message
        )

    def test_create_issue_with_two_assignees_event_message(self) -> None:
        expected_subject = "Zulip GitLab Test / issue #2 Zulip Test Issue 2"
        expected_message = "Adam Birds created [issue #2](https://gitlab.com/adambirds/zulip-gitlab-test/issues/2) (assigned to Adam Birds and Eeshan Garg):\n\n~~~ quote\nZulip Test Issue 2\n~~~"

        self.check_webhook(
            "issue_hook__issue_created_with_two_assignees", expected_subject, expected_message
        )

    def test_create_issue_with_three_assignees_event_message(self) -> None:
        expected_subject = "Zulip GitLab Test / issue #2 Zulip Test Issue 2"
        expected_message = "Adam Birds created [issue #2](https://gitlab.com/adambirds/zulip-gitlab-test/issues/2) (assigned to Adam Birds, Eeshan Garg and Tim Abbott):\n\n~~~ quote\nZulip Test Issue 2\n~~~"

        self.check_webhook(
            "issue_hook__issue_created_with_three_assignees", expected_subject, expected_message
        )

    def test_create_confidential_issue_with_assignee_event_message(self) -> None:
        expected_subject = "testing / issue #2 Testing"
        expected_message = "Joe Bloggs created [issue #2](https://gitlab.example.co.uk/joe.bloggs/testing/issues/2) (assigned to Joe Bloggs):\n\n~~~ quote\nTesting\n~~~"

        self.check_webhook(
            "issue_hook__confidential_issue_created_with_assignee",
            expected_subject,
            expected_message,
        )

    def test_create_issue_with_hidden_comment_in_description(self) -> None:
        expected_topic_name = "public-repo / issue #3 New Issue with hidden comment"
        expected_message = "Eeshan Garg created [issue #3](https://gitlab.com/eeshangarg/public-repo/issues/3):\n\n~~~ quote\nThis description actually has a hidden comment in it!\n~~~"

        self.check_webhook(
            "issue_hook__issue_created_with_hidden_comment_in_description",
            expected_topic_name,
            expected_message,
        )

    def test_create_confidential_issue_with_hidden_comment_in_description(self) -> None:
        expected_subject = "testing / issue #1 Testing"
        expected_message = "Joe Bloggs created [issue #1](https://gitlab.example.co.uk/joe.bloggs/testing/issues/1):\n\n~~~ quote\nThis description actually has a hidden comment in it!\n~~~"

        self.check_webhook(
            "issue_hook__confidential_issue_created_with_hidden_comment_in_description",
            expected_subject,
            expected_message,
        )

    def test_create_issue_with_null_description(self) -> None:
        expected_topic_name = "my-awesome-project / issue #7 Issue without description"
        expected_message = "Eeshan Garg created [issue #7](https://gitlab.com/eeshangarg/my-awesome-project/issues/7)."
        self.check_webhook(
            "issue_hook__issue_opened_with_null_description", expected_topic_name, expected_message
        )

    def test_update_issue_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / issue #1 Issue title_new"
        expected_message = "Tomasz Kolek updated [issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)."

        self.check_webhook("issue_hook__issue_updated", expected_topic_name, expected_message)

    def test_update_confidential_issue_event_message(self) -> None:
        expected_subject = "testing / issue #1 Testing"
        expected_message = "Joe Bloggs updated [issue #1](https://gitlab.example.co.uk/joe.bloggs/testing/issues/1)."

        self.check_webhook(
            "issue_hook__confidential_issue_updated", expected_subject, expected_message
        )

    def test_update_issue_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "[[my-awesome-project](https://gitlab.com/tomaszkolek0/my-awesome-project)] Tomasz Kolek updated [issue #1 Issue title_new](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)."

        self.check_webhook("issue_hook__issue_updated", expected_topic_name, expected_message)

    def test_close_issue_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / issue #1 Issue title_new"
        expected_message = "Tomasz Kolek closed [issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)."

        self.check_webhook("issue_hook__issue_closed", expected_topic_name, expected_message)

    def test_close_confidential_issue_event_message(self) -> None:
        expected_subject = "testing / issue #1 Testing Test"
        expected_message = "Joe Bloggs closed [issue #1](https://gitlab.example.co.uk/joe.bloggs/testing/issues/1)."

        self.check_webhook(
            "issue_hook__confidential_issue_closed", expected_subject, expected_message
        )

    def test_reopen_issue_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / issue #1 Issue title_new"
        expected_message = "Tomasz Kolek reopened [issue #1](https://gitlab.com/tomaszkolek0/my-awesome-project/issues/1)."

        self.check_webhook("issue_hook__issue_reopened", expected_topic_name, expected_message)

    def test_reopen_confidential_issue_event_message(self) -> None:
        expected_subject = "testing / issue #1 Testing Test"
        expected_message = "Joe Bloggs reopened [issue #1](https://gitlab.example.co.uk/joe.bloggs/testing/issues/1)."

        self.check_webhook(
            "issue_hook__confidential_issue_reopened", expected_subject, expected_message
        )

    def test_note_commit_event_message(self) -> None:
        expected_topic_name = "testing-zulip-gitlab-integration"
        expected_message = "Satyam Bansal [commented](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/commit/82689ddf00fd7bdadb5c2afb3b94bd555edc9d01#note_1406241063) on [82689ddf00f](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/commit/82689ddf00fd7bdadb5c2afb3b94bd555edc9d01):\n~~~ quote\nWow what a beautiful commit.\n~~~"

        self.check_webhook("note_hook__commit_note", expected_topic_name, expected_message)

    def test_note_merge_request_event_message(self) -> None:
        expected_topic_name = "testing-zulip-gitlab-integration / MR #1 add new-feature"
        expected_message = "Satyam Bansal [commented](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/merge_requests/1#note_1406328457) on [MR #1](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/merge_requests/1):\n\n~~~ quote\nI am not sure if this new feature is even required or not.\n~~~"

        self.check_webhook("note_hook__merge_request_note", expected_topic_name, expected_message)

    def test_note_merge_request_event_message_without_merge_request_title(self) -> None:
        expected_topic_name = "testing-zulip-gitlab-integration / MR #1"
        expected_message = "Satyam Bansal [commented](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/merge_requests/1#note_1406328457) on [MR #1](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/merge_requests/1):\n\n~~~ quote\nI am not sure if this new feature is even required or not.\n~~~"
        # To keep things as valid JSON.
        self.url = self.build_webhook_url(use_merge_request_title="false")
        self.check_webhook("note_hook__merge_request_note", expected_topic_name, expected_message)

    def test_note_merge_request_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "[[testing-zulip-gitlab-integration](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration)] Satyam Bansal [commented](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/merge_requests/1#note_1406328457) on [MR #1 add new-feature](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/merge_requests/1):\n\n~~~ quote\nI am not sure if this new feature is even required or not.\n~~~"

        self.check_webhook("note_hook__merge_request_note", expected_topic_name, expected_message)

    def test_note_issue_event_message(self) -> None:
        expected_topic_name = "testing-zulip-gitlab-integration / issue #1 Add more lines"
        expected_message = "Satyam Bansal [commented](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/issues/1#note_1406279810) on [issue #1](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/issues/1):\n\n~~~ quote\nThis is again a random comment.\n~~~"

        self.check_webhook("note_hook__issue_note", expected_topic_name, expected_message)

    def test_note_confidential_issue_event_message(self) -> None:
        expected_subject = "testing-zulip-gitlab-integration / issue #1 Add more lines"
        expected_message = "Satyam Bansal [commented](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/issues/1#note_1406130881) on [issue #1](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/issues/1):\n\n~~~ quote\nSome more comments\n~~~"

        self.check_webhook("note_hook__confidential_issue_note", expected_subject, expected_message)

    def test_note_issue_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "[[testing-zulip-gitlab-integration](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration)] Satyam Bansal [commented](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/issues/1#note_1406279810) on [issue #1 Add more lines](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/issues/1):\n\n~~~ quote\nThis is again a random comment.\n~~~"

        self.check_webhook("note_hook__issue_note", expected_topic_name, expected_message)

    def test_note_snippet_old_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / snippet #2 test"
        expected_message = "Tomasz Kolek [commented](https://gitlab.com/tomaszkolek0/my-awesome-project/snippets/2#note_14172058) on [snippet #2](https://gitlab.com/tomaszkolek0/my-awesome-project/-/snippets/2):\n\n~~~ quote\nNice snippet\n~~~"

        self.check_webhook("note_hook__snippet_note_old", expected_topic_name, expected_message)

    def test_note_snippet_event_message(self) -> None:
        expected_topic_name = "testing-zulip-gitlab-integration / snippet #2547713 a ver..."
        expected_message = "Satyam Bansal [commented](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/snippets/2547713#note_1424268837) on [snippet #2547713](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/snippets/2547713):\n\n~~~ quote\nsome comment\n~~~"

        self.check_webhook("note_hook__snippet_note", expected_topic_name, expected_message)

    def test_note_snippet_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "[[testing-zulip-gitlab-integration](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration)] Satyam Bansal [commented](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/snippets/2547713#note_1424268837) on [snippet #2547713 a very new new feature](https://gitlab.com/sbansal1999/testing-zulip-gitlab-integration/-/snippets/2547713):\n\n~~~ quote\nsome comment\n~~~"

        self.check_webhook("note_hook__snippet_note", expected_topic_name, expected_message)

    def test_merge_request_created_without_assignee_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #2 NEW MR"
        expected_message = "Tomasz Kolek created [MR #2](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2) from `tomek` to `master`:\n\n~~~ quote\ndescription of merge request\n~~~"

        self.check_webhook(
            "merge_request_hook__merge_request_created_without_assignee",
            expected_topic_name,
            expected_message,
        )

    def test_merge_request_created_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "[[my-awesome-project](https://gitlab.com/tomaszkolek0/my-awesome-project)] Tomasz Kolek created [MR #2 NEW MR](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2) from `tomek` to `master`:\n\n~~~ quote\ndescription of merge request\n~~~"

        self.check_webhook(
            "merge_request_hook__merge_request_created_without_assignee",
            expected_topic_name,
            expected_message,
        )

    def test_merge_request_created_with_assignee_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #3 New Merge Request"
        expected_message = "Tomasz Kolek created [MR #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3) from `tomek` to `master` (assigned to Tomasz Kolek):\n\n~~~ quote\ndescription of merge request\n~~~"
        self.check_webhook(
            "merge_request_hook__merge_request_created_with_assignee",
            expected_topic_name,
            expected_message,
        )

    def test_merge_request_created_with_multiple_assignees_event_message(self) -> None:
        expected_topic_name = "Demo Project / MR #1 Make a trivial change to the README."
        expected_message = """
Hemanth V. Alluri created [MR #1](https://gitlab.com/Hypro999/demo-project/-/merge_requests/1) from `devel` to `master` (assigned to Hemanth V. Alluri and Hemanth V. Alluri):

~~~ quote
A trivial change that should probably be ignored.
~~~
        """.strip()
        self.check_webhook(
            "merge_request_hook__merge_request_created_with_multiple_assignees",
            expected_topic_name,
            expected_message,
        )

    def test_merge_request_closed_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #2 NEW MR"
        expected_message = "Tomasz Kolek closed [MR #2](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2)."

        self.check_webhook(
            "merge_request_hook__merge_request_closed", expected_topic_name, expected_message
        )

    def test_merge_request_closed_event_message_without_using_title(self) -> None:
        expected_topic_name = "my-awesome-project / MR #2"
        expected_message = "Tomasz Kolek closed [MR #2](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2)."
        self.url = self.build_webhook_url(use_merge_request_title="false")
        self.check_webhook(
            "merge_request_hook__merge_request_closed", expected_topic_name, expected_message
        )

    def test_merge_request_closed_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "[[my-awesome-project](https://gitlab.com/tomaszkolek0/my-awesome-project)] Tomasz Kolek closed [MR #2 NEW MR](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2)."

        self.check_webhook(
            "merge_request_hook__merge_request_closed", expected_topic_name, expected_message
        )

    def test_merge_request_reopened_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #1 Update the README with author ..."
        expected_message = "Eeshan Garg reopened [MR #1](https://gitlab.com/eeshangarg/my-awesome-project/merge_requests/1)."

        self.check_webhook(
            "merge_request_hook__merge_request_reopened", expected_topic_name, expected_message
        )

    def test_merge_request_approved_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #1 Update the README with author ..."
        expected_message = "Eeshan Garg approved [MR #1](https://gitlab.com/eeshangarg/my-awesome-project/merge_requests/1)."

        self.check_webhook(
            "merge_request_hook__merge_request_approved", expected_topic_name, expected_message
        )

    def test_merge_request_updated_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #3 New Merge Request"
        expected_message = "Tomasz Kolek updated [MR #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3) (assigned to Tomasz Kolek):\n\n~~~ quote\nupdated desc\n~~~"
        self.check_webhook(
            "merge_request_hook__merge_request_updated", expected_topic_name, expected_message
        )

    def test_merge_request_added_commit_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #3 New Merge Request"
        expected_message = "Tomasz Kolek added commit(s) to [MR #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3)."
        self.check_webhook(
            "merge_request_hook__merge_request_added_commit", expected_topic_name, expected_message
        )

    def test_merge_request_merged_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #3 New Merge Request"
        expected_message = "Tomasz Kolek merged [MR #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3) from `tomek` to `master`."

        self.check_webhook(
            "merge_request_hook__merge_request_merged", expected_topic_name, expected_message
        )

    def test_wiki_page_opened_event_message(self) -> None:
        expected_topic_name = "my-awesome-project"
        expected_message = 'Tomasz Kolek created [wiki page "how to"](https://gitlab.com/tomaszkolek0/my-awesome-project/wikis/how-to).'

        self.check_webhook(
            "wiki_page_hook__wiki_page_opened", expected_topic_name, expected_message
        )

    def test_wiki_page_edited_event_message(self) -> None:
        expected_topic_name = "my-awesome-project"
        expected_message = 'Tomasz Kolek updated [wiki page "how to"](https://gitlab.com/tomaszkolek0/my-awesome-project/wikis/how-to).'

        self.check_webhook(
            "wiki_page_hook__wiki_page_edited", expected_topic_name, expected_message
        )

    def test_build_created_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / master"
        expected_message = "Build job_name from test stage was created."

        self.check_webhook(
            "build_created",
            expected_topic_name,
            expected_message,
            HTTP_X_GITLAB_EVENT="Job Hook",
        )

    def test_build_started_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / master"
        expected_message = "Build job_name from test stage started."

        self.check_webhook(
            "build_started",
            expected_topic_name,
            expected_message,
            HTTP_X_GITLAB_EVENT="Job Hook",
        )

    def test_build_succeeded_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / master"
        expected_message = "Build job_name from test stage changed status to success."

        self.check_webhook(
            "build_succeeded",
            expected_topic_name,
            expected_message,
            HTTP_X_GITLAB_EVENT="Job Hook",
        )

    def test_build_created_event_message_legacy_event_name(self) -> None:
        expected_topic_name = "my-awesome-project / master"
        expected_message = "Build job_name from test stage was created."

        self.check_webhook(
            "build_created",
            expected_topic_name,
            expected_message,
            HTTP_X_GITLAB_EVENT="Build Hook",
        )

    def test_build_started_event_message_legacy_event_name(self) -> None:
        expected_topic_name = "my-awesome-project / master"
        expected_message = "Build job_name from test stage started."

        self.check_webhook(
            "build_started",
            expected_topic_name,
            expected_message,
            HTTP_X_GITLAB_EVENT="Build Hook",
        )

    def test_build_succeeded_event_message_legacy_event_name(self) -> None:
        expected_topic_name = "my-awesome-project / master"
        expected_message = "Build job_name from test stage changed status to success."

        self.check_webhook(
            "build_succeeded",
            expected_topic_name,
            expected_message,
            HTTP_X_GITLAB_EVENT="Build Hook",
        )

    def test_pipeline_succeeded_with_artifacts_event_message(self) -> None:
        expected_topic_name = "onlysomeproject / test/links-in-zulip-pipeline-message"
        expected_message = "[Pipeline (22668)](https://gitlab.example.com/group1/onlysomeproject/-/pipelines/22668) changed status to success with build(s):\n* [cleanup:cleanup docker image](https://gitlab.example.com/group1/onlysomeproject/-/jobs/58592) - success\n* [pages](https://gitlab.example.com/group1/onlysomeproject/-/jobs/58591) - success\n  * built artifact: *artifacts.zip* [[Browse](https://gitlab.example.com/group1/onlysomeproject/-/jobs/58591/artifacts/browse)|[Download](https://gitlab.example.com/group1/onlysomeproject/-/jobs/58591/artifacts/download)]\n* [black+pytest:future environment](https://gitlab.example.com/group1/onlysomeproject/-/jobs/58590) - success\n* [docs:anaconda environment](https://gitlab.example.com/group1/onlysomeproject/-/jobs/58589) - success\n  * built artifact: *sphinx-docs.zip* [[Browse](https://gitlab.example.com/group1/onlysomeproject/-/jobs/58589/artifacts/browse)|[Download](https://gitlab.example.com/group1/onlysomeproject/-/jobs/58589/artifacts/download)]\n* [pytest:current environment](https://gitlab.example.com/group1/onlysomeproject/-/jobs/58588) - success\n* [black:current environment](https://gitlab.example.com/group1/onlysomeproject/-/jobs/58587) - success\n* [setup:docker image](https://gitlab.example.com/group1/onlysomeproject/-/jobs/58586) - success."

        self.check_webhook(
            "pipeline_hook__pipeline_succeeded_with_artifacts",
            expected_topic_name,
            expected_message,
        )

    def test_pipeline_succeeded_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / master"
        expected_message = "[Pipeline (4414206)](https://gitlab.com/TomaszKolek/my-awesome-project/-/pipelines/4414206) changed status to success with build(s):\n* [job_name2](https://gitlab.com/TomaszKolek/my-awesome-project/-/jobs/4541113) - success\n* [job_name](https://gitlab.com/TomaszKolek/my-awesome-project/-/jobs/4541112) - success."

        self.check_webhook(
            "pipeline_hook__pipeline_succeeded",
            expected_topic_name,
            expected_message,
        )

    def test_pipeline_started_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / master"
        expected_message = "[Pipeline (4414206)](https://gitlab.com/TomaszKolek/my-awesome-project/-/pipelines/4414206) started with build(s):\n* [job_name](https://gitlab.com/TomaszKolek/my-awesome-project/-/jobs/4541112) - running\n* [job_name2](https://gitlab.com/TomaszKolek/my-awesome-project/-/jobs/4541113) - pending."

        self.check_webhook(
            "pipeline_hook__pipeline_started",
            expected_topic_name,
            expected_message,
        )

    def test_pipeline_pending_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / master"
        expected_message = "[Pipeline (4414206)](https://gitlab.com/TomaszKolek/my-awesome-project/-/pipelines/4414206) was created with build(s):\n* [job_name2](https://gitlab.com/TomaszKolek/my-awesome-project/-/jobs/4541113) - pending\n* [job_name](https://gitlab.com/TomaszKolek/my-awesome-project/-/jobs/4541112) - created."

        self.check_webhook(
            "pipeline_hook__pipeline_pending",
            expected_topic_name,
            expected_message,
        )

    def test_issue_type_test_payload(self) -> None:
        expected_topic_name = "public-repo"
        expected_message = "Webhook for **public-repo** has been configured successfully! :tada:"

        self.check_webhook(
            "test_hook__issue_test_payload",
            expected_topic_name,
            expected_message,
        )

    @patch("zerver.lib.webhooks.common.check_send_webhook_message")
    def test_push_event_message_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        payload = self.get_body("push_hook")
        result = self.client_post(
            self.url, payload, HTTP_X_GITLAB_EVENT="Push Hook", content_type="application/json"
        )
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.lib.webhooks.common.check_send_webhook_message")
    def test_push_commits_more_than_limit_message_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        payload = self.get_body("push_hook__push_commits_more_than_limit")
        result = self.client_post(
            self.url, payload, HTTP_X_GITLAB_EVENT="Push Hook", content_type="application/json"
        )
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_job_hook_event(self) -> None:
        expected_topic_name = "gitlab_test / gitlab-script-trigger"
        expected_message = "Build test from test stage was created."
        self.check_webhook("job_hook__build_created", expected_topic_name, expected_message)

    def test_job_hook_event_topic(self) -> None:
        self.url = self.build_webhook_url(topic="provided topic")
        expected_topic_name = "provided topic"
        expected_message = "[[gitlab_test](http://192.168.64.1:3005/gitlab-org/gitlab-test)] Build test from test stage was created."
        self.check_webhook("job_hook__build_created", expected_topic_name, expected_message)

    def test_system_push_event_message(self) -> None:
        expected_topic_name = "gitlab / master"
        expected_message = "John Smith [pushed](http://test.example.com/gitlab/gitlab/-/compare/95790bf891e76fee5e1747ab589903a6a1f80f22...da1560886d4f094c3e6c9ef40349f7d38b5d27d7) 1 commit to branch master. Commits by Test User (1).\n\n* Add simple search to projects in public area ([c5feabde2d8](https://test.example.com/gitlab/gitlab/-/commit/c5feabde2d8cd023215af4d2ceeb7a64839fc428))"
        self.check_webhook("system_hook__push_hook", expected_topic_name, expected_message)

    def test_system_merge_request_created_without_assignee_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #2 NEW MR"
        expected_message = "Tomasz Kolek created [MR #2](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2) from `tomek` to `master`:\n\n~~~ quote\ndescription of merge request\n~~~"

        self.check_webhook(
            "system_hook__merge_request_created_without_assignee",
            expected_topic_name,
            expected_message,
        )

    def test_system_merge_request_created_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "[[my-awesome-project](https://gitlab.com/tomaszkolek0/my-awesome-project)] Tomasz Kolek created [MR #2 NEW MR](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2) from `tomek` to `master`:\n\n~~~ quote\ndescription of merge request\n~~~"

        self.check_webhook(
            "system_hook__merge_request_created_without_assignee",
            expected_topic_name,
            expected_message,
        )

    def test_system_merge_request_created_with_assignee_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #3 New Merge Request"
        expected_message = "Tomasz Kolek created [MR #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3) from `tomek` to `master` (assigned to Tomasz Kolek):\n\n~~~ quote\ndescription of merge request\n~~~"
        self.check_webhook(
            "system_hook__merge_request_created_with_assignee",
            expected_topic_name,
            expected_message,
        )

    def test_system_merge_request_closed_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #2 NEW MR"
        expected_message = "Tomasz Kolek closed [MR #2](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2)."

        self.check_webhook(
            "system_hook__merge_request_closed", expected_topic_name, expected_message
        )

    def test_system_merge_request_merged_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #3 New Merge Request"
        expected_message = "Tomasz Kolek merged [MR #3](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/3) from `tomek` to `master`."

        self.check_webhook(
            "system_hook__merge_request_merged", expected_topic_name, expected_message
        )

    def test_system_merge_request_closed_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "[[my-awesome-project](https://gitlab.com/tomaszkolek0/my-awesome-project)] Tomasz Kolek closed [MR #2 NEW MR](https://gitlab.com/tomaszkolek0/my-awesome-project/merge_requests/2)."

        self.check_webhook(
            "system_hook__merge_request_closed", expected_topic_name, expected_message
        )

    def test_merge_request_unapproved_event_message(self) -> None:
        expected_topic_name = "my-awesome-project / MR #1 Update the README with author ..."
        expected_message = "Eeshan Garg unapproved [MR #1](https://gitlab.com/eeshangarg/my-awesome-project/merge_requests/1)."

        self.check_webhook(
            "merge_request_hook__merge_request_unapproved", expected_topic_name, expected_message
        )
