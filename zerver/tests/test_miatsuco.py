import re

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.upload import upload_message_attachment

# Tests for MiAtSu.Co fork-specific features, kept in their own file
# rather than being added directly to Zulip's own test files, so
# that upstream can freely reorganize its own test files across
# releases without our tests ever needing to be touched during a
# rebase. See docs/contributing/miatsuco-fork-conventions.md for the
# naming and architecture conventions this fork follows.
#
# This file is deliberately created here, in the fork's foundational
# patch, rather than by whichever feature patch happens to need it
# first: every feature patch that needs a test class here depends on
# this file already existing (i.e. on this patch), not on each other.
# Each such patch should append its own test class independently,
# reusing MiatsucoMarkdownTestMixin below rather than duplicating its
# helper methods.
#
# In particular, add new imports to a feature patch's *own* test
# class body/methods rather than to this shared import block if at
# all avoidable: two independent feature patches both editing this
# same top-of-file block is exactly the kind of shared-line collision
# that can fail to apply depending on which patch lands first. The
# upload_file_and_get_path_id() helper below exists specifically so
# that the common "upload a file, then derive its path_id" pattern
# doesn't require every feature patch to import re and
# upload_message_attachment itself.


class MiatsucoMarkdownTestMixin(ZulipTestCase):
    def assert_message_content_is(
        self, message_id: int, rendered_content: str, user_name: str = "othello"
    ) -> None:
        sender_user_profile = self.example_user(user_name)
        result = self.assert_json_success(
            self.api_get(sender_user_profile, f"/api/v1/messages/{message_id}")
        )
        self.assertEqual(result["message"]["content"], rendered_content)

    def send_message_content(self, content: str, user_name: str = "othello") -> int:
        sender_user_profile = self.example_user(user_name)
        return self.send_stream_message(
            sender=sender_user_profile,
            stream_name="Verona",
            content=content,
        )

    def upload_file_and_get_path_id(
        self, filename: str, content_type: str, contents: bytes = b"", user_name: str = "othello"
    ) -> tuple[str, str]:
        url = upload_message_attachment(
            filename,
            content_type,
            contents,
            self.example_user(user_name),
        )[0]
        path_id = re.sub(r"/user_uploads/", "", url)
        return url, path_id
