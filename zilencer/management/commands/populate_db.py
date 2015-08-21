from __future__ import absolute_import

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from django.contrib.sites.models import Site
from zerver.models import Message, UserProfile, Stream, Recipient, Client, \
    Subscription, Huddle, get_huddle, Realm, UserMessage, \
    get_huddle_hash, clear_database, get_client, get_user_profile_by_id, \
    split_email_to_domain, email_to_username
from zerver.lib.actions import do_send_message, set_default_streams, \
    do_activate_user, do_deactivate_user, do_change_password, do_change_is_admin
from zerver.lib.parallel import run_parallel
from django.db.models import Count
from django.conf import settings
from zerver.lib.bulk_create import bulk_create_realms, \
    bulk_create_streams, bulk_create_users, bulk_create_huddles, \
    bulk_create_clients
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import MAX_MESSAGE_LENGTH
from zerver.models import DefaultStream, get_stream
from zilencer.models import Deployment

import ujson
import datetime
import random
import glob
import os
from optparse import make_option

settings.TORNADO_SERVER = None

def create_users(realms, name_list, bot=False):
    user_set = set()
    for full_name, email in name_list:
        short_name = email_to_username(email)
        user_set.add((email, full_name, short_name, True))
    bulk_create_users(realms, user_set, bot)

def create_streams(realms, realm, stream_list):
    stream_set = set()
    for stream_name in stream_list:
        stream_set.add((realm.domain, stream_name))
    bulk_create_streams(realms, stream_set)

class Command(BaseCommand):
    help = "Populate a test database"

    option_list = BaseCommand.option_list + (
        make_option('-n', '--num-messages',
                    dest='num_messages',
                    type='int',
                    default=600,
                    help='The number of messages to create.'),
        make_option('--extra-users',
                    dest='extra_users',
                    type='int',
                    default=0,
                    help='The number of extra users to create'),
        make_option('--huddles',
                    dest='num_huddles',
                    type='int',
                    default=3,
                    help='The number of huddles to create.'),
        make_option('--personals',
                    dest='num_personals',
                    type='int',
                    default=6,
                    help='The number of personal pairs to create.'),
        make_option('--threads',
                    dest='threads',
                    type='int',
                    default=10,
                    help='The number of threads to use.'),
        make_option('--percent-huddles',
                    dest='percent_huddles',
                    type='float',
                    default=15,
                    help='The percent of messages to be huddles.'),
        make_option('--percent-personals',
                    dest='percent_personals',
                    type='float',
                    default=15,
                    help='The percent of messages to be personals.'),
        make_option('--stickyness',
                    dest='stickyness',
                    type='float',
                    default=20,
                    help='The percent of messages to repeat recent folks.'),
        make_option('--nodelete',
                    action="store_false",
                    default=True,
                    dest='delete',
                    help='Whether to delete all the existing messages.'),
        make_option('--test-suite',
                    default=False,
                    action="store_true",
                    help='Whether to delete all the existing messages.'),
        make_option('--replay-old-messages',
                    action="store_true",
                    default=False,
                    dest='replay_old_messages',
                    help='Whether to replace the log of old messages.'),
        )

    def handle(self, **options):
        if options["percent_huddles"] + options["percent_personals"] > 100:
            self.stderr.write("Error!  More than 100% of messages allocated.\n")
            return

        if options["delete"]:
            # Start by clearing all the data in our database
            clear_database()

            # Create our two default realms
            zulip_realm = Realm.objects.create(domain="zulip.com", name="Zulip Dev")
            if options["test_suite"]:
                Realm.objects.create(domain="mit.edu")
            realms = {}
            for realm in Realm.objects.all():
                realms[realm.domain] = realm

            # Create test Users (UserProfiles are automatically created,
            # as are subscriptions to the ability to receive personals).
            names = [("Othello, the Moor of Venice", "othello@zulip.com"), ("Iago", "iago@zulip.com"),
                     ("Prospero from The Tempest", "prospero@zulip.com"),
                     ("Cordelia Lear", "cordelia@zulip.com"), ("King Hamlet", "hamlet@zulip.com")]
            for i in xrange(options["extra_users"]):
                names.append(('Extra User %d' % (i,), 'extrauser%d@zulip.com' % (i,)))
            create_users(realms, names)
            iago = UserProfile.objects.get(email="iago@zulip.com")
            do_change_is_admin(iago, True)
            # Create public streams.
            stream_list = ["Verona", "Denmark", "Scotland", "Venice", "Rome"]
            create_streams(realms, zulip_realm, stream_list)
            recipient_streams = [Stream.objects.get(name=name, realm=zulip_realm).id for name in stream_list]

            # Create subscriptions to streams
            subscriptions_to_add = []
            profiles = UserProfile.objects.select_related().all()
            for i, profile in enumerate(profiles):
                # Subscribe to some streams.
                for type_id in recipient_streams[:int(len(recipient_streams) *
                                                      float(i)/len(profiles)) + 1]:
                    r = Recipient.objects.get(type=Recipient.STREAM, type_id=type_id)
                    s = Subscription(recipient=r, user_profile=profile)
                    subscriptions_to_add.append(s)
            Subscription.objects.bulk_create(subscriptions_to_add)
        else:
            zulip_realm = Realm.objects.get(domain="zulip.com")
            recipient_streams = [klass.type_id for klass in
                                 Recipient.objects.filter(type=Recipient.STREAM)]

        # Extract a list of all users
        user_profiles = [user_profile.id for user_profile in UserProfile.objects.all()]

        # Create several initial huddles
        for i in xrange(options["num_huddles"]):
            get_huddle(random.sample(user_profiles, random.randint(3, 4)))

        # Create several initial pairs for personals
        personals_pairs = [random.sample(user_profiles, 2)
                           for i in xrange(options["num_personals"])]

        threads = options["threads"]
        jobs = []
        for i in xrange(threads):
            count = options["num_messages"] / threads
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
                create_users(realms, testsuite_mit_users)

            # These bots are directly referenced from code and thus
            # are needed for the test suite.
            all_realm_bots = [(bot['name'], bot['email_template'] % (settings.INTERNAL_BOT_DOMAIN,))
                              for bot in settings.INTERNAL_BOTS]
            zulip_realm_bots = [
                ("Zulip New User Bot", "new-user-bot@zulip.com"),
                ("Zulip Error Bot", "error-bot@zulip.com"),
                ]
            zulip_realm_bots.extend(all_realm_bots)
            create_users(realms, zulip_realm_bots, bot=True)

            if not options["test_suite"]:
                # To keep the messages.json fixtures file for the test
                # suite fast, don't add these users and subscriptions
                # when running populate_db for the test suite

                zulip_stream_list = ["devel", "all", "zulip", "design", "support", "social", "test",
                                      "errors", "sales"]
                create_streams(realms, zulip_realm, zulip_stream_list)

                # Add a few default streams
                for stream_name in ["design", "devel", "social", "support"]:
                    DefaultStream.objects.create(realm=zulip_realm, stream=get_stream(stream_name, zulip_realm))

                # Now subscribe everyone to these streams
                subscriptions_to_add = []
                profiles = UserProfile.objects.select_related().filter(realm=zulip_realm)
                for cls in zulip_stream_list:
                    stream = Stream.objects.get(name=cls, realm=zulip_realm)
                    recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream.id)
                    for profile in profiles:
                        # Subscribe to some streams.
                        s = Subscription(recipient=recipient, user_profile=profile)
                        subscriptions_to_add.append(s)
                Subscription.objects.bulk_create(subscriptions_to_add)

                # These bots are not needed by the test suite
                internal_zulip_users_nosubs = [
                    ("Zulip Commit Bot", "commit-bot@zulip.com"),
                    ("Zulip Trac Bot", "trac-bot@zulip.com"),
                    ("Zulip Nagios Bot", "nagios-bot@zulip.com"),
                    ("Zulip Feedback Bot", "feedback@zulip.com"),
                    ]
                create_users(realms, internal_zulip_users_nosubs, bot=True)

            # Mark all messages as read
            UserMessage.objects.all().update(flags=UserMessage.flags.read)

            self.stdout.write("Successfully populated test database.\n")
        if options["replay_old_messages"]:
            restore_saved_messages()

recipient_hash = {}
def get_recipient_by_id(rid):
    if rid in recipient_hash:
        return recipient_hash[rid]
    return Recipient.objects.get(id=rid)

def restore_saved_messages():
    old_messages = []
    duplicate_suppression_hash = {}

    stream_dict = {}
    user_set = set()
    email_set = set([u.email for u in UserProfile.objects.all()])
    realm_set = set()
    # Initial client_set is nonempty temporarily because we don't have
    # clients in logs at all right now -- later we can start with nothing.
    client_set = set(["populate_db", "website", "zephyr_mirror"])
    huddle_user_set = set()
    # First, determine all the objects our messages will need.
    print datetime.datetime.now(), "Creating realms/streams/etc..."
    def process_line(line):
        old_message_json = line.strip()

        # Due to populate_db's shakespeare mode, we have a lot of
        # duplicate messages in our log that only differ in their
        # logged ID numbers (same timestamp, content, etc.).  With
        # sqlite, bulk creating those messages won't work properly: in
        # particular, the first 100 messages will actually only result
        # in 20 rows ending up in the target table, which screws up
        # the below accounting where for handling changing
        # subscriptions, we assume that the Nth row populate_db
        # created goes with the Nth non-subscription row of the input
        # So suppress the duplicates when using sqlite.
        if "sqlite" in settings.DATABASES["default"]["ENGINE"]:
            tmp_message = ujson.loads(old_message_json)
            tmp_message['id'] = '1'
            duplicate_suppression_key = ujson.dumps(tmp_message)
            if duplicate_suppression_key in duplicate_suppression_hash:
                return
            duplicate_suppression_hash[duplicate_suppression_key] = True

        old_message = ujson.loads(old_message_json)
        message_type = old_message["type"]

        # Lower case emails and domains; it will screw up
        # deduplication if we don't
        def fix_email(email):
            return email.strip().lower()

        if message_type in ["stream", "huddle", "personal"]:
            old_message["sender_email"] = fix_email(old_message["sender_email"])
            # Fix the length on too-long messages before we start processing them
            if len(old_message["content"]) > MAX_MESSAGE_LENGTH:
                old_message["content"] = "[ This message was deleted because it was too long ]"
        if message_type in ["subscription_added", "subscription_removed"]:
            old_message["domain"] = old_message["domain"].lower()
            old_message["user"] = fix_email(old_message["user"])
        elif message_type == "subscription_property":
            old_message["user"] = fix_email(old_message["user"])
        elif message_type == "user_email_changed":
            old_message["old_email"] = fix_email(old_message["old_email"])
            old_message["new_email"] = fix_email(old_message["new_email"])
        elif message_type.startswith("user_"):
            old_message["user"] = fix_email(old_message["user"])
        elif message_type.startswith("enable_"):
            old_message["user"] = fix_email(old_message["user"])

        if message_type == 'personal':
            old_message["recipient"][0]["email"] = fix_email(old_message["recipient"][0]["email"])
        elif message_type == "huddle":
            for i in xrange(len(old_message["recipient"])):
                old_message["recipient"][i]["email"] = fix_email(old_message["recipient"][i]["email"])

        old_messages.append(old_message)

        if message_type in ["subscription_added", "subscription_removed"]:
            stream_name = old_message["name"].strip()
            canon_stream_name = stream_name.lower()
            if canon_stream_name not in stream_dict:
                stream_dict[(old_message["domain"], canon_stream_name)] = \
                    (old_message["domain"], stream_name)
        elif message_type == "user_created":
            user_set.add((old_message["user"], old_message["full_name"], old_message["short_name"], False))
        elif message_type == "realm_created":
            realm_set.add(old_message["domain"])

        if message_type not in ["stream", "huddle", "personal"]:
            return

        sender_email = old_message["sender_email"]

        domain = split_email_to_domain(sender_email)
        realm_set.add(domain)

        if old_message["sender_email"] not in email_set:
            user_set.add((old_message["sender_email"],
                          old_message["sender_full_name"],
                          old_message["sender_short_name"],
                          False))

        if 'sending_client' in old_message:
            client_set.add(old_message['sending_client'])

        if message_type == 'stream':
            stream_name = old_message["recipient"].strip()
            canon_stream_name = stream_name.lower()
            if canon_stream_name not in stream_dict:
                stream_dict[(domain, canon_stream_name)] = (domain, stream_name)
        elif message_type == 'personal':
            u = old_message["recipient"][0]
            if u["email"] not in email_set:
                user_set.add((u["email"], u["full_name"], u["short_name"], False))
                email_set.add(u["email"])
        elif message_type == 'huddle':
            for u in old_message["recipient"]:
                user_set.add((u["email"], u["full_name"], u["short_name"], False))
                if u["email"] not in email_set:
                    user_set.add((u["email"], u["full_name"], u["short_name"], False))
                    email_set.add(u["email"])
            huddle_user_set.add(tuple(sorted(set(u["email"] for u in old_message["recipient"]))))
        else:
            raise ValueError('Bad message type')

    event_glob = os.path.join(settings.EVENT_LOG_DIR, 'events.*')
    for filename in sorted(glob.glob(event_glob)):
        with file(filename, "r") as message_log:
            for line in message_log.readlines():
                process_line(line)

    stream_recipients = {}
    user_recipients = {}
    huddle_recipients = {}

    # Then, create the objects our messages need.
    print datetime.datetime.now(), "Creating realms..."
    bulk_create_realms(realm_set)

    realms = {}
    for realm in Realm.objects.all():
        realms[realm.domain] = realm

    print datetime.datetime.now(), "Creating clients..."
    bulk_create_clients(client_set)

    clients = {}
    for client in Client.objects.all():
        clients[client.name] = client

    print datetime.datetime.now(), "Creating streams..."
    bulk_create_streams(realms, stream_dict.values())

    streams = {}
    for stream in Stream.objects.all():
        streams[stream.id] = stream
    for recipient in Recipient.objects.filter(type=Recipient.STREAM):
        stream_recipients[(streams[recipient.type_id].realm_id,
                           streams[recipient.type_id].name.lower())] = recipient

    print datetime.datetime.now(), "Creating users..."
    bulk_create_users(realms, user_set)

    users = {}
    users_by_id = {}
    for user_profile in UserProfile.objects.select_related().all():
        users[user_profile.email] = user_profile
        users_by_id[user_profile.id] = user_profile
    for recipient in Recipient.objects.filter(type=Recipient.PERSONAL):
        user_recipients[users_by_id[recipient.type_id].email] = recipient

    print datetime.datetime.now(), "Creating huddles..."
    bulk_create_huddles(users, huddle_user_set)

    huddles_by_id = {}
    for huddle in Huddle.objects.all():
        huddles_by_id[huddle.id] = huddle
    for recipient in Recipient.objects.filter(type=Recipient.HUDDLE):
        huddle_recipients[huddles_by_id[recipient.type_id].huddle_hash] = recipient

    # TODO: Add a special entry type in the log that is a subscription
    # change and import those as we go to make subscription changes
    # take effect!
    print datetime.datetime.now(), "Importing subscriptions..."
    subscribers = {}
    for s in Subscription.objects.select_related().all():
        if s.active:
            subscribers.setdefault(s.recipient.id, set()).add(s.user_profile.id)

    # Then create all the messages, without talking to the DB!
    print datetime.datetime.now(), "Importing messages, part 1..."
    first_message_id = None
    if Message.objects.exists():
        first_message_id = Message.objects.all().order_by("-id")[0].id + 1

    messages_to_create = []
    for idx, old_message in enumerate(old_messages):
        message_type = old_message["type"]
        if message_type not in ["stream", "huddle", "personal"]:
            continue

        message = Message()

        sender_email = old_message["sender_email"]
        domain = split_email_to_domain(sender_email)
        realm = realms[domain]

        message.sender = users[sender_email]
        type_hash = {"stream": Recipient.STREAM,
                     "huddle": Recipient.HUDDLE,
                     "personal": Recipient.PERSONAL}

        if 'sending_client' in old_message:
            message.sending_client = clients[old_message['sending_client']]
        elif sender_email in ["othello@zulip.com", "iago@zulip.com", "prospero@zulip.com",
                              "cordelia@zulip.com", "hamlet@zulip.com"]:
            message.sending_client = clients['populate_db']
        elif realm.domain == "zulip.com":
            message.sending_client = clients["website"]
        elif realm.domain == "mit.edu":
            message.sending_client = clients['zephyr_mirror']
        else:
            message.sending_client = clients['populate_db']

        message.type = type_hash[message_type]
        message.content = old_message["content"]
        message.subject = old_message["subject"]
        message.pub_date = timestamp_to_datetime(old_message["timestamp"])

        if message.type == Recipient.PERSONAL:
            message.recipient = user_recipients[old_message["recipient"][0]["email"]]
        elif message.type == Recipient.STREAM:
            message.recipient = stream_recipients[(realm.id,
                                                   old_message["recipient"].lower())]
        elif message.type == Recipient.HUDDLE:
            huddle_hash = get_huddle_hash([users[u["email"]].id
                                           for u in old_message["recipient"]])
            message.recipient = huddle_recipients[huddle_hash]
        else:
            raise ValueError('Bad message type')
        messages_to_create.append(message)

    print datetime.datetime.now(), "Importing messages, part 2..."
    Message.objects.bulk_create(messages_to_create)
    messages_to_create = []

    # Finally, create all the UserMessage objects
    print datetime.datetime.now(), "Importing usermessages, part 1..."
    personal_recipients = {}
    for r in Recipient.objects.filter(type = Recipient.PERSONAL):
        personal_recipients[r.id] = True

    all_messages = Message.objects.all()
    user_messages_to_create = []

    messages_by_id = {}
    for message in all_messages:
        messages_by_id[message.id] = message

    if len(messages_by_id) == 0:
        print datetime.datetime.now(), "No old messages to replay"
        return

    if first_message_id is None:
        first_message_id = min(messages_by_id.keys())

    tot_user_messages = 0
    pending_subs = {}
    current_message_id = first_message_id
    pending_colors = {}
    for old_message in old_messages:
        message_type = old_message["type"]
        if message_type == 'subscription_added':
            stream_key = (realms[old_message["domain"]].id, old_message["name"].strip().lower())
            subscribers.setdefault(stream_recipients[stream_key].id,
                                   set()).add(users[old_message["user"]].id)
            pending_subs[(stream_recipients[stream_key].id,
                          users[old_message["user"]].id)] = True
            continue
        elif message_type == "subscription_removed":
            stream_key = (realms[old_message["domain"]].id, old_message["name"].strip().lower())
            user_id = users[old_message["user"]].id
            subscribers.setdefault(stream_recipients[stream_key].id, set())
            try:
                subscribers[stream_recipients[stream_key].id].remove(user_id)
            except KeyError:
                print "Error unsubscribing %s from %s: not subscribed" % (
                    old_message["user"], old_message["name"])
            pending_subs[(stream_recipients[stream_key].id,
                          users[old_message["user"]].id)] = False
            continue
        elif message_type == "user_activated" or message_type == "user_created":
            # These are rare, so just handle them the slow way
            user_profile = users[old_message["user"]]
            join_date = timestamp_to_datetime(old_message['timestamp'])
            do_activate_user(user_profile, log=False, join_date=join_date)
            # Update the cache of users to show this user as activated
            users_by_id[user_profile.id] = user_profile
            users[old_message["user"]] = user_profile
            continue
        elif message_type == "user_deactivated":
            user_profile = users[old_message["user"]]
            do_deactivate_user(user_profile, log=False)
            continue
        elif message_type == "user_change_password":
            # Just handle these the slow way
            user_profile = users[old_message["user"]]
            do_change_password(user_profile, old_message["pwhash"], log=False,
                               hashed_password=True)
            continue
        elif message_type == "user_change_full_name":
            # Just handle these the slow way
            user_profile = users[old_message["user"]]
            user_profile.full_name = old_message["full_name"]
            user_profile.save(update_fields=["full_name"])
            continue
        elif message_type == "enable_desktop_notifications_changed":
            # Just handle these the slow way
            user_profile = users[old_message["user"]]
            user_profile.enable_desktop_notifications = (old_message["enable_desktop_notifications"] != "false")
            user_profile.save(update_fields=["enable_desktop_notifications"])
            continue
        elif message_type == "enable_sounds_changed":
            user_profile = users[old_message["user"]]
            user_profile.enable_sounds = (old_message["enable_sounds"] != "false")
            user_profile.save(update_fields=["enable_sounds"])
        elif message_type == "enable_offline_email_notifications_changed":
            user_profile = users[old_message["user"]]
            user_profile.enable_offline_email_notifications = (old_message["enable_offline_email_notifications"] != "false")
            user_profile.save(update_fields=["enable_offline_email_notifications"])
            continue
        elif message_type == "enable_offline_push_notifications_changed":
            user_profile = users[old_message["user"]]
            user_profile.enable_offline_push_notifications = (old_message["enable_offline_push_notifications"] != "false")
            user_profile.save(update_fields=["enable_offline_push_notifications"])
            continue
        elif message_type == "default_streams":
            set_default_streams(Realm.objects.get(domain=old_message["domain"]),
                                old_message["streams"])
            continue
        elif message_type == "subscription_property":
            property_name = old_message.get("property")
            if property_name == "stream_color" or property_name == "color":
                color = old_message.get("color", old_message.get("value"))
                pending_colors[(old_message["user"],
                                old_message["stream_name"].lower())] = color
            elif property_name in ["in_home_view", "notifications"]:
                # TODO: Handle this
                continue
            else:
                raise RuntimeError("Unknown property %s" % (property_name,))
            continue
        elif message_type == "realm_created":
            # No action required
            continue
        elif message_type in ["user_email_changed", "update_onboarding", "update_message"]:
            # TODO: Handle these
            continue
        if message_type not in ["stream", "huddle", "personal"]:
            raise RuntimeError("Unexpected message type %s" % (message_type,))

        message = messages_by_id[current_message_id]
        current_message_id += 1

        if message.recipient_id not in subscribers:
            # Nobody received this message -- probably due to our
            # subscriptions being out-of-date.
            continue

        recipient_user_ids = set()
        for user_profile_id in subscribers[message.recipient_id]:
            recipient_user_ids.add(user_profile_id)
        if message.recipient_id in personal_recipients:
            # Include the sender in huddle recipients
            recipient_user_ids.add(message.sender_id)

        for user_profile_id in recipient_user_ids:
            if users_by_id[user_profile_id].is_active:
                um = UserMessage(user_profile_id=user_profile_id,
                                 message=message)
                user_messages_to_create.append(um)

        if len(user_messages_to_create) > 100000:
            tot_user_messages += len(user_messages_to_create)
            UserMessage.objects.bulk_create(user_messages_to_create)
            user_messages_to_create = []

    print datetime.datetime.now(), "Importing usermessages, part 2..."
    tot_user_messages += len(user_messages_to_create)
    UserMessage.objects.bulk_create(user_messages_to_create)

    print datetime.datetime.now(), "Finalizing subscriptions..."
    current_subs = {}
    current_subs_obj = {}
    for s in Subscription.objects.select_related().all():
        current_subs[(s.recipient_id, s.user_profile_id)] = s.active
        current_subs_obj[(s.recipient_id, s.user_profile_id)] = s

    subscriptions_to_add = []
    subscriptions_to_change = []
    for pending_sub in pending_subs.keys():
        (recipient_id, user_profile_id) = pending_sub
        current_state = current_subs.get(pending_sub)
        if pending_subs[pending_sub] == current_state:
            # Already correct in the database
            continue
        elif current_state is not None:
            subscriptions_to_change.append((pending_sub, pending_subs[pending_sub]))
            continue

        s = Subscription(recipient_id=recipient_id,
                         user_profile_id=user_profile_id,
                         active=pending_subs[pending_sub])
        subscriptions_to_add.append(s)
    Subscription.objects.bulk_create(subscriptions_to_add)
    for (sub, active) in subscriptions_to_change:
        current_subs_obj[sub].active = active
        current_subs_obj[sub].save(update_fields=["active"])

    subs = {}
    for sub in Subscription.objects.all():
        subs[(sub.user_profile_id, sub.recipient_id)] = sub

    # TODO: do restore of subscription colors -- we're currently not
    # logging changes so there's little point in having the code :(

    print datetime.datetime.now(), "Finished importing %s messages (%s usermessages)" % \
        (len(all_messages), tot_user_messages)

    site = Site.objects.get_current()
    site.domain = 'zulip.com'
    site.save()

    print datetime.datetime.now(), "Filling in user pointers..."

    # Set restored pointers to the very latest messages
    for user_profile in UserProfile.objects.all():
        try:
            top = UserMessage.objects.filter(
                user_profile_id=user_profile.id).order_by("-message")[0]
            user_profile.pointer = top.message_id
        except IndexError:
            user_profile.pointer = -1
        user_profile.save(update_fields=["pointer"])

    print datetime.datetime.now(), "Done replaying old messages"

# Create some test messages, including:
# - multiple streams
# - multiple subjects per stream
# - multiple huddles
# - multiple personals converastions
# - multiple messages per subject
# - both single and multi-line content
def send_messages(data):
    (tot_messages, personals_pairs, options, output) = data
    random.seed(os.getpid())
    texts = file("zilencer/management/commands/test_messages.txt", "r").readlines()
    offset = random.randint(0, len(texts))

    recipient_streams = [klass.id for klass in
                         Recipient.objects.filter(type=Recipient.STREAM)]
    recipient_huddles = [h.id for h in Recipient.objects.filter(type=Recipient.HUDDLE)]

    huddle_members = {}
    for h in recipient_huddles:
        huddle_members[h] = [s.user_profile.id for s in
                             Subscription.objects.filter(recipient_id=h)]

    num_messages = 0
    random_max = 1000000
    recipients = {}
    while num_messages < tot_messages:
        saved_data = ''
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
                personals_pair = saved_data
                random.shuffle(personals_pair)
            elif message_type == Recipient.STREAM:
                message.subject = saved_data
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
            saved_data = personals_pair
        elif message_type == Recipient.STREAM:
            stream = Stream.objects.get(id=message.recipient.type_id)
            # Pick a random subscriber to the stream
            message.sender = random.choice(Subscription.objects.filter(
                    recipient=message.recipient)).user_profile
            message.subject = stream.name + str(random.randint(1, 3))
            saved_data = message.subject

        message.pub_date = now()
        do_send_message(message)

        recipients[num_messages] = [message_type, message.recipient.id, saved_data]
        num_messages += 1
    return tot_messages
