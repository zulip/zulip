# See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html for
# high-level documentation on how this system works.
import copy
import logging
import time
from typing import Any, Callable, Collection, Dict, Iterable, Mapping, Optional, Sequence, Set

from django.conf import settings
from django.utils.translation import gettext as _

from version import API_FEATURE_LEVEL, ZULIP_MERGE_BASE, ZULIP_VERSION
from zerver.actions.default_streams import default_stream_groups_to_dicts_sorted
from zerver.actions.realm_settings import get_realm_authentication_methods_for_page_params_api
from zerver.actions.users import get_owned_bot_dicts
from zerver.lib import emoji
from zerver.lib.alert_words import user_alert_words
from zerver.lib.avatar import avatar_url
from zerver.lib.bot_config import load_bot_config_template
from zerver.lib.compatibility import is_outdated_server
from zerver.lib.default_streams import get_default_streams_for_realm_as_dicts
from zerver.lib.exceptions import JsonableError
from zerver.lib.external_accounts import get_default_external_accounts
from zerver.lib.hotspots import get_next_onboarding_steps
from zerver.lib.integrations import (
    EMBEDDED_BOTS,
    WEBHOOK_INTEGRATIONS,
    get_all_event_types_for_integration,
)
from zerver.lib.message import (
    add_message_to_unread_msgs,
    aggregate_unread_data,
    apply_unread_message_event,
    extract_unread_data_from_um_rows,
    get_raw_unread_data,
    get_recent_conversations_recipient_id,
    get_recent_private_conversations,
    get_starred_message_ids,
    remove_message_id_from_unread_mgs,
)
from zerver.lib.muted_users import get_user_mutes
from zerver.lib.narrow_helpers import NarrowTerm, read_stop_words
from zerver.lib.narrow_predicate import check_narrow_for_events
from zerver.lib.presence import get_presence_for_user, get_presences_for_realm
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.realm_logo import get_realm_logo_source, get_realm_logo_url
from zerver.lib.scheduled_messages import get_undelivered_scheduled_messages
from zerver.lib.soft_deactivation import reactivate_user_if_soft_deactivated
from zerver.lib.sounds import get_available_notification_sounds
from zerver.lib.stream_subscription import handle_stream_notifications_compatibility
from zerver.lib.streams import do_get_streams, get_web_public_streams
from zerver.lib.subscription_info import (
    build_unsubscribed_sub_from_stream_dict,
    gather_subscriptions_helper,
    get_web_public_subs,
)
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.timezone import canonicalize_timezone
from zerver.lib.topic import TOPIC_NAME
from zerver.lib.user_groups import (
    get_server_supported_permission_settings,
    user_groups_in_realm_serialized,
)
from zerver.lib.user_status import get_user_status_dict
from zerver.lib.user_topics import get_topic_mutes, get_user_topics
from zerver.lib.users import (
    get_cross_realm_dicts,
    get_data_for_inaccessible_user,
    get_users_for_api,
    is_administrator_role,
    max_message_id_for_user,
)
from zerver.lib.utils import optional_bytes_to_mib
from zerver.models import (
    Client,
    CustomProfileField,
    Draft,
    Realm,
    RealmUserDefault,
    Recipient,
    Stream,
    Subscription,
    UserProfile,
    UserStatus,
    UserTopic,
)
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.custom_profile_fields import custom_profile_fields_for_realm
from zerver.models.linkifiers import linkifiers_for_realm
from zerver.models.realm_emoji import get_all_custom_emoji_for_realm
from zerver.models.realm_playgrounds import get_realm_playgrounds
from zerver.models.realms import get_realm_domains
from zerver.models.streams import get_default_stream_groups
from zerver.tornado.django_api import get_user_events, request_event_queue
from zproject.backends import email_auth_enabled, password_auth_enabled


def add_realm_logo_fields(state: Dict[str, Any], realm: Realm) -> None:
    state["realm_logo_url"] = get_realm_logo_url(realm, night=False)
    state["realm_logo_source"] = get_realm_logo_source(realm, night=False)
    state["realm_night_logo_url"] = get_realm_logo_url(realm, night=True)
    state["realm_night_logo_source"] = get_realm_logo_source(realm, night=True)
    state["max_logo_file_size_mib"] = settings.MAX_LOGO_FILE_SIZE_MIB


def always_want(msg_type: str) -> bool:
    """
    This function is used as a helper in
    fetch_initial_state_data, when the user passes
    in None for event_types, and we want to fetch
    info for every event type.  Defining this at module
    level makes it easier to mock.
    """
    return True


def fetch_initial_state_data(
    user_profile: Optional[UserProfile],
    *,
    realm: Optional[Realm] = None,
    event_types: Optional[Iterable[str]] = None,
    queue_id: Optional[str] = "",
    client_gravatar: bool = False,
    user_avatar_url_field_optional: bool = False,
    user_settings_object: bool = False,
    slim_presence: bool = False,
    include_subscribers: bool = True,
    include_streams: bool = True,
    spectator_requested_language: Optional[str] = None,
    pronouns_field_type_supported: bool = True,
    linkifier_url_template: bool = False,
    user_list_incomplete: bool = False,
) -> Dict[str, Any]:
    """When `event_types` is None, fetches the core data powering the
    web app's `page_params` and `/api/v1/register` (for mobile/terminal
    apps).  Can also fetch a subset as determined by `event_types`.

    The user_profile=None code path is used for logged-out public
    access to streams with is_web_public=True.

    Whenever you add new code to this function, you should also add
    corresponding events for changes in the data structures and new
    code to apply_events (and add a test in test_events.py).
    """
    if realm is None:
        assert user_profile is not None
        realm = user_profile.realm

    state: Dict[str, Any] = {"queue_id": queue_id}

    if event_types is None:
        # return True always
        want: Callable[[str], bool] = always_want
    else:
        want = set(event_types).__contains__

    # Show the version info unconditionally.
    state["zulip_version"] = ZULIP_VERSION
    state["zulip_feature_level"] = API_FEATURE_LEVEL
    state["zulip_merge_base"] = ZULIP_MERGE_BASE

    if want("alert_words"):
        state["alert_words"] = [] if user_profile is None else user_alert_words(user_profile)

    if want("custom_profile_fields"):
        if user_profile is None:
            # Spectators can't access full user profiles or
            # personal settings, so we send an empty list.
            state["custom_profile_fields"] = []
        else:
            fields = custom_profile_fields_for_realm(realm.id)
            state["custom_profile_fields"] = [f.as_dict() for f in fields]
        state["custom_profile_field_types"] = {
            item[4]: {"id": item[0], "name": str(item[1])}
            for item in CustomProfileField.ALL_FIELD_TYPES
        }

        if not pronouns_field_type_supported:
            for field in state["custom_profile_fields"]:
                if field["type"] == CustomProfileField.PRONOUNS:
                    field["type"] = CustomProfileField.SHORT_TEXT

            del state["custom_profile_field_types"]["PRONOUNS"]

    if want("onboarding_steps"):
        # Even if we offered special onboarding steps for guests without an
        # account, we'd maybe need to store their state using cookies
        # or local storage, rather than in the database.
        state["onboarding_steps"] = (
            [] if user_profile is None else get_next_onboarding_steps(user_profile)
        )

    if want("message"):
        # Since the introduction of `anchor="latest"` in the API,
        # `max_message_id` is primarily used for generating `local_id`
        # values that are higher than this.  We likely can eventually
        # remove this parameter from the API.
        state["max_message_id"] = max_message_id_for_user(user_profile)

    if want("drafts"):
        if user_profile is None:
            state["drafts"] = []
        else:
            # Note: if a user ever disables syncing drafts then all of
            # their old drafts stored on the server will be deleted and
            # simply retained in local storage. In which case user_drafts
            # would just be an empty queryset.
            user_draft_objects = Draft.objects.filter(user_profile=user_profile).order_by(
                "-last_edit_time"
            )[: settings.MAX_DRAFTS_IN_REGISTER_RESPONSE]
            user_draft_dicts = [draft.to_dict() for draft in user_draft_objects]
            state["drafts"] = user_draft_dicts

    if want("scheduled_messages"):
        state["scheduled_messages"] = (
            [] if user_profile is None else get_undelivered_scheduled_messages(user_profile)
        )

    if want("muted_topics") and (
        # Suppress muted_topics data for clients that explicitly
        # support user_topic. This allows clients to request both the
        # user_topic and muted_topics, and receive the duplicate
        # muted_topics data only from older servers that don't yet
        # support user_topic.
        event_types is None or not want("user_topic")
    ):
        state["muted_topics"] = [] if user_profile is None else get_topic_mutes(user_profile)

    if want("muted_users"):
        state["muted_users"] = [] if user_profile is None else get_user_mutes(user_profile)

    if want("presence"):
        state["presences"] = (
            {}
            if user_profile is None
            else get_presences_for_realm(realm, slim_presence, user_profile)
        )
        # Send server_timestamp, to match the format of `GET /presence` requests.
        state["server_timestamp"] = time.time()

    if want("realm"):
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

        for (
            setting_name,
            permission_configuration,
        ) in Realm.REALM_PERMISSION_GROUP_SETTINGS.items():
            state["realm_" + setting_name] = getattr(realm, permission_configuration.id_field_name)

        # Most state is handled via the property_types framework;
        # these manual entries are for those realm settings that don't
        # fit into that framework.
        realm_authentication_methods_dict = realm.authentication_methods_dict()
        state["realm_authentication_methods"] = (
            get_realm_authentication_methods_for_page_params_api(
                realm, realm_authentication_methods_dict
            )
        )

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

        # Important: Encode units in the client-facing API name.
        state["max_avatar_file_size_mib"] = settings.MAX_AVATAR_FILE_SIZE_MIB
        state["max_file_upload_size_mib"] = settings.MAX_FILE_UPLOAD_SIZE
        state["max_icon_file_size_mib"] = settings.MAX_ICON_FILE_SIZE_MIB
        upload_quota_bytes = realm.upload_quota_bytes()
        state["realm_upload_quota_mib"] = optional_bytes_to_mib(upload_quota_bytes)

        state["realm_icon_url"] = realm_icon_url(realm)
        state["realm_icon_source"] = realm.icon_source
        add_realm_logo_fields(state, realm)

        state["realm_uri"] = realm.uri
        state["realm_bot_domain"] = realm.get_bot_domain()
        state["realm_available_video_chat_providers"] = realm.VIDEO_CHAT_PROVIDERS
        state["settings_send_digest_emails"] = settings.SEND_DIGEST_EMAILS

        state["realm_digest_emails_enabled"] = (
            realm.digest_emails_enabled and settings.SEND_DIGEST_EMAILS
        )
        state["realm_email_auth_enabled"] = email_auth_enabled(
            realm, realm_authentication_methods_dict
        )
        state["realm_password_auth_enabled"] = password_auth_enabled(
            realm, realm_authentication_methods_dict
        )

        state["server_generation"] = settings.SERVER_GENERATION
        state["realm_is_zephyr_mirror_realm"] = realm.is_zephyr_mirror_realm
        state["development_environment"] = settings.DEVELOPMENT
        state["realm_org_type"] = realm.org_type
        state["realm_plan_type"] = realm.plan_type
        state["zulip_plan_is_not_limited"] = realm.plan_type != Realm.PLAN_TYPE_LIMITED
        state["upgrade_text_for_wide_organization_logo"] = str(Realm.UPGRADE_TEXT_STANDARD)

        if realm.push_notifications_enabled_end_timestamp is not None:
            state["realm_push_notifications_enabled_end_timestamp"] = datetime_to_timestamp(
                realm.push_notifications_enabled_end_timestamp
            )
        else:
            state["realm_push_notifications_enabled_end_timestamp"] = None

        state["password_min_length"] = settings.PASSWORD_MIN_LENGTH
        state["password_min_guesses"] = settings.PASSWORD_MIN_GUESSES
        state["server_inline_image_preview"] = settings.INLINE_IMAGE_PREVIEW
        state["server_inline_url_embed_preview"] = settings.INLINE_URL_EMBED_PREVIEW
        state["server_avatar_changes_disabled"] = settings.AVATAR_CHANGES_DISABLED
        state["server_name_changes_disabled"] = settings.NAME_CHANGES_DISABLED
        state["server_web_public_streams_enabled"] = settings.WEB_PUBLIC_STREAMS_ENABLED
        state["giphy_rating_options"] = realm.get_giphy_rating_options()

        state["server_emoji_data_url"] = emoji.data_url()

        state["server_needs_upgrade"] = is_outdated_server(user_profile)
        state["event_queue_longpoll_timeout_seconds"] = (
            settings.EVENT_QUEUE_LONGPOLL_TIMEOUT_SECONDS
        )

        # TODO: This probably belongs on the server object.
        state["realm_default_external_accounts"] = get_default_external_accounts()

        server_default_jitsi_server_url = (
            settings.JITSI_SERVER_URL.rstrip("/") if settings.JITSI_SERVER_URL is not None else None
        )
        state["server_jitsi_server_url"] = server_default_jitsi_server_url
        state["jitsi_server_url"] = (
            realm.jitsi_server_url
            if realm.jitsi_server_url is not None
            else server_default_jitsi_server_url
        )

        new_stream_announcements_stream = realm.get_new_stream_announcements_stream()
        if new_stream_announcements_stream:
            state["realm_new_stream_announcements_stream_id"] = new_stream_announcements_stream.id
        else:
            state["realm_new_stream_announcements_stream_id"] = -1

        signup_announcements_stream = realm.get_signup_announcements_stream()
        if signup_announcements_stream:
            state["realm_signup_announcements_stream_id"] = signup_announcements_stream.id
        else:
            state["realm_signup_announcements_stream_id"] = -1

        zulip_update_announcements_stream = realm.get_zulip_update_announcements_stream()
        if zulip_update_announcements_stream:
            state["realm_zulip_update_announcements_stream_id"] = (
                zulip_update_announcements_stream.id
            )
        else:
            state["realm_zulip_update_announcements_stream_id"] = -1

        state["max_stream_name_length"] = Stream.MAX_NAME_LENGTH
        state["max_stream_description_length"] = Stream.MAX_DESCRIPTION_LENGTH
        state["max_topic_length"] = MAX_TOPIC_NAME_LENGTH
        state["max_message_length"] = settings.MAX_MESSAGE_LENGTH
        if realm.demo_organization_scheduled_deletion_date is not None:
            state["demo_organization_scheduled_deletion_date"] = datetime_to_timestamp(
                realm.demo_organization_scheduled_deletion_date
            )
        state["realm_date_created"] = datetime_to_timestamp(realm.date_created)

        # Presence system parameters for client behavior.
        state["server_presence_ping_interval_seconds"] = settings.PRESENCE_PING_INTERVAL_SECS
        state["server_presence_offline_threshold_seconds"] = settings.OFFLINE_THRESHOLD_SECS
        # Typing notifications protocol parameters for client behavior.
        state["server_typing_started_expiry_period_milliseconds"] = (
            settings.TYPING_STARTED_EXPIRY_PERIOD_MILLISECONDS
        )
        state["server_typing_stopped_wait_period_milliseconds"] = (
            settings.TYPING_STOPPED_WAIT_PERIOD_MILLISECONDS
        )
        state["server_typing_started_wait_period_milliseconds"] = (
            settings.TYPING_STARTED_WAIT_PERIOD_MILLISECONDS
        )

        state["server_supported_permission_settings"] = get_server_supported_permission_settings()
    if want("realm_user_settings_defaults"):
        realm_user_default = RealmUserDefault.objects.get(realm=realm)
        state["realm_user_settings_defaults"] = {}
        for property_name in RealmUserDefault.property_types:
            state["realm_user_settings_defaults"][property_name] = getattr(
                realm_user_default, property_name
            )

        state["realm_user_settings_defaults"]["emojiset_choices"] = (
            RealmUserDefault.emojiset_choices()
        )
        state["realm_user_settings_defaults"]["available_notification_sounds"] = (
            get_available_notification_sounds()
        )

    if want("realm_domains"):
        state["realm_domains"] = get_realm_domains(realm)

    if want("realm_emoji"):
        state["realm_emoji"] = get_all_custom_emoji_for_realm(realm.id)

    if want("realm_linkifiers"):
        if linkifier_url_template:
            state["realm_linkifiers"] = linkifiers_for_realm(realm.id)
        else:
            # When URL template is not supported by the client, return an empty list
            # because the new format is incompatible with the old URL format strings
            # and the client would not render it properly.
            state["realm_linkifiers"] = []

    # Backwards compatibility code.
    if want("realm_filters"):
        # Always return an empty list because the new URL template format is incompatible
        # with the old URL format string, because legacy clients that use the
        # backwards-compatible `realm_filters` event would not render the it properly.
        state["realm_filters"] = []

    if want("realm_playgrounds"):
        state["realm_playgrounds"] = get_realm_playgrounds(realm)

    if want("realm_user_groups"):
        state["realm_user_groups"] = user_groups_in_realm_serialized(realm)

    if user_profile is not None:
        settings_user = user_profile
    else:
        assert spectator_requested_language is not None
        # When UserProfile=None, we want to serve the values for various
        # settings as the defaults.  Instead of copying the default values
        # from models/users.py here, we access these default values from a
        # temporary UserProfile object that will not be saved to the database.
        #
        # We also can set various fields to avoid duplicating code
        # unnecessarily.
        settings_user = UserProfile(
            full_name="Anonymous User",
            email="username@example.com",
            delivery_email="username@example.com",
            realm=realm,
            # We tag logged-out users as guests because most guest
            # restrictions apply to these users as well, and it lets
            # us avoid unnecessary conditionals.
            role=UserProfile.ROLE_GUEST,
            is_billing_admin=False,
            avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
            # ID=0 is not used in real Zulip databases, ensuring this is unique.
            id=0,
            default_language=spectator_requested_language,
            # Set home view to recent conversations for spectators regardless of default.
            web_home_view="recent_topics",
        )
    if want("realm_user"):
        state["raw_users"] = get_users_for_api(
            realm,
            user_profile,
            client_gravatar=client_gravatar,
            user_avatar_url_field_optional=user_avatar_url_field_optional,
            # Don't send custom profile field values to spectators.
            include_custom_profile_fields=user_profile is not None,
            user_list_incomplete=user_list_incomplete,
        )
        state["cross_realm_bots"] = list(get_cross_realm_dicts())

        # For the user's own avatar URL, we force
        # client_gravatar=False, since that saves some unnecessary
        # client-side code for handing medium-size avatars.  See #8253
        # for details.
        state["avatar_source"] = settings_user.avatar_source
        state["avatar_url_medium"] = avatar_url(
            settings_user,
            medium=True,
            client_gravatar=False,
        )
        state["avatar_url"] = avatar_url(
            settings_user,
            medium=False,
            client_gravatar=False,
        )

        state["can_create_private_streams"] = settings_user.can_create_private_streams()
        state["can_create_public_streams"] = settings_user.can_create_public_streams()
        # TODO/compatibility: Deprecated in Zulip 5.0 (feature level
        # 102); we can remove this once we no longer need to support
        # legacy mobile app versions that read the old property.
        state["can_create_streams"] = (
            settings_user.can_create_private_streams()
            or settings_user.can_create_public_streams()
            or settings_user.can_create_web_public_streams()
        )
        state["can_create_web_public_streams"] = settings_user.can_create_web_public_streams()
        state["can_subscribe_other_users"] = settings_user.can_subscribe_other_users()
        state["can_invite_others_to_realm"] = settings_user.can_invite_users_by_email()
        state["is_admin"] = settings_user.is_realm_admin
        state["is_owner"] = settings_user.is_realm_owner
        state["is_moderator"] = settings_user.is_moderator
        state["is_guest"] = settings_user.is_guest
        state["is_billing_admin"] = settings_user.is_billing_admin
        state["user_id"] = settings_user.id
        state["email"] = settings_user.email
        state["delivery_email"] = settings_user.delivery_email
        state["full_name"] = settings_user.full_name

    if want("realm_bot"):
        state["realm_bots"] = [] if user_profile is None else get_owned_bot_dicts(user_profile)

    # This does not yet have an apply_event counterpart, since currently,
    # new entries for EMBEDDED_BOTS can only be added directly in the codebase.
    if want("realm_embedded_bots"):
        state["realm_embedded_bots"] = [
            {"name": bot.name, "config": load_bot_config_template(bot.name)}
            for bot in EMBEDDED_BOTS
        ]

    # This does not have an apply_events counterpart either since this
    # data is mostly static. This excludes the legacy webhook
    # integrations as those do not follow the same URL construction
    # patterns as other integrations.
    if want("realm_incoming_webhook_bots"):
        state["realm_incoming_webhook_bots"] = [
            {
                "name": integration.name,
                "display_name": integration.display_name,
                "all_event_types": get_all_event_types_for_integration(integration),
                "config": {c[1]: c[0] for c in integration.config_options},
            }
            for integration in WEBHOOK_INTEGRATIONS
            if integration.legacy is False
        ]

    if want("recent_private_conversations"):
        # A data structure containing records of this form:
        #
        #   [{'max_message_id': 700175, 'user_ids': [801]}]
        #
        # for all recent direct message conversations, ordered by the
        # highest message ID in the conversation. The user_ids list
        # is the list of users other than the current user in the
        # direct message conversation (so it is [] for direct messages
        # to self).
        #
        # Note that raw_recent_private_conversations is an
        # intermediate form as a dictionary keyed by recipient_id,
        # which is more efficient to update, and is rewritten to the
        # final format in post_process_state.
        state["raw_recent_private_conversations"] = (
            {} if user_profile is None else get_recent_private_conversations(user_profile)
        )

    if want("subscription"):
        if user_profile is not None:
            sub_info = gather_subscriptions_helper(
                user_profile,
                include_subscribers=include_subscribers,
            )
        else:
            sub_info = get_web_public_subs(realm)

        state["subscriptions"] = sub_info.subscriptions
        state["unsubscribed"] = sub_info.unsubscribed
        state["never_subscribed"] = sub_info.never_subscribed

    if want("update_message_flags") and want("message"):
        # Keeping unread_msgs updated requires both message flag updates and
        # message updates. This is due to the fact that new messages will not
        # generate a flag update so we need to use the flags field in the
        # message event.

        if user_profile is not None:
            state["raw_unread_msgs"] = get_raw_unread_data(user_profile)
        else:
            # For logged-out visitors, we treat all messages as read;
            # calling this helper lets us return empty objects in the
            # appropriate format.
            state["raw_unread_msgs"] = extract_unread_data_from_um_rows([], user_profile)

    if want("starred_messages"):
        state["starred_messages"] = (
            [] if user_profile is None else get_starred_message_ids(user_profile)
        )

    if want("stream") and include_streams:
        # The web app doesn't use the data from here; instead,
        # it uses data from state["subscriptions"] and other
        # places.
        if user_profile is not None:
            state["streams"] = do_get_streams(
                user_profile,
                include_web_public=True,
                include_all_active=user_profile.is_realm_admin,
            )
        else:
            # TODO: This line isn't used by the web app because it
            # gets these data via the `subscriptions` key; it will
            # be used when the mobile apps support logged-out
            # access.
            state["streams"] = get_web_public_streams(realm)  # nocoverage
    if want("default_streams"):
        if settings_user.is_guest:
            # Guest users and logged-out users don't have access to
            # all default streams, so we pretend the organization
            # doesn't have any.
            state["realm_default_streams"] = []
        else:
            state["realm_default_streams"] = get_default_streams_for_realm_as_dicts(realm.id)

    if want("default_stream_groups"):
        if settings_user.is_guest:
            state["realm_default_stream_groups"] = []
        else:
            state["realm_default_stream_groups"] = default_stream_groups_to_dicts_sorted(
                get_default_stream_groups(realm)
            )

    if want("stop_words"):
        state["stop_words"] = read_stop_words()

    if want("update_display_settings") and not user_settings_object:
        for prop in UserProfile.display_settings_legacy:
            state[prop] = getattr(settings_user, prop)
        state["emojiset_choices"] = UserProfile.emojiset_choices()
        state["timezone"] = canonicalize_timezone(settings_user.timezone)

    if want("update_global_notifications") and not user_settings_object:
        for notification in UserProfile.notification_settings_legacy:
            state[notification] = getattr(settings_user, notification)
        state["available_notification_sounds"] = get_available_notification_sounds()

    if want("user_settings"):
        state["user_settings"] = {}

        for prop in UserProfile.property_types:
            state["user_settings"][prop] = getattr(settings_user, prop)

        state["user_settings"]["emojiset_choices"] = UserProfile.emojiset_choices()
        state["user_settings"]["timezone"] = canonicalize_timezone(settings_user.timezone)
        state["user_settings"]["available_notification_sounds"] = (
            get_available_notification_sounds()
        )

    if want("user_status"):
        # We require creating an account to access statuses.
        state["user_status"] = (
            {}
            if user_profile is None
            else get_user_status_dict(realm=realm, user_profile=user_profile)
        )

    if want("user_topic"):
        state["user_topics"] = [] if user_profile is None else get_user_topics(user_profile)

    if want("video_calls"):
        state["has_zoom_token"] = settings_user.zoom_token is not None

    if want("giphy"):
        # Normally, it would be a nasty security bug to send a
        # server's API key to end users. However, GIPHY's API key
        # security model is precisely to do that; every service
        # publishes its API key (and GIPHY's client-side JS libraries
        # require the API key to work).  This security model makes
        # sense because GIPHY API keys are all essentially equivalent
        # in letting one search for GIFs; GIPHY only requires API keys
        # to exist at all so that they can deactivate them in cases of
        # abuse.
        state["giphy_api_key"] = settings.GIPHY_API_KEY if settings.GIPHY_API_KEY else ""

    if user_profile is None:
        # To ensure we have the correct user state set.
        assert state["is_admin"] is False
        assert state["is_owner"] is False
        assert state["is_guest"] is True

    return state


def apply_events(
    user_profile: UserProfile,
    *,
    state: Dict[str, Any],
    events: Iterable[Dict[str, Any]],
    fetch_event_types: Optional[Collection[str]],
    client_gravatar: bool,
    slim_presence: bool,
    include_subscribers: bool,
    linkifier_url_template: bool,
    user_list_incomplete: bool,
) -> None:
    for event in events:
        if fetch_event_types is not None and event["type"] not in fetch_event_types:
            # TODO: continuing here is not, most precisely, correct.
            # In theory, an event of one type, e.g. `realm_user`,
            # could modify state that doesn't come from that
            # `fetch_event_types` value, e.g. the `our_person` part of
            # that code path.  But it should be extremely rare, and
            # fixing that will require a nontrivial refactor of
            # `apply_event`.  For now, be careful in your choice of
            # `fetch_event_types`.
            continue
        apply_event(
            user_profile,
            state=state,
            event=event,
            client_gravatar=client_gravatar,
            slim_presence=slim_presence,
            include_subscribers=include_subscribers,
            linkifier_url_template=linkifier_url_template,
            user_list_incomplete=user_list_incomplete,
        )


def apply_event(
    user_profile: UserProfile,
    *,
    state: Dict[str, Any],
    event: Dict[str, Any],
    client_gravatar: bool,
    slim_presence: bool,
    include_subscribers: bool,
    linkifier_url_template: bool,
    user_list_incomplete: bool,
) -> None:
    if event["type"] == "message":
        state["max_message_id"] = max(state["max_message_id"], event["message"]["id"])
        if "raw_unread_msgs" in state and "read" not in event["flags"]:
            apply_unread_message_event(
                user_profile,
                state["raw_unread_msgs"],
                event["message"],
                event["flags"],
            )

        if event["message"]["type"] != "stream":
            if "raw_recent_private_conversations" in state:
                # Handle maintaining the recent_private_conversations data structure.
                conversations = state["raw_recent_private_conversations"]
                recipient_id = get_recent_conversations_recipient_id(
                    user_profile, event["message"]["recipient_id"], event["message"]["sender_id"]
                )

                if recipient_id not in conversations:
                    conversations[recipient_id] = dict(
                        user_ids=sorted(
                            user_dict["id"]
                            for user_dict in event["message"]["display_recipient"]
                            if user_dict["id"] != user_profile.id
                        ),
                    )
                conversations[recipient_id]["max_message_id"] = event["message"]["id"]
            return

        # Below, we handle maintaining first_message_id.
        for sub_dict in state.get("subscriptions", []):
            if (
                event["message"]["stream_id"] == sub_dict["stream_id"]
                and sub_dict["first_message_id"] is None
            ):
                sub_dict["first_message_id"] = event["message"]["id"]
        for stream_dict in state.get("streams", []):
            if (
                event["message"]["stream_id"] == stream_dict["stream_id"]
                and stream_dict["first_message_id"] is None
            ):
                stream_dict["first_message_id"] = event["message"]["id"]

    elif event["type"] == "heartbeat":
        # It may be impossible for a heartbeat event to actually reach
        # this code path. But in any case, they're noops.
        pass

    elif event["type"] == "drafts":
        if event["op"] == "add":
            state["drafts"].extend(event["drafts"])
        else:
            if event["op"] == "update":
                event_draft_idx = event["draft"]["id"]

                def _draft_update_action(i: int) -> None:
                    state["drafts"][i] = event["draft"]

            elif event["op"] == "remove":
                event_draft_idx = event["draft_id"]

                def _draft_update_action(i: int) -> None:
                    del state["drafts"][i]

            # We have to perform a linear search for the draft that
            # was either edited or removed since we have a list
            # ordered by the last edited timestamp and not id.
            state_draft_idx = None
            for idx, draft in enumerate(state["drafts"]):
                if draft["id"] == event_draft_idx:
                    state_draft_idx = idx
                    break
            assert state_draft_idx is not None
            _draft_update_action(state_draft_idx)

    elif event["type"] == "scheduled_messages":
        if event["op"] == "add":
            # Since bulk addition of scheduled messages will not be used by a normal user.
            assert len(event["scheduled_messages"]) == 1

            state["scheduled_messages"].append(event["scheduled_messages"][0])
            # Sort in ascending order of scheduled_delivery_timestamp.
            state["scheduled_messages"].sort(
                key=lambda scheduled_message: scheduled_message["scheduled_delivery_timestamp"]
            )

        if event["op"] == "update":
            for idx, scheduled_message in enumerate(state["scheduled_messages"]):
                if (
                    scheduled_message["scheduled_message_id"]
                    == event["scheduled_message"]["scheduled_message_id"]
                ):
                    state["scheduled_messages"][idx] = event["scheduled_message"]
                    # If scheduled_delivery_timestamp was changed, we need to sort it again.
                    if (
                        scheduled_message["scheduled_delivery_timestamp"]
                        != event["scheduled_message"]["scheduled_delivery_timestamp"]
                    ):
                        state["scheduled_messages"].sort(
                            key=lambda scheduled_message: scheduled_message[
                                "scheduled_delivery_timestamp"
                            ]
                        )
                    break

        if event["op"] == "remove":
            for idx, scheduled_message in enumerate(state["scheduled_messages"]):
                if scheduled_message["scheduled_message_id"] == event["scheduled_message_id"]:
                    del state["scheduled_messages"][idx]

    elif event["type"] == "onboarding_steps":
        state["onboarding_steps"] = event["onboarding_steps"]
    elif event["type"] == "custom_profile_fields":
        state["custom_profile_fields"] = event["fields"]
        custom_profile_field_ids = {field["id"] for field in state["custom_profile_fields"]}

        if "raw_users" in state:
            for user_dict in state["raw_users"].values():
                if "profile_data" not in user_dict:
                    continue
                profile_data = user_dict["profile_data"]
                for field_id, field_data in list(profile_data.items()):
                    if int(field_id) not in custom_profile_field_ids:
                        del profile_data[field_id]
    elif event["type"] == "realm_user":
        person = event["person"]
        person_user_id = person["user_id"]

        if event["op"] == "add":
            person = copy.deepcopy(person)

            if client_gravatar:
                email_address_visibility = UserProfile.objects.get(
                    id=person_user_id
                ).email_address_visibility
                if email_address_visibility != UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE:
                    client_gravatar = False

            if client_gravatar and person["avatar_url"].startswith("https://secure.gravatar.com/"):
                person["avatar_url"] = None
            person["is_active"] = True
            if not person["is_bot"]:
                person["profile_data"] = {}
            state["raw_users"][person_user_id] = person
        elif event["op"] == "update":
            is_me = person_user_id == user_profile.id

            if is_me:
                if "avatar_url" in person and "avatar_url" in state:
                    state["avatar_source"] = person["avatar_source"]
                    state["avatar_url"] = person["avatar_url"]
                    state["avatar_url_medium"] = person["avatar_url_medium"]

                if "role" in person:
                    state["is_admin"] = is_administrator_role(person["role"])
                    state["is_owner"] = person["role"] == UserProfile.ROLE_REALM_OWNER
                    state["is_moderator"] = person["role"] == UserProfile.ROLE_MODERATOR
                    state["is_guest"] = person["role"] == UserProfile.ROLE_GUEST
                    # Recompute properties based on is_admin/is_guest
                    state["can_create_private_streams"] = user_profile.can_create_private_streams()
                    state["can_create_public_streams"] = user_profile.can_create_public_streams()
                    state["can_create_web_public_streams"] = (
                        user_profile.can_create_web_public_streams()
                    )
                    state["can_create_streams"] = (
                        state["can_create_private_streams"]
                        or state["can_create_public_streams"]
                        or state["can_create_web_public_streams"]
                    )
                    state["can_subscribe_other_users"] = user_profile.can_subscribe_other_users()
                    state["can_invite_others_to_realm"] = user_profile.can_invite_users_by_email()

                    if state["is_guest"]:
                        state["realm_default_streams"] = []
                    else:
                        state["realm_default_streams"] = get_default_streams_for_realm_as_dicts(
                            user_profile.realm_id
                        )

                for field in ["delivery_email", "email", "full_name", "is_billing_admin"]:
                    if field in person and field in state:
                        state[field] = person[field]

                if "new_email" in person:
                    state["email"] = person["new_email"]

                # In the unlikely event that the current user
                # just changed to/from being an admin, we need
                # to add/remove the data on all bots in the
                # realm.  This is ugly and probably better
                # solved by removing the all-realm-bots data
                # given to admin users from this flow.
                if "role" in person and "realm_bots" in state:
                    prev_state = state["raw_users"][user_profile.id]
                    was_admin = prev_state["is_admin"]
                    now_admin = is_administrator_role(person["role"])

                    if was_admin and not now_admin:
                        state["realm_bots"] = []
                    if not was_admin and now_admin:
                        state["realm_bots"] = get_owned_bot_dicts(user_profile)

            if person_user_id in state["raw_users"]:
                p = state["raw_users"][person_user_id]

                if "avatar_url" in person:
                    # Respect the client_gravatar setting in the `users` data.
                    if client_gravatar:
                        email_address_visibility = UserProfile.objects.get(
                            id=person_user_id
                        ).email_address_visibility
                        if (
                            email_address_visibility
                            != UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE
                        ):
                            client_gravatar = False

                    if client_gravatar and person["avatar_url"].startswith(
                        "https://secure.gravatar.com/"
                    ):
                        person["avatar_url"] = None
                        person["avatar_url_medium"] = None

                for field in p:
                    if field in person:
                        p[field] = person[field]

                if "role" in person:
                    p["is_admin"] = is_administrator_role(person["role"])
                    p["is_owner"] = person["role"] == UserProfile.ROLE_REALM_OWNER
                    p["is_guest"] = person["role"] == UserProfile.ROLE_GUEST

                if "is_billing_admin" in person:
                    p["is_billing_admin"] = person["is_billing_admin"]

                if "custom_profile_field" in person:
                    custom_field_id = str(person["custom_profile_field"]["id"])
                    custom_field_new_value = person["custom_profile_field"]["value"]
                    if custom_field_new_value is None and "profile_data" in p:
                        p["profile_data"].pop(custom_field_id, None)
                    elif "rendered_value" in person["custom_profile_field"]:
                        p["profile_data"][custom_field_id] = {
                            "value": custom_field_new_value,
                            "rendered_value": person["custom_profile_field"]["rendered_value"],
                        }
                    else:
                        p["profile_data"][custom_field_id] = {
                            "value": custom_field_new_value,
                        }

                if "new_email" in person:
                    p["email"] = person["new_email"]

                if "is_active" in person and not person["is_active"] and include_subscribers:
                    for sub in state["subscriptions"]:
                        sub["subscribers"] = [
                            user_id for user_id in sub["subscribers"] if user_id != person_user_id
                        ]
        elif event["op"] == "remove":
            if person_user_id in state["raw_users"]:
                if user_list_incomplete:
                    del state["raw_users"][person_user_id]
                else:
                    inaccessible_user_dict = get_data_for_inaccessible_user(
                        user_profile.realm, person_user_id
                    )
                    state["raw_users"][person_user_id] = inaccessible_user_dict

            if include_subscribers:
                for sub in state["subscriptions"]:
                    sub["subscribers"] = [
                        user_id for user_id in sub["subscribers"] if user_id != person_user_id
                    ]
        else:
            raise AssertionError("Unexpected event type {type}/{op}".format(**event))
    elif event["type"] == "realm_bot":
        if event["op"] == "add":
            state["realm_bots"].append(event["bot"])
        elif event["op"] == "delete":
            state["realm_bots"] = [
                item for item in state["realm_bots"] if item["user_id"] != event["bot"]["user_id"]
            ]
        elif event["op"] == "update":
            for bot in state["realm_bots"]:
                if bot["user_id"] == event["bot"]["user_id"]:
                    if "owner_id" in event["bot"]:
                        bot_owner_id = event["bot"]["owner_id"]
                        bot["owner_id"] = bot_owner_id
                    else:
                        bot.update(event["bot"])
        else:
            raise AssertionError("Unexpected event type {type}/{op}".format(**event))
    elif event["type"] == "stream":
        if event["op"] == "create":
            for stream in event["streams"]:
                stream_data = copy.deepcopy(stream)
                if include_subscribers:
                    stream_data["subscribers"] = []

                # Here we need to query the database to check whether the
                # user was previously subscribed. If they were, we need to
                # include the stream in the unsubscribed list after adding
                # personal subscription metadata (such as configured stream
                # color; most of the other personal setting have no effect
                # when not subscribed).
                unsubscribed_stream_sub = Subscription.objects.filter(
                    user_profile=user_profile,
                    recipient__type_id=stream["stream_id"],
                    recipient__type=Recipient.STREAM,
                ).values(
                    *Subscription.API_FIELDS,
                    "recipient_id",
                    "active",
                )

                if len(unsubscribed_stream_sub) == 1:
                    unsubscribed_stream_dict = build_unsubscribed_sub_from_stream_dict(
                        user_profile, unsubscribed_stream_sub[0], stream_data
                    )
                    if include_subscribers:
                        unsubscribed_stream_dict["subscribers"] = []
                    state["unsubscribed"].append(unsubscribed_stream_dict)
                else:
                    assert len(unsubscribed_stream_sub) == 0
                    state["never_subscribed"].append(stream_data)

                if "streams" in state:
                    state["streams"].append(stream)

            state["unsubscribed"].sort(key=lambda elt: elt["name"])
            state["never_subscribed"].sort(key=lambda elt: elt["name"])
            if "streams" in state:
                state["streams"].sort(key=lambda elt: elt["name"])

        if event["op"] == "delete":
            deleted_stream_ids = {stream["stream_id"] for stream in event["streams"]}
            if "streams" in state:
                state["streams"] = [
                    s for s in state["streams"] if s["stream_id"] not in deleted_stream_ids
                ]

            state["subscriptions"] = [
                stream
                for stream in state["subscriptions"]
                if stream["stream_id"] not in deleted_stream_ids
            ]

            state["unsubscribed"] = [
                stream
                for stream in state["unsubscribed"]
                if stream["stream_id"] not in deleted_stream_ids
            ]

            state["never_subscribed"] = [
                stream
                for stream in state["never_subscribed"]
                if stream["stream_id"] not in deleted_stream_ids
            ]

        if event["op"] == "update":
            # For legacy reasons, we call stream data 'subscriptions' in
            # the state var here, for the benefit of the JS code.
            for sub_list in [
                state["subscriptions"],
                state["unsubscribed"],
                state["never_subscribed"],
            ]:
                for obj in sub_list:
                    if obj["name"].lower() == event["name"].lower():
                        obj[event["property"]] = event["value"]
                        if event["property"] == "description":
                            obj["rendered_description"] = event["rendered_description"]
                        if event.get("history_public_to_subscribers") is not None:
                            obj["history_public_to_subscribers"] = event[
                                "history_public_to_subscribers"
                            ]
                        if event.get("is_web_public") is not None:
                            obj["is_web_public"] = event["is_web_public"]
            # Also update the pure streams data
            if "streams" in state:
                for stream in state["streams"]:
                    if stream["name"].lower() == event["name"].lower():
                        prop = event["property"]
                        if prop in stream:
                            stream[prop] = event["value"]
                            if prop == "description":
                                stream["rendered_description"] = event["rendered_description"]
                            if event.get("history_public_to_subscribers") is not None:
                                stream["history_public_to_subscribers"] = event[
                                    "history_public_to_subscribers"
                                ]
                            if event.get("is_web_public") is not None:
                                stream["is_web_public"] = event["is_web_public"]

    elif event["type"] == "default_streams":
        state["realm_default_streams"] = event["default_streams"]
    elif event["type"] == "default_stream_groups":
        state["realm_default_stream_groups"] = event["default_stream_groups"]
    elif event["type"] == "realm":
        if event["op"] == "update":
            field = "realm_" + event["property"]
            state[field] = event["value"]

            if event["property"] == "plan_type":
                # Then there are some extra fields that also need to be set.
                state["zulip_plan_is_not_limited"] = event["value"] != Realm.PLAN_TYPE_LIMITED
                # upload_quota is in bytes, so we need to convert it to MiB.
                upload_quota_bytes = event["extra_data"]["upload_quota"]
                state["realm_upload_quota_mib"] = optional_bytes_to_mib(upload_quota_bytes)

            if field == "realm_jitsi_server_url":
                state["jitsi_server_url"] = (
                    state["realm_jitsi_server_url"]
                    if state["realm_jitsi_server_url"] is not None
                    else state["server_jitsi_server_url"]
                )

            policy_permission_dict = {
                "create_public_stream_policy": "can_create_public_streams",
                "create_private_stream_policy": "can_create_private_streams",
                "create_web_public_stream_policy": "can_create_web_public_streams",
                "invite_to_stream_policy": "can_subscribe_other_users",
                "invite_to_realm_policy": "can_invite_others_to_realm",
            }

            # Tricky interaction: Whether we can create streams and can subscribe other users
            # can get changed here.

            if field == "realm_waiting_period_threshold":
                for policy, permission in policy_permission_dict.items():
                    if permission in state:
                        state[permission] = user_profile.has_permission(policy)

            if (
                event["property"] in policy_permission_dict
                and policy_permission_dict[event["property"]] in state
            ):
                state[policy_permission_dict[event["property"]]] = user_profile.has_permission(
                    event["property"]
                )

            # Finally, we need to recompute this value from its inputs.
            state["can_create_streams"] = (
                state["can_create_private_streams"]
                or state["can_create_public_streams"]
                or state["can_create_web_public_streams"]
            )
        elif event["op"] == "update_dict":
            for key, value in event["data"].items():
                state["realm_" + key] = value
                # It's a bit messy, but this is where we need to
                # update the state for whether password authentication
                # is enabled on this server.
                if key == "authentication_methods":
                    state["realm_password_auth_enabled"] = (
                        value["Email"]["enabled"] or value["LDAP"]["enabled"]
                    )
                    state["realm_email_auth_enabled"] = value["Email"]["enabled"]
        elif event["op"] == "deactivated":
            # The realm has just been deactivated.  If our request had
            # arrived a moment later, we'd have rendered the
            # deactivation UI; if it'd been a moment sooner, we've
            # have rendered the app and then immediately got this
            # event (or actually, more likely, an auth error on GET
            # /events) and immediately reloaded into the same
            # deactivation UI. Passing achieves the same result.
            pass
        else:
            raise AssertionError("Unexpected event type {type}/{op}".format(**event))
    elif event["type"] == "realm_user_settings_defaults":
        if event["op"] == "update":
            state["realm_user_settings_defaults"][event["property"]] = event["value"]
        else:
            raise AssertionError("Unexpected event type {type}/{op}".format(**event))
    elif event["type"] == "subscription":
        if event["op"] == "add":
            added_stream_ids = {sub["stream_id"] for sub in event["subscriptions"]}
            was_added = lambda s: s["stream_id"] in added_stream_ids

            existing_stream_ids = {sub["stream_id"] for sub in state["subscriptions"]}

            # add the new subscriptions
            for sub in event["subscriptions"]:
                if sub["stream_id"] not in existing_stream_ids:
                    if "subscribers" in sub and not include_subscribers:
                        sub = copy.deepcopy(sub)
                        del sub["subscribers"]
                    state["subscriptions"].append(sub)

            # remove them from unsubscribed if they had been there
            state["unsubscribed"] = [s for s in state["unsubscribed"] if not was_added(s)]

            # remove them from never_subscribed if they had been there
            state["never_subscribed"] = [s for s in state["never_subscribed"] if not was_added(s)]

        elif event["op"] == "remove":
            removed_stream_ids = {sub["stream_id"] for sub in event["subscriptions"]}
            was_removed = lambda s: s["stream_id"] in removed_stream_ids

            # Find the subs we are affecting.
            removed_subs = list(filter(was_removed, state["subscriptions"]))

            # Remove our user from the subscribers of the removed subscriptions.
            if include_subscribers:
                for sub in removed_subs:
                    sub["subscribers"].remove(user_profile.id)

            state["unsubscribed"] += removed_subs

            # Now filter out the removed subscriptions from subscriptions.
            state["subscriptions"] = [s for s in state["subscriptions"] if not was_removed(s)]

        elif event["op"] == "update":
            for sub in state["subscriptions"]:
                if sub["stream_id"] == event["stream_id"]:
                    sub[event["property"]] = event["value"]
        elif event["op"] == "peer_add":
            if include_subscribers:
                stream_ids = set(event["stream_ids"])
                user_ids = set(event["user_ids"])

                for sub_dict in [
                    state["subscriptions"],
                    state["unsubscribed"],
                    state["never_subscribed"],
                ]:
                    for sub in sub_dict:
                        if sub["stream_id"] in stream_ids:
                            subscribers = set(sub["subscribers"]) | user_ids
                            sub["subscribers"] = sorted(subscribers)
        elif event["op"] == "peer_remove":
            if include_subscribers:
                stream_ids = set(event["stream_ids"])
                user_ids = set(event["user_ids"])

                for sub_dict in [
                    state["subscriptions"],
                    state["unsubscribed"],
                    state["never_subscribed"],
                ]:
                    for sub in sub_dict:
                        if sub["stream_id"] in stream_ids:
                            subscribers = set(sub["subscribers"]) - user_ids
                            sub["subscribers"] = sorted(subscribers)
        else:
            raise AssertionError("Unexpected event type {type}/{op}".format(**event))
    elif event["type"] == "presence":
        if slim_presence:
            user_key = str(event["user_id"])
        else:
            user_key = event["email"]
        state["presences"][user_key] = get_presence_for_user(event["user_id"], slim_presence)[
            user_key
        ]
    elif event["type"] == "update_message":
        # We don't return messages in /register, so we don't need to
        # do anything for content updates, but we may need to update
        # the unread_msgs data if the topic of an unread message changed.
        if "raw_unread_msgs" in state and "new_stream_id" in event:
            stream_dict = state["raw_unread_msgs"]["stream_dict"]
            stream_id = event["new_stream_id"]
            for message_id in event["message_ids"]:
                if message_id in stream_dict:
                    stream_dict[message_id]["stream_id"] = stream_id

        if "raw_unread_msgs" in state and TOPIC_NAME in event:
            stream_dict = state["raw_unread_msgs"]["stream_dict"]
            topic_name = event[TOPIC_NAME]
            for message_id in event["message_ids"]:
                if message_id in stream_dict:
                    stream_dict[message_id]["topic"] = topic_name
    elif event["type"] == "delete_message":
        if "message_id" in event:
            message_ids = [event["message_id"]]
        else:
            message_ids = event["message_ids"]  # nocoverage
        state["max_message_id"] = max_message_id_for_user(user_profile)

        if "raw_unread_msgs" in state:
            for remove_id in message_ids:
                remove_message_id_from_unread_mgs(state["raw_unread_msgs"], remove_id)

        # The remainder of this block is about maintaining recent_private_conversations
        if "raw_recent_private_conversations" not in state or event["message_type"] != "private":
            return

        # OK, we just deleted what had been the max_message_id for
        # this recent conversation; we need to recompute that value
        # from scratch.  Definitely don't need to re-query everything,
        # but this case is likely rare enough that it's reasonable to do so.
        state["raw_recent_private_conversations"] = get_recent_private_conversations(user_profile)
    elif event["type"] == "reaction":
        # The client will get the message with the reactions directly
        pass
    elif event["type"] == "submessage":
        # The client will get submessages with their messages
        pass
    elif event["type"] == "typing":
        # Typing notification events are transient and thus ignored
        pass
    elif event["type"] == "attachment":
        # Attachment events are just for updating the "uploads" UI;
        # they are not sent directly.
        pass
    elif event["type"] == "update_message_flags":
        # We don't return messages in `/register`, so most flags we
        # can ignore, but we do need to update the unread_msgs data if
        # unread state is changed.
        if "raw_unread_msgs" in state and event["flag"] == "read" and event["op"] == "add":
            for remove_id in event["messages"]:
                remove_message_id_from_unread_mgs(state["raw_unread_msgs"], remove_id)
        if "raw_unread_msgs" in state and event["flag"] == "read" and event["op"] == "remove":
            for message_id_str, message_details in event["message_details"].items():
                add_message_to_unread_msgs(
                    user_profile.id,
                    state["raw_unread_msgs"],
                    int(message_id_str),
                    message_details,
                )
        if event["flag"] == "starred" and "starred_messages" in state:
            if event["op"] == "add":
                state["starred_messages"] += event["messages"]
            if event["op"] == "remove":
                state["starred_messages"] = [
                    message
                    for message in state["starred_messages"]
                    if message not in event["messages"]
                ]
    elif event["type"] == "realm_domains":
        if event["op"] == "add":
            state["realm_domains"].append(event["realm_domain"])
        elif event["op"] == "change":
            for realm_domain in state["realm_domains"]:
                if realm_domain["domain"] == event["realm_domain"]["domain"]:
                    realm_domain["allow_subdomains"] = event["realm_domain"]["allow_subdomains"]
        elif event["op"] == "remove":
            state["realm_domains"] = [
                realm_domain
                for realm_domain in state["realm_domains"]
                if realm_domain["domain"] != event["domain"]
            ]
        else:
            raise AssertionError("Unexpected event type {type}/{op}".format(**event))
    elif event["type"] == "realm_emoji":
        state["realm_emoji"] = event["realm_emoji"]
    elif event["type"] == "realm_export":
        # These realm export events are only available to
        # administrators, and aren't included in page_params.
        pass
    elif event["type"] == "alert_words":
        state["alert_words"] = event["alert_words"]
    elif event["type"] == "muted_topics":
        state["muted_topics"] = event["muted_topics"]
    elif event["type"] == "muted_users":
        state["muted_users"] = event["muted_users"]
    elif event["type"] == "realm_linkifiers":
        # We only send realm_linkifiers event to clients that indicate
        # support for linkifiers with URL templates. Otherwise, silently
        # ignore the event.
        if linkifier_url_template:
            state["realm_linkifiers"] = event["realm_linkifiers"]
    elif event["type"] == "realm_playgrounds":
        state["realm_playgrounds"] = event["realm_playgrounds"]
    elif event["type"] == "update_display_settings":
        if event["setting_name"] != "timezone":
            assert event["setting_name"] in UserProfile.display_settings_legacy
        state[event["setting_name"]] = event["setting"]
    elif event["type"] == "update_global_notifications":
        assert event["notification_name"] in UserProfile.notification_settings_legacy
        state[event["notification_name"]] = event["setting"]
    elif event["type"] == "user_settings":
        # time zone setting is not included in property_types dict because
        # this setting is not a part of UserBaseSettings class.
        if event["property"] != "timezone":
            assert event["property"] in UserProfile.property_types
        if event["property"] in {
            **UserProfile.display_settings_legacy,
            **UserProfile.notification_settings_legacy,
        }:
            state[event["property"]] = event["value"]
        state["user_settings"][event["property"]] = event["value"]
    elif event["type"] == "invites_changed":
        pass
    elif event["type"] == "user_group":
        if event["op"] == "add":
            state["realm_user_groups"].append(event["group"])
            state["realm_user_groups"].sort(key=lambda group: group["id"])
        elif event["op"] == "update":
            for user_group in state["realm_user_groups"]:
                if user_group["id"] == event["group_id"]:
                    user_group.update(event["data"])
        elif event["op"] == "add_members":
            for user_group in state["realm_user_groups"]:
                if user_group["id"] == event["group_id"]:
                    user_group["members"].extend(event["user_ids"])
                    user_group["members"].sort()
        elif event["op"] == "remove_members":
            for user_group in state["realm_user_groups"]:
                if user_group["id"] == event["group_id"]:
                    members = set(user_group["members"])
                    user_group["members"] = sorted(members - set(event["user_ids"]))
        elif event["op"] == "add_subgroups":
            for user_group in state["realm_user_groups"]:
                if user_group["id"] == event["group_id"]:
                    user_group["direct_subgroup_ids"].extend(event["direct_subgroup_ids"])
                    user_group["direct_subgroup_ids"].sort()
        elif event["op"] == "remove_subgroups":
            for user_group in state["realm_user_groups"]:
                if user_group["id"] == event["group_id"]:
                    subgroups = set(user_group["direct_subgroup_ids"])
                    user_group["direct_subgroup_ids"] = sorted(
                        subgroups - set(event["direct_subgroup_ids"])
                    )
        elif event["op"] == "remove":
            state["realm_user_groups"] = [
                ug for ug in state["realm_user_groups"] if ug["id"] != event["group_id"]
            ]
        else:
            raise AssertionError("Unexpected event type {type}/{op}".format(**event))
    elif event["type"] == "user_status":
        user_id_str = str(event["user_id"])
        user_status = state["user_status"]
        away = event.get("away")
        status_text = event.get("status_text")
        emoji_name = event.get("emoji_name")
        emoji_code = event.get("emoji_code")
        reaction_type = event.get("reaction_type")

        if user_id_str not in user_status:
            user_status[user_id_str] = {}

        if away is not None:
            if away:
                user_status[user_id_str]["away"] = True
            else:
                user_status[user_id_str].pop("away", None)

        if status_text is not None:
            if status_text == "":
                user_status[user_id_str].pop("status_text", None)
            else:
                user_status[user_id_str]["status_text"] = status_text

            if emoji_name is not None:
                if emoji_name == "":
                    user_status[user_id_str].pop("emoji_name", None)
                else:
                    user_status[user_id_str]["emoji_name"] = emoji_name

                if emoji_code is not None:
                    if emoji_code == "":
                        user_status[user_id_str].pop("emoji_code", None)
                    else:
                        user_status[user_id_str]["emoji_code"] = emoji_code

                if reaction_type is not None:
                    if reaction_type == UserStatus.UNICODE_EMOJI and emoji_name == "":
                        user_status[user_id_str].pop("reaction_type", None)
                    else:
                        user_status[user_id_str]["reaction_type"] = reaction_type

        if not user_status[user_id_str]:
            user_status.pop(user_id_str, None)

        state["user_status"] = user_status
    elif event["type"] == "user_topic":
        if event["visibility_policy"] == UserTopic.VisibilityPolicy.INHERIT:
            user_topics_state = state["user_topics"]
            for i in range(len(user_topics_state)):
                if (
                    user_topics_state[i]["stream_id"] == event["stream_id"]
                    and user_topics_state[i]["topic_name"] == event["topic_name"]
                ):
                    del user_topics_state[i]
                    break
        else:
            fields = ["stream_id", "topic_name", "visibility_policy", "last_updated"]
            state["user_topics"].append({x: event[x] for x in fields})
    elif event["type"] == "has_zoom_token":
        state["has_zoom_token"] = event["value"]
    elif event["type"] == "web_reload_client":
        # This is an unlikely race, where the queue was created with a
        # previous Tornado process, which restarted, and subsequently
        # was told by restart-server to tell its old clients to
        # reload.  We warn, since we do not expect this race to be
        # possible, but the worst expected outcome is that the client
        # retains the old JS instead of reloading.
        logging.warning("Got a web_reload_client event during apply_events")
    elif event["type"] == "restart":
        # The Tornado process restarted.  This has no effect; we ignore it.
        pass
    else:
        raise AssertionError("Unexpected event type {}".format(event["type"]))


def do_events_register(
    user_profile: Optional[UserProfile],
    realm: Realm,
    user_client: Client,
    apply_markdown: bool = True,
    client_gravatar: bool = False,
    slim_presence: bool = False,
    event_types: Optional[Sequence[str]] = None,
    queue_lifespan_secs: int = 0,
    all_public_streams: bool = False,
    include_subscribers: bool = True,
    include_streams: bool = True,
    client_capabilities: Mapping[str, bool] = {},
    narrow: Collection[NarrowTerm] = [],
    fetch_event_types: Optional[Collection[str]] = None,
    spectator_requested_language: Optional[str] = None,
    pronouns_field_type_supported: bool = True,
) -> Dict[str, Any]:
    # Technically we don't need to check this here because
    # build_narrow_predicate will check it, but it's nicer from an error
    # handling perspective to do it before contacting Tornado
    check_narrow_for_events(narrow)

    notification_settings_null = client_capabilities.get("notification_settings_null", False)
    bulk_message_deletion = client_capabilities.get("bulk_message_deletion", False)
    user_avatar_url_field_optional = client_capabilities.get(
        "user_avatar_url_field_optional", False
    )
    stream_typing_notifications = client_capabilities.get("stream_typing_notifications", False)
    user_settings_object = client_capabilities.get("user_settings_object", False)
    linkifier_url_template = client_capabilities.get("linkifier_url_template", False)
    user_list_incomplete = client_capabilities.get("user_list_incomplete", False)

    if fetch_event_types is not None:
        event_types_set: Optional[Set[str]] = set(fetch_event_types)
    elif event_types is not None:
        event_types_set = set(event_types)
    else:
        event_types_set = None

    if user_profile is None:
        # TODO: Unify the two fetch_initial_state_data code paths.
        assert client_gravatar is False
        assert include_subscribers is False
        assert include_streams is False
        ret = fetch_initial_state_data(
            user_profile,
            realm=realm,
            event_types=event_types_set,
            queue_id=None,
            # Force client_gravatar=False for security reasons.
            client_gravatar=client_gravatar,
            linkifier_url_template=linkifier_url_template,
            user_avatar_url_field_optional=user_avatar_url_field_optional,
            user_settings_object=user_settings_object,
            user_list_incomplete=user_list_incomplete,
            # slim_presence is a noop, because presence is not included.
            slim_presence=True,
            # Force include_subscribers=False for security reasons.
            include_subscribers=include_subscribers,
            # Force include_streams=False for security reasons.
            include_streams=include_streams,
            spectator_requested_language=spectator_requested_language,
        )

        post_process_state(user_profile, ret, notification_settings_null=False)
        return ret

    # Fill up the UserMessage rows if a soft-deactivated user has returned
    reactivate_user_if_soft_deactivated(user_profile)

    legacy_narrow = [[nt.operator, nt.operand] for nt in narrow]

    # Note that we pass event_types, not fetch_event_types here, since
    # that's what controls which future events are sent.
    queue_id = request_event_queue(
        user_profile,
        user_client,
        apply_markdown,
        client_gravatar,
        slim_presence,
        queue_lifespan_secs,
        event_types,
        all_public_streams,
        narrow=legacy_narrow,
        bulk_message_deletion=bulk_message_deletion,
        stream_typing_notifications=stream_typing_notifications,
        user_settings_object=user_settings_object,
        pronouns_field_type_supported=pronouns_field_type_supported,
        linkifier_url_template=linkifier_url_template,
        user_list_incomplete=user_list_incomplete,
    )

    if queue_id is None:
        raise JsonableError(_("Could not allocate event queue"))

    ret = fetch_initial_state_data(
        user_profile,
        event_types=event_types_set,
        queue_id=queue_id,
        client_gravatar=client_gravatar,
        user_avatar_url_field_optional=user_avatar_url_field_optional,
        user_settings_object=user_settings_object,
        slim_presence=slim_presence,
        include_subscribers=include_subscribers,
        include_streams=include_streams,
        pronouns_field_type_supported=pronouns_field_type_supported,
        linkifier_url_template=linkifier_url_template,
        user_list_incomplete=user_list_incomplete,
    )

    # Apply events that came in while we were fetching initial data
    events = get_user_events(user_profile, queue_id, -1)
    apply_events(
        user_profile,
        state=ret,
        events=events,
        fetch_event_types=fetch_event_types,
        client_gravatar=client_gravatar,
        slim_presence=slim_presence,
        include_subscribers=include_subscribers,
        linkifier_url_template=linkifier_url_template,
        user_list_incomplete=user_list_incomplete,
    )

    post_process_state(user_profile, ret, notification_settings_null)

    if len(events) > 0:
        ret["last_event_id"] = events[-1]["id"]
    else:
        ret["last_event_id"] = -1
    return ret


def post_process_state(
    user_profile: Optional[UserProfile], ret: Dict[str, Any], notification_settings_null: bool
) -> None:
    """
    NOTE:

    Below is an example of post-processing initial state data AFTER we
    apply events.  For large payloads like `unread_msgs`, it's helpful
    to have an intermediate data structure that is easy to manipulate
    with O(1)-type operations as we apply events.

    Then, only at the end, we put it in the form that's more appropriate
    for client.
    """
    if "raw_unread_msgs" in ret:
        ret["unread_msgs"] = aggregate_unread_data(ret["raw_unread_msgs"])
        del ret["raw_unread_msgs"]

    """
    See the note above; the same technique applies below.
    """
    if "raw_users" in ret:
        user_dicts = sorted(ret["raw_users"].values(), key=lambda x: x["user_id"])

        ret["realm_users"] = [d for d in user_dicts if d["is_active"]]
        ret["realm_non_active_users"] = [d for d in user_dicts if not d["is_active"]]

        """
        Be aware that we do intentional aliasing in the below code.
        We can now safely remove the `is_active` field from all the
        dicts that got partitioned into the two lists above.

        We remove the field because it's already implied, and sending
        it to clients makes clients prone to bugs where they "trust"
        the field but don't actually update in live updates.  It also
        wastes bandwidth.
        """
        for d in user_dicts:
            d.pop("is_active")

        del ret["raw_users"]

    if "raw_recent_private_conversations" in ret:
        # Reformat recent_private_conversations to be a list of dictionaries, rather than a dict.
        ret["recent_private_conversations"] = sorted(
            (
                dict(
                    **value,
                )
                for (recipient_id, value) in ret["raw_recent_private_conversations"].items()
            ),
            key=lambda x: -x["max_message_id"],
        )
        del ret["raw_recent_private_conversations"]

    if not notification_settings_null and "subscriptions" in ret:
        for stream_dict in ret["subscriptions"] + ret["unsubscribed"]:
            handle_stream_notifications_compatibility(
                user_profile, stream_dict, notification_settings_null
            )
