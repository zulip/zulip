from datetime import timedelta
from unittest.mock import patch

from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.whispers import (
    WhisperConversationError,
    WhisperPermissionError,
    WhisperValidationError,
    add_participant_to_whisper,
    cleanup_expired_whisper_requests,
    cleanup_inactive_whisper_conversations,
    create_whisper_conversation,
    get_active_whisper_conversation,
    get_user_whisper_conversations,
    get_whisper_conversation_participants,
    get_whisper_participants_hash,
    has_access_to_recipient,
    is_whisper_participant,
    remove_participant_from_whisper,
    update_whisper_participants_hash,
    validate_whisper_participants,
)
from zerver.models import (
    Recipient,
    Stream,
    Subscription,
    UserProfile,
    WhisperConversation,
    WhisperParticipant,
    WhisperRequest,
    get_realm,
)


class WhisperLibTest(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm("zulip")
        self.user1 = self.example_user("hamlet")
        self.user2 = self.example_user("cordelia")
        self.user3 = self.example_user("othello")
        self.user4 = self.example_user("iago")
        
        # Create a test stream
        self.stream = Stream.objects.create(
            name="test-stream",
            realm=self.realm,
        )
        self.stream_recipient = Recipient.objects.create(
            type=Recipient.STREAM,
            type_id=self.stream.id
        )
        
        # Subscribe users to the stream
        for user in [self.user1, self.user2, self.user3]:
            Subscription.objects.create(
                user_profile=user,
                recipient=self.stream_recipient,
                is_user_active=True
            )

    def test_validate_whisper_participants_success(self) -> None:
        """Test successful participant validation"""
        participant_ids = [self.user2.id, self.user3.id]
        participants = validate_whisper_participants(
            self.user1, participant_ids, self.stream_recipient
        )
        
        self.assertEqual(len(participants), 2)
        self.assertIn(self.user2, participants)
        self.assertIn(self.user3, participants)

    def test_validate_whisper_participants_empty_list(self) -> None:
        """Test validation with empty participant list"""
        with self.assertRaises(WhisperValidationError):
            validate_whisper_participants(self.user1, [], self.stream_recipient)

    def test_validate_whisper_participants_only_self(self) -> None:
        """Test validation when only requesting user is in list"""
        with self.assertRaises(WhisperValidationError):
            validate_whisper_participants(
                self.user1, [self.user1.id], self.stream_recipient
            )

    def test_validate_whisper_participants_no_access(self) -> None:
        """Test validation when participant lacks access to parent conversation"""
        # user4 is not subscribed to the stream
        with self.assertRaises(WhisperPermissionError):
            validate_whisper_participants(
                self.user1, [self.user4.id], self.stream_recipient
            )

    def test_validate_whisper_participants_requesting_user_no_access(self) -> None:
        """Test validation when requesting user lacks access"""
        # Create a stream user1 is not subscribed to
        other_stream = Stream.objects.create(name="other-stream", realm=self.realm)
        other_recipient = Recipient.objects.create(
            type=Recipient.STREAM,
            type_id=other_stream.id
        )
        
        with self.assertRaises(WhisperPermissionError):
            validate_whisper_participants(
                self.user1, [self.user2.id], other_recipient
            )

    def test_has_access_to_recipient_stream(self) -> None:
        """Test stream access checking"""
        # User with subscription should have access
        self.assertTrue(has_access_to_recipient(self.user1, self.stream_recipient))
        
        # User without subscription should not have access
        self.assertFalse(has_access_to_recipient(self.user4, self.stream_recipient))

    def test_create_whisper_conversation_success(self) -> None:
        """Test successful whisper conversation creation"""
        participant_ids = [self.user2.id, self.user3.id]
        conversation = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        self.assertIsInstance(conversation, WhisperConversation)
        self.assertEqual(conversation.parent_recipient, self.stream_recipient)
        self.assertEqual(conversation.created_by, self.user1)
        self.assertTrue(conversation.is_active)
        
        # Check participants were created
        participants = get_whisper_conversation_participants(conversation)
        self.assertEqual(len(participants), 3)  # user1 + user2 + user3
        
        participant_ids_set = {p.id for p in participants}
        expected_ids = {self.user1.id, self.user2.id, self.user3.id}
        self.assertEqual(participant_ids_set, expected_ids)

    def test_create_whisper_conversation_duplicate(self) -> None:
        """Test that creating duplicate conversation returns existing one"""
        participant_ids = [self.user2.id, self.user3.id]
        
        conversation1 = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        conversation2 = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        self.assertEqual(conversation1.id, conversation2.id)

    def test_is_whisper_participant(self) -> None:
        """Test checking if user is whisper participant"""
        participant_ids = [self.user2.id]
        conversation = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        self.assertTrue(is_whisper_participant(conversation, self.user1))
        self.assertTrue(is_whisper_participant(conversation, self.user2))
        self.assertFalse(is_whisper_participant(conversation, self.user3))

    def test_add_participant_to_whisper_success(self) -> None:
        """Test successfully adding participant to whisper"""
        participant_ids = [self.user2.id]
        conversation = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        # Add user3 to the conversation
        participant = add_participant_to_whisper(conversation, self.user1, self.user3)
        
        self.assertIsInstance(participant, WhisperParticipant)
        self.assertEqual(participant.user_profile, self.user3)
        self.assertTrue(is_whisper_participant(conversation, self.user3))

    def test_add_participant_to_whisper_no_permission(self) -> None:
        """Test adding participant when requesting user is not a participant"""
        participant_ids = [self.user2.id]
        conversation = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        # user3 is not a participant, so can't add others
        with self.assertRaises(WhisperPermissionError):
            add_participant_to_whisper(conversation, self.user3, self.user4)

    def test_add_participant_already_exists(self) -> None:
        """Test adding participant who is already in conversation"""
        participant_ids = [self.user2.id]
        conversation = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        with self.assertRaises(WhisperValidationError):
            add_participant_to_whisper(conversation, self.user1, self.user2)

    def test_remove_participant_from_whisper_self(self) -> None:
        """Test user leaving whisper conversation"""
        participant_ids = [self.user2.id, self.user3.id]
        conversation = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        # user2 leaves the conversation
        still_active = remove_participant_from_whisper(conversation, self.user2)
        
        self.assertTrue(still_active)  # Conversation should still be active
        self.assertFalse(is_whisper_participant(conversation, self.user2))
        self.assertTrue(is_whisper_participant(conversation, self.user1))
        self.assertTrue(is_whisper_participant(conversation, self.user3))

    def test_remove_participant_conversation_closes(self) -> None:
        """Test conversation closes when only one participant left"""
        participant_ids = [self.user2.id]
        conversation = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        # user2 leaves, leaving only user1
        still_active = remove_participant_from_whisper(conversation, self.user2)
        
        self.assertFalse(still_active)  # Conversation should be closed
        
        # Refresh from database
        conversation.refresh_from_db()
        self.assertFalse(conversation.is_active)

    def test_remove_participant_by_creator(self) -> None:
        """Test conversation creator removing another participant"""
        participant_ids = [self.user2.id, self.user3.id]
        conversation = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        # user1 (creator) removes user2
        still_active = remove_participant_from_whisper(
            conversation, self.user1, self.user2
        )
        
        self.assertTrue(still_active)
        self.assertFalse(is_whisper_participant(conversation, self.user2))

    def test_remove_participant_no_permission(self) -> None:
        """Test non-creator trying to remove another participant"""
        participant_ids = [self.user2.id, self.user3.id]
        conversation = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        # user2 tries to remove user3 (not allowed)
        with self.assertRaises(WhisperPermissionError):
            remove_participant_from_whisper(conversation, self.user2, self.user3)

    def test_get_whisper_participants_hash_consistency(self) -> None:
        """Test that participant hash is consistent regardless of order"""
        user_ids1 = [1, 2, 3]
        user_ids2 = [3, 1, 2]
        user_ids3 = [2, 3, 1]
        
        hash1 = get_whisper_participants_hash(user_ids1)
        hash2 = get_whisper_participants_hash(user_ids2)
        hash3 = get_whisper_participants_hash(user_ids3)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(hash2, hash3)

    def test_get_active_whisper_conversation(self) -> None:
        """Test finding active whisper conversation"""
        participant_ids = [self.user2.id, self.user3.id]
        all_participant_ids = [self.user1.id] + participant_ids
        
        # No conversation exists initially
        conversation = get_active_whisper_conversation(
            self.stream_recipient, all_participant_ids
        )
        self.assertIsNone(conversation)
        
        # Create conversation
        created_conversation = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        # Should find it now
        found_conversation = get_active_whisper_conversation(
            self.stream_recipient, all_participant_ids
        )
        self.assertEqual(found_conversation.id, created_conversation.id)

    def test_update_whisper_participants_hash(self) -> None:
        """Test updating participants hash after changes"""
        participant_ids = [self.user2.id, self.user3.id]
        conversation = create_whisper_conversation(
            self.user1, participant_ids, self.stream_recipient
        )
        
        original_hash = conversation.participants_hash
        
        # Remove a participant
        remove_participant_from_whisper(conversation, self.user2)
        
        # Hash should be updated
        conversation.refresh_from_db()
        self.assertNotEqual(conversation.participants_hash, original_hash)

    def test_get_user_whisper_conversations(self) -> None:
        """Test getting user's whisper conversations"""
        # Create conversations
        conversation1 = create_whisper_conversation(
            self.user1, [self.user2.id], self.stream_recipient
        )
        conversation2 = create_whisper_conversation(
            self.user1, [self.user3.id], self.stream_recipient
        )
        
        # user1 should be in both conversations
        user1_conversations = get_user_whisper_conversations(self.user1)
        self.assertEqual(len(user1_conversations), 2)
        
        conversation_ids = {c.id for c in user1_conversations}
        expected_ids = {conversation1.id, conversation2.id}
        self.assertEqual(conversation_ids, expected_ids)
        
        # user2 should only be in conversation1
        user2_conversations = get_user_whisper_conversations(self.user2)
        self.assertEqual(len(user2_conversations), 1)
        self.assertEqual(user2_conversations[0].id, conversation1.id)

    def test_get_user_whisper_conversations_filtered(self) -> None:
        """Test getting user's whisper conversations filtered by parent"""
        # Create another stream
        other_stream = Stream.objects.create(name="other-stream", realm=self.realm)
        other_recipient = Recipient.objects.create(
            type=Recipient.STREAM,
            type_id=other_stream.id
        )
        
        # Subscribe users to other stream
        for user in [self.user1, self.user2]:
            Subscription.objects.create(
                user_profile=user,
                recipient=other_recipient,
                is_user_active=True
            )
        
        # Create conversations in different streams
        conversation1 = create_whisper_conversation(
            self.user1, [self.user2.id], self.stream_recipient
        )
        conversation2 = create_whisper_conversation(
            self.user1, [self.user2.id], other_recipient
        )
        
        # Filter by parent recipient
        stream_conversations = get_user_whisper_conversations(
            self.user1, self.stream_recipient
        )
        self.assertEqual(len(stream_conversations), 1)
        self.assertEqual(stream_conversations[0].id, conversation1.id)

    def test_cleanup_expired_whisper_requests(self) -> None:
        """Test cleaning up expired whisper requests"""
        # Create some requests
        old_time = timezone_now() - timedelta(hours=25)
        recent_time = timezone_now() - timedelta(hours=1)
        
        with patch('django.utils.timezone.now', return_value=old_time):
            old_request = WhisperRequest.objects.create(
                requester=self.user1,
                recipient=self.user2,
                parent_recipient=self.stream_recipient,
                realm=self.realm
            )
        
        with patch('django.utils.timezone.now', return_value=recent_time):
            recent_request = WhisperRequest.objects.create(
                requester=self.user1,
                recipient=self.user3,
                parent_recipient=self.stream_recipient,
                realm=self.realm
            )
        
        # Clean up expired requests
        cleaned_count = cleanup_expired_whisper_requests(self.realm, hours=24)
        
        self.assertEqual(cleaned_count, 1)
        
        # Check status updates
        old_request.refresh_from_db()
        recent_request.refresh_from_db()
        
        self.assertEqual(old_request.status, WhisperRequest.Status.EXPIRED)
        self.assertEqual(recent_request.status, WhisperRequest.Status.PENDING)

    def test_cleanup_inactive_whisper_conversations(self) -> None:
        """Test cleaning up inactive whisper conversations"""
        # Create old conversation
        old_time = timezone_now() - timedelta(days=8)
        
        with patch('django.utils.timezone.now', return_value=old_time):
            old_conversation = create_whisper_conversation(
                self.user1, [self.user2.id], self.stream_recipient
            )
        
        # Create recent conversation
        recent_conversation = create_whisper_conversation(
            self.user1, [self.user3.id], self.stream_recipient
        )
        
        # Clean up inactive conversations
        cleaned_count = cleanup_inactive_whisper_conversations(self.realm, days=7)
        
        self.assertEqual(cleaned_count, 1)
        
        # Check status updates
        old_conversation.refresh_from_db()
        recent_conversation.refresh_from_db()
        
        self.assertFalse(old_conversation.is_active)
        self.assertTrue(recent_conversation.is_active)