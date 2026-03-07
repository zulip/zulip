from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.streams import ensure_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Stream, Subscription
from zerver.models.realms import get_realm


class TestMeetingStreamCreation(ZulipTestCase):
    """
    Test suite to demonstrate how to create a private channel (stream) 
    and invite a series of specific users to it.
    """

    def test_create_meeting_stream_and_invite_users(self) -> None:
        # 1. Setup basic data
        realm = get_realm("zulip")
        organizer = self.example_user("hamlet")  # The person organizing the meeting
        
        # Define the participants we want to invite
        participants = [
            self.example_user("cordelia"),
            self.example_user("othello"),
            self.example_user("iago"),
        ]
        
        stream_name = "Meeting: Project X Sync"
        
        # 2. Create the private stream (invite_only=True)
        # ensure_stream will create it if it doesn't exist, or return existing.
        stream = ensure_stream(
            realm, 
            stream_name, 
            invite_only=True, 
            acting_user=organizer
        )
        
        # 3. Add all participants to the stream
        # This function handles database records and real-time event notifications.
        # It's recommended to include the organizer in the list as well if they 
        # aren't already subscribed.
        users_to_subscribe = participants + [organizer]
        
        # bulk_add_subscriptions returns a tuple: (newly_subscribed, already_subscribed)
        subscribed, already = bulk_add_subscriptions(
            realm, 
            [stream], 
            users_to_subscribe, 
            acting_user=organizer
        )
        
        # 4. Verifications
        # Check the stream was created correctly
        self.assertTrue(Stream.objects.filter(name=stream_name, realm=realm).exists())
        self.assertTrue(stream.invite_only)
        
        # Check all participants are now subscribed
        for user in users_to_subscribe:
            self.assertTrue(
                Subscription.objects.filter(
                    user_profile=user, 
                    recipient=stream.recipient, 
                    active=True
                ).exists(),
                f"User {user.full_name} should be subscribed to {stream_name}"
            )
            
        print(f"Successfully created stream '{stream_name}' and added {len(users_to_subscribe)} users.")

    def test_idempotency_of_subscription(self) -> None:
        """
        Verify that calling bulk_add_subscriptions multiple times doesn't cause errors.
        """
        realm = get_realm("zulip")
        organizer = self.example_user("hamlet")
        participant = self.example_user("cordelia")
        stream = ensure_stream(realm, "Idempotent Stream", invite_only=True, acting_user=organizer)
        
        # First call
        bulk_add_subscriptions(realm, [stream], [participant], acting_user=organizer)
        
        # Second call with the same user
        subscribed, already = bulk_add_subscriptions(realm, [stream], [participant], acting_user=organizer)
        
        # Verify that 'already' contains the participant and 'subscribed' is empty
        self.assertEqual(len(subscribed), 0)
        self.assertEqual(already[0].user.id, participant.id)
