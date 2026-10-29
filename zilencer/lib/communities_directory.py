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
        communities_directory_listing_requested=True,
        registration_deactivated=False,
        realm_deactivated=False,
        realm_locally_deleted=False,
        server__deactivated=False,
    )


def is_remote_realm_reachable(remote_realm: RemoteRealm) -> bool:
    """Whether the organization's host answers as a Zulip server, so that we
    do not advertise a link that is dead.

    The host is self-reported by the server that uploaded it, and the
    response carries no realm UUID, so this establishes that a Zulip realm
    answers there, not that it is the one we hold metadata for.
    """
    try:
        # The host is unvalidated input from the remote server. Joining an
        # absolute path discards any path, query or fragment in it.
        # OutgoingSession proxying through Smokescreen keeps the request
        # away from internal addresses. A malformed host makes urljoin
        # raise ValueError.
        url = urljoin(f"https://{remote_realm.host}", "/api/v1/server_settings")
        response = OutgoingSession(
            role="communities_directory",
            # One quick attempt each, so a slow organization cannot hold up
            # the pass. It takes several days of failures to stop being
            # listed, so the next pass is the retry.
            timeout=10,
        ).get(url)
    except (ValueError, requests.RequestException) as e:
        logger.info("Probe for %s failed: %s", remote_realm.host, e)
        return False

    if response.status_code != 200:
        logger.info("Probe for %s returned status %d", remote_realm.host, response.status_code)
        return False

    try:
        server_settings = response.json()
    except requests.exceptions.JSONDecodeError:
        logger.info("Probe for %s did not return valid JSON", remote_realm.host)
        return False

    if not isinstance(server_settings, dict) or "zulip_version" not in server_settings:
        logger.info("Probe for %s did not answer as a Zulip realm", remote_realm.host)
        return False

    realm_url = server_settings.get("realm_url")
    if realm_url != f"https://{remote_realm.host}":
        logger.info("Probe for %s answered as %s", remote_realm.host, realm_url)
        return False

    return True


def check_remote_realms_active_for_communities_directory() -> None:
    now = timezone_now()
    reached_count = 0
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
        if not is_remote_realm_reachable(remote_realm):
            continue

        remote_realm.last_reachable_datetime = now
        remote_realm.save(update_fields=["last_reachable_datetime"])
        reached_count += 1

    logger.info("Probed %d organizations, reached %d", probed_count, reached_count)
