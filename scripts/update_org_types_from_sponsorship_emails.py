#!/usr/bin/env python3

import mailbox
import os
import quopri
import sys
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from scripts.lib.setup_path import setup_path

setup_path()

os.environ["DJANGO_SETTINGS_MODULE"] = "zproject.settings"

import bs4
import django
from django.db import transaction

django.setup()

from corporate.models import ZulipSponsorshipRequest
from zerver.models import Realm, UserProfile, get_realm

# The keys in the dict below are the form values used in the
# old sponsorship form requests.
ORG_TYPE_MAPPING = {
    "open_source": Realm.ORG_TYPES["opensource"]["id"],
    "research": Realm.ORG_TYPES["research"]["id"],
    "education": Realm.ORG_TYPES["education"]["id"],
    "non_profit": Realm.ORG_TYPES["nonprofit"]["id"],
    "event": Realm.ORG_TYPES["event"]["id"],
    "other": Realm.ORG_TYPES["other"]["id"],
}


def parse_realm_string_id(support_url: bs4.element.Tag) -> str:
    return support_url.next_sibling.next_sibling.text.split("=")[-1]


def parse_website(website: bs4.element.Tag) -> Optional[str]:
    try:
        return website.next_sibling.next_sibling["href"]
    except Exception:
        # If there isn't an href, it's because the user entered
        # something that isn't actually a URL.  Inspecting the values
        # revealed none can be converted into a URL; so it's the
        # equivalent of leaving the field blank, which we record as
        # None.
        return None


def parse_org_type(org_type_string: bs4.element.Tag) -> str:
    return org_type_string.next_sibling.strip(":").strip().lower()


def parse_desc(desc: bs4.element.Tag) -> str:
    message = []
    pointer = desc.next_sibling.next_sibling.next_sibling
    while pointer.name != "br":
        message.append(str(pointer).strip())
        pointer = pointer.next_sibling

    return "".join(message)


def parse_requested_by_full_name(requested_by: bs4.element.Tag) -> str:
    name = requested_by.next_sibling.strip(":").strip().split("(")[0].strip()
    if name.endswith(" ·"):
        return name[:-2]
    return name


def parse_requested_by_role_name(requested_by: bs4.element.Tag) -> str:
    return requested_by.next_sibling.strip(":").strip().split("(")[-1].strip(")").strip()


mbox = mailbox.mbox("sponsorship.mbox")
sponsorships = []

for key, message in mbox.items():
    # Emails are exported in MIME-quoted-printable format
    email_html_str = quopri.decodestring(message.get_payload())
    email = bs4.BeautifulSoup(email_html_str, "html.parser")
    support_url, website, org_type_string, desc, requested_by = email.find_all("b")[0:5]
    sponsorship = {
        "realm_string_id": parse_realm_string_id(support_url),
        "website": parse_website(website),
        "org_type_string": parse_org_type(org_type_string),
        "desc": parse_desc(desc),
        "requested_by_full_name": parse_requested_by_full_name(requested_by),
        "requested_by_role_name": parse_requested_by_role_name(requested_by),
    }
    sponsorships.append(sponsorship)


for sponsorship in sponsorships:
    # Skip if the realm cannot be found
    try:
        string_id = sponsorship["realm_string_id"]
        assert string_id is not None
        realm = get_realm(string_id)
    except Realm.DoesNotExist:
        print("SKIPPING: Realm {} does not exist.".format(sponsorship["realm_string_id"]))
        continue
    # Skip if the realm already has a valid org type set
    if realm is None or realm.org_type != Realm.ORG_TYPES["unspecified"]["id"]:
        print("OK: Realm {} already has a valid org type.".format(realm.string_id))
        continue

    try:
        sponsorship_request = ZulipSponsorshipRequest.objects.get(realm=realm)
    except ZulipSponsorshipRequest.DoesNotExist:
        sponsorship_request = None

    if sponsorship_request:
        # Ignore realms that already have sponsorship requests in the
        # database.
        print(
            "SKIPPING: Realm {} already has a saved sponsorship request in the database".format(
                realm.string_id
            )
        )
        continue

    users = UserProfile.objects.filter(
        realm=realm, full_name__iexact=sponsorship["requested_by_full_name"]
    )
    requested_by_user: Optional[UserProfile] = None
    for user in users:
        if user.has_billing_access:
            requested_by_user = user
            break
        else:
            print(f"User {user.full_name} does not have billing access")

    if requested_by_user is None:
        if UserProfile.objects.filter(realm=realm, is_billing_admin=True).exists():
            requested_by_user = UserProfile.objects.get(realm=realm, is_billing_admin=True)
            print(
                f"Found requestor for {realm.string_id} via billing access: "
                + f'{requested_by_user.full_name} ?= {sponsorship["requested_by_full_name"]}'
            )

    if requested_by_user is None:
        print(
            "SKIPPING: Could not find a user with the full name {} who has billing access in realm {}.".format(
                sponsorship["requested_by_full_name"], realm.string_id
            )
        )
        continue

    org_type_string = sponsorship["org_type_string"]
    assert org_type_string is not None
    org_type_id = ORG_TYPE_MAPPING.get(org_type_string)
    if org_type_id is None:
        print(
            "SKIPPING: Realm {} has a sponsorship request with an invalid org type {}.".format(
                realm.string_id, sponsorship["org_type_string"]
            )
        )
        continue

    with transaction.atomic():
        print("Setting org type ID {} for realm {}...".format(org_type_id, realm.string_id))
        if realm.org_type != org_type_id:
            realm.org_type = org_type_id
            realm.save(update_fields=["org_type"])

        print("Creating sponsorship request for realm {}...".format(realm.string_id))
        sponsorship_request = ZulipSponsorshipRequest(
            realm=realm,
            requested_by=requested_by_user,
            org_website=sponsorship["website"],
            org_description=sponsorship["desc"],
            org_type=org_type_id,
        )
        sponsorship_request.save()
