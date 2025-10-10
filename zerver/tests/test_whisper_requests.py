from datetime import timedelta
from unittest.mock import patch

from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.whispers import (
    WhisperPermissionError,
    WhisperValidationError,
    bulk_expire_whisper_requests_for_conversation,
    cancel_whisper_request,
    create_whisper_conversation,
    create_whisper_request,
    get_pending_whisper_requests_for_user,
    get_sent_whisper_requests_for_user,
    get_whisper_request_by_id,
    get_whisper_request_stats_for_user,
    respond_to_whisper_request,
    validate_whisper_request_rate_limit,
)
from zerver.models import (
    Recipient,
    Stream,
    Subscription,
    WhisperRequest,
    get_realm,
)


class WhisperRequestTest(ZulipTestCase):
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

    def test_create_whisper_request_success(self) -> None:
        """Test successful whisper request creation"""
        request = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        self.assertIsInstance(request, WhisperRequest)
        self.assertEqual(request.requester, self.user1)
        self.assertEqual(request.recipient, self.user2)
        self.assertEqual(request.parent_recipient, self.stream_recipient)
        self.assertEqual(request.status, WhisperRequest.Status.PENDING)
        self.assertEqual(request.realm, self.realm)

    def test_create_whisper_request_no_access_requester(self) -> None:
        """Test whisper request creation when requester lacks access"""
        # user4 is not subscribed to the stream
        with self.assertRaises(WhisperPermissionError):
            create_whisper_request(
                requester=self.user4,
                recipient=self.user2,
                parent_recipient=self.stream_recipient,
                proposed_participants=[self.user4.id, self.user2.id]
            )

    def test_create_whisper_request_no_access_recipient(self) -> None:
        """Test whisper request creation when recipient lacks access"""
        # user4 is not subscribed to the stream
        with self.assertRaises(WhisperPermissionError):
            create_whisper_request(
                requester=self.user1,
                recipient=self.user4,
                parent_recipient=self.stream_recipient,
                proposed_participants=[self.user1.id, self.user4.id]
            )

    def test_create_whisper_request_duplicate_pending(self) -> None:
        """Test creating duplicate pending request fails"""
        # Create first request
        create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        # Try to create duplicate
        with self.assertRaises(WhisperValidationError):
            create_whisper_request(
                requester=self.user1,
                recipient=self.user2,
                parent_recipient=self.stream_recipient,
                proposed_participants=[self.user1.id, self.user2.id]
            )

    def test_create_whisper_request_already_in_conversation(self) -> None:
        """Test creating request when users are already in whisper together"""
        # Create a whisper conversation first
        create_whisper_conversation(
            self.user1, [self.user2.id], self.stream_recipient
        )
        
        # Try to create request
        with self.assertRaises(WhisperValidationError):
            create_whisper_request(
                requester=self.user1,
                recipient=self.user2,
                parent_recipient=self.stream_recipient,
                proposed_participants=[self.user1.id, self.user2.id]
            )

    def test_respond_to_whisper_request_accept(self) -> None:
        """Test accepting a whisper request"""
        request = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        # Accept the request
        conversation = respond_to_whisper_request(
            request, self.user2, accept=True
        )
        
        self.assertIsNotNone(conversation)
        self.assertEqual(conversation.parent_recipient, self.stream_recipient)
        
        # Check request status updated
        request.refresh_from_db()
        self.assertEqual(request.status, WhisperRequest.Status.ACCEPTED)
        self.assertEqual(request.whisper_conversation, conversation)

    def test_respond_to_whisper_request_accept_with_additional_participants(self) -> None:
        """Test accepting request with additional participants"""
        request = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        # Accept with additional participant
        conversation = respond_to_whisper_request(
            request, self.user2, accept=True, additional_participants=[self.user3.id]
        )
        
        self.assertIsNotNone(conversation)
        
        # Check all participants are in conversation
        participant_ids = list(conversation.get_participant_ids())
        expected_ids = {self.user1.id, self.user2.id, self.user3.id}
        self.assertEqual(set(participant_ids), expected_ids)

    def test_respond_to_whisper_request_decline(self) -> None:
        """Test declining a whisper request"""
        request = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        # Decline the request
        conversation = respond_to_whisper_request(
            request, self.user2, accept=False
        )
        
        self.assertIsNone(conversation)
        
        # Check request status updated
        request.refresh_from_db()
        self.assertEqual(request.status, WhisperRequest.Status.DECLINED)
        self.assertIsNone(request.whisper_conversation)

    def test_respond_to_whisper_request_wrong_user(self) -> None:
        """Test responding to request as wrong user"""
        request = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        # user3 tries to respond (not the recipient)
        with self.assertRaises(WhisperPermissionError):
            respond_to_whisper_request(request, self.user3, accept=True)

    def test_respond_to_whisper_request_not_pending(self) -> None:
        """Test responding to non-pending request"""
        request = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        # Accept first
        respond_to_whisper_request(request, self.user2, accept=True)
        
        # Try to respond again
        with self.assertRaises(WhisperValidationError):
            respond_to_whisper_request(request, self.user2, accept=False)

    def test_get_pending_whisper_requests_for_user(self) -> None:
        """Test getting pending requests for a user"""
        # Create requests
        request1 = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        request2 = create_whisper_request(
            requester=self.user3,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user3.id, self.user2.id]
        )
        
        # Accept one request
        respond_to_whisper_request(request2, self.user2, accept=True)
        
        # Get pending requests for user2
        pending_requests = get_pending_whisper_requests_for_user(self.user2)
        
        self.assertEqual(len(pending_requests), 1)
        self.assertEqual(pending_requests[0].id, request1.id)

    def test_get_sent_whisper_requests_for_user(self) -> None:
        """Test getting sent requests for a user"""
        # Create requests
        request1 = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        request2 = create_whisper_request(
            requester=self.user1,
            recipient=self.user3,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user3.id]
        )
        
        # Get sent requests for user1
        sent_requests = get_sent_whisper_requests_for_user(self.user1)
        
        self.assertEqual(len(sent_requests), 2)
        request_ids = {r.id for r in sent_requests}
        expected_ids = {request1.id, request2.id}
        self.assertEqual(request_ids, expected_ids)

    def test_cancel_whisper_request_success(self) -> None:
        """Test successfully cancelling a whisper request"""
        request = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        # Cancel the request
        cancel_whisper_request(request, self.user1)
        
        # Check status updated
        request.refresh_from_db()
        self.assertEqual(request.status, WhisperRequest.Status.EXPIRED)

    def test_cancel_whisper_request_wrong_user(self) -> None:
        """Test cancelling request as wrong user"""
        request = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        # user2 tries to cancel (not the requester)
        with self.assertRaises(WhisperPermissionError):
            cancel_whisper_request(request, self.user2)

    def test_cancel_whisper_request_not_pending(self) -> None:
        """Test cancelling non-pending request"""
        request = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        # Accept the request first
        respond_to_whisper_request(request, self.user2, accept=True)
        
        # Try to cancel
        with self.assertRaises(WhisperValidationError):
            cancel_whisper_request(request, self.user1)

    def test_get_whisper_request_by_id_success(self) -> None:
        """Test getting whisper request by ID"""
        request = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        # Requester should be able to access
        retrieved_request = get_whisper_request_by_id(request.id, self.user1)
        self.assertEqual(retrieved_request.id, request.id)
        
        # Recipient should be able to access
        retrieved_request = get_whisper_request_by_id(request.id, self.user2)
        self.assertEqual(retrieved_request.id, request.id)

    def test_get_whisper_request_by_id_no_permission(self) -> None:
        """Test getting whisper request by ID without permission"""
        request = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        
        # user3 should not be able to access
        with self.assertRaises(WhisperPermissionError):
            get_whisper_request_by_id(request.id, self.user3)

    def test_get_whisper_request_by_id_not_found(self) -> None:
        """Test getting non-existent whisper request"""
        with self.assertRaises(WhisperValidationError):
            get_whisper_request_by_id(99999, self.user1)

    def test_bulk_expire_whisper_requests_for_conversation(self) -> None:
        """Test expiring requests when conversation is created"""
        # Create some requests between users
        request1 = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        request2 = create_whisper_request(
            requester=self.user2,
            recipient=self.user3,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user2.id, self.user3.id]
        )
        
        # Create a conversation with these users
        conversation = create_whisper_conversation(
            self.user1, [self.user2.id, self.user3.id], self.stream_recipient
        )
        
        # Expire related requests
        expired_count = bulk_expire_whisper_requests_for_conversation(conversation)
        
        self.assertEqual(expired_count, 2)
        
        # Check requests are expired
        request1.refresh_from_db()
        request2.refresh_from_db()
        
        self.assertEqual(request1.status, WhisperRequest.Status.EXPIRED)
        self.assertEqual(request2.status, WhisperRequest.Status.EXPIRED)

    def test_get_whisper_request_stats_for_user(self) -> None:
        """Test getting request statistics for a user"""
        # Create various requests
        request1 = create_whisper_request(
            requester=self.user1,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user1.id, self.user2.id]
        )
        request2 = create_whisper_request(
            requester=self.user3,
            recipient=self.user2,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user3.id, self.user2.id]
        )
        
        # Accept one, decline another
        respond_to_whisper_request(request1, self.user2, accept=True)
        respond_to_whisper_request(request2, self.user2, accept=False)
        
        # Create a sent request
        sent_request = create_whisper_request(
            requester=self.user2,
            recipient=self.user1,
            parent_recipient=self.stream_recipient,
            proposed_participants=[self.user2.id, self.user1.id]
        )
        
        # Get stats for user2
        stats = get_whisper_request_stats_for_user(self.user2)
        
        expected_stats = {
            'received_pending': 0,
            'received_total': 2,
            'received_accepted': 1,
            'received_declined': 1,
            'sent_pending': 1,
            'sent_total': 1,
            'sent_accepted': 0,
            'sent_declined': 0,
        }
        
        self.assertEqual(stats, expected_stats)

    def test_validate_whisper_request_rate_limit_success(self) -> None:
        """Test rate limit validation when under limit"""
        # Should not raise any exception
        validate_whisper_request_rate_limit(self.user1, self.user2)

    def test_validate_whisper_request_rate_limit_exceeded_general(self) -> None:
        """Test rate limit validation when general limit exceeded"""
        # Create multiple requests in short time
        for i in range(5):
            create_whisper_request(
                requester=self.user1,
                recipient=self.user2 if i % 2 == 0 else self.user3,
                parent_recipient=self.stream_recipient,
                proposed_participants=[self.user1.id, (self.user2 if i % 2 == 0 else self.user3).id]
            )
        
        # Next request should fail
        with self.assertRaises(WhisperValidationError):
            validate_whisper_request_rate_limit(self.user1, self.user2)

    def test_validate_whisper_request_rate_limit_exceeded_specific_user(self) -> None:
        """Test rate limit validation when specific user limit exceeded"""
        # Create multiple requests to same user
        for i in range(2):
            request = create_whisper_request(
                requester=self.user1,
                recipient=self.user2,
                parent_recipient=self.stream_recipient,
                proposed_participants=[self.user1.id, self.user2.id]
            )
            # Cancel to allow creating another
            cancel_whisper_request(request, self.user1)
        
        # Next request to same user should fail
        with self.assertRaises(WhisperValidationError):
            validate_whisper_request_rate_limit(self.user1, self.user2)

    def test_validate_whisper_request_rate_limit_time_window(self) -> None:
        """Test rate limit validation respects time window"""
        old_time = timezone_now() - timedelta(hours=2)
        
        # Create old requests (should not count against limit)
        with patch('django.utils.timezone.now', return_value=old_time):
            for i in range(5):
                create_whisper_request(
                    requester=self.user1,
                    recipient=self.user2 if i % 2 == 0 else self.user3,
                    parent_recipient=self.stream_recipient,
                    proposed_participants=[self.user1.id, (self.user2 if i % 2 == 0 else self.user3).id]
                )
        
        # Should be able to create new request (old ones don't count)
        validate_whisper_request_rate_limit(self.user1, self.user2)