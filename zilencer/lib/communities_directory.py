import logging
from datetime import timedelta
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.db.models import QuerySet
from django.utils.timezone import now as timezone_now

from corporate.lib.communities_directory import meets_communities_directory_base_criteria
from zerver.actions.message_send import internal_send_stream_message
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.thumbnail import BadImageError
from zerver.lib.upload import get_upload_backend
from zerver.models import Stream
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.models.users import get_system_bot
from zilencer.models import RemoteRealm

logger = logging.getLogger(__name__)

# How long an organization keeps being advertised after the last time we
# reached it. The job that probes runs daily, so this tolerates a server
# being down for maintenance, or a probe failing once.
REACHABILITY_WINDOW = timedelta(days=3)

MODERATION_CHANNEL_NAME = "signups"
MODERATION_TOPIC_NAME = "communities directory"

# The fields the directory shows, other than the icon; a change to any of
# them changes what visitors see, so a human should look at it.
MODERATED_FIELDS = ["name", "host", "description"]


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
    try:
        # An absolute path, so that a host carrying a path of its own cannot
        # redirect the probe somewhere else. The host is whatever the server
        # uploaded, so building the URL can fail as easily as fetching it.
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

    return True


def remote_realm_is_advertised(remote_realm: RemoteRealm) -> bool:
    """Whether the organization should appear in the communities directory.

    Computed rather than stored, so that an organization which stops
    meeting the criteria drops out on the next page load.
    """
    if not meets_communities_directory_base_criteria(
        description=remote_realm.description,
        invite_required=remote_realm.invite_required,
        emails_restricted_to_domains=remote_realm.emails_restricted_to_domains,
        has_web_public_streams=remote_realm.has_web_public_streams,
        is_demo_organization=remote_realm.is_demo_organization,
    ):
        return False

    if remote_realm.mirrored_icon_version == 0:
        # The directory shows our own copy of the icon, so there is
        # nothing to show until we have fetched one.
        return False

    return (
        remote_realm.last_reachable_datetime is not None
        and remote_realm.last_reachable_datetime > timezone_now() - REACHABILITY_WINDOW
    )


def mirror_remote_realm_icon(remote_realm: RemoteRealm) -> None:
    """Fetch the remote realm's icon and store our own copy of it."""
    # The organization's own server caps icons at MAX_ICON_FILE_SIZE_MIB, but
    # we are reading from a server that need not have honoured that.
    size_limit = settings.MAX_ICON_FILE_SIZE_MIB * 1024 * 1024
    image_data = b""
    try:
        # Streamed, so that we stop reading an oversized response rather
        # than holding all of it first.
        with OutgoingSession(
            role="communities_directory",
            timeout=10,
        ).get(remote_realm.icon_url, stream=True) as response:
            if response.status_code != 200:
                logger.info(
                    "Icon fetch for %s returned status %d", remote_realm.host, response.status_code
                )
                return

            for chunk in response.iter_content(chunk_size=64 * 1024):
                image_data += chunk
                if len(image_data) > size_limit:
                    logger.info("Icon for %s is larger than we accept", remote_realm.host)
                    return
    except requests.RequestException as e:
        logger.info("Icon fetch for %s failed: %s", remote_realm.host, e)
        return

    try:
        get_upload_backend().store_remote_realm_icon_image(str(remote_realm.uuid), image_data)
    except BadImageError:
        logger.info("Icon for %s is not an image we can use", remote_realm.host)
        return

    remote_realm.last_mirrored_icon_url = remote_realm.icon_url
    remote_realm.mirrored_icon_version += 1


def post_communities_directory_moderation_message(message: str) -> None:
    """Post to the channel staff watch, so that a human sees what the
    directory has started showing, or what an organization changed it to.
    """
    admin_realm = get_realm(settings.SYSTEM_BOT_REALM)
    sender = get_system_bot(settings.NOTIFICATION_BOT, admin_realm.id)
    try:
        channel = get_stream(MODERATION_CHANNEL_NAME, admin_realm)
    except Stream.DoesNotExist:
        logger.error("No channel named %s to post to", MODERATION_CHANNEL_NAME)
        return

    internal_send_stream_message(sender, channel, MODERATION_TOPIC_NAME, message)


def post_remote_realm_first_advertised(remote_realm: RemoteRealm) -> None:
    icon_url = get_upload_backend().get_remote_realm_icon_url(
        str(remote_realm.uuid), remote_realm.mirrored_icon_version
    )
    post_communities_directory_moderation_message(
        f"[{remote_realm.name}](https://{remote_realm.host}) is now listed.\n\n"
        f"{remote_realm.description}\n\n"
        f"![icon]({icon_url})",
    )


def post_remote_realm_listing_changed(
    remote_realm: RemoteRealm, changes: list[tuple[str, str, str]]
) -> None:
    changed_lines = "\n".join(
        f"**{attr_name}**: ~~{old_value}~~ {new_value}"
        for attr_name, old_value, new_value in changes
    )
    post_communities_directory_moderation_message(
        f"[{remote_realm.name}](https://{remote_realm.host}) changed what the "
        f"directory shows.\n\n{changed_lines}",
    )


def post_remote_realm_icon_changed(remote_realm: RemoteRealm) -> None:
    icon_url = get_upload_backend().get_remote_realm_icon_url(
        str(remote_realm.uuid), remote_realm.mirrored_icon_version
    )
    post_communities_directory_moderation_message(
        f"[{remote_realm.name}](https://{remote_realm.host}) changed its icon.\n\n"
        f"![icon]({icon_url})",
    )


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
        if not is_remote_realm_reachable(remote_realm):
            continue

        remote_realm.last_reachable_datetime = now
        if remote_realm.last_mirrored_icon_url != remote_realm.icon_url:
            # A failure here leaves the copy we already have in place,
            # stale icon is shown until next probe - which is acceptable.
            previous_icon_version = remote_realm.mirrored_icon_version
            mirror_remote_realm_icon(remote_realm)
            if (
                remote_realm.mirrored_icon_version != previous_icon_version
                # A first copy is shown by the post announcing the listing.
                and previous_icon_version > 0
                and remote_realm.first_advertised_datetime is not None
            ):
                post_remote_realm_icon_changed(remote_realm)
        if remote_realm.first_advertised_datetime is None and remote_realm_is_advertised(
            remote_realm
        ):
            remote_realm.first_advertised_datetime = now
            post_remote_realm_first_advertised(remote_realm)
        reached.append(remote_realm)

    RemoteRealm.objects.bulk_update(
        reached,
        [
            "last_reachable_datetime",
            "last_mirrored_icon_url",
            "mirrored_icon_version",
            "first_advertised_datetime",
        ],
    )
    logger.info("Probed %d organizations, reached %d", probed_count, len(reached))
