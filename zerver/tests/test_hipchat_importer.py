from zerver.data_import.hipchat import (
    get_hipchat_sender_id,
)
from zerver.data_import.hipchat_user import (
    UserHandler,
)
from zerver.data_import.sequencer import (
    IdMapper,
)

from zerver.lib.test_classes import (
    ZulipTestCase,
)
from typing import Any, Dict


class HipChatImporter(ZulipTestCase):
    def test_sender_ids(self) -> None:
        realm_id = 5
        user_handler = UserHandler()

        user_id_mapper = IdMapper()
        user_id_mapper.has = lambda key: True  # type: ignore # it's just a stub

        # Simulate a "normal" user first.
        user_with_id = dict(
            id=1,
            # other fields don't matter here
        )
        user_handler.add_user(user=user_with_id)

        normal_message = dict(
            sender=dict(
                id=1,
            )
        )  # type: Dict[str, Any]

        sender_id = get_hipchat_sender_id(
            realm_id=realm_id,
            slim_mode=False,
            message_dict=normal_message,
            user_id_mapper=user_id_mapper,
            user_handler=user_handler,
        )

        self.assertEqual(sender_id, 1)

        bot_message = dict(
            sender='fred_bot',
        )

        # Every message from fred_bot should
        # return the same sender_id.
        fred_bot_sender_id = 2

        for i in range(3):
            sender_id = get_hipchat_sender_id(
                realm_id=realm_id,
                slim_mode=False,
                message_dict=bot_message,
                user_id_mapper=user_id_mapper,
                user_handler=user_handler,
            )

            self.assertEqual(sender_id, fred_bot_sender_id)

        id_zero_message = dict(
            sender=dict(
                id=0,
                name='hal_bot',
            ),
        )

        hal_bot_sender_id = 3
        for i in range(3):
            sender_id = get_hipchat_sender_id(
                realm_id=realm_id,
                slim_mode=False,
                message_dict=id_zero_message,
                user_id_mapper=user_id_mapper,
                user_handler=user_handler,
            )

            self.assertEqual(sender_id, hal_bot_sender_id)
