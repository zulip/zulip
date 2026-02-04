import uuid
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from typing_extensions import override

from confirmation.models import Confirmation, create_confirmation_link
from zerver.actions.invites import do_invite_users
from zerver.models import PreregistrationUser, UserProfile


class Command(BaseCommand):
    help = (
        "Create an invitation requiring the invited email and print the /register URL "
        "with prefilled email and invitation_key."
    )

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--invitee-email",
            dest="invitee_email",
            default="dev-enforce@example.com",
            help="Email address to invite (and enforce usage during registration)",
        )
        parser.add_argument(
            "--inviter-email",
            dest="inviter_email",
            default="hamlet@zulip.com",
            help="Existing user who will send the invitation",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        inviter_email: str = options["inviter_email"]
        invitee_email: str = options["invitee_email"]

        try:
            inviter = UserProfile.objects.get(email=inviter_email)
        except UserProfile.DoesNotExist:
            inviter_candidate = (
                UserProfile.objects.filter(is_bot=False, is_active=True).order_by("id").first()
            )
            if inviter_candidate is None:
                raise RuntimeError(
                    "No active human users found to act as inviter; please create a user first."
                )
            inviter = inviter_candidate

        # Clean up any existing PreregistrationUser objects for this email
        # to avoid "already invited" errors
        PreregistrationUser.objects.filter(email=invitee_email, realm=inviter.realm).delete()

        # If the base email still conflicts, generate a unique one
        original_invitee = invitee_email
        attempt = 0
        while True:
            try:
                skipped = do_invite_users(
                    inviter,
                    {invitee_email},
                    [],
                    notify_referrer_on_join=True,
                    user_groups=[],
                    invite_expires_in_minutes=24 * 60,
                    include_realm_default_subscriptions=False,
                    invite_as=PreregistrationUser.INVITE_AS["MEMBER"],
                    welcome_message_custom_text=None,
                    require_invited_email=True,
                )
                break
            except Exception as e:
                if "We weren't able to invite anyone" in str(e) and attempt < 5:
                    # Try with a unique email suffix
                    attempt += 1
                    base_email, domain = original_invitee.split("@", 1)
                    invitee_email = f"{base_email}-{uuid.uuid4().hex[:8]}@{domain}"
                    continue
                raise

        if skipped:
            self.stderr.write(self.style.WARNING(f"Skipped invites: {skipped}"))

        prereg = PreregistrationUser.objects.get(email=invitee_email)
        link = create_confirmation_link(
            prereg, Confirmation.INVITATION, validity_in_minutes=24 * 60
        )
        key = link.split("/")[-1]
        register_url = f"/register/?email={invitee_email}&invitation_key={key}"
        # Print both absolute and relative for convenience.
        self.stdout.write(self.style.SUCCESS("REGISTER_URL_RELATIVE=" + register_url))
        self.stdout.write(
            self.style.SUCCESS(f"REGISTER_URL_ABSOLUTE=http://localhost:9991{register_url}")
        )
        if invitee_email != original_invitee:
            self.stdout.write(
                self.style.WARNING(
                    f"Note: Used modified email {invitee_email} instead of {original_invitee} "
                    "to avoid conflicts."
                )
            )
