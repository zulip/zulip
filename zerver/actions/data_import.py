import glob
import logging
import os
import shutil
import tempfile
from typing import Any

from django.conf import settings

from confirmation import settings as confirmation_settings
from zerver.actions.create_realm import get_email_address_visibility_default
from zerver.actions.realm_settings import do_delete_all_realm_attachments
from zerver.actions.users import do_change_user_role
from zerver.context_processors import is_realm_import_enabled
from zerver.data_import.slack import do_convert_zipfile
from zerver.lib.exceptions import SlackImportInvalidFileError
from zerver.lib.import_realm import do_import_realm
from zerver.lib.upload import save_attachment_contents
from zerver.models.prereg_users import PreregistrationRealm
from zerver.models.realms import Realm
from zerver.models.users import RealmUserDefault, UserProfile, get_user_by_delivery_email

logger = logging.getLogger("zulip.registration")


def import_slack_data(event: dict[str, Any]) -> None:
    # This is only possible if data imports were enqueued before the
    # setting was turned off.
    assert is_realm_import_enabled()

    preregistration_realm = PreregistrationRealm.objects.get(id=event["preregistration_realm_id"])
    string_id = preregistration_realm.string_id
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

            realm = do_import_realm(output_dir, string_id)
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
                importing_user = get_user_by_delivery_email(preregistration_realm.email, realm)
                assert (
                    importing_user.is_active
                    and not importing_user.is_bot
                    and not importing_user.is_mirror_dummy
                )
                if importing_user.role != UserProfile.ROLE_REALM_OWNER:
                    do_change_user_role(
                        importing_user,
                        UserProfile.ROLE_REALM_OWNER,
                        acting_user=importing_user,
                        notify=False,
                    )
                preregistration_realm.status = confirmation_settings.STATUS_USED
            except UserProfile.DoesNotExist:
                # If the email address that the importing user
                # validated with Zulip does not appear in the data
                # export, we will prompt them which account is theirs.
                preregistration_realm.data_import_metadata["need_select_realm_owner"] = True

            preregistration_realm.created_realm = realm
            preregistration_realm.data_import_metadata["is_import_work_queued"] = False
            preregistration_realm.save()
            logger.info("(%s) All done!", string_id)
    except Exception as e:
        logger.exception(e)
        try:
            # Clean up the realm if the import failed
            preregistration_realm.created_realm = None
            preregistration_realm.data_import_metadata["is_import_work_queued"] = False
            if type(e) is SlackImportInvalidFileError:
                # Store the error to be displayed to the user.
                preregistration_realm.data_import_metadata["invalid_file_error_message"] = str(e)
            preregistration_realm.save()

            realm = Realm.objects.get(string_id=string_id)
            do_delete_all_realm_attachments(realm)
            realm.delete()
        except Realm.DoesNotExist:
            pass
        raise
    finally:
        shutil.rmtree(output_dir)
