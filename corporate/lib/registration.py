from django.conf import settings
from django.utils.translation import gettext as _

from corporate.lib.stripe import LicenseLimitError, get_latest_seat_count, get_seat_count
from corporate.models.plans import CustomerPlan, get_current_plan_by_realm
from zerver.actions.create_user import send_group_direct_message_to_admins
from zerver.lib.exceptions import InvitationError, JsonableError
from zerver.models import Realm, UserProfile
from zerver.models.users import get_system_bot


def get_plan_if_manual_license_management_enforced(realm: Realm) -> CustomerPlan | None:
    plan = get_current_plan_by_realm(realm)
    if plan is None or plan.automanage_licenses or plan.customer.exempt_from_license_number_check:
        return None
    return plan


def generate_licenses_low_warning_message_if_required(realm: Realm) -> str | None:
    plan = get_plan_if_manual_license_management_enforced(realm)
    if plan is None:
        return None

    licenses_remaining = plan.licenses() - get_latest_seat_count(realm)
    if licenses_remaining > 3:
        return None

    format_kwargs = {
        "billing_page_link": "/billing/",
        "deactivate_user_help_page_link": "/help/deactivate-or-reactivate-a-user",
    }

    if licenses_remaining <= 0:
        return _(
            "Your organization has no Zulip licenses remaining and can no longer accept new users. "
            "Please [increase the number of licenses]({billing_page_link}) or "
            "[deactivate inactive users]({deactivate_user_help_page_link}) to allow new users to join."
        ).format(**format_kwargs)

    return {
        1: _(
            "Your organization has only one Zulip license remaining. You can "
            "[increase the number of licenses]({billing_page_link}) or [deactivate inactive users]({deactivate_user_help_page_link}) "
            "to allow more than one user to join."
        ),
        2: _(
            "Your organization has only two Zulip licenses remaining. You can "
            "[increase the number of licenses]({billing_page_link}) or [deactivate inactive users]({deactivate_user_help_page_link}) "
            "to allow more than two users to join."
        ),
        3: _(
            "Your organization has only three Zulip licenses remaining. You can "
            "[increase the number of licenses]({billing_page_link}) or [deactivate inactive users]({deactivate_user_help_page_link}) "
            "to allow more than three users to join."
        ),
    }[licenses_remaining].format(**format_kwargs)


def send_user_unable_to_signup_group_direct_message_to_admins(
    realm: Realm, user_email: str
) -> None:
    message = _(
        "A new user ({email}) was unable to join because your organization does not have enough "
        "Zulip licenses. To allow new users to join, make sure that the [number of licenses for "
        "the current and next billing period]({billing_page_link}) is greater than the current "
        "number of users."
    ).format(
        email=user_email,
        billing_page_link="/billing/",
    )

    send_group_direct_message_to_admins(
        get_system_bot(settings.NOTIFICATION_BOT, realm.id), realm, message
    )


def check_spare_licenses_available(
    realm: Realm, plan: CustomerPlan, extra_non_guests_count: int = 0, extra_guests_count: int = 0
) -> None:
    seat_count = get_seat_count(
        realm, extra_non_guests_count=extra_non_guests_count, extra_guests_count=extra_guests_count
    )
    current_licenses = plan.licenses()
    renewal_licenses = plan.licenses_at_next_renewal()
    if current_licenses < seat_count or (renewal_licenses and renewal_licenses < seat_count):
        raise LicenseLimitError


def check_spare_licenses_available_for_registering_new_user(
    realm: Realm,
    user_email_to_add: str,
    role: int,
) -> None:
    plan = get_plan_if_manual_license_management_enforced(realm)
    if plan is None:
        return

    try:
        if role == UserProfile.ROLE_GUEST:
            check_spare_licenses_available(realm, plan, extra_guests_count=1)
        else:
            check_spare_licenses_available(realm, plan, extra_non_guests_count=1)
    except LicenseLimitError:
        send_user_unable_to_signup_group_direct_message_to_admins(realm, user_email_to_add)
        raise


def check_spare_licenses_available_for_inviting_new_users(
    realm: Realm, extra_non_guests_count: int = 0, extra_guests_count: int = 0
) -> None:
    plan = get_plan_if_manual_license_management_enforced(realm)
    if plan is None:
        return

    try:
        check_spare_licenses_available(realm, plan, extra_non_guests_count, extra_guests_count)
    except LicenseLimitError:
        message = _(
            "Your organization does not have enough Zulip licenses. Invitations were not sent."
        )
        raise InvitationError(message, [], sent_invitations=False, license_limit_reached=True)


def check_spare_license_available_for_changing_guest_user_role(realm: Realm) -> None:
    plan = get_plan_if_manual_license_management_enforced(realm)
    if plan is None:
        return

    try:
        check_spare_licenses_available(realm, plan, extra_non_guests_count=1)
    except LicenseLimitError:
        error_message = _(
            "Your organization does not have enough Zulip licenses to change a guest user's role."
        )
        raise JsonableError(error_message)
