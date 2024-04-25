import time
from copy import deepcopy
from typing import Any, Dict, List, Optional

import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Draft


class DraftCreationTests(ZulipTestCase):
    def create_and_check_drafts_for_success(
        self,
        draft_dicts: List[Dict[str, Any]],
        expected_draft_dicts: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Now send a POST request to the API endpoint.
        payload = {"drafts": orjson.dumps(draft_dicts).decode()}
        resp = self.api_post(hamlet, "/api/v1/drafts", payload)
        self.assert_json_success(resp)

        # Finally check to make sure that the drafts were actually created properly.
        new_draft_dicts = []
        for draft in Draft.objects.filter(user_profile=hamlet).order_by("last_edit_time"):
            draft_dict = draft.to_dict()
            draft_dict.pop("id")
            new_draft_dicts.append(draft_dict)
        if expected_draft_dicts is None:
            expected_draft_dicts = draft_dicts
        self.assertEqual(new_draft_dicts, expected_draft_dicts)

    def create_and_check_drafts_for_error(
        self, draft_dicts: List[Dict[str, Any]], expected_message: str
    ) -> None:
        hamlet = self.example_user("hamlet")

        initial_count = Draft.objects.count()

        # Now send a POST request to the API endpoint.
        payload = {"drafts": orjson.dumps(draft_dicts).decode()}
        resp = self.api_post(hamlet, "/api/v1/drafts", payload)
        self.assert_json_error(resp, expected_message)

        # Make sure that there are no drafts in the database at the
        # end of the test. Drafts should never be created in error
        # conditions.
        self.assertEqual(Draft.objects.count(), initial_count)

    def test_require_enable_drafts_synchronization(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet.enable_drafts_synchronization = False
        hamlet.save()
        payload = {"drafts": "[]"}
        resp = self.api_post(hamlet, "/api/v1/drafts", payload)
        self.assert_json_error(resp, "User has disabled synchronizing drafts.")

    def test_create_one_stream_draft_properly(self) -> None:
        hamlet = self.example_user("hamlet")
        visible_stream_name = self.get_streams(hamlet)[0]
        visible_stream_id = self.get_stream_id(visible_stream_name)
        draft_dicts = [
            {
                "type": "stream",
                "to": [visible_stream_id],
                "topic": "sync drafts",
                "content": "Let's add backend support for syncing drafts.",
                "timestamp": 1595479019,
            }
        ]
        self.create_and_check_drafts_for_success(draft_dicts)

    def test_create_one_personal_message_draft_properly(self) -> None:
        zoe = self.example_user("ZOE")
        draft_dicts = [
            {
                "type": "private",
                "to": [zoe.id],
                "topic": "This topic should be ignored.",
                "content": "What if we made it possible to sync drafts in Zulip?",
                "timestamp": 1595479019,
            }
        ]
        # For direct messages, the topic should be ignored.
        expected_draft_dicts = [
            {
                "type": "private",
                "to": [zoe.id],
                "topic": "",
                "content": "What if we made it possible to sync drafts in Zulip?",
                "timestamp": 1595479019,
            }
        ]
        self.create_and_check_drafts_for_success(draft_dicts, expected_draft_dicts)

    def test_create_one_group_personal_message_draft_properly(self) -> None:
        zoe = self.example_user("ZOE")
        othello = self.example_user("othello")
        draft_dicts = [
            {
                "type": "private",
                "to": [zoe.id, othello.id],
                "topic": "This topic should be ignored.",
                "content": "What if we made it possible to sync drafts in Zulip?",
                "timestamp": 1595479019,
            }
        ]
        # For direct messages, the topic should be ignored.
        expected_draft_dicts = [
            {
                "type": "private",
                "to": [zoe.id, othello.id],
                "topic": "",
                "content": "What if we made it possible to sync drafts in Zulip?",
                "timestamp": 1595479019,
            }
        ]
        self.create_and_check_drafts_for_success(draft_dicts, expected_draft_dicts)

    def test_create_batch_of_drafts_properly(self) -> None:
        hamlet = self.example_user("hamlet")
        visible_stream_name = self.get_streams(hamlet)[0]
        visible_stream_id = self.get_stream_id(visible_stream_name)
        zoe = self.example_user("ZOE")
        othello = self.example_user("othello")
        draft_dicts = [
            {
                "type": "stream",
                "to": [visible_stream_id],
                "topic": "sync drafts",
                "content": "Let's add backend support for syncing drafts.",
                "timestamp": 1595479019,
            },
            {
                "type": "private",
                "to": [zoe.id],
                "topic": "",
                "content": "What if we made it possible to sync drafts in Zulip?",
                "timestamp": 1595479020,
            },
            {
                "type": "private",
                "to": [zoe.id, othello.id],
                "topic": "",
                "content": "What if we made it possible to sync drafts in Zulip?",
                "timestamp": 1595479021,
            },
        ]
        self.create_and_check_drafts_for_success(draft_dicts)

    def test_missing_timestamps(self) -> None:
        """If a timestamp is not provided for a draft dict then it should be automatically
        filled in."""
        hamlet = self.example_user("hamlet")
        visible_stream_name = self.get_streams(hamlet)[0]
        visible_stream_id = self.get_stream_id(visible_stream_name)

        draft_dicts = [
            {
                "type": "stream",
                "to": [visible_stream_id],
                "topic": "sync drafts",
                "content": "Let's add backend support for syncing drafts.",
            }
        ]

        initial_count = Draft.objects.count()

        current_time = int(time.time())
        payload = {"drafts": orjson.dumps(draft_dicts).decode()}
        resp = self.api_post(hamlet, "/api/v1/drafts", payload)
        ids = orjson.loads(resp.content)["ids"]
        self.assert_json_success(resp)

        new_drafts = Draft.objects.filter(id__gte=ids[0])
        self.assertEqual(Draft.objects.count() - initial_count, 1)
        new_draft = new_drafts[0].to_dict()
        self.assertTrue(isinstance(new_draft["timestamp"], int))
        # Since it would be too tricky to get the same times, perform
        # a relative check.
        self.assertTrue(new_draft["timestamp"] >= current_time)

    def test_invalid_timestamp(self) -> None:
        draft_dicts = [
            {
                "type": "stream",
                "to": [],
                "topic": "sync drafts",
                "content": "Let's add backend support for syncing drafts.",
                "timestamp": -10.10,
            }
        ]
        self.create_and_check_drafts_for_error(draft_dicts, "Timestamp must not be negative.")

    def test_create_non_stream_draft_with_no_recipient(self) -> None:
        """When "to" is an empty list, the type should become "" as well."""
        draft_dicts = [
            {
                "type": "private",
                "to": [],
                "topic": "sync drafts",
                "content": "Let's add backend support for syncing drafts.",
                "timestamp": 1595479019,
            },
            {
                "type": "",
                "to": [],
                "topic": "sync drafts",
                "content": "Let's add backend support for syncing drafts.",
                "timestamp": 1595479019,
            },
        ]
        expected_draft_dicts = [
            {
                "type": "",
                "to": [],
                "topic": "",
                "content": "Let's add backend support for syncing drafts.",
                "timestamp": 1595479019,
            },
            {
                "type": "",
                "to": [],
                "topic": "",
                "content": "Let's add backend support for syncing drafts.",
                "timestamp": 1595479019,
            },
        ]
        self.create_and_check_drafts_for_success(draft_dicts, expected_draft_dicts)

    def test_create_stream_draft_with_no_recipient(self) -> None:
        draft_dicts = [
            {
                "type": "stream",
                "to": [],
                "topic": "sync drafts",
                "content": "Let's add backend support for syncing drafts.",
                "timestamp": 15954790199,
            }
        ]
        self.create_and_check_drafts_for_error(
            draft_dicts, "Must specify exactly 1 channel ID for channel messages"
        )

    def test_create_stream_draft_for_inaccessible_stream(self) -> None:
        # When the user does not have permission to access the stream:
        stream = self.make_stream("Secret Society", invite_only=True)
        draft_dicts = [
            {
                "type": "stream",
                "to": [stream.id],  # This can't be accessed by hamlet.
                "topic": "sync drafts",
                "content": "Let's add backend support for syncing drafts.",
                "timestamp": 1595479019,
            }
        ]
        self.create_and_check_drafts_for_error(draft_dicts, "Invalid channel ID")

        # When the stream itself does not exist:
        draft_dicts = [
            {
                "type": "stream",
                "to": [99999999999999],  # Hopefully, this doesn't exist.
                "topic": "sync drafts",
                "content": "Let's add backend support for syncing drafts.",
                "timestamp": 1595479019,
            }
        ]
        self.create_and_check_drafts_for_error(draft_dicts, "Invalid channel ID")

    def test_create_personal_message_draft_for_non_existing_user(self) -> None:
        draft_dicts = [
            {
                "type": "private",
                "to": [99999999999999],  # Hopefully, this doesn't exist either.
                "topic": "This topic should be ignored.",
                "content": "What if we made it possible to sync drafts in Zulip?",
                "timestamp": 1595479019,
            }
        ]
        self.create_and_check_drafts_for_error(draft_dicts, "Invalid user ID 99999999999999")

    def test_create_draft_with_null_bytes(self) -> None:
        draft_dicts = [
            {
                "type": "",
                "to": [],
                "topic": "sync drafts.",
                "content": "Some regular \x00 content here",
                "timestamp": 15954790199,
            }
        ]
        self.create_and_check_drafts_for_error(draft_dicts, "Message must not contain null bytes")

        draft_dicts = [
            {
                "type": "stream",
                "to": [10],
                "topic": "thinking about \x00",
                "content": "Let's add backend support for syncing drafts.",
                "timestamp": 15954790199,
            }
        ]
        self.create_and_check_drafts_for_error(draft_dicts, "Topic must not contain null bytes")


class DraftEditTests(ZulipTestCase):
    def test_require_enable_drafts_synchronization(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet.enable_drafts_synchronization = False
        hamlet.save()
        resp = self.api_patch(hamlet, "/api/v1/drafts/1", {"draft": {}})
        self.assert_json_error(resp, "User has disabled synchronizing drafts.")

    def test_edit_draft_successfully(self) -> None:
        hamlet = self.example_user("hamlet")
        visible_streams = self.get_streams(hamlet)
        stream_a = self.get_stream_id(visible_streams[0])
        stream_b = self.get_stream_id(visible_streams[1])

        # Create a draft.
        draft_dict = {
            "type": "stream",
            "to": [stream_a],
            "topic": "drafts",
            "content": "The API should be good",
            "timestamp": 1595505700,
        }
        resp = self.api_post(
            hamlet, "/api/v1/drafts", {"drafts": orjson.dumps([draft_dict]).decode()}
        )
        self.assert_json_success(resp)
        new_draft_id = orjson.loads(resp.content)["ids"][0]

        # Change the draft data.
        draft_dict["content"] = "The API needs to be structured yet simple to use."
        draft_dict["to"] = [stream_b]
        draft_dict["topic"] = "designing drafts"
        draft_dict["timestamp"] = 1595505800

        # Update this change in the backend.
        resp = self.api_patch(
            hamlet, f"/api/v1/drafts/{new_draft_id}", {"draft": orjson.dumps(draft_dict).decode()}
        )
        self.assert_json_success(resp)

        # Now make sure that the change was made successfully.
        new_draft = Draft.objects.get(id=new_draft_id, user_profile=hamlet)
        new_draft_dict = new_draft.to_dict()
        new_draft_dict.pop("id")
        self.assertEqual(new_draft_dict, draft_dict)

    def test_edit_non_existent_draft(self) -> None:
        hamlet = self.example_user("hamlet")

        initial_count = Draft.objects.count()

        # Try to update a draft that doesn't exist.
        draft_dict = {
            "type": "stream",
            "to": [10],
            "topic": "drafts",
            "content": "The API should be good",
            "timestamp": 1595505700,
        }
        resp = self.api_patch(
            hamlet, "/api/v1/drafts/999999999", {"draft": orjson.dumps(draft_dict).decode()}
        )
        self.assert_json_error(resp, "Draft does not exist", status_code=404)

        # Now make sure that no changes were made.
        self.assertEqual(Draft.objects.count() - initial_count, 0)

    def test_edit_unowned_draft(self) -> None:
        hamlet = self.example_user("hamlet")
        visible_streams = self.get_streams(hamlet)
        stream_id = self.get_stream_id(visible_streams[0])

        # Create a draft.
        draft_dict = {
            "type": "stream",
            "to": [stream_id],
            "topic": "drafts",
            "content": "The API should be good",
            "timestamp": 1595505700,
        }
        resp = self.api_post(
            hamlet, "/api/v1/drafts", {"drafts": orjson.dumps([draft_dict]).decode()}
        )
        self.assert_json_success(resp)
        new_draft_id = orjson.loads(resp.content)["ids"][0]

        # Change the draft data.
        modified_draft_dict = deepcopy(draft_dict)
        modified_draft_dict["content"] = "???"

        # Update this change in the backend as a different user.
        zoe = self.example_user("ZOE")
        resp = self.api_patch(
            zoe, f"/api/v1/drafts/{new_draft_id}", {"draft": orjson.dumps(draft_dict).decode()}
        )
        self.assert_json_error(resp, "Draft does not exist", status_code=404)

        # Now make sure that no changes were made.
        existing_draft = Draft.objects.get(id=new_draft_id, user_profile=hamlet)
        existing_draft_dict = existing_draft.to_dict()
        existing_draft_dict.pop("id")
        self.assertEqual(existing_draft_dict, draft_dict)


class DraftDeleteTests(ZulipTestCase):
    def test_require_enable_drafts_synchronization(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet.enable_drafts_synchronization = False
        hamlet.save()
        resp = self.api_delete(hamlet, "/api/v1/drafts/1")
        self.assert_json_error(resp, "User has disabled synchronizing drafts.")

    def test_delete_draft_successfully(self) -> None:
        hamlet = self.example_user("hamlet")
        visible_streams = self.get_streams(hamlet)
        stream_id = self.get_stream_id(visible_streams[0])

        # Make sure that there are no drafts at the start of this test.
        initial_count = Draft.objects.count()

        # Create a draft.
        draft_dict = {
            "type": "stream",
            "to": [stream_id],
            "topic": "drafts",
            "content": "The API should be good",
            "timestamp": 1595505700,
        }
        resp = self.api_post(
            hamlet, "/api/v1/drafts", {"drafts": orjson.dumps([draft_dict]).decode()}
        )
        self.assert_json_success(resp)
        new_draft_id = orjson.loads(resp.content)["ids"][0]

        # Make sure that exactly 1 draft exists now.
        self.assertEqual(Draft.objects.count() - initial_count, 1)

        # Update this change in the backend.
        resp = self.api_delete(hamlet, f"/api/v1/drafts/{new_draft_id}")
        self.assert_json_success(resp)

        # Now make sure that the there are no more drafts.
        self.assertEqual(Draft.objects.count() - initial_count, 0)

    def test_delete_non_existent_draft(self) -> None:
        hamlet = self.example_user("hamlet")

        # Make sure that no draft exists in the first place.
        initial_count = Draft.objects.count()

        # Try to delete a draft that doesn't exist.
        resp = self.api_delete(hamlet, "/api/v1/drafts/9999999999")
        self.assert_json_error(resp, "Draft does not exist", status_code=404)

        # Now make sure that no drafts were made for whatever reason.
        self.assertEqual(Draft.objects.count() - initial_count, 0)

    def test_delete_unowned_draft(self) -> None:
        hamlet = self.example_user("hamlet")
        visible_streams = self.get_streams(hamlet)
        stream_id = self.get_stream_id(visible_streams[0])

        # Make sure that there are no drafts at the start of this test.
        initial_count = Draft.objects.count()

        # Create a draft.
        draft_dict = {
            "type": "stream",
            "to": [stream_id],
            "topic": "drafts",
            "content": "The API should be good",
            "timestamp": 1595505700,
        }
        resp = self.api_post(
            hamlet, "/api/v1/drafts", {"drafts": orjson.dumps([draft_dict]).decode()}
        )
        self.assert_json_success(resp)
        new_draft_id = orjson.loads(resp.content)["ids"][0]

        # Delete this draft in the backend as a different user.
        zoe = self.example_user("ZOE")
        resp = self.api_delete(zoe, f"/api/v1/drafts/{new_draft_id}")
        self.assert_json_error(resp, "Draft does not exist", status_code=404)

        # Make sure that the draft was not deleted.
        self.assertEqual(Draft.objects.count() - initial_count, 1)

        # Now make sure that no changes were made either.
        existing_draft = Draft.objects.get(id=new_draft_id, user_profile=hamlet)
        existing_draft_dict = existing_draft.to_dict()
        existing_draft_dict.pop("id")
        self.assertEqual(existing_draft_dict, draft_dict)


class DraftFetchTest(ZulipTestCase):
    def test_require_enable_drafts_synchronization(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet.enable_drafts_synchronization = False
        hamlet.save()
        resp = self.api_get(hamlet, "/api/v1/drafts")
        self.assert_json_error(resp, "User has disabled synchronizing drafts.")

    def test_fetch_drafts(self) -> None:
        initial_count = Draft.objects.count()

        hamlet = self.example_user("hamlet")
        zoe = self.example_user("ZOE")
        othello = self.example_user("othello")
        visible_stream_id = self.get_stream_id(self.get_streams(hamlet)[0])
        draft_dicts = [
            {
                "type": "stream",
                "to": [visible_stream_id],
                "topic": "thinking out loud",
                "content": "What if pigs really could fly?",
                "timestamp": 15954790197,
            },
            {
                "type": "private",
                "to": [zoe.id, othello.id],
                "topic": "",
                "content": "What if made it possible to sync drafts in Zulip?",
                "timestamp": 15954790198,
            },
            {
                "type": "private",
                "to": [zoe.id],
                "topic": "",
                "content": "What if made it possible to sync drafts in Zulip?",
                "timestamp": 15954790199,
            },
        ]
        payload = {"drafts": orjson.dumps(draft_dicts).decode()}
        resp = self.api_post(hamlet, "/api/v1/drafts", payload)
        self.assert_json_success(resp)

        self.assertEqual(Draft.objects.count() - initial_count, 3)

        zoe_draft_dicts = [
            {
                "type": "private",
                "to": [hamlet.id],
                "topic": "",
                "content": "Hello there!",
                "timestamp": 15954790200,
            },
        ]
        payload = {"drafts": orjson.dumps(zoe_draft_dicts).decode()}
        resp = self.api_post(zoe, "/api/v1/drafts", payload)
        self.assert_json_success(resp)

        self.assertEqual(Draft.objects.count() - initial_count, 4)

        # Now actually fetch the drafts. Make sure that hamlet gets only
        # his drafts and exactly as he made them.
        resp = self.api_get(hamlet, "/api/v1/drafts")
        self.assert_json_success(resp)
        data = orjson.loads(resp.content)
        self.assertEqual(data["count"], 3)

        first_draft_id = Draft.objects.filter(user_profile=hamlet).order_by("id")[0].id
        expected_draft_contents: List[Dict[str, object]] = [
            {"id": first_draft_id + i, **draft_dicts[i]} for i in range(3)
        ]

        self.assertEqual(data["drafts"], expected_draft_contents)
