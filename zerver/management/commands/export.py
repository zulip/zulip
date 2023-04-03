import os
import tempfile
from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError

from zerver.actions.realm_settings import do_deactivate_realm
from zerver.lib.export import export_realm_wrapper
from zerver.lib.management import ZulipBaseCommand
from zerver.models import Message, Reaction, UserProfile


class Command(ZulipBaseCommand):
    help = """Exports all data from a Zulip realm

    This command exports all significant data from a Zulip realm.  The
    result can be imported using the `./manage.py import` command.

    Things that are exported:
    * All user-accessible data in the Zulip database (Messages,
      Streams, UserMessages, RealmEmoji, etc.)
    * Copies of all uploaded files and avatar images along with
      metadata needed to restore them even in the ab

    Things that are not exported:
    * Confirmation and PreregistrationUser (transient tables)
    * Sessions (everyone will need to log in again post-export)
    * Users' passwords and API keys (users will need to use SSO or reset password)
    * Mobile tokens for APNS/GCM (users will need to reconnect their mobile devices)
    * ScheduledEmail (not relevant on a new server)
    * RemoteZulipServer (unlikely to be migrated)
    * third_party_api_results cache (this means rerendering all old
      messages could be expensive)

    Things that will break as a result of the export:
    * Passwords will not be transferred.  They will all need to go
      through the password reset flow to obtain a new password (unless
      they intend to only use e.g. Google auth).
    * Users will need to log out and re-log in to the Zulip desktop and
      mobile apps.  The apps now all have an option on the login page
      where you can specify which Zulip server to use; your users
      should enter <domain name>.
    * All bots will stop working since they will be pointing to the
      wrong server URL, and all users' API keys have been rotated as
      part of the migration.  So to re-enable your integrations, you
      will need to direct your integrations at the new server.
      Usually this means updating the URL and the bots' API keys.  You
      can see a list of all the bots that have been configured for
      your realm on the `/#organization` page, and use that list to
      make sure you migrate them all.

    The proper procedure for using this to export a realm is as follows:

    * Use `./manage.py export --deactivate` to deactivate and export
      the realm, producing a data tarball.

    * Transfer the tarball to the new server and unpack it.

    * Use `./manage.py import` to import the realm

    * Inform the users about the things broken above.

    We recommend testing by exporting without `--deactivate` first, to
    make sure you have the procedure right and minimize downtime.

    Performance: In one test, the tool exported a realm with hundreds
    of users and ~1M messages of history with --threads=1 in about 3
    hours of serial runtime (goes down to ~50m with --threads=6 on a
    machine with 8 CPUs).  Importing that same data set took about 30
    minutes.  But this will vary a lot depending on the average number
    of recipients of messages in the realm, hardware, etc."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--output", dest="output_dir", help="Directory to write exported data to."
        )
        parser.add_argument(
            "--threads",
            default=settings.DEFAULT_DATA_EXPORT_IMPORT_PARALLELISM,
            help="Threads to use in exporting UserMessage objects in parallel",
        )
        parser.add_argument(
            "--public-only",
            action="store_true",
            help="Export only public stream messages and associated attachments",
        )
        parser.add_argument(
            "--deactivate-realm",
            action="store_true",
            help=(
                "Deactivate the realm immediately before exporting; the exported data "
                "will show the realm as active"
            ),
        )
        parser.add_argument(
            "--consent-message-id",
            type=int,
            help="ID of the message advertising users to react with thumbs up",
        )
        parser.add_argument(
            "--upload",
            action="store_true",
            help="Whether to upload resulting tarball to s3 or LOCAL_UPLOADS_DIR",
        )
        self.add_realm_args(parser, required=True)

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        output_dir = options["output_dir"]
        public_only = options["public_only"]
        consent_message_id = options["consent_message_id"]

        print(f"\033[94mExporting realm\033[0m: {realm.string_id}")

        num_threads = int(options["threads"])
        if num_threads < 1:
            raise CommandError("You must have at least one thread.")

        if public_only and consent_message_id is not None:
            raise CommandError("Please pass either --public-only or --consent-message-id")

        if options["deactivate_realm"] and realm.deactivated:
            raise CommandError(f"The realm {realm.string_id} is already deactivated.  Aborting...")

        if consent_message_id is not None:
            try:
                message = Message.objects.get(id=consent_message_id)
            except Message.DoesNotExist:
                raise CommandError("Message with given ID does not exist. Aborting...")

            if message.last_edit_time is not None:
                raise CommandError("Message was edited. Aborting...")

            # Since the message might have been sent by
            # Notification Bot, we can't trivially check the realm of
            # the message through message.sender.realm.  So instead we
            # check the realm of the people who reacted to the message
            # (who must all be in the message's realm).
            reactions = Reaction.objects.filter(
                message=message,
                # outbox = 1f4e4
                emoji_code="1f4e4",
                reaction_type="unicode_emoji",
            )
            for reaction in reactions:
                if reaction.user_profile.realm != realm:
                    raise CommandError(
                        "Users from a different realm reacted to message. Aborting..."
                    )

            print(f"\n\033[94mMessage content:\033[0m\n{message.content}\n")

            user_count = (
                UserProfile.objects.filter(
                    realm_id=realm.id,
                    is_active=True,
                    is_bot=False,
                )
                .exclude(
                    # We exclude guests, because they're not a priority for
                    # looking at whether most users are being exported.
                    role=UserProfile.ROLE_GUEST,
                )
                .count()
            )
            print(
                f"\033[94mNumber of users that reacted outbox:\033[0m {len(reactions)} / {user_count} total non-guest users\n"
            )

            proceed = input("Continue? [y/N] ")
            if proceed.lower() not in ("y", "yes"):
                raise CommandError("Aborting!")

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="zulip-export-")
        else:
            output_dir = os.path.realpath(os.path.expanduser(output_dir))
            if os.path.exists(output_dir):
                if os.listdir(output_dir):
                    raise CommandError(
                        f"Refusing to overwrite nonempty directory: {output_dir}. Aborting...",
                    )
            else:
                os.makedirs(output_dir)

        tarball_path = output_dir.rstrip("/") + ".tar.gz"
        try:
            with open(tarball_path, "x"):
                pass
        except FileExistsError:
            raise CommandError(
                f"Refusing to overwrite existing tarball: {tarball_path}. Aborting..."
            )

        if options["deactivate_realm"]:
            print(f"\033[94mDeactivating realm\033[0m: {realm.string_id}")
            do_deactivate_realm(realm, acting_user=None)

        def percent_callback(bytes_transferred: Any) -> None:
            print(end=".", flush=True)

        # Allows us to trigger exports separately from command line argument parsing
        export_realm_wrapper(
            realm=realm,
            output_dir=output_dir,
            threads=num_threads,
            upload=options["upload"],
            public_only=public_only,
            percent_callback=percent_callback,
            consent_message_id=consent_message_id,
            export_as_active=True if options["deactivate_realm"] else None,
        )
