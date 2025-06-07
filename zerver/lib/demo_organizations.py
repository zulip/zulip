from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.models.realms import Realm


def demo_organization_owner_email_exists(realm: Realm) -> bool:
    human_owner_emails = set(realm.get_human_owner_users().values_list("delivery_email", flat=True))
    return human_owner_emails != {""}


def check_demo_organization_has_set_email(realm: Realm) -> None:
    # This should be called after checking that the realm has
    # a demo_organization_scheduled_deletion_date set.
    assert realm.demo_organization_scheduled_deletion_date is not None
    if not demo_organization_owner_email_exists(realm):
        raise JsonableError(_("Configure owner account email address."))
