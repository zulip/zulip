from unittest.mock import patch

import orjson

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.webhooks.git import COMMITS_LIMIT

TOPIC_REPO = "public-repo"
TOPIC_ISSUE = "public-repo / issue #2 Spelling error in the README file"
TOPIC_PR = "public-repo / PR #1 Update the README with new information"
TOPIC_DEPLOYMENT = "public-repo / Deployment on production"
TOPIC_ORGANIZATION = "baxterandthehackers organization"
TOPIC_BRANCH = "public-repo / changes"
TOPIC_WIKI = "public-repo / wiki pages"
TOPIC_DISCUSSION = "public-repo discussion #90: Welcome to discussions!"


class GitHubWebhookTest(WebhookTestCase):
    STREAM_NAME = "github"
    URL_TEMPLATE = "/api/v1/external/github?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "github"

    def test_ping_event(self) -> None:
        expected_message = "GitHub webhook has been successfully configured by TomaszKolek."
        self.check_webhook("ping", TOPIC_REPO, expected_message)

    def test_star_event(self) -> None:
        expected_message = "Codertocat starred the repository [Codertocat/Hello-World](https://github.com/Codertocat/Hello-World)."
        expected_topic = "Hello-World"
        self.check_webhook("star", expected_topic, expected_message)

    def test_ping_organization_event(self) -> None:
        expected_message = "GitHub webhook has been successfully configured by eeshangarg."
        self.check_webhook("ping__organization", "zulip-test-org", expected_message)

    def test_push_delete_branch(self) -> None:
        expected_message = "eeshangarg [deleted](https://github.com/eeshangarg/public-repo/compare/2e8cf535fb38...000000000000) the branch feature."
        self.check_webhook("push__delete_branch", "public-repo / feature", expected_message)

    def test_push_local_branch_without_commits(self) -> None:
        expected_message = "eeshangarg [pushed](https://github.com/eeshangarg/public-repo/compare/feature) the branch feature."
        self.check_webhook(
            "push__local_branch_without_commits", "public-repo / feature", expected_message
        )

    def test_push_1_commit(self) -> None:
        expected_message = "baxterthehacker [pushed](https://github.com/baxterthehacker/public-repo/compare/9049f1265b7d...0d1a26e67d8f) 1 commit to branch changes.\n\n* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))"
        self.check_webhook("push__1_commit", TOPIC_BRANCH, expected_message)

    def test_push_1_commit_without_username(self) -> None:
        expected_message = "eeshangarg [pushed](https://github.com/eeshangarg/public-repo/compare/0383613da871...2e8cf535fb38) 1 commit to branch changes. Commits by John Snow (1).\n\n* Update the README ([2e8cf535fb3](https://github.com/eeshangarg/public-repo/commit/2e8cf535fb38a3dab2476cdf856efda904ad4c94))"
        self.check_webhook("push__1_commit_without_username", TOPIC_BRANCH, expected_message)

    def test_push_1_commit_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url("master,changes")
        expected_message = "baxterthehacker [pushed](https://github.com/baxterthehacker/public-repo/compare/9049f1265b7d...0d1a26e67d8f) 1 commit to branch changes.\n\n* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))"
        self.check_webhook("push__1_commit", TOPIC_BRANCH, expected_message)

    def test_push_multiple_committers(self) -> None:
        commits_info = "* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))\n"
        expected_message = f"""baxterthehacker [pushed](https://github.com/baxterthehacker/public-repo/compare/9049f1265b7d...0d1a26e67d8f) 6 commits to branch changes. Commits by Tomasz (3), Ben (2) and baxterthehacker (1).\n\n{commits_info * 5}* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))"""

        self.check_webhook("push__multiple_committers", TOPIC_BRANCH, expected_message)

    def test_push_multiple_committers_with_others(self) -> None:
        commits_info = "* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))\n"
        expected_message = f"""baxterthehacker [pushed](https://github.com/baxterthehacker/public-repo/compare/9049f1265b7d...0d1a26e67d8f) 10 commits to branch changes. Commits by Tomasz (4), Ben (3), James (2) and others (1).\n\n{commits_info * 9}* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))"""

        self.check_webhook("push__multiple_committers_with_others", TOPIC_BRANCH, expected_message)

    def test_push_multiple_committers_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url("master,changes")
        commits_info = "* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))\n"
        expected_message = f"""baxterthehacker [pushed](https://github.com/baxterthehacker/public-repo/compare/9049f1265b7d...0d1a26e67d8f) 6 commits to branch changes. Commits by Tomasz (3), Ben (2) and baxterthehacker (1).\n\n{commits_info * 5}* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))"""

        self.check_webhook("push__multiple_committers", TOPIC_BRANCH, expected_message)

    def test_push_multiple_committers_with_others_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url("master,changes")
        commits_info = "* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))\n"
        expected_message = f"""baxterthehacker [pushed](https://github.com/baxterthehacker/public-repo/compare/9049f1265b7d...0d1a26e67d8f) 10 commits to branch changes. Commits by Tomasz (4), Ben (3), James (2) and others (1).\n\n{commits_info * 9}* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))"""

        self.check_webhook("push__multiple_committers_with_others", TOPIC_BRANCH, expected_message)

    def test_push_50_commits(self) -> None:
        commit_info = "* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))\n"
        expected_message = f"baxterthehacker [pushed](https://github.com/baxterthehacker/public-repo/compare/9049f1265b7d...0d1a26e67d8f) 50 commits to branch changes.\n\n{commit_info * COMMITS_LIMIT}[and 30 more commit(s)]"
        self.check_webhook("push__50_commits", TOPIC_BRANCH, expected_message)

    def test_push_50_commits_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,changes")
        commit_info = "* Update README.md ([0d1a26e67d8](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c))\n"
        expected_message = f"baxterthehacker [pushed](https://github.com/baxterthehacker/public-repo/compare/9049f1265b7d...0d1a26e67d8f) 50 commits to branch changes.\n\n{commit_info * COMMITS_LIMIT}[and 30 more commit(s)]"
        self.check_webhook("push__50_commits", TOPIC_BRANCH, expected_message)

    def test_commit_comment_msg(self) -> None:
        expected_message = "baxterthehacker [commented](https://github.com/baxterthehacker/public-repo/commit/9049f1265b7d61be4a8904a9a27120d2064dab3b#commitcomment-11056394) on [9049f1265b7](https://github.com/baxterthehacker/public-repo/commit/9049f1265b7d61be4a8904a9a27120d2064dab3b):\n~~~ quote\nThis is a really good change! :+1:\n~~~"
        self.check_webhook("commit_comment", TOPIC_REPO, expected_message)

    def test_create_msg(self) -> None:
        expected_message = "baxterthehacker created tag 0.0.1."
        self.check_webhook("create", TOPIC_REPO, expected_message)

    def test_delete_msg(self) -> None:
        expected_message = "baxterthehacker deleted tag simple-tag."
        self.check_webhook("delete", TOPIC_REPO, expected_message)

    def test_deployment_msg(self) -> None:
        expected_message = "baxterthehacker created new deployment."
        self.check_webhook("deployment", TOPIC_DEPLOYMENT, expected_message)

    def test_deployment_status_msg(self) -> None:
        expected_message = "Deployment changed status to success."
        self.check_webhook("deployment_status", TOPIC_DEPLOYMENT, expected_message)

    def test_fork_msg(self) -> None:
        expected_message = "baxterandthehackers forked [public-repo](https://github.com/baxterandthehackers/public-repo)."
        self.check_webhook("fork", TOPIC_REPO, expected_message)

    def test_issue_comment_msg(self) -> None:
        expected_message = "baxterthehacker [commented](https://github.com/baxterthehacker/public-repo/issues/2#issuecomment-99262140) on [issue #2](https://github.com/baxterthehacker/public-repo/issues/2):\n\n~~~ quote\nYou are totally right! I'll get this fixed right away.\n~~~"
        self.check_webhook("issue_comment", TOPIC_ISSUE, expected_message)

    def test_issue_comment_deleted_msg(self) -> None:
        expected_topic = "Scheduler / issue #5 This is a new issue"
        expected_message = "eeshangarg deleted a [comment](https://github.com/eeshangarg/Scheduler/issues/5#issuecomment-425164194) on [issue #5](https://github.com/eeshangarg/Scheduler/issues/5):\n\n~~~ quote\nThis is a comment on this new issue.\n~~~"
        self.check_webhook("issue_comment__deleted", expected_topic, expected_message)

    def test_issue_comment_msg_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "baxterthehacker [commented](https://github.com/baxterthehacker/public-repo/issues/2#issuecomment-99262140) on [issue #2 Spelling error in the README file](https://github.com/baxterthehacker/public-repo/issues/2):\n\n~~~ quote\nYou are totally right! I'll get this fixed right away.\n~~~"
        self.check_webhook("issue_comment", expected_topic, expected_message)

    def test_issue_msg(self) -> None:
        expected_message = "baxterthehacker opened [issue #2](https://github.com/baxterthehacker/public-repo/issues/2):\n\n~~~ quote\nIt looks like you accidentally spelled 'commit' with two 't's.\n~~~"
        self.check_webhook("issues", TOPIC_ISSUE, expected_message)

    def test_issue_msg_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "baxterthehacker opened [issue #2 Spelling error in the README file](https://github.com/baxterthehacker/public-repo/issues/2):\n\n~~~ quote\nIt looks like you accidentally spelled 'commit' with two 't's.\n~~~"
        self.check_webhook("issues", expected_topic, expected_message)

    def test_membership_msg(self) -> None:
        expected_message = (
            "baxterthehacker added [kdaigle](https://github.com/kdaigle) to the Contractors team."
        )
        self.check_webhook("membership", TOPIC_ORGANIZATION, expected_message)

    def test_membership_removal_msg(self) -> None:
        expected_message = "baxterthehacker removed [kdaigle](https://github.com/kdaigle) from the Contractors team."
        self.check_webhook("membership__removal", TOPIC_ORGANIZATION, expected_message)

    def test_member_msg(self) -> None:
        expected_message = "baxterthehacker added [octocat](https://github.com/octocat) to [public-repo](https://github.com/baxterthehacker/public-repo)."
        self.check_webhook("member", TOPIC_REPO, expected_message)

    def test_pull_request_opened_msg(self) -> None:
        expected_message = "baxterthehacker opened [PR #1](https://github.com/baxterthehacker/public-repo/pull/1) from `changes` to `master`:\n\n~~~ quote\nThis is a pretty simple change that we need to pull into master.\n~~~"
        self.check_webhook("pull_request__opened", TOPIC_PR, expected_message)

    def test_pull_request_opened_with_preassigned_assignee_msg(self) -> None:
        expected_topic = "Scheduler / PR #4 Improve README"
        expected_message = "eeshangarg opened [PR #4](https://github.com/eeshangarg/Scheduler/pull/4) (assigned to eeshangarg) from `improve-readme-2` to `master`."
        self.check_webhook(
            "pull_request__opened_with_preassigned_assignee", expected_topic, expected_message
        )

    def test_pull_request_opened_msg_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "baxterthehacker opened [PR #1 Update the README with new information](https://github.com/baxterthehacker/public-repo/pull/1) from `changes` to `master`:\n\n~~~ quote\nThis is a pretty simple change that we need to pull into master.\n~~~"
        self.check_webhook("pull_request__opened", expected_topic, expected_message)

    def test_pull_request_synchronized_msg(self) -> None:
        expected_message = "baxterthehacker updated [PR #1](https://github.com/baxterthehacker/public-repo/pull/1) from `changes` to `master`."
        self.check_webhook("pull_request__synchronized", TOPIC_PR, expected_message)

    def test_pull_request_closed_msg(self) -> None:
        expected_message = "baxterthehacker closed without merge [PR #1](https://github.com/baxterthehacker/public-repo/pull/1)."
        self.check_webhook("pull_request__closed", TOPIC_PR, expected_message)

    def test_pull_request_closed_msg_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "baxterthehacker closed without merge [PR #1 Update the README with new information](https://github.com/baxterthehacker/public-repo/pull/1)."
        self.check_webhook("pull_request__closed", expected_topic, expected_message)

    def test_pull_request_merged_msg(self) -> None:
        expected_message = (
            "baxterthehacker merged [PR #1](https://github.com/baxterthehacker/public-repo/pull/1)."
        )
        self.check_webhook("pull_request__merged", TOPIC_PR, expected_message)

    def test_public_msg(self) -> None:
        expected_message = "baxterthehacker made the repository [baxterthehacker/public-repo](https://github.com/baxterthehacker/public-repo) public."
        self.check_webhook("public", TOPIC_REPO, expected_message)

    def test_wiki_pages_msg(self) -> None:
        expected_message = "jasonrudolph:\n* created [Home](https://github.com/baxterthehacker/public-repo/wiki/Home)\n* created [Home](https://github.com/baxterthehacker/public-repo/wiki/Home)"
        self.check_webhook("gollum__wiki_pages", TOPIC_WIKI, expected_message)

    def test_watch_msg(self) -> None:
        expected_message = "baxterthehacker starred the repository [baxterthehacker/public-repo](https://github.com/baxterthehacker/public-repo)."
        self.check_webhook("watch__repository", TOPIC_REPO, expected_message)

    def test_repository_msg(self) -> None:
        expected_message = "baxterthehacker created the repository [baxterandthehackers/public-repo](https://github.com/baxterandthehackers/public-repo)."
        self.check_webhook("repository", TOPIC_REPO, expected_message)

    def test_team_add_msg(self) -> None:
        expected_message = "The repository [baxterandthehackers/public-repo](https://github.com/baxterandthehackers/public-repo) was added to team github."
        self.check_webhook("team_add", TOPIC_REPO, expected_message)

    def test_release_msg(self) -> None:
        expected_message = "baxterthehacker published release [0.0.1](https://github.com/baxterthehacker/public-repo/releases/tag/0.0.1) for tag 0.0.1."
        self.check_webhook("release", TOPIC_REPO, expected_message)

    def test_release_msg_with_name(self) -> None:
        expected_message = "baxterthehacker published release [0.0.1](https://github.com/baxterthehacker/public-repo/releases/tag/0.0.1) for tag 0.0.1."
        self.check_webhook("release__with_name", TOPIC_REPO, expected_message)

    def test_page_build_msg(self) -> None:
        expected_message = (
            "GitHub Pages build, triggered by baxterthehacker, has finished building."
        )
        self.check_webhook("page_build", TOPIC_REPO, expected_message)

    def test_page_build_errored_msg(self) -> None:
        expected_message = "GitHub Pages build, triggered by baxterthehacker, has failed: \n~~~ quote\nSomething went wrong.\n~~~."
        self.check_webhook("page_build__errored", TOPIC_REPO, expected_message)

    def test_status_msg(self) -> None:
        expected_message = "[9049f1265b7](https://github.com/baxterthehacker/public-repo/commit/9049f1265b7d61be4a8904a9a27120d2064dab3b) changed its status to success."
        self.check_webhook("status", TOPIC_REPO, expected_message)

    def test_status_with_target_url_msg(self) -> None:
        expected_message = "[9049f1265b7](https://github.com/baxterthehacker/public-repo/commit/9049f1265b7d61be4a8904a9a27120d2064dab3b) changed its status to [success](https://example.com/build/status)."
        self.check_webhook("status__with_target_url", TOPIC_REPO, expected_message)

    def test_pull_request_review_msg(self) -> None:
        expected_message = "baxterthehacker submitted [PR review](https://github.com/baxterthehacker/public-repo/pull/1#pullrequestreview-2626884)."
        self.check_webhook("pull_request_review", TOPIC_PR, expected_message)

    def test_pull_request_review_msg_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "baxterthehacker submitted [PR review for #1 Update the README with new information](https://github.com/baxterthehacker/public-repo/pull/1#pullrequestreview-2626884)."
        self.check_webhook("pull_request_review", expected_topic, expected_message)

    def test_pull_request_review_comment_msg(self) -> None:
        expected_message = "baxterthehacker created [PR review comment](https://github.com/baxterthehacker/public-repo/pull/1#discussion_r29724692):\n\n~~~ quote\nMaybe you should use more emojji on this line.\n~~~"
        self.check_webhook("pull_request_review_comment", TOPIC_PR, expected_message)

    def test_pull_request_review_comment_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "baxterthehacker created [PR review comment on #1 Update the README with new information](https://github.com/baxterthehacker/public-repo/pull/1#discussion_r29724692):\n\n~~~ quote\nMaybe you should use more emojji on this line.\n~~~"
        self.check_webhook("pull_request_review_comment", expected_topic, expected_message)

    def test_pull_request_locked(self) -> None:
        expected_message = "tushar912 has locked [PR #1](https://github.com/tushar912/public-repo/pull/1) as off-topic and limited conversation to collaborators."
        self.check_webhook("pull_request__locked", TOPIC_PR, expected_message)

    def test_pull_request_unlocked(self) -> None:
        expected_message = (
            "tushar912 has unlocked [PR #1](https://github.com/tushar912/public-repo/pull/1)."
        )
        self.check_webhook("pull_request__unlocked", TOPIC_PR, expected_message)

    def test_pull_request_auto_merge_enabled(self) -> None:
        expected_message = "tushar912 has enabled auto merge for [PR #1](https://github.com/tushar912/public-repo/pull/1)."
        self.check_webhook("pull_request__auto_merge_enabled", TOPIC_PR, expected_message)

    def test_pull_request_auto_merge_disabled(self) -> None:
        expected_message = "tushar912 has disabled auto merge for [PR #1](https://github.com/tushar912/public-repo/pull/1)."
        self.check_webhook("pull_request__auto_merge_disabled", TOPIC_PR, expected_message)

    def test_push_tag_msg(self) -> None:
        expected_message = "baxterthehacker pushed tag abc."
        self.check_webhook("push__tag", TOPIC_REPO, expected_message)

    def test_pull_request_edited_msg(self) -> None:
        expected_message = "baxterthehacker edited [PR #1](https://github.com/baxterthehacker/public-repo/pull/1) from `changes` to `master`."
        self.check_webhook("pull_request__edited", TOPIC_PR, expected_message)

    def test_pull_request_edited_with_body_change(self) -> None:
        expected_message = "cozyrohan edited [PR #1](https://github.com/cozyrohan/public-repo/pull/1) from `issue-#1` to `main`:\n\n~~~ quote\nPR EDITED\n~~~"
        self.check_webhook("pull_request__edited_with_body_change", TOPIC_PR, expected_message)

    def test_pull_request_synchronized_with_body(self) -> None:
        expected_message = "baxterthehacker updated [PR #1](https://github.com/baxterthehacker/public-repo/pull/1) from `changes` to `master`."
        self.check_webhook("pull_request__synchronized_with_body", TOPIC_PR, expected_message)

    def test_pull_request_assigned_msg(self) -> None:
        expected_message = "baxterthehacker assigned [PR #1](https://github.com/baxterthehacker/public-repo/pull/1) to baxterthehacker."
        self.check_webhook("pull_request__assigned", TOPIC_PR, expected_message)

    def test_pull_request_assigned_msg_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "baxterthehacker assigned [PR #1 Update the README with new information](https://github.com/baxterthehacker/public-repo/pull/1) to baxterthehacker."
        self.check_webhook("pull_request__assigned", expected_topic, expected_message)

    def test_pull_request_unassigned_msg(self) -> None:
        expected_message = (
            "eeshangarg unassigned [PR #1](https://github.com/zulip-test-org/helloworld/pull/1)."
        )
        self.check_webhook(
            "pull_request__unassigned",
            "helloworld / PR #1 Mention that Zulip rocks!",
            expected_message,
        )

    def test_pull_request_ready_for_review_msg(self) -> None:
        expected_message = "**Hypro999** has marked [PR #2](https://github.com/Hypro999/temp-test-github-webhook/pull/2) as ready for review."
        self.check_webhook(
            "pull_request__ready_for_review",
            "temp-test-github-webhook / PR #2 Test",
            expected_message,
        )

    def test_pull_request_review_requested_msg(self) -> None:
        expected_message = "**eeshangarg** requested [showell](https://github.com/showell) for a review on [PR #1](https://github.com/eeshangarg/Scheduler/pull/1)."
        self.check_webhook(
            "pull_request__review_requested",
            "Scheduler / PR #1 This is just a test commit",
            expected_message,
        )

    def test_pull_request__review_requested_team_reviewer_msg(self) -> None:
        expected_message = "**singhsourabh** requested [authority](https://github.com/orgs/test-org965/teams/authority) for a review on [PR #4](https://github.com/test-org965/webhook-test/pull/4)."
        self.check_webhook(
            "pull_request__review_requested_team_reviewer",
            "webhook-test / PR #4 testing webhook",
            expected_message,
        )

    def test_pull_request_review_requested_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "**eeshangarg** requested [showell](https://github.com/showell) for a review on [PR #1 This is just a test commit](https://github.com/eeshangarg/Scheduler/pull/1)."
        self.check_webhook("pull_request__review_requested", expected_topic, expected_message)

    def test_check_run(self) -> None:
        expected_topic = "hello-world / checks"
        expected_message = """
Check [randscape](http://github.com/github/hello-world/runs/4) completed (success). ([d6fde92930d](http://github.com/github/hello-world/commit/d6fde92930d4715a2b49857d24b940956b26d2d3))
""".strip()
        self.check_webhook("check_run__completed", expected_topic, expected_message)

    def test_team_edited_description(self) -> None:
        expected_topic = "team Testing"
        expected_message = """\
**Hypro999** changed the team description to:
```quote
A temporary team so that I can get some webhook fixtures!
```"""
        self.check_webhook("team__edited_description", expected_topic, expected_message)

    def test_team_edited_name(self) -> None:
        expected_topic = "team Testing Team"
        expected_message = """Team `Testing` was renamed to `Testing Team`."""
        self.check_webhook("team__edited_name", expected_topic, expected_message)

    def test_team_edited_privacy(self) -> None:
        expected_topic = "team Testing Team"
        expected_message = """Team visibility changed to `secret`"""
        self.check_webhook("team__edited_privacy_secret", expected_topic, expected_message)

    def verify_post_is_ignored(self, payload: str, http_x_github_event: str) -> None:
        with patch("zerver.webhooks.github.view.check_send_webhook_message") as m:
            result = self.client_post(
                self.url,
                payload,
                HTTP_X_GITHUB_EVENT=http_x_github_event,
                content_type="application/json",
            )
        self.assertFalse(m.called)
        self.assert_json_success(result)

    def test_check_run_in_progress_ignore(self) -> None:
        payload = self.get_body("check_run__in_progress")
        self.verify_post_is_ignored(payload, "check_run")

    def test_ignored_pull_request_actions(self) -> None:
        ignored_actions = [
            "approved",
            "converted_to_draft",
            "labeled",
            "review_request_removed",
            "unlabeled",
        ]
        for action in ignored_actions:
            data = dict(action=action)
            payload = orjson.dumps(data).decode()
            self.verify_post_is_ignored(payload, "pull_request")

    def test_ignored_team_actions(self) -> None:
        ignored_actions = [
            "added_to_repository",
            "created",
            "deleted",
            "removed_from_repository",
        ]
        for action in ignored_actions:
            data = dict(action=action)
            payload = orjson.dumps(data).decode()
            self.verify_post_is_ignored(payload, "team")

    def test_push_1_commit_filtered_by_branches_ignore(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        payload = self.get_body("push__1_commit")
        self.verify_post_is_ignored(payload, "push")

    def test_push_50_commits_filtered_by_branches_ignore(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        payload = self.get_body("push__50_commits")
        self.verify_post_is_ignored(payload, "push")

    def test_push_multiple_committers_filtered_by_branches_ignore(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        payload = self.get_body("push__multiple_committers")
        self.verify_post_is_ignored(payload, "push")

    def test_push_multiple_committers_with_others_filtered_by_branches_ignore(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        payload = self.get_body("push__multiple_committers_with_others")
        self.verify_post_is_ignored(payload, "push")

    def test_repository_vulnerability_alert_ignore(self) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body("repository_vulnerability_alert")
        self.verify_post_is_ignored(payload, "repository_vulnerability_alert")

    def test_ignored_events(self) -> None:
        # The payload for these events never gets looked at in the
        # webhook itself; it only needs to be valid JSON.
        payload = "{}"

        ignored_events = [
            "check_suite",
            "label",
            "meta",
            "milestone",
            "organization",
            "project_card",
            "repository_vulnerability_alert",
        ]

        for event in ignored_events:
            self.verify_post_is_ignored(payload, event)

    def test_team_edited_with_unsupported_keys(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)

        event = "team"
        payload = dict(
            action="edited",
            changes=dict(
                bogus_key1={},
                bogus_key2={},
            ),
            team=dict(name="My Team"),
        )

        log_mock = patch("zerver.decorator.webhook_unsupported_events_logger.exception")

        with log_mock as m:
            stream_message = self.send_webhook_payload(
                self.test_user,
                self.url,
                payload,
                HTTP_X_GITHUB_EVENT=event,
                content_type="application/json",
            )

        self.assert_stream_message(
            message=stream_message,
            stream_name=self.STREAM_NAME,
            topic_name="team My Team",
            content="Team has changes to `bogus_key1/bogus_key2` data.",
        )

        m.assert_called_once()
        msg = m.call_args[0][0]
        stack_info = m.call_args[1]["stack_info"]

        self.assertIn(
            "The 'team/edited (changes: bogus_key1/bogus_key2)' event isn't currently supported by the GitHub webhook",
            msg,
        )
        self.assertTrue(stack_info)

    def test_discussion_msg(self) -> None:
        expected_message = "Codertocat created [discussion #90](https://github.com/baxterthehacker/public-repo/discussions/90) in General:\n```quote\n### Welcome to discussions!\nWe're glad to have you here!\n```"
        self.check_webhook("discussion", TOPIC_DISCUSSION, expected_message)

    def test_discussion_comment_msg(self) -> None:
        expected_message = "Codertocat [commented](https://github.com/baxterthehacker/public-repo/discussions/90#discussioncomment-544078) on [discussion #90](https://github.com/baxterthehacker/public-repo/discussions/90):\n```quote\nI have so many questions to ask you!\n```"
        self.check_webhook("discussion_comment", TOPIC_DISCUSSION, expected_message)
