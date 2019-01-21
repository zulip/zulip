import ujson

from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.test_helpers import (
    EventInfo,
    capture_event,
)
from zerver.lib.user_status import (
    get_away_user_ids,
    update_user_status,
)

from zerver.models import (
    get_client,
    UserStatus,
)

from typing import Any, Dict

class UserStatusTest(ZulipTestCase):
    def test_basics(self) -> None:
        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')
        king_lear = self.lear_user('king')

        realm_id = hamlet.realm_id

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, set())

        client1 = get_client('web')
        client2 = get_client('ZT')

        update_user_status(
            user_profile_id=hamlet.id,
            status=UserStatus.AWAY,
            client_id=client1.id,
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, {hamlet.id})

        # Test that second client just updates
        # the record.  We only store one record
        # per user.  The user's status transcends
        # clients; we only store the client for
        # reference and to maybe reconcile timeout
        # situations.
        update_user_status(
            user_profile_id=hamlet.id,
            status=UserStatus.AWAY,
            client_id=client2.id,
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, {hamlet.id})

        rec_count = UserStatus.objects.filter(user_profile_id=hamlet.id).count()
        self.assertEqual(rec_count, 1)

        update_user_status(
            user_profile_id=hamlet.id,
            status=UserStatus.NORMAL,
            client_id=client2.id,
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, set())

        # Now set away status for three different users across
        # two realms.
        update_user_status(
            user_profile_id=hamlet.id,
            status=UserStatus.AWAY,
            client_id=client1.id,
        )
        update_user_status(
            user_profile_id=cordelia.id,
            status=UserStatus.AWAY,
            client_id=client2.id,
        )
        update_user_status(
            user_profile_id=king_lear.id,
            status=UserStatus.AWAY,
            client_id=client2.id,
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, {cordelia.id, hamlet.id})

        away_user_ids = get_away_user_ids(realm_id=king_lear.realm.id)
        self.assertEqual(away_user_ids, {king_lear.id})

        # Revoke Hamlet again.
        update_user_status(
            user_profile_id=hamlet.id,
            status=UserStatus.NORMAL,
            client_id=client2.id,
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, {cordelia.id})

    def test_endpoints(self) -> None:
        hamlet = self.example_user('hamlet')
        realm_id = hamlet.realm_id

        self.login(hamlet.email)

        # Try to omit parameter--this should be an error.
        payload = dict()  # type: Dict[str, Any]
        result = self.client_post('/json/users/me/status', payload)
        self.assert_json_error(result, "Missing 'away' argument")

        # Set the "away" status.
        payload = dict(away=ujson.dumps(True))

        event_info = EventInfo()
        with capture_event(event_info):
            result = self.client_post('/json/users/me/status', payload)
        self.assert_json_success(result)

        self.assertEqual(
            event_info.payload,
            dict(type='user_status', user_id=hamlet.id, away=True),
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, {hamlet.id})

        # Now revoke "away" status.
        payload = dict(away=ujson.dumps(False))

        event_info = EventInfo()
        with capture_event(event_info):
            result = self.client_post('/json/users/me/status', payload)
        self.assert_json_success(result)

        self.assertEqual(
            event_info.payload,
            dict(type='user_status', user_id=hamlet.id, away=False),
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, set())
