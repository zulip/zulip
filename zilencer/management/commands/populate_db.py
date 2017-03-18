from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from zerver.models import Message, UserProfile, Stream, Recipient, UserPresence, \
    Subscription, get_huddle, Realm, UserMessage, RealmAlias, \
    clear_database, get_client, get_user_profile_by_id, \
    email_to_username
from zerver.lib.actions import STREAM_ASSIGNMENT_COLORS, do_send_messages, \
    do_change_is_admin
from django.conf import settings
from zerver.lib.bulk_create import bulk_create_clients, \
    bulk_create_streams, bulk_create_users, bulk_create_huddles
from zerver.models import DefaultStream, get_stream, get_realm

import random
import os
from optparse import make_option
from six.moves import range
from typing import Any, Callable, Dict, List, Iterable, Mapping, Sequence, Set, Tuple, Text

settings.TORNADO_SERVER = None
# Disable using memcached caches to avoid 'unsupported pickle
# protocol' errors if `populate_db` is run with a different Python
# from `run-dev.py`.
settings.CACHES['default'] = {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
}

def create_users(realm, name_list, bot_type=None):
    # type: (Realm, Iterable[Tuple[Text, Text]], int) -> None
    user_set = set() # type: Set[Tuple[Text, Text, Text, bool]]
    for full_name, email in name_list:
        short_name = email_to_username(email)
        user_set.add((email, full_name, short_name, True))
    tos_version = settings.TOS_VERSION if bot_type is None else None
    bulk_create_users(realm, user_set, bot_type=bot_type, tos_version=tos_version)

class Command(BaseCommand):
    help = "Populate a test database"

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument('-n', '--num-messages',
                            dest='num_messages',
                            type=int,
                            default=600,
                            help='The number of messages to create.')

        parser.add_argument('--extra-users',
                            dest='extra_users',
                            type=int,
                            default=0,
                            help='The number of extra users to create')

        parser.add_argument('--extra-bots',
                            dest='extra_bots',
                            type=int,
                            default=0,
                            help='The number of extra bots to create')

        parser.add_argument('--huddles',
                            dest='num_huddles',
                            type=int,
                            default=3,
                            help='The number of huddles to create.')

        parser.add_argument('--personals',
                            dest='num_personals',
                            type=int,
                            default=6,
                            help='The number of personal pairs to create.')

        parser.add_argument('--threads',
                            dest='threads',
                            type=int,
                            default=10,
                            help='The number of threads to use.')

        parser.add_argument('--percent-huddles',
                            dest='percent_huddles',
                            type=float,
                            default=15,
                            help='The percent of messages to be huddles.')

        parser.add_argument('--percent-personals',
                            dest='percent_personals',
                            type=float,
                            default=15,
                            help='The percent of messages to be personals.')

        parser.add_argument('--stickyness',
                            dest='stickyness',
                            type=float,
                            default=20,
                            help='The percent of messages to repeat recent folks.')

        parser.add_argument('--nodelete',
                            action="store_false",
                            default=True,
                            dest='delete',
                            help='Whether to delete all the existing messages.')

        parser.add_argument('--test-suite',
                            default=False,
                            action="store_true",
                            help='Whether to delete all the existing messages.')

    def handle(self, **options):
        # type: (**Any) -> None
        if options["percent_huddles"] + options["percent_personals"] > 100:
            self.stderr.write("Error!  More than 100% of messages allocated.\n")
            return

        if options["delete"]:
            # Start by clearing all the data in our database
            clear_database()

            # Create our two default realms
            # Could in theory be done via zerver.lib.actions.do_create_realm, but
            # welcome-bot (needed for do_create_realm) hasn't been created yet
            zulip_realm = Realm.objects.create(
                string_id="zulip", name="Zulip Dev", restricted_to_domain=True,
                invite_required=False, org_type=Realm.CORPORATE, domain="zulip.com")
            RealmAlias.objects.create(realm=zulip_realm, domain="zulip.com")
            if options["test_suite"]:
                mit_realm = Realm.objects.create(
                    string_id="zephyr", name="MIT", restricted_to_domain=True,
                    invite_required=False, org_type=Realm.CORPORATE, domain="mit.edu")
                RealmAlias.objects.create(realm=mit_realm, domain="mit.edu")

            # Create test Users (UserProfiles are automatically created,
            # as are subscriptions to the ability to receive personals).
            names = [
                ("Zoe", "ZOE@zulip.com"),
                ("Othello, the Moor of Venice", "othello@zulip.com"),
                ("Iago", "iago@zulip.com"),
                ("Prospero from The Tempest", "prospero@zulip.com"),
                ("Cordelia Lear", "cordelia@zulip.com"),
                ("King Hamlet", "hamlet@zulip.com"),
                ("aaron", "AARON@zulip.com"),
            ]
            for i in range(options["extra_users"]):
                names.append(('Extra User %d' % (i,), 'extrauser%d@zulip.com' % (i,)))
            create_users(zulip_realm, names)
            iago = UserProfile.objects.get(email="iago@zulip.com")
            do_change_is_admin(iago, True)
            # Create public streams.
            stream_list = ["Verona", "Denmark", "Scotland", "Venice", "Rome"]
            stream_dict = {
                "Verona": {"description": "A city in Italy", "invite_only": False},
                "Denmark": {"description": "A Scandinavian country", "invite_only": False},
                "Scotland": {"description": "Located in the United Kingdom", "invite_only": False},
                "Venice": {"description": "A northeastern Italian city", "invite_only": False},
                "Rome": {"description": "Yet another Italian city", "invite_only": False}
            } # type: Dict[Text, Dict[Text, Any]]

            bulk_create_streams(zulip_realm, stream_dict)
            recipient_streams = [Stream.objects.get(name=name, realm=zulip_realm).id
                                 for name in stream_list] # type: List[int]
            # Create subscriptions to streams.  The following
            # algorithm will give each of the users a different but
            # deterministic subset of the streams (given a fixed list
            # of users).
            subscriptions_to_add = [] # type: List[Subscription]
            profiles = UserProfile.objects.select_related().all().order_by("email") # type: Sequence[UserProfile]
            for i, profile in enumerate(profiles):
                # Subscribe to some streams.
                for type_id in recipient_streams[:int(len(recipient_streams) *
                                                      float(i)/len(profiles)) + 1]:
                    r = Recipient.objects.get(type=Recipient.STREAM, type_id=type_id)
                    s = Subscription(
                        recipient=r,
                        user_profile=profile,
                        color=STREAM_ASSIGNMENT_COLORS[i % len(STREAM_ASSIGNMENT_COLORS)])

                    subscriptions_to_add.append(s)
            Subscription.objects.bulk_create(subscriptions_to_add)
        else:
            zulip_realm = get_realm("zulip")
            recipient_streams = [klass.type_id for klass in
                                 Recipient.objects.filter(type=Recipient.STREAM)]

        # Extract a list of all users
        user_profiles = list(UserProfile.objects.all()) # type: List[UserProfile]

        if not options["test_suite"]:
            # Populate users with some bar data
            for user in user_profiles:
                status = UserPresence.ACTIVE # type: int
                date = timezone.now()
                client = get_client("website")
                if user.full_name[0] <= 'H':
                    client = get_client("ZulipAndroid")
                UserPresence.objects.get_or_create(user_profile=user, client=client, timestamp=date, status=status)

        user_profiles_ids = [user_profile.id for user_profile in user_profiles]

        # Create several initial huddles
        for i in range(options["num_huddles"]):
            get_huddle(random.sample(user_profiles_ids, random.randint(3, 4)))

        # Create several initial pairs for personals
        personals_pairs = [random.sample(user_profiles_ids, 2)
                           for i in range(options["num_personals"])]

        threads = options["threads"]
        jobs = [] # type: List[Tuple[int, List[List[int]], Dict[str, Any], Callable[[str], int]]]
        for i in range(threads):
            count = options["num_messages"] // threads
            if i < options["num_messages"] % threads:
                count += 1
            jobs.append((count, personals_pairs, options, self.stdout.write))

        for job in jobs:
            send_messages(job)

        if options["delete"]:
            # Create the "website" and "API" clients; if we don't, the
            # default values in zerver/decorators.py will not work
            # with the Django test suite.
            get_client("website")
            get_client("API")

            if options["test_suite"]:
                # Create test users; the MIT ones are needed to test
                # the Zephyr mirroring codepaths.
                testsuite_mit_users = [
                    ("Fred Sipb (MIT)", "sipbtest@mit.edu"),
                    ("Athena Consulting Exchange User (MIT)", "starnine@mit.edu"),
                    ("Esp Classroom (MIT)", "espuser@mit.edu"),
                ]
                create_users(mit_realm, testsuite_mit_users)

            # These bots are directly referenced from code and thus
            # are needed for the test suite.
            all_realm_bots = [(bot['name'], bot['email_template'] % (settings.INTERNAL_BOT_DOMAIN,))
                              for bot in settings.INTERNAL_BOTS]
            zulip_realm_bots = [
                ("Zulip New User Bot", "new-user-bot@zulip.com"),
                ("Zulip Error Bot", "error-bot@zulip.com"),
                ("Zulip Default Bot", "default-bot@zulip.com"),
            ]
            for i in range(options["extra_bots"]):
                zulip_realm_bots.append(('Extra Bot %d' % (i,), 'extrabot%d@zulip.com' % (i,)))
            zulip_realm_bots.extend(all_realm_bots)
            create_users(zulip_realm, zulip_realm_bots, bot_type=UserProfile.DEFAULT_BOT)

            zulip_webhook_bots = [
                ("Zulip Webhook Bot", "webhook-bot@zulip.com"),
            ]
            create_users(zulip_realm, zulip_webhook_bots, bot_type=UserProfile.INCOMING_WEBHOOK_BOT)

            create_simple_community_realm()

            if not options["test_suite"]:
                # Initialize the email gateway bot as an API Super User
                email_gateway_bot = UserProfile.objects.get(email__iexact=settings.EMAIL_GATEWAY_BOT)
                email_gateway_bot.is_api_super_user = True
                email_gateway_bot.save()

                # To keep the messages.json fixtures file for the test
                # suite fast, don't add these users and subscriptions
                # when running populate_db for the test suite

                zulip_stream_dict = {
                    "devel": {"description": "For developing", "invite_only": False},
                    "all": {"description": "For everything", "invite_only": False},
                    "announce": {"description": "For announcements", "invite_only": False},
                    "design": {"description": "For design", "invite_only": False},
                    "support": {"description": "For support", "invite_only": False},
                    "social": {"description": "For socializing", "invite_only": False},
                    "test": {"description": "For testing", "invite_only": False},
                    "errors": {"description": "For errors", "invite_only": False},
                    "sales": {"description": "For sales discussion", "invite_only": False}
                }  # type: Dict[Text, Dict[Text, Any]]
                bulk_create_streams(zulip_realm, zulip_stream_dict)
                # Now that we've created the notifications stream, configure it properly.
                zulip_realm.notifications_stream = get_stream("announce", zulip_realm)
                zulip_realm.save(update_fields=['notifications_stream'])

                # Add a few default streams
                for default_stream_name in ["design", "devel", "social", "support"]:
                    DefaultStream.objects.create(realm=zulip_realm,
                                                 stream=get_stream(default_stream_name, zulip_realm))

                # Now subscribe everyone to these streams
                subscriptions_to_add = []
                profiles = UserProfile.objects.select_related().filter(realm=zulip_realm)
                for i, stream_name in enumerate(zulip_stream_dict):
                    stream = Stream.objects.get(name=stream_name, realm=zulip_realm)
                    recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream.id)
                    for profile in profiles:
                        # Subscribe to some streams.
                        s = Subscription(
                            recipient=recipient,
                            user_profile=profile,
                            color=STREAM_ASSIGNMENT_COLORS[i % len(STREAM_ASSIGNMENT_COLORS)])
                        subscriptions_to_add.append(s)
                Subscription.objects.bulk_create(subscriptions_to_add)

                # These bots are not needed by the test suite
                internal_zulip_users_nosubs = [
                    ("Zulip Commit Bot", "commit-bot@zulip.com"),
                    ("Zulip Trac Bot", "trac-bot@zulip.com"),
                    ("Zulip Nagios Bot", "nagios-bot@zulip.com"),
                ]
                create_users(zulip_realm, internal_zulip_users_nosubs, bot_type=UserProfile.DEFAULT_BOT)

            zulip_cross_realm_bots = [
                ("Zulip Feedback Bot", "feedback@zulip.com"),
            ]
            create_users(zulip_realm, zulip_cross_realm_bots, bot_type=UserProfile.DEFAULT_BOT)

            # Mark all messages as read
            UserMessage.objects.all().update(flags=UserMessage.flags.read)

            self.stdout.write("Successfully populated test database.\n")

recipient_hash = {} # type: Dict[int, Recipient]
def get_recipient_by_id(rid):
    # type: (int) -> Recipient
    if rid in recipient_hash:
        return recipient_hash[rid]
    return Recipient.objects.get(id=rid)

# Create some test messages, including:
# - multiple streams
# - multiple subjects per stream
# - multiple huddles
# - multiple personals converastions
# - multiple messages per subject
# - both single and multi-line content
def send_messages(data):
    # type: (Tuple[int, Sequence[Sequence[int]], Mapping[str, Any], Callable[[str], Any]]) -> int
    (tot_messages, personals_pairs, options, output) = data
    random.seed(os.getpid())
    texts = open("zilencer/management/commands/test_messages.txt", "r").readlines()
    offset = random.randint(0, len(texts))

    recipient_streams = [klass.id for klass in
                         Recipient.objects.filter(type=Recipient.STREAM)] # type: List[int]
    recipient_huddles = [h.id for h in Recipient.objects.filter(type=Recipient.HUDDLE)] # type: List[int]

    huddle_members = {} # type: Dict[int, List[int]]
    for h in recipient_huddles:
        huddle_members[h] = [s.user_profile.id for s in
                             Subscription.objects.filter(recipient_id=h)]

    num_messages = 0
    random_max = 1000000
    recipients = {} # type: Dict[int, Tuple[int, int, Dict[str, Any]]]
    while num_messages < tot_messages:
        saved_data = {} # type: Dict[str, Any]
        message = Message()
        message.sending_client = get_client('populate_db')
        length = random.randint(1, 5)
        lines = (t.strip() for t in texts[offset: offset + length])
        message.content = '\n'.join(lines)
        offset += length
        offset = offset % len(texts)

        randkey = random.randint(1, random_max)
        if (num_messages > 0 and
                random.randint(1, random_max) * 100. / random_max < options["stickyness"]):
            # Use an old recipient
            message_type, recipient_id, saved_data = recipients[num_messages - 1]
            if message_type == Recipient.PERSONAL:
                personals_pair = saved_data['personals_pair']
                random.shuffle(personals_pair)
            elif message_type == Recipient.STREAM:
                message.subject = saved_data['subject']
                message.recipient = get_recipient_by_id(recipient_id)
            elif message_type == Recipient.HUDDLE:
                message.recipient = get_recipient_by_id(recipient_id)
        elif (randkey <= random_max * options["percent_huddles"] / 100.):
            message_type = Recipient.HUDDLE
            message.recipient = get_recipient_by_id(random.choice(recipient_huddles))
        elif (randkey <= random_max * (options["percent_huddles"] + options["percent_personals"]) / 100.):
            message_type = Recipient.PERSONAL
            personals_pair = random.choice(personals_pairs)
            random.shuffle(personals_pair)
        elif (randkey <= random_max * 1.0):
            message_type = Recipient.STREAM
            message.recipient = get_recipient_by_id(random.choice(recipient_streams))

        if message_type == Recipient.HUDDLE:
            sender_id = random.choice(huddle_members[message.recipient.id])
            message.sender = get_user_profile_by_id(sender_id)
        elif message_type == Recipient.PERSONAL:
            message.recipient = Recipient.objects.get(type=Recipient.PERSONAL,
                                                      type_id=personals_pair[0])
            message.sender = get_user_profile_by_id(personals_pair[1])
            saved_data['personals_pair'] = personals_pair
        elif message_type == Recipient.STREAM:
            stream = Stream.objects.get(id=message.recipient.type_id)
            # Pick a random subscriber to the stream
            message.sender = random.choice(Subscription.objects.filter(
                recipient=message.recipient)).user_profile
            message.subject = stream.name + Text(random.randint(1, 3))
            saved_data['subject'] = message.subject

        message.pub_date = timezone.now()
        do_send_messages([{'message': message}])

        recipients[num_messages] = (message_type, message.recipient.id, saved_data)
        num_messages += 1
    return tot_messages

def create_simple_community_realm():
    # type: () -> None
    simple_realm = Realm.objects.create(
        string_id="simple", name="Simple Realm", restricted_to_domain=False,
        invite_required=False, org_type=Realm.COMMUNITY, domain="simple.com")

    names = [
        ("alice", "alice@example.com"),
        ("bob", "bob@foo.edu"),
        ("cindy", "cindy@foo.tv"),
    ]
    create_users(simple_realm, names)

    user_profiles = UserProfile.objects.filter(realm__string_id='simple')
    create_user_presences(user_profiles)

def create_user_presences(user_profiles):
    # type: (Iterable[UserProfile]) -> None
    for user in user_profiles:
        status = 1 # type: int
        date = timezone.now()
        client = get_client("website")
        UserPresence.objects.get_or_create(
            user_profile=user,
            client=client,
            timestamp=date,
            status=status)
