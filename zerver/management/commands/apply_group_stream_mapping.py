import logging
from json import load as json_load
from typing import Any, Dict, List

from django.conf import settings
from django.core.management.base import CommandParser

from zerver.actions.streams import bulk_add_subscriptions, bulk_remove_subscriptions
from zerver.lib.logging_util import log_to_file
from zerver.lib.management import ZulipBaseCommand
from zerver.models import Recipient, Stream, Subscription, UserGroupMembership, UserProfile

## Setup ##
logger = logging.getLogger("zulip.sync_ldap_user_data")
log_to_file(logger, settings.GROUP_STREAM_SYNC_LOG_PATH)


class Command(ZulipBaseCommand):
    help = """Add some or all users in a realm to a set of streams."""

    def add_arguments(self, parser: CommandParser) -> None:
        self.add_realm_args(parser, required=True)

        parser.add_argument(
            "-c",
            "--config",
            required=True,
            help="Configuration file in json format containing channel mapping (in Rocketchat format).",
        )
        parser.add_argument(
            "--remove-user",
            default=False,
            action="store_true",
            help="Also remove from channel if not inside required groups.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        with open(options["config"]) as rc_data_buf:
            rc_data = json_load(rc_data_buf)

        json_channel_set = set()

        for ldap_group, channel_list in rc_data.items():
            for channel in channel_list:
                json_channel_set.add(channel)

        channel_group_mapping: Dict[str, List[str]] = {}
        private_streams = list(Stream.objects.filter(realm_id=realm.id, invite_only=True))
        for stream in private_streams:
            if stream.name in json_channel_set:
                channel_group_mapping[stream.name] = []

        for ldap_group, channel_list in rc_data.items():
            for channel in channel_list:
                if channel not in channel_group_mapping:
                    logger.warning("skipping %s (does not exist as a private channel)", channel)
                    continue
                channel_group_mapping[channel].append(ldap_group)

        for stream in private_streams:
            if stream.name not in channel_group_mapping:
                continue

            allowed_ids = set(
                UserGroupMembership.objects.filter(
                    user_group__name__in=channel_group_mapping[stream.name],
                ).values_list("user_profile_id", flat=True)
            )

            current_ids = set(
                Subscription.objects.filter(
                    recipient__type=Recipient.STREAM,
                    recipient__type_id=stream.id,
                    active=True,
                ).values_list("user_profile_id", flat=True)
            )

            user_profile_to_remove: List[UserProfile] = []
            for remove_id in current_ids.difference(allowed_ids):
                user_profile = UserProfile.objects.get(realm=realm, id=remove_id)
                if options["remove_user"]:
                    logger.info("remove %s from %s", user_profile.delivery_email, stream.name)
                    user_profile_to_remove.append(user_profile)
                else:
                    logger.info(
                        "remove %s from %s [skipped]", user_profile.delivery_email, stream.name
                    )
            bulk_remove_subscriptions(realm, user_profile_to_remove, [stream], acting_user=None)

            user_profile_to_add: List[UserProfile] = []
            for add_id in allowed_ids.difference(current_ids):
                user_profile = UserProfile.objects.get(realm=realm, id=add_id)
                logger.info("add %s to %s ", user_profile.delivery_email, stream.name)
                user_profile_to_add.append(user_profile)

            bulk_add_subscriptions(realm, [stream], user_profile_to_add, acting_user=None)
