from datetime import timedelta
from email.headerregistry import Address
from typing import Any, Dict, Iterable, List, Optional, TypeVar, Union
from unittest import mock

import orjson
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from confirmation.models import Confirmation
from zerver.actions.create_user import do_create_user, do_reactivate_user
from zerver.actions.invites import do_create_multiuse_invite_link, do_invite_users
from zerver.actions.message_send import RecipientInfoResult, get_recipient_info
from zerver.actions.muted_users import do_mute_user
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.user_settings import bulk_regenerate_api_keys, do_change_user_setting
from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.actions.users import (
    change_user_is_active,
    do_change_can_create_users,
    do_change_user_role,
    do_deactivate_user,
    do_delete_user,
    do_delete_user_preserving_messages,
)
from zerver.lib.avatar import avatar_url, get_avatar_field, get_gravatar_url
from zerver.lib.bulk_create import create_users
from zerver.lib.create_user import copy_default_settings
from zerver.lib.events import do_events_register
from zerver.lib.exceptions import JsonableError
from zerver.lib.send_email import (
    clear_scheduled_emails,
    deliver_scheduled_emails,
    send_future_email,
)
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    get_subscription,
    get_test_image_file,
    reset_email_visibility_to_everyone_in_zulip_realm,
    simulated_empty_cache,
)
from zerver.lib.upload import upload_avatar_image
from zerver.lib.user_groups import get_system_user_group_for_user
from zerver.lib.users import (
    Account,
    access_user_by_id,
    access_user_by_id_including_cross_realm,
    get_accounts_for_email,
    get_cross_realm_dicts,
    get_inaccessible_user_ids,
    user_ids_to_users,
)
from zerver.lib.utils import assert_is_not_none
from zerver.models import (
    CustomProfileField,
    Message,
    OnboardingStep,
    PreregistrationUser,
    RealmAuditLog,
    RealmDomain,
    RealmUserDefault,
    Recipient,
    ScheduledEmail,
    Stream,
    Subscription,
    UserGroupMembership,
    UserProfile,
    UserTopic,
)
from zerver.models.clients import get_client
from zerver.models.custom_profile_fields import check_valid_user_ids
from zerver.models.groups import SystemGroups
from zerver.models.prereg_users import filter_to_valid_prereg_users
from zerver.models.realms import InvalidFakeEmailDomainError, get_fake_email_domain, get_realm
from zerver.models.streams import get_stream
from zerver.models.users import (
    get_source_profile,
    get_system_bot,
    get_user,
    get_user_by_delivery_email,
    get_user_by_id_in_realm_including_cross_realm,
)

K = TypeVar("K")
V = TypeVar("V")


def find_dict(lst: Iterable[Dict[K, V]], k: K, v: V) -> Dict[K, V]:
    for dct in lst:
        if dct[k] == v:
            return dct
    raise AssertionError(f"Cannot find element in list where key {k} == {v}")


class PermissionTest(ZulipTestCase):
    def test_role_setters(self) -> None:
        user_profile = self.example_user("hamlet")

        user_profile.is_realm_admin = True
        self.assertEqual(user_profile.is_realm_admin, True)
        self.assertEqual(user_profile.role, UserProfile.ROLE_REALM_ADMINISTRATOR)

        user_profile.is_guest = False
        self.assertEqual(user_profile.is_guest, False)
        self.assertEqual(user_profile.role, UserProfile.ROLE_REALM_ADMINISTRATOR)

        user_profile.is_realm_owner = False
        self.assertEqual(user_profile.is_realm_owner, False)
        self.assertEqual(user_profile.role, UserProfile.ROLE_REALM_ADMINISTRATOR)

        user_profile.is_moderator = False
        self.assertEqual(user_profile.is_moderator, False)
        self.assertEqual(user_profile.role, UserProfile.ROLE_REALM_ADMINISTRATOR)

        user_profile.is_realm_admin = False
        self.assertEqual(user_profile.is_realm_admin, False)
        self.assertEqual(user_profile.role, UserProfile.ROLE_MEMBER)

        user_profile.is_guest = True
        self.assertEqual(user_profile.is_guest, True)
        self.assertEqual(user_profile.role, UserProfile.ROLE_GUEST)

        user_profile.is_realm_admin = False
        self.assertEqual(user_profile.is_guest, True)
        self.assertEqual(user_profile.role, UserProfile.ROLE_GUEST)

        user_profile.is_guest = False
        self.assertEqual(user_profile.is_guest, False)
        self.assertEqual(user_profile.role, UserProfile.ROLE_MEMBER)

        user_profile.is_realm_owner = True
        self.assertEqual(user_profile.is_realm_owner, True)
        self.assertEqual(user_profile.role, UserProfile.ROLE_REALM_OWNER)

        user_profile.is_realm_owner = False
        self.assertEqual(user_profile.is_realm_owner, False)
        self.assertEqual(user_profile.role, UserProfile.ROLE_MEMBER)

        user_profile.is_moderator = True
        self.assertEqual(user_profile.is_moderator, True)
        self.assertEqual(user_profile.role, UserProfile.ROLE_MODERATOR)

        user_profile.is_moderator = False
        self.assertEqual(user_profile.is_moderator, False)
        self.assertEqual(user_profile.role, UserProfile.ROLE_MEMBER)

    def test_get_admin_users(self) -> None:
        user_profile = self.example_user("hamlet")
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER, acting_user=None)
        self.assertFalse(user_profile.is_realm_owner)
        admin_users = user_profile.realm.get_human_admin_users()
        self.assertFalse(user_profile in admin_users)
        admin_users = user_profile.realm.get_admin_users_and_bots()
        self.assertFalse(user_profile in admin_users)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        self.assertFalse(user_profile.is_realm_owner)
        admin_users = user_profile.realm.get_human_admin_users()
        self.assertTrue(user_profile in admin_users)
        admin_users = user_profile.realm.get_admin_users_and_bots()
        self.assertTrue(user_profile in admin_users)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_OWNER, acting_user=None)
        self.assertTrue(user_profile.is_realm_owner)
        admin_users = user_profile.realm.get_human_admin_users()
        self.assertTrue(user_profile in admin_users)
        admin_users = user_profile.realm.get_human_admin_users(include_realm_owners=False)
        self.assertFalse(user_profile in admin_users)
        admin_users = user_profile.realm.get_admin_users_and_bots()
        self.assertTrue(user_profile in admin_users)
        admin_users = user_profile.realm.get_admin_users_and_bots(include_realm_owners=False)
        self.assertFalse(user_profile in admin_users)

    def test_get_first_human_user(self) -> None:
        realm = get_realm("zulip")
        UserProfile.objects.filter(realm=realm).delete()

        UserProfile.objects.create(
            realm=realm, email="bot1@zulip.com", delivery_email="bot1@zulip.com", is_bot=True
        )
        first_human_user = UserProfile.objects.create(
            realm=realm, email="user1@zulip.com", delivery_email="user1@zulip.com", is_bot=False
        )
        UserProfile.objects.create(
            realm=realm, email="user2@zulip.com", delivery_email="user2@zulip.com", is_bot=False
        )
        UserProfile.objects.create(
            realm=realm, email="bot2@zulip.com", delivery_email="bot2@zulip.com", is_bot=True
        )
        self.assertEqual(first_human_user, realm.get_first_human_user())

    def test_updating_non_existent_user(self) -> None:
        self.login("hamlet")
        admin = self.example_user("hamlet")
        do_change_user_role(admin, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)

        invalid_user_id = 1000
        result = self.client_patch(f"/json/users/{invalid_user_id}", {})
        self.assert_json_error(result, "No such user")

    def test_owner_api(self) -> None:
        self.login("iago")

        desdemona = self.example_user("desdemona")
        othello = self.example_user("othello")
        iago = self.example_user("iago")
        realm = iago.realm

        do_change_user_role(iago, UserProfile.ROLE_REALM_OWNER, acting_user=None)

        result = self.client_get("/json/users")
        members = self.assert_json_success(result)["members"]
        iago_dict = find_dict(members, "email", iago.email)
        self.assertTrue(iago_dict["is_owner"])
        othello_dict = find_dict(members, "email", othello.email)
        self.assertFalse(othello_dict["is_owner"])

        req = dict(role=UserProfile.ROLE_REALM_OWNER)
        with self.capture_send_event_calls(expected_num_events=6) as events:
            result = self.client_patch(f"/json/users/{othello.id}", req)
        self.assert_json_success(result)
        owner_users = realm.get_human_owner_users()
        self.assertTrue(othello in owner_users)
        person = events[0]["event"]["person"]
        self.assertEqual(person["user_id"], othello.id)
        self.assertEqual(person["role"], UserProfile.ROLE_REALM_OWNER)

        req = dict(role=UserProfile.ROLE_MEMBER)
        with self.capture_send_event_calls(expected_num_events=5) as events:
            result = self.client_patch(f"/json/users/{othello.id}", req)
        self.assert_json_success(result)
        owner_users = realm.get_human_owner_users()
        self.assertFalse(othello in owner_users)
        person = events[0]["event"]["person"]
        self.assertEqual(person["user_id"], othello.id)
        self.assertEqual(person["role"], UserProfile.ROLE_MEMBER)

        # Cannot take away from last owner
        self.login("desdemona")
        req = dict(role=UserProfile.ROLE_MEMBER)
        with self.capture_send_event_calls(expected_num_events=4) as events:
            result = self.client_patch(f"/json/users/{iago.id}", req)
        self.assert_json_success(result)
        owner_users = realm.get_human_owner_users()
        self.assertFalse(iago in owner_users)
        person = events[0]["event"]["person"]
        self.assertEqual(person["user_id"], iago.id)
        self.assertEqual(person["role"], UserProfile.ROLE_MEMBER)
        with self.capture_send_event_calls(expected_num_events=0):
            result = self.client_patch(f"/json/users/{desdemona.id}", req)
        self.assert_json_error(
            result, "The owner permission cannot be removed from the only organization owner."
        )

        do_change_user_role(iago, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        self.login("iago")
        with self.capture_send_event_calls(expected_num_events=0):
            result = self.client_patch(f"/json/users/{desdemona.id}", req)
        self.assert_json_error(result, "Must be an organization owner")

    def test_admin_api(self) -> None:
        self.login("desdemona")

        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        desdemona = self.example_user("desdemona")
        realm = hamlet.realm

        # Make sure we see is_admin flag in /json/users
        result = self.client_get("/json/users")
        members = self.assert_json_success(result)["members"]
        desdemona_dict = find_dict(members, "email", desdemona.email)
        self.assertTrue(desdemona_dict["is_admin"])
        othello_dict = find_dict(members, "email", othello.email)
        self.assertFalse(othello_dict["is_admin"])

        # Giveth
        req = dict(role=orjson.dumps(UserProfile.ROLE_REALM_ADMINISTRATOR).decode())

        with self.capture_send_event_calls(expected_num_events=6) as events:
            result = self.client_patch(f"/json/users/{othello.id}", req)
        self.assert_json_success(result)
        admin_users = realm.get_human_admin_users()
        self.assertTrue(othello in admin_users)
        person = events[0]["event"]["person"]
        self.assertEqual(person["user_id"], othello.id)
        self.assertEqual(person["role"], UserProfile.ROLE_REALM_ADMINISTRATOR)

        # Taketh away
        req = dict(role=orjson.dumps(UserProfile.ROLE_MEMBER).decode())
        with self.capture_send_event_calls(expected_num_events=5) as events:
            result = self.client_patch(f"/json/users/{othello.id}", req)
        self.assert_json_success(result)
        admin_users = realm.get_human_admin_users()
        self.assertFalse(othello in admin_users)
        person = events[0]["event"]["person"]
        self.assertEqual(person["user_id"], othello.id)
        self.assertEqual(person["role"], UserProfile.ROLE_MEMBER)

        # Make sure only admins can patch other user's info.
        self.login("othello")
        result = self.client_patch(f"/json/users/{hamlet.id}", req)
        self.assert_json_error(result, "Insufficient permission")

    def test_admin_api_hide_emails(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        user = self.example_user("hamlet")
        admin = self.example_user("iago")
        self.login_user(user)

        # First, verify client_gravatar works normally
        result = self.client_get("/json/users", {"client_gravatar": "true"})
        members = self.assert_json_success(result)["members"]
        hamlet = find_dict(members, "user_id", user.id)
        self.assertEqual(hamlet["email"], user.email)
        self.assertIsNone(hamlet["avatar_url"])
        self.assertEqual(hamlet["delivery_email"], user.delivery_email)

        # Also verify the /events code path.  This is a bit hacky, but
        # we need to verify client_gravatar is not being overridden.
        with mock.patch(
            "zerver.lib.events.request_event_queue", return_value=None
        ) as mock_request_event_queue:
            with self.assertRaises(JsonableError):
                do_events_register(user, user.realm, get_client("website"), client_gravatar=True)
            self.assertEqual(mock_request_event_queue.call_args_list[0][0][3], True)

        #############################################################
        # Now, switch email address visibility, check client_gravatar
        # is automatically disabled for the user.
        with self.captureOnCommitCallbacks(execute=True):
            do_change_user_setting(
                user,
                "email_address_visibility",
                UserProfile.EMAIL_ADDRESS_VISIBILITY_ADMINS,
                acting_user=None,
            )
        result = self.client_get("/json/users", {"client_gravatar": "true"})
        members = self.assert_json_success(result)["members"]
        hamlet = find_dict(members, "user_id", user.id)
        self.assertEqual(hamlet["email"], f"user{user.id}@zulip.testserver")
        self.assertEqual(hamlet["avatar_url"], get_gravatar_url(user.delivery_email, 1))

        # client_gravatar is still turned off for admins.  In theory,
        # it doesn't need to be, but client-side changes would be
        # required in apps like the mobile apps.
        # delivery_email is sent for admins.
        admin.refresh_from_db()
        user.refresh_from_db()
        self.login_user(admin)
        result = self.client_get("/json/users", {"client_gravatar": "true"})
        members = self.assert_json_success(result)["members"]
        hamlet = find_dict(members, "user_id", user.id)
        self.assertEqual(hamlet["email"], f"user{user.id}@zulip.testserver")
        self.assertEqual(hamlet["avatar_url"], get_gravatar_url(user.delivery_email, 1))
        self.assertEqual(hamlet["delivery_email"], self.example_email("hamlet"))

    def test_user_cannot_promote_to_admin(self) -> None:
        self.login("hamlet")
        req = dict(role=orjson.dumps(UserProfile.ROLE_REALM_ADMINISTRATOR).decode())
        result = self.client_patch("/json/users/{}".format(self.example_user("hamlet").id), req)
        self.assert_json_error(result, "Insufficient permission")

    def test_admin_user_can_change_full_name(self) -> None:
        new_name = "new name"
        self.login("iago")
        hamlet = self.example_user("hamlet")
        req = dict(full_name=new_name)
        result = self.client_patch(f"/json/users/{hamlet.id}", req)
        self.assert_json_success(result)
        hamlet = self.example_user("hamlet")
        self.assertEqual(hamlet.full_name, new_name)

    def test_non_admin_cannot_change_full_name(self) -> None:
        self.login("hamlet")
        req = dict(full_name="new name")
        result = self.client_patch("/json/users/{}".format(self.example_user("othello").id), req)
        self.assert_json_error(result, "Insufficient permission")

    def test_admin_cannot_set_long_full_name(self) -> None:
        new_name = "a" * (UserProfile.MAX_NAME_LENGTH + 1)
        self.login("iago")
        req = dict(full_name=new_name)
        result = self.client_patch("/json/users/{}".format(self.example_user("hamlet").id), req)
        self.assert_json_error(result, "Name too long!")

    def test_admin_cannot_set_short_full_name(self) -> None:
        new_name = "a"
        self.login("iago")
        req = dict(full_name=new_name)
        result = self.client_patch("/json/users/{}".format(self.example_user("hamlet").id), req)
        self.assert_json_error(result, "Name too short!")

    def test_not_allowed_format(self) -> None:
        # Name of format "Alice|999" breaks in Markdown
        new_name = "iago|72"
        self.login("iago")
        req = dict(full_name=new_name)
        result = self.client_patch("/json/users/{}".format(self.example_user("hamlet").id), req)
        self.assert_json_error(result, "Invalid format!")

    def test_allowed_format_complex(self) -> None:
        # Adding characters after r'|d+' doesn't break Markdown
        new_name = "Hello- 12iago|72k"
        self.login("iago")
        req = dict(full_name=new_name)
        result = self.client_patch("/json/users/{}".format(self.example_user("hamlet").id), req)
        self.assert_json_success(result)

    def test_require_unique_names(self) -> None:
        self.login("desdemona")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")

        do_set_realm_property(hamlet.realm, "require_unique_names", True, acting_user=None)
        req = dict(full_name="IaGo")
        result = self.client_patch(f"/json/users/{hamlet.id}", req)
        self.assert_json_error(result, "Unique names required in this organization.")

        req = dict(full_name="𝕚𝕒𝕘𝕠")
        result = self.client_patch(f"/json/users/{hamlet.id}", req)
        self.assert_json_error(result, "Unique names required in this organization.")

        req = dict(full_name="ｉａｇｏ")
        result = self.client_patch(f"/json/users/{hamlet.id}", req)
        self.assert_json_error(result, "Unique names required in this organization.")

        req = dict(full_name="𝒾𝒶𝑔𝑜")
        result = self.client_patch(f"/json/users/{hamlet.id}", req)
        self.assert_json_error(result, "Unique names required in this organization.")

        # check for uniqueness including imported users
        iago.is_mirror_dummy = True
        req = dict(full_name="iago")
        result = self.client_patch(f"/json/users/{hamlet.id}", req)
        self.assert_json_error(result, "Unique names required in this organization.")

        # check for uniqueness including deactivated users
        do_deactivate_user(iago, acting_user=None)
        req = dict(full_name="iago")
        result = self.client_patch(f"/json/users/{hamlet.id}", req)
        self.assert_json_error(result, "Unique names required in this organization.")

        do_set_realm_property(hamlet.realm, "require_unique_names", False, acting_user=None)
        req = dict(full_name="iago")
        result = self.client_patch(f"/json/users/{hamlet.id}", req)
        self.assert_json_success(result)

    def test_not_allowed_format_complex(self) -> None:
        new_name = "Hello- 12iago|72"
        self.login("iago")
        req = dict(full_name=new_name)
        result = self.client_patch("/json/users/{}".format(self.example_user("hamlet").id), req)
        self.assert_json_error(result, "Invalid format!")

    def test_admin_cannot_set_full_name_with_invalid_characters(self) -> None:
        new_name = "Opheli*"
        self.login("iago")
        req = dict(full_name=new_name)
        result = self.client_patch("/json/users/{}".format(self.example_user("hamlet").id), req)
        self.assert_json_error(result, "Invalid characters in name!")

    def test_access_user_by_id(self) -> None:
        iago = self.example_user("iago")
        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)

        # Must be a valid user ID in the realm
        with self.assertRaises(JsonableError):
            access_user_by_id(iago, 1234, for_admin=False)
        with self.assertRaises(JsonableError):
            access_user_by_id_including_cross_realm(iago, 1234, for_admin=False)
        with self.assertRaises(JsonableError):
            access_user_by_id(iago, self.mit_user("sipbtest").id, for_admin=False)
        with self.assertRaises(JsonableError):
            access_user_by_id_including_cross_realm(
                iago, self.mit_user("sipbtest").id, for_admin=False
            )

        # Can only access bot users if allow_bots is passed
        bot = self.example_user("default_bot")
        access_user_by_id(iago, bot.id, allow_bots=True, for_admin=True)
        access_user_by_id_including_cross_realm(iago, bot.id, allow_bots=True, for_admin=True)
        with self.assertRaises(JsonableError):
            access_user_by_id(iago, bot.id, for_admin=True)
        with self.assertRaises(JsonableError):
            access_user_by_id_including_cross_realm(iago, bot.id, for_admin=True)

        # Only the including_cross_realm variant works for system bots.
        system_bot = get_system_bot(settings.WELCOME_BOT, internal_realm.id)
        with self.assertRaises(JsonableError):
            access_user_by_id(iago, system_bot.id, allow_bots=True, for_admin=False)
        access_user_by_id_including_cross_realm(
            iago, system_bot.id, allow_bots=True, for_admin=False
        )
        # And even then, only if `allow_bots` was passed.
        with self.assertRaises(JsonableError):
            access_user_by_id(iago, system_bot.id, for_admin=False)
        with self.assertRaises(JsonableError):
            access_user_by_id_including_cross_realm(iago, system_bot.id, for_admin=False)

        # Can only access deactivated users if allow_deactivated is passed
        hamlet = self.example_user("hamlet")
        do_deactivate_user(hamlet, acting_user=None)
        with self.assertRaises(JsonableError):
            access_user_by_id(iago, hamlet.id, for_admin=False)
        with self.assertRaises(JsonableError):
            access_user_by_id_including_cross_realm(iago, hamlet.id, for_admin=False)

        with self.assertRaises(JsonableError):
            access_user_by_id(iago, hamlet.id, for_admin=True)
        with self.assertRaises(JsonableError):
            access_user_by_id_including_cross_realm(iago, hamlet.id, for_admin=True)
        access_user_by_id(iago, hamlet.id, allow_deactivated=True, for_admin=True)
        access_user_by_id_including_cross_realm(
            iago, hamlet.id, allow_deactivated=True, for_admin=True
        )

        # Non-admin user can't admin another user
        with self.assertRaises(JsonableError):
            access_user_by_id(
                self.example_user("cordelia"), self.example_user("aaron").id, for_admin=True
            )
        with self.assertRaises(JsonableError):
            access_user_by_id_including_cross_realm(
                self.example_user("cordelia"), self.example_user("aaron").id, for_admin=True
            )

        # But does have read-only access to it.
        access_user_by_id(
            self.example_user("cordelia"), self.example_user("aaron").id, for_admin=False
        )
        access_user_by_id_including_cross_realm(
            self.example_user("cordelia"), self.example_user("aaron").id, for_admin=False
        )

    def check_property_for_role(self, user_profile: UserProfile, role: int) -> bool:
        if role == UserProfile.ROLE_REALM_ADMINISTRATOR:
            return (
                user_profile.is_realm_admin
                and not user_profile.is_guest
                and not user_profile.is_realm_owner
                and not user_profile.is_moderator
            )
        elif role == UserProfile.ROLE_REALM_OWNER:
            return (
                user_profile.is_realm_owner
                and user_profile.is_realm_admin
                and not user_profile.is_moderator
                and not user_profile.is_guest
            )
        elif role == UserProfile.ROLE_MODERATOR:
            return (
                user_profile.is_moderator
                and not user_profile.is_realm_owner
                and not user_profile.is_realm_admin
                and not user_profile.is_guest
            )

        if role == UserProfile.ROLE_MEMBER:
            return (
                not user_profile.is_guest
                and not user_profile.is_moderator
                and not user_profile.is_realm_admin
                and not user_profile.is_realm_owner
            )

        assert role == UserProfile.ROLE_GUEST
        return (
            user_profile.is_guest
            and not user_profile.is_moderator
            and not user_profile.is_realm_admin
            and not user_profile.is_realm_owner
        )

    def check_user_role_change(
        self,
        user_email: str,
        new_role: int,
    ) -> None:
        self.login("desdemona")

        user_profile = self.example_user(user_email)
        old_role = user_profile.role
        old_system_group = get_system_user_group_for_user(user_profile)

        self.assertTrue(self.check_property_for_role(user_profile, old_role))
        self.assertTrue(
            UserGroupMembership.objects.filter(
                user_profile=user_profile, user_group=old_system_group
            ).exists()
        )

        req = dict(role=orjson.dumps(new_role).decode())

        # The basic events sent in all cases on changing role are - one event
        # for changing role and one event each for adding and removing user
        # from system user group.
        num_events = 3

        if UserProfile.ROLE_MEMBER in [old_role, new_role]:
            # There is one additional event for adding/removing user from
            # the "Full members" group as well.
            num_events += 1

        if new_role == UserProfile.ROLE_GUEST:
            # There is one additional event deleting the unsubscribed public
            # streams that the user will not able to access after becoming guest.
            num_events += 1

        if old_role == UserProfile.ROLE_GUEST:
            # User will receive one event for creation of unsubscribed public
            # (and private, if the new role is owner or admin) streams that
            # they did not have access to previously and 3 more peer_add
            # events for each of the public stream.
            if new_role in [UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_REALM_OWNER]:
                # If the new role is owner or admin, the peer_add event will be
                # sent for one private stream as well.
                num_events += 5
            else:
                num_events += 4
        elif new_role in [
            UserProfile.ROLE_REALM_ADMINISTRATOR,
            UserProfile.ROLE_REALM_OWNER,
        ] and old_role not in [UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_REALM_OWNER]:
            # If old_role is not guest and user's role is changed to admin or owner from moderator
            # or member, then the user gains access to unsubscribed private streams and thus
            # receives one event for stream creation and one peer_add event for it.
            num_events += 2

        with self.capture_send_event_calls(expected_num_events=num_events) as events:
            result = self.client_patch(f"/json/users/{user_profile.id}", req)
        self.assert_json_success(result)

        user_profile = self.example_user(user_email)
        self.assertTrue(self.check_property_for_role(user_profile, new_role))
        system_group = get_system_user_group_for_user(user_profile)
        self.assertTrue(
            UserGroupMembership.objects.filter(
                user_profile=user_profile, user_group=system_group
            ).exists()
        )

        person = events[0]["event"]["person"]
        self.assertEqual(person["user_id"], user_profile.id)
        self.assertTrue(person["role"], new_role)

    def test_change_regular_member_to_guest(self) -> None:
        self.check_user_role_change("hamlet", UserProfile.ROLE_GUEST)

    def test_change_guest_to_regular_member(self) -> None:
        self.check_user_role_change("polonius", UserProfile.ROLE_MEMBER)

    def test_change_admin_to_guest(self) -> None:
        self.check_user_role_change("iago", UserProfile.ROLE_GUEST)

    def test_change_guest_to_admin(self) -> None:
        self.check_user_role_change("polonius", UserProfile.ROLE_REALM_ADMINISTRATOR)

    def test_change_owner_to_guest(self) -> None:
        self.login("desdemona")
        iago = self.example_user("iago")
        do_change_user_role(iago, UserProfile.ROLE_REALM_OWNER, acting_user=None)
        self.check_user_role_change("iago", UserProfile.ROLE_GUEST)

    def test_change_guest_to_owner(self) -> None:
        self.check_user_role_change("polonius", UserProfile.ROLE_REALM_OWNER)

    def test_change_admin_to_owner(self) -> None:
        self.check_user_role_change("iago", UserProfile.ROLE_REALM_OWNER)

    def test_change_owner_to_admin(self) -> None:
        self.login("desdemona")
        iago = self.example_user("iago")
        do_change_user_role(iago, UserProfile.ROLE_REALM_OWNER, acting_user=None)
        self.check_user_role_change("iago", UserProfile.ROLE_REALM_ADMINISTRATOR)

    def test_change_owner_to_moderator(self) -> None:
        iago = self.example_user("iago")
        do_change_user_role(iago, UserProfile.ROLE_REALM_OWNER, acting_user=None)
        self.check_user_role_change("iago", UserProfile.ROLE_MODERATOR)

    def test_change_moderator_to_owner(self) -> None:
        self.check_user_role_change("shiva", UserProfile.ROLE_REALM_OWNER)

    def test_change_admin_to_moderator(self) -> None:
        self.check_user_role_change("iago", UserProfile.ROLE_MODERATOR)

    def test_change_moderator_to_admin(self) -> None:
        self.check_user_role_change("shiva", UserProfile.ROLE_REALM_ADMINISTRATOR)

    def test_change_guest_to_moderator(self) -> None:
        self.check_user_role_change("polonius", UserProfile.ROLE_MODERATOR)

    def test_change_moderator_to_guest(self) -> None:
        self.check_user_role_change("shiva", UserProfile.ROLE_GUEST)

    def test_admin_user_can_change_profile_data(self) -> None:
        realm = get_realm("zulip")
        self.login("iago")
        new_profile_data = []
        cordelia = self.example_user("cordelia")

        # Test for all type of data
        fields = {
            "Phone number": "short text data",
            "Biography": "long text data",
            "Favorite food": "short text data",
            "Favorite editor": "0",
            "Birthday": "1909-03-05",
            "Favorite website": "https://zulip.com",
            "Mentor": [cordelia.id],
            "GitHub username": "timabbott",
            "Pronouns": "she/her",
        }

        for field_name in fields:
            field = CustomProfileField.objects.get(name=field_name, realm=realm)
            new_profile_data.append(
                {
                    "id": field.id,
                    "value": fields[field_name],
                }
            )

        result = self.client_patch(
            f"/json/users/{cordelia.id}", {"profile_data": orjson.dumps(new_profile_data).decode()}
        )
        self.assert_json_success(result)

        cordelia = self.example_user("cordelia")
        for field_dict in cordelia.profile_data():
            with self.subTest(field_name=field_dict["name"]):
                self.assertEqual(field_dict["value"], fields[field_dict["name"]])

        # Test admin user cannot set invalid profile data
        invalid_fields = [
            (
                "Favorite editor",
                "invalid choice",
                "'invalid choice' is not a valid choice for 'Favorite editor'.",
            ),
            ("Birthday", "1909-34-55", "Birthday is not a date"),
            ("Favorite website", "not url", "Favorite website is not a URL"),
            ("Mentor", "not list of user ids", "User IDs is not a list"),
        ]

        for field_name, field_value, error_msg in invalid_fields:
            new_profile_data = []
            field = CustomProfileField.objects.get(name=field_name, realm=realm)
            new_profile_data.append(
                {
                    "id": field.id,
                    "value": field_value,
                }
            )

            result = self.client_patch(
                f"/json/users/{cordelia.id}",
                {"profile_data": orjson.dumps(new_profile_data).decode()},
            )
            self.assert_json_error(result, error_msg)

        # non-existent field and no data
        invalid_profile_data = [
            {
                "id": 9001,
                "value": "",
            }
        ]
        result = self.client_patch(
            f"/json/users/{cordelia.id}",
            {"profile_data": orjson.dumps(invalid_profile_data).decode()},
        )
        self.assert_json_error(result, "Field id 9001 not found.")

        # non-existent field and data
        invalid_profile_data = [
            {
                "id": 9001,
                "value": "some data",
            }
        ]
        result = self.client_patch(
            f"/json/users/{cordelia.id}",
            {"profile_data": orjson.dumps(invalid_profile_data).decode()},
        )
        self.assert_json_error(result, "Field id 9001 not found.")

        # Test for clearing/resetting field values.
        empty_profile_data = []
        for field_name in fields:
            field = CustomProfileField.objects.get(name=field_name, realm=realm)
            value: Union[str, None, List[Any]] = ""
            if field.field_type == CustomProfileField.USER:
                value = []
            empty_profile_data.append(
                {
                    "id": field.id,
                    "value": value,
                }
            )
        result = self.client_patch(
            f"/json/users/{cordelia.id}",
            {"profile_data": orjson.dumps(empty_profile_data).decode()},
        )
        self.assert_json_success(result)
        for field_dict in cordelia.profile_data():
            with self.subTest(field_name=field_dict["name"]):
                self.assertEqual(field_dict["value"], None)

        # Test adding some of the field values after removing all.
        hamlet = self.example_user("hamlet")
        new_fields = {
            "Phone number": None,
            "Biography": "A test user",
            "Favorite food": None,
            "Favorite editor": None,
            "Birthday": None,
            "Favorite website": "https://zulip.github.io",
            "Mentor": [hamlet.id],
            "GitHub username": "timabbott",
            "Pronouns": None,
        }
        new_profile_data = []
        for field_name in fields:
            field = CustomProfileField.objects.get(name=field_name, realm=realm)
            value = None
            if new_fields[field_name]:
                value = new_fields[field_name]
            new_profile_data.append(
                {
                    "id": field.id,
                    "value": value,
                }
            )
        result = self.client_patch(
            f"/json/users/{cordelia.id}", {"profile_data": orjson.dumps(new_profile_data).decode()}
        )
        self.assert_json_success(result)
        for field_dict in cordelia.profile_data():
            with self.subTest(field_name=field_dict["name"]):
                self.assertEqual(field_dict["value"], new_fields[str(field_dict["name"])])

    def test_non_admin_user_cannot_change_profile_data(self) -> None:
        self.login("cordelia")
        hamlet = self.example_user("hamlet")
        realm = get_realm("zulip")

        new_profile_data = []
        field = CustomProfileField.objects.get(name="Biography", realm=realm)
        new_profile_data.append(
            {
                "id": field.id,
                "value": "New hamlet Biography",
            }
        )
        result = self.client_patch(
            f"/json/users/{hamlet.id}", {"profile_data": orjson.dumps(new_profile_data).decode()}
        )
        self.assert_json_error(result, "Insufficient permission")

        result = self.client_patch(
            "/json/users/{}".format(self.example_user("cordelia").id),
            {"profile_data": orjson.dumps(new_profile_data).decode()},
        )
        self.assert_json_error(result, "Insufficient permission")


class QueryCountTest(ZulipTestCase):
    def test_create_user_with_multiple_streams(self) -> None:
        # add_new_user_history needs messages to be current
        Message.objects.all().update(date_sent=timezone_now())

        ContentType.objects.clear_cache()

        # This just focuses on making sure we don't too many
        # queries/cache tries or send too many events.
        realm = get_realm("zulip")

        self.make_stream("private_stream1", invite_only=True)
        self.make_stream("private_stream2", invite_only=True)

        stream_names = [
            "Denmark",
            "Scotland",
            "Verona",
            "private_stream1",
            "private_stream2",
        ]
        streams = [get_stream(stream_name, realm) for stream_name in stream_names]

        invite_expires_in_minutes = 4 * 24 * 60
        with self.captureOnCommitCallbacks(execute=True):
            do_invite_users(
                user_profile=self.example_user("hamlet"),
                invitee_emails=["fred@zulip.com"],
                streams=streams,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )

        prereg_user = PreregistrationUser.objects.get(email="fred@zulip.com")

        with self.assert_database_query_count(93):
            with self.assert_memcached_count(23):
                with self.capture_send_event_calls(expected_num_events=11) as events:
                    fred = do_create_user(
                        email="fred@zulip.com",
                        password="password",
                        realm=realm,
                        full_name="Fred Flintstone",
                        prereg_user=prereg_user,
                        acting_user=None,
                    )

        peer_add_events = [event for event in events if event["event"].get("op") == "peer_add"]

        notifications = set()
        for event in peer_add_events:
            stream_ids = event["event"]["stream_ids"]
            stream_names = sorted(Stream.objects.get(id=stream_id).name for stream_id in stream_ids)
            self.assertTrue(event["event"]["user_ids"], {fred.id})
            notifications.add(",".join(stream_names))

        self.assertEqual(
            notifications, {"Denmark,Scotland,Verona", "private_stream1", "private_stream2"}
        )


class BulkCreateUserTest(ZulipTestCase):
    def test_create_users(self) -> None:
        realm = get_realm("zulip")
        realm_user_default = RealmUserDefault.objects.get(realm=realm)
        realm_user_default.email_address_visibility = (
            RealmUserDefault.EMAIL_ADDRESS_VISIBILITY_ADMINS
        )
        realm_user_default.save()

        name_list = [
            ("Fred Flintstone", "fred@zulip.com"),
            ("Lisa Simpson", "lisa@zulip.com"),
        ]

        create_users(realm, name_list)

        fred = get_user_by_delivery_email("fred@zulip.com", realm)
        self.assertEqual(
            fred.email,
            f"user{fred.id}@zulip.testserver",
        )

        lisa = get_user_by_delivery_email("lisa@zulip.com", realm)
        self.assertEqual(lisa.full_name, "Lisa Simpson")
        self.assertEqual(lisa.is_bot, False)
        self.assertEqual(lisa.bot_type, None)

        realm_user_default.email_address_visibility = (
            RealmUserDefault.EMAIL_ADDRESS_VISIBILITY_EVERYONE
        )
        realm_user_default.save()

        name_list = [
            ("Bono", "bono@zulip.com"),
            ("Cher", "cher@zulip.com"),
        ]

        now = timezone_now()
        expected_user_group_names = {
            SystemGroups.MEMBERS,
            SystemGroups.FULL_MEMBERS,
        }
        create_users(realm, name_list)
        bono = get_user_by_delivery_email("bono@zulip.com", realm)
        self.assertEqual(bono.email, "bono@zulip.com")
        self.assertEqual(bono.delivery_email, "bono@zulip.com")
        user_group_names = set(
            RealmAuditLog.objects.filter(
                realm=realm,
                modified_user=bono,
                event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
                event_time__gte=now,
            ).values_list("modified_user_group__name", flat=True)
        )
        self.assertSetEqual(
            user_group_names,
            expected_user_group_names,
        )

        cher = get_user_by_delivery_email("cher@zulip.com", realm)
        self.assertEqual(cher.full_name, "Cher")
        user_group_names = set(
            RealmAuditLog.objects.filter(
                realm=realm,
                modified_user=cher,
                event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
                event_time__gte=now,
            ).values_list("modified_user_group__name", flat=True)
        )
        self.assertSetEqual(
            user_group_names,
            expected_user_group_names,
        )


class AdminCreateUserTest(ZulipTestCase):
    def test_create_user_backend(self) -> None:
        # This test should give us complete coverage on
        # create_user_backend.  It mostly exercises error
        # conditions, and it also does a basic test of the success
        # path.

        admin = self.example_user("hamlet")
        realm = admin.realm
        self.login_user(admin)
        do_change_user_role(admin, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        do_set_realm_property(realm, "default_language", "ja", acting_user=None)
        valid_params = dict(
            email="romeo@zulip.net",
            password="xxxx",
            full_name="Romeo Montague",
        )

        self.assertEqual(admin.can_create_users, False)
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result, "User not authorized to create users")

        do_change_can_create_users(admin, True)
        # can_create_users is insufficient without being a realm administrator:
        do_change_user_role(admin, UserProfile.ROLE_MEMBER, acting_user=None)
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result, "Must be an organization administrator")

        do_change_user_role(admin, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)

        result = self.client_post("/json/users", {})
        self.assert_json_error(result, "Missing 'email' argument")

        result = self.client_post(
            "/json/users",
            dict(
                email="romeo@not-zulip.com",
            ),
        )
        self.assert_json_error(result, "Missing 'password' argument")

        result = self.client_post(
            "/json/users",
            dict(
                email="romeo@not-zulip.com",
                password="xxxx",
            ),
        )
        self.assert_json_error(result, "Missing 'full_name' argument")

        # Test short_name gets properly ignored
        result = self.client_post(
            "/json/users",
            dict(
                email="romeo@zulip.com",
                password="xxxx",
                full_name="Romeo Montague",
                short_name="DEPRECATED",
            ),
        )
        self.assert_json_success(result, ignored_parameters=["short_name"])

        result = self.client_post(
            "/json/users",
            dict(
                email="broken",
                password="xxxx",
                full_name="Romeo Montague",
            ),
        )
        self.assert_json_error(result, "Bad name or username")

        do_set_realm_property(realm, "emails_restricted_to_domains", True, acting_user=None)
        result = self.client_post(
            "/json/users",
            dict(
                email="romeo@not-zulip.com",
                password="xxxx",
                full_name="Romeo Montague",
            ),
        )
        self.assert_json_error(
            result, "Email 'romeo@not-zulip.com' not allowed in this organization"
        )

        RealmDomain.objects.create(realm=get_realm("zulip"), domain="zulip.net")
        # Check can't use a bad password with zxcvbn enabled
        with self.settings(PASSWORD_MIN_LENGTH=6, PASSWORD_MIN_GUESSES=1000):
            result = self.client_post("/json/users", valid_params)
            self.assert_json_error(result, "The password is too weak.")

        result = self.client_post("/json/users", valid_params)
        self.assert_json_success(result)

        # Romeo is a newly registered user
        new_user = get_user_by_delivery_email("romeo@zulip.net", get_realm("zulip"))
        result = orjson.loads(result.content)
        self.assertEqual(new_user.full_name, "Romeo Montague")
        self.assertEqual(new_user.id, result["user_id"])
        self.assertEqual(new_user.tos_version, UserProfile.TOS_VERSION_BEFORE_FIRST_LOGIN)
        # Make sure the new user got the realm's default language
        self.assertEqual(new_user.default_language, "ja")

        # Make sure the recipient field is set correctly.
        self.assertEqual(
            new_user.recipient, Recipient.objects.get(type=Recipient.PERSONAL, type_id=new_user.id)
        )

        # we can't create the same user twice.
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result, "Email 'romeo@zulip.net' already in use")

        # Don't allow user to sign up with disposable email.
        realm.emails_restricted_to_domains = False
        realm.disallow_disposable_email_addresses = True
        realm.save()

        valid_params["email"] = "abc@mailnator.com"
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(
            result, "Disposable email addresses are not allowed in this organization"
        )

        # Don't allow creating a user with + in their email address when realm
        # is restricted to a domain.
        realm.emails_restricted_to_domains = True
        realm.save()

        valid_params["email"] = "iago+label@zulip.com"
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result, "Email addresses containing + are not allowed.")

        # Users can be created with + in their email address when realm
        # is not restricted to a domain.
        realm.emails_restricted_to_domains = False
        realm.save()

        valid_params["email"] = "iago+label@zulip.com"
        result = self.client_post("/json/users", valid_params)
        self.assert_json_success(result)


class UserProfileTest(ZulipTestCase):
    def test_valid_user_id(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        bot = self.example_user("default_bot")

        # Invalid user ID
        invalid_uid: object = 1000
        with self.assertRaisesRegex(ValidationError, r"User IDs is not a list"):
            check_valid_user_ids(realm.id, invalid_uid)
        with self.assertRaisesRegex(ValidationError, rf"Invalid user ID: {invalid_uid}"):
            check_valid_user_ids(realm.id, [invalid_uid])

        invalid_uid = "abc"
        with self.assertRaisesRegex(ValidationError, r"User IDs\[0\] is not an integer"):
            check_valid_user_ids(realm.id, [invalid_uid])

        invalid_uid = str(othello.id)
        with self.assertRaisesRegex(ValidationError, r"User IDs\[0\] is not an integer"):
            check_valid_user_ids(realm.id, [invalid_uid])

        # User is in different realm
        with self.assertRaisesRegex(ValidationError, rf"Invalid user ID: {hamlet.id}"):
            check_valid_user_ids(get_realm("zephyr").id, [hamlet.id])

        # User is not active
        change_user_is_active(hamlet, False)
        with self.assertRaisesRegex(ValidationError, rf"User with ID {hamlet.id} is deactivated"):
            check_valid_user_ids(realm.id, [hamlet.id])
        check_valid_user_ids(realm.id, [hamlet.id], allow_deactivated=True)

        # User is a bot
        with self.assertRaisesRegex(ValidationError, rf"User with ID {bot.id} is a bot"):
            check_valid_user_ids(realm.id, [bot.id])

        # Successfully get non-bot, active user belong to your realm
        check_valid_user_ids(realm.id, [othello.id])

    def test_cache_invalidation(self) -> None:
        hamlet = self.example_user("hamlet")
        with mock.patch("zerver.lib.cache.delete_display_recipient_cache") as m:
            hamlet.full_name = "Hamlet Junior"
            hamlet.save(update_fields=["full_name"])

        self.assertTrue(m.called)

        with mock.patch("zerver.lib.cache.delete_display_recipient_cache") as m:
            hamlet.long_term_idle = True
            hamlet.save(update_fields=["long_term_idle"])

        self.assertFalse(m.called)

    def test_user_ids_to_users(self) -> None:
        real_user_ids = [
            self.example_user("hamlet").id,
            self.example_user("cordelia").id,
        ]

        self.assertEqual(user_ids_to_users([], get_realm("zulip")), [])
        self.assertEqual(
            {
                user_profile.id
                for user_profile in user_ids_to_users(real_user_ids, get_realm("zulip"))
            },
            set(real_user_ids),
        )
        with self.assertRaises(JsonableError):
            user_ids_to_users([1234], get_realm("zephyr"))
        with self.assertRaises(JsonableError):
            user_ids_to_users(real_user_ids, get_realm("zephyr"))

    def test_get_accounts_for_email(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        def check_account_present_in_accounts(user: UserProfile, accounts: List[Account]) -> None:
            for account in accounts:
                realm = user.realm
                if (
                    account["avatar"] == avatar_url(user)
                    and account["full_name"] == user.full_name
                    and account["realm_name"] == realm.name
                    and account["realm_id"] == realm.id
                ):
                    return
            raise AssertionError("Account not found")

        lear_realm = get_realm("lear")
        cordelia_in_zulip = self.example_user("cordelia")
        cordelia_in_lear = get_user_by_delivery_email("cordelia@zulip.com", lear_realm)

        email = "cordelia@zulip.com"
        accounts = get_accounts_for_email(email)
        self.assert_length(accounts, 2)
        check_account_present_in_accounts(cordelia_in_zulip, accounts)
        check_account_present_in_accounts(cordelia_in_lear, accounts)

        email = "CORDelia@zulip.com"
        accounts = get_accounts_for_email(email)
        self.assert_length(accounts, 2)
        check_account_present_in_accounts(cordelia_in_zulip, accounts)
        check_account_present_in_accounts(cordelia_in_lear, accounts)

        email = "IAGO@ZULIP.COM"
        accounts = get_accounts_for_email(email)
        self.assert_length(accounts, 1)
        check_account_present_in_accounts(self.example_user("iago"), accounts)

        # We verify that get_accounts_for_email don't return deactivated users accounts
        user = self.example_user("hamlet")
        do_deactivate_user(user, acting_user=None)
        email = self.example_email("hamlet")
        accounts = get_accounts_for_email(email)
        with self.assertRaises(AssertionError):
            check_account_present_in_accounts(user, accounts)

    def test_get_source_profile(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()
        zulip_realm_id = get_realm("zulip").id
        iago = get_source_profile("iago@zulip.com", zulip_realm_id)
        assert iago is not None
        self.assertEqual(iago.email, "iago@zulip.com")
        self.assertEqual(iago.realm, get_realm("zulip"))

        iago = get_source_profile("IAGO@ZULIP.com", zulip_realm_id)
        assert iago is not None
        self.assertEqual(iago.email, "iago@zulip.com")

        lear_realm_id = get_realm("lear").id
        cordelia = get_source_profile("cordelia@zulip.com", lear_realm_id)
        assert cordelia is not None
        self.assertEqual(cordelia.email, "cordelia@zulip.com")

        self.assertIsNone(get_source_profile("iagod@zulip.com", zulip_realm_id))
        self.assertIsNone(get_source_profile("iago@zulip.com", 0))
        self.assertIsNone(get_source_profile("iago@zulip.com", lear_realm_id))

    def test_copy_default_settings_from_another_user(self) -> None:
        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        do_change_user_setting(cordelia, "default_language", "de", acting_user=None)
        do_change_user_setting(cordelia, "web_home_view", "all_messages", acting_user=None)
        do_change_user_setting(cordelia, "emojiset", "twitter", acting_user=None)
        do_change_user_setting(cordelia, "timezone", "America/Phoenix", acting_user=None)
        do_change_user_setting(
            cordelia, "color_scheme", UserProfile.COLOR_SCHEME_NIGHT, acting_user=None
        )
        do_change_user_setting(
            cordelia, "enable_offline_email_notifications", False, acting_user=None
        )
        do_change_user_setting(cordelia, "enable_stream_push_notifications", True, acting_user=None)
        do_change_user_setting(cordelia, "enter_sends", False, acting_user=None)
        cordelia.avatar_source = UserProfile.AVATAR_FROM_USER
        cordelia.save()

        # Upload cordelia's avatar
        with get_test_image_file("img.png") as image_file:
            upload_avatar_image(image_file, cordelia, cordelia)

        OnboardingStep.objects.filter(user=cordelia).delete()
        OnboardingStep.objects.filter(user=iago).delete()
        hotspots_completed = {"intro_streams", "intro_topics"}
        for hotspot in hotspots_completed:
            OnboardingStep.objects.create(user=cordelia, onboarding_step=hotspot)

        # Check that we didn't send an realm_user update events to
        # users; this work is happening before the user account is
        # created, so any changes will be reflected in the "add" event
        # introducing the user to clients.
        with self.capture_send_event_calls(expected_num_events=0):
            copy_default_settings(cordelia, iago)

        # We verify that cordelia and iago match, but hamlet has the defaults.
        self.assertEqual(iago.full_name, "Cordelia, Lear's daughter")
        self.assertEqual(cordelia.full_name, "Cordelia, Lear's daughter")
        self.assertEqual(hamlet.full_name, "King Hamlet")

        self.assertEqual(iago.default_language, "de")
        self.assertEqual(cordelia.default_language, "de")
        self.assertEqual(hamlet.default_language, "en")

        self.assertEqual(iago.emojiset, "twitter")
        self.assertEqual(cordelia.emojiset, "twitter")
        self.assertEqual(hamlet.emojiset, "google")

        self.assertEqual(iago.timezone, "America/Phoenix")
        self.assertEqual(cordelia.timezone, "America/Phoenix")
        self.assertEqual(hamlet.timezone, "")

        self.assertEqual(iago.color_scheme, UserProfile.COLOR_SCHEME_NIGHT)
        self.assertEqual(cordelia.color_scheme, UserProfile.COLOR_SCHEME_NIGHT)
        self.assertEqual(hamlet.color_scheme, UserProfile.COLOR_SCHEME_AUTOMATIC)

        self.assertEqual(iago.enable_offline_email_notifications, False)
        self.assertEqual(cordelia.enable_offline_email_notifications, False)
        self.assertEqual(hamlet.enable_offline_email_notifications, True)

        self.assertEqual(iago.enable_stream_push_notifications, True)
        self.assertEqual(cordelia.enable_stream_push_notifications, True)
        self.assertEqual(hamlet.enable_stream_push_notifications, False)

        self.assertEqual(iago.enter_sends, False)
        self.assertEqual(cordelia.enter_sends, False)
        self.assertEqual(hamlet.enter_sends, True)

        hotspots = set(
            OnboardingStep.objects.filter(user=iago).values_list("onboarding_step", flat=True)
        )
        self.assertEqual(hotspots, hotspots_completed)

    def test_copy_default_settings_from_realm_user_default(self) -> None:
        cordelia = self.example_user("cordelia")
        realm = get_realm("zulip")
        realm_user_default = RealmUserDefault.objects.get(realm=realm)

        realm_user_default.web_home_view = "recent_topics"
        realm_user_default.emojiset = "twitter"
        realm_user_default.color_scheme = UserProfile.COLOR_SCHEME_LIGHT
        realm_user_default.enable_offline_email_notifications = False
        realm_user_default.enable_stream_push_notifications = True
        realm_user_default.enter_sends = True
        realm_user_default.save()

        # Check that we didn't send an realm_user update events to
        # users; this work is happening before the user account is
        # created, so any changes will be reflected in the "add" event
        # introducing the user to clients.
        with self.capture_send_event_calls(expected_num_events=0):
            copy_default_settings(realm_user_default, cordelia)

        self.assertEqual(cordelia.web_home_view, "recent_topics")
        self.assertEqual(cordelia.emojiset, "twitter")
        self.assertEqual(cordelia.color_scheme, UserProfile.COLOR_SCHEME_LIGHT)
        self.assertEqual(cordelia.enable_offline_email_notifications, False)
        self.assertEqual(cordelia.enable_stream_push_notifications, True)
        self.assertEqual(cordelia.enter_sends, True)

    def test_get_user_by_id_in_realm_including_cross_realm(self) -> None:
        realm = get_realm("zulip")
        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        bot = get_system_bot(settings.WELCOME_BOT, internal_realm.id)

        # Pass in the ID of a cross-realm bot and a valid realm
        cross_realm_bot = get_user_by_id_in_realm_including_cross_realm(bot.id, realm)
        self.assertEqual(cross_realm_bot.email, bot.email)
        self.assertEqual(cross_realm_bot.id, bot.id)

        # Pass in the ID of a cross-realm bot but with a invalid realm,
        # note that the realm should be irrelevant here
        cross_realm_bot = get_user_by_id_in_realm_including_cross_realm(bot.id, None)
        self.assertEqual(cross_realm_bot.email, bot.email)
        self.assertEqual(cross_realm_bot.id, bot.id)

        # Pass in the ID of a non-cross-realm user with a realm
        user_profile = get_user_by_id_in_realm_including_cross_realm(othello.id, realm)
        self.assertEqual(user_profile.email, othello.email)
        self.assertEqual(user_profile.id, othello.id)

        # If the realm doesn't match, or if the ID is not that of a
        # cross-realm bot, UserProfile.DoesNotExist is raised
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user_by_id_in_realm_including_cross_realm(hamlet.id, None)

    def test_cross_realm_dicts(self) -> None:
        def user_row(email: str) -> Dict[str, object]:
            user = UserProfile.objects.get(email=email)
            avatar_url = get_avatar_field(
                user_id=user.id,
                realm_id=user.realm_id,
                email=user.delivery_email,
                avatar_source=user.avatar_source,
                avatar_version=1,
                medium=False,
                client_gravatar=False,
            )
            return dict(
                # bot-specific fields
                avatar_url=avatar_url,
                date_joined=user.date_joined.isoformat(),
                delivery_email=email,
                email=email,
                full_name=user.full_name,
                user_id=user.id,
                # common fields
                avatar_version=1,
                bot_owner_id=None,
                bot_type=1,
                is_active=True,
                is_admin=False,
                is_billing_admin=False,
                is_bot=True,
                is_guest=False,
                is_owner=False,
                is_system_bot=True,
                role=400,
                timezone="",
            )

        expected_emails = [
            "emailgateway@zulip.com",
            "notification-bot@zulip.com",
            "welcome-bot@zulip.com",
        ]

        expected_dicts = [user_row(email) for email in expected_emails]

        with self.assert_database_query_count(1):
            actual_dicts = get_cross_realm_dicts()

        self.assertEqual(actual_dicts, expected_dicts)

        # Now it should be cached.
        with self.assert_database_query_count(0, keep_cache_warm=True):
            actual_dicts = get_cross_realm_dicts()

        self.assertEqual(actual_dicts, expected_dicts)

        # Test cache invalidation
        welcome_bot = UserProfile.objects.get(email="welcome-bot@zulip.com")
        welcome_bot.full_name = "fred"
        welcome_bot.save()

        with self.assert_database_query_count(1, keep_cache_warm=True):
            actual_dicts = get_cross_realm_dicts()

        expected_dicts = [user_row(email) for email in expected_emails]
        self.assertEqual(actual_dicts, expected_dicts)

    def test_get_user_subscription_status(self) -> None:
        self.login("hamlet")
        iago = self.example_user("iago")
        stream = get_stream("Rome", iago.realm)

        # Invalid user ID.
        result = self.client_get(f"/json/users/25/subscriptions/{stream.id}")
        self.assert_json_error(result, "No such user")

        # Invalid stream ID.
        result = self.client_get(f"/json/users/{iago.id}/subscriptions/25")
        self.assert_json_error(result, "Invalid channel ID")

        result = orjson.loads(
            self.client_get(f"/json/users/{iago.id}/subscriptions/{stream.id}").content
        )
        self.assertFalse(result["is_subscribed"])

        # Subscribe to the stream.
        self.subscribe(iago, stream.name)
        with self.assert_database_query_count(7):
            result = orjson.loads(
                self.client_get(f"/json/users/{iago.id}/subscriptions/{stream.id}").content
            )

        self.assertTrue(result["is_subscribed"])

        # Logging in with a Guest user.
        polonius = self.example_user("polonius")
        self.login("polonius")
        self.assertTrue(polonius.is_guest)
        self.assertTrue(stream.is_web_public)

        result = orjson.loads(
            self.client_get(f"/json/users/{iago.id}/subscriptions/{stream.id}").content
        )
        self.assertTrue(result["is_subscribed"])

        # Test case when guest cannot access all users in the realm.
        self.set_up_db_for_testing_user_access()
        cordelia = self.example_user("cordelia")
        result = self.client_get(f"/json/users/{cordelia.id}/subscriptions/{stream.id}")
        self.assert_json_error(result, "Insufficient permission")

        result = orjson.loads(
            self.client_get(f"/json/users/{iago.id}/subscriptions/{stream.id}").content
        )
        self.assertTrue(result["is_subscribed"])

        self.login("iago")
        stream = self.make_stream("private_stream", invite_only=True)
        # Unsubscribed admin can check subscription status in a private stream.
        result = orjson.loads(
            self.client_get(f"/json/users/{iago.id}/subscriptions/{stream.id}").content
        )
        self.assertFalse(result["is_subscribed"])

        # Unsubscribed non-admins cannot check subscription status in a private stream.
        self.login("shiva")
        result = self.client_get(f"/json/users/{iago.id}/subscriptions/{stream.id}")
        self.assert_json_error(result, "Invalid channel ID")

        # Subscribed non-admins can check subscription status in a private stream
        self.subscribe(self.example_user("shiva"), stream.name)
        result = orjson.loads(
            self.client_get(f"/json/users/{iago.id}/subscriptions/{stream.id}").content
        )
        self.assertFalse(result["is_subscribed"])


class ActivateTest(ZulipTestCase):
    def test_basics(self) -> None:
        user = self.example_user("hamlet")
        do_deactivate_user(user, acting_user=None)
        self.assertFalse(user.is_active)
        do_reactivate_user(user, acting_user=None)
        self.assertTrue(user.is_active)

    def test_subscriptions_is_user_active(self) -> None:
        user = self.example_user("hamlet")
        do_deactivate_user(user, acting_user=None)
        self.assertFalse(user.is_active)
        self.assertTrue(Subscription.objects.filter(user_profile=user).exists())
        self.assertFalse(
            Subscription.objects.filter(user_profile=user, is_user_active=True).exists()
        )

        do_reactivate_user(user, acting_user=None)
        self.assertTrue(user.is_active)
        self.assertTrue(Subscription.objects.filter(user_profile=user).exists())
        self.assertFalse(
            Subscription.objects.filter(user_profile=user, is_user_active=False).exists()
        )

    def test_api(self) -> None:
        admin = self.example_user("othello")
        do_change_user_role(admin, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        self.login("othello")

        user = self.example_user("hamlet")
        self.assertTrue(user.is_active)

        result = self.client_delete(f"/json/users/{user.id}")
        self.assert_json_success(result)
        user = self.example_user("hamlet")
        self.assertFalse(user.is_active)

        result = self.client_post(f"/json/users/{user.id}/reactivate")
        self.assert_json_success(result)
        user = self.example_user("hamlet")
        self.assertTrue(user.is_active)

    def test_email_sent(self) -> None:
        self.login("iago")
        user = self.example_user("hamlet")

        # Verify no email sent by default.
        result = self.client_delete(f"/json/users/{user.id}", dict())
        self.assert_json_success(result)
        from django.core.mail import outbox

        self.assert_length(outbox, 0)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        # Reactivate user
        do_reactivate_user(user, acting_user=None)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        # Verify no email sent by default.
        result = self.client_delete(
            f"/json/users/{user.id}",
            dict(
                deactivation_notification_comment="Dear Hamlet,\nyou just got deactivated.",
            ),
        )
        self.assert_json_success(result)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        self.assert_length(outbox, 1)
        msg = outbox[0]
        self.assertEqual(msg.subject, "Notification of account deactivation on Zulip Dev")
        self.assert_length(msg.reply_to, 1)
        self.assertEqual(msg.reply_to[0], "noreply@testserver")
        self.assertIn("Dear Hamlet,", msg.body)

    def test_api_with_nonexistent_user(self) -> None:
        self.login("iago")

        # Organization administrator cannot deactivate organization owner.
        result = self.client_delete(f'/json/users/{self.example_user("desdemona").id}')
        self.assert_json_error(result, "Must be an organization owner")

        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")
        do_change_user_role(iago, UserProfile.ROLE_REALM_OWNER, acting_user=None)

        # Cannot deactivate a user with the bot api
        result = self.client_delete("/json/bots/{}".format(self.example_user("hamlet").id))
        self.assert_json_error(result, "No such bot")

        # Cannot deactivate a nonexistent user.
        invalid_user_id = 1000
        result = self.client_delete(f"/json/users/{invalid_user_id}")
        self.assert_json_error(result, "No such user")

        result = self.client_delete("/json/users/{}".format(self.example_user("webhook_bot").id))
        self.assert_json_error(result, "No such user")

        result = self.client_delete(f"/json/users/{desdemona.id}")
        self.assert_json_success(result)

        result = self.client_delete(f"/json/users/{iago.id}")
        self.assert_json_error(result, "Cannot deactivate the only organization owner")

        # Cannot reactivate a nonexistent user.
        invalid_user_id = 1000
        result = self.client_post(f"/json/users/{invalid_user_id}/reactivate")
        self.assert_json_error(result, "No such user")

    def test_api_with_mirrordummy_user(self) -> None:
        self.login("iago")
        desdemona = self.example_user("desdemona")
        change_user_is_active(desdemona, False)

        desdemona.is_mirror_dummy = True
        desdemona.save(update_fields=["is_mirror_dummy"])

        # Cannot deactivate a user which is marked as "mirror dummy" from importing
        result = self.client_post(f"/json/users/{desdemona.id}/reactivate")
        self.assert_json_error(
            result, "Cannot activate a placeholder account; ask the user to sign up, instead."
        )

    def test_api_with_insufficient_permissions(self) -> None:
        non_admin = self.example_user("othello")
        do_change_user_role(non_admin, UserProfile.ROLE_MEMBER, acting_user=None)
        self.login("othello")

        # Cannot deactivate a user with the users api
        result = self.client_delete("/json/users/{}".format(self.example_user("hamlet").id))
        self.assert_json_error(result, "Insufficient permission")

        # Cannot reactivate a user
        result = self.client_post(
            "/json/users/{}/reactivate".format(self.example_user("hamlet").id)
        )
        self.assert_json_error(result, "Insufficient permission")

    def test_revoke_invites(self) -> None:
        """
        Verify that any invitations generated by the user get revoked
        when the user is deactivated
        """
        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")

        invite_expires_in_minutes = 2 * 24 * 60
        with self.captureOnCommitCallbacks(execute=True):
            do_invite_users(
                iago,
                ["new1@zulip.com", "new2@zulip.com"],
                [],
                invite_expires_in_minutes=invite_expires_in_minutes,
                invite_as=PreregistrationUser.INVITE_AS["REALM_ADMIN"],
            )
            do_invite_users(
                desdemona,
                ["new3@zulip.com", "new4@zulip.com"],
                [],
                invite_expires_in_minutes=invite_expires_in_minutes,
                invite_as=PreregistrationUser.INVITE_AS["REALM_ADMIN"],
            )

            do_invite_users(
                iago,
                ["new5@zulip.com"],
                [],
                invite_expires_in_minutes=None,
                invite_as=PreregistrationUser.INVITE_AS["REALM_ADMIN"],
            )
            do_invite_users(
                desdemona,
                ["new6@zulip.com"],
                [],
                invite_expires_in_minutes=None,
                invite_as=PreregistrationUser.INVITE_AS["REALM_ADMIN"],
            )

        iago_multiuse_key = do_create_multiuse_invite_link(
            iago, PreregistrationUser.INVITE_AS["MEMBER"], invite_expires_in_minutes
        ).split("/")[-2]
        desdemona_multiuse_key = do_create_multiuse_invite_link(
            desdemona, PreregistrationUser.INVITE_AS["MEMBER"], invite_expires_in_minutes
        ).split("/")[-2]

        iago_never_expire_multiuse_key = do_create_multiuse_invite_link(
            iago, PreregistrationUser.INVITE_AS["MEMBER"], None
        ).split("/")[-2]
        desdemona_never_expire_multiuse_key = do_create_multiuse_invite_link(
            desdemona, PreregistrationUser.INVITE_AS["MEMBER"], None
        ).split("/")[-2]

        self.assertEqual(
            filter_to_valid_prereg_users(
                PreregistrationUser.objects.filter(referred_by=iago)
            ).count(),
            3,
        )
        self.assertEqual(
            filter_to_valid_prereg_users(
                PreregistrationUser.objects.filter(referred_by=desdemona)
            ).count(),
            3,
        )
        self.assertTrue(
            assert_is_not_none(
                Confirmation.objects.get(confirmation_key=iago_multiuse_key).expiry_date
            )
            > timezone_now()
        )
        self.assertTrue(
            assert_is_not_none(
                Confirmation.objects.get(confirmation_key=desdemona_multiuse_key).expiry_date
            )
            > timezone_now()
        )
        self.assertIsNone(
            Confirmation.objects.get(confirmation_key=iago_never_expire_multiuse_key).expiry_date
        )
        self.assertIsNone(
            Confirmation.objects.get(
                confirmation_key=desdemona_never_expire_multiuse_key
            ).expiry_date
        )

        do_deactivate_user(iago, acting_user=None)

        # Now we verify that invitations generated by iago were revoked, while desdemona's
        # remain valid.
        self.assertEqual(
            filter_to_valid_prereg_users(
                PreregistrationUser.objects.filter(referred_by=iago)
            ).count(),
            0,
        )
        self.assertEqual(
            filter_to_valid_prereg_users(
                PreregistrationUser.objects.filter(referred_by=desdemona)
            ).count(),
            3,
        )
        self.assertTrue(
            assert_is_not_none(
                Confirmation.objects.get(confirmation_key=iago_multiuse_key).expiry_date
            )
            <= timezone_now()
        )
        self.assertTrue(
            assert_is_not_none(
                Confirmation.objects.get(confirmation_key=desdemona_multiuse_key).expiry_date
            )
            > timezone_now()
        )
        self.assertTrue(
            assert_is_not_none(
                Confirmation.objects.get(
                    confirmation_key=iago_never_expire_multiuse_key
                ).expiry_date
            )
            <= timezone_now()
        )
        self.assertIsNone(
            Confirmation.objects.get(
                confirmation_key=desdemona_never_expire_multiuse_key
            ).expiry_date
        )

    def test_clear_sessions(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        session_key = self.client.session.session_key
        self.assertTrue(session_key)

        result = self.client_get("/json/users")
        self.assert_json_success(result)
        self.assertEqual(Session.objects.filter(pk=session_key).count(), 1)

        with self.captureOnCommitCallbacks(execute=True):
            do_deactivate_user(user, acting_user=None)
        self.assertEqual(Session.objects.filter(pk=session_key).count(), 0)

        result = self.client_get("/json/users")
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", 401
        )

    def test_clear_scheduled_jobs(self) -> None:
        user = self.example_user("hamlet")
        send_future_email(
            "zerver/emails/onboarding_zulip_topics",
            user.realm,
            to_user_ids=[user.id],
            delay=timedelta(hours=1),
        )
        self.assertEqual(ScheduledEmail.objects.count(), 1)
        do_deactivate_user(user, acting_user=None)
        self.assertEqual(ScheduledEmail.objects.count(), 0)

    def test_send_future_email_with_multiple_recipients(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        send_future_email(
            "zerver/emails/onboarding_zulip_topics",
            iago.realm,
            to_user_ids=[hamlet.id, iago.id],
            delay=timedelta(hours=1),
        )
        self.assertEqual(
            ScheduledEmail.objects.filter(users__in=[hamlet, iago]).distinct().count(), 1
        )
        email = ScheduledEmail.objects.all().first()
        assert email is not None and email.users is not None
        self.assertEqual(email.users.count(), 2)

    def test_clear_schedule_emails(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        send_future_email(
            "zerver/emails/onboarding_zulip_topics",
            iago.realm,
            to_user_ids=[hamlet.id, iago.id],
            delay=timedelta(hours=1),
        )
        self.assertEqual(ScheduledEmail.objects.count(), 1)
        clear_scheduled_emails(hamlet.id)
        self.assertEqual(ScheduledEmail.objects.count(), 1)
        self.assertEqual(ScheduledEmail.objects.filter(users=hamlet).count(), 0)
        self.assertEqual(ScheduledEmail.objects.filter(users=iago).count(), 1)

    def test_deliver_scheduled_emails(self) -> None:
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        send_future_email(
            "zerver/emails/onboarding_zulip_topics",
            iago.realm,
            to_user_ids=[hamlet.id, iago.id],
            delay=timedelta(hours=1),
        )
        self.assertEqual(ScheduledEmail.objects.count(), 1)
        email = ScheduledEmail.objects.all().first()
        deliver_scheduled_emails(assert_is_not_none(email))
        from django.core.mail import outbox

        self.assert_length(outbox, 1)
        for message in outbox:
            self.assertEqual(
                set(message.to),
                {
                    str(Address(display_name=hamlet.full_name, addr_spec=hamlet.delivery_email)),
                    str(Address(display_name=iago.full_name, addr_spec=iago.delivery_email)),
                },
            )
        self.assertEqual(ScheduledEmail.objects.count(), 0)

    def test_deliver_scheduled_emails_no_addressees(self) -> None:
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        to_user_ids = [hamlet.id, iago.id]
        send_future_email(
            "zerver/emails/onboarding_zulip_topics",
            iago.realm,
            to_user_ids=to_user_ids,
            delay=timedelta(hours=1),
        )
        self.assertEqual(ScheduledEmail.objects.count(), 1)
        email = ScheduledEmail.objects.all().first()
        assert email is not None
        email.users.remove(*to_user_ids)

        email_id = email.id
        scheduled_at = email.scheduled_timestamp
        with self.assertLogs("zulip.send_email", level="INFO") as info_log:
            deliver_scheduled_emails(email)
        from django.core.mail import outbox

        self.assert_length(outbox, 0)
        self.assertEqual(ScheduledEmail.objects.count(), 0)
        self.assertEqual(
            info_log.output,
            [
                f"WARNING:zulip.send_email:ScheduledEmail {email_id} at {scheduled_at} "
                "had empty users and address attributes: "
                "{'template_prefix': 'zerver/emails/onboarding_zulip_topics', 'from_name': None, "
                "'from_address': None, 'language': None, 'context': {}}"
            ],
        )


class RecipientInfoTest(ZulipTestCase):
    def test_stream_recipient_info(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        # These tests were written with the old default for
        # enable_online_push_notifications; that default is better for
        # testing the full code path anyway.
        for user in [hamlet, cordelia, othello]:
            do_change_user_setting(
                user, "enable_online_push_notifications", False, acting_user=None
            )

        realm = hamlet.realm

        stream_name = "Test stream"
        topic_name = "test topic"

        for user in [hamlet, cordelia, othello]:
            self.subscribe(user, stream_name)

        stream = get_stream(stream_name, realm)
        recipient = stream.recipient
        assert recipient is not None

        stream_topic = StreamTopicTarget(
            stream_id=stream.id,
            topic_name=topic_name,
        )

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_topic_wildcard_mention=False,
            possible_stream_wildcard_mention=False,
        )

        all_user_ids = {hamlet.id, cordelia.id, othello.id}

        expected_info = RecipientInfoResult(
            active_user_ids=all_user_ids,
            online_push_user_ids=set(),
            dm_mention_email_disabled_user_ids=set(),
            dm_mention_push_disabled_user_ids=set(),
            stream_push_user_ids=set(),
            stream_email_user_ids=set(),
            topic_wildcard_mention_user_ids=set(),
            stream_wildcard_mention_user_ids=set(),
            followed_topic_push_user_ids=set(),
            followed_topic_email_user_ids=set(),
            topic_wildcard_mention_in_followed_topic_user_ids=set(),
            stream_wildcard_mention_in_followed_topic_user_ids=set(),
            muted_sender_user_ids=set(),
            um_eligible_user_ids=all_user_ids,
            long_term_idle_user_ids=set(),
            default_bot_user_ids=set(),
            service_bot_tuples=[],
            all_bot_user_ids=set(),
            topic_participant_user_ids=set(),
            sender_muted_stream=False,
        )

        self.assertEqual(info, expected_info)

        do_change_user_setting(
            hamlet, "enable_offline_email_notifications", False, acting_user=None
        )
        do_change_user_setting(hamlet, "enable_offline_push_notifications", False, acting_user=None)
        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_stream_wildcard_mention=False,
        )
        self.assertEqual(info.dm_mention_email_disabled_user_ids, {hamlet.id})
        self.assertEqual(info.dm_mention_push_disabled_user_ids, {hamlet.id})
        do_change_user_setting(hamlet, "enable_offline_email_notifications", True, acting_user=None)
        do_change_user_setting(hamlet, "enable_offline_push_notifications", True, acting_user=None)

        do_change_user_setting(cordelia, "wildcard_mentions_notify", False, acting_user=None)
        do_change_user_setting(hamlet, "enable_stream_push_notifications", True, acting_user=None)
        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_stream_wildcard_mention=False,
        )
        self.assertEqual(info.stream_push_user_ids, {hamlet.id})
        self.assertEqual(info.stream_wildcard_mention_user_ids, set())

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_stream_wildcard_mention=True,
        )
        self.assertEqual(info.stream_wildcard_mention_user_ids, {hamlet.id, othello.id})

        do_change_user_setting(
            hamlet,
            "wildcard_mentions_notify",
            True,
            acting_user=None,
        )
        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_topic_wildcard_mention=True,
            possible_stream_wildcard_mention=False,
        )
        self.assertEqual(info.stream_wildcard_mention_user_ids, set())
        self.assertEqual(info.topic_wildcard_mention_user_ids, {hamlet.id})

        # User who sent a message to the topic, or reacted to a message on the topic
        # is only considered as a possible user to be notified for topic mention.
        self.send_stream_message(
            othello, stream_name, content="test message", topic_name=topic_name
        )
        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_topic_wildcard_mention=True,
            possible_stream_wildcard_mention=False,
        )
        self.assertEqual(info.stream_wildcard_mention_user_ids, set())
        self.assertEqual(info.topic_wildcard_mention_user_ids, {hamlet.id, othello.id})

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_topic_wildcard_mention=False,
            possible_stream_wildcard_mention=True,
        )
        self.assertEqual(info.stream_wildcard_mention_user_ids, {hamlet.id, othello.id})
        self.assertEqual(info.topic_wildcard_mention_user_ids, set())

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_topic_wildcard_mention=True,
            possible_stream_wildcard_mention=True,
        )
        self.assertEqual(info.stream_wildcard_mention_user_ids, {hamlet.id, othello.id})
        self.assertEqual(info.topic_wildcard_mention_user_ids, {hamlet.id, othello.id})

        sub = get_subscription(stream_name, hamlet)
        sub.push_notifications = False
        sub.save()
        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
        )
        self.assertEqual(info.stream_push_user_ids, set())

        do_change_user_setting(hamlet, "enable_stream_push_notifications", False, acting_user=None)
        sub = get_subscription(stream_name, hamlet)
        sub.push_notifications = True
        sub.save()
        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
        )
        self.assertEqual(info.stream_push_user_ids, {hamlet.id})

        # Now have Hamlet mute the stream and unmute the topic,
        # which shouldn't omit him from stream_push_user_ids.
        sub.is_muted = True
        sub.save()

        do_set_user_topic_visibility_policy(
            hamlet,
            stream,
            topic_name,
            visibility_policy=UserTopic.VisibilityPolicy.UNMUTED,
        )

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
        )
        self.assertEqual(info.stream_push_user_ids, {hamlet.id})

        # Now unmute the stream and remove topic visibility_policy.
        sub.is_muted = False
        sub.save()
        do_set_user_topic_visibility_policy(
            hamlet, stream, topic_name, visibility_policy=UserTopic.VisibilityPolicy.INHERIT
        )

        # Now have Hamlet mute the topic to omit him from stream_push_user_ids.
        do_set_user_topic_visibility_policy(
            hamlet,
            stream,
            topic_name,
            visibility_policy=UserTopic.VisibilityPolicy.MUTED,
        )

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_stream_wildcard_mention=False,
        )
        self.assertEqual(info.stream_push_user_ids, set())
        self.assertEqual(info.stream_wildcard_mention_user_ids, set())

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_stream_wildcard_mention=True,
        )
        self.assertEqual(info.stream_push_user_ids, set())
        # Since Hamlet has muted the stream and Cordelia has disabled
        # wildcard notifications, it should just be Othello here.
        self.assertEqual(info.stream_wildcard_mention_user_ids, {othello.id})

        # If Hamlet mutes Cordelia, he should be in `muted_sender_user_ids` for a message
        # sent by Cordelia.
        do_mute_user(hamlet, cordelia)
        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=cordelia.id,
            stream_topic=stream_topic,
            possible_stream_wildcard_mention=True,
        )
        self.assertTrue(hamlet.id in info.muted_sender_user_ids)

        sub = get_subscription(stream_name, othello)
        sub.wildcard_mentions_notify = False
        sub.save()

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_stream_wildcard_mention=True,
        )
        self.assertEqual(info.stream_push_user_ids, set())
        # Verify that stream-level wildcard_mentions_notify=False works correctly.
        self.assertEqual(info.stream_wildcard_mention_user_ids, set())

        # Verify that True works as expected as well
        sub = get_subscription(stream_name, othello)
        sub.wildcard_mentions_notify = True
        sub.save()

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possible_stream_wildcard_mention=True,
        )
        self.assertEqual(info.stream_push_user_ids, set())
        self.assertEqual(info.stream_wildcard_mention_user_ids, {othello.id})

        # Add a service bot.
        service_bot = do_create_user(
            email="service-bot@zulip.com",
            password="",
            realm=realm,
            full_name="",
            bot_type=UserProfile.EMBEDDED_BOT,
            acting_user=None,
        )

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possibly_mentioned_user_ids={service_bot.id},
        )
        self.assertEqual(
            info.service_bot_tuples,
            [
                (service_bot.id, UserProfile.EMBEDDED_BOT),
            ],
        )

        # Add a normal bot.
        normal_bot = do_create_user(
            email="normal-bot@zulip.com",
            password="",
            realm=realm,
            full_name="",
            bot_type=UserProfile.DEFAULT_BOT,
            acting_user=None,
        )

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possibly_mentioned_user_ids={service_bot.id, normal_bot.id},
        )
        self.assertEqual(info.default_bot_user_ids, {normal_bot.id})
        self.assertEqual(info.all_bot_user_ids, {normal_bot.id, service_bot.id})

        # Now Hamlet follows the topic with the 'followed_topic_email_notifications',
        # 'followed_topic_push_notifications' and 'followed_topic_wildcard_mention_notify'
        # global settings enabled by default.
        do_set_user_topic_visibility_policy(
            hamlet,
            stream,
            topic_name,
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
        )
        self.assertEqual(info.followed_topic_email_user_ids, {hamlet.id})
        self.assertEqual(info.followed_topic_push_user_ids, {hamlet.id})
        self.assertEqual(info.stream_wildcard_mention_in_followed_topic_user_ids, {hamlet.id})

        # Omit Hamlet from followed_topic_email_user_ids
        do_change_user_setting(
            hamlet,
            "enable_followed_topic_email_notifications",
            False,
            acting_user=None,
        )
        # Omit Hamlet from followed_topic_push_user_ids
        do_change_user_setting(
            hamlet,
            "enable_followed_topic_push_notifications",
            False,
            acting_user=None,
        )
        # Omit Hamlet from stream_wildcard_mention_in_followed_topic_user_ids
        do_change_user_setting(
            hamlet,
            "enable_followed_topic_wildcard_mentions_notify",
            False,
            acting_user=None,
        )

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
        )
        self.assertEqual(info.followed_topic_email_user_ids, set())
        self.assertEqual(info.followed_topic_push_user_ids, set())
        self.assertEqual(info.stream_wildcard_mention_in_followed_topic_user_ids, set())

    def test_get_recipient_info_invalid_recipient_type(self) -> None:
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        stream = get_stream("Rome", realm)
        stream_topic = StreamTopicTarget(
            stream_id=stream.id,
            topic_name="test topic",
        )

        # Make sure get_recipient_info asserts on invalid recipient types
        with self.assertRaisesRegex(ValueError, "Bad recipient type"):
            invalid_recipient = Recipient(type=999)  # 999 is not a valid type
            get_recipient_info(
                realm_id=realm.id,
                recipient=invalid_recipient,
                sender_id=hamlet.id,
                stream_topic=stream_topic,
            )


class BulkUsersTest(ZulipTestCase):
    def test_client_gravatar_option(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()
        self.login("cordelia")

        hamlet = self.example_user("hamlet")

        def get_hamlet_avatar(client_gravatar: bool) -> Optional[str]:
            data = dict(client_gravatar=orjson.dumps(client_gravatar).decode())
            result = self.client_get("/json/users", data)
            rows = self.assert_json_success(result)["members"]
            [hamlet_data] = (row for row in rows if row["user_id"] == hamlet.id)
            return hamlet_data["avatar_url"]

        self.assertEqual(
            get_hamlet_avatar(client_gravatar=True),
            None,
        )

        """
        The main purpose of this test is to make sure we
        return None for avatar_url when client_gravatar is
        set to True.  And we do a sanity check for when it's
        False, but we leave it to other tests to validate
        the specific URL.
        """
        self.assertIn(
            "gravatar.com",
            assert_is_not_none(get_hamlet_avatar(client_gravatar=False)),
        )


class GetProfileTest(ZulipTestCase):
    def test_cache_behavior(self) -> None:
        """Tests whether fetching a user object the normal way, with
        `get_user`, makes 1 cache query and 1 database query.
        """
        realm = get_realm("zulip")
        email = self.example_user("hamlet").email
        with self.assert_database_query_count(1):
            with simulated_empty_cache() as cache_queries:
                user_profile = get_user(email, realm)

        self.assert_length(cache_queries, 1)
        self.assertEqual(user_profile.email, email)

    def test_get_user_profile(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")
        shiva = self.example_user("shiva")
        self.login("hamlet")
        result = orjson.loads(self.client_get("/json/users/me").content)
        self.assertEqual(result["email"], hamlet.email)
        self.assertEqual(result["full_name"], "King Hamlet")
        self.assertIn("user_id", result)
        self.assertFalse(result["is_bot"])
        self.assertFalse(result["is_admin"])
        self.assertFalse(result["is_owner"])
        self.assertFalse(result["is_guest"])
        self.assertEqual(result["role"], UserProfile.ROLE_MEMBER)
        self.assertEqual(result["delivery_email"], hamlet.delivery_email)
        self.login("iago")
        result = orjson.loads(self.client_get("/json/users/me").content)
        self.assertEqual(result["email"], iago.email)
        self.assertEqual(result["full_name"], "Iago")
        self.assertFalse(result["is_bot"])
        self.assertTrue(result["is_admin"])
        self.assertFalse(result["is_owner"])
        self.assertFalse(result["is_guest"])
        self.assertEqual(result["role"], UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login("desdemona")
        result = orjson.loads(self.client_get("/json/users/me").content)
        self.assertEqual(result["email"], desdemona.email)
        self.assertFalse(result["is_bot"])
        self.assertTrue(result["is_admin"])
        self.assertTrue(result["is_owner"])
        self.assertFalse(result["is_guest"])
        self.assertEqual(result["role"], UserProfile.ROLE_REALM_OWNER)
        self.login("shiva")
        result = orjson.loads(self.client_get("/json/users/me").content)
        self.assertEqual(result["email"], shiva.email)
        self.assertFalse(result["is_bot"])
        self.assertFalse(result["is_admin"])
        self.assertFalse(result["is_owner"])
        self.assertFalse(result["is_guest"])
        self.assertEqual(result["role"], UserProfile.ROLE_MODERATOR)

        # Tests the GET ../users/{id} API endpoint.
        user = self.example_user("hamlet")
        result = orjson.loads(self.client_get(f"/json/users/{user.id}").content)
        self.assertEqual(result["user"]["email"], user.email)
        self.assertEqual(result["user"]["full_name"], user.full_name)
        self.assertIn("user_id", result["user"])
        self.assertNotIn("profile_data", result["user"])
        self.assertFalse(result["user"]["is_bot"])
        self.assertFalse(result["user"]["is_admin"])
        self.assertFalse(result["user"]["is_owner"])

        result = orjson.loads(
            self.client_get(
                f"/json/users/{user.id}", {"include_custom_profile_fields": "true"}
            ).content
        )

        self.assertIn("profile_data", result["user"])
        result = self.client_get("/json/users/30")
        self.assert_json_error(result, "No such user")

        bot = self.example_user("default_bot")
        result = orjson.loads(self.client_get(f"/json/users/{bot.id}").content)
        self.assertEqual(result["user"]["email"], bot.email)
        self.assertTrue(result["user"]["is_bot"])

    def test_get_user_by_email(self) -> None:
        user = self.example_user("hamlet")
        self.login("hamlet")
        result = orjson.loads(self.client_get(f"/json/users/{user.email}").content)

        self.assertEqual(result["user"]["email"], user.email)

        self.assertEqual(result["user"]["full_name"], user.full_name)
        self.assertIn("user_id", result["user"])
        self.assertNotIn("profile_data", result["user"])
        self.assertFalse(result["user"]["is_bot"])
        self.assertFalse(result["user"]["is_admin"])
        self.assertFalse(result["user"]["is_owner"])

        result = orjson.loads(
            self.client_get(
                f"/json/users/{user.email}", {"include_custom_profile_fields": "true"}
            ).content
        )
        self.assertIn("profile_data", result["user"])

        result = self.client_get("/json/users/invalid")
        self.assert_json_error(result, "No such user")

        bot = self.example_user("default_bot")
        result = orjson.loads(self.client_get(f"/json/users/{bot.email}").content)
        self.assertEqual(result["user"]["email"], bot.email)
        self.assertTrue(result["user"]["is_bot"])

    def test_get_all_profiles_avatar_urls(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.api_get(
            hamlet, "/api/v1/users", {"client_gravatar": orjson.dumps(False).decode()}
        )
        response_dict = self.assert_json_success(result)

        (my_user,) = (user for user in response_dict["members"] if user["email"] == hamlet.email)

        self.assertEqual(
            my_user["avatar_url"],
            avatar_url(hamlet),
        )

    def test_user_email_according_to_email_address_visibility_setting(self) -> None:
        hamlet = self.example_user("hamlet")

        do_change_user_setting(
            hamlet,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY,
            acting_user=None,
        )

        # Check that even admin cannot access email when setting is set to
        # EMAIL_ADDRESS_VISIBILITY_NOBODY.
        self.login("iago")
        result = orjson.loads(self.client_get(f"/json/users/{hamlet.id}").content)
        self.assertEqual(result["user"].get("delivery_email"), None)
        self.assertEqual(result["user"].get("email"), f"user{hamlet.id}@zulip.testserver")

        do_change_user_setting(
            hamlet,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            acting_user=None,
        )

        # Check that admin can access email when setting is set to
        # EMAIL_ADDRESS_VISIBILITY_ADMINS.
        result = orjson.loads(self.client_get(f"/json/users/{hamlet.id}").content)
        self.assertEqual(result["user"].get("delivery_email"), hamlet.delivery_email)
        self.assertEqual(result["user"].get("email"), f"user{hamlet.id}@zulip.testserver")

        # Check that moderator cannot access email when setting is set to
        # EMAIL_ADDRESS_VISIBILITY_ADMINS.
        self.login("shiva")
        result = orjson.loads(self.client_get(f"/json/users/{hamlet.id}").content)
        self.assertEqual(result["user"].get("delivery_email"), None)
        self.assertEqual(result["user"].get("email"), f"user{hamlet.id}@zulip.testserver")

        do_change_user_setting(
            hamlet,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_MODERATORS,
            acting_user=None,
        )

        # Check that moderator can access email when setting is set to
        # EMAIL_ADDRESS_VISIBILITY_MODERATORS.
        result = orjson.loads(self.client_get(f"/json/users/{hamlet.id}").content)
        self.assertEqual(result["user"].get("delivery_email"), hamlet.delivery_email)
        self.assertEqual(result["user"].get("email"), f"user{hamlet.id}@zulip.testserver")

        # Check that normal user cannot access email when setting is set to
        # EMAIL_ADDRESS_VISIBILITY_MODERATORS.
        self.login("cordelia")
        result = orjson.loads(self.client_get(f"/json/users/{hamlet.id}").content)
        self.assertEqual(result["user"].get("delivery_email"), None)
        self.assertEqual(result["user"].get("email"), f"user{hamlet.id}@zulip.testserver")

        do_change_user_setting(
            hamlet,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_MEMBERS,
            acting_user=None,
        )

        # Check that normal user can access email when setting is set to
        # EMAIL_ADDRESS_VISIBILITY_MEMBERS.
        result = orjson.loads(self.client_get(f"/json/users/{hamlet.id}").content)
        self.assertEqual(result["user"].get("delivery_email"), hamlet.delivery_email)
        self.assertEqual(result["user"].get("email"), f"user{hamlet.id}@zulip.testserver")

        # Check that guest cannot access email when setting is set to
        # EMAIL_ADDRESS_VISIBILITY_MEMBERS.
        self.login("polonius")
        result = orjson.loads(self.client_get(f"/json/users/{hamlet.id}").content)
        self.assertEqual(result["user"].get("delivery_email"), None)
        self.assertEqual(result["user"].get("email"), f"user{hamlet.id}@zulip.testserver")

        do_change_user_setting(
            hamlet,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=None,
        )

        # Check that moderator, member and guest all can access email when setting
        # is set to EMAIL_ADDRESS_VISIBILITY_EVERYONE.
        self.login("shiva")
        result = orjson.loads(self.client_get(f"/json/users/{hamlet.id}").content)
        self.assertEqual(result["user"].get("delivery_email"), hamlet.delivery_email)
        self.assertEqual(result["user"].get("email"), hamlet.delivery_email)

        self.login("cordelia")
        result = orjson.loads(self.client_get(f"/json/users/{hamlet.id}").content)
        self.assertEqual(result["user"].get("delivery_email"), hamlet.delivery_email)
        self.assertEqual(result["user"].get("email"), hamlet.delivery_email)

        self.login("polonius")
        result = orjson.loads(self.client_get(f"/json/users/{hamlet.id}").content)
        self.assertEqual(result["user"].get("delivery_email"), hamlet.delivery_email)
        self.assertEqual(result["user"].get("email"), hamlet.delivery_email)

    def test_restricted_access_to_users(self) -> None:
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")
        desdemona = self.example_user("desdemona")
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        prospero = self.example_user("prospero")
        aaron = self.example_user("aaron")
        shiva = self.example_user("shiva")
        zoe = self.example_user("ZOE")
        polonius = self.example_user("polonius")

        self.set_up_db_for_testing_user_access()

        self.login("polonius")
        with self.assert_database_query_count(9):
            result = orjson.loads(self.client_get("/json/users").content)
        accessible_users = [
            user
            for user in result["members"]
            if user["full_name"] != UserProfile.INACCESSIBLE_USER_NAME
        ]
        # The user can access 3 bot users and 7 human users.
        self.assert_length(accessible_users, 10)
        accessible_human_users = [user for user in accessible_users if not user["is_bot"]]
        # The user can access the following 7 human users -
        # 1. Hamlet and Iago - they are subscribed to common streams.
        # 2. Prospero - Because Polonius sent a DM to Prospero when
        # they were allowed to access all users.
        # 3. Aaron and Zoe - Because they are particapting in a
        # group DM with Polonius.
        # 4. Shiva - Because Shiva sent a DM to Polonius.
        # 5. Polonius - A user can obviously access themselves.
        self.assert_length(accessible_human_users, 7)
        accessible_user_ids = [user["user_id"] for user in accessible_human_users]
        self.assertCountEqual(
            accessible_user_ids,
            [polonius.id, hamlet.id, iago.id, prospero.id, aaron.id, zoe.id, shiva.id],
        )

        inaccessible_users = [
            user
            for user in result["members"]
            if user["full_name"] == UserProfile.INACCESSIBLE_USER_NAME
        ]
        inaccessible_user_ids = [user["user_id"] for user in inaccessible_users]
        self.assertCountEqual(inaccessible_user_ids, [cordelia.id, desdemona.id, othello.id])

        do_deactivate_user(hamlet, acting_user=None)
        do_deactivate_user(aaron, acting_user=None)
        do_deactivate_user(shiva, acting_user=None)
        result = orjson.loads(self.client_get("/json/users").content)
        accessible_users = [
            user
            for user in result["members"]
            if user["full_name"] != UserProfile.INACCESSIBLE_USER_NAME
        ]
        self.assert_length(accessible_users, 9)
        # Guests can only access those deactivated users who were involved in
        # DMs and not those who were subscribed to some common streams.
        accessible_human_users = [user for user in accessible_users if not user["is_bot"]]
        self.assert_length(accessible_human_users, 6)
        accessible_user_ids = [user["user_id"] for user in accessible_human_users]
        self.assertCountEqual(
            accessible_user_ids, [polonius.id, iago.id, prospero.id, aaron.id, zoe.id, shiva.id]
        )

        inaccessible_users = [
            user
            for user in result["members"]
            if user["full_name"] == UserProfile.INACCESSIBLE_USER_NAME
        ]
        inaccessible_user_ids = [user["user_id"] for user in inaccessible_users]
        self.assertCountEqual(
            inaccessible_user_ids, [cordelia.id, desdemona.id, othello.id, hamlet.id]
        )

    def test_get_user_with_restricted_access(self) -> None:
        polonius = self.example_user("polonius")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        iago = self.example_user("iago")
        prospero = self.example_user("prospero")
        aaron = self.example_user("aaron")
        zoe = self.example_user("ZOE")
        shiva = self.example_user("shiva")
        cordelia = self.example_user("cordelia")
        desdemona = self.example_user("desdemona")
        reset_email_visibility_to_everyone_in_zulip_realm()

        self.set_up_db_for_testing_user_access()

        self.login("polonius")

        accessible_users = [polonius, iago, shiva, hamlet, aaron, zoe, shiva, prospero]
        for user in accessible_users:
            result = self.client_get(f"/json/users/{user.id}")
            self.assert_json_success(result)
            user_dict = orjson.loads(result.content)["user"]
            self.assertEqual(user_dict["user_id"], user.id)
            self.assertEqual(user_dict["full_name"], user.full_name)
            self.assertEqual(user_dict["delivery_email"], user.delivery_email)

        # Guest user cannot access -
        # 1. othello, even though he sent a message to test_stream1
        # because he is not subscribed to the stream now.
        # 2. cordelia, because the guest user is not subscribed
        # to Verona anymore to which cordelia is subscribed.
        # 3. desdemona, because she is not subscribed to any
        # streams that the guest is subscribed to and is not
        # involved in any DMs with guest.
        inaccessible_users = [othello, cordelia, desdemona]
        for user in inaccessible_users:
            result = self.client_get(f"/json/users/{user.id}")
            self.assert_json_error(result, "Insufficient permission")

    def test_get_inaccessible_user_ids(self) -> None:
        polonius = self.example_user("polonius")
        bot = self.example_user("default_bot")
        othello = self.example_user("othello")
        shiva = self.example_user("shiva")
        hamlet = self.example_user("hamlet")
        prospero = self.example_user("prospero")

        inaccessible_user_ids = get_inaccessible_user_ids(
            [bot.id, hamlet.id, othello.id, shiva.id, prospero.id], polonius
        )
        self.assert_length(inaccessible_user_ids, 0)

        self.set_up_db_for_testing_user_access()
        polonius = self.example_user("polonius")

        inaccessible_user_ids = get_inaccessible_user_ids([bot.id], polonius)
        self.assert_length(inaccessible_user_ids, 0)

        inaccessible_user_ids = get_inaccessible_user_ids([bot.id, hamlet.id], polonius)
        self.assert_length(inaccessible_user_ids, 0)

        inaccessible_user_ids = get_inaccessible_user_ids([bot.id, hamlet.id, othello.id], polonius)
        self.assertEqual(inaccessible_user_ids, {othello.id})

        inaccessible_user_ids = get_inaccessible_user_ids(
            [bot.id, hamlet.id, othello.id, shiva.id, prospero.id], polonius
        )
        self.assertEqual(inaccessible_user_ids, {othello.id})


class DeleteUserTest(ZulipTestCase):
    def test_do_delete_user(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        hamlet_personal_recipient = hamlet.recipient
        hamlet_user_id = hamlet.id
        hamlet_date_joined = hamlet.date_joined

        self.send_personal_message(cordelia, hamlet)
        self.send_personal_message(hamlet, cordelia)

        personal_message_ids_to_hamlet = Message.objects.filter(
            realm_id=realm.id, recipient=hamlet_personal_recipient
        ).values_list("id", flat=True)
        self.assertGreater(len(personal_message_ids_to_hamlet), 0)
        self.assertTrue(Message.objects.filter(realm_id=realm.id, sender=hamlet).exists())

        huddle_message_ids_from_cordelia = [
            self.send_huddle_message(cordelia, [hamlet, othello]) for i in range(3)
        ]
        huddle_message_ids_from_hamlet = [
            self.send_huddle_message(hamlet, [cordelia, othello]) for i in range(3)
        ]

        huddle_with_hamlet_recipient_ids = list(
            Subscription.objects.filter(
                user_profile=hamlet, recipient__type=Recipient.DIRECT_MESSAGE_GROUP
            ).values_list("recipient_id", flat=True)
        )
        self.assertGreater(len(huddle_with_hamlet_recipient_ids), 0)

        do_delete_user(hamlet, acting_user=None)

        replacement_dummy_user = UserProfile.objects.get(id=hamlet_user_id, realm=realm)

        self.assertEqual(
            replacement_dummy_user.delivery_email, f"deleteduser{hamlet_user_id}@zulip.testserver"
        )
        self.assertEqual(replacement_dummy_user.is_mirror_dummy, True)
        self.assertEqual(replacement_dummy_user.is_active, False)
        self.assertEqual(replacement_dummy_user.date_joined, hamlet_date_joined)

        self.assertEqual(Message.objects.filter(id__in=personal_message_ids_to_hamlet).count(), 0)
        # Huddle messages from hamlet should have been deleted, but messages of other participants should
        # be kept.
        self.assertEqual(Message.objects.filter(id__in=huddle_message_ids_from_hamlet).count(), 0)
        self.assertEqual(Message.objects.filter(id__in=huddle_message_ids_from_cordelia).count(), 3)

        self.assertEqual(
            Message.objects.filter(realm_id=realm.id, sender_id=hamlet_user_id).count(), 0
        )

        # Verify that the dummy user is subscribed to the deleted user's huddles, to keep huddle data
        # in a correct state.
        for recipient_id in huddle_with_hamlet_recipient_ids:
            self.assertTrue(
                Subscription.objects.filter(
                    user_profile=replacement_dummy_user, recipient_id=recipient_id
                ).exists()
            )

    def test_do_delete_user_preserving_messages(self) -> None:
        """
        This test is extremely similar to the one for do_delete_user, with the only difference being
        that Messages are supposed to be preserved. All other effects should be identical.
        """

        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        hamlet_personal_recipient = hamlet.recipient
        hamlet_user_id = hamlet.id
        hamlet_date_joined = hamlet.date_joined

        self.send_personal_message(cordelia, hamlet)
        self.send_personal_message(hamlet, cordelia)

        personal_message_ids_to_hamlet = Message.objects.filter(
            realm_id=realm.id, recipient=hamlet_personal_recipient
        ).values_list("id", flat=True)
        self.assertGreater(len(personal_message_ids_to_hamlet), 0)
        self.assertTrue(Message.objects.filter(realm_id=realm.id, sender=hamlet).exists())

        huddle_message_ids_from_cordelia = [
            self.send_huddle_message(cordelia, [hamlet, othello]) for i in range(3)
        ]
        huddle_message_ids_from_hamlet = [
            self.send_huddle_message(hamlet, [cordelia, othello]) for i in range(3)
        ]

        huddle_with_hamlet_recipient_ids = list(
            Subscription.objects.filter(
                user_profile=hamlet, recipient__type=Recipient.DIRECT_MESSAGE_GROUP
            ).values_list("recipient_id", flat=True)
        )
        self.assertGreater(len(huddle_with_hamlet_recipient_ids), 0)

        original_messages_from_hamlet_count = Message.objects.filter(
            realm_id=realm.id, sender_id=hamlet_user_id
        ).count()
        self.assertGreater(original_messages_from_hamlet_count, 0)

        do_delete_user_preserving_messages(hamlet)

        replacement_dummy_user = UserProfile.objects.get(id=hamlet_user_id, realm=realm)

        self.assertEqual(
            replacement_dummy_user.delivery_email, f"deleteduser{hamlet_user_id}@zulip.testserver"
        )
        self.assertEqual(replacement_dummy_user.is_mirror_dummy, True)
        self.assertEqual(replacement_dummy_user.is_active, False)
        self.assertEqual(replacement_dummy_user.date_joined, hamlet_date_joined)

        # All messages should have been preserved:
        self.assertEqual(
            Message.objects.filter(id__in=personal_message_ids_to_hamlet).count(),
            len(personal_message_ids_to_hamlet),
        )
        self.assertEqual(
            Message.objects.filter(id__in=huddle_message_ids_from_hamlet).count(),
            len(huddle_message_ids_from_hamlet),
        )
        self.assertEqual(
            Message.objects.filter(id__in=huddle_message_ids_from_cordelia).count(),
            len(huddle_message_ids_from_cordelia),
        )

        self.assertEqual(
            Message.objects.filter(realm_id=realm.id, sender_id=hamlet_user_id).count(),
            original_messages_from_hamlet_count,
        )

        # Verify that the dummy user is subscribed to the deleted user's huddles, to keep huddle data
        # in a correct state.
        for recipient_id in huddle_with_hamlet_recipient_ids:
            self.assertTrue(
                Subscription.objects.filter(
                    user_profile=replacement_dummy_user, recipient_id=recipient_id
                ).exists()
            )


class FakeEmailDomainTest(ZulipTestCase):
    def test_get_fake_email_domain(self) -> None:
        realm = get_realm("zulip")
        self.assertEqual("zulip.testserver", get_fake_email_domain(realm.host))

        with self.settings(EXTERNAL_HOST="example.com"):
            self.assertEqual("zulip.example.com", get_fake_email_domain(realm.host))

    @override_settings(FAKE_EMAIL_DOMAIN="fakedomain.com", REALM_HOSTS={"zulip": "127.0.0.1"})
    def test_get_fake_email_domain_realm_host_is_ip_addr(self) -> None:
        realm = get_realm("zulip")
        self.assertEqual("fakedomain.com", get_fake_email_domain(realm.host))

    @override_settings(FAKE_EMAIL_DOMAIN="invaliddomain", REALM_HOSTS={"zulip": "127.0.0.1"})
    def test_invalid_fake_email_domain(self) -> None:
        realm = get_realm("zulip")
        with self.assertRaises(InvalidFakeEmailDomainError):
            get_fake_email_domain(realm.host)

    @override_settings(FAKE_EMAIL_DOMAIN="127.0.0.1", REALM_HOSTS={"zulip": "127.0.0.1"})
    def test_invalid_fake_email_domain_ip(self) -> None:
        with self.assertRaises(InvalidFakeEmailDomainError):
            realm = get_realm("zulip")
            get_fake_email_domain(realm.host)


class TestBulkRegenerateAPIKey(ZulipTestCase):
    def test_bulk_regenerate_api_keys(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        hamlet_old_api_key = hamlet.api_key
        cordelia_old_api_key = cordelia.api_key
        othello_old_api_key = othello.api_key

        bulk_regenerate_api_keys([hamlet.id, cordelia.id])

        hamlet.refresh_from_db()
        cordelia.refresh_from_db()
        othello.refresh_from_db()

        self.assertNotEqual(hamlet_old_api_key, hamlet.api_key)
        self.assertNotEqual(cordelia_old_api_key, cordelia.api_key)

        self.assertEqual(othello_old_api_key, othello.api_key)
