import logging
import shutil
import tempfile
from typing import Any

from django.conf import settings

from confirmation import settings as confirmation_settings
from zerver.actions.realm_settings import do_delete_all_realm_attachments
from zerver.data_import.slack import do_convert_zipfile
from zerver.lib.import_realm import do_import_realm
from zerver.lib.upload import save_attachment_contents
from zerver.models.prereg_users import PreregistrationRealm
from zerver.models.realms import Realm
from zerver.models.users import UserProfile

logger = logging.getLogger(__name__)


def import_slack_data(event: dict[str, Any]) -> None:
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
            try:  # nocoverage
                prereg_user = UserProfile.objects.get(
                    delivery_email__iexact=preregistration_realm.email, realm=realm
                )
                if prereg_user.role != UserProfile.ROLE_REALM_OWNER:
                    prereg_user.role = UserProfile.ROLE_REALM_OWNER
                    prereg_user.save(update_fields=["role"])
                preregistration_realm.status = confirmation_settings.STATUS_USED
                preregistration_realm.created_realm = realm
            except UserProfile.DoesNotExist:
                # The email address in the import may not match the email
                # address they provided. Ask user which user they want to become.
                preregistration_realm.data_import_metadata["no_user_matching_email"] = True

            preregistration_realm.data_import_metadata["is_import_work_queued"] = False
            preregistration_realm.save()
    except Exception as e:  # nocoverage
        logger.exception(e)
        try:
            # Clean up the realm if the import failed
            preregistration_realm.created_realm = None
            preregistration_realm.data_import_metadata["is_import_work_queued"] = False
            preregistration_realm.save()

            realm = Realm.objects.get(string_id=string_id)
            do_delete_all_realm_attachments(realm)
            realm.delete()
        except Realm.DoesNotExist:
            pass
        raise
    finally:
        shutil.rmtree(output_dir)
