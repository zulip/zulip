from typing import TypedDict

from zerver.lib.realm_description import get_realm_text_description
from zerver.lib.realm_icon import get_realm_icon_url
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import Realm
from zerver.models.realms import OrgTypeDict


class RealmDict(TypedDict):
    id: int
    name: str
    description: str
    icon_url: str
    realm_url: str
    date_created: int
    org_type_key: str


def get_public_realms_that_want_to_be_advertised() -> tuple[
    list[RealmDict], dict[str, OrgTypeDict]
]:
    eligible_realms = []
    unique_org_type_ids = set()
    want_to_be_advertised_realms = (
        Realm.objects.filter(
            want_advertise_in_communities_directory=True,
        )
        .exclude(
            # Filter out realms who haven't changed their description from the default.
            description="",
        )
        .exclude(
            # Filter out demo organizations.
            demo_organization_scheduled_deletion_date__isnull=False,
        )
        .order_by("name")
    )
    for realm in want_to_be_advertised_realms:
        open_to_public = not realm.invite_required and not realm.emails_restricted_to_domains
        if realm.allow_web_public_streams_access() or open_to_public:
            org_type_key = next(
                (key for key in Realm.ORG_TYPES if Realm.ORG_TYPES[key]["id"] == realm.org_type),
                None,
            )

            if org_type_key is None:
                continue  # nocoverage

            date_created = datetime_to_timestamp(realm.date_created)
            eligible_realms.append(
                RealmDict(
                    id=realm.id,
                    name=realm.name,
                    description=get_realm_text_description(realm),
                    icon_url=get_realm_icon_url(realm),
                    realm_url=realm.url,
                    date_created=date_created,
                    org_type_key=org_type_key,
                )
            )
            unique_org_type_ids.add(realm.org_type)

    # Custom list of org filters to show.
    CATEGORIES_TO_OFFER = [
        "opensource",
        "research",
        "community",
    ]

    # Remove org_types for which there are no open organizations.
    org_types = dict()
    for org_type in CATEGORIES_TO_OFFER:
        if Realm.ORG_TYPES[org_type]["id"] in unique_org_type_ids:
            org_types[org_type] = Realm.ORG_TYPES[org_type]

    # This code is not required right bot could be useful in future.
    # If we ever decided to show all the ORG_TYPES.
    # Remove `Unspecified` ORG_TYPE
    # org_types.pop("unspecified", None)

    # Change display name of non-profit orgs.
    # if org_types.get("nonprofit"):  # nocoverage
    #    org_types["nonprofit"]["name"] = "Non-profit"
    return eligible_realms, org_types
