from zerver.lib.test_classes import ZulipTestCase

from zerver.models import (
    SubMessage,
)

from typing import Any, Dict, List

class TestBasics(ZulipTestCase):
    def test_get_raw_db_rows(self) -> None:
        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')
        stream_name = 'Verona'

        message_id = self.send_stream_message(
            sender_email=cordelia.email,
            stream_name=stream_name,
        )

        def get_raw_rows() -> List[Dict[str, Any]]:
            query = SubMessage.get_raw_db_rows([message_id])
            rows = list(query)
            return rows

        rows = get_raw_rows()
        self.assertEqual(rows, [])

        sm1 = SubMessage.objects.create(
            msg_type='whatever',
            content='stuff1',
            message_id=message_id,
            sender=cordelia,
        )

        sm2 = SubMessage.objects.create(
            msg_type='whatever',
            content='stuff2',
            message_id=message_id,
            sender=hamlet,
        )

        expected_data = [
            dict(
                id=sm1.id,
                message_id=message_id,
                sender_id=cordelia.id,
                msg_type='whatever',
                content='stuff1',
            ),
            dict(
                id=sm2.id,
                message_id=message_id,
                sender_id=hamlet.id,
                msg_type='whatever',
                content='stuff2',
            ),
        ]

        self.assertEqual(get_raw_rows(), expected_data)
