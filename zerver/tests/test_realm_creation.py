import base64
import time
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import quote, quote_plus

import orjson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import override_settings

from confirmation import settings as confirmation_settings
from zerver.actions.create_realm import do_change_realm_subdomain
from zerver.actions.create_user import do_create_user
from zerver.forms import check_subdomain_available
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.subdomains import is_root_domain_available
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import find_key_by_email, ratelimit_rule
from zerver.models import (
    Message,
    OnboardingUserMessage,
    PreregistrationRealm,
    Realm,
    RealmAuditLog,
    Recipient,
    ScheduledEmail,
    UserProfile,
)
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.models.users import get_system_bot, get_user


class DemoCreationTest(ZulipTestCase):
    @override_settings(OPEN_REALM_CREATION=True, DEMO_ORG_DEADLINE_DAYS=30)
    def test_create_demo_organization(self) -> None:
        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, internal_realm.id)
        signups_channel, _ = create_stream_if_needed(notification_bot.realm, "signups")

        result = self.submit_demo_creation_form("demo test")
        realm = Realm.objects.latest("date_created")
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith(
                f"http://{realm.string_id}.testserver/accounts/login/subdomain"
            )
        )

        self.assertIn("demo test", realm.name)
        expected_deletion_date = realm.date_created + timedelta(days=30)
        self.assertEqual(realm.demo_organization_scheduled_deletion_date, expected_deletion_date)

        result = self.client_get(result["Location"], subdomain=realm.string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"http://{realm.string_id}.testserver")

        user_profile = UserProfile.objects.all().order_by("id").last()
        assert user_profile is not None
        self.assert_logged_in_user_id(user_profile.id)

        # Demo organizations are created without setting an email address for the owner.
        self.assertEqual(user_profile.delivery_email, "")
        scheduled_email = ScheduledEmail.objects.filter(users=user_profile).last()
        assert scheduled_email is None

        self.assertIn(realm.string_id, user_profile.email)
        self.assertEqual(
            user_profile.email_address_visibility, UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY
        )

        # Make sure the correct Welcome Bot direct message is sent.
        welcome_msg = Message.objects.filter(
            realm_id=realm.id,
            sender__email="welcome-bot@zulip.com",
            recipient__type=Recipient.PERSONAL,
        ).latest("id")
        self.assertTrue(welcome_msg.content.startswith("Hello, and welcome to Zulip!"))
        self.assertIn("getting started guide", welcome_msg.content)
        self.assertNotIn("using Zulip for a class guide", welcome_msg.content)
        self.assertIn("demo organization", welcome_msg.content)

        # Confirm we have the expected audit log data.
        realm_creation_audit_log = RealmAuditLog.objects.get(
            realm=realm, event_type=AuditLogEventType.REALM_CREATED
        )
        self.assertEqual(realm_creation_audit_log.acting_user, user_profile)
        self.assertEqual(realm_creation_audit_log.event_time, realm.date_created)
        audit_log_extra_data = realm_creation_audit_log.extra_data
        self.assertEqual(
            audit_log_extra_data["how_realm_creator_found_zulip"],
            RealmAuditLog.HOW_REALM_CREATOR_FOUND_ZULIP_OPTIONS["ai_chatbot"],
        )
        self.assertEqual(
            audit_log_extra_data["how_realm_creator_found_zulip_extra_context"],
            "I don't remember.",
        )

        # Check admin organization's signups channel messages
        recipient = signups_channel.recipient
        messages = Message.objects.filter(realm_id=internal_realm.id, recipient=recipient).order_by(
            "id"
        )
        self.assert_length(messages, 1)
        # Check organization name, subdomain and organization type are in message content
        self.assertIn(realm.name, messages[0].content)
        self.assertIn(realm.string_id, messages[0].content)
        self.assertEqual("business demos", messages[0].topic_name())

    @ratelimit_rule(10, 2, domain="demo_realm_creation_by_ip")
    def test_demo_creation_rate_limiter(self) -> None:
        start_time = time.time()
        with patch("time.time", return_value=start_time):
            self.submit_demo_creation_form("demo 1")
            self.submit_demo_creation_form("demo 2")

            result = self.submit_demo_creation_form("demo 3")
            self.assertEqual(result.status_code, 429)
            self.assert_in_response("Rate limit exceeded.", result)

            result = self.client_get("/new/demo/")
            self.assertEqual(result.status_code, 200)

        with patch("time.time", return_value=start_time + 11):
            self.submit_demo_creation_form("demo 4")

    @override_settings(OPEN_REALM_CREATION=True, USING_CAPTCHA=True, ALTCHA_HMAC_KEY="secret")
    def test_create_demo_with_captcha(self) -> None:
        realm_name = "demo test captcha"

        result = self.client_get("/new/demo/")
        self.assert_not_in_success_response(["Validation failed"], result)

        # Without the CAPTCHA value, we get an error
        result = self.submit_demo_creation_form(realm_name)
        self.assert_in_success_response(["Validation failed, please try again."], result)

        # With an invalid value, we also get an error
        with self.assertLogs(level="WARNING") as logs:
            result = self.submit_demo_creation_form(realm_name, captcha="moose")
            self.assert_in_success_response(["Validation failed, please try again."], result)
            self.assert_length(logs.output, 1)
            self.assertIn("Invalid altcha solution: Invalid altcha payload", logs.output[0])

        # With something which raises an exception, we also get the same error
        with self.assertLogs(level="WARNING") as logs:
            result = self.submit_demo_creation_form(
                realm_name,
                captcha=base64.b64encode(
                    orjson.dumps(["algorithm", "challenge", "number", "salt", "signature"])
                ).decode(),
            )
            self.assert_in_success_response(["Validation failed, please try again."], result)
            self.assert_length(logs.output, 1)
            self.assertIn(
                "TypeError: list indices must be integers or slices, not str", logs.output[0]
            )

        # If we override the validation, we get an error because it's not in the session
        payload = base64.b64encode(orjson.dumps({"challenge": "moose"})).decode()
        with (
            patch("zerver.forms.verify_solution", return_value=(True, None)) as verify,
            self.assertLogs(level="WARNING") as logs,
        ):
            result = self.submit_demo_creation_form(realm_name, captcha=payload)
            self.assert_in_success_response(["Validation failed, please try again."], result)
            verify.assert_called_once_with(payload, "secret", check_expires=True)
            self.assert_length(logs.output, 1)
            self.assertIn("Expired or replayed altcha solution", logs.output[0])

        self.assertEqual(self.client.session.get("altcha_challenges"), None)
        result = self.client_get("/json/antispam_challenge")
        data = self.assert_json_success(result)
        self.assertEqual(data["algorithm"], "SHA-256")
        self.assertEqual(data["max_number"], 500000)
        self.assertIn("signature", data)
        self.assertIn("challenge", data)
        self.assertIn("salt", data)

        self.assert_length(self.client.session["altcha_challenges"], 1)
        self.assertEqual(self.client.session["altcha_challenges"][0][0], data["challenge"])

        # Update the payload so the challenge matches what is in the
        # session.  The real payload would have other keys.
        payload = base64.b64encode(orjson.dumps({"challenge": data["challenge"]})).decode()
        with patch("zerver.forms.verify_solution", return_value=(True, None)) as verify:
            result = self.submit_demo_creation_form(realm_name, captcha=payload)
            self.assertEqual(result.status_code, 302)
            verify.assert_called_once_with(payload, "secret", check_expires=True)

        # And the challenge has been stripped out of the session
        self.assertEqual(self.client.session["altcha_challenges"], [])

    def test_demo_organizations_disabled(self) -> None:
        with self.settings(OPEN_REALM_CREATION=False):
            result = self.submit_demo_creation_form("demo test")
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("Demo organizations are not enabled on this server.", result)

        with self.settings(DEMO_ORG_DEADLINE_DAYS=None):
            result = self.submit_demo_creation_form("demo test")
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("Demo organizations are not enabled on this server.", result)


class RealmCreationTest(ZulipTestCase):
    @override_settings(OPEN_REALM_CREATION=True)
    def check_able_to_create_realm(self, email: str, password: str = "test") -> None:
        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, internal_realm.id)
        signups_stream, _ = create_stream_if_needed(notification_bot.realm, "signups")

        string_id = "custom-test"
        org_name = "Zulip Test"
        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=org_name
        )

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(org_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)
        prereg_realm = PreregistrationRealm.objects.get(email=email)
        self.assertEqual(prereg_realm.name, "Zulip Test")
        self.assertEqual(prereg_realm.org_type, Realm.ORG_TYPES["business"]["id"])
        self.assertEqual(prereg_realm.default_language, "en")
        self.assertEqual(prereg_realm.string_id, string_id)

        # Check confirmation email has the correct subject and body, extract
        # confirmation link and visit it
        confirmation_url = self.get_confirmation_url_from_outbox(
            email,
            email_subject_contains="Create your Zulip organization",
            email_body_contains="You have requested a new Zulip organization",
        )
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain=string_id, realm_name=org_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith("http://custom-test.testserver/accounts/login/subdomain/")
        )

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        user = get_user(email, realm)
        self.assertEqual(user.realm, realm)

        # Check that user is the owner.
        self.assertEqual(user.role, UserProfile.ROLE_REALM_OWNER)

        # Check defaults
        self.assertEqual(realm.org_type, Realm.ORG_TYPES["business"]["id"])
        self.assertEqual(realm.default_language, "en")
        self.assertEqual(realm.emails_restricted_to_domains, False)
        self.assertEqual(realm.invite_required, True)

        prereg_realm = PreregistrationRealm.objects.get(email=email)
        # Check created_realm and created_user field of PreregistrationRealm object
        self.assertEqual(prereg_realm.created_realm, realm)
        self.assertEqual(prereg_realm.created_user, user)
        self.assertEqual(prereg_realm.status, confirmation_settings.STATUS_USED)

        # Check initial realm messages for onboarding
        greetings_message_content = "a great place to say “hi”"
        experiments_message_content = "Use this topic to try out"

        for stream_name, topic, text, message_count in [
            (
                str(Realm.DEFAULT_NOTIFICATION_STREAM_NAME),
                "greetings",
                greetings_message_content,
                2,
            ),
            (
                str(Realm.ZULIP_SANDBOX_CHANNEL_NAME),
                "experiments",
                experiments_message_content,
                5,
            ),
        ]:
            stream = get_stream(stream_name, realm)
            recipient = stream.recipient
            messages = Message.objects.filter(realm_id=realm.id, recipient=recipient).order_by(
                "date_sent"
            )
            self.assert_length(messages, message_count)
            self.assertEqual(topic, messages[0].topic_name())
            self.assertIn(text, messages[0].content)

        # Check admin organization's signups stream messages
        recipient = signups_stream.recipient
        messages = Message.objects.filter(realm_id=internal_realm.id, recipient=recipient).order_by(
            "id"
        )
        self.assert_length(messages, 1)
        # Check organization name, subdomain and organization type are in message content
        self.assertIn("Zulip Test", messages[0].content)
        self.assertIn("custom-test", messages[0].content)
        self.assertEqual("business signups", messages[0].topic_name())

        realm_creation_audit_log = RealmAuditLog.objects.get(
            realm=realm, event_type=AuditLogEventType.REALM_CREATED
        )
        self.assertEqual(realm_creation_audit_log.acting_user, user)
        self.assertEqual(realm_creation_audit_log.event_time, realm.date_created)
        audit_log_extra_data = realm_creation_audit_log.extra_data
        self.assertEqual(
            audit_log_extra_data["how_realm_creator_found_zulip"],
            RealmAuditLog.HOW_REALM_CREATOR_FOUND_ZULIP_OPTIONS["other"],
        )
        self.assertEqual(
            audit_log_extra_data["how_realm_creator_found_zulip_extra_context"],
            "I found it on the internet.",
        )

        # Piggyback a little check for how we handle
        # empty string_ids.
        realm.string_id = ""
        self.assertEqual(realm.display_subdomain, ".")

    def test_create_realm_non_existing_email(self) -> None:
        self.check_able_to_create_realm("user1@test.com")

    def test_create_realm_existing_email(self) -> None:
        self.check_able_to_create_realm("hamlet@zulip.com")

    @override_settings(AUTHENTICATION_BACKENDS=("zproject.backends.ZulipLDAPAuthBackend",))
    def test_create_realm_ldap_email(self) -> None:
        self.init_default_ldap_database()

        with self.settings(LDAP_EMAIL_ATTR="mail"):
            self.check_able_to_create_realm(
                "newuser_email@zulip.com", self.ldap_password("newuser_with_email")
            )

    def test_create_realm_as_system_bot(self) -> None:
        result = self.submit_realm_creation_form(
            email="notification-bot@zulip.com",
            realm_subdomain="custom-test",
            realm_name="Zulip test",
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("notification-bot@zulip.com is reserved for system bots", result)

    def test_create_realm_no_creation_key(self) -> None:
        """
        Trying to create a realm without a creation_key should fail when
        OPEN_REALM_CREATION is false.
        """
        email = "user1@test.com"

        with self.settings(OPEN_REALM_CREATION=False):
            # Create new realm with the email, but no creation key.
            result = self.submit_realm_creation_form(
                email, realm_subdomain="custom-test", realm_name="Zulip test"
            )
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("Organization creation link required", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_without_password_backend_enabled(self) -> None:
        email = "user@example.com"
        with self.settings(
            AUTHENTICATION_BACKENDS=(
                "zproject.backends.SAMLAuthBackend",
                "zproject.backends.ZulipDummyBackend",
            )
        ):
            result = self.submit_realm_creation_form(
                email, realm_subdomain="custom-test", realm_name="Zulip test"
            )
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("Organization creation link required", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_subdomain(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(
            email, email_body_contains="Organization URL"
        )
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://custom-test.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        self.assertEqual(get_user(email, realm).realm, realm)

        self.assertEqual(realm.name, realm_name)
        self.assertEqual(realm.subdomain, string_id)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_marketing_emails_enabled(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
            enable_marketing_emails=True,
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://custom-test.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        user = get_user(email, realm)
        self.assertEqual(user.realm, realm)
        self.assertTrue(user.enable_marketing_emails)

    @override_settings(OPEN_REALM_CREATION=True, CORPORATE_ENABLED=False)
    def test_create_realm_without_prompting_for_marketing_emails(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        # Simulate the initial POST that is made by redirect-to-post.ts
        # by triggering submit on confirm_preregistration.html.
        payload = {
            "full_name": "",
            "key": find_key_by_email(email),
            "from_confirmation": "1",
        }
        result = self.client_post("/realm/register/", payload)
        # Assert that the form did not prompt the user for enabling
        # marketing emails.
        self.assert_not_in_success_response(['input id="id_enable_marketing_emails"'], result)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://custom-test.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        user = get_user(email, realm)
        self.assertEqual(user.realm, realm)
        self.assertFalse(user.enable_marketing_emails)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_marketing_emails_disabled(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Zulip test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
            enable_marketing_emails=False,
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://custom-test.testserver")

        # Make sure the realm is created
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        user = get_user(email, realm)
        self.assertEqual(user.realm, realm)
        self.assertFalse(user.enable_marketing_emails)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_regular_realm_welcome_bot_direct_message(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        # Create new realm with the email.
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
            enable_marketing_emails=False,
        )
        self.assertEqual(result.status_code, 302)

        # Make sure the correct Welcome Bot direct message is sent.
        realm = get_realm(string_id)
        welcome_msg = Message.objects.filter(
            realm_id=realm.id,
            sender__email="welcome-bot@zulip.com",
            recipient__type=Recipient.PERSONAL,
        ).latest("id")
        self.assertTrue(welcome_msg.content.startswith("Hello, and welcome to Zulip!"))

        # Organization type is not education or education_nonprofit,
        # and organization is not a demo organization.
        self.assertIn("getting started guide", welcome_msg.content)
        self.assertNotIn("using Zulip for a class guide", welcome_msg.content)
        self.assertNotIn("demo organization", welcome_msg.content)

        # Organization has tracked onboarding messages.
        self.assertTrue(OnboardingUserMessage.objects.filter(realm_id=realm.id).exists())
        self.assertIn("I've kicked off some conversations", welcome_msg.content)

        # Verify that Organization without 'OnboardingUserMessage' records
        # doesn't include "I've kicked off..." text in welcome_msg content.
        OnboardingUserMessage.objects.filter(realm_id=realm.id).delete()
        do_create_user("hamlet", "password", realm, "hamlet", acting_user=None)
        welcome_msg = Message.objects.filter(
            realm_id=realm.id,
            sender__email="welcome-bot@zulip.com",
            recipient__type=Recipient.PERSONAL,
        ).latest("id")
        self.assertTrue(welcome_msg.content.startswith("Hello, and welcome to Zulip!"))
        self.assertNotIn("I've kicked off some conversations", welcome_msg.content)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_education_organization_welcome_bot_direct_message(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        # Create new realm with the email.
        result = self.submit_realm_creation_form(
            email,
            realm_subdomain=string_id,
            realm_name=realm_name,
            realm_type=Realm.ORG_TYPES["education"]["id"],
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=35&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
            enable_marketing_emails=False,
            realm_type=Realm.ORG_TYPES["education"]["id"],
        )
        self.assertEqual(result.status_code, 302)

        # Make sure the correct Welcome Bot direct message is sent.
        welcome_msg = Message.objects.filter(
            realm_id=get_realm(string_id).id,
            sender__email="welcome-bot@zulip.com",
            recipient__type=Recipient.PERSONAL,
        ).latest("id")
        self.assertTrue(welcome_msg.content.startswith("Hello, and welcome to Zulip!"))

        # Organization type is education.
        self.assertNotIn("getting started guide", welcome_msg.content)
        self.assertIn("using Zulip for a class guide", welcome_msg.content)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_with_custom_language(self) -> None:
        email = "user1@test.com"
        password = "test"
        string_id = "custom-test"
        realm_name = "Zulip Test"
        realm_language = "de"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        # Create new realm with the email
        result = self.submit_realm_creation_form(
            email,
            realm_subdomain=string_id,
            realm_name=realm_name,
            realm_default_language=realm_language,
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language={realm_language}&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        prereg_realm = PreregistrationRealm.objects.get(email=email)
        # Check default_language field of PreregistrationRealm object
        self.assertEqual(prereg_realm.default_language, realm_language)

        # Visit the confirmation link.
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=string_id,
            realm_name=realm_name,
            realm_default_language=realm_language,
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://custom-test.testserver")

        # Make sure the realm is created and check default_language field
        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        self.assertEqual(realm.default_language, realm_language)

        # Check initial realm messages for onboarding
        greetings_channel = "allgemein"
        greetings_topic = "Grüße"
        greetings_message_content = "Thema ist ein toller Ort um “hi”"
        experiments_channel = "Sandbox"
        experiments_topic = "Experimente"
        experiments_message_content = "Verwende dieses Thema um"

        for stream_name, topic, text, message_count in [
            (greetings_channel, greetings_topic, greetings_message_content, 2),
            (experiments_channel, experiments_topic, experiments_message_content, 5),
        ]:
            stream = get_stream(stream_name, realm)
            recipient = stream.recipient
            messages = Message.objects.filter(realm_id=realm.id, recipient=recipient).order_by(
                "date_sent"
            )
            self.assert_length(messages, message_count)
            self.assertEqual(topic, messages[0].topic_name())
            self.assertIn(text, messages[0].content)

    @override_settings(OPEN_REALM_CREATION=True, CLOUD_FREE_TRIAL_DAYS=30)
    def test_create_realm_during_free_trial(self) -> None:
        password = "test"
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )

        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        confirmation_url = self.get_confirmation_url_from_outbox(
            email, email_body_contains="Organization URL"
        )
        result = self.client_get(confirmation_url)
        self.assertEqual(result.status_code, 200)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assertEqual(result["Location"], "http://custom-test.testserver/upgrade/")

        result = self.client_get(result["Location"], subdomain=string_id)
        self.assert_in_success_response(["Your card will not be charged", "free trial"], result)

        realm = get_realm(string_id)
        self.assertEqual(realm.string_id, string_id)
        self.assertEqual(get_user(email, realm).realm, realm)

        self.assertEqual(realm.name, realm_name)
        self.assertEqual(realm.subdomain, string_id)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_two_realms(self) -> None:
        """
        Verify correct behavior and PreregistrationRealm handling when using
        two pre-generated realm creation links to create two different realms.
        """
        password = "test"
        first_string_id = "custom-test"
        second_string_id = "custom-test2"
        email = "user1@test.com"
        first_realm_name = "Test"
        second_realm_name = "Test"

        # Make sure the realms do not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(first_string_id)
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(second_string_id)

        # Now we pre-generate two realm creation links
        result = self.submit_realm_creation_form(
            email, realm_subdomain=first_string_id, realm_name=first_realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(first_realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={first_string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)
        first_confirmation_url = self.get_confirmation_url_from_outbox(
            email, email_body_contains="Organization URL"
        )
        self.assertEqual(PreregistrationRealm.objects.filter(email=email, status=0).count(), 1)

        result = self.submit_realm_creation_form(
            email, realm_subdomain=second_string_id, realm_name=second_realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].endswith(
                f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(second_realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={second_string_id}"
            )
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)
        second_confirmation_url = self.get_confirmation_url_from_outbox(
            email, email_body_contains="Organization URL"
        )

        self.assertNotEqual(first_confirmation_url, second_confirmation_url)
        self.assertEqual(PreregistrationRealm.objects.filter(email=email, status=0).count(), 2)

        # Create and verify the first realm
        result = self.client_get(first_confirmation_url)
        self.assertEqual(result.status_code, 200)
        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=first_string_id,
            realm_name=first_realm_name,
            key=first_confirmation_url.split("/")[-1],
        )
        self.assertEqual(result.status_code, 302)
        # Make sure the realm is created
        realm = get_realm(first_string_id)
        self.assertEqual(realm.string_id, first_string_id)
        self.assertEqual(realm.name, first_realm_name)

        # One of the PreregistrationRealm should have been used up:
        self.assertEqual(PreregistrationRealm.objects.filter(email=email, status=0).count(), 1)

        # Create and verify the second realm
        result = self.client_get(second_confirmation_url)
        self.assertEqual(result.status_code, 200)
        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain=second_string_id,
            realm_name=second_realm_name,
            key=second_confirmation_url.split("/")[-1],
        )
        self.assertEqual(result.status_code, 302)
        # Make sure the realm is created
        realm = get_realm(second_string_id)
        self.assertEqual(realm.string_id, second_string_id)
        self.assertEqual(realm.name, second_realm_name)

        # The remaining PreregistrationRealm should have been used up:
        self.assertEqual(PreregistrationRealm.objects.filter(email=email, status=0).count(), 0)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_invalid_email_signup(self) -> None:
        result = self.submit_realm_creation_form(
            email="<foo", realm_subdomain="custom-test", realm_name="Zulip test"
        )
        self.assert_in_response("Please use your real email address.", result)
        self.assert_in_response("Enter a valid email address.", result)

        result = self.submit_realm_creation_form(
            email="foo\x00bar", realm_subdomain="custom-test", realm_name="Zulip test"
        )
        self.assert_in_response("Please use your real email address.", result)
        self.assert_in_response("Null characters are not allowed.", result)
        self.assert_in_response("Enter a valid email address.", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_mailinator_signup(self) -> None:
        result = self.client_post("/new/", {"email": "hi@mailinator.com"})
        self.assert_in_response("Please use your real email address.", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        errors = {
            "id": "length 3 or greater",
            "-id": "cannot start or end with a",
            "string-ID": "lowercase letters",
            "string_id": "lowercase letters",
            "stream": "reserved",
            "streams": "reserved",
            "about": "reserved",
            "abouts": "reserved",
            "zephyr": "already in use",
        }
        for string_id, error_msg in errors.items():
            result = self.submit_realm_creation_form(
                email, realm_subdomain=string_id, realm_name=realm_name
            )
            self.assert_in_response(error_msg, result)

        # test valid subdomain
        result = self.submit_realm_creation_form(
            email, realm_subdomain="a-0", realm_name=realm_name
        )
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain="a-0", realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith("http://a-0.testserver/accounts/login/subdomain/")
        )

    @override_settings(OPEN_REALM_CREATION=True)
    def test_create_realm_using_old_subdomain_of_a_realm(self) -> None:
        realm = get_realm("zulip")
        do_change_realm_subdomain(realm, "new-name", acting_user=None)

        email = "user1@test.com"

        result = self.submit_realm_creation_form(email, realm_subdomain="test", realm_name="Test")
        self.assert_in_response("Subdomain reserved. Please choose a different one.", result)

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions_root_domain(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        # test root domain will fail with ROOT_DOMAIN_LANDING_PAGE
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.submit_realm_creation_form(
                email, realm_subdomain="", realm_name=realm_name
            )
            self.assert_in_response("already in use", result)

        # test valid use of root domain
        result = self.submit_realm_creation_form(email, realm_subdomain="", realm_name=realm_name)
        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        result = self.submit_reg_form_for_user(
            email, password, realm_subdomain="", realm_name=realm_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith("http://testserver/accounts/login/subdomain/")
        )

    @override_settings(OPEN_REALM_CREATION=True)
    def test_subdomain_restrictions_root_domain_option(self) -> None:
        password = "test"
        email = "user1@test.com"
        realm_name = "Test"

        # test root domain will fail with ROOT_DOMAIN_LANDING_PAGE
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.submit_realm_creation_form(
                email, realm_subdomain="abcdef", realm_name=realm_name, realm_in_root_domain="true"
            )
            self.assert_in_response("already in use", result)

        # test valid use of root domain
        result = self.submit_realm_creation_form(
            email, realm_subdomain="abcdef", realm_name=realm_name, realm_in_root_domain="true"
        )

        self.client_get(result["Location"])
        confirmation_url = self.get_confirmation_url_from_outbox(email)
        self.client_get(confirmation_url)

        result = self.submit_reg_form_for_user(
            email,
            password,
            realm_subdomain="abcdef",
            realm_in_root_domain="true",
            realm_name=realm_name,
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            result["Location"].startswith("http://testserver/accounts/login/subdomain/")
        )

    def test_is_root_domain_available(self) -> None:
        self.assertTrue(is_root_domain_available())
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            self.assertFalse(is_root_domain_available())
        realm = get_realm("zulip")
        realm.string_id = Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
        realm.save()
        self.assertFalse(is_root_domain_available())

    def test_subdomain_check_api(self) -> None:
        result = self.client_get("/json/realm/subdomain/zulip")
        self.assert_in_success_response(
            ["Subdomain is already in use. Please choose a different one."], result
        )

        result = self.client_get("/json/realm/subdomain/zu_lip")
        self.assert_in_success_response(
            ["Subdomain can only have lowercase letters, numbers, and '-'s."], result
        )

        with self.settings(SOCIAL_AUTH_SUBDOMAIN="zulipauth"):
            result = self.client_get("/json/realm/subdomain/zulipauth")
            self.assert_in_success_response(
                ["Subdomain reserved. Please choose a different one."], result
            )

        with self.settings(SELF_HOSTING_MANAGEMENT_SUBDOMAIN="zulipselfhosting"):
            result = self.client_get("/json/realm/subdomain/zulipselfhosting")
            self.assert_in_success_response(
                ["Subdomain reserved. Please choose a different one."], result
            )

        result = self.client_get("/json/realm/subdomain/hufflepuff")
        self.assert_in_success_response(["available"], result)
        self.assert_not_in_success_response(["already in use"], result)
        self.assert_not_in_success_response(["reserved"], result)

    def test_subdomain_check_management_command(self) -> None:
        # Short names should not work, even with the flag
        with self.assertRaises(ValidationError):
            check_subdomain_available("aa")
        with self.assertRaises(ValidationError):
            check_subdomain_available("aa", allow_reserved_subdomain=True)

        # Malformed names should never work
        with self.assertRaises(ValidationError):
            check_subdomain_available("-ba_d-")
        with self.assertRaises(ValidationError):
            check_subdomain_available("-ba_d-", allow_reserved_subdomain=True)

        with patch("zerver.lib.name_restrictions.is_reserved_subdomain", return_value=False):
            # Existing realms should never work even if they are not reserved keywords
            with self.assertRaises(ValidationError):
                check_subdomain_available("zulip")
            with self.assertRaises(ValidationError):
                check_subdomain_available("zulip", allow_reserved_subdomain=True)

        # Reserved ones should only work with the flag
        with self.assertRaises(ValidationError):
            check_subdomain_available("stream")
        check_subdomain_available("stream", allow_reserved_subdomain=True)

        # "zulip" and "kandra" are allowed if not CORPORATE_ENABLED or with the flag
        with self.settings(CORPORATE_ENABLED=False):
            check_subdomain_available("we-are-zulip-team")
        with self.settings(CORPORATE_ENABLED=True):
            with self.assertRaises(ValidationError):
                check_subdomain_available("we-are-zulip-team")
            check_subdomain_available("we-are-zulip-team", allow_reserved_subdomain=True)

    @override_settings(OPEN_REALM_CREATION=True, USING_CAPTCHA=True, ALTCHA_HMAC_KEY="secret")
    def test_create_realm_with_captcha(self) -> None:
        string_id = "custom-test"
        email = "user1@test.com"
        realm_name = "Test"

        # Make sure the realm does not exist
        with self.assertRaises(Realm.DoesNotExist):
            get_realm(string_id)

        result = self.client_get("/new/")
        self.assert_not_in_success_response(["Validation failed"], result)

        # Without the CAPTCHA value, we get an error
        result = self.submit_realm_creation_form(
            email, realm_subdomain=string_id, realm_name=realm_name
        )
        self.assert_in_success_response(["Validation failed, please try again."], result)

        # With an invalid value, we also get an error
        with self.assertLogs(level="WARNING") as logs:
            result = self.submit_realm_creation_form(
                email, realm_subdomain=string_id, realm_name=realm_name, captcha="moose"
            )
            self.assert_in_success_response(["Validation failed, please try again."], result)
            self.assert_length(logs.output, 1)
            self.assertIn("Invalid altcha solution: Invalid altcha payload", logs.output[0])

        # With something which raises an exception, we also get the same error
        with self.assertLogs(level="WARNING") as logs:
            result = self.submit_realm_creation_form(
                email,
                realm_subdomain=string_id,
                realm_name=realm_name,
                captcha=base64.b64encode(
                    orjson.dumps(["algorithm", "challenge", "number", "salt", "signature"])
                ).decode(),
            )
            self.assert_in_success_response(["Validation failed, please try again."], result)
            self.assert_length(logs.output, 1)
            self.assertIn(
                "TypeError: list indices must be integers or slices, not str", logs.output[0]
            )

        # If we override the validation, we get an error because it's not in the session
        payload = base64.b64encode(orjson.dumps({"challenge": "moose"})).decode()
        with (
            patch("zerver.forms.verify_solution", return_value=(True, None)) as verify,
            self.assertLogs(level="WARNING") as logs,
        ):
            result = self.submit_realm_creation_form(
                email, realm_subdomain=string_id, realm_name=realm_name, captcha=payload
            )
            self.assert_in_success_response(["Validation failed, please try again."], result)
            verify.assert_called_once_with(payload, "secret", check_expires=True)
            self.assert_length(logs.output, 1)
            self.assertIn("Expired or replayed altcha solution", logs.output[0])

        self.assertEqual(self.client.session.get("altcha_challenges"), None)
        result = self.client_get("/json/antispam_challenge")
        data = self.assert_json_success(result)
        self.assertEqual(data["algorithm"], "SHA-256")
        self.assertEqual(data["max_number"], 500000)
        self.assertIn("signature", data)
        self.assertIn("challenge", data)
        self.assertIn("salt", data)

        self.assert_length(self.client.session["altcha_challenges"], 1)
        self.assertEqual(self.client.session["altcha_challenges"][0][0], data["challenge"])

        # Update the payload so the challenge matches what is in the
        # session.  The real payload would have other keys.
        payload = base64.b64encode(orjson.dumps({"challenge": data["challenge"]})).decode()
        with patch("zerver.forms.verify_solution", return_value=(True, None)) as verify:
            result = self.submit_realm_creation_form(
                email, realm_subdomain=string_id, realm_name=realm_name, captcha=payload
            )
            self.assertEqual(result.status_code, 302)
            verify.assert_called_once_with(payload, "secret", check_expires=True)

        # And the challenge has been stripped out of the session
        self.assertEqual(self.client.session["altcha_challenges"], [])
