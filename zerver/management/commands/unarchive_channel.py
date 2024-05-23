from argparse import ArgumentParser
from typing import Any, Optional

from django.core.management.base import CommandError
from typing_extensions import override

from zerver.actions.streams import deactivated_streams_by_old_name, do_unarchive_stream
from zerver.lib.management import ZulipBaseCommand
from zerver.models import RealmAuditLog, Stream


class Command(ZulipBaseCommand):
    help = """Reactivate a channel that was deactivated."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        specify_channel = parser.add_mutually_exclusive_group(required=True)
        specify_channel.add_argument(
            "-c",
            "--channel",
            help="Name of a deactivated channel in the realm.",
        )
        specify_channel.add_argument(
            "--channel-id",
            help="ID of a deactivated channel in the realm.",
        )
        parser.add_argument(
            "-n",
            "--new-name",
            required=False,
            help="Name to reactivate as; defaults to the old name.",
        )
        self.add_realm_args(parser, required=True)

    @override
    def handle(self, *args: Any, **options: Optional[str]) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        # Looking up the channel is complicated, since they get renamed
        # when they are deactivated, in a transformation which may be
        # lossy.

        if options["channel_id"] is not None:
            channel = Stream.objects.get(id=options["channel_id"])
            if channel.realm_id != realm.id:
                raise CommandError(
                    f"Channel id {channel.id}, named '{channel.name}', is in realm '{channel.realm.string_id}', not '{realm.string_id}'"
                )
            if not channel.deactivated:
                raise CommandError(
                    f"Channel id {channel.id}, named '{channel.name}', is not deactivated"
                )
            if options["new_name"] is None:
                raise CommandError("--new-name flag is required with --channel-id")
            new_name = options["new_name"]
        else:
            channel_name = options["channel"]
            assert channel_name is not None

            possible_channels = deactivated_streams_by_old_name(realm, channel_name)
            if len(possible_channels) == 0:
                raise CommandError("No matching deactivated channels found!")

            if len(possible_channels) > 1:
                # Print ids of all possible channels, support passing by id
                print("Matching channels:")
                for channel in possible_channels:
                    last_deactivation = (
                        RealmAuditLog.objects.filter(
                            realm=realm,
                            modified_stream=channel,
                            event_type=RealmAuditLog.STREAM_DEACTIVATED,
                        )
                        .order_by("-id")
                        .first()
                    )
                    assert last_deactivation is not None
                    print(
                        f"  ({channel.id}) {channel.name}, deactivated on {last_deactivation.event_time}"
                    )
                raise CommandError(
                    "More than one matching channel found!  Specify which with --channel-id"
                )

            channel = possible_channels[0]
            if options["new_name"] is not None:
                new_name = options["new_name"]
            else:
                new_name = channel_name

        if Stream.objects.filter(realm=realm, name=new_name).exists():
            raise CommandError(
                f"Channel with name '{new_name}' already exists; pass a different --new-name"
            )

        assert channel is not None
        do_unarchive_stream(channel, new_name, acting_user=None)
