from typing import Dict, Optional

from django.conf import settings

from zerver.lib.compatibility import is_outdated_server
from zerver.lib.emoji import server_emoji_data_url
from zerver.lib.external_accounts import get_default_external_accounts
from zerver.lib.push_notifications import push_notifications_enabled
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.realm_logo import get_realm_logo_source, get_realm_logo_url
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import MAX_TOPIC_NAME_LENGTH, Realm, Stream, UserProfile
from zproject.backends import email_auth_enabled, password_auth_enabled


def get_realm_bundle(user_profile: Optional[UserProfile], realm: Realm) -> Dict[str, object]:
    state = {}

    # The realm bundle includes both realm properties and server
    # properties, since it's rare that one would want one and not
    # the other. We expect most clients to want it.
    #
    # A note on naming: For some settings, one could imagine
    # having a server-level value and a realm-level value (with
    # the server value serving as the default for the realm
    # value). For such settings, we prefer the following naming
    # scheme:
    #
    # * realm_inline_image_preview (current realm setting)
    # * server_inline_image_preview (server-level default)
    #
    # In situations where for backwards-compatibility reasons we
    # have an unadorned name, we should arrange that clients using
    # that unadorned name work correctly (i.e. that should be the
    # currently active setting, not a server-level default).
    #
    # Other settings, which are just server-level settings or data
    # about the version of Zulip, can be named without prefixes,
    # e.g. giphy_rating_options or development_environment.
    for property_name in Realm.property_types:
        state["realm_" + property_name] = getattr(realm, property_name)

    realm_authentication_methods_dict = realm.authentication_methods_dict()

    # We pretend these features are disabled because anonymous
    # users can't access them.  In the future, we may want to move
    # this logic to the frontends, so that we can correctly
    # display what these fields are in the settings.
    state["realm_allow_message_editing"] = (
        False if user_profile is None else realm.allow_message_editing
    )
    state["realm_edit_topic_policy"] = (
        Realm.POLICY_ADMINS_ONLY if user_profile is None else realm.edit_topic_policy
    )
    state["realm_delete_own_message_policy"] = (
        Realm.POLICY_ADMINS_ONLY if user_profile is None else realm.delete_own_message_policy
    )

    # This setting determines whether to send presence and also
    # whether to display of users list in the right sidebar; we
    # want both behaviors for logged-out users.  We may in the
    # future choose to move this logic to the frontend.
    state["realm_presence_disabled"] = True if user_profile is None else realm.presence_disabled

    def realm_digest_emails_enabled() -> bool:
        return realm.digest_emails_enabled and settings.SEND_DIGEST_EMAILS

    def realm_password_auth_enabled() -> bool:
        return password_auth_enabled(realm, realm_authentication_methods_dict)

    state["development_environment"] = settings.DEVELOPMENT
    state["event_queue_longpoll_timeout_seconds"] = settings.EVENT_QUEUE_LONGPOLL_TIMEOUT_SECONDS
    state["giphy_rating_options"] = realm.get_giphy_rating_options()
    state["max_avatar_file_size_mib"] = settings.MAX_AVATAR_FILE_SIZE_MIB
    state["max_file_upload_size_mib"] = settings.MAX_FILE_UPLOAD_SIZE
    state["max_icon_file_size_mib"] = settings.MAX_ICON_FILE_SIZE_MIB
    state["max_logo_file_size_mib"] = settings.MAX_LOGO_FILE_SIZE_MIB
    state["max_message_length"] = settings.MAX_MESSAGE_LENGTH
    state["max_stream_description_length"] = Stream.MAX_DESCRIPTION_LENGTH
    state["max_stream_name_length"] = Stream.MAX_NAME_LENGTH
    state["max_topic_length"] = MAX_TOPIC_NAME_LENGTH
    state["password_min_guesses"] = settings.PASSWORD_MIN_GUESSES
    state["password_min_length"] = settings.PASSWORD_MIN_LENGTH
    state["realm_authentication_methods"] = realm_authentication_methods_dict
    state["realm_available_video_chat_providers"] = realm.VIDEO_CHAT_PROVIDERS
    state["realm_bot_domain"] = realm.get_bot_domain()
    state["realm_date_created"] = datetime_to_timestamp(realm.date_created)
    state["realm_default_external_accounts"] = get_default_external_accounts()
    state["realm_digest_emails_enabled"] = realm_digest_emails_enabled()
    state["realm_email_auth_enabled"] = email_auth_enabled(realm, realm_authentication_methods_dict)
    state["realm_icon_source"] = realm.icon_source
    state["realm_icon_url"] = realm_icon_url(realm)
    state["realm_is_zephyr_mirror_realm"] = realm.is_zephyr_mirror_realm
    state["realm_logo_source"] = get_realm_logo_source(realm, night=False)
    state["realm_logo_url"] = get_realm_logo_url(realm, night=False)
    state["realm_night_logo_source"] = get_realm_logo_source(realm, night=True)
    state["realm_night_logo_url"] = get_realm_logo_url(realm, night=True)
    state["realm_org_type"] = realm.org_type
    state["realm_password_auth_enabled"] = realm_password_auth_enabled()
    state["realm_plan_type"] = realm.plan_type
    state["realm_push_notifications_enabled"] = push_notifications_enabled()
    state["realm_upload_quota_mib"] = realm.upload_quota_bytes()
    state["realm_uri"] = realm.uri
    state["server_avatar_changes_disabled"] = settings.AVATAR_CHANGES_DISABLED
    state["server_emoji_data_url"] = server_emoji_data_url()
    state["server_generation"] = settings.SERVER_GENERATION
    state["server_inline_image_preview"] = settings.INLINE_IMAGE_PREVIEW
    state["server_inline_url_embed_preview"] = settings.INLINE_URL_EMBED_PREVIEW
    state["server_name_changes_disabled"] = settings.NAME_CHANGES_DISABLED
    state["server_needs_upgrade"] = is_outdated_server(user_profile)
    state["server_presence_offline_threshold_seconds"] = settings.OFFLINE_THRESHOLD_SECS
    state["server_presence_ping_interval_seconds"] = settings.PRESENCE_PING_INTERVAL_SECS
    state["server_web_public_streams_enabled"] = settings.WEB_PUBLIC_STREAMS_ENABLED
    state["settings_send_digest_emails"] = settings.SEND_DIGEST_EMAILS
    state["upgrade_text_for_wide_organization_logo"] = str(Realm.UPGRADE_TEXT_STANDARD)
    state["zulip_plan_is_not_limited"] = realm.plan_type != Realm.PLAN_TYPE_LIMITED

    if settings.JITSI_SERVER_URL is not None:
        state["jitsi_server_url"] = settings.JITSI_SERVER_URL.rstrip("/")
    else:  # nocoverage
        state["jitsi_server_url"] = None

    if realm.notifications_stream and not realm.notifications_stream.deactivated:
        notifications_stream = realm.notifications_stream
        state["realm_notifications_stream_id"] = notifications_stream.id
    else:
        state["realm_notifications_stream_id"] = -1

    signup_notifications_stream = realm.get_signup_notifications_stream()
    if signup_notifications_stream:
        state["realm_signup_notifications_stream_id"] = signup_notifications_stream.id
    else:
        state["realm_signup_notifications_stream_id"] = -1

    if realm.demo_organization_scheduled_deletion_date is not None:
        state["demo_organization_scheduled_deletion_date"] = datetime_to_timestamp(
            realm.demo_organization_scheduled_deletion_date
        )
    return state
