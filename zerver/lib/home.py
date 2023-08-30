import calendar
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.http import HttpRequest
from django.utils import translation
from two_factor.utils import default_device

from zerver.context_processors import get_apps_page_url
from zerver.lib.events import do_events_register
from zerver.lib.i18n import (
    get_and_set_request_language,
    get_language_list,
    get_language_translation_data,
)
from zerver.lib.narrow_helpers import NarrowTerm
from zerver.lib.realm_description import get_realm_rendered_description
from zerver.lib.request import RequestNotes
from zerver.models import Message, Realm, Stream, UserProfile
from zerver.views.message_flags import get_latest_update_message_flag_activity
from zproject.config import get_config


@dataclass
class BillingInfo:
    show_billing: bool
    show_plans: bool


@dataclass
class UserPermissionInfo:
    color_scheme: int
    is_guest: bool
    is_realm_admin: bool
    is_realm_owner: bool
    show_webathena: bool


def get_furthest_read_time(user_profile: Optional[UserProfile]) -> Optional[float]:
    if user_profile is None:
        return time.time()

    user_activity = get_latest_update_message_flag_activity(user_profile)
    if user_activity is None:
        return None

    return calendar.timegm(user_activity.last_visit.utctimetuple())


def get_bot_types(user_profile: Optional[UserProfile]) -> List[Dict[str, object]]:
    bot_types: List[Dict[str, object]] = []
    if user_profile is None:
        return bot_types

    for type_id, name in UserProfile.BOT_TYPES.items():
        bot_types.append(
            dict(
                type_id=type_id,
                name=name,
                allowed=type_id in user_profile.allowed_bot_types,
            )
        )
    return bot_types


def promote_sponsoring_zulip_in_realm(realm: Realm) -> bool:
    if not settings.PROMOTE_SPONSORING_ZULIP:
        return False

    # If PROMOTE_SPONSORING_ZULIP is enabled, advertise sponsoring
    # Zulip in the gear menu of non-paying organizations.
    return realm.plan_type in [Realm.PLAN_TYPE_STANDARD_FREE, Realm.PLAN_TYPE_SELF_HOSTED]


def get_billing_info(user_profile: Optional[UserProfile]) -> BillingInfo:
    show_billing = False
    show_plans = False
    if settings.CORPORATE_ENABLED and user_profile is not None:
        if user_profile.has_billing_access:
            from corporate.models import CustomerPlan, get_customer_by_realm

            customer = get_customer_by_realm(user_profile.realm)
            if customer is not None:
                if customer.sponsorship_pending:
                    show_billing = True
                elif CustomerPlan.objects.filter(customer=customer).exists():
                    show_billing = True

        if not user_profile.is_guest and user_profile.realm.plan_type == Realm.PLAN_TYPE_LIMITED:
            show_plans = True

    return BillingInfo(
        show_billing=show_billing,
        show_plans=show_plans,
    )


def get_user_permission_info(user_profile: Optional[UserProfile]) -> UserPermissionInfo:
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
    user_profile: Optional[UserProfile],
    realm: Realm,
    insecure_desktop_app: bool,
    narrow: List[NarrowTerm],
    narrow_stream: Optional[Stream],
    narrow_topic: Optional[str],
    first_in_realm: bool,
    prompt_for_invites: bool,
    needs_tutorial: bool,
) -> Tuple[int, Dict[str, object]]:
    """
    This function computes page_params for when we load the home page.

    The page_params data structure gets sent to the client.
    """
    client_capabilities = {
        "notification_settings_null": True,
        "bulk_message_deletion": True,
        "user_avatar_url_field_optional": True,
        "stream_typing_notifications": False,  # Set this to True when frontend support is implemented.
        "user_settings_object": True,
        "linkifier_url_template": True,
    }

    if user_profile is not None:
        client = RequestNotes.get_notes(request).client
        assert client is not None
        register_ret = do_events_register(
            user_profile,
            realm,
            client,
            apply_markdown=True,
            client_gravatar=True,
            slim_presence=True,
            client_capabilities=client_capabilities,
            narrow=narrow,
            include_streams=False,
        )
        default_language = register_ret["user_settings"]["default_language"]
    else:
        # The spectator client will be fetching the /register response
        # for spectators via the API. But we still need to set the
        # values not presence in that object.
        register_ret = {
            "queue_id": None,
        }
        default_language = realm.default_language

    if user_profile is None:
        request_language = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, default_language)
    else:
        request_language = get_and_set_request_language(
            request,
            default_language,
            translation.get_language_from_path(request.path_info),
        )

    furthest_read_time = get_furthest_read_time(user_profile)
    two_fa_enabled = settings.TWO_FACTOR_AUTHENTICATION_ENABLED and user_profile is not None
    billing_info = get_billing_info(user_profile)
    user_permission_info = get_user_permission_info(user_profile)

    # Pass parameters to the client-side JavaScript code.
    # These end up in a JavaScript Object named 'page_params'.
    page_params: Dict[str, object] = dict(
        ## Server settings.
        test_suite=settings.TEST_SUITE,
        insecure_desktop_app=insecure_desktop_app,
        login_page=settings.HOME_NOT_LOGGED_IN,
        warn_no_email=settings.WARN_NO_EMAIL,
        # Only show marketing email settings if on Zulip Cloud
        corporate_enabled=settings.CORPORATE_ENABLED,
        ## Misc. extra data.
        language_list=get_language_list(),
        needs_tutorial=needs_tutorial,
        first_in_realm=first_in_realm,
        prompt_for_invites=prompt_for_invites,
        furthest_read_time=furthest_read_time,
        bot_types=get_bot_types(user_profile),
        two_fa_enabled=two_fa_enabled,
        apps_page_url=get_apps_page_url(),
        show_billing=billing_info.show_billing,
        promote_sponsoring_zulip=promote_sponsoring_zulip_in_realm(realm),
        show_plans=billing_info.show_plans,
        show_webathena=user_permission_info.show_webathena,
        # Adding two_fa_enabled as condition saves us 3 queries when
        # 2FA is not enabled.
        two_fa_enabled_user=two_fa_enabled and bool(default_device(user_profile)),
        is_spectator=user_profile is None,
        # There is no event queue for spectators since
        # events support for spectators is not implemented yet.
        no_event_queue=user_profile is None,
        server_sentry_dsn=settings.SENTRY_FRONTEND_DSN,
    )

    if settings.SENTRY_FRONTEND_DSN is not None:
        page_params["realm_sentry_key"] = realm.string_id
        page_params["server_sentry_environment"] = get_config(
            "machine", "deploy_type", "development"
        )
        page_params["server_sentry_sample_rate"] = settings.SENTRY_FRONTEND_SAMPLE_RATE
        page_params["server_sentry_trace_rate"] = settings.SENTRY_FRONTEND_TRACE_RATE

    for field_name in register_ret:
        page_params[field_name] = register_ret[field_name]

    if narrow_stream is not None:
        # In narrow_stream context, initial pointer is just latest message
        recipient = narrow_stream.recipient
        page_params["max_message_id"] = -1
        max_message = (
            # Uses index: zerver_message_realm_recipient_id
            Message.objects.filter(realm_id=realm.id, recipient=recipient)
            .order_by("-id")
            .only("id")
            .first()
        )
        if max_message:
            page_params["max_message_id"] = max_message.id
        page_params["narrow_stream"] = narrow_stream.name
        if narrow_topic is not None:
            page_params["narrow_topic"] = narrow_topic
        page_params["narrow"] = [
            dict(operator=term.operator, operand=term.operand) for term in narrow
        ]
        assert isinstance(page_params["user_settings"], dict)
        page_params["user_settings"]["enable_desktop_notifications"] = False

    page_params["translation_data"] = get_language_translation_data(request_language)

    if user_profile is None:
        # Get rendered version of realm description which is displayed in right
        # sidebar for spectator.
        page_params["realm_rendered_description"] = get_realm_rendered_description(realm)
        page_params["language_cookie_name"] = settings.LANGUAGE_COOKIE_NAME

    return register_ret["queue_id"], page_params
