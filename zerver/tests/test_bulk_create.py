import itertools
import random
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils.timezone import now as timezone_now

from zerver.lib.bulk_create import _add_random_reactions_to_message, bulk_create_reactions
from zerver.models import (
    Client,
    Huddle,
    Message,
    Reaction,
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserProfile,
)


class TestBulkCreateReactions(TestCase):
    def setUp(self) -> None:
        super().setUp()
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

    def tearDown(self) -> None:
        for reaction in Reaction.objects.filter(message=self.personal_message):
            reaction.delete()
        self.personal_message.delete()
        self.realm.delete()
        self.message_client.delete()
        for recipient in self.recipients:
            recipient.delete()
        super().tearDown()

    @patch('zerver.lib.bulk_create.random')
    def test_reactions_to_personal_messages(self, mock_random: MagicMock) -> None:
        assert Reaction.objects.filter(message=self.personal_message).count() == 0
        mock_random.random.side_effect = [0, 1, 1]  # first reaction, no upvote, no second reaction
        bulk_create_reactions(messages=[self.personal_message], users=[self.bob], emojis=[('+1', '1f44d')])
        assert Reaction.objects.filter(message=self.personal_message).count() == 1

    @patch('zerver.lib.bulk_create.random')
    def test_reactions_default_users(self, mock_random: MagicMock) -> None:
        assert Reaction.objects.filter(message=self.personal_message).count() == 0
        mock_random.random.side_effect = [0, 1, 1]  # first reaction, no upvote, no second reaction
        bulk_create_reactions(messages=[self.personal_message], emojis=[('+1', '1f44d')])
        assert Reaction.objects.filter(message=self.personal_message).count() == 1

    @patch('zerver.lib.bulk_create.random')
    def test_upvoted_reaction_to_personal_message(self, mock_random: MagicMock) -> None:
        assert Reaction.objects.filter(message=self.personal_message).count() == 0
        mock_random.random.side_effect = [0, 0, 1, 1]  # first reaction, one upvote, no second reaction
        bulk_create_reactions(messages=[self.personal_message], users=[self.bob, self.alice], emojis=[('+1', '1f44d'), ('smiley', '1f603')])
        reactions = Reaction.objects.filter(message=self.personal_message)
        assert reactions.count() == 2
        r1, r2 = reactions
        assert r1.emoji_name == r2.emoji_name
        assert r1.emoji_code == r2.emoji_code
        assert r1.user_profile != r2.user_profile

    @patch('zerver.lib.bulk_create.random')
    def test_reactions_to_stream_messages(self, mock_random: MagicMock) -> None:
        assert Reaction.objects.filter(message=self.stream_message).count() == 0
        mock_random.random.side_effect = [0, 0, 0, 1, 0, 0, 1, 1]  # first reaction, two upvotes, second reaction, one upvote
        bulk_create_reactions(messages=[self.stream_message], emojis=[('+1', '1f44d'), ('smiley', '1f603')])
        reactions = Reaction.objects.filter(message=self.stream_message)
        assert reactions.count() == 5
        plus_one_reactions = reactions.filter(emoji_name='+1')
        assert plus_one_reactions.count() == 3
        smiley_reactions = reactions.filter(emoji_name='smiley')
        assert smiley_reactions.count() == 2

    @patch('zerver.lib.bulk_create.random')
    def test_reactions_to_huddle_messages(self, mock_random: MagicMock) -> None:
        assert Reaction.objects.filter(message=self.huddle_message).count() == 0
        mock_random.random.side_effect = [0, 0, 1, 0, 0, 0, 1, 1]  # first reaction, one upvote, second reaction, two upvotes
        bulk_create_reactions(messages=[self.huddle_message], emojis=[('+1', '1f44d'), ('smiley', '1f603')])
        reactions = Reaction.objects.filter(message=self.huddle_message)
        assert reactions.count() == 5
        plus_one_reactions = reactions.filter(emoji_name='+1')
        assert plus_one_reactions.count() == 2
        smiley_reactions = reactions.filter(emoji_name='smiley')
        assert smiley_reactions.count() == 3

    @patch('zerver.lib.bulk_create.random')
    def test_duplicate_reactions_removed(self, mock_random: MagicMock) -> None:
        assert Reaction.objects.filter(message=self.stream_message).count() == 0
        # a bunch of duplicated reactions from the second set of loops
        mock_random.random.side_effect = [0] * 20 + [1] + [0] * 20 + [1, 1]
        bulk_create_reactions(messages=[self.stream_message], emojis=[('+1', '1f44d')])
        reactions = Reaction.objects.filter(message=self.stream_message)
        assert reactions.count() == 3

    @patch('zerver.lib.bulk_create.random')
    def test_reactions_default_emojis(self, mock_random: MagicMock) -> None:
        assert Reaction.objects.filter(message=self.stream_message).count() == 0
        mock_random.random.side_effect = itertools.chain([0], (random.random() for _ in itertools.count(1)))
        bulk_create_reactions(messages=[self.stream_message])
        assert Reaction.objects.filter(message=self.stream_message).count() > 0

    @patch('zerver.lib.bulk_create.Subscription')
    def test_no_subscription_users(self, MockSubscription: MagicMock) -> None:
        assert Reaction.objects.filter(message=self.stream_message).count() == 0
        MockSubscription.objects.filter.return_value = []
        bulk_create_reactions(messages=[self.stream_message])
        assert Reaction.objects.filter(message = self.stream_message).count() == 0

    def test_probabilities_between_zero_and_one(self) -> None:
        with self.assertRaises(ValueError):
            _add_random_reactions_to_message(
                self.personal_message, [('+1', '1f44d')], self.users,
                prob_reaction=-1
            )
        with self.assertRaises(ValueError):
            _add_random_reactions_to_message(
                self.personal_message, [('+1', '1f44d')], self.users,
                prob_reaction=2
            )
        with self.assertRaises(ValueError):
            _add_random_reactions_to_message(
                self.personal_message, [('+1', '1f44d')], self.users,
                prob_upvote=-1
            )
        with self.assertRaises(ValueError):
            _add_random_reactions_to_message(
                self.personal_message, [('+1', '1f44d')], self.users,
                prob_upvote=2
            )
        with self.assertRaises(ValueError):
            _add_random_reactions_to_message(
                self.personal_message, [('+1', '1f44d')], self.users,
                prob_repeat=-1
            )
        with self.assertRaises(ValueError):
            _add_random_reactions_to_message(
                self.personal_message, [('+1', '1f44d')], self.users,
                prob_repeat=2
            )
