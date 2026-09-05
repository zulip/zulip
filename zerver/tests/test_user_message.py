from unittest import TestCase, mock

from zerver.lib.user_message import UserMessageLite, bulk_insert_ums


class BulkInsertUserMessageTests(TestCase):
    def test_bulk_insert_ums_sorts_by_message_id(self) -> None:
        ums = [
            UserMessageLite(user_profile_id=1, message_id=5, flags=1),
            UserMessageLite(user_profile_id=2, message_id=3, flags=2),
            UserMessageLite(user_profile_id=3, message_id=4, flags=3),
            UserMessageLite(user_profile_id=4, message_id=3, flags=4),
        ]

        with (
            mock.patch("zerver.lib.user_message.execute_values") as mock_execute_values,
            mock.patch("zerver.lib.user_message.connection.cursor") as mock_cursor,
        ):
            mock_cursor.return_value.__enter__.return_value.cursor = mock.MagicMock()

            bulk_insert_ums(ums)

        mock_execute_values.assert_called_once()
        self.assertEqual(
            mock_execute_values.call_args.args[2],
            [
                (2, 3, 2),
                (4, 3, 4),
                (3, 4, 3),
                (1, 5, 1),
            ],
        )
