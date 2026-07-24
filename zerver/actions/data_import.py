import glob
import logging
import os
import shutil
import tempfile
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError
from django.utils.timezone import now as timezone_now

from confirmation import settings as confirmation_settings
from zerver.actions.create_realm import get_email_address_visibility_default
from zerver.actions.create_user import do_reactivate_user
from zerver.actions.realm_settings import do_delete_realm
from zerver.actions.users import do_change_user_role
from zerver.context_processors import is_realm_import_enabled
from zerver.data_import.slack import do_convert_zipfile
from zerver.lib.exceptions import SlackImportInvalidFileError
from zerver.lib.import_realm import do_import_realm
from zerver.lib.upload import save_attachment_contents
from zerver.models.prereg_users import PreregistrationRealm
from zerver.models.realms import Realm, get_realm
from zerver.models.users import RealmUserDefault, UserProfile, get_user_by_delivery_email

logger = logging.getLogger("zulip.registration")


def is_string_id_unique_violation(e: BaseException) -> bool:
    """True when e is the IntegrityError from violating the unique constraint
    on Realm.string_id -- i.e. the subdomain is already taken by another
    realm. Other IntegrityErrors (e.g. genuine bugs elsewhere in the import)
    return False, so they get the normal failure handling rather than being
    mistaken for a taken subdomain."""
    if not isinstance(e, IntegrityError):
        return False
    # Django wraps the underlying psycopg2 error as __cause__; its
    # diagnostics carry the Postgres constraint name.
    diag = getattr(e.__cause__, "diag", None)
    return getattr(diag, "constraint_name", None) == "zerver_realm_string_id_key"


def import_slack_data(event: dict[str, Any]) -> None:
    # This is only possible if data imports were enqueued before the
    # setting was turned off.
    assert is_realm_import_enabled()

    preregistration_realm = PreregistrationRealm.objects.get(id=event["preregistration_realm_id"])
    string_id = preregistration_realm.string_id

    if preregistration_realm.created_realm is not None:
        # A prior delivery of this event already finished the import. The
        # worker can die after a successful import but before the event is
        # acked, which redelivers the event; there is nothing left to do.
        logger.info("(%s) Slack import already completed; skipping redelivery", string_id)
        return

    try:
        existing_realm: Realm | None = get_realm(string_id)
    except Realm.DoesNotExist:
        existing_realm = None
    if existing_realm is not None:
        if preregistration_realm.data_import_metadata.get("import_created_realm_id") == (
            existing_realm.id
        ):
            # A prior attempt of *this* import created the realm and then the
            # worker died before finishing, and the event was redelivered.
            # The realm is our own half-imported orphan, so delete it and
            # re-import below, rather than treating it as a foreign conflict.
            logger.warning(
                "(%s) Cleaning up our own orphaned realm from a prior import attempt", string_id
            )
            orphan = Realm.objects.get(id=existing_realm.id)
            assert orphan.date_created >= timezone_now() - timedelta(hours=24)
            do_delete_realm(orphan)
        else:
            # The subdomain is taken by an earlier or concurrent import of the
            # same subdomain that won the race to create the realm (string_id
            # is unique). Importing would fail on that unique constraint, and
            # we must not touch the other import's realm, so abort before the
            # expensive conversion work and surface the conflict to the user.
            logger.error("(%s) Aborting Slack import: subdomain is already in use", string_id)
            preregistration_realm.data_import_metadata["is_import_work_queued"] = False
            preregistration_realm.data_import_metadata["subdomain_unavailable"] = True
            preregistration_realm.save(update_fields=["data_import_metadata"])
            return

    output_dir = tempfile.mkdtemp(
        prefix=f"import-{preregistration_realm.id}-converted-",
        dir=settings.IMPORT_TMPFILE_DIRECTORY,
    )
    logger.info(
        "(%s) Starting Slack import from %s / %s",
        string_id,
        event["filename"],
        event["slack_access_token"],
    )

    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"import-{preregistration_realm.id}-slack-",
            suffix=".zip",
            dir=settings.IMPORT_TMPFILE_DIRECTORY,
        ) as fh:
            save_attachment_contents(event["filename"], fh)
            fh.flush()
            logger.info(
                "(%s) Wrote %d bytes of %s to %s", string_id, fh.tell(), event["filename"], fh.name
            )
            do_convert_zipfile(
                fh.name,
                output_dir,
                event["slack_access_token"],
                convert_slack_threads=True,
            )
            attachment_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(f"{output_dir}/uploads/")
                for filename in filenames
            )
            message_count = len(glob.glob(f"{output_dir}/messages-*.json")) * 1000
            logger.info(
                "(%s) Completed conversion into %s (%d MB attachments, <= %d messages)",
                string_id,
                output_dir,
                attachment_size / 1024 / 1024,
                message_count,
            )

            def record_created_realm(new_realm: Realm) -> None:
                # Stamp the registration with the realm it owns, atomically
                # with the realm's creation, so a redelivered import (after a
                # crash) can recognize and clean up its own half-imported realm
                # instead of mistaking it for a foreign conflict.
                preregistration_realm.data_import_metadata["import_created_realm_id"] = new_realm.id
                preregistration_realm.save(update_fields=["data_import_metadata"])

            realm = do_import_realm(output_dir, string_id, on_realm_created=record_created_realm)
            logger.info("(%s) Completed import, performing post-import steps", string_id)
            realm.org_type = preregistration_realm.org_type
            realm.default_language = preregistration_realm.default_language
            realm.save()

            realm_user_default = RealmUserDefault.objects.get(realm=realm)
            realm_user_default.email_address_visibility = (
                preregistration_realm.data_import_metadata.get(
                    "email_address_visibility",
                    get_email_address_visibility_default(realm.org_type),
                )
            )
            realm_user_default.save(update_fields=["email_address_visibility"])

            # Set email address visibility for all users in the realm.
            UserProfile.objects.filter(realm=realm, is_bot=False).update(
                email_address_visibility=realm_user_default.email_address_visibility
            )

            # Try finding the user who imported this realm and make them owner.
            try:
                importing_user: UserProfile | None = get_user_by_delivery_email(
                    preregistration_realm.email, realm
                )
            except UserProfile.DoesNotExist:
                importing_user = None

            if importing_user is None or importing_user.is_bot or importing_user.is_mirror_dummy:
                # The email address that the importing user validated
                # with Zulip either does not appear in the data export,
                # or maps to an account that cannot own the
                # organization (a bot or a placeholder/mirror-dummy
                # account). Prompt them to pick which account is theirs.
                preregistration_realm.data_import_metadata["need_select_realm_owner"] = True
            else:
                if not importing_user.is_active:
                    # The importer's account was deactivated in the
                    # export; reactivate it so they can own the realm.
                    do_reactivate_user(importing_user, acting_user=None)
                if importing_user.role != UserProfile.ROLE_REALM_OWNER:
                    do_change_user_role(
                        importing_user,
                        UserProfile.ROLE_REALM_OWNER,
                        acting_user=importing_user,
                        notify=False,
                    )
                preregistration_realm.status = confirmation_settings.STATUS_USED

            preregistration_realm.created_realm = realm
            preregistration_realm.data_import_metadata["is_import_work_queued"] = False
            preregistration_realm.save()
            logger.info("(%s) All done!", string_id)
    except Exception as e:
        logger.exception(e)
        try:
            preregistration_realm.created_realm = None
            preregistration_realm.data_import_metadata["is_import_work_queued"] = False
            if type(e) is SlackImportInvalidFileError:
                # Store the error to be displayed to the user.
                preregistration_realm.data_import_metadata["invalid_file_error_message"] = str(e)

            # do_import_realm creates the realm with this string_id. If a
            # concurrent or earlier import of the same subdomain won the
            # race to create it, our realm insert violates the unique
            # constraint on Realm.string_id and do_import_realm raises that
            # IntegrityError. The existing realm belongs to the other
            # import, so we must not clean it up: deleting it would destroy
            # their data and can deadlock against their in-progress work on
            # zerver_userprofile. We record the conflict for the status poll
            # to surface instead.
            subdomain_taken = is_string_id_unique_violation(e)
            if subdomain_taken:
                preregistration_realm.data_import_metadata["subdomain_unavailable"] = True
            preregistration_realm.save()

            # For any other failure -- including IntegrityErrors from
            # genuine bugs on some other constraint -- delete the realm
            # this import created, if it got that far. A failure before
            # do_import_realm creates the realm (e.g. an invalid-file error
            # during conversion) leaves no such realm, so the get() below
            # raises Realm.DoesNotExist, which we swallow. Otherwise the
            # realm with this string_id is the (possibly half-imported) one
            # we created. The age assertion is a last line of defense
            # against a bug ever pointing this deletion at an established
            # realm; a Slack import's realm is created at conversion time,
            # so it is always far younger than a day by the time we get
            # here.
            if not subdomain_taken:
                realm = Realm.objects.get(string_id=string_id)
                assert realm.date_created >= timezone_now() - timedelta(hours=24)
                do_delete_realm(realm)
        except Realm.DoesNotExist:
            pass
        raise
    finally:
        shutil.rmtree(output_dir)
