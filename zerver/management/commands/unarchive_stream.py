from argparse import ArgumentParser
from typing import Any, Optional

from django.core.management.base import CommandError

from zerver.actions.streams import deactivated_streams_by_old_name, do_unarchive_stream
from zerver.lib.management import ZulipBaseCommand
from zerver.models import RealmAuditLog, Stream


class Command(ZulipBaseCommand):
    help = """Reactivate a stream that was deactivated."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        specify_stream = parser.add_mutually_exclusive_group(required=True)
        specify_stream.add_argument(
            "-s",
            "--stream",
            help="Name of a deactivated stream in the realm.",
        )
        specify_stream.add_argument(
            "--stream-id",
            help="ID of a deactivated stream in the realm.",
        )
        parser.add_argument(
            "-n",
            "--new-name",
            required=False,
            help="Name to reactivate as; defaults to the old name.",
        )
        self.add_realm_args(parser, required=True)

    def handle(self, *args: Any, **options: Optional[str]) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        # Looking up the stream is complicated, since they get renamed
        # when they are deactivated, in a transformation which may be
        # lossy.

        if options["stream_id"] is not None:
            stream = Stream.objects.get(id=options["stream_id"])
            if not stream.deactivated:
                raise CommandError(
                    f"Stream id {stream.id}, named '{stream.name}', is not deactivated"
                )
            if options["new_name"] is None:
                raise CommandError("--new-name flag is required with --stream-id")
            new_name = options["new_name"]
        else:
            stream_name = options["stream"]
            assert stream_name is not None

            possible_streams = deactivated_streams_by_old_name(realm, stream_name)
            if len(possible_streams) == 0:
                raise CommandError("No matching deactivated streams found!")

            if len(possible_streams) > 1:
                # Print ids of all possible streams, support passing by id
                print("Matching streams:")
                for stream in possible_streams:
                    last_deactivation = (
                        RealmAuditLog.objects.filter(
                            realm=realm,
                            modified_stream=stream,
                            event_type=RealmAuditLog.STREAM_DEACTIVATED,
                        )
                        .order_by("-id")
                        .first()
                    )
                    assert last_deactivation is not None
                    print(
                        f"  ({stream.id}) {stream.name}, deactivated on {last_deactivation.event_time}"
                    )
                raise CommandError(
                    "More than one matching stream found!  Specify which with --stream-id"
                )

            stream = possible_streams[0]
            if options["new_name"] is not None:
                new_name = options["new_name"]
            else:
                new_name = stream_name

        if Stream.objects.filter(realm=realm, name=new_name).exists():
            raise CommandError(
                f"Stream with name '{new_name}' already exists; pass a different --new-name"
            )

        assert stream is not None
        do_unarchive_stream(stream, new_name, acting_user=None)
