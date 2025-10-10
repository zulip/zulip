from django.test import TestCase
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    Message,
    Realm,
    Recipient,
    Stream,
    UserProfile,
    WhisperConversation,
    WhisperParticipant,
    WhisperRequest,
    get_realm,
)
from zerver.models.whispers import get_active_whisper_conversation, get_whisper_participants_hash


class WhisperModelsTest(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm("zulip")
        self.user1 = self.example_user("hamlet")
        self.user2 = self.example_user("cordelia")
        self.user3 = self.example_user("othello")
        
        # Create a test stream for parent conversation
        self.stream = Stream.objects.create(
            name="test-stream",
            realm=self.realm,
        )
        self.stream_recipient = Recipient.objects.create(
            type=Recipient.STREAM,
            type_id=self.stream.id
        )

    def test_whisper_participants_hash_generation(self) -> None:
        """Test that participant hash is generated correctly and consistently"""
        user_ids = [self.user1.id, self.user2.id, self.user3.id]
        hash1 = get_whisper_participants_hash(user_ids)
        
        # Hash should be consistent regardless of order
        user_ids_reversed = [self.user3.id, self.user2.id, self.user1.id]
        hash2 = get_whisper_participants_hash(user_ids_reversed)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 40)  # SHA1 hash length

    def test_whisper_conversation_creation(self) -> None:
        """Test creating a whisper conversation"""
        user_ids = [self.user1.id, self.user2.id]
        participants_hash = get_whisper_participants_hash(user_ids)
        
        whisper_conversation = WhisperConversation.objects.create(
            parent_recipient=self.stream_recipient,
            realm=self.realm,
            created_by=self.user1,
            participants_hash=participants_hash
        )
        
        self.assertEqual(whisper_conversation.parent_recipient, self.stream_recipient)
        self.assertEqual(whisper_conversation.realm, self.realm)
        self.assertEqual(whisper_conversation.created_by, self.user1)
        self.assertEqual(whisper_conversation.participants_hash, participants_hash)
        self.assertTrue(whisper_conversation.is_active)

    def test_whisper_participant_creation(self) -> None:
        """Test creating whisper participants"""
        user_ids = [self.user1.id, self.user2.id]
        participants_hash = get_whisper_participants_hash(user_ids)
        
        whisper_conversation = WhisperConversation.objects.create(
            parent_recipient=self.stream_recipient,
            realm=self.realm,
            created_by=self.user1,
            participants_hash=participants_hash
        )
        
        # Add participants
        participant1 = WhisperParticipant.objects.create(
            whisper_conversation=whisper_conversation,
            user_profile=self.user1
        )
        participant2 = WhisperParticipant.objects.create(
            whisper_conversation=whisper_conversation,
            user_profile=self.user2
        )
        
        self.assertEqual(participant1.whisper_conversation, whisper_conversation)
        self.assertEqual(participant1.user_profile, self.user1)
        self.assertTrue(participant1.is_active)
        
        self.assertEqual(participant2.whisper_conversation, whisper_conversation)
        self.assertEqual(participant2.user_profile, self.user2)
        self.assertTrue(participant2.is_active)

    def test_whisper_request_creation(self) -> None:
        """Test creating a whisper request"""
        whisper_request = WhisperRequest.objects.create(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            realm=self.realm
        )
        
        self.assertEqual(whisper_request.requester, self.user1)
        self.assertEqual(whisper_request.recipient, self.user2)
        self.assertEqual(whisper_request.parent_recipient, self.stream_recipient)
        self.assertEqual(whisper_request.realm, self.realm)
        self.assertEqual(whisper_request.status, WhisperRequest.Status.PENDING)

    def test_get_active_whisper_conversation(self) -> None:
        """Test finding an active whisper conversation"""
        user_ids = [self.user1.id, self.user2.id]
        participants_hash = get_whisper_participants_hash(user_ids)
        
        # No conversation exists initially
        conversation = get_active_whisper_conversation(self.stream_recipient, user_ids)
        self.assertIsNone(conversation)
        
        # Create a conversation
        whisper_conversation = WhisperConversation.objects.create(
            parent_recipient=self.stream_recipient,
            realm=self.realm,
            created_by=self.user1,
            participants_hash=participants_hash
        )
        
        # Should find the conversation now
        conversation = get_active_whisper_conversation(self.stream_recipient, user_ids)
        self.assertEqual(conversation, whisper_conversation)
        
        # Deactivate the conversation
        whisper_conversation.is_active = False
        whisper_conversation.save()
        
        # Should not find inactive conversation
        conversation = get_active_whisper_conversation(self.stream_recipient, user_ids)
        self.assertIsNone(conversation)

    def test_whisper_conversation_get_participant_ids(self) -> None:
        """Test getting participant IDs from a whisper conversation"""
        user_ids = [self.user1.id, self.user2.id, self.user3.id]
        participants_hash = get_whisper_participants_hash(user_ids)
        
        whisper_conversation = WhisperConversation.objects.create(
            parent_recipient=self.stream_recipient,
            realm=self.realm,
            created_by=self.user1,
            participants_hash=participants_hash
        )
        
        # Add participants
        WhisperParticipant.objects.create(
            whisper_conversation=whisper_conversation,
            user_profile=self.user1
        )
        WhisperParticipant.objects.create(
            whisper_conversation=whisper_conversation,
            user_profile=self.user2
        )
        WhisperParticipant.objects.create(
            whisper_conversation=whisper_conversation,
            user_profile=self.user3
        )
        
        participant_ids = list(whisper_conversation.get_participant_ids())
        self.assertEqual(set(participant_ids), set(user_ids))

    def test_whisper_message_association(self) -> None:
        """Test that messages can be associated with whisper conversations"""
        user_ids = [self.user1.id, self.user2.id]
        participants_hash = get_whisper_participants_hash(user_ids)
        
        whisper_conversation = WhisperConversation.objects.create(
            parent_recipient=self.stream_recipient,
            realm=self.realm,
            created_by=self.user1,
            participants_hash=participants_hash
        )
        
        # Create a message associated with the whisper conversation
        message = Message.objects.create(
            sender=self.user1,
            recipient=self.stream_recipient,
            realm=self.realm,
            subject="test topic",
            content="test whisper message",
            date_sent=timezone_now(),
            whisper_conversation=whisper_conversation
        )
        
        self.assertEqual(message.whisper_conversation, whisper_conversation)
        
        # Test that regular messages don't have whisper conversation
        regular_message = Message.objects.create(
            sender=self.user1,
            recipient=self.stream_recipient,
            realm=self.realm,
            subject="test topic",
            content="regular message",
            date_sent=timezone_now()
        )
        
        self.assertIsNone(regular_message.whisper_conversation)

    def test_recipient_whisper_type(self) -> None:
        """Test that Recipient model supports WHISPER type"""
        self.assertEqual(Recipient.WHISPER, 4)
        self.assertEqual(Recipient._type_names[Recipient.WHISPER], "whisper")
        
        # Test parent_recipient relationship
        whisper_recipient = Recipient.objects.create(
            type=Recipient.WHISPER,
            type_id=1,  # This would be the WhisperConversation ID
            parent_recipient=self.stream_recipient
        )
        
        self.assertEqual(whisper_recipient.parent_recipient, self.stream_recipient)
        self.assertEqual(whisper_recipient.type_name(), "whisper")