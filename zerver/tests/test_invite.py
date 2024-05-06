import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional, Sequence, Union
from unittest.mock import patch
from urllib.parse import quote, urlencode

import orjson
import time_machine
from django.conf import settings
from django.core import mail
from django.core.mail.message import EmailMultiAlternatives
from django.http import HttpRequest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from confirmation import settings as confirmation_settings
from confirmation.models import (
    Confirmation,
    ConfirmationKeyError,
    create_confirmation_link,
    get_object_from_key,
)
from corporate.lib.stripe import get_latest_seat_count
from zerver.actions.create_realm import do_change_realm_subdomain, do_create_realm
from zerver.actions.create_user import (
    do_create_user,
    process_new_human_user,
    set_up_streams_for_new_human_user,
)
from zerver.actions.default_streams import do_add_default_stream
from zerver.actions.invites import (
    do_create_multiuse_invite_link,
    do_get_invites_controlled_by_user,
    do_invite_users,
    do_revoke_multi_use_invite,
    too_many_recent_realm_invites,
)
from zerver.actions.realm_settings import (
    do_change_realm_permission_group_setting,
    do_change_realm_plan_type,
    do_set_realm_property,
)
from zerver.actions.user_settings import do_change_full_name
from zerver.actions.users import change_user_is_active
from zerver.context_processors import common_context
from zerver.lib.create_user import create_user
from zerver.lib.default_streams import get_default_streams_for_realm_as_dicts
from zerver.lib.send_email import FromAddress, deliver_scheduled_emails, send_future_email
from zerver.lib.streams import ensure_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import find_key_by_email
from zerver.models import (
    DefaultStream,
    Message,
    MultiuseInvite,
    NamedUserGroup,
    PreregistrationUser,
    Realm,
    ScheduledEmail,
    Stream,
    UserMessage,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.models.users import get_user_by_delivery_email
from zerver.views.invite import INVITATION_LINK_VALIDITY_MINUTES, get_invitee_emails_set
from zerver.views.registration import accounts_home

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class StreamSetupTest(ZulipTestCase):
    def add_messages_to_stream(self, stream_name: str) -> None:
        # Make sure that add_new_user_history has some messages
        # to process, so that we get consistent query counts.
        user = self.example_user("hamlet")
        self.subscribe(user, stream_name)

        for i in range(5):
            self.send_stream_message(user, stream_name, f"test {i}")

    def create_simple_new_user(self, realm: Realm, email: str) -> UserProfile:
        # We don't need to get bogged down in all the details of creating
        # full users to test how to set up streams.
        return create_user(
            email=email,
            password=None,
            realm=realm,
            full_name="full_name",
        )

    def test_query_counts_for_new_user_using_default_streams(self) -> None:
        DefaultStream.objects.all().delete()
        realm = get_realm("zulip")

        for i in range(25):
            stream = ensure_stream(realm, f"stream{i}", acting_user=None)
            do_add_default_stream(stream)

        self.add_messages_to_stream("stream5")

        new_user = self.create_simple_new_user(realm, "alice@zulip.com")

        with self.assert_database_query_count(13):
            set_up_streams_for_new_human_user(
                user_profile=new_user,
                prereg_user=None,
                default_stream_groups=[],
            )

    def test_query_counts_when_admin_assigns_streams(self) -> None:
        admin = self.example_user("iago")
        realm = admin.realm

        streams = [
            get_stream("Denmark", realm),
            get_stream("Rome", realm),
            get_stream("Scotland", realm),
            get_stream("Scotland", realm),
            get_stream("Verona", realm),
            get_stream("Venice", realm),
        ]

        self.add_messages_to_stream("Rome")

        new_user_email = "bob@zulip.com"

        do_invite_users(
            admin,
            [new_user_email],
            streams,
            invite_expires_in_minutes=1000,
        )

        prereg_user = PreregistrationUser.objects.get(email=new_user_email)

        new_user = self.create_simple_new_user(realm, new_user_email)

        with self.assert_database_query_count(13):
            set_up_streams_for_new_human_user(
                user_profile=new_user,
                prereg_user=prereg_user,
                default_stream_groups=[],
            )


class InviteUserBase(ZulipTestCase):
    def check_sent_emails(self, correct_recipients: List[str], clear: bool = False) -> None:
        self.assert_length(mail.outbox, len(correct_recipients))
        email_recipients = [email.recipients()[0] for email in mail.outbox]
        self.assertEqual(sorted(email_recipients), sorted(correct_recipients))
        if len(mail.outbox) == 0:
            return

        self.assertIn("Zulip", self.email_display_from(mail.outbox[0]))

        self.assertEqual(self.email_envelope_from(mail.outbox[0]), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertRegex(
            self.email_display_from(mail.outbox[0]), rf" <{self.TOKENIZED_NOREPLY_REGEX}>\Z"
        )

        if clear:
            mail.outbox = []

    def invite(
        self,
        invitee_emails: str,
        stream_names: Sequence[str],
        invite_expires_in_minutes: Optional[int] = INVITATION_LINK_VALIDITY_MINUTES,
        body: str = "",
        invite_as: int = PreregistrationUser.INVITE_AS["MEMBER"],
        realm: Optional[Realm] = None,
    ) -> "TestHttpResponse":
        """
        Invites the specified users to Zulip with the specified streams.

        users should be a string containing the users to invite, comma or
            newline separated.

        streams should be a list of strings.
        """
        stream_ids = [self.get_stream_id(stream_name, realm=realm) for stream_name in stream_names]

        invite_expires_in: Union[str, Optional[int]] = invite_expires_in_minutes
        if invite_expires_in is None:
            invite_expires_in = orjson.dumps(None).decode()

        with self.captureOnCommitCallbacks(execute=True):
            return self.client_post(
                "/json/invites",
                {
                    "invitee_emails": invitee_emails,
                    "invite_expires_in_minutes": invite_expires_in,
                    "stream_ids": orjson.dumps(stream_ids).decode(),
                    "invite_as": invite_as,
                },
                subdomain=realm.string_id if realm else "zulip",
            )


class InviteUserTest(InviteUserBase):
    def test_successful_invite_user(self) -> None:
        """
        A call to /json/invites with valid parameters causes an invitation
        email to be sent.
        """
        self.login("hamlet")
        invitee = "alice-test@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(invitee))
        self.check_sent_emails([invitee])

    def test_newbie_restrictions(self) -> None:
        user_profile = self.example_user("hamlet")
        invitee = "alice-test@zulip.com"
        stream_name = "Denmark"

        self.login_user(user_profile)

        result = self.invite(invitee, [stream_name])
        self.assert_json_success(result)

        user_profile.date_joined = timezone_now() - timedelta(days=10)
        user_profile.save()

        with self.settings(INVITES_MIN_USER_AGE_DAYS=5):
            result = self.invite(invitee, [stream_name])
            self.assert_json_success(result)

        with self.settings(INVITES_MIN_USER_AGE_DAYS=15):
            result = self.invite(invitee, [stream_name])
            self.assert_json_error_contains(result, "Your account is too new")

    def test_invite_limits(self) -> None:
        user_profile = self.example_user("hamlet")
        realm = user_profile.realm
        self.login_user(user_profile)

        def try_invite(
            num_invitees: int,
            *,
            default_realm_max: int,
            new_realm_max: int,
            realm_max: int,
            open_realm_creation: bool = True,
            realm: Optional[Realm] = None,
            stream_name: str = "Denmark",
        ) -> "TestHttpResponse":
            if realm is None:
                realm = get_realm("zulip")
            invitees = ",".join(
                [f"{realm.string_id}-{i:02}@zulip.com" for i in range(num_invitees)]
            )
            with self.settings(
                OPEN_REALM_CREATION=open_realm_creation,
                INVITES_DEFAULT_REALM_DAILY_MAX=default_realm_max,
                INVITES_NEW_REALM_LIMIT_DAYS=[(1, new_realm_max)],
            ):
                realm.max_invites = realm_max
                realm.save()
                return self.invite(invitees, [stream_name], realm=realm)

        # Trip the "new realm" limits
        realm.date_created = timezone_now()
        realm.save()
        result = try_invite(30, default_realm_max=50, new_realm_max=20, realm_max=40)
        self.assert_json_error_contains(result, "reached the limit")
        self.check_sent_emails([])

        # If some other realm consumes some invites, it affects our realm.  Invite 20 users in lear:
        lear_realm = get_realm("lear")
        lear_realm.date_created = timezone_now()
        lear_realm.save()
        self.login_user(self.lear_user("king"))
        result = try_invite(
            20,
            default_realm_max=50,
            new_realm_max=20,
            realm_max=40,
            realm=lear_realm,
            stream_name="general",
        )
        self.assert_json_success(result)
        self.check_sent_emails([f"lear-{i:02}@zulip.com" for i in range(20)], clear=True)

        # Which prevents inviting 1 in our realm:
        self.login_user(user_profile)
        result = try_invite(1, default_realm_max=50, new_realm_max=20, realm_max=40)
        self.assert_json_error_contains(result, "reached the limit")
        self.check_sent_emails([])

        # If our realm max is over the default realm's, we're exempt from INVITES_NEW_REALM_LIMIT_DAYS
        result = try_invite(10, default_realm_max=15, new_realm_max=5, realm_max=20)
        self.assert_json_success(result)
        self.check_sent_emails([f"zulip-{i:02}@zulip.com" for i in range(10)], clear=True)

        # We've sent 10 invites.  Trying to invite 15 people, even if
        # 10 of them are the same, still trips the limit (10 previous
        # + 15 in this submission > 20 realm max)
        result = try_invite(15, default_realm_max=15, new_realm_max=5, realm_max=20)
        self.assert_json_error_contains(result, "reached the limit")
        self.check_sent_emails([])

        # Inviting 10 more people (to the realm max of 20) works, and
        # sends emails to the same 10 users again.
        result = try_invite(10, default_realm_max=15, new_realm_max=5, realm_max=20)
        self.assert_json_success(result)
        self.check_sent_emails([f"zulip-{i:02}@zulip.com" for i in range(10)], clear=True)

        # We've sent 20 invites.  The 10 we just sent do count against
        # us if we send to them again, since we did send mail
        result = try_invite(10, default_realm_max=15, new_realm_max=5, realm_max=20)
        self.assert_json_error_contains(result, "reached the limit")
        self.check_sent_emails([])

        # We've sent 20 invites.  The realm is exempt from the new realm max
        # (INVITES_NEW_REALM_LIMIT_DAYS) if it is old enough
        realm.date_created = timezone_now() - timedelta(days=8)
        realm.save()
        result = try_invite(10, default_realm_max=50, new_realm_max=20, realm_max=40)
        self.assert_json_success(result)
        self.check_sent_emails([f"zulip-{i:02}@zulip.com" for i in range(10)], clear=True)

        # We've sent 30 invites.  None of the limits matter if open
        # realm creation is disabled.
        result = try_invite(
            10, default_realm_max=30, new_realm_max=20, realm_max=10, open_realm_creation=False
        )
        self.assert_json_success(result)
        self.check_sent_emails([f"zulip-{i:02}@zulip.com" for i in range(10)], clear=True)

        # We've sent 40 invites "today".  Fast-forward 48 hours
        # and ensure that we can invite more people
        with time_machine.travel(timezone_now() + timedelta(hours=48), tick=False):
            result = try_invite(5, default_realm_max=30, new_realm_max=20, realm_max=10)
            self.assert_json_success(result)
            self.check_sent_emails([f"zulip-{i:02}@zulip.com" for i in range(5)], clear=True)

            # We've sent 5 invites.  Ensure we can trip the fresh "today" limit for the realm
            result = try_invite(10, default_realm_max=30, new_realm_max=20, realm_max=10)
            self.assert_json_error_contains(result, "reached the limit")
            self.check_sent_emails([])

            # We've sent 5 invites.  Reset the realm to be "recently"
            # created, and ensure that we can trip the whole-server
            # limit
            realm.date_created = timezone_now() - timedelta(days=3)
            realm.save()
            result = try_invite(10, default_realm_max=50, new_realm_max=10, realm_max=40)
            self.assert_json_error_contains(result, "reached the limit")
            self.check_sent_emails([])

    @override_settings(OPEN_REALM_CREATION=True)
    def test_limited_plan_heuristics(self) -> None:
        # There additional limits only apply if OPEN_REALM_CREATION is
        # True and the plan is "limited," which is primarily only
        # relevant on Zulip Cloud.

        realm = do_create_realm("sdfoijt23489fuskdfjhksdf", "Totally Normal")
        realm.plan_type = Realm.PLAN_TYPE_LIMITED
        realm.invite_required = False
        realm.save()

        # Create a first user
        admin_user = do_create_user(
            "someone@example.com",
            "password",
            realm,
            "full name",
            role=UserProfile.ROLE_REALM_OWNER,
            realm_creation=True,
            acting_user=None,
        )

        # Inviting would work at all
        with self.assertLogs(level="INFO") as m:
            self.assertFalse(too_many_recent_realm_invites(realm, 1))
        self.assertEqual(
            m.output,
            [
                (
                    "INFO:root:sdfoijt23489fuskdfjhksdf "
                    "(!: random-realm-name,no-realm-description,no-realm-icon,realm-created-in-last-hour,only-one-user,no-messages-sent) "
                    "inviting 1 more, have 0 recent, but only 1 current users.  "
                    "Ratio 1.0, 2 allowed"
                )
            ],
        )

        # This realm is currently very suspicious, so can only invite
        # 2 users at once (2x current 1 user)
        with self.assertLogs(level="INFO") as m:
            self.assertFalse(too_many_recent_realm_invites(realm, 2))
            self.assertTrue(too_many_recent_realm_invites(realm, 3))
        self.assertEqual(
            m.output,
            [
                (
                    "INFO:root:sdfoijt23489fuskdfjhksdf "
                    "(!: random-realm-name,no-realm-description,no-realm-icon,realm-created-in-last-hour,only-one-user,no-messages-sent) "
                    "inviting 2 more, have 0 recent, but only 1 current users.  "
                    "Ratio 2.0, 2 allowed"
                ),
                (
                    "WARNING:root:sdfoijt23489fuskdfjhksdf "
                    "(!: random-realm-name,no-realm-description,no-realm-icon,realm-created-in-last-hour,only-one-user,no-messages-sent) "
                    "inviting 3 more, have 0 recent, but only 1 current users.  "
                    "Ratio 3.0, 2 allowed"
                ),
            ],
        )

        # Having another user makes it slightly less suspicious, and
        # also able to invite more in ratio with the current count of
        # users (3x current 2 users)
        self.register("other@example.com", "test", subdomain=realm.string_id)
        with self.assertLogs(level="INFO") as m:
            self.assertFalse(too_many_recent_realm_invites(realm, 6))
            self.assertTrue(too_many_recent_realm_invites(realm, 7))
        self.assertEqual(
            m.output,
            [
                (
                    "INFO:root:sdfoijt23489fuskdfjhksdf "
                    "(!: random-realm-name,no-realm-description,no-realm-icon,realm-created-in-last-hour,no-messages-sent) "
                    "inviting 6 more, have 0 recent, but only 2 current users.  "
                    "Ratio 3.0, 3 allowed"
                ),
                (
                    "WARNING:root:sdfoijt23489fuskdfjhksdf "
                    "(!: random-realm-name,no-realm-description,no-realm-icon,realm-created-in-last-hour,no-messages-sent) "
                    "inviting 7 more, have 0 recent, but only 2 current users.  "
                    "Ratio 3.5, 3 allowed"
                ),
            ],
        )

        # Remove some more warning flags
        do_change_realm_subdomain(realm, "reasonable", acting_user=None)
        realm.description = "A real place"
        realm.date_created = timezone_now() - timedelta(hours=2)
        realm.save()

        # This is now more allowable (5x current 2 users)
        with self.assertLogs(level="INFO") as m:
            self.assertFalse(too_many_recent_realm_invites(realm, 10))
            self.assertTrue(too_many_recent_realm_invites(realm, 11))
        self.assertEqual(
            m.output,
            [
                (
                    "INFO:root:reasonable "
                    "(!: no-realm-icon,no-messages-sent) "
                    "inviting 10 more, have 0 recent, but only 2 current users.  "
                    "Ratio 5.0, 5 allowed"
                ),
                (
                    "WARNING:root:reasonable "
                    "(!: no-realm-icon,no-messages-sent) "
                    "inviting 11 more, have 0 recent, but only 2 current users.  "
                    "Ratio 5.5, 5 allowed"
                ),
            ],
        )

        # If we have a different max_invites on the realm that kicks in, though
        realm.max_invites = 8
        realm.save()
        self.assertFalse(too_many_recent_realm_invites(realm, 8))
        self.assertTrue(too_many_recent_realm_invites(realm, 9))

        # And if we have a non-default max invite then that applies
        # but not the heuristics (which would limit us to 10, here)
        realm.max_invites = 12
        realm.save()
        self.assertFalse(too_many_recent_realm_invites(realm, 12))
        self.assertTrue(too_many_recent_realm_invites(realm, 13))

        # Not being a limited plan also opens us up from the
        # heuristics.  First, set us back to the default invite limit
        realm.max_invites = settings.INVITES_DEFAULT_REALM_DAILY_MAX
        realm.save()
        with self.assertLogs(level="INFO") as m:
            self.assertFalse(too_many_recent_realm_invites(realm, 10))
            self.assertTrue(too_many_recent_realm_invites(realm, 11))
        self.assertEqual(
            m.output,
            [
                (
                    "INFO:root:reasonable "
                    "(!: no-realm-icon,no-messages-sent) "
                    "inviting 10 more, have 0 recent, but only 2 current users.  "
                    "Ratio 5.0, 5 allowed"
                ),
                (
                    "WARNING:root:reasonable "
                    "(!: no-realm-icon,no-messages-sent) "
                    "inviting 11 more, have 0 recent, but only 2 current users.  "
                    "Ratio 5.5, 5 allowed"
                ),
            ],
        )
        # Become a Standard plan
        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_STANDARD, acting_user=admin_user)
        self.assertFalse(too_many_recent_realm_invites(realm, 3000))
        self.assertTrue(too_many_recent_realm_invites(realm, 3001))
        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_STANDARD_FREE, acting_user=admin_user)
        self.assertFalse(too_many_recent_realm_invites(realm, 3000))
        self.assertTrue(too_many_recent_realm_invites(realm, 3001))

    def test_invite_user_to_realm_on_manual_license_plan(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        _, ledger = self.subscribe_realm_to_monthly_plan_on_manual_license_management(
            user.realm, 50, 50
        )

        with self.settings(BILLING_ENABLED=True):
            result = self.invite(self.nonreg_email("alice"), ["Denmark"])
        self.assert_json_success(result)

        ledger.licenses_at_next_renewal = 5
        ledger.save(update_fields=["licenses_at_next_renewal"])
        with self.settings(BILLING_ENABLED=True):
            result = self.invite(self.nonreg_email("bob"), ["Denmark"])
        self.assert_json_success(result)

        ledger.licenses = get_latest_seat_count(user.realm) + 1
        ledger.save(update_fields=["licenses"])
        with self.settings(BILLING_ENABLED=True):
            invitee_emails = self.nonreg_email("bob") + "," + self.nonreg_email("alice")
            result = self.invite(invitee_emails, ["Denmark"])
        self.assert_json_error_contains(
            result, "Your organization does not have enough unused Zulip licenses to invite 2 users"
        )

        ledger.licenses = get_latest_seat_count(user.realm)
        ledger.save(update_fields=["licenses"])
        with self.settings(BILLING_ENABLED=True):
            result = self.invite(self.nonreg_email("bob"), ["Denmark"])
        self.assert_json_error_contains(
            result, "All Zulip licenses for this organization are currently in use"
        )

        with self.settings(BILLING_ENABLED=True):
            result = self.invite(
                self.nonreg_email("bob"),
                ["Denmark"],
                invite_as=PreregistrationUser.INVITE_AS["GUEST_USER"],
            )
        self.assert_json_success(result)

    def test_cross_realm_bot(self) -> None:
        inviter = self.example_user("hamlet")
        self.login_user(inviter)

        cross_realm_bot_email = "emailgateway@zulip.com"
        legit_new_email = "fred@zulip.com"
        invitee_emails = f"{cross_realm_bot_email},{legit_new_email}"

        result = self.invite(invitee_emails, ["Denmark"])
        self.assert_json_error(
            result,
            (
                "Some of those addresses are already using Zulip, so we didn't send them an"
                " invitation. We did send invitations to everyone else!"
            ),
        )

    def test_invite_mirror_dummy_user(self) -> None:
        """
        A mirror dummy account is a temporary account
        that we keep in our system if we are mirroring
        data from something like Zephyr or IRC.

        We want users to eventually just sign up or
        register for Zulip, in which case we will just
        fully "activate" the account.

        Here we test that you can invite a person who
        has a mirror dummy account.
        """
        inviter = self.example_user("hamlet")
        self.login_user(inviter)

        mirror_user = self.example_user("cordelia")
        mirror_user.is_mirror_dummy = True
        mirror_user.save()
        change_user_is_active(mirror_user, False)

        self.assertEqual(
            PreregistrationUser.objects.filter(email=mirror_user.email).count(),
            0,
        )

        result = self.invite(mirror_user.email, ["Denmark"])
        self.assert_json_success(result)

        prereg_user = PreregistrationUser.objects.get(email=mirror_user.email)
        assert prereg_user.referred_by is not None and inviter is not None
        self.assertEqual(
            prereg_user.referred_by.email,
            inviter.email,
        )

    def test_invite_from_now_deactivated_user(self) -> None:
        """
        While accepting an invitation from a user,
        processing for a new user account will only
        be completed if the inviter is not deactivated
        after sending the invite.
        """
        inviter = self.example_user("hamlet")
        self.login_user(inviter)
        invitee = self.nonreg_email("alice")

        result = self.invite(invitee, ["Denmark"])
        self.assert_json_success(result)

        prereg_user = PreregistrationUser.objects.get(email=invitee)
        change_user_is_active(inviter, False)
        do_create_user(
            invitee,
            "password",
            inviter.realm,
            "full name",
            prereg_user=prereg_user,
            acting_user=None,
        )

    def test_successful_invite_user_as_owner_from_owner_account(self) -> None:
        self.login("desdemona")
        invitee = self.nonreg_email("alice")
        result = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_OWNER"]
        )
        self.assert_json_success(result)
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        self.assertTrue(invitee_profile.is_realm_owner)
        self.assertFalse(invitee_profile.is_guest)
        self.check_user_added_in_system_group(invitee_profile)

    def test_invite_user_as_owner_from_admin_account(self) -> None:
        self.login("iago")
        invitee = self.nonreg_email("alice")
        response = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_OWNER"]
        )
        self.assert_json_error(response, "Must be an organization owner")

    def test_successful_invite_user_as_admin_from_admin_account(self) -> None:
        self.login("iago")
        invitee = self.nonreg_email("alice")
        result = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_ADMIN"]
        )
        self.assert_json_success(result)
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        self.assertTrue(invitee_profile.is_realm_admin)
        self.assertFalse(invitee_profile.is_realm_owner)
        self.assertFalse(invitee_profile.is_guest)
        self.check_user_added_in_system_group(invitee_profile)

    def test_invite_user_as_admin_from_normal_account(self) -> None:
        self.login("hamlet")
        invitee = self.nonreg_email("alice")
        response = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_ADMIN"]
        )
        self.assert_json_error(response, "Must be an organization administrator")

    def test_successful_invite_user_as_moderator_from_admin_account(self) -> None:
        self.login("iago")
        invitee = self.nonreg_email("alice")
        result = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["MODERATOR"]
        )
        self.assert_json_success(result)
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        self.assertFalse(invitee_profile.is_realm_admin)
        self.assertTrue(invitee_profile.is_moderator)
        self.assertFalse(invitee_profile.is_guest)
        self.check_user_added_in_system_group(invitee_profile)

    def test_invite_user_as_moderator_from_normal_account(self) -> None:
        self.login("hamlet")
        invitee = self.nonreg_email("alice")
        response = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["MODERATOR"]
        )
        self.assert_json_error(response, "Must be an organization administrator")

    def test_invite_user_as_moderator_from_moderator_account(self) -> None:
        self.login("shiva")
        invitee = self.nonreg_email("alice")
        response = self.invite(
            invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["MODERATOR"]
        )
        self.assert_json_error(response, "Must be an organization administrator")

    def test_invite_user_as_invalid_type(self) -> None:
        """
        Test inviting a user as invalid type of user i.e. type of invite_as
        is not in PreregistrationUser.INVITE_AS
        """
        self.login("iago")
        invitee = self.nonreg_email("alice")
        response = self.invite(invitee, ["Denmark"], invite_as=10)
        self.assert_json_error(response, "Invalid invite_as")

    def test_successful_invite_user_as_guest_from_normal_account(self) -> None:
        self.login("hamlet")
        invitee = self.nonreg_email("alice")
        self.assert_json_success(
            self.invite(invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["GUEST_USER"])
        )
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        self.assertFalse(invitee_profile.is_realm_admin)
        self.assertTrue(invitee_profile.is_guest)
        self.check_user_added_in_system_group(invitee_profile)

    def test_successful_invite_user_as_guest_from_admin_account(self) -> None:
        self.login("iago")
        invitee = self.nonreg_email("alice")
        self.assert_json_success(
            self.invite(invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["GUEST_USER"])
        )
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        self.assertFalse(invitee_profile.is_realm_admin)
        self.assertTrue(invitee_profile.is_guest)
        self.check_user_added_in_system_group(invitee_profile)

    def test_successful_invite_user_with_name(self) -> None:
        """
        A call to /json/invites with valid parameters causes an invitation
        email to be sent.
        """
        self.login("hamlet")
        email = "alice-test@zulip.com"
        invitee = f"Alice Test <{email}>"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.check_sent_emails([email])

    def test_successful_invite_user_with_name_and_normal_one(self) -> None:
        """
        A call to /json/invites with valid parameters causes an invitation
        email to be sent.
        """
        self.login("hamlet")
        email = "alice-test@zulip.com"
        email2 = "bob-test@zulip.com"
        invitee = f"Alice Test <{email}>, {email2}"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2])

    def test_successful_invite_users_with_specified_streams(self) -> None:
        invitee = self.nonreg_email("alice")
        realm = get_realm("zulip")
        self.login("hamlet")

        stream_names = ["Rome", "Scotland", "Venice"]
        streams = [get_stream(stream_name, realm) for stream_name in stream_names]
        self.assert_json_success(self.invite(invitee, stream_names))
        self.assertTrue(find_key_by_email(invitee))
        self.submit_reg_form_for_user(invitee, "password")
        self.check_user_subscribed_only_to_streams("alice", streams)

        invitee = self.nonreg_email("bob")
        self.assert_json_success(self.invite(invitee, []))
        self.assertTrue(find_key_by_email(invitee))

        default_streams = get_default_streams_for_realm_as_dicts(realm.id)
        self.assert_length(default_streams, 1)

        self.submit_reg_form_for_user(invitee, "password")
        # If no streams are provided, user is not subscribed to
        # default streams as well.
        self.check_user_subscribed_only_to_streams("bob", [])

    def test_can_invite_others_to_realm(self) -> None:
        def validation_func(user_profile: UserProfile) -> bool:
            return user_profile.can_invite_users_by_email()

        realm = get_realm("zulip")
        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_NOBODY, acting_user=None
        )
        desdemona = self.example_user("desdemona")
        self.assertFalse(validation_func(desdemona))

        self.check_has_permission_policies("invite_to_realm_policy", validation_func)

    def test_invite_others_to_realm_setting(self) -> None:
        """
        The invite_to_realm_policy realm setting works properly.
        """
        realm = get_realm("zulip")
        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_NOBODY, acting_user=None
        )
        self.login("desdemona")
        email = "alice-test@zulip.com"
        email2 = "bob-test@zulip.com"
        invitee = f"Alice Test <{email}>, {email2}"
        self.assert_json_error(
            self.invite(invitee, ["Denmark"]),
            "Insufficient permission",
        )

        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_ADMINS_ONLY, acting_user=None
        )

        self.login("shiva")
        self.assert_json_error(
            self.invite(invitee, ["Denmark"]),
            "Insufficient permission",
        )

        # Now verify an administrator can do it
        self.login("iago")
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))

        self.check_sent_emails([email, email2])

        mail.outbox = []

        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_MODERATORS_ONLY, acting_user=None
        )
        self.login("hamlet")
        email = "carol-test@zulip.com"
        email2 = "earl-test@zulip.com"
        invitee = f"Carol Test <{email}>, {email2}"
        self.assert_json_error(
            self.invite(invitee, ["Denmark"]),
            "Insufficient permission",
        )

        self.login("shiva")
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2])

        mail.outbox = []

        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_MEMBERS_ONLY, acting_user=None
        )

        self.login("polonius")
        email = "dave-test@zulip.com"
        email2 = "mark-test@zulip.com"
        invitee = f"Dave Test <{email}>, {email2}"
        self.assert_json_error(self.invite(invitee, ["Denmark"]), "Not allowed for guest users")

        self.login("hamlet")
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2])

        mail.outbox = []

        do_set_realm_property(
            realm, "invite_to_realm_policy", Realm.POLICY_FULL_MEMBERS_ONLY, acting_user=None
        )
        do_set_realm_property(realm, "waiting_period_threshold", 1000, acting_user=None)

        hamlet = self.example_user("hamlet")
        hamlet.date_joined = timezone_now() - timedelta(days=realm.waiting_period_threshold - 1)

        email = "issac-test@zulip.com"
        email2 = "steven-test@zulip.com"
        invitee = f"Issac Test <{email}>, {email2}"
        self.assert_json_error(
            self.invite(invitee, ["Denmark"]),
            "Insufficient permission",
        )

        do_set_realm_property(realm, "waiting_period_threshold", 0, acting_user=None)

        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(email))
        self.assertTrue(find_key_by_email(email2))
        self.check_sent_emails([email, email2])

    def test_invite_user_signup_initial_history(self) -> None:
        """
        Test that a new user invited to a stream receives some initial
        history but only from public streams.
        """
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
        private_stream_name = "Secret"
        self.make_stream(private_stream_name, invite_only=True)
        self.subscribe(user_profile, private_stream_name)
        public_msg_id = self.send_stream_message(
            self.example_user("hamlet"),
            "Denmark",
            topic_name="Public topic",
            content="Public message",
        )
        secret_msg_id = self.send_stream_message(
            self.example_user("hamlet"),
            private_stream_name,
            topic_name="Secret topic",
            content="Secret message",
        )
        invitee = self.nonreg_email("alice")
        self.assert_json_success(self.invite(invitee, [private_stream_name, "Denmark"]))
        self.assertTrue(find_key_by_email(invitee))

        self.submit_reg_form_for_user(invitee, "password")
        invitee_profile = self.nonreg_user("alice")
        invitee_msg_ids = [
            um.message_id for um in UserMessage.objects.filter(user_profile=invitee_profile)
        ]
        self.assertTrue(public_msg_id in invitee_msg_ids)
        self.assertFalse(secret_msg_id in invitee_msg_ids)
        self.assertFalse(invitee_profile.is_realm_admin)

        invitee_msg, signups_stream_msg, inviter_msg, secret_msg = Message.objects.all().order_by(
            "-id"
        )[0:4]

        self.assertEqual(secret_msg.id, secret_msg_id)

        self.assertEqual(inviter_msg.sender.email, "notification-bot@zulip.com")
        self.assertTrue(
            inviter_msg.content.startswith(
                f"@_**{invitee_profile.full_name}|{invitee_profile.id}** accepted your",
            )
        )

        self.assertEqual(signups_stream_msg.sender.email, "notification-bot@zulip.com")
        self.assertTrue(
            signups_stream_msg.content.startswith(
                f"@_**alice_zulip.com|{invitee_profile.id}** joined this organization",
            )
        )

        self.assertEqual(invitee_msg.sender.email, "welcome-bot@zulip.com")
        self.assertTrue(invitee_msg.content.startswith("Hello, and welcome to Zulip!"))
        self.assertNotIn("demo organization", invitee_msg.content)

    def test_multi_user_invite(self) -> None:
        """
        Invites multiple users with a variety of delimiters.
        """
        self.login("hamlet")
        # Intentionally use a weird string.
        self.assert_json_success(
            self.invite(
                """bob-test@zulip.com,     carol-test@zulip.com,
            dave-test@zulip.com


earl-test@zulip.com""",
                ["Denmark"],
            )
        )
        for user in ("bob", "carol", "dave", "earl"):
            self.assertTrue(find_key_by_email(f"{user}-test@zulip.com"))
        self.check_sent_emails(
            [
                "bob-test@zulip.com",
                "carol-test@zulip.com",
                "dave-test@zulip.com",
                "earl-test@zulip.com",
            ]
        )

    def test_max_invites_model(self) -> None:
        realm = get_realm("zulip")
        self.assertEqual(realm.max_invites, settings.INVITES_DEFAULT_REALM_DAILY_MAX)
        realm.max_invites = 3
        realm.save()
        self.assertEqual(get_realm("zulip").max_invites, 3)
        realm.max_invites = settings.INVITES_DEFAULT_REALM_DAILY_MAX
        realm.save()

    def test_missing_or_invalid_params(self) -> None:
        """
        Tests inviting with various missing or invalid parameters.
        """
        realm = get_realm("zulip")
        do_set_realm_property(realm, "emails_restricted_to_domains", True, acting_user=None)

        self.login("hamlet")

        for address in ("noatsign.com", "outsideyourdomain@example.net"):
            self.assert_json_error(
                self.invite(address, ["Denmark"]),
                "Some emails did not validate, so we didn't send any invitations.",
            )
        self.check_sent_emails([])

        self.assert_json_error(
            self.invite("", ["Denmark"]), "You must specify at least one email address."
        )
        self.check_sent_emails([])

    def test_guest_user_invitation(self) -> None:
        """
        Guest user can't invite new users
        """
        self.login("polonius")
        invitee = "alice-test@zulip.com"
        self.assert_json_error(self.invite(invitee, ["Denmark"]), "Not allowed for guest users")
        self.assertEqual(find_key_by_email(invitee), None)
        self.check_sent_emails([])

    def test_invalid_stream(self) -> None:
        """
        Tests inviting to a non-existent stream.
        """
        self.login("hamlet")
        self.assert_json_error(
            self.invite("iago-test@zulip.com", ["NotARealStream"]),
            f"Invalid channel ID {self.INVALID_STREAM_ID}. No invites were sent.",
        )
        self.check_sent_emails([])

    def test_invite_existing_user(self) -> None:
        """
        If you invite an address already using Zulip, no invitation is sent.
        """
        self.login("hamlet")

        hamlet_email = "hAmLeT@zUlIp.com"
        result = self.invite(hamlet_email, ["Denmark"])
        self.assert_json_error(result, "We weren't able to invite anyone.")

        self.assertFalse(
            PreregistrationUser.objects.filter(email__iexact=hamlet_email).exists(),
        )
        self.check_sent_emails([])

    def normalize_string(self, s: str) -> str:
        s = s.strip()
        return re.sub(r"\s+", " ", s)

    def test_invite_links_in_name(self) -> None:
        """
        Names are escaped in the emails which are sent.
        """
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        # Test we properly handle links in user full names
        do_change_full_name(hamlet, "</a> https://www.google.com", hamlet)

        result = self.invite("newuser@zulip.com", ["Denmark"])
        self.assert_json_success(result)
        self.check_sent_emails(["newuser@zulip.com"])
        assert isinstance(mail.outbox[0], EmailMultiAlternatives)
        assert isinstance(mail.outbox[0].alternatives[0][0], str)
        body = self.normalize_string(mail.outbox[0].alternatives[0][0])

        # Verify that one can't get Zulip to send invitation emails
        # that third-party products will linkify using the full_name
        # field, because we've included that field inside the mailto:
        # link for the sender.
        self.assertIn(
            '<a href="mailto:hamlet@zulip.com" style="color: #5f5ec7;text-decoration: underline;">&lt;/a&gt; https://www.google.com (hamlet@zulip.com)</a> wants',
            body,
        )

        # TODO: Ideally, this test would also test the Invitation
        # Reminder email generated, but the test setup for that is
        # annoying.

    def test_invite_some_existing_some_new(self) -> None:
        """
        If you invite a mix of already existing and new users, invitations are
        only sent to the new users.
        """
        self.login("hamlet")
        existing = [self.example_email("hamlet"), "othello@zulip.com"]
        new = ["foo-test@zulip.com", "bar-test@zulip.com"]
        invitee_emails = "\n".join(existing + new)
        self.assert_json_error(
            self.invite(invitee_emails, ["Denmark"]),
            "Some of those addresses are already using Zulip, \
so we didn't send them an invitation. We did send invitations to everyone else!",
        )

        # We only created accounts for the new users.
        for email in existing:
            with self.assertRaises(PreregistrationUser.DoesNotExist):
                PreregistrationUser.objects.get(email=email)
        for email in new:
            self.assertTrue(PreregistrationUser.objects.get(email=email))

        # We only sent emails to the new users.
        self.check_sent_emails(new)

    def test_invite_outside_domain_in_closed_realm(self) -> None:
        """
        In a realm with `emails_restricted_to_domains = True`, you can't invite people
        with a different domain from that of the realm or your e-mail address.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = True
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo@example.com"

        self.assert_json_error(
            self.invite(external_address, ["Denmark"]),
            "Some emails did not validate, so we didn't send any invitations.",
        )

    def test_invite_using_disposable_email(self) -> None:
        """
        In a realm with `disallow_disposable_email_addresses = True`, you can't invite
        people with a disposable domain.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.disallow_disposable_email_addresses = True
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo@mailnator.com"

        self.assert_json_error(
            self.invite(external_address, ["Denmark"]),
            "Some emails did not validate, so we didn't send any invitations.",
        )

    def test_invite_outside_domain_in_open_realm(self) -> None:
        """
        In a realm with `emails_restricted_to_domains = False`, you can invite people
        with a different domain from that of the realm or your e-mail address.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo@example.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

    def test_invite_outside_domain_before_closing(self) -> None:
        """
        If you invite someone with a different domain from that of the realm
        when `emails_restricted_to_domains = False`, but `emails_restricted_to_domains` later
        changes to true, the invitation should succeed but the invitee's signup
        attempt should fail.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo@example.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

        zulip_realm.emails_restricted_to_domains = True
        zulip_realm.save()

        result = self.submit_reg_form_for_user("foo@example.com", "password")
        self.assertEqual(result.status_code, 400)
        self.assert_in_response(
            "does not allow signups using emails with your email domain", result
        )

    def test_disposable_emails_before_closing(self) -> None:
        """
        If you invite someone with a disposable email when
        `disallow_disposable_email_addresses = False`, but
        later changes to true, the invitation should succeed
        but the invitee's signup attempt should fail.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.disallow_disposable_email_addresses = False
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo@mailnator.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

        zulip_realm.disallow_disposable_email_addresses = True
        zulip_realm.save()

        result = self.submit_reg_form_for_user("foo@mailnator.com", "password")
        self.assertEqual(result.status_code, 400)
        self.assert_in_response("does not allow signups using disposable email addresses.", result)

    def test_invite_with_email_containing_plus_before_closing(self) -> None:
        """
        If you invite someone with an email containing plus when
        `emails_restricted_to_domains = False`, but later change
        `emails_restricted_to_domains = True`, the invitation should
        succeed but the invitee's signup attempt should fail as
        users are not allowed to sign up using email containing +
        when the realm is restricted to domain.
        """
        zulip_realm = get_realm("zulip")
        zulip_realm.emails_restricted_to_domains = False
        zulip_realm.save()

        self.login("hamlet")
        external_address = "foo+label@zulip.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

        zulip_realm.emails_restricted_to_domains = True
        zulip_realm.save()

        result = self.submit_reg_form_for_user(external_address, "password")
        self.assertEqual(result.status_code, 400)
        self.assert_in_response('does not allow signups using emails that contain "+".', result)

    def test_invalid_email_check_after_confirming_email(self) -> None:
        self.login("hamlet")
        email = "test@zulip.com"

        self.assert_json_success(self.invite(email, ["Denmark"]))

        obj = Confirmation.objects.get(confirmation_key=find_key_by_email(email))
        prereg_user = obj.content_object
        assert prereg_user is not None
        prereg_user.email = "invalid.email"
        prereg_user.save()

        result = self.submit_reg_form_for_user(email, "password")
        self.assertEqual(result.status_code, 400)
        self.assert_in_response(
            "The email address you are trying to sign up with is not valid", result
        )

    def test_invite_with_non_ascii_streams(self) -> None:
        """
        Inviting someone to streams with non-ASCII characters succeeds.
        """
        self.login("hamlet")
        invitee = "alice-test@zulip.com"

        stream_name = "hÃ¼mbÃ¼Çµ"

        # Make sure we're subscribed before inviting someone.
        self.subscribe(self.example_user("hamlet"), stream_name)

        self.assert_json_success(self.invite(invitee, [stream_name]))

    def test_invite_without_permission_to_subscribe_others(self) -> None:
        realm = get_realm("zulip")
        do_set_realm_property(
            realm, "invite_to_stream_policy", Realm.POLICY_ADMINS_ONLY, acting_user=None
        )

        invitee = self.nonreg_email("alice")

        self.login("hamlet")
        result = self.invite(invitee, ["Denmark", "Scotland"])
        self.assert_json_error(
            result, "You do not have permission to subscribe other users to channels."
        )

        result = self.invite(invitee, [])
        self.assert_json_success(result)
        self.check_sent_emails([invitee])
        mail.outbox.pop()

        self.login("iago")
        invitee = self.nonreg_email("bob")
        result = self.invite(invitee, ["Denmark", "Scotland"])
        self.assert_json_success(result)
        self.check_sent_emails([invitee])
        mail.outbox.pop()

        do_set_realm_property(
            realm, "invite_to_stream_policy", Realm.POLICY_MEMBERS_ONLY, acting_user=None
        )
        self.login("hamlet")
        invitee = self.nonreg_email("test")
        result = self.invite(invitee, ["Denmark", "Scotland"])
        self.assert_json_success(result)
        self.check_sent_emails([invitee])

    def test_invitation_reminder_email(self) -> None:
        # All users belong to zulip realm
        referrer_name = "hamlet"
        current_user = self.example_user(referrer_name)
        self.login_user(current_user)
        invitee_email = self.nonreg_email("alice")
        self.assert_json_success(self.invite(invitee_email, ["Denmark"]))
        self.assertTrue(find_key_by_email(invitee_email))
        self.check_sent_emails([invitee_email])

        data = {"email": invitee_email, "referrer_email": current_user.email}
        invitee = PreregistrationUser.objects.get(email=data["email"])
        referrer = self.example_user(referrer_name)
        validity_in_minutes = 2 * 24 * 60
        link = create_confirmation_link(
            invitee, Confirmation.INVITATION, validity_in_minutes=validity_in_minutes
        )
        context = common_context(referrer)
        context.update(
            activate_url=link,
            referrer_name=referrer.full_name,
            referrer_email=referrer.email,
            referrer_realm_name=referrer.realm.name,
        )
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
            email = data["email"]
            send_future_email(
                "zerver/emails/invitation_reminder",
                referrer.realm,
                to_emails=[email],
                from_address=FromAddress.no_reply_placeholder,
                context=context,
            )
        email_jobs_to_deliver = ScheduledEmail.objects.filter(
            scheduled_timestamp__lte=timezone_now()
        )
        self.assert_length(email_jobs_to_deliver, 1)
        email_count = len(mail.outbox)
        for job in email_jobs_to_deliver:
            deliver_scheduled_emails(job)
        self.assert_length(mail.outbox, email_count + 1)
        self.assertEqual(self.email_envelope_from(mail.outbox[-1]), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertIn(FromAddress.NOREPLY, self.email_display_from(mail.outbox[-1]))

        # Now verify that signing up clears invite_reminder emails
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
            email = data["email"]
            send_future_email(
                "zerver/emails/invitation_reminder",
                referrer.realm,
                to_emails=[email],
                from_address=FromAddress.no_reply_placeholder,
                context=context,
            )

        email_jobs_to_deliver = ScheduledEmail.objects.filter(
            scheduled_timestamp__lte=timezone_now(), type=ScheduledEmail.INVITATION_REMINDER
        )
        self.assert_length(email_jobs_to_deliver, 1)

        self.register(invitee_email, "test")
        email_jobs_to_deliver = ScheduledEmail.objects.filter(
            scheduled_timestamp__lte=timezone_now(), type=ScheduledEmail.INVITATION_REMINDER
        )
        self.assert_length(email_jobs_to_deliver, 0)

    def test_no_invitation_reminder_when_link_expires_quickly(self) -> None:
        self.login("hamlet")
        # Check invitation reminder email is scheduled with 4 day link expiry
        self.invite("alice@zulip.com", ["Denmark"], invite_expires_in_minutes=4 * 24 * 60)
        self.assertEqual(
            ScheduledEmail.objects.filter(
                address="alice@zulip.com", type=ScheduledEmail.INVITATION_REMINDER
            ).count(),
            1,
        )
        # Check invitation reminder email is not scheduled with 3 day link expiry
        self.invite("bob@zulip.com", ["Denmark"], invite_expires_in_minutes=3 * 24 * 60)
        self.assertEqual(
            ScheduledEmail.objects.filter(
                address="bob@zulip.com", type=ScheduledEmail.INVITATION_REMINDER
            ).count(),
            0,
        )

    # make sure users can't take a valid confirmation key from another
    # pathway and use it with the invitation URL route
    def test_confirmation_key_of_wrong_type(self) -> None:
        email = self.nonreg_email("alice")
        realm = get_realm("zulip")
        inviter = self.example_user("iago")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        url = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        registration_key = url.split("/")[-1]

        # Mainly a test of get_object_from_key, rather than of the invitation pathway
        with self.assertRaises(ConfirmationKeyError) as cm:
            get_object_from_key(registration_key, [Confirmation.INVITATION], mark_object_used=True)
        self.assertEqual(cm.exception.error_type, ConfirmationKeyError.DOES_NOT_EXIST)

        # Verify that using the wrong type doesn't work in the main confirm code path
        email_change_url = create_confirmation_link(prereg_user, Confirmation.EMAIL_CHANGE)
        email_change_key = email_change_url.split("/")[-1]
        result = self.client_post("/accounts/register/", {"key": email_change_key})
        self.assertEqual(result.status_code, 404)
        self.assert_in_response(
            "Whoops. We couldn't find your confirmation link in the system.", result
        )

    def test_confirmation_expired(self) -> None:
        email = self.nonreg_email("alice")
        realm = get_realm("zulip")
        inviter = self.example_user("iago")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        date_sent = timezone_now() - timedelta(weeks=3)
        with time_machine.travel(date_sent, tick=False):
            url = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)

        key = url.split("/")[-1]
        confirmation_link_path = "/" + url.split("/", 3)[3]
        # Both the confirmation link and submitting the key to the registration endpoint
        # directly will return the appropriate error.
        result = self.client_get(confirmation_link_path)
        self.assertEqual(result.status_code, 404)
        self.assert_in_response(
            "Whoops. The confirmation link has expired or been deactivated.", result
        )

        result = self.client_post("/accounts/register/", {"key": key})
        self.assertEqual(result.status_code, 404)
        self.assert_in_response(
            "Whoops. The confirmation link has expired or been deactivated.", result
        )

    def test_never_expire_confirmation_object(self) -> None:
        email = self.nonreg_email("alice")
        realm = get_realm("zulip")
        inviter = self.example_user("iago")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        activation_url = create_confirmation_link(
            prereg_user, Confirmation.INVITATION, validity_in_minutes=None
        )
        confirmation = Confirmation.objects.last()
        assert confirmation is not None
        self.assertEqual(confirmation.expiry_date, None)
        activation_key = activation_url.split("/")[-1]
        response = self.client_post(
            "/accounts/register/",
            {"key": activation_key, "from_confirmation": 1, "full_nme": "alice"},
        )
        self.assertEqual(response.status_code, 200)

    def test_send_more_than_one_invite_to_same_user(self) -> None:
        self.user_profile = self.example_user("iago")
        streams = [
            get_stream(stream_name, self.user_profile.realm)
            for stream_name in ["Denmark", "Scotland"]
        ]

        invite_expires_in_minutes = 2 * 24 * 60
        with self.captureOnCommitCallbacks(execute=True):
            do_invite_users(
                self.user_profile,
                ["foo@zulip.com"],
                streams,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
        prereg_user = PreregistrationUser.objects.get(email="foo@zulip.com")
        with self.captureOnCommitCallbacks(execute=True):
            do_invite_users(
                self.user_profile,
                ["foo@zulip.com"],
                streams,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
            do_invite_users(
                self.user_profile,
                ["foo@zulip.com"],
                streams,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )

        # Also send an invite from a different realm.
        lear = get_realm("lear")
        lear_user = self.lear_user("cordelia")
        with self.captureOnCommitCallbacks(execute=True):
            do_invite_users(
                lear_user,
                ["foo@zulip.com"],
                [],
                invite_expires_in_minutes=invite_expires_in_minutes,
            )

        invites = PreregistrationUser.objects.filter(email__iexact="foo@zulip.com")
        self.assert_length(invites, 4)

        created_user = do_create_user(
            "foo@zulip.com",
            "password",
            self.user_profile.realm,
            "full name",
            prereg_user=prereg_user,
            acting_user=None,
        )

        accepted_invite = PreregistrationUser.objects.filter(
            email__iexact="foo@zulip.com", status=confirmation_settings.STATUS_USED
        )
        revoked_invites = PreregistrationUser.objects.filter(
            email__iexact="foo@zulip.com", status=confirmation_settings.STATUS_REVOKED
        )
        # If a user was invited more than once, when it accepts one invite and register
        # the others must be canceled.
        self.assert_length(accepted_invite, 1)
        self.assertEqual(accepted_invite[0].id, prereg_user.id)
        self.assertEqual(accepted_invite[0].created_user, created_user)

        expected_revoked_invites = set(invites.exclude(id=prereg_user.id).exclude(realm=lear))
        self.assertEqual(set(revoked_invites), expected_revoked_invites)

        self.assertEqual(
            PreregistrationUser.objects.get(email__iexact="foo@zulip.com", realm=lear).status, 0
        )

        with self.assertRaises(AssertionError):
            process_new_human_user(created_user, prereg_user)

    def test_confirmation_obj_not_exist_error(self) -> None:
        """Since the key is a param input by the user to the registration endpoint,
        if it inserts an invalid value, the confirmation object won't be found. This
        tests if, in that scenario, we handle the exception by redirecting the user to
        the link_expired page.
        """
        email = self.nonreg_email("alice")
        password = "password"
        realm = get_realm("zulip")
        inviter = self.example_user("iago")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)

        registration_key = "invalid_confirmation_key"
        url = "/accounts/register/"
        response = self.client_post(
            url, {"key": registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        self.assertEqual(response.status_code, 404)
        self.assert_in_response(
            "Whoops. We couldn't find your confirmation link in the system.", response
        )

        registration_key = confirmation_link.split("/")[-1]
        response = self.client_post(
            url, {"key": registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        self.assert_in_success_response(
            ["Enter your account details to complete registration."], response
        )
        response = self.submit_reg_form_for_user(email, password, key=registration_key)
        self.assertEqual(response.status_code, 302)

    def test_validate_email_not_already_in_realm(self) -> None:
        email = self.nonreg_email("alice")
        password = "password"
        realm = get_realm("zulip")
        inviter = self.example_user("iago")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )

        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        registration_key = confirmation_link.split("/")[-1]

        url = "/accounts/register/"
        self.client_post(
            url, {"key": registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        self.submit_reg_form_for_user(email, password, key=registration_key)

        new_prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        new_confirmation_link = create_confirmation_link(
            new_prereg_user, Confirmation.USER_REGISTRATION
        )
        new_registration_key = new_confirmation_link.split("/")[-1]
        url = "/accounts/register/"
        response = self.client_post(
            url, {"key": new_registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("login") + "?" + urlencode({"email": email, "already_registered": 1}),
        )

    def test_confirmation_key_cant_be_reused(self) -> None:
        email = self.nonreg_email("alice")
        password = "password"
        realm = get_realm("zulip")
        inviter = self.example_user("iago")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )

        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        registration_key = confirmation_link.split("/")[-1]

        url = "/accounts/register/"
        self.client_post(
            url, {"key": registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        self.submit_reg_form_for_user(email, password, key=registration_key)

        prereg_user.refresh_from_db()
        self.assertIsNotNone(prereg_user.created_user)

        # Now attempt to reuse the same key.
        result = self.client_post("/accounts/register/", {"key": registration_key})
        self.assertEqual(result.status_code, 404)
        self.assert_in_response(
            "Whoops. The confirmation link has expired or been deactivated.", result
        )

    def test_confirmation_link_in_manual_license_plan(self) -> None:
        inviter = self.example_user("iago")
        realm = get_realm("zulip")

        email = self.nonreg_email("alice")
        realm = get_realm("zulip")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        registration_key = confirmation_link.split("/")[-1]
        url = "/accounts/register/"
        self.client_post(
            url, {"key": registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        response = self.submit_reg_form_for_user(email, "password", key=registration_key)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://zulip.testserver/")

        # We want to simulate the organization having exactly all their licenses
        # used, to verify that joining as a regular user is not allowed,
        # but as a guest still works (guests are free up to a certain number).
        current_seat_count = get_latest_seat_count(realm)
        self.subscribe_realm_to_monthly_plan_on_manual_license_management(
            realm, current_seat_count, current_seat_count
        )

        email = self.nonreg_email("bob")
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )
        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        registration_key = confirmation_link.split("/")[-1]
        url = "/accounts/register/"
        self.client_post(url, {"key": registration_key, "from_confirmation": 1, "full_name": "bob"})
        response = self.submit_reg_form_for_user(email, "password", key=registration_key)
        self.assert_in_success_response(
            ["Organization cannot accept new members right now"], response
        )

        guest_prereg_user = PreregistrationUser.objects.create(
            email=email,
            referred_by=inviter,
            realm=realm,
            invited_as=PreregistrationUser.INVITE_AS["GUEST_USER"],
        )
        confirmation_link = create_confirmation_link(
            guest_prereg_user, Confirmation.USER_REGISTRATION
        )
        registration_key = confirmation_link.split("/")[-1]
        url = "/accounts/register/"

        self.client_post(
            url, {"key": registration_key, "from_confirmation": 1, "full_name": "alice"}
        )
        response = self.submit_reg_form_for_user(email, "password", key=registration_key)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://zulip.testserver/")


class InvitationsTestCase(InviteUserBase):
    def test_do_get_invites_controlled_by_user(self) -> None:
        user_profile = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        streams = [
            get_stream(stream_name, user_profile.realm) for stream_name in ["Denmark", "Scotland"]
        ]

        invite_expires_in_minutes = 2 * 24 * 60
        with self.captureOnCommitCallbacks(execute=True):
            do_invite_users(
                user_profile,
                ["TestOne@zulip.com"],
                streams,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
            do_invite_users(
                user_profile,
                ["TestTwo@zulip.com"],
                streams,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
            do_invite_users(
                hamlet,
                ["TestThree@zulip.com"],
                streams,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
            do_invite_users(
                othello,
                ["TestFour@zulip.com"],
                streams,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
            do_invite_users(
                self.mit_user("sipbtest"),
                ["TestOne@mit.edu"],
                [],
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
        do_create_multiuse_invite_link(
            user_profile, PreregistrationUser.INVITE_AS["MEMBER"], invite_expires_in_minutes
        )
        do_create_multiuse_invite_link(
            hamlet, PreregistrationUser.INVITE_AS["MEMBER"], invite_expires_in_minutes
        )
        self.assert_length(do_get_invites_controlled_by_user(user_profile), 6)
        self.assert_length(do_get_invites_controlled_by_user(hamlet), 2)
        self.assert_length(do_get_invites_controlled_by_user(othello), 1)

    def test_successful_get_open_invitations(self) -> None:
        """
        A GET call to /json/invites returns all unexpired invitations.
        """
        active_value = getattr(confirmation_settings, "STATUS_USED", "Wrong")
        self.assertNotEqual(active_value, "Wrong")

        self.login("iago")
        user_profile = self.example_user("iago")
        self.login_user(user_profile)

        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        streams = [
            get_stream(stream_name, user_profile.realm) for stream_name in ["Denmark", "Scotland"]
        ]

        invite_expires_in_minutes = 2 * 24 * 60
        with self.captureOnCommitCallbacks(execute=True):
            do_invite_users(
                user_profile,
                ["TestOne@zulip.com"],
                streams,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )

        with time_machine.travel(
            (timezone_now() - timedelta(days=3)), tick=False
        ), self.captureOnCommitCallbacks(execute=True):
            do_invite_users(
                user_profile,
                ["TestTwo@zulip.com"],
                streams,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
            do_create_multiuse_invite_link(
                othello, PreregistrationUser.INVITE_AS["MEMBER"], invite_expires_in_minutes
            )

        prereg_user_three = PreregistrationUser(
            email="TestThree@zulip.com", referred_by=user_profile, status=active_value
        )
        prereg_user_three.save()
        create_confirmation_link(
            prereg_user_three,
            Confirmation.INVITATION,
            validity_in_minutes=invite_expires_in_minutes,
        )

        do_create_multiuse_invite_link(
            hamlet, PreregistrationUser.INVITE_AS["MEMBER"], invite_expires_in_minutes
        )

        result = self.client_get("/json/invites")
        self.assertEqual(result.status_code, 200)
        invites = orjson.loads(result.content)["invites"]
        self.assert_length(invites, 2)

        self.assertFalse(invites[0]["is_multiuse"])
        self.assertEqual(invites[0]["email"], "TestOne@zulip.com")
        self.assertTrue(invites[1]["is_multiuse"])
        self.assertEqual(invites[1]["invited_by_user_id"], hamlet.id)

    def test_get_never_expiring_invitations(self) -> None:
        self.login("iago")
        user_profile = self.example_user("iago")

        streams = [
            get_stream(stream_name, user_profile.realm) for stream_name in ["Denmark", "Scotland"]
        ]

        with time_machine.travel(
            (timezone_now() - timedelta(days=1000)), tick=False
        ), self.captureOnCommitCallbacks(execute=True):
            # Testing the invitation with expiry date set to "None" exists
            # after a large amount of days.
            do_invite_users(
                user_profile,
                ["TestOne@zulip.com"],
                streams,
                invite_expires_in_minutes=None,
            )
            do_invite_users(
                user_profile,
                ["TestTwo@zulip.com"],
                streams,
                invite_expires_in_minutes=100 * 24 * 60,
            )
            do_create_multiuse_invite_link(
                user_profile, PreregistrationUser.INVITE_AS["MEMBER"], None
            )
            do_create_multiuse_invite_link(
                user_profile, PreregistrationUser.INVITE_AS["MEMBER"], 100
            )

        result = self.client_get("/json/invites")
        self.assertEqual(result.status_code, 200)
        invites = orjson.loads(result.content)["invites"]
        # We only get invitations that will never expire because we have mocked time such
        # that the other invitations are created in the deep past.
        self.assert_length(invites, 2)

        self.assertFalse(invites[0]["is_multiuse"])
        self.assertEqual(invites[0]["email"], "TestOne@zulip.com")
        self.assertEqual(invites[0]["expiry_date"], None)
        self.assertTrue(invites[1]["is_multiuse"])
        self.assertEqual(invites[1]["invited_by_user_id"], user_profile.id)
        self.assertEqual(invites[1]["expiry_date"], None)

    def test_successful_delete_invitation(self) -> None:
        """
        A DELETE call to /json/invites/<ID> should delete the invite and
        any scheduled invitation reminder emails.
        """
        self.login("iago")

        invitee = "DeleteMe@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        prereg_user = PreregistrationUser.objects.get(email=invitee)

        # Verify that the scheduled email exists.
        ScheduledEmail.objects.get(address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER)

        result = self.client_delete("/json/invites/" + str(prereg_user.id))
        self.assertEqual(result.status_code, 200)
        error_result = self.client_delete("/json/invites/" + str(prereg_user.id))
        self.assert_json_error(error_result, "No such invitation")

        self.assertRaises(
            ScheduledEmail.DoesNotExist,
            lambda: ScheduledEmail.objects.get(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ),
        )

    def test_successful_member_delete_invitation(self) -> None:
        """
        A DELETE call from member account to /json/invites/<ID> should delete the invite and
        any scheduled invitation reminder emails.
        """
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        invitee = "DeleteMe@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))

        # Verify that the scheduled email exists.
        prereg_user = PreregistrationUser.objects.get(email=invitee, referred_by=user_profile)
        ScheduledEmail.objects.get(address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER)

        # Verify another non-admin can't delete
        result = self.api_delete(
            self.example_user("othello"), "/api/v1/invites/" + str(prereg_user.id)
        )
        self.assert_json_error(result, "Must be an organization administrator")

        # Verify that the scheduled email still exists.
        prereg_user = PreregistrationUser.objects.get(email=invitee, referred_by=user_profile)
        ScheduledEmail.objects.get(address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER)

        # Verify deletion works.
        result = self.api_delete(user_profile, "/api/v1/invites/" + str(prereg_user.id))
        self.assertEqual(result.status_code, 200)

        result = self.api_delete(user_profile, "/api/v1/invites/" + str(prereg_user.id))
        self.assert_json_error(result, "No such invitation")

        self.assertRaises(
            ScheduledEmail.DoesNotExist,
            lambda: ScheduledEmail.objects.get(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ),
        )

    def test_delete_owner_invitation(self) -> None:
        self.login("desdemona")
        owner = self.example_user("desdemona")

        invitee = "DeleteMe@zulip.com"
        self.assert_json_success(
            self.invite(
                invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_OWNER"]
            )
        )
        prereg_user = PreregistrationUser.objects.get(email=invitee)
        result = self.api_delete(
            self.example_user("iago"), "/api/v1/invites/" + str(prereg_user.id)
        )
        self.assert_json_error(result, "Must be an organization owner")

        result = self.api_delete(owner, "/api/v1/invites/" + str(prereg_user.id))
        self.assert_json_success(result)
        result = self.api_delete(owner, "/api/v1/invites/" + str(prereg_user.id))
        self.assert_json_error(result, "No such invitation")
        self.assertRaises(
            ScheduledEmail.DoesNotExist,
            lambda: ScheduledEmail.objects.get(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ),
        )

    def test_delete_multiuse_invite(self) -> None:
        """
        A DELETE call to /json/invites/multiuse<ID> should delete the
        multiuse_invite.
        """
        self.login("iago")

        zulip_realm = get_realm("zulip")
        multiuse_invite = MultiuseInvite.objects.create(
            referred_by=self.example_user("hamlet"), realm=zulip_realm
        )
        validity_in_minutes = 2 * 24 * 60
        create_confirmation_link(
            multiuse_invite, Confirmation.MULTIUSE_INVITE, validity_in_minutes=validity_in_minutes
        )
        result = self.client_delete("/json/invites/multiuse/" + str(multiuse_invite.id))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            MultiuseInvite.objects.get(id=multiuse_invite.id).status,
            confirmation_settings.STATUS_REVOKED,
        )
        # Test that trying to double-delete fails
        error_result = self.client_delete("/json/invites/multiuse/" + str(multiuse_invite.id))
        self.assert_json_error(error_result, "Invitation has already been revoked")

        # Test deleting owner multiuse_invite.
        multiuse_invite = MultiuseInvite.objects.create(
            referred_by=self.example_user("desdemona"),
            realm=zulip_realm,
            invited_as=PreregistrationUser.INVITE_AS["REALM_OWNER"],
        )
        validity_in_minutes = 2
        create_confirmation_link(
            multiuse_invite, Confirmation.MULTIUSE_INVITE, validity_in_minutes=validity_in_minutes
        )
        error_result = self.client_delete("/json/invites/multiuse/" + str(multiuse_invite.id))
        self.assert_json_error(error_result, "Must be an organization owner")

        self.login("desdemona")
        result = self.client_delete("/json/invites/multiuse/" + str(multiuse_invite.id))
        self.assert_json_success(result)
        self.assertEqual(
            MultiuseInvite.objects.get(id=multiuse_invite.id).status,
            confirmation_settings.STATUS_REVOKED,
        )

        # Test non-admins can only delete invitations created by them.
        multiuse_invite = MultiuseInvite.objects.create(
            referred_by=self.example_user("hamlet"), realm=zulip_realm
        )
        create_confirmation_link(
            multiuse_invite, Confirmation.MULTIUSE_INVITE, validity_in_minutes=validity_in_minutes
        )

        self.login("cordelia")
        error_result = self.client_delete("/json/invites/multiuse/" + str(multiuse_invite.id))
        self.assert_json_error(error_result, "Must be an organization administrator")

        self.login("hamlet")
        result = self.client_delete("/json/invites/multiuse/" + str(multiuse_invite.id))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            MultiuseInvite.objects.get(id=multiuse_invite.id).status,
            confirmation_settings.STATUS_REVOKED,
        )

        # Test deleting multiuse invite from another realm
        mit_realm = get_realm("zephyr")
        multiuse_invite_in_mit = MultiuseInvite.objects.create(
            referred_by=self.mit_user("sipbtest"), realm=mit_realm
        )
        validity_in_minutes = 2 * 24 * 60
        create_confirmation_link(
            multiuse_invite_in_mit,
            Confirmation.MULTIUSE_INVITE,
            validity_in_minutes=validity_in_minutes,
        )
        error_result = self.client_delete(
            "/json/invites/multiuse/" + str(multiuse_invite_in_mit.id)
        )
        self.assert_json_error(error_result, "No such invitation")

        non_existent_id = MultiuseInvite.objects.count() + 9999
        error_result = self.client_delete(f"/json/invites/multiuse/{non_existent_id}")
        self.assert_json_error(error_result, "No such invitation")

    def test_successful_resend_invitation(self) -> None:
        """
        A POST call to /json/invites/<ID>/resend should send an invitation reminder email
        and delete any scheduled invitation reminder email.
        """
        self.login("iago")
        invitee = "resend_me@zulip.com"

        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        prereg_user = PreregistrationUser.objects.get(email=invitee)

        # Verify and then clear from the outbox the original invite email
        self.check_sent_emails([invitee])
        mail.outbox.pop()

        # Verify that the scheduled email exists.
        scheduledemail_filter = ScheduledEmail.objects.filter(
            address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
        )
        self.assertEqual(scheduledemail_filter.count(), 1)
        original_timestamp = scheduledemail_filter.values_list("scheduled_timestamp", flat=True)

        # Resend invite
        with self.captureOnCommitCallbacks(execute=True):
            result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assertEqual(
            ScheduledEmail.objects.filter(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ).count(),
            1,
        )

        # Check that we have exactly one scheduled email, and that it is different
        self.assertEqual(scheduledemail_filter.count(), 1)
        self.assertNotEqual(
            original_timestamp, scheduledemail_filter.values_list("scheduled_timestamp", flat=True)
        )

        self.assertEqual(result.status_code, 200)
        error_result = self.client_post("/json/invites/" + str(9999) + "/resend")
        self.assert_json_error(error_result, "No such invitation")

        self.check_sent_emails([invitee])

    def test_successful_member_resend_invitation(self) -> None:
        """A POST call from member a account to /json/invites/<ID>/resend
        should send an invitation reminder email and delete any
        scheduled invitation reminder email if they send the invite.
        """
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
        invitee = "resend_me@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        # Verify hamlet has only one invitation (Member can resend invitations only sent by him).
        invitation = PreregistrationUser.objects.filter(referred_by=user_profile)
        self.assert_length(invitation, 1)
        prereg_user = PreregistrationUser.objects.get(email=invitee)

        # Verify and then clear from the outbox the original invite email
        self.check_sent_emails([invitee])
        mail.outbox.pop()

        # Verify that the scheduled email exists.
        scheduledemail_filter = ScheduledEmail.objects.filter(
            address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
        )
        self.assertEqual(scheduledemail_filter.count(), 1)
        original_timestamp = scheduledemail_filter.values_list("scheduled_timestamp", flat=True)

        # Resend invite
        with self.captureOnCommitCallbacks(execute=True):
            result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assertEqual(
            ScheduledEmail.objects.filter(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ).count(),
            1,
        )

        # Check that we have exactly one scheduled email, and that it is different
        self.assertEqual(scheduledemail_filter.count(), 1)
        self.assertNotEqual(
            original_timestamp, scheduledemail_filter.values_list("scheduled_timestamp", flat=True)
        )

        self.assertEqual(result.status_code, 200)
        error_result = self.client_post("/json/invites/" + str(9999) + "/resend")
        self.assert_json_error(error_result, "No such invitation")

        self.check_sent_emails([invitee])

        self.logout()
        self.login("othello")
        invitee = "TestOne@zulip.com"
        prereg_user_one = PreregistrationUser(email=invitee, referred_by=user_profile)
        prereg_user_one.save()
        prereg_user = PreregistrationUser.objects.get(email=invitee)
        error_result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assert_json_error(error_result, "Must be an organization administrator")

    def test_resend_owner_invitation(self) -> None:
        self.login("desdemona")

        invitee = "resend_owner@zulip.com"
        self.assert_json_success(
            self.invite(
                invitee, ["Denmark"], invite_as=PreregistrationUser.INVITE_AS["REALM_OWNER"]
            )
        )
        self.check_sent_emails([invitee])
        scheduledemail_filter = ScheduledEmail.objects.filter(
            address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
        )
        self.assertEqual(scheduledemail_filter.count(), 1)
        original_timestamp = scheduledemail_filter.values_list("scheduled_timestamp", flat=True)

        # Test only organization owners can resend owner invitation.
        self.login("iago")
        prereg_user = PreregistrationUser.objects.get(email=invitee)
        error_result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assert_json_error(error_result, "Must be an organization owner")

        self.login("desdemona")
        with self.captureOnCommitCallbacks(execute=True):
            result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assert_json_success(result)

        self.assertEqual(
            ScheduledEmail.objects.filter(
                address__iexact=invitee, type=ScheduledEmail.INVITATION_REMINDER
            ).count(),
            1,
        )

        # Check that we have exactly one scheduled email, and that it is different
        self.assertEqual(scheduledemail_filter.count(), 1)
        self.assertNotEqual(
            original_timestamp, scheduledemail_filter.values_list("scheduled_timestamp", flat=True)
        )

    def test_resend_never_expiring_invitation(self) -> None:
        self.login("iago")
        invitee = "resend@zulip.com"

        self.assert_json_success(self.invite(invitee, ["Denmark"], None))
        prereg_user = PreregistrationUser.objects.get(email=invitee)

        # Verify and then clear from the outbox the original invite email
        self.check_sent_emails([invitee])
        mail.outbox.pop()

        with self.captureOnCommitCallbacks(execute=True):
            result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assert_json_success(result)
        self.check_sent_emails([invitee])

    def test_accessing_invites_in_another_realm(self) -> None:
        inviter = UserProfile.objects.exclude(realm=get_realm("zulip")).first()
        assert inviter is not None
        prereg_user = PreregistrationUser.objects.create(
            email="email", referred_by=inviter, realm=inviter.realm
        )
        self.login("iago")
        error_result = self.client_post("/json/invites/" + str(prereg_user.id) + "/resend")
        self.assert_json_error(error_result, "No such invitation")
        error_result = self.client_delete("/json/invites/" + str(prereg_user.id))
        self.assert_json_error(error_result, "No such invitation")

    def test_prereg_user_status(self) -> None:
        email = self.nonreg_email("alice")
        password = "password"
        realm = get_realm("zulip")

        inviter = UserProfile.objects.filter(realm=realm).first()
        prereg_user = PreregistrationUser.objects.create(
            email=email, referred_by=inviter, realm=realm
        )

        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        registration_key = confirmation_link.split("/")[-1]

        result = self.client_post(
            "/accounts/register/",
            {"key": registration_key, "from_confirmation": "1", "full_name": "alice"},
        )
        self.assertEqual(result.status_code, 200)
        confirmation = Confirmation.objects.get(confirmation_key=registration_key)
        assert confirmation.content_object is not None
        prereg_user = confirmation.content_object
        self.assertEqual(prereg_user.status, 0)

        result = self.submit_reg_form_for_user(email, password, key=registration_key)
        self.assertEqual(result.status_code, 302)
        prereg_user = PreregistrationUser.objects.get(email=email, referred_by=inviter, realm=realm)
        self.assertEqual(prereg_user.status, confirmation_settings.STATUS_USED)
        user = get_user_by_delivery_email(email, realm)
        self.assertIsNotNone(user)
        self.assertEqual(user.delivery_email, email)


class InviteeEmailsParserTests(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.email1 = "email1@zulip.com"
        self.email2 = "email2@zulip.com"
        self.email3 = "email3@zulip.com"

    def test_if_emails_separated_by_commas_are_parsed_and_striped_correctly(self) -> None:
        emails_raw = f"{self.email1} ,{self.email2}, {self.email3}"
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_separated_by_newlines_are_parsed_and_striped_correctly(self) -> None:
        emails_raw = f"{self.email1}\n {self.email2}\n {self.email3} "
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_from_email_client_separated_by_newlines_are_parsed_correctly(self) -> None:
        emails_raw = (
            f"Email One <{self.email1}>\nEmailTwo<{self.email2}>\nEmail Three<{self.email3}>"
        )
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)

    def test_if_emails_in_mixed_style_are_parsed_correctly(self) -> None:
        emails_raw = f"Email One <{self.email1}>,EmailTwo<{self.email2}>\n{self.email3}"
        expected_set = {self.email1, self.email2, self.email3}
        self.assertEqual(get_invitee_emails_set(emails_raw), expected_set)


class MultiuseInviteTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm("zulip")
        self.realm.invite_required = True
        self.realm.save()

    def generate_multiuse_invite_link(
        self, streams: Optional[List[Stream]] = None, date_sent: Optional[datetime] = None
    ) -> str:
        invite = MultiuseInvite(realm=self.realm, referred_by=self.example_user("iago"))
        invite.save()

        if streams is not None:
            invite.streams.set(streams)

        if date_sent is None:
            date_sent = timezone_now()
        validity_in_minutes = 2 * 24 * 60
        with time_machine.travel(date_sent, tick=False):
            return create_confirmation_link(
                invite, Confirmation.MULTIUSE_INVITE, validity_in_minutes=validity_in_minutes
            )

    def check_user_able_to_register(self, email: str, invite_link: str) -> None:
        password = "password"

        result = self.client_post(invite_link, {"email": email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(f"/accounts/send_confirm/?email={quote(email)}")
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(email, password)
        self.assertEqual(result.status_code, 302)

        # Verify the PreregistrationUser object was set up as expected.
        prereg_user = PreregistrationUser.objects.last()
        multiuse_invite = MultiuseInvite.objects.last()

        assert prereg_user is not None
        self.assertEqual(prereg_user.email, email)
        self.assertEqual(prereg_user.multiuse_invite, multiuse_invite)

        mail.outbox.pop()

    def test_valid_multiuse_link(self) -> None:
        email1 = self.nonreg_email("test")
        email2 = self.nonreg_email("test1")
        email3 = self.nonreg_email("alice")

        date_sent = timezone_now() - timedelta(days=1)
        invite_link = self.generate_multiuse_invite_link(date_sent=date_sent)

        self.check_user_able_to_register(email1, invite_link)
        self.check_user_able_to_register(email2, invite_link)
        self.check_user_able_to_register(email3, invite_link)

    def test_expired_multiuse_link(self) -> None:
        email = self.nonreg_email("newuser")
        date_sent = timezone_now() - timedelta(days=settings.INVITATION_LINK_VALIDITY_DAYS + 1)
        invite_link = self.generate_multiuse_invite_link(date_sent=date_sent)
        result = self.client_post(invite_link, {"email": email})

        self.assertEqual(result.status_code, 404)
        self.assert_in_response("The confirmation link has expired or been deactivated.", result)

    def test_revoked_multiuse_link(self) -> None:
        email = self.nonreg_email("newuser")
        invite_link = self.generate_multiuse_invite_link()
        multiuse_invite = MultiuseInvite.objects.last()
        assert multiuse_invite is not None
        do_revoke_multi_use_invite(multiuse_invite)

        result = self.client_post(invite_link, {"email": email})

        self.assertEqual(result.status_code, 404)
        self.assert_in_response("We couldn't find your confirmation link in the system.", result)

    def test_invalid_multiuse_link(self) -> None:
        email = self.nonreg_email("newuser")
        invite_link = "/join/invalid_key/"
        result = self.client_post(invite_link, {"email": email})

        self.assertEqual(result.status_code, 404)
        self.assert_in_response("Whoops. The confirmation link is malformed.", result)

    def test_invalid_multiuse_link_in_open_realm(self) -> None:
        self.realm.invite_required = False
        self.realm.save()

        email = self.nonreg_email("newuser")
        invite_link = "/join/invalid_key/"

        with patch("zerver.views.registration.get_realm_from_request", return_value=self.realm):
            with patch("zerver.views.registration.get_realm", return_value=self.realm):
                self.check_user_able_to_register(email, invite_link)

    def test_multiuse_link_with_specified_streams(self) -> None:
        name1 = "newuser"
        name2 = "bob"
        name3 = "alice"
        email1 = self.nonreg_email(name1)
        email2 = self.nonreg_email(name2)
        email3 = self.nonreg_email(name3)

        stream_names = ["Rome", "Scotland", "Venice"]
        streams = [get_stream(stream_name, self.realm) for stream_name in stream_names]
        invite_link = self.generate_multiuse_invite_link(streams=streams)
        self.check_user_able_to_register(email1, invite_link)
        self.check_user_subscribed_only_to_streams(name1, streams)

        stream_names = ["Rome", "Verona"]
        streams = [get_stream(stream_name, self.realm) for stream_name in stream_names]
        invite_link = self.generate_multiuse_invite_link(streams=streams)
        self.check_user_able_to_register(email2, invite_link)
        self.check_user_subscribed_only_to_streams(name2, streams)

        streams = []
        invite_link = self.generate_multiuse_invite_link(streams=streams)
        self.check_user_able_to_register(email3, invite_link)
        # User is not subscribed to default streams as well.
        self.assert_length(get_default_streams_for_realm_as_dicts(self.realm.id), 1)
        self.check_user_subscribed_only_to_streams(name3, [])

    def test_multiuse_link_different_realms(self) -> None:
        """
        Verify that an invitation generated for one realm can't be used
        to join another.
        """
        lear_realm = get_realm("lear")
        self.realm = lear_realm
        invite_link = self.generate_multiuse_invite_link(streams=[])
        key = invite_link.split("/")[-2]

        result = self.client_get(f"/join/{key}/", subdomain="zulip")
        self.assertEqual(result.status_code, 404)
        self.assert_in_response(
            "Whoops. We couldn't find your confirmation link in the system.", result
        )

        # Now we want to test the accounts_home function, which can't be used
        # for the multiuse invite case via an HTTP request, but is still supposed
        # to do its own verification that the realms match as a hardening measure
        # against a caller that fails to do that.
        request = HttpRequest()
        confirmation = Confirmation.objects.get(confirmation_key=key)
        multiuse_object = confirmation.content_object
        with patch(
            "zerver.views.registration.get_subdomain", return_value="zulip"
        ), self.assertRaises(AssertionError):
            accounts_home(request, multiuse_object=multiuse_object)

    def test_create_multiuse_link_api_call(self) -> None:
        self.login("iago")

        result = self.client_post(
            "/json/invites/multiuse", {"invite_expires_in_minutes": 2 * 24 * 60}
        )
        invite_link = self.assert_json_success(result)["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)

    def test_create_multiuse_link_with_specified_streams_api_call(self) -> None:
        self.login("iago")
        stream_names = ["Rome", "Scotland", "Venice"]
        streams = [get_stream(stream_name, self.realm) for stream_name in stream_names]
        stream_ids = [stream.id for stream in streams]

        result = self.client_post(
            "/json/invites/multiuse",
            {
                "stream_ids": orjson.dumps(stream_ids).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        invite_link = self.assert_json_success(result)["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)
        self.check_user_subscribed_only_to_streams("test", streams)

        self.login("iago")
        stream_ids = []
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "stream_ids": orjson.dumps(stream_ids).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        invite_link = self.assert_json_success(result)["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("alice"), invite_link)
        # User is not subscribed to default streams as well.
        self.assert_length(get_default_streams_for_realm_as_dicts(self.realm.id), 1)
        self.check_user_subscribed_only_to_streams("alice", [])

    def test_multiuse_invite_without_permission_to_subscribe_others(self) -> None:
        realm = get_realm("zulip")
        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "create_multiuse_invite_group", members_group, acting_user=None
        )
        do_set_realm_property(
            realm, "invite_to_stream_policy", Realm.POLICY_ADMINS_ONLY, acting_user=None
        )

        self.login("hamlet")
        stream_names = ["Rome", "Scotland", "Venice"]
        streams = [get_stream(stream_name, self.realm) for stream_name in stream_names]
        stream_ids = [stream.id for stream in streams]
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "stream_ids": orjson.dumps(stream_ids).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        self.assert_json_error(
            result, "You do not have permission to subscribe other users to channels."
        )

        result = self.client_post(
            "/json/invites/multiuse",
            {
                "stream_ids": orjson.dumps([]).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        self.assert_json_success(result)

        self.login("iago")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "stream_ids": orjson.dumps(stream_ids).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        self.assert_json_success(result)

        do_set_realm_property(
            realm, "invite_to_stream_policy", Realm.POLICY_MEMBERS_ONLY, acting_user=None
        )
        self.login("hamlet")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "stream_ids": orjson.dumps(stream_ids).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        self.assert_json_success(result)

    def test_create_multiuse_invite_group_setting(self) -> None:
        realm = get_realm("zulip")
        full_members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.FULL_MEMBERS, realm=realm, is_system_group=True
        )
        nobody_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )

        # Default value of create_multiuse_invite_group is administrators
        self.login("shiva")
        result = self.client_post("/json/invites/multiuse")
        self.assert_json_error(result, "Insufficient permission")

        self.login("iago")
        result = self.client_post("/json/invites/multiuse")
        invite_link = self.assert_json_success(result)["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)

        do_change_realm_permission_group_setting(
            realm, "create_multiuse_invite_group", full_members_system_group, acting_user=None
        )

        self.login("hamlet")
        result = self.client_post("/json/invites/multiuse")
        invite_link = self.assert_json_success(result)["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test1"), invite_link)

        self.login("desdemona")
        do_change_realm_permission_group_setting(
            realm, "create_multiuse_invite_group", nobody_system_group, acting_user=None
        )
        result = self.client_post("/json/invites/multiuse")
        self.assert_json_error(result, "Insufficient permission")

    def test_only_owner_can_change_create_multiuse_invite_group(self) -> None:
        realm = get_realm("zulip")
        full_members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.FULL_MEMBERS, realm=realm, is_system_group=True
        )

        self.login("iago")
        result = self.client_patch(
            "/json/realm",
            {"create_multiuse_invite_group": orjson.dumps(full_members_system_group.id).decode()},
        )
        self.assert_json_error(result, "Must be an organization owner")

        self.login("desdemona")
        result = self.client_patch(
            "/json/realm",
            {"create_multiuse_invite_group": orjson.dumps(full_members_system_group.id).decode()},
        )
        self.assert_json_success(result)
        realm = get_realm("zulip")
        self.assertEqual(realm.create_multiuse_invite_group_id, full_members_system_group.id)

    def test_multiuse_link_for_inviting_as_owner(self) -> None:
        self.login("iago")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "invite_as": orjson.dumps(PreregistrationUser.INVITE_AS["REALM_OWNER"]).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        self.assert_json_error(result, "Must be an organization owner")

        self.login("desdemona")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "invite_as": orjson.dumps(PreregistrationUser.INVITE_AS["REALM_OWNER"]).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        invite_link = self.assert_json_success(result)["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)

    def test_multiuse_link_for_inviting_as_admin(self) -> None:
        realm = get_realm("zulip")
        full_members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.FULL_MEMBERS, realm=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm, "create_multiuse_invite_group", full_members_system_group, acting_user=None
        )

        self.login("hamlet")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "invite_as": orjson.dumps(PreregistrationUser.INVITE_AS["REALM_ADMIN"]).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        self.assert_json_error(result, "Must be an organization administrator")

        self.login("iago")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "invite_as": orjson.dumps(PreregistrationUser.INVITE_AS["REALM_ADMIN"]).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        invite_link = self.assert_json_success(result)["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)

    def test_multiuse_link_for_inviting_as_moderator(self) -> None:
        realm = get_realm("zulip")
        full_members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.FULL_MEMBERS, realm=realm, is_system_group=True
        )

        do_change_realm_permission_group_setting(
            realm, "create_multiuse_invite_group", full_members_system_group, acting_user=None
        )

        self.login("hamlet")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "invite_as": orjson.dumps(PreregistrationUser.INVITE_AS["MODERATOR"]).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        self.assert_json_error(result, "Must be an organization administrator")

        self.login("shiva")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "invite_as": orjson.dumps(PreregistrationUser.INVITE_AS["MODERATOR"]).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        self.assert_json_error(result, "Must be an organization administrator")

        self.login("iago")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "invite_as": orjson.dumps(PreregistrationUser.INVITE_AS["REALM_ADMIN"]).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        invite_link = self.assert_json_success(result)["invite_link"]
        self.check_user_able_to_register(self.nonreg_email("test"), invite_link)

    def test_create_multiuse_link_invalid_stream_api_call(self) -> None:
        self.login("iago")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "stream_ids": orjson.dumps([54321]).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        self.assert_json_error(result, "Invalid channel ID 54321. No invites were sent.")

    def test_create_multiuse_link_invalid_invite_as_api_call(self) -> None:
        self.login("iago")
        result = self.client_post(
            "/json/invites/multiuse",
            {
                "invite_as": orjson.dumps(PreregistrationUser.INVITE_AS["GUEST_USER"] + 1).decode(),
                "invite_expires_in_minutes": 2 * 24 * 60,
            },
        )
        self.assert_json_error(result, "Invalid invite_as")
