import logging
import shutil
import tempfile
from typing import Any

from django.conf import settings

from confirmation import settings as confirmation_settings
from zerver.actions.realm_settings import do_delete_all_realm_attachments
from zerver.actions.users import do_change_user_role
from zerver.context_processors import is_realm_import_enabled
from zerver.data_import.slack import do_convert_zipfile
from zerver.lib.exceptions import SlackImportInvalidFileError
from zerver.lib.import_realm import do_import_realm
from zerver.lib.upload import save_attachment_contents
from zerver.models.prereg_users import PreregistrationRealm
from zerver.models.realms import Realm
from zerver.models.users import UserProfile, get_user_by_delivery_email

logger = logging.getLogger(__name__)


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

    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"import-{preregistration_realm.id}-slack-",
            suffix=".zip",
            dir=settings.IMPORT_TMPFILE_DIRECTORY,
        ) as fh:
            save_attachment_contents(event["filename"], fh)
            fh.flush()
            do_convert_zipfile(
                fh.name,
                output_dir,
                event["slack_access_token"],
            )

            realm = do_import_realm(output_dir, string_id)
            realm.org_type = preregistration_realm.org_type
            realm.default_language = preregistration_realm.default_language
            realm.save()

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
                        importing_user, UserProfile.ROLE_REALM_OWNER, acting_user=importing_user
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
