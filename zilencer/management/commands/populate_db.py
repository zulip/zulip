import itertools
import os
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

import bmemcached
import orjson
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.files.base import File
from django.core.management import call_command
from django.core.management.base import CommandParser
from django.core.validators import validate_email
from django.db import connection
from django.db.models import F
from django.db.models.signals import post_delete
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from scripts.lib.zulip_tools import get_or_create_dev_uuid_var_path
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.create_realm import do_create_realm
from zerver.actions.custom_profile_fields import (
    do_update_user_custom_profile_data_if_changed,
    try_add_realm_custom_profile_field,
    try_add_realm_default_custom_profile_field,
)
from zerver.actions.message_send import build_message_send_dict, do_send_messages
from zerver.actions.realm_emoji import check_add_realm_emoji
from zerver.actions.realm_linkifiers import do_add_linkifier
from zerver.actions.realm_settings import (
    do_set_realm_moderation_request_channel,
    do_set_realm_property,
)
from zerver.actions.scheduled_messages import check_schedule_message
from zerver.actions.streams import bulk_add_subscriptions
from zerver.actions.user_groups import create_user_group_in_database
from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.users import do_change_user_role
from zerver.lib.bulk_create import bulk_create_streams
from zerver.lib.generate_test_data import create_test_data, generate_topics
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.onboarding import create_if_missing_realm_internal_bots
from zerver.lib.onboarding_steps import ALL_ONBOARDING_STEPS
from zerver.lib.push_notifications import logger as push_notifications_logger
from zerver.lib.remote_server import get_realms_info_for_push_bouncer
from zerver.lib.server_initialization import create_internal_realm, create_users
from zerver.lib.storage import static_path
from zerver.lib.stream_color import STREAM_ASSIGNMENT_COLORS
from zerver.lib.stream_subscription import bulk_create_stream_subscriptions
from zerver.lib.types import AnalyticsDataUploadLevel, ProfileFieldData
from zerver.lib.users import add_service
from zerver.lib.utils import generate_api_key
from zerver.models import (
    AlertWord,
    Client,
    CustomProfileField,
    DefaultStream,
    DirectMessageGroup,
    Draft,
    Message,
    Reaction,
    Realm,
    RealmAuditLog,
    RealmDomain,
    RealmUserDefault,
    Recipient,
    Service,
    Stream,
    Subscription,
    UserMessage,
    UserPresence,
    UserProfile,
)
from zerver.models.alert_words import flush_alert_word
from zerver.models.clients import get_client
from zerver.models.groups import NamedUserGroup, SystemGroups
from zerver.models.onboarding_steps import OnboardingStep
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zerver.models.recipients import get_or_create_direct_message_group
from zerver.models.streams import get_stream
from zerver.models.users import get_user, get_user_by_delivery_email, get_user_profile_by_id
from zilencer.models import RemoteRealm, RemoteZulipServer, RemoteZulipServerAuditLog
from zilencer.views import update_remote_realm_data_for_server

# Disable the push notifications bouncer to avoid enqueuing updates in
# maybe_enqueue_audit_log_upload during early setup.
settings.ZULIP_SERVICE_PUSH_NOTIFICATIONS = False
settings.ZULIP_SERVICE_SUBMIT_USAGE_STATISTICS = False
settings.ZULIP_SERVICE_SECURITY_ALERTS = False
settings.ANALYTICS_DATA_UPLOAD_LEVEL = AnalyticsDataUploadLevel.NONE
settings.USING_TORNADO = False
# Disable using memcached caches to avoid 'unsupported pickle
# protocol' errors if `populate_db` is run with a different Python
# from `run-dev`.
default_cache = settings.CACHES["default"]
settings.CACHES["default"] = {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
}

DEFAULT_EMOJIS = [
    ("+1", "1f44d"),
    ("smiley", "1f603"),
    ("eyes", "1f440"),
    ("crying_cat_face", "1f63f"),
    ("arrow_up", "2b06"),
    ("confetti_ball", "1f38a"),
    ("hundred_points", "1f4af"),
]


def clear_database() -> None:
    # Hacky function only for use inside populate_db.  Designed to
    # allow running populate_db repeatedly in series to work without
    # flushing memcached or clearing the database manually.

    # With `zproject.test_settings`, we aren't using real memcached
    # and; we only need to flush memcached if we're populating a
    # database that would be used with it (i.e. zproject.dev_settings).
    if default_cache["BACKEND"] == "zerver.lib.singleton_bmemcached.SingletonBMemcached":
        memcached_client = bmemcached.Client(
            (default_cache["LOCATION"],),
            **default_cache["OPTIONS"],
        )
        try:
            memcached_client.flush_all()
        finally:
            memcached_client.disconnect_all()

    model: Any = None  # Hack because mypy doesn't know these are model classes

    # The after-delete signal on this just updates caches, and slows
    # down the deletion noticeably.  Remove the signal and replace it
    # after we're done.
    post_delete.disconnect(flush_alert_word, sender=AlertWord)
    for model in [
        Message,
        Stream,
        AlertWord,
        UserProfile,
        Recipient,
        Realm,
        Subscription,
        DirectMessageGroup,
        UserMessage,
        Client,
        DefaultStream,
        RemoteRealm,
        RemoteZulipServer,
    ]:
        model.objects.all().delete()
    Session.objects.all().delete()
    post_delete.connect(flush_alert_word, sender=AlertWord)


def subscribe_users_to_streams(realm: Realm, stream_dict: dict[str, dict[str, Any]]) -> None:
    subscriptions_to_add = []
    event_time = timezone_now()
    all_subscription_logs = []
    subscriber_count_changes: dict[int, set[int]] = defaultdict(set)
    profiles = UserProfile.objects.select_related("realm").filter(realm=realm)
    for i, stream_name in enumerate(stream_dict):
        stream = Stream.objects.get(name=stream_name, realm=realm)
        recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream.id)
        for profile in profiles:
            # Subscribe to some streams.
            s = Subscription(
                recipient=recipient,
                user_profile=profile,
                is_user_active=profile.is_active,
                color=STREAM_ASSIGNMENT_COLORS[i % len(STREAM_ASSIGNMENT_COLORS)],
            )
            subscriptions_to_add.append(s)
            if profile.is_active:
                subscriber_count_changes[stream.id].add(profile.id)

            log = RealmAuditLog(
                realm=profile.realm,
                modified_user=profile,
                modified_stream=stream,
                event_last_message_id=0,
                event_type=AuditLogEventType.SUBSCRIPTION_CREATED,
                event_time=event_time,
            )
            all_subscription_logs.append(log)
    bulk_create_stream_subscriptions(subs=subscriptions_to_add, streams=subscriber_count_changes)
    RealmAuditLog.objects.bulk_create(all_subscription_logs)


def create_alert_words(realm_id: int) -> None:
    user_ids = UserProfile.objects.filter(
        realm_id=realm_id,
        is_bot=False,
        is_active=True,
    ).values_list("id", flat=True)

    alert_words = [
        "algorithms",
        "complexity",
        "founded",
        "galaxy",
        "grammar",
        "illustrious",
        "natural",
        "objective",
        "people",
        "robotics",
        "study",
    ]

    recs: list[AlertWord] = []
    for user_id in user_ids:
        random.shuffle(alert_words)
        recs.extend(
            AlertWord(realm_id=realm_id, user_profile_id=user_id, word=word)
            for word in alert_words[:4]
        )

    AlertWord.objects.bulk_create(recs)


class Command(ZulipBaseCommand):
    help = "Populate a test database"

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-n", "--num-messages", type=int, default=1000, help="The number of messages to create."
        )

        parser.add_argument(
            "-o",
            "--oldest-message-days",
            type=int,
            default=5,
            help="The start of the time range where messages could have been sent.",
        )

        parser.add_argument(
            "-b",
            "--batch-size",
            type=int,
            default=1000,
            help="How many messages to process in a single batch",
        )

        parser.add_argument(
            "--extra-users", type=int, default=0, help="The number of extra users to create"
        )

        parser.add_argument(
            "--extra-bots", type=int, default=0, help="The number of extra bots to create"
        )

        parser.add_argument(
            "--extra-streams", type=int, default=0, help="The number of extra streams to create"
        )

        parser.add_argument("--max-topics", type=int, help="The number of maximum topics to create")

        parser.add_argument(
            "--direct-message-groups",
            dest="num_direct_message_groups",
            type=int,
            default=3,
            help="The number of direct message groups to create.",
        )

        parser.add_argument(
            "--personals",
            dest="num_personals",
            type=int,
            default=6,
            help="The number of personal pairs to create.",
        )

        parser.add_argument("--threads", type=int, default=1, help="The number of threads to use.")

        parser.add_argument(
            "--percent-direct-message-groups",
            type=float,
            default=15,
            help="The percent of messages to be direct message groups.",
        )

        parser.add_argument(
            "--percent-personals",
            type=float,
            default=15,
            help="The percent of messages to be personals.",
        )

        parser.add_argument(
            "--stickiness",
            type=float,
            default=20,
            help="The percent of messages to repeat recent folks.",
        )

        parser.add_argument(
            "--nodelete",
            action="store_false",
            dest="delete",
            help="Whether to delete all the existing messages.",
        )

        parser.add_argument(
            "--test-suite",
            action="store_true",
            help="Configures populate_db to create a deterministic data set for the backend tests.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        # Suppress spammy output from the push notifications logger
        push_notifications_logger.disabled = True

        if options["percent_direct_message_groups"] + options["percent_personals"] > 100:
            self.stderr.write("Error!  More than 100% of messages allocated.\n")
            return

        # Get consistent data for backend tests.
        if options["test_suite"]:
            random.seed(0)

            with connection.cursor() as cursor:
                # Sometimes bugs relating to confusing recipient.id for recipient.type_id
                # or <object>.id for <object>.recipient_id remain undiscovered by the test suite
                # due to these numbers happening to coincide in such a way that it makes tests
                # accidentally pass. By bumping the Recipient.id sequence by a large enough number,
                # we can have those ids in a completely different range of values than object ids,
                # eliminating the possibility of such coincidences.
                cursor.execute("SELECT setval('zerver_recipient_id_seq', 100)")

        if options["max_topics"] is None:
            # If max_topics is not set, we use a default that's big
            # enough "show all topics" should appear, and scales slowly
            # with the number of messages.
            options["max_topics"] = 8 + options["num_messages"] // 1000

        if options["delete"]:
            # Start by clearing all the data in our database
            clear_database()

            # Create our three default realms
            # Could in theory be done via zerver.actions.create_realm.do_create_realm, but
            # welcome-bot (needed for do_create_realm) hasn't been created yet
            create_internal_realm()
            zulip_realm = do_create_realm(
                string_id="zulip",
                name="Zulip Dev",
                emails_restricted_to_domains=False,
                description="The Zulip development environment default organization."
                "  It's great for testing!",
                invite_required=False,
                plan_type=Realm.PLAN_TYPE_SELF_HOSTED,
                org_type=Realm.ORG_TYPES["business"]["id"],
                enable_read_receipts=True,
                enable_spectator_access=True,
            )
            RealmDomain.objects.create(realm=zulip_realm, domain="zulip.com")
            assert zulip_realm.new_stream_announcements_stream is not None
            zulip_realm.new_stream_announcements_stream.name = "Verona"
            zulip_realm.new_stream_announcements_stream.description = "A city in Italy"
            zulip_realm.new_stream_announcements_stream.save(update_fields=["name", "description"])

            realm_user_default = RealmUserDefault.objects.get(realm=zulip_realm)
            realm_user_default.enter_sends = True
            realm_user_default.email_address_visibility = (
                RealmUserDefault.EMAIL_ADDRESS_VISIBILITY_ADMINS
            )
            realm_user_default.save()

            if options["test_suite"]:
                mit_realm = do_create_realm(
                    string_id="zephyr",
                    name="MIT",
                    emails_restricted_to_domains=True,
                    invite_required=False,
                    plan_type=Realm.PLAN_TYPE_SELF_HOSTED,
                    org_type=Realm.ORG_TYPES["business"]["id"],
                )
                RealmDomain.objects.create(realm=mit_realm, domain="mit.edu")

                lear_realm = do_create_realm(
                    string_id="lear",
                    name="Lear & Co.",
                    emails_restricted_to_domains=False,
                    invite_required=False,
                    plan_type=Realm.PLAN_TYPE_SELF_HOSTED,
                    org_type=Realm.ORG_TYPES["business"]["id"],
                )

            # Realms should have matching RemoteRealm entries - simulating having realms registered
            # with the bouncer, which is going to be the primary case for modern servers. Tests
            # wanting to have missing registrations, or simulating legacy server scenarios,
            # should delete RemoteRealms to explicit set things up.

            assert isinstance(settings.ZULIP_ORG_ID, str)
            assert isinstance(settings.ZULIP_ORG_KEY, str)
            server = RemoteZulipServer.objects.create(
                uuid=settings.ZULIP_ORG_ID,
                api_key=settings.ZULIP_ORG_KEY,
                hostname=settings.EXTERNAL_HOST,
                last_updated=timezone_now(),
                contact_email="remotezulipserver@zulip.com",
            )
            RemoteZulipServerAuditLog.objects.create(
                event_type=AuditLogEventType.REMOTE_SERVER_CREATED,
                server=server,
                event_time=server.last_updated,
            )
            update_remote_realm_data_for_server(server, get_realms_info_for_push_bouncer())

            # Create test Users (UserProfiles are automatically created,
            # as are subscriptions to the ability to receive personals).
            names = [
                ("Zoe", "ZOE@zulip.com"),
                ("Othello, the Moor of Venice", "othello@zulip.com"),
                ("Iago", "iago@zulip.com"),
                ("Prospero from The Tempest", "prospero@zulip.com"),
                ("Cordelia, Lear's daughter", "cordelia@zulip.com"),
                ("King Hamlet", "hamlet@zulip.com"),
                ("aaron", "AARON@zulip.com"),
                ("Polonius", "polonius@zulip.com"),
                ("Desdemona", "desdemona@zulip.com"),
                ("शिव", "shiva@zulip.com"),
            ]

            # For testing really large batches:
            # Create extra users with semi realistic names to make search
            # functions somewhat realistic.  We'll still create 1000 users
            # like Extra222 User for some predictability.
            num_names = options["extra_users"]
            num_boring_names = 300

            for i in range(min(num_names, num_boring_names)):
                full_name = f"Extra{i:03} User"
                names.append((full_name, f"extrauser{i}@zulip.com"))

            if num_names > num_boring_names:
                fnames = [
                    "Amber",
                    "Arpita",
                    "Bob",
                    "Cindy",
                    "Daniela",
                    "Dan",
                    "Dinesh",
                    "Faye",
                    "François",
                    "George",
                    "Hank",
                    "Irene",
                    "James",
                    "Janice",
                    "Jenny",
                    "Jill",
                    "John",
                    "Kate",
                    "Katelyn",
                    "Kobe",
                    "Lexi",
                    "Manish",
                    "Mark",
                    "Matt",
                    "Mayna",
                    "Michael",
                    "Pete",
                    "Peter",
                    "Phil",
                    "Phillipa",
                    "Preston",
                    "Sally",
                    "Scott",
                    "Sandra",
                    "Steve",
                    "Stephanie",
                    "Vera",
                ]
                mnames = ["de", "van", "von", "Shaw", "T."]
                lnames = [
                    "Adams",
                    "Agarwal",
                    "Beal",
                    "Benson",
                    "Bonita",
                    "Davis",
                    "George",
                    "Harden",
                    "James",
                    "Jones",
                    "Johnson",
                    "Jordan",
                    "Lee",
                    "Leonard",
                    "Singh",
                    "Smith",
                    "Patel",
                    "Towns",
                    "Wall",
                ]
                non_ascii_names = [
                    "Günter",
                    "أحمد",
                    "Magnús",
                    "आशी",
                    "イツキ",
                    "语嫣",
                    "அருண்",
                    "Александр",
                    "José",
                ]
                # to imitate emoji insertions in usernames
                raw_emojis = ["😎", "😂", "🐱‍👤"]

            for i in range(num_boring_names, num_names):
                fname = random.choice(fnames) + str(i)
                full_name = fname
                if random.random() < 0.7:
                    if random.random() < 0.3:
                        full_name += " " + random.choice(non_ascii_names)
                    else:
                        full_name += " " + random.choice(mnames)
                    if random.random() < 0.1:
                        full_name += f" {random.choice(raw_emojis)} "
                    else:
                        full_name += " " + random.choice(lnames)
                email = fname.lower().encode("ascii", "ignore").decode("ascii") + "@zulip.com"
                validate_email(email)
                names.append((full_name, email))

            create_users(zulip_realm, names, tos_version=settings.TERMS_OF_SERVICE_VERSION)

            # Add time zones to some users. Ideally, this would be
            # done in the initial create_users calls, but the
            # tuple-based interface for that function doesn't support
            # doing so.
            def assign_time_zone_by_delivery_email(delivery_email: str, new_time_zone: str) -> None:
                u = get_user_by_delivery_email(delivery_email, zulip_realm)
                u.timezone = new_time_zone
                u.save(update_fields=["timezone"])

            # Note: Hamlet keeps default time zone of "".
            assign_time_zone_by_delivery_email("AARON@zulip.com", "US/Pacific")
            assign_time_zone_by_delivery_email("othello@zulip.com", "US/Pacific")
            assign_time_zone_by_delivery_email("ZOE@zulip.com", "US/Eastern")
            assign_time_zone_by_delivery_email("iago@zulip.com", "US/Eastern")
            assign_time_zone_by_delivery_email("desdemona@zulip.com", "Canada/Newfoundland")
            assign_time_zone_by_delivery_email("polonius@zulip.com", "Asia/Shanghai")  # China
            assign_time_zone_by_delivery_email("shiva@zulip.com", "Asia/Kolkata")  # India
            assign_time_zone_by_delivery_email("cordelia@zulip.com", "UTC")

            iago = get_user_by_delivery_email("iago@zulip.com", zulip_realm)
            do_change_user_role(iago, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
            iago.is_staff = True
            iago.save(update_fields=["is_staff"])

            # We need to create at least two test draft for Iago for the sake
            # of the cURL tests. Two since one will be deleted.
            Draft.objects.create(
                user_profile=iago,
                recipient=None,
                topic="Release Notes",
                content="Release 4.0 will contain ...",
                last_edit_time=timezone_now(),
            )
            Draft.objects.create(
                user_profile=iago,
                recipient=None,
                topic="Release Notes",
                content="Release 4.0 will contain many new features such as ... ",
                last_edit_time=timezone_now(),
            )

            desdemona = get_user_by_delivery_email("desdemona@zulip.com", zulip_realm)
            do_change_user_role(desdemona, UserProfile.ROLE_REALM_OWNER, acting_user=None)

            shiva = get_user_by_delivery_email("shiva@zulip.com", zulip_realm)
            do_change_user_role(shiva, UserProfile.ROLE_MODERATOR, acting_user=None)

            polonius = get_user_by_delivery_email("polonius@zulip.com", zulip_realm)
            do_change_user_role(polonius, UserProfile.ROLE_GUEST, acting_user=None)

            # These bots are directly referenced from code and thus
            # are needed for the test suite.
            zulip_realm_bots = [
                ("Zulip Default Bot", "default-bot@zulip.com"),
                *(
                    (f"Extra Bot {i}", f"extrabot{i}@zulip.com")
                    for i in range(options["extra_bots"])
                ),
            ]

            create_users(
                zulip_realm, zulip_realm_bots, bot_type=UserProfile.DEFAULT_BOT, bot_owner=desdemona
            )

            zoe = get_user_by_delivery_email("zoe@zulip.com", zulip_realm)
            zulip_webhook_bots = [
                ("Zulip Webhook Bot", "webhook-bot@zulip.com"),
            ]
            # If a stream is not supplied in the webhook URL, the webhook
            # will (in some cases) send the notification as a PM to the
            # owner of the webhook bot, so bot_owner can't be None
            create_users(
                zulip_realm,
                zulip_webhook_bots,
                bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
                bot_owner=zoe,
            )
            aaron = get_user_by_delivery_email("AARON@zulip.com", zulip_realm)

            zulip_outgoing_bots = [
                ("Outgoing Webhook", "outgoing-webhook@zulip.com"),
            ]
            create_users(
                zulip_realm,
                zulip_outgoing_bots,
                bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                bot_owner=aaron,
            )
            outgoing_webhook = get_user("outgoing-webhook@zulip.com", zulip_realm)
            add_service(
                "outgoing-webhook",
                user_profile=outgoing_webhook,
                interface=Service.GENERIC,
                base_url="http://127.0.0.1:5002",
                token=generate_api_key(),
            )

            # Add the realm internal bots to each realm.
            create_if_missing_realm_internal_bots()

            # Create streams.
            zulip_discussion_channel_name = str(Realm.ZULIP_DISCUSSION_CHANNEL_NAME)
            zulip_sandbox_channel_name = str(Realm.ZULIP_SANDBOX_CHANNEL_NAME)

            stream_list = [
                "Verona",
                "Denmark",
                "Scotland",
                "Venice",
                "Rome",
                "core team",
                zulip_discussion_channel_name,
                zulip_sandbox_channel_name,
            ]
            stream_dict: dict[str, dict[str, Any]] = {
                "Denmark": {"description": "A Scandinavian country"},
                "Scotland": {"description": "Located in the United Kingdom", "creator": iago},
                "Venice": {"description": "A northeastern Italian city", "creator": polonius},
                "Rome": {"description": "Yet another Italian city", "is_web_public": True},
                "core team": {
                    "description": "A private channel for core team members",
                    "invite_only": True,
                    "creator": desdemona,
                },
            }

            bulk_create_streams(zulip_realm, stream_dict)
            recipient_streams: list[int] = [
                Stream.objects.get(name=name, realm=zulip_realm).id for name in stream_list
            ]

            # Create subscriptions to streams.  The following
            # algorithm will give each of the users a different but
            # deterministic subset of the streams (given a fixed list
            # of users). For the test suite, we have a fixed list of
            # subscriptions to make sure test data is consistent
            # across platforms.

            subscriptions_list: list[tuple[UserProfile, Recipient]] = []
            profiles: Sequence[UserProfile] = list(
                UserProfile.objects.select_related("realm").filter(is_bot=False).order_by("email")
            )

            if options["test_suite"]:
                subscriptions_map = {
                    "AARON@zulip.com": ["Verona"],
                    "cordelia@zulip.com": ["Verona"],
                    "hamlet@zulip.com": [
                        "Verona",
                        "Denmark",
                        "core team",
                        zulip_discussion_channel_name,
                        zulip_sandbox_channel_name,
                    ],
                    "iago@zulip.com": [
                        "Verona",
                        "Denmark",
                        "Scotland",
                        "core team",
                        zulip_discussion_channel_name,
                        zulip_sandbox_channel_name,
                    ],
                    "othello@zulip.com": ["Verona", "Denmark", "Scotland"],
                    "prospero@zulip.com": ["Verona", "Denmark", "Scotland", "Venice"],
                    "ZOE@zulip.com": ["Verona", "Denmark", "Scotland", "Venice", "Rome"],
                    "polonius@zulip.com": ["Verona"],
                    "desdemona@zulip.com": [
                        "Verona",
                        "Denmark",
                        "Venice",
                        "core team",
                        zulip_discussion_channel_name,
                        zulip_sandbox_channel_name,
                    ],
                    "shiva@zulip.com": ["Verona", "Denmark", "Scotland"],
                }

                for profile in profiles:
                    email = profile.delivery_email
                    if email not in subscriptions_map:
                        raise Exception(f"Subscriptions not listed for user {email}")

                    for stream_name in subscriptions_map[email]:
                        stream = Stream.objects.get(name=stream_name, realm=zulip_realm)
                        r = Recipient.objects.get(type=Recipient.STREAM, type_id=stream.id)
                        subscriptions_list.append((profile, r))
            else:
                num_streams = len(recipient_streams)
                num_users = len(profiles)
                for i, profile in enumerate(profiles):
                    # Subscribe to some streams.
                    fraction = float(i) / num_users
                    num_recips = int(num_streams * fraction) + 1

                    for type_id in recipient_streams[:num_recips]:
                        r = Recipient.objects.get(type=Recipient.STREAM, type_id=type_id)
                        subscriptions_list.append((profile, r))

            subscriptions_to_add: list[Subscription] = []
            subscriber_count_changes: dict[int, set[int]] = defaultdict(set)
            event_time = timezone_now()
            all_subscription_logs: list[RealmAuditLog] = []

            i = 0
            for profile, recipient in subscriptions_list:
                i += 1
                color = STREAM_ASSIGNMENT_COLORS[i % len(STREAM_ASSIGNMENT_COLORS)]
                s = Subscription(
                    recipient=recipient,
                    user_profile=profile,
                    is_user_active=profile.is_active,
                    color=color,
                )

                subscriptions_to_add.append(s)
                if profile.is_active:
                    subscriber_count_changes[recipient.type_id].add(profile.id)

                log = RealmAuditLog(
                    realm=profile.realm,
                    modified_user=profile,
                    modified_stream_id=recipient.type_id,
                    event_last_message_id=0,
                    event_type=AuditLogEventType.SUBSCRIPTION_CREATED,
                    event_time=event_time,
                )
                all_subscription_logs.append(log)

            bulk_create_stream_subscriptions(
                subs=subscriptions_to_add, streams=subscriber_count_changes
            )
            RealmAuditLog.objects.bulk_create(all_subscription_logs)

            # Create custom profile field data
            phone_number = try_add_realm_custom_profile_field(
                zulip_realm, "Phone number", CustomProfileField.SHORT_TEXT, hint=""
            )
            biography = try_add_realm_custom_profile_field(
                zulip_realm,
                "Biography",
                CustomProfileField.LONG_TEXT,
                hint="What are you known for?",
            )
            favorite_food = try_add_realm_custom_profile_field(
                zulip_realm,
                "Favorite food",
                CustomProfileField.SHORT_TEXT,
                hint="Or drink, if you'd prefer",
            )
            field_data: ProfileFieldData = {
                "0": {"text": "Vim", "order": "1"},
                "1": {"text": "Emacs", "order": "2"},
            }
            favorite_editor = try_add_realm_custom_profile_field(
                zulip_realm, "Favorite editor", CustomProfileField.SELECT, field_data=field_data
            )
            birthday = try_add_realm_custom_profile_field(
                zulip_realm, "Birthday", CustomProfileField.DATE
            )
            favorite_website = try_add_realm_custom_profile_field(
                zulip_realm,
                "Favorite website",
                CustomProfileField.URL,
                hint="Or your personal blog's URL",
            )
            mentor = try_add_realm_custom_profile_field(
                zulip_realm, "Mentor", CustomProfileField.USER
            )
            github_profile = try_add_realm_default_custom_profile_field(zulip_realm, "github")
            pronouns = try_add_realm_custom_profile_field(
                zulip_realm,
                "Pronouns",
                CustomProfileField.PRONOUNS,
                hint="What pronouns should people use to refer to you?",
            )

            # Fill in values for Iago and Hamlet
            hamlet = get_user_by_delivery_email("hamlet@zulip.com", zulip_realm)
            do_update_user_custom_profile_data_if_changed(
                iago,
                [
                    {"id": phone_number.id, "value": "+1-234-567-8901"},
                    {"id": biography.id, "value": "Betrayer of Othello."},
                    {"id": favorite_food.id, "value": "Apples"},
                    {"id": favorite_editor.id, "value": "1"},
                    {"id": birthday.id, "value": "2000-01-01"},
                    {"id": favorite_website.id, "value": "https://zulip.readthedocs.io/en/latest/"},
                    {"id": mentor.id, "value": [hamlet.id]},
                    {"id": github_profile.id, "value": "zulip"},
                    {"id": pronouns.id, "value": "he/him"},
                ],
            )
            do_update_user_custom_profile_data_if_changed(
                hamlet,
                [
                    {"id": phone_number.id, "value": "+0-11-23-456-7890"},
                    {
                        "id": biography.id,
                        "value": "I am:\n* The prince of Denmark\n* Nephew to the usurping Claudius",
                    },
                    {"id": favorite_food.id, "value": "Dark chocolate"},
                    {"id": favorite_editor.id, "value": "0"},
                    {"id": birthday.id, "value": "1900-01-01"},
                    {"id": favorite_website.id, "value": "https://blog.zulig.org"},
                    {"id": mentor.id, "value": [iago.id]},
                    {"id": github_profile.id, "value": "zulipbot"},
                    {"id": pronouns.id, "value": "he/him"},
                ],
            )
            # We need to create at least one scheduled message for Iago for the api-test
            # cURL example to delete an existing scheduled message.
            check_schedule_message(
                sender=iago,
                client=get_client("ZulipDataImport"),
                recipient_type_name="stream",
                message_to=[Stream.objects.get(name="Denmark", realm=zulip_realm).id],
                topic_name="test-api",
                message_content="It's time to celebrate the anniversary of provisioning this development environment :tada:!",
                deliver_at=timezone_now() + timedelta(days=365),
                realm=zulip_realm,
            )
            check_schedule_message(
                sender=iago,
                client=get_client("ZulipDataImport"),
                recipient_type_name="private",
                message_to=[iago.id],
                topic_name=None,
                message_content="Note to self: It's been a while since you've provisioned this development environment.",
                deliver_at=timezone_now() + timedelta(days=365),
                realm=zulip_realm,
            )
            do_add_linkifier(
                zulip_realm,
                "#D(?P<id>[0-9]{2,8})",
                "https://github.com/zulip/zulip-desktop/pull/{id}",
                acting_user=None,
            )
            do_add_linkifier(
                zulip_realm,
                "zulip-mobile#(?P<id>[0-9]{2,8})",
                "https://github.com/zulip/zulip-mobile/pull/{id}",
                acting_user=None,
            )
            do_add_linkifier(
                zulip_realm,
                "zulip-(?P<repo>[a-zA-Z-_0-9]+)#(?P<id>[0-9]{2,8})",
                "https://github.com/zulip/{repo}/pull/{id}",
                acting_user=None,
            )
        else:
            zulip_realm = get_realm("zulip")
            recipient_streams = [
                klass.type_id for klass in Recipient.objects.filter(type=Recipient.STREAM)
            ]

        # Extract a list of all users
        user_profiles: list[UserProfile] = list(
            UserProfile.objects.filter(is_bot=False, realm=zulip_realm)
        )

        if options["test_suite"]:
            # As we plan to change the default values for 'automatically_follow_topics_policy' and
            # 'automatically_unmute_topics_in_muted_streams_policy' in the future, it will lead to
            # skewing a lot of our tests, which now need to take into account extra events and database queries.
            #
            # We explicitly set the values for both settings to 'AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER'
            # to make the tests independent of the default values.
            #
            # We have separate tests to verify events generated, database query counts,
            # and other important details related to the above-mentioned settings.
            #
            # We set the value of 'automatically_follow_topics_where_mentioned' to 'False' so that it
            # does not increase the number of events and db queries while running tests.
            for user in user_profiles:
                do_change_user_setting(
                    user,
                    "automatically_follow_topics_policy",
                    UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER,
                    acting_user=None,
                )
                do_change_user_setting(
                    user,
                    "automatically_unmute_topics_in_muted_streams_policy",
                    UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER,
                    acting_user=None,
                )
                do_change_user_setting(
                    user,
                    "automatically_follow_topics_where_mentioned",
                    False,
                    acting_user=None,
                )

            # Channel event messages are disabled by default, but we want them
            # enabled in the development environment (so that we naturally test
            # them when doing manual testing) and unit tests (to preserve the old behaviour).
            do_set_realm_property(
                zulip_realm, "send_channel_events_messages", True, acting_user=None
            )
        # Create a test realm emoji.
        IMAGE_FILE_PATH = static_path("images/test-images/checkbox.png")
        with open(IMAGE_FILE_PATH, "rb") as fp:
            check_add_realm_emoji(
                zulip_realm, "green_tick", iago, File(fp, name="checkbox.png"), "image/png"
            )

        if not options["test_suite"]:
            # Populate users with some bar data
            for user in user_profiles:
                date = timezone_now()
                UserPresence.objects.get_or_create(
                    user_profile=user,
                    realm_id=user.realm_id,
                    defaults={"last_active_time": date, "last_connected_time": date},
                )

        user_profiles_ids = []
        onboarding_steps: list[OnboardingStep] = []
        for user_profile in user_profiles:
            user_profiles_ids.append(user_profile.id)
            onboarding_steps.extend(
                OnboardingStep(user=user_profile, onboarding_step=onboarding_step.name)
                for onboarding_step in ALL_ONBOARDING_STEPS
            )

        # Mark onboarding steps as seen for existing users to avoid
        # unnecessary popups during development.
        OnboardingStep.objects.bulk_create(onboarding_steps)

        # Create several initial direct message groups
        for i in range(options["num_direct_message_groups"]):
            get_or_create_direct_message_group(
                random.sample(user_profiles_ids, random.randint(3, 4))
            )

        # Create several initial pairs for personals
        personals_pairs = [
            random.sample(user_profiles_ids, 2) for i in range(options["num_personals"])
        ]

        create_alert_words(zulip_realm.id)

        # Generate a new set of test data.
        create_test_data()

        if options["delete"]:
            if options["test_suite"]:
                # Create test users
                event_time = timezone_now()
                testsuite_mit_users = [
                    ("Fred Sipb (MIT)", "sipbtest@mit.edu"),
                    ("Athena Consulting Exchange User (MIT)", "starnine@mit.edu"),
                    ("Esp Classroom (MIT)", "espuser@mit.edu"),
                ]
                create_users(
                    mit_realm, testsuite_mit_users, tos_version=settings.TERMS_OF_SERVICE_VERSION
                )

                mit_user = get_user_by_delivery_email("sipbtest@mit.edu", mit_realm)
                bulk_create_streams(
                    mit_realm,
                    {
                        "core team": {
                            "description": "A private channel for core team members",
                            "invite_only": True,
                            "history_public_to_subscribers": False,
                        }
                    },
                )
                core_team_stream = Stream.objects.get(name="core team", realm=mit_realm)
                bulk_add_subscriptions(mit_realm, [core_team_stream], [mit_user], acting_user=None)

                testsuite_lear_users = [
                    ("King Lear", "king@lear.org"),
                    ("Cordelia, Lear's daughter", "cordelia@zulip.com"),
                ]
                create_users(
                    lear_realm, testsuite_lear_users, tos_version=settings.TERMS_OF_SERVICE_VERSION
                )

                lear_user = get_user_by_delivery_email("king@lear.org", lear_realm)
                bulk_create_streams(
                    lear_realm,
                    {
                        "core team": {
                            "description": "A private channel for core team members",
                            "invite_only": True,
                        }
                    },
                )
                core_team_stream = Stream.objects.get(name="core team", realm=lear_realm)
                bulk_add_subscriptions(
                    lear_realm, [core_team_stream], [lear_user], acting_user=None
                )

                core_team_stream = Stream.objects.get(name="core team", realm=zulip_realm)
                do_set_realm_moderation_request_channel(
                    zulip_realm, core_team_stream, core_team_stream.id, acting_user=None
                )

            if not options["test_suite"]:
                # To keep the messages.json fixtures file for the test
                # suite fast, don't add these users and subscriptions
                # when running populate_db for the test suite

                # to imitate emoji insertions in stream names
                raw_emojis = ["😎", "😂", "🐱‍👤"]

                admins_system_group = NamedUserGroup.objects.get(
                    name=SystemGroups.ADMINISTRATORS,
                    realm_for_sharding=zulip_realm,
                    is_system_group=True,
                )

                engineering_channel_folder = check_add_channel_folder(
                    zulip_realm,
                    "Engineering",
                    "For convenient *channel folder* testing! :octopus:",
                    acting_user=iago,
                )
                information_channel_folder = check_add_channel_folder(
                    zulip_realm,
                    "Information",
                    "For user-facing information and questions",
                    acting_user=iago,
                )
                zulip_stream_dict: dict[str, dict[str, Any]] = {
                    "devel": {
                        "description": "For developing",
                        "folder_id": engineering_channel_folder.id,
                    },
                    # ビデオゲーム - VideoGames (japanese)
                    "ビデオゲーム": {
                        "description": f"Share your favorite video games!  {raw_emojis[2]}",
                        "creator": shiva,
                    },
                    "announce": {
                        "description": "For announcements",
                        "can_send_message_group": admins_system_group,
                        "folder_id": information_channel_folder.id,
                    },
                    "design": {"description": "For design", "creator": hamlet},
                    "support": {
                        "description": "For support",
                        "folder_id": information_channel_folder.id,
                    },
                    "social": {"description": "For socializing"},
                    "test": {
                        "description": "For testing `code`",
                        "folder_id": engineering_channel_folder.id,
                    },
                    "errors": {
                        "description": "For errors",
                        "folder_id": engineering_channel_folder.id,
                    },
                    # 조리법 - Recipes (Korean), Пельмени - Dumplings (Russian)
                    "조리법 " + raw_emojis[0]: {
                        "description": "Everything cooking, from pasta to Пельмени"
                    },
                }

                extra_stream_names = [
                    "802.11a",
                    "Ad Hoc Network",
                    "Augmented Reality",
                    "Cycling",
                    "DPI",
                    "FAQ",
                    "FiFo",
                    "commits",
                    "Control panel",
                    "desktop",
                    "компьютеры",
                    "Data security",
                    "desktop",
                    "काम",
                    "discussions",
                    "Cloud storage",
                    "GCI",
                    "Vaporware",
                    "Recent Trends",
                    "issues",
                    "live",
                    "Health",
                    "mobile",
                    "空間",
                    "provision",
                    "hidrógeno",
                    "HR",
                    "アニメ",
                ]

                # Add stream names and stream descriptions
                for i in range(options["extra_streams"]):
                    extra_stream_name = random.choice(extra_stream_names) + " " + str(i)

                    # to imitate emoji insertions in stream names
                    if random.random() <= 0.15:
                        extra_stream_name += random.choice(raw_emojis)

                    zulip_stream_dict[extra_stream_name] = {
                        "description": "Auto-generated extra stream.",
                    }

                bulk_create_streams(zulip_realm, zulip_stream_dict)
                # Now that we've created the new_stream_announcements_stream, configure it properly.
                # By default, 'New stream' & 'Zulip update' announcements are sent to the same stream.
                announce_stream = get_stream("announce", zulip_realm)
                zulip_realm.new_stream_announcements_stream = announce_stream
                zulip_realm.zulip_update_announcements_stream = announce_stream
                zulip_realm.save(
                    update_fields=[
                        "new_stream_announcements_stream",
                        "zulip_update_announcements_stream",
                    ]
                )

                # Add a few default streams
                for default_stream_name in ["design", "devel", "social", "support"]:
                    DefaultStream.objects.create(
                        realm=zulip_realm, stream=get_stream(default_stream_name, zulip_realm)
                    )

                # Now subscribe everyone to these streams
                subscribe_users_to_streams(zulip_realm, zulip_stream_dict)

            create_user_groups()

            if not options["test_suite"]:
                # We populate the analytics database here for
                # development purpose only
                call_command("populate_analytics_db", skip_checks=True)

        threads = options["threads"]
        jobs: list[tuple[int, list[list[int]], dict[str, Any], int]] = []
        for i in range(threads):
            count = options["num_messages"] // threads
            if i < options["num_messages"] % threads:
                count += 1
            jobs.append((count, personals_pairs, options, random.randint(0, 10**10)))

        for job in jobs:
            generate_and_send_messages(job)

        if options["delete"]:
            if not options["test_suite"]:
                # These bots are not needed by the test suite
                # Also, we don't want interacting with each other
                # in dev setup.
                internal_zulip_users_nosubs = [
                    ("Zulip Commit Bot", "commit-bot@zulip.com"),
                    ("Zulip Trac Bot", "trac-bot@zulip.com"),
                    ("Zulip Nagios Bot", "nagios-bot@zulip.com"),
                ]
                create_users(
                    zulip_realm,
                    internal_zulip_users_nosubs,
                    bot_type=UserProfile.DEFAULT_BOT,
                    bot_owner=desdemona,
                )

            mark_all_messages_as_read()
            self.stdout.write("Successfully populated test database.\n")

        push_notifications_logger.disabled = False


def mark_all_messages_as_read() -> None:
    """
    We want to keep these flags mostly intact after we create
    messages. The is_private flag, for example, would be bad to overwrite.

    So we're careful to only toggle the read flag.

    We exclude marking messages as read for bots, since bots, by
    default, never mark messages as read.
    """
    # Mark all messages as read
    UserMessage.objects.filter(user_profile__is_bot=False).update(
        flags=F("flags").bitor(UserMessage.flags.read),
    )


recipient_hash: dict[int, Recipient] = {}


def get_recipient_by_id(rid: int) -> Recipient:
    if rid in recipient_hash:
        return recipient_hash[rid]
    return Recipient.objects.get(id=rid)


# Create some test messages, including:
# - multiple streams
# - multiple subjects per stream
# - multiple direct message groups
# - multiple personal conversations
# - multiple messages per subject
# - both single and multi-line content
def generate_and_send_messages(
    data: tuple[int, Sequence[Sequence[int]], Mapping[str, Any], int],
) -> int:
    realm = get_realm("zulip")
    (tot_messages, personals_pairs, options, random_seed) = data
    random.seed(random_seed)

    with open(
        os.path.join(get_or_create_dev_uuid_var_path("test-backend"), "test_messages.json"), "rb"
    ) as infile:
        dialog = orjson.loads(infile.read())
    random.shuffle(dialog)
    texts = itertools.cycle(dialog)

    # We need to filter out streams from the analytics realm as we don't want to generate
    # messages to its streams - and they might also have no subscribers, which would break
    # our message generation mechanism below.
    stream_ids = Stream.objects.filter(realm=realm).values_list("id", flat=True)
    recipient_streams: list[int] = [
        recipient.id
        for recipient in Recipient.objects.filter(type=Recipient.STREAM, type_id__in=stream_ids)
    ]
    recipient_direct_message_groups: list[int] = [
        h.id for h in Recipient.objects.filter(type=Recipient.DIRECT_MESSAGE_GROUP)
    ]

    direct_message_group_members: dict[int, list[int]] = {}
    for h in recipient_direct_message_groups:
        direct_message_group_members[h] = [
            s.user_profile.id for s in Subscription.objects.filter(recipient_id=h)
        ]

    # Generate different topics for each stream
    possible_topic_names = {}
    for stream_id in recipient_streams:
        # We want the test suite to have a predictable database state,
        # since some tests depend on it; but for actual development,
        # we want some streams to have more topics than others for
        # realistic variety.
        if not options["test_suite"]:
            num_topics = random.randint(1, options["max_topics"])
        else:
            num_topics = options["max_topics"]

        possible_topic_names[stream_id] = generate_topics(num_topics)

    message_batch_size = options["batch_size"]
    num_messages = 0
    random_max = 1000000
    recipients: dict[int, tuple[int, int, dict[str, Any]]] = {}
    messages: list[Message] = []
    while num_messages < tot_messages:
        saved_data: dict[str, Any] = {}
        message = Message(realm=realm)
        message.sending_client = get_client("ZulipDataImport")

        message.content = next(texts)

        randkey = random.randint(1, random_max)
        if (
            num_messages > 0
            and random.randint(1, random_max) * 100.0 / random_max < options["stickiness"]
        ):
            # Use an old recipient
            recipient_type, recipient_id, saved_data = recipients[num_messages - 1]
            if recipient_type == Recipient.PERSONAL:
                personals_pair = list(saved_data["personals_pair"])
                random.shuffle(personals_pair)
            elif recipient_type == Recipient.STREAM:
                message.subject = saved_data["subject"]
                message.recipient = get_recipient_by_id(recipient_id)
            elif recipient_type == Recipient.DIRECT_MESSAGE_GROUP:
                message.recipient = get_recipient_by_id(recipient_id)
        elif randkey <= random_max * options["percent_direct_message_groups"] / 100.0:
            recipient_type = Recipient.DIRECT_MESSAGE_GROUP
            message.recipient = get_recipient_by_id(random.choice(recipient_direct_message_groups))
        elif (
            randkey
            <= random_max
            * (options["percent_direct_message_groups"] + options["percent_personals"])
            / 100.0
        ):
            recipient_type = Recipient.PERSONAL
            personals_pair = list(random.choice(personals_pairs))
            random.shuffle(personals_pair)
        elif randkey <= random_max * 1.0:
            recipient_type = Recipient.STREAM
            message.recipient = get_recipient_by_id(random.choice(recipient_streams))

        if recipient_type == Recipient.DIRECT_MESSAGE_GROUP:
            sender_id = random.choice(direct_message_group_members[message.recipient.id])
            message.sender = get_user_profile_by_id(sender_id)
            message.subject = Message.DM_TOPIC
        elif recipient_type == Recipient.PERSONAL:
            message.recipient = Recipient.objects.get(
                type=Recipient.PERSONAL, type_id=personals_pair[0]
            )
            message.sender = get_user_profile_by_id(personals_pair[1])
            message.subject = Message.DM_TOPIC
            saved_data["personals_pair"] = personals_pair
        elif recipient_type == Recipient.STREAM:
            # Pick a random subscriber to the stream
            message.sender = random.choice(
                list(Subscription.objects.filter(recipient=message.recipient))
            ).user_profile
            message.subject = random.choice(possible_topic_names[message.recipient.id])
            saved_data["subject"] = message.subject

        message.is_channel_message = recipient_type == Recipient.STREAM
        message.date_sent = choose_date_sent(
            num_messages, tot_messages, options["oldest_message_days"], options["threads"]
        )
        messages.append(message)

        recipients[num_messages] = (recipient_type, message.recipient.id, saved_data)
        num_messages += 1

        if (num_messages % message_batch_size) == 0:
            # Send the batch and empty the list:
            send_messages(messages)
            messages = []

    if len(messages) > 0:
        # If there are unsent messages after exiting the loop, send them:
        send_messages(messages)

    return tot_messages


def send_messages(messages: list[Message]) -> None:
    # We disable USING_RABBITMQ here, so that deferred work is
    # executed in do_send_message_messages, rather than being
    # queued.  This is important, because otherwise, if run-dev
    # wasn't running when populate_db was run, a developer can end
    # up with queued events that reference objects from a previous
    # life of the database, which naturally throws exceptions.
    settings.USING_RABBITMQ = False
    do_send_messages([build_message_send_dict(message=message) for message in messages])
    bulk_create_reactions(messages)
    settings.USING_RABBITMQ = True


def get_message_to_users(message_ids: list[int]) -> dict[int, list[int]]:
    rows = UserMessage.objects.filter(
        message_id__in=message_ids,
    ).values("message_id", "user_profile_id")

    result: dict[int, list[int]] = defaultdict(list)

    for row in rows:
        result[row["message_id"]].append(row["user_profile_id"])

    return result


def bulk_create_reactions(all_messages: list[Message]) -> None:
    reactions: list[Reaction] = []

    num_messages = int(0.2 * len(all_messages))
    messages = random.sample(all_messages, num_messages)
    message_ids = [message.id for message in messages]

    message_to_users = get_message_to_users(message_ids)

    for message_id in message_ids:
        msg_user_ids = message_to_users[message_id]

        if msg_user_ids:
            # Now let between 1 and 7 users react.
            #
            # Ideally, we'd make exactly 1 reaction more common than
            # this algorithm generates.
            max_num_users = min(7, len(msg_user_ids))
            num_users = random.randrange(1, max_num_users + 1)
            user_ids = random.sample(msg_user_ids, num_users)

            for user_id in user_ids:
                # each user does between 1 and 3 emojis
                num_emojis = random.choice([1, 2, 3])
                emojis = random.sample(DEFAULT_EMOJIS, num_emojis)

                for emoji_name, emoji_code in emojis:
                    reaction = Reaction(
                        user_profile_id=user_id,
                        message_id=message_id,
                        emoji_name=emoji_name,
                        emoji_code=emoji_code,
                        reaction_type=Reaction.UNICODE_EMOJI,
                    )
                    reactions.append(reaction)

    Reaction.objects.bulk_create(reactions)


def choose_date_sent(
    num_messages: int, tot_messages: int, oldest_message_days: int, threads: int
) -> datetime:
    # Spoofing time not supported with threading
    if threads != 1:
        return timezone_now()

    # We want to ensure that:
    # (1) some messages are sent in the last 4 hours,
    # (2) there are some >24hr gaps between adjacent messages, and
    # (3) a decent bulk of messages in the last day so you see adjacent messages with the same date.
    # So we distribute 80% of messages starting from oldest_message_days days ago, over a period
    # of the first min(oldest_message_days-2, 1) of those days. Then, distributes remaining messages
    # over the past 24 hours.
    amount_in_first_chunk = int(tot_messages * 0.8)
    amount_in_second_chunk = tot_messages - amount_in_first_chunk

    if num_messages < amount_in_first_chunk:
        spoofed_date = timezone_now() - timedelta(days=oldest_message_days)
        num_days_for_first_chunk = min(oldest_message_days - 2, 1)
        interval_size = num_days_for_first_chunk * 24 * 60 * 60 / amount_in_first_chunk
        lower_bound = interval_size * num_messages
        upper_bound = interval_size * (num_messages + 1)

    else:
        # We're in the last 20% of messages, so distribute them over the last 24 hours:
        spoofed_date = timezone_now() - timedelta(days=1)
        interval_size = 24 * 60 * 60 / amount_in_second_chunk
        lower_bound = interval_size * (num_messages - amount_in_first_chunk)
        upper_bound = interval_size * (num_messages - amount_in_first_chunk + 1)

    offset_seconds = random.uniform(lower_bound, upper_bound)
    spoofed_date += timedelta(seconds=offset_seconds)

    return spoofed_date


def create_user_groups() -> None:
    zulip = get_realm("zulip")
    cordelia = get_user_by_delivery_email("cordelia@zulip.com", zulip)
    members = [
        get_user_by_delivery_email("cordelia@zulip.com", zulip),
        get_user_by_delivery_email("hamlet@zulip.com", zulip),
    ]
    create_user_group_in_database(
        "hamletcharacters", members, zulip, description="Characters of Hamlet", acting_user=cordelia
    )
