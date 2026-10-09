import calendar
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpRequest
from django.utils import translation
from two_factor.utils import default_device

from zerver.context_processors import get_apps_page_url
from zerver.lib.i18n import (
    get_and_set_request_language,
    get_default_language_for_user,
    get_language_list,
    get_language_translation_data,
)
from zerver.lib.realm_description import get_realm_rendered_description
from zerver.lib.workplace_users import (
    realm_eligible_for_non_workplace_pricing,
    realm_on_discounted_cloud_plan,
)
from zerver.models import Realm, Stream, UserProfile
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
        )
    else:
        return UserPermissionInfo(
            color_scheme=UserProfile.COLOR_SCHEME_AUTOMATIC,
            is_guest=False,
            is_realm_admin=False,
            is_realm_owner=False,
        )


def build_page_params_for_home_page_load(
    request: HttpRequest,
    user_profile: UserProfile | None,
    realm: Realm,
    insecure_desktop_app: bool,
    narrow_stream: Stream | None,
    narrow_topic_name: str | None,
) -> dict[str, object]:
    """
    This function computes page_params for when we load the home page.

    The page_params data structure gets sent to the client.

    The initial state is not included; the client fetches it via
    POST /json/register, which keeps this response small enough to
    load reliably on flaky networks (#36094).
    """

    if user_profile is None:
        request_language = request.COOKIES.get(
            settings.LANGUAGE_COOKIE_NAME, realm.default_language
        )
        split_url = urlsplit(request.build_absolute_uri())
        show_try_zulip_modal = (
            settings.DEVELOPMENT or split_url.hostname == "chat.zulip.org"
        ) and split_url.query == "show_try_zulip_modal"
    else:
        request_language = get_and_set_request_language(
            request,
            get_default_language_for_user(user_profile),
            translation.get_language_from_path(request.path_info),
        )
        show_try_zulip_modal = False

    furthest_read_time = get_furthest_read_time(user_profile)
    two_fa_enabled = settings.TWO_FACTOR_AUTHENTICATION_ENABLED and user_profile is not None

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
        # Adding two_fa_enabled as condition saves us 3 queries when
        # 2FA is not enabled.
        two_fa_enabled_user=two_fa_enabled and bool(default_device(user_profile)),
        is_spectator=user_profile is None,
        presence_history_limit_days_for_web_app=settings.PRESENCE_HISTORY_LIMIT_DAYS_FOR_WEB_APP,
        show_try_zulip_modal=show_try_zulip_modal,
        non_workplace_pricing_eligible=realm_eligible_for_non_workplace_pricing(realm),
        is_cloud_realm_with_discounted_plan=realm_on_discounted_cloud_plan(realm),
    )

    if narrow_stream is not None:
        page_params["narrow_stream"] = narrow_stream.name
        narrow = [dict(operator="stream", operand=narrow_stream.name)]
        if narrow_topic_name is not None:
            page_params["narrow_topic"] = narrow_topic_name
            narrow.append(dict(operator="topic", operand=narrow_topic_name))
        page_params["narrow"] = narrow

    page_params["translation_data"] = get_language_translation_data(request_language)

    # This is used by `admin.ts` to display realm description for non-administrator
    # logged-in users.
    page_params["realm_rendered_description"] = get_realm_rendered_description(realm)

    if user_profile is None:
        page_params["language_cookie_name"] = settings.LANGUAGE_COOKIE_NAME

    return page_params
