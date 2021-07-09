from typing import Optional

from django.conf import settings
from django.utils.translation import gettext as _

from corporate.lib.stripe import LicenseLimitError, get_latest_seat_count
from corporate.models import get_current_plan_by_realm
from zerver.lib.actions import send_message_to_signup_notification_stream
from zerver.lib.exceptions import InvitationError
from zerver.models import Realm, get_system_bot


def generate_licenses_low_warning_message_if_required(realm: Realm) -> Optional[str]:
    plan = get_current_plan_by_realm(realm)
    if plan is None or plan.automanage_licenses:
        return None

    licenses_remaining = plan.licenses() - get_latest_seat_count(realm)
    if licenses_remaining > 3:
        return None

    format_kwargs = {
        "billing_page_link": "/billing/#settings",
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


def send_user_unable_to_signup_message_to_signup_notification_stream(
    realm: Realm, user_email: str
) -> None:
    message = _(
        "A new member ({email}) was unable to join your organization because all Zulip licenses "
        "are in use. Please [increase the number of licenses]({billing_page_link}) or "
        "[deactivate inactive users]({deactivate_user_help_page_link}) to allow new members to join."
    ).format(
        email=user_email,
        billing_page_link="/billing/#settings",
        deactivate_user_help_page_link="/help/deactivate-or-reactivate-a-user",
    )

    send_message_to_signup_notification_stream(
        get_system_bot(settings.NOTIFICATION_BOT, realm.id), realm, message
    )


def check_spare_licenses_available_for_adding_new_users(
    realm: Realm, number_of_users_to_add: int
) -> None:
    plan = get_current_plan_by_realm(realm)
    if (
        plan is None
        or plan.automanage_licenses
        or plan.customer.exempt_from_from_license_number_check
    ):
        return

    if plan.licenses() < get_latest_seat_count(realm) + number_of_users_to_add:
        raise LicenseLimitError()


def check_spare_licenses_available_for_registering_new_user(
    realm: Realm, user_email_to_add: str
) -> None:
    try:
        check_spare_licenses_available_for_adding_new_users(realm, 1)
    except LicenseLimitError:
        send_user_unable_to_signup_message_to_signup_notification_stream(realm, user_email_to_add)
        raise


def check_spare_licenses_available_for_inviting_new_users(realm: Realm, num_invites: int) -> None:
    try:
        check_spare_licenses_available_for_adding_new_users(realm, num_invites)
    except LicenseLimitError:
        if num_invites == 1:
            message = _("All Zulip licenses for this organization are currently in use.")
        else:
            message = _(
                "Your organization does not have enough unused Zulip licenses to invite {num_invites} users."
            ).format(num_invites=num_invites)
        raise InvitationError(message, [], sent_invitations=False, license_limit_reached=True)
