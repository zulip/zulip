import calendar
import os
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpRequest
from django.utils import translation
from two_factor.utils import default_device

from zerver.context_processors import get_apps_page_url
from zerver.lib.events import ClientCapabilities, do_events_register
from zerver.lib.i18n import (
    get_and_set_request_language,
    get_language_list,
    get_language_translation_data,
)
from zerver.lib.narrow_helpers import NeverNegatedNarrowTerm
from zerver.lib.realm_description import get_realm_rendered_description
from zerver.lib.request import RequestNotes
from zerver.models import Message, Realm, Stream, UserProfile
from zerver.views.message_flags import get_latest_update_message_flag_activity


@dataclass
class BillingInfo:
    show_billing: bool
    show_plans: bool
    sponsorship_pending: bool
    show_remote_billing: bool


@dataclass
class UserPermissionInfo:
    color_scheme: int
    is_guest: bool
    is_realm_admin: bool
    is_realm_owner: bool
    show_webathena: bool


def get_furthest_read_time(user_profile: UserProfile | None) -> float | None:
    if user_profile is None:
        return time.time()

    user_activity = get_latest_update_message_flag_activity(user_profile)
    if user_activity is None:
        return None

    return calendar.timegm(user_activity.last_visit.utctimetuple())


def promote_sponsoring_zulip_in_realm(realm: Realm) -> bool:
    if not settings.PROMOTE_SPONSORING_ZULIP:
        return False

    # If PROMOTE_SPONSORING_ZULIP is enabled, advertise sponsoring
    # Zulip in the gear menu of non-paying organizations.
    return realm.plan_type in [Realm.PLAN_TYPE_STANDARD_FREE, Realm.PLAN_TYPE_SELF_HOSTED]


def get_user_permission_info(user_profile: UserProfile | None) -> UserPermissionInfo:
    if user_profile is not None:
        return UserPermissionInfo(
            color_scheme=user_profile.color_scheme,
            is_guest=user_profile.is_guest,
            is_realm_owner=user_profile.is_realm_owner,
            is_realm_admin=user_profile.is_realm_admin,
            show_webathena=user_profile.realm.webathena_enabled,
        )
    else:
        return UserPermissionInfo(
            color_scheme=UserProfile.COLOR_SCHEME_AUTOMATIC,
            is_guest=False,
            is_realm_admin=False,
            is_realm_owner=False,
            show_webathena=False,
        )


def build_page_params_for_home_page_load(
    request: HttpRequest,
    user_profile: UserProfile | None,
    realm: Realm,
    insecure_desktop_app: bool,
    narrow: list[NeverNegatedNarrowTerm],
    narrow_stream: Stream | None,
    narrow_topic_name: str | None,
) -> tuple[int, dict[str, object]]:
    """
    This function computes page_params for when we load the home page.

    The page_params data structure gets sent to the client.
    """

    client_capabilities = ClientCapabilities(
        notification_settings_null=True,
        bulk_message_deletion=True,
        user_avatar_url_field_optional=True,
        stream_typing_notifications=True,
        user_settings_object=True,
        linkifier_url_template=True,
        user_list_incomplete=True,
        include_deactivated_groups=True,
        archived_channels=True,
        empty_topic_name=True,
    )

    if user_profile is not None:
        client = RequestNotes.get_notes(request).client
        assert client is not None
        partial_subscribers = os.environ.get("PARTIAL_SUBSCRIBERS") is not None
        state_data = do_events_register(
            user_profile,
            realm,
            client,
            apply_markdown=True,
            client_gravatar=True,
            slim_presence=True,
            presence_last_update_id_fetched_by_client=-1,
            presence_history_limit_days=settings.PRESENCE_HISTORY_LIMIT_DAYS_FOR_WEB_APP,
            client_capabilities=client_capabilities,
            narrow=narrow,
            include_streams=False,
            include_subscribers="partial" if partial_subscribers else True,
        )
        queue_id = state_data["queue_id"]
        default_language = state_data["user_settings"]["default_language"]
    else:
        # The spectator client will be fetching the /register response
        # for spectators via the API.
        state_data = None
        queue_id = None
        default_language = realm.default_language

    if user_profile is None:
        request_language = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, default_language)
        split_url = urlsplit(request.build_absolute_uri())
        show_try_zulip_modal = (
            settings.DEVELOPMENT or split_url.hostname == "chat.zulip.org"
        ) and split_url.query == "show_try_zulip_modal"
    else:
        request_language = get_and_set_request_language(
            request,
            default_language,
            translation.get_language_from_path(request.path_info),
        )
        show_try_zulip_modal = False

    furthest_read_time = get_furthest_read_time(user_profile)
    two_fa_enabled = settings.TWO_FACTOR_AUTHENTICATION_ENABLED and user_profile is not None
    user_permission_info = get_user_permission_info(user_profile)

    # Pass parameters to the client-side JavaScript code.
    # These end up in a JavaScript Object named 'page_params'.
    #
    # Sync this with home_params_schema in base_page_params.ts.
    page_params: dict[str, object] = dict(
        page_type="home",
        ## Server settings.
        test_suite=settings.TEST_SUITE,
        insecure_desktop_app=insecure_desktop_app,
        login_page=settings.HOME_NOT_LOGGED_IN,
        warn_no_email=settings.WARN_NO_EMAIL,
        # Only show marketing email settings if on Zulip Cloud
        corporate_enabled=settings.CORPORATE_ENABLED,
        ## Misc. extra data.
        language_list=get_language_list(),
        furthest_read_time=furthest_read_time,
        embedded_bots_enabled=settings.EMBEDDED_BOTS_ENABLED,
        two_fa_enabled=two_fa_enabled,
        apps_page_url=get_apps_page_url(),
        promote_sponsoring_zulip=promote_sponsoring_zulip_in_realm(realm),
        show_webathena=user_permission_info.show_webathena,
        # Adding two_fa_enabled as condition saves us 3 queries when
        # 2FA is not enabled.
        two_fa_enabled_user=two_fa_enabled and bool(default_device(user_profile)),
        is_spectator=user_profile is None,
        presence_history_limit_days_for_web_app=settings.PRESENCE_HISTORY_LIMIT_DAYS_FOR_WEB_APP,
        # There is no event queue for spectators since
        # events support for spectators is not implemented yet.
        no_event_queue=user_profile is None,
        show_try_zulip_modal=show_try_zulip_modal,
    )

    page_params["state_data"] = state_data

    if narrow_stream is not None and state_data is not None:
        # In narrow_stream context, initial pointer is just latest message
        recipient = narrow_stream.recipient
        state_data["max_message_id"] = -1
        max_message = (
            # Uses index: zerver_message_realm_recipient_id
            Message.objects.filter(realm_id=realm.id, recipient=recipient)
            .order_by("-id")
            .only("id")
            .first()
        )
        if max_message:
            state_data["max_message_id"] = max_message.id
        page_params["narrow_stream"] = narrow_stream.name
        if narrow_topic_name is not None:
            page_params["narrow_topic"] = narrow_topic_name
        page_params["narrow"] = [
            dict(operator=term.operator, operand=term.operand) for term in narrow
        ]
        assert isinstance(state_data["user_settings"], dict)
        state_data["user_settings"]["enable_desktop_notifications"] = False

    page_params["translation_data"] = get_language_translation_data(request_language)

    if user_profile is None:
        # Get rendered version of realm description which is displayed in right
        # sidebar for spectator.
        page_params["realm_rendered_description"] = get_realm_rendered_description(realm)
        page_params["language_cookie_name"] = settings.LANGUAGE_COOKIE_NAME

    return queue_id, page_params
