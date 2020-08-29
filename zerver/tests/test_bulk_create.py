import itertools
import random
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils.timezone import now as timezone_now

from zerver.lib.bulk_create import (
    DEFAULT_EMOJIS,
    _add_random_reactions_to_message,
    bulk_create_reactions,
)
from zerver.models import (
    Client,
    Huddle,
    Message,
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
)


class TestBulkCreateReactions(TestCase):
    """This test class is somewhat low value and uses extensive mocking of
    random; it's possible we should delete it rather than doing a
    great deal of work to preserve it; this test mostly exists to
    achieve coverage goals."""

    def setUp(self) -> None:
        super().setUp()
        random.seed(42)
        self.realm = Realm.objects.create(
            name="test_realm",
            string_id="test_realm"
        )
        self.message_client = Client.objects.create(
            name='test_client'
        )
        self.alice = UserProfile.objects.create(
            delivery_email='alice@gmail.com',
            email='alice@gmail.com',
            realm=self.realm,
            full_name='Alice'
        )
        self.bob = UserProfile.objects.create(
            delivery_email='bob@gmail.com',
            email='bob@gmail.com',
            realm=self.realm,
            full_name='Bob'
        )
        self.charlie = UserProfile.objects.create(
            delivery_email='charlie@gmail.com',
            email='charlie@gmail.com',
            realm=self.realm,
            full_name='Charlie'
        )

        self.users = [self.alice, self.bob, self.charlie]
        type_ids = Recipient \
            .objects.filter(type=Recipient.PERSONAL).values_list('type_id')
        max_type_id = max(x[0] for x in type_ids)
        self.recipients = []
        for i, user in enumerate(self.users):
            recipient = Recipient.objects.create(
                type=Recipient.PERSONAL,
                type_id=max_type_id + i + 1
            )
            user.recipient = recipient
            user.save()
            self.recipients.append(recipient)
        self.personal_message = Message.objects.create(
            sender=self.alice,
            recipient=self.bob.recipient,
            content='It is I, Alice.',
            sending_client=self.message_client,
            date_sent=timezone_now()
        )

        self.stream = Stream.objects.create(
            name="test_stream",
            realm=self.realm,
        )
        self.stream.recipient = Recipient.objects.create(
            type=Recipient.STREAM,
            type_id=1 + max(
                x[0] for x in Recipient.objects.filter(type=Recipient.STREAM).values_list('type_id'))
        )
        self.stream.save()
        for user in self.users:
            Subscription.objects.create(
                user_profile=user,
                recipient=self.stream.recipient
            )
        self.stream_message = Message.objects.create(
            sender=self.alice,
            recipient=self.stream.recipient,
            content='This is Alice.',
            sending_client=self.message_client,
            date_sent=timezone_now()
        )

        self.huddle = Huddle.objects.create(
            huddle_hash="bad-hash",
        )
        self.huddle.recipient = Recipient.objects.create(
            type=Recipient.HUDDLE,
            type_id=1 + max(
                itertools.chain(
                    (x[0] for x in Recipient.objects.filter(type=Recipient.HUDDLE).values_list('type_id')),
                    [0])))
        self.huddle.save()
        for user in self.users:
            Subscription.objects.create(
                user_profile=user,
                recipient=self.huddle.recipient
            )
        self.huddle_message = Message.objects.create(
            sender=self.alice,
            recipient=self.huddle.recipient,
            content='Alice my name is.',
            sending_client=self.message_client,
            date_sent=timezone_now()
        )

    def test_invalid_probabilities(self) -> None:
        message = self.personal_message
        emojis = DEFAULT_EMOJIS
        users = self.users
        prob_keys = ['prob_reaction', 'prob_upvote', 'prob_repeat']
        for probs in [
            (1, .5, .5),
            (.5, 1, .5),
            (.5, .5, 1),
            (-0.01, .5, .5),
            (.5, -.01, .5),
            (.5, .5, -.01),
        ]:
            kwargs = dict(zip(prob_keys, probs))
            with self.assertRaises(ValueError):
                _add_random_reactions_to_message(message, emojis, users, **kwargs)

    @patch('zerver.lib.bulk_create.random')
    @patch('zerver.lib.bulk_create.UserProfile')
    @patch('zerver.lib.bulk_create.Subscription')
    def test_early_exit_if_no_reactions(
            self,
            MockSubscription: MagicMock,
            MockUserProfile: MagicMock,
            mock_random: MagicMock) -> None:
        message = self.personal_message
        emojis = DEFAULT_EMOJIS
        users = None
        mock_random.random.return_value = 1
        reactions = _add_random_reactions_to_message(message, emojis, users)
        self.assertEqual(reactions, [])
        self.assertFalse(MockUserProfile.objects.get.called)
        self.assertFalse(MockSubscription.objects.filter.called)

    @patch('zerver.lib.bulk_create.random')
    @patch('zerver.lib.bulk_create.UserMessage')
    def test_query_for_personal_message_users(
            self,
            MockUserProfile: MagicMock,
            mock_random: MagicMock) -> None:
        message = self.personal_message
        emojis = DEFAULT_EMOJIS
        users = None
        mock_random.choice = random.choice
        mock_random.random.side_effect = [0, 1, 1, 1, 1, 1]
        _add_random_reactions_to_message(message, emojis, users)
        self.assertTrue(MockUserProfile.objects.filter.called)

    @patch('zerver.lib.bulk_create.random')
    @patch('zerver.lib.bulk_create.UserMessage')
    def test_query_for_stream_message_users(
            self,
            MockUserMessage: MagicMock,
            mock_random: MagicMock) -> None:
        message = self.stream_message
        emojis = DEFAULT_EMOJIS
        users = None
        mock_random.choice = random.choice
        mock_random.random.side_effect = [0, 1, 1, 1, 1, 1]
        _add_random_reactions_to_message(message, emojis, users)
        self.assertTrue(MockUserMessage.objects.filter.called)

    @patch('zerver.lib.bulk_create.random')
    @patch('zerver.lib.bulk_create.UserMessage')
    def test_query_for_huddle_message_users(
            self,
            MockUserMessage: MagicMock,
            mock_random: MagicMock) -> None:
        message = self.huddle_message
        emojis = DEFAULT_EMOJIS
        users = None
        mock_random.choice = random.choice
        mock_random.random.side_effect = [0, 1, 1, 1, 1, 1]
        _add_random_reactions_to_message(message, emojis, users)
        self.assertTrue(MockUserMessage.objects.filter.called)

    @patch('zerver.lib.bulk_create.random')
    @patch('zerver.lib.bulk_create.UserMessage')
    def test_early_exit_if_no_users(
            self,
            MockUserMessage: MagicMock,
            mock_random: MagicMock) -> None:
        message = self.stream_message
        emojis = DEFAULT_EMOJIS
        users = None
        mock_random.choice = random.choice
        mock_random.random.side_effect = [0, 1, 1, 1, 1, 1]
        MockUserMessage.objects.filter.return_value = UserMessage.objects.none()
        reactions = _add_random_reactions_to_message(message, emojis, users)
        self.assertTrue(MockUserMessage.objects.filter.called)
        self.assertEqual(reactions, [])

    @patch('zerver.lib.bulk_create.random')
    def test_single_reaction(
            self,
            mock_random: MagicMock) -> None:
        message = self.stream_message
        emojis = DEFAULT_EMOJIS
        users = self.users
        mock_random.choice = random.choice
        mock_random.random.side_effect = [0, 1, 1]
        reactions = _add_random_reactions_to_message(message, emojis, users)
        self.assertEqual(len(reactions), 1)

    @patch('zerver.lib.bulk_create.random')
    def test_single_reaction_with_upvote(
            self,
            mock_random: MagicMock) -> None:
        message = self.stream_message
        emojis = DEFAULT_EMOJIS
        users = self.users
        mock_random.choice = random.choice
        mock_random.random.side_effect = [0, 0, 1, 1]
        reactions = _add_random_reactions_to_message(message, emojis, users)
        self.assertEqual(len(reactions), 2)
        assert reactions[0].emoji_name == reactions[1].emoji_name
        assert reactions[0].user_profile_id != reactions[1].user_profile_id

    @patch('zerver.lib.bulk_create.random')
    def test_two_reactions_with_different_emojis(
            self, mock_random: MagicMock) -> None:
        message = self.stream_message
        emojis = DEFAULT_EMOJIS
        users = self.users
        mock_random.choice.side_effect = [emojis[0], users[0].id, emojis[1], users[1].id]
        mock_random.random.side_effect = [0, 1, 0, 1, 1]
        reactions = _add_random_reactions_to_message(message, emojis, users)
        self.assertEqual(len(reactions), 2)
        assert reactions[0].emoji_name != reactions[1].emoji_name
        assert reactions[0].user_profile_id != reactions[1].user_profile_id

    @patch('zerver.lib.bulk_create.random')
    def test_deduplicated_reactions(
            self, mock_random: MagicMock) -> None:
        message = self.stream_message
        emojis = DEFAULT_EMOJIS[:1]
        users = self.users[:1]
        mock_random.choice = random.choice
        mock_random.random.side_effect = [0, 1, 0, 1, 1]
        reactions = _add_random_reactions_to_message(message, emojis, users)
        self.assertEqual(len(reactions), 1)

    @patch('zerver.lib.bulk_create.random')
    def test_no_available_users(
            self, mock_random: MagicMock) -> None:
        message = self.stream_message
        emojis = DEFAULT_EMOJIS
        users = self.users[:1]
        mock_random.choice = random.choice
        mock_random.random.side_effect = [0, 0, 1, 1]
        reactions = _add_random_reactions_to_message(message, emojis, users)
        self.assertEqual(len(reactions), 1)

    @patch('zerver.lib.bulk_create.Reaction')
    @patch('zerver.lib.bulk_create._add_random_reactions_to_message')
    def test_default_emojis(
            self,
            mock_add_random_reactions_to_message: MagicMock,
            MockReaction: MagicMock) -> None:
        messages = [self.personal_message]
        users = [self.users[0]]
        emojis = None
        bulk_create_reactions(messages, users, emojis)
        self.assertTrue(mock_add_random_reactions_to_message.called)
        mock_add_random_reactions_to_message.assert_called_with(
            messages[0], DEFAULT_EMOJIS, users)
