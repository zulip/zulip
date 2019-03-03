#  -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class Bitbucket3HookTests(WebhookTestCase):
    STREAM_NAME = "bitbucket3"
    URL_TEMPLATE = "/api/v1/external/bitbucket3?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = "bitbucket3"
    EXPECTED_TOPIC = "sandbox"
    EXPECTED_TOPIC_BRANCH_EVENTS = "sandbox / {branch}"

    def test_commit_comment_added(self) -> None:
        expected_message = """hypro999 commented on [508d1b6](http://139.59.64.214:7990/projects\
/SBOX/repos/sandbox/commits/508d1b67f1f8f3a25f543a030a7a178894aa9907)\n~~~ quote\nJust an \
arbitrary comment on a commit.\n~~~"""
        self.send_and_test_stream_message("commit_comment_added",
                                          self.EXPECTED_TOPIC,
                                          expected_message)

    def test_commit_comment_edited(self) -> None:
        expected_message = """hypro999 edited their comment on [508d1b6](http://139.59.64.214:7990\
/projects/SBOX/repos/sandbox/commits/508d1b67f1f8f3a25f543a030a7a178894aa9907)\n~~~ quote\nJust \
an arbitrary comment on a commit. Nothing to see here...\n~~~"""
        self.send_and_test_stream_message("commit_comment_edited",
                                          self.EXPECTED_TOPIC,
                                          expected_message)

    def test_commit_comment_deleted(self) -> None:
        expected_message = """hypro999 deleted their comment on [508d1b6]\
(http://139.59.64.214:7990/projects/SBOX/repos/sandbox/commits/508d1b67f1f8f3a25f543a030a7a178894a\
a9907)\n~~~ quote\nJust an arbitrary comment on a commit. Nothing to see here...\n~~~"""
        self.send_and_test_stream_message("commit_comment_deleted",
                                          self.EXPECTED_TOPIC,
                                          expected_message)

    def test_bitbucket3_repo_forked(self) -> None:
        expected_message = """User Hemanth V. Alluri(login: hypro999) forked the repository into \
[sandbox fork](http://139.59.64.214:7990/users/hypro999/repos/sandbox-fork/browse)."""
        self.send_and_test_stream_message("repo_forked", self.EXPECTED_TOPIC, expected_message)

    def test_bitbucket3_repo_modified(self) -> None:
        expected_message = """hypro999 changed the name of the **sandbox** repo from **sandbox** \
to **sandbox v2**"""
        expected_topic = "sandbox v2"
        self.send_and_test_stream_message("repo_modified", expected_topic, expected_message)

    def test_push_add_branch(self) -> None:
        expected_message = """hypro999 created branch2 branch"""
        expected_topic = self.EXPECTED_TOPIC_BRANCH_EVENTS.format(branch="branch2")
        self.send_and_test_stream_message("repo_push_add_branch",
                                          expected_topic,
                                          expected_message)

    def test_push_add_tag(self) -> None:
        expected_message = """hypro999 pushed tag newtag"""
        self.send_and_test_stream_message("repo_push_add_tag",
                                          self.EXPECTED_TOPIC,
                                          expected_message)

    def test_push_delete_branch(self) -> None:
        expected_message = """hypro999 deleted branch branch2"""
        expected_topic = self.EXPECTED_TOPIC_BRANCH_EVENTS.format(branch="branch2")
        self.send_and_test_stream_message("repo_push_delete_branch",
                                          expected_topic,
                                          expected_message)

    def test_push_delete_tag(self) -> None:
        expected_message = """hypro999 removed tag test-tag"""
        self.send_and_test_stream_message("repo_push_delete_tag",
                                          self.EXPECTED_TOPIC,
                                          expected_message)

    def test_push_update_single_branch(self) -> None:
        expected_message = """hypro999 pushed to branch master. Head is now \
e68c981ef53dbab0a5ca320a2d8d80e216c70528"""
        expected_topic = self.EXPECTED_TOPIC_BRANCH_EVENTS.format(branch="master")
        self.send_and_test_stream_message("repo_push_update_single_branch",
                                          expected_topic,
                                          expected_message)

    def test_push_update_multiple_branches(self) -> None:
        expected_message_first = """hypro999 pushed to branch branch1. Head is now \
3980c2be32a7e23c795741d5dc1a2eecb9b85d6d"""
        expected_message_second = """hypro999 pushed to branch master. Head is now \
fc43d13cff1abb28631196944ba4fc4ad06a2cf2"""
        self.send_and_test_stream_message("repo_push_update_multiple_branches")

        msg = self.get_last_message()
        self.do_test_topic(msg, self.EXPECTED_TOPIC_BRANCH_EVENTS.format(branch="master"))
        self.do_test_message(msg, expected_message_second)

        msg = self.get_second_to_last_message()
        self.do_test_topic(msg, self.EXPECTED_TOPIC_BRANCH_EVENTS.format(branch="branch1"))
        self.do_test_message(msg, expected_message_first)

    def test_push_update_multiple_branches_with_branch_filter(self) -> None:
        self.url = self.build_webhook_url(branches='master')
        expected_message = """hypro999 pushed to branch master. Head is now \
fc43d13cff1abb28631196944ba4fc4ad06a2cf2"""
        expected_topic = self.EXPECTED_TOPIC_BRANCH_EVENTS.format(branch="master")
        self.send_and_test_stream_message("repo_push_update_multiple_branches",
                                          expected_topic,
                                          expected_message)

        self.url = self.build_webhook_url(branches='branch1')
        expected_message = """hypro999 pushed to branch branch1. Head is now \
3980c2be32a7e23c795741d5dc1a2eecb9b85d6d"""
        expected_topic = self.EXPECTED_TOPIC_BRANCH_EVENTS.format(branch="branch1")
        self.send_and_test_stream_message("repo_push_update_multiple_branches",
                                          expected_topic,
                                          expected_message)
