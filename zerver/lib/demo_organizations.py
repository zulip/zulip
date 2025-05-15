from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.models.realms import Realm


def check_demo_organization_has_set_email(realm: Realm) -> None:
    # This should be called after checking that the realm has
    # a demo_organization_scheduled_deletion_date set.
    assert realm.demo_organization_scheduled_deletion_date is not None
    human_owner_emails = set(realm.get_human_owner_users().values_list("delivery_email", flat=True))
    if "" in human_owner_emails:
        raise JsonableError(_("Configure owner account email address."))
