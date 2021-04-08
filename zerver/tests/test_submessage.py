from typing import Any, Dict, List, Mapping, Set
from unittest import mock

from zerver.lib.actions import do_change_stream_invite_only, do_change_stream_web_public
from zerver.lib.message import MessageDict
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import tornado_redirected_to_list
from zerver.models import Message, SubMessage


class TestBasics(ZulipTestCase):
    def test_get_raw_db_rows(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        stream_name = "Verona"

        message_id = self.send_stream_message(
            sender=cordelia,
            stream_name=stream_name,
        )

        def get_raw_rows() -> List[Dict[str, Any]]:
            query = SubMessage.get_raw_db_rows([message_id])
            rows = list(query)
            return rows

        rows = get_raw_rows()
        self.assertEqual(rows, [])

        sm1 = SubMessage.objects.create(
            msg_type="whatever",
            content="stuff1",
            message_id=message_id,
            sender=cordelia,
        )

        sm2 = SubMessage.objects.create(
            msg_type="whatever",
            content="stuff2",
            message_id=message_id,
            sender=hamlet,
        )

        expected_data = [
            dict(
                id=sm1.id,
                message_id=message_id,
                sender_id=cordelia.id,
                msg_type="whatever",
                content="stuff1",
            ),
            dict(
                id=sm2.id,
                message_id=message_id,
                sender_id=hamlet.id,
                msg_type="whatever",
                content="stuff2",
            ),
        ]

        self.assertEqual(get_raw_rows(), expected_data)

        message = Message.objects.get(id=message_id)
        message_json = MessageDict.wide_dict(message)
        rows = message_json["submessages"]
        rows.sort(key=lambda r: r["id"])
        self.assertEqual(rows, expected_data)

        msg_rows = MessageDict.get_raw_db_rows([message_id])
        rows = msg_rows[0]["submessages"]
        rows.sort(key=lambda r: r["id"])
        self.assertEqual(rows, expected_data)

    def test_event_receivers(self) -> None:
        def test_add_submessage_event(message_id: int, exp_receivers: Set[int]) -> None:
            payload = dict(
                message_id=message_id,
                msg_type="whatever",
                content='{"sample": "JSON"}',
            )

            events: List[Mapping[str, Any]] = []
            with tornado_redirected_to_list(events):
                result = self.client_post("/json/submessage", payload)

            self.assert_json_success(result)
            self.assert_length(events, 1)
            event = events[0]["event"]
            self.assertEqual(event["type"], "submessage")
            self.assertEqual(exp_receivers, {usr for usr in events[0]["users"]})

        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        polonius = self.example_user("polonius")

        # Test `invite_only` streams with `!history_public_to_subscribers` and `!is_web_public`
        stream = self.make_stream(
            "test_submessage_stream", invite_only=True, history_public_to_subscribers=False
        )
        self.subscribe(iago, stream.name)
        message_id = self.send_stream_message(iago, "test_submessage_stream", "before subscription")
        self.subscribe(hamlet, stream.name)
        self.subscribe(polonius, stream.name)
        self.login_user(iago)
        # Hamlet and Polonius joined after the message was sent, and
        # so only Iago should receive the event.
        test_add_submessage_event(message_id, {iago.id})

        # Make stream history public to subscribers
        do_change_stream_invite_only(stream, False, history_public_to_subscribers=True)
        test_add_submessage_event(message_id, {iago.id, hamlet.id})

        # Make stream web_public as well.
        do_change_stream_web_public(stream, True)
        test_add_submessage_event(message_id, {iago.id, hamlet.id, polonius.id})

    def test_endpoint_errors(self) -> None:
        cordelia = self.example_user("cordelia")
        stream_name = "Verona"
        message_id = self.send_stream_message(
            sender=cordelia,
            stream_name=stream_name,
        )
        self.login_user(cordelia)

        payload = dict(
            message_id=message_id,
            msg_type="whatever",
            content="not json",
        )
        result = self.client_post("/json/submessage", payload)
        self.assert_json_error(result, "Invalid json for submessage")

        hamlet = self.example_user("hamlet")
        bad_message_id = self.send_personal_message(
            from_user=hamlet,
            to_user=hamlet,
        )
        payload = dict(
            message_id=bad_message_id,
            msg_type="whatever",
            content="does not matter",
        )
        result = self.client_post("/json/submessage", payload)
        self.assert_json_error(result, "Invalid message(s)")

    def test_endpoint_success(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        stream_name = "Verona"
        message_id = self.send_stream_message(
            sender=cordelia,
            stream_name=stream_name,
        )
        self.login_user(cordelia)

        payload = dict(
            message_id=message_id,
            msg_type="whatever",
            content='{"name": "alice", "salary": 20}',
        )
        with mock.patch("zerver.lib.actions.send_event") as m:
            result = self.client_post("/json/submessage", payload)
        self.assert_json_success(result)

        submessage = SubMessage.objects.get(message_id=message_id)

        expected_data = dict(
            message_id=message_id,
            submessage_id=submessage.id,
            content=payload["content"],
            msg_type="whatever",
            sender_id=cordelia.id,
            type="submessage",
        )

        self.assertEqual(m.call_count, 1)
        data = m.call_args[0][1]
        self.assertEqual(data, expected_data)
        users = m.call_args[0][2]
        self.assertIn(cordelia.id, users)
        self.assertIn(hamlet.id, users)

        rows = SubMessage.get_raw_db_rows([message_id])
        self.assertEqual(len(rows), 1)
        row = rows[0]

        expected_data = dict(
            id=row["id"],
            message_id=message_id,
            content='{"name": "alice", "salary": 20}',
            msg_type="whatever",
            sender_id=cordelia.id,
        )
        self.assertEqual(row, expected_data)
