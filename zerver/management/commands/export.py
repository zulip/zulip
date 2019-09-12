import os
import tempfile
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.export import export_realm_wrapper
from zerver.models import Message, Reaction

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
    * Sessions (everyone will need to login again post-export)
    * Users' passwords and API keys (users will need to use SSO or reset password)
    * Mobile tokens for APNS/GCM (users will need to reconnect their mobile devices)
    * ScheduledEmail (Not relevant on a new server)
    * RemoteZulipServer (Unlikely to be migrated)
    * third_party_api_results cache (this means rerending all old
      messages could be expensive)

    Things that will break as a result of the export:
    * Passwords will not be transferred.  They will all need to go
      through the password reset flow to obtain a new password (unless
      they intend to only use e.g. Google Auth).
    * Users will need to logout and re-login to the Zulip desktop and
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

    * Use `./manage.py deactivate_realm` to deactivate the realm, so
      nothing happens in the realm being exported during the export
      process.

    * Use `./manage.py export` to export the realm, producing a data
      tarball.

    * Transfer the tarball to the new server and unpack it.

    * Use `./manage.py import` to import the realm

    * Use `./manage.py reactivate_realm` to reactivate the realm, so
      users can login again.

    * Inform the users about the things broken above.

    We recommend testing by exporting without having deactivated the
    realm first, to make sure you have the procedure right and
    minimize downtime.

    Performance: In one test, the tool exported a realm with hundreds
    of users and ~1M messages of history with --threads=1 in about 3
    hours of serial runtime (goes down to ~50m with --threads=6 on a
    machine with 8 CPUs).  Importing that same data set took about 30
    minutes.  But this will vary a lot depending on the average number
    of recipients of messages in the realm, hardware, etc."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--output',
                            dest='output_dir',
                            action="store",
                            default=None,
                            help='Directory to write exported data to.')
        parser.add_argument('--threads',
                            dest='threads',
                            action="store",
                            default=6,
                            help='Threads to use in exporting UserMessage objects in parallel')
        parser.add_argument('--public-only',
                            action="store_true",
                            help='Export only public stream messages and associated attachments')
        parser.add_argument('--consent-message-id',
                            dest="consent_message_id",
                            action="store",
                            default=None,
                            type=int,
                            help='ID of the message advertising users to react with thumbs up')
        parser.add_argument('--upload',
                            action="store_true",
                            help="Whether to upload resulting tarball to s3 or LOCAL_UPLOADS_DIR")
        parser.add_argument('--delete-after-upload',
                            action="store_true",
                            help='Automatically delete the local tarball after a successful export')
        self.add_realm_args(parser, True)

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        output_dir = options["output_dir"]
        public_only = options["public_only"]
        consent_message_id = options["consent_message_id"]

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="zulip-export-")
        else:
            output_dir = os.path.realpath(os.path.expanduser(output_dir))
            if os.path.exists(output_dir):
                if os.listdir(output_dir):
                    raise CommandError(
                        "Refusing to overwrite nonempty directory: %s. Aborting..."
                        % (output_dir,)
                    )
            else:
                os.makedirs(output_dir)

        tarball_path = output_dir.rstrip("/") + ".tar.gz"
        try:
            os.close(os.open(tarball_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666))
        except FileExistsError:
            raise CommandError("Refusing to overwrite existing tarball: %s. Aborting..." % (tarball_path,))

        print("\033[94mExporting realm\033[0m: %s" % (realm.string_id,))

        num_threads = int(options['threads'])
        if num_threads < 1:
            raise CommandError('You must have at least one thread.')

        if public_only and consent_message_id is not None:
            raise CommandError('Please pass either --public-only or --consent-message-id')

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
            reactions = Reaction.objects.filter(message=message,
                                                # outbox = 1f4e4
                                                emoji_code="1f4e4",
                                                reaction_type="unicode_emoji")
            for reaction in reactions:
                if reaction.user_profile.realm != realm:
                    raise CommandError("Users from a different realm reacted to message. Aborting...")

            print("\n\033[94mMessage content:\033[0m\n{}\n".format(message.content))

            print("\033[94mNumber of users that reacted outbox:\033[0m {}\n".format(len(reactions)))

        # Allows us to trigger exports separately from command line argument parsing
        export_realm_wrapper(realm=realm, output_dir=output_dir,
                             threads=num_threads, upload=options['upload'],
                             public_only=public_only,
                             delete_after_upload=options["delete_after_upload"],
                             consent_message_id=consent_message_id)
