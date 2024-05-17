from zerver.lib.test_classes import WebhookTestCase

TOPIC = "sandbox"
TOPIC_BRANCH_EVENTS = "sandbox / {branch}"


class Bitbucket3HookTests(WebhookTestCase):
    CHANNEL_NAME = "bitbucket3"
    URL_TEMPLATE = "/api/v1/external/bitbucket3?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "bitbucket3"

    # Diagnostics events:
    def test_ping(self) -> None:
        expected_message = (
            "Congratulations! The Bitbucket Server webhook was configured successfully!"
        )
        self.check_webhook("diagnostics_ping", "Bitbucket Server Ping", expected_message)

    def test_ping_with_user_defined_topic(self) -> None:
        self.url = self.build_webhook_url(topic="my topic")
        expected_message = (
            "Congratulations! The Bitbucket Server webhook was configured successfully!"
        )
        self.check_webhook("diagnostics_ping", "my topic", expected_message)

    # Core repo events:
    def test_commit_comment_added(self) -> None:
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) commented on [508d1b67f1f](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/commits/508d1b67f1f8f3a25f543a030a7a178894aa9907):\n~~~ quote\nJust an arbitrary comment on a commit.\n~~~"""
        self.check_webhook("commit_comment_added", TOPIC, expected_message)

    def test_commit_comment_edited(self) -> None:
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) edited their comment on [508d1b67f1f](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/commits/508d1b67f1f8f3a25f543a030a7a178894aa9907):\n~~~ quote\nJust an arbitrary comment on a commit. Nothing to see here...\n~~~"""
        self.check_webhook("commit_comment_edited", TOPIC, expected_message)

    def test_commit_comment_deleted(self) -> None:
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) deleted their comment on [508d1b67f1f](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/commits/508d1b67f1f8f3a25f543a030a7a178894aa9907):\n~~~ quote\n~~Just an arbitrary comment on a commit. Nothing to see here...~~\n~~~"""
        self.check_webhook("commit_comment_deleted", TOPIC, expected_message)

    def test_bitbucket3_repo_forked(self) -> None:
        expected_message = """User Hemanth V. Alluri(login: [hypro999](http://139.59.64.214:7990/users/hypro999)) forked the repository into [sandbox fork](http://139.59.64.214:7990/users/hypro999/repos/sandbox-fork/browse)."""
        self.check_webhook("repo_forked", TOPIC, expected_message)

    def test_bitbucket3_repo_modified(self) -> None:
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) changed the name of the **sandbox** repo from **sandbox** to **sandbox v2**."""
        expected_topic_name = "sandbox v2"
        self.check_webhook("repo_modified", expected_topic_name, expected_message)

    # Repo push events:
    def test_push_add_branch(self) -> None:
        expected_message = (
            """[hypro999](http://139.59.64.214:7990/users/hypro999) created branch2 branch."""
        )
        expected_topic_name = TOPIC_BRANCH_EVENTS.format(branch="branch2")
        self.check_webhook("repo_push_add_branch", expected_topic_name, expected_message)

    def test_push_add_tag(self) -> None:
        expected_message = (
            """[hypro999](http://139.59.64.214:7990/users/hypro999) pushed tag newtag."""
        )
        self.check_webhook("repo_push_add_tag", TOPIC, expected_message)

    def test_push_delete_branch(self) -> None:
        expected_message = (
            """[hypro999](http://139.59.64.214:7990/users/hypro999) deleted branch branch2."""
        )
        expected_topic_name = TOPIC_BRANCH_EVENTS.format(branch="branch2")
        self.check_webhook("repo_push_delete_branch", expected_topic_name, expected_message)

    def test_push_delete_tag(self) -> None:
        expected_message = (
            """[hypro999](http://139.59.64.214:7990/users/hypro999) removed tag test-tag."""
        )
        self.check_webhook("repo_push_delete_tag", TOPIC, expected_message)

    def test_push_update_single_branch(self) -> None:
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) pushed to branch master. Head is now e68c981ef53dbab0a5ca320a2d8d80e216c70528."""
        expected_topic_name = TOPIC_BRANCH_EVENTS.format(branch="master")
        self.check_webhook("repo_push_update_single_branch", expected_topic_name, expected_message)

    def test_push_update_multiple_branches(self) -> None:
        branch1_content = """[hypro999](http://139.59.64.214:7990/users/hypro999) pushed to branch branch1. Head is now 3980c2be32a7e23c795741d5dc1a2eecb9b85d6d."""
        master_content = """[hypro999](http://139.59.64.214:7990/users/hypro999) pushed to branch master. Head is now fc43d13cff1abb28631196944ba4fc4ad06a2cf2."""

        self.subscribe(self.test_user, self.CHANNEL_NAME)
        payload = self.get_body("repo_push_update_multiple_branches")

        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            payload,
            content_type="application/json",
        )

        msg = self.get_second_to_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.CHANNEL_NAME,
            topic_name=TOPIC_BRANCH_EVENTS.format(branch="branch1"),
            content=branch1_content,
        )

        msg = self.get_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.CHANNEL_NAME,
            topic_name=TOPIC_BRANCH_EVENTS.format(branch="master"),
            content=master_content,
        )

    def test_push_update_multiple_branches_with_branch_filter(self) -> None:
        self.url = self.build_webhook_url(branches="master")
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) pushed to branch master. Head is now fc43d13cff1abb28631196944ba4fc4ad06a2cf2."""
        expected_topic_name = TOPIC_BRANCH_EVENTS.format(branch="master")
        self.check_webhook(
            "repo_push_update_multiple_branches", expected_topic_name, expected_message
        )

        self.url = self.build_webhook_url(branches="branch1")
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) pushed to branch branch1. Head is now 3980c2be32a7e23c795741d5dc1a2eecb9b85d6d."""
        expected_topic_name = TOPIC_BRANCH_EVENTS.format(branch="branch1")
        self.check_webhook(
            "repo_push_update_multiple_branches", expected_topic_name, expected_message
        )

    # Core PR events:
    def test_pr_opened_without_reviewers(self) -> None:
        expected_topic_name = "sandbox / PR #1 Branch1"
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) opened [PR #1](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/1) from `branch1` to `master`:\n\n~~~ quote\n* Add file2.txt\r\n* Add file3.txt\n~~~"""
        self.check_webhook(
            "pull_request_opened_without_reviewers", expected_topic_name, expected_message
        )

    def test_pr_opened_without_description(self) -> None:
        expected_topic_name = "sandbox / PR #2 Add notes feature."
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) opened [PR #2](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/2) from `master` to `master`."""
        self.check_webhook(
            "pull_request_opened_without_description", expected_topic_name, expected_message
        )

    def test_pr_opened_with_two_reviewers(self) -> None:
        expected_topic_name = "sandbox / PR #5 Add Notes Feature"
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) opened [PR #5](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/5) from `master` to `master` (assigned reviewers: [shimura](http://139.59.64.214:7990/users/shimura) and [sougo](http://139.59.64.214:7990/users/sougo))."""
        self.check_webhook(
            "pull_request_opened_with_two_reviewers", expected_topic_name, expected_message
        )

    def test_pr_opened_with_two_reviewers_and_user_defined_topic(self) -> None:
        expected_topic_name = "sandbox / PR #5 Add Notes Feature"
        expected_topic_name = "custom_topic"
        self.url = self.build_webhook_url(topic="custom_topic")
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) opened [PR #5 Add Notes Feature](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/5) from `master` to `master` (assigned reviewers: [shimura](http://139.59.64.214:7990/users/shimura) and [sougo](http://139.59.64.214:7990/users/sougo))."""
        self.check_webhook(
            "pull_request_opened_with_two_reviewers", expected_topic_name, expected_message
        )

    def test_pr_opened_with_multiple_reviewers(self) -> None:
        expected_topic_name = "sandbox / PR #6 sample_file: Add sample_file.txt."
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) opened [PR #6](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/6) from `master` to `master` (assigned reviewers: [sougo](http://139.59.64.214:7990/users/sougo), [zura](http://139.59.64.214:7990/users/zura) and [shimura](http://139.59.64.214:7990/users/shimura)):\n\n~~~ quote\nAdd a simple text file for further testing purposes.\n~~~"""
        self.check_webhook(
            "pull_request_opened_with_multiple_reviewers", expected_topic_name, expected_message
        )

    def test_pr_modified(self) -> None:
        expected_topic_name = "sandbox / PR #1 Branch1"
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) modified [PR #1](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/1) (assigned reviewers: [shimura](http://139.59.64.214:7990/users/shimura)):\n\n~~~ quote\n* Add file2.txt\n* Add file3.txt\nBoth of these files would be important additions to the project!\n~~~"""
        self.check_webhook("pull_request_modified", expected_topic_name, expected_message)

    def test_pr_modified_with_include_title(self) -> None:
        expected_topic_name = "custom_topic"
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) modified [PR #1 Branch1](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/1) (assigned reviewers: [shimura](http://139.59.64.214:7990/users/shimura)):\n\n~~~ quote\n* Add file2.txt\n* Add file3.txt\nBoth of these files would be important additions to the project!\n~~~"""
        self.url = self.build_webhook_url(topic="custom_topic")
        self.check_webhook("pull_request_modified", expected_topic_name, expected_message)

    def test_pr_deleted(self) -> None:
        expected_topic_name = "sandbox / PR #2 Add notes feature."
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) deleted [PR #2](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/2)."""
        self.check_webhook("pull_request_deleted", expected_topic_name, expected_message)

    def test_pr_deleted_with_include_title(self) -> None:
        expected_topic_name = "custom_topic"
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) deleted [PR #2 Add notes feature.](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/2)"""
        self.url = self.build_webhook_url(topic="custom_topic")
        self.check_webhook("pull_request_deleted", expected_topic_name, expected_message)

    def test_pr_declined(self) -> None:
        expected_topic_name = "sandbox / PR #7 Crazy Idea"
        expected_message = """[zura](http://139.59.64.214:7990/users/zura) declined [PR #7](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/7)."""
        self.check_webhook("pull_request_declined", expected_topic_name, expected_message)

    def test_pr_merged(self) -> None:
        expected_topic_name = "sandbox / PR #6 sample_file: Add sample_file.txt."
        expected_message = """[zura](http://139.59.64.214:7990/users/zura) merged [PR #6](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/6) from `master` to `master`."""
        self.check_webhook("pull_request_merged", expected_topic_name, expected_message)

    # PR reviewer events:
    def test_pr_approved(self) -> None:
        expected_topic_name = "sandbox / PR #6 sample_file: Add sample_file.txt."
        expected_message = """[zura](http://139.59.64.214:7990/users/zura) approved [PR #6](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/6)."""
        self.check_webhook("pull_request_approved", expected_topic_name, expected_message)

    def test_pr_unapproved(self) -> None:
        expected_topic_name = "sandbox / PR #6 sample_file: Add sample_file.txt."
        expected_message = """[zura](http://139.59.64.214:7990/users/zura) unapproved [PR #6](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/6)."""
        self.check_webhook("pull_request_unapproved", expected_topic_name, expected_message)

    def test_pr_marked_as_needs_review(self) -> None:
        expected_topic_name = "sandbox / PR #6 sample_file: Add sample_file.txt."
        expected_message = """[zura](http://139.59.64.214:7990/users/zura) marked [PR #6](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/6) as \"needs work\"."""
        self.check_webhook("pull_request_needs_work", expected_topic_name, expected_message)

    def test_pr_marked_as_needs_review_and_include_title(self) -> None:
        expected_topic_name = "custom_topic"
        expected_message = """[zura](http://139.59.64.214:7990/users/zura) marked [PR #6 sample_file: Add sample_file.txt.](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/6) as \"needs work\"."""
        self.url = self.build_webhook_url(topic="custom_topic")
        self.check_webhook("pull_request_needs_work", expected_topic_name, expected_message)

    def test_pull_request_reviewer_added(self) -> None:
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) reassigned [PR #1](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/1) to [shimura](http://139.59.64.214:7990/users/shimura)."""
        expected_topic_name = "sandbox / PR #1 Branch1"
        self.check_webhook("pull_request_add_reviewer", expected_topic_name, expected_message)

    def test_pull_request_reviewer_added_and_include_title(self) -> None:
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) reassigned [PR #1 Branch1](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/1) to [shimura](http://139.59.64.214:7990/users/shimura)."""
        expected_topic_name = "custom_topic"
        self.url = self.build_webhook_url(topic="custom_topic")
        self.check_webhook("pull_request_add_reviewer", expected_topic_name, expected_message)

    def test_pull_request_reviewers_added(self) -> None:
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) reassigned [PR #1](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/1) to [shimura](http://139.59.64.214:7990/users/shimura) and [sougo](http://139.59.64.214:7990/users/sougo)."""
        expected_topic_name = "sandbox / PR #1 Branch1"
        self.check_webhook("pull_request_add_two_reviewers", expected_topic_name, expected_message)

    def test_pull_request_remove_all_reviewers(self) -> None:
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) removed all reviewers from [PR #1](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/1)."""
        expected_topic_name = "sandbox / PR #1 Branch1"
        self.check_webhook("pull_request_remove_reviewer", expected_topic_name, expected_message)

    def test_pull_request_remove_all_reviewers_with_title(self) -> None:
        expected_message = """[hypro999](http://139.59.64.214:7990/users/hypro999) removed all reviewers from [PR #1 Branch1](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/1)."""
        expected_topic_name = "sandbox / PR #1 Branch1"
        expected_topic_name = "custom_topic"
        self.url = self.build_webhook_url(topic="custom_topic")
        self.check_webhook("pull_request_remove_reviewer", expected_topic_name, expected_message)

    # PR comment events:
    def test_pull_request_comment_added(self) -> None:
        expected_message = """[zura](http://139.59.64.214:7990/users/zura) commented on [PR #6](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/6):\n\n~~~ quote\nThis seems like a pretty good idea.\n~~~"""
        expected_topic_name = "sandbox / PR #6 sample_file: Add sample_file.txt."
        self.check_webhook("pull_request_comment_added", expected_topic_name, expected_message)

    def test_pull_request_comment_edited(self) -> None:
        expected_message = """[zura](http://139.59.64.214:7990/users/zura) edited their comment on [PR #6](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/6):\n\n~~~ quote\nThis seems like a pretty good idea. @shimura what do you think?\n~~~"""
        expected_topic_name = "sandbox / PR #6 sample_file: Add sample_file.txt."
        self.check_webhook("pull_request_comment_edited", expected_topic_name, expected_message)

    def test_pull_request_comment_deleted(self) -> None:
        expected_message = """[zura](http://139.59.64.214:7990/users/zura) deleted their comment on [PR #6](http://139.59.64.214:7990/projects/SBOX/repos/sandbox/pull-requests/6):\n\n~~~ quote\n~~This seems like a pretty good idea. @shimura what do you think?~~\n~~~"""
        expected_topic_name = "sandbox / PR #6 sample_file: Add sample_file.txt."
        self.check_webhook("pull_request_comment_deleted", expected_topic_name, expected_message)
