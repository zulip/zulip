import logging
from urllib.parse import urljoin

import requests
from django.db.models import QuerySet
from django.utils.timezone import now as timezone_now

from corporate.lib.communities_directory import meets_communities_directory_base_criteria
from zerver.lib.outgoing_http import OutgoingSession
from zilencer.models import RemoteRealm

logger = logging.getLogger(__name__)


def get_remote_realms_asking_to_be_advertised() -> QuerySet[RemoteRealm]:
    return RemoteRealm.objects.filter(
        asks_to_advertise_in_communities_directory=True,
        registration_deactivated=False,
        realm_deactivated=False,
        realm_locally_deleted=False,
    )


def is_remote_realm_reachable(remote_realm: RemoteRealm) -> bool:
    """Whether the organization's host answers as a Zulip server, so that we
    do not advertise a link that is dead.

    The host is self-reported by the server that uploaded it, and the
    response carries no realm UUID, so this establishes that a Zulip realm
    answers there, not that it is the one we hold metadata for.
    """
    # An absolute path, so that a host carrying a path of its own cannot
    # redirect the probe somewhere else.
    url = urljoin(f"https://{remote_realm.host}", "/api/v1/server_settings")
    try:
        response = OutgoingSession(
            role="communities_directory",
            # One quick attempt each, so a slow organization cannot hold up
            # the pass. It takes several days of failures to stop being
            # listed, so the next pass is the retry.
            timeout=10,
        ).get(url)
    except requests.RequestException as e:
        logger.info("Probe for %s failed: %s", remote_realm.host, e)
        return False

    if response.status_code != 200:
        logger.info("Probe for %s returned status %d", remote_realm.host, response.status_code)
        return False

    try:
        return "zulip_version" in response.json()
    except ValueError:
        logger.info("Probe for %s did not return JSON", remote_realm.host)
        return False


def probe_remote_realms_for_communities_directory() -> None:
    now = timezone_now()
    reached = []
    probed_count = 0

    for remote_realm in get_remote_realms_asking_to_be_advertised():
        if not meets_communities_directory_base_criteria(
            description=remote_realm.description,
            invite_required=remote_realm.invite_required,
            emails_restricted_to_domains=remote_realm.emails_restricted_to_domains,
            has_web_public_streams=remote_realm.has_web_public_streams,
            is_demo_organization=remote_realm.is_demo_organization,
        ):
            # No point spending a request on an organization we would not
            # advertise whatever the answer.
            continue

        probed_count += 1
        if is_remote_realm_reachable(remote_realm):
            remote_realm.last_reachable_datetime = now
            reached.append(remote_realm)

    RemoteRealm.objects.bulk_update(reached, ["last_reachable_datetime"])
    logger.info("Probed %d organizations, reached %d", probed_count, len(reached))
