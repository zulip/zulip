from zerver.actions.streams import bulk_add_subscriptions, get_subscriber_ids
from zerver.lib.streams import ensure_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zerver.models.realms import get_realm

class TestMeetingUserLists(ZulipTestCase):
    """
    Test suite to demonstrate fetching and printing users at both 
    the Realm (Organization) and Stream (Channel) levels.
    """

    def test_print_realm_and_channel_users(self) -> None:
        realm = get_realm("zulip")
        organizer = self.example_user("hamlet")
        
        # 1. Fetch and print all active human users in the Organization (Realm)
        # -------------------------------------------------------------------
        all_realm_users = UserProfile.objects.filter(
            realm=realm, 
            is_active=True, 
            is_bot=False
        ).order_by("full_name")
        
        print("" + "="*50)
        print(f"ORGANIZATION USERS (Realm: {realm.string_id})")
        print("="*50)
        for user in all_realm_users:
            print(f"- {user.full_name} ({user.email}) [ID: {user.id}]")
        print(f"Total realm users: {len(all_realm_users)}")

        # 2. Ensure a channel exists and subscribe some users
        # -------------------------------------------------------------------
        stream_name = "Meeting Room A"
        stream = ensure_stream(realm, stream_name, invite_only=True, acting_user=organizer)
        
        # Subscribe Hamlet (organizer) and Cordelia if not already there
        participants = [organizer, self.example_user("cordelia")]
        bulk_add_subscriptions(realm, [stream], participants, acting_user=organizer)

        # 3. Fetch and print all users in the specific Channel (Stream)
        # -------------------------------------------------------------------
        # We use get_subscriber_ids to get the IDs, then fetch the objects
        # We must pass a requesting_user because it is a private stream.
        subscriber_ids = get_subscriber_ids(stream, requesting_user=organizer)
        channel_users = UserProfile.objects.filter(id__in=subscriber_ids).order_by("full_name")

        print("" + "="*50)
        print(f"CHANNEL USERS (Stream: {stream_name})")
        print("="*50)
        for user in channel_users:
            print(f"- {user.full_name} ({user.email}) [ID: {user.id}]")
        print(f"Total channel users: {len(channel_users)}")
        print("="*50 + "")

        # Basic assertions to ensure the test passes
        self.assertIn(organizer.id, subscriber_ids)
        self.assertGreaterEqual(len(all_realm_users), len(channel_users))
