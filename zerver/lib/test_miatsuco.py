# nocoverage
#
# The bare "# nocoverage" line above excludes this whole module from
# backend coverage enforcement (see tools/coveragerc). This module
# provides shared test *support* (a helper mixin), not tests of its
# own. Its methods are exercised by each feature's test module
# (zerver/tests/test_miatsuco_<feature>.py) once those land, not by
# this file directly, so on a baseline that ships ahead of any feature
# it has no coverage of its own. Upstream marks comparable helper code
# in zerver/lib/test_classes.py and test_helpers.py the same way. When
# feature tests that call every helper here are present, this marker
# can be removed so the helpers are held to real coverage through their
# callers.
import re

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.upload import upload_message_attachment

# Shared test support for MiAtSu.Co fork-specific features.
#
# This lives in zerver/lib/ (not zerver/tests/) on purpose, following
# upstream Zulip's own convention of keeping reusable test base
# classes in zerver/lib/test_classes.py rather than in the test
# modules themselves. The backend test runner only discovers modules
# under zerver/tests/, so a helper module here is never mistaken for a
# test module (upstream keeps test_classes.py, test_helpers.py, and
# others here for the same reason).
#
# Each fork feature gets its own test module named for that feature,
# zerver/tests/test_miatsuco_<feature>.py, and imports
# MiatsucoMarkdownTestMixin from here. This is deliberate: because no
# two feature branches ever edit the same file, each feature's tests
# apply cleanly and independently, in any order, with no merge
# conflict between them -- which matters both for this fork's own
# stacked feature patches and for anyone developing a feature branch
# independently. Adding a new feature's tests never requires touching
# this file or any other feature's test file.
#
# The upload_file_and_get_path_id() helper below exists so the common
# "upload a file, then derive its path_id" pattern doesn't require
# every feature's test module to re-import re and
# upload_message_attachment. If a feature needs a new shared helper,
# add it here; if a helper is specific to one feature, keep it in that
# feature's own test module.
#
# See docs/contributing/miatsuco-fork-conventions.md for the full
# rationale.


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
