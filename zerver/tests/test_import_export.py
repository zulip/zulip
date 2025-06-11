import json
import os
import shutil
import uuid
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import orjson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.db.models import Q, QuerySet
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from analytics.models import UserCount
from version import ZULIP_VERSION
from zerver.actions.alert_words import do_add_alert_words
from zerver.actions.create_user import do_create_user
from zerver.actions.custom_profile_fields import (
    do_update_user_custom_profile_data_if_changed,
    try_add_realm_custom_profile_field,
)
from zerver.actions.muted_users import do_mute_user
from zerver.actions.navigation_views import do_add_navigation_view
from zerver.actions.presence import do_update_user_presence
from zerver.actions.reactions import check_add_reaction
from zerver.actions.realm_emoji import check_add_realm_emoji
from zerver.actions.realm_icon import do_change_icon_source
from zerver.actions.realm_logo import do_change_logo_source
from zerver.actions.realm_settings import (
    do_change_realm_plan_type,
    do_set_realm_authentication_methods,
)
from zerver.actions.saved_snippets import do_create_saved_snippet
from zerver.actions.scheduled_messages import check_schedule_message
from zerver.actions.streams import do_change_stream_description
from zerver.actions.user_activity import do_update_user_activity_interval
from zerver.actions.user_settings import do_change_user_delivery_email, do_change_user_setting
from zerver.actions.user_status import do_update_user_status
from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.actions.users import do_deactivate_user
from zerver.lib import upload
from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.bot_config import set_bot_config
from zerver.lib.bot_lib import StateHandler
from zerver.lib.export import (
    PRESERVED_AUDIT_LOG_EVENT_TYPES,
    Record,
    do_export_realm,
    do_export_user,
    export_usermessages_batch,
    get_consented_user_ids,
)
from zerver.lib.import_realm import do_import_realm, get_incoming_message_ids
from zerver.lib.migration_status import STALE_MIGRATIONS, AppMigrations, MigrationStatusJson
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    activate_push_notification_service,
    create_s3_buckets,
    get_test_image_file,
    most_recent_message,
    most_recent_usermessage,
    read_test_image_file,
    use_s3_backend,
)
from zerver.lib.thumbnail import BadImageError
from zerver.lib.upload import claim_attachment, upload_avatar_image, upload_message_attachment
from zerver.lib.utils import assert_is_not_none, get_fk_field_name
from zerver.models import (
    AlertWord,
    Attachment,
    BotConfigData,
    BotStorageData,
    ChannelFolder,
    CustomProfileField,
    CustomProfileFieldValue,
    DirectMessageGroup,
    GroupGroupMembership,
    Message,
    MutedUser,
    NamedUserGroup,
    NavigationView,
    OnboardingStep,
    OnboardingUserMessage,
    Reaction,
    Realm,
    RealmAuditLog,
    RealmEmoji,
    RealmExport,
    RealmUserDefault,
    Recipient,
    ScheduledMessage,
    Stream,
    Subscription,
    UserActivity,
    UserGroup,
    UserGroupMembership,
    UserMessage,
    UserPresence,
    UserProfile,
    UserStatus,
    UserTopic,
)
from zerver.models.clients import Client, get_client
from zerver.models.groups import SystemGroups
from zerver.models.messages import ImageAttachment
from zerver.models.presence import PresenceSequence
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zerver.models.recipients import get_direct_message_group_hash
from zerver.models.streams import get_active_streams, get_stream
from zerver.models.users import get_system_bot, get_user_by_delivery_email


def make_datetime(val: float) -> datetime:
    return datetime.fromtimestamp(val, tz=timezone.utc)


def get_output_dir() -> str:
    return os.path.join(settings.TEST_WORKER_DIR, "test-export")


def make_export_output_dir() -> str:
    output_dir = get_output_dir()
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    return output_dir


def read_json(fn: str) -> Any:
    output_dir = get_output_dir()
    full_fn = os.path.join(output_dir, fn)
    with open(full_fn, "rb") as f:
        return orjson.loads(f.read())


def export_fn(fn: str) -> str:
    output_dir = get_output_dir()
    return os.path.join(output_dir, fn)


def get_user_id(r: Realm, full_name: str) -> int:
    return UserProfile.objects.get(realm=r, full_name=full_name).id


def get_direct_message_group_hashes(r: Realm) -> str:
    cordelia_full_name = "Cordelia, Lear's daughter"
    hamlet_full_name = "King Hamlet"
    othello_full_name = "Othello, the Moor of Venice"

    user_id_list = [
        get_user_id(r, cordelia_full_name),
        get_user_id(r, hamlet_full_name),
        get_user_id(r, othello_full_name),
    ]

    direct_message_group_hash = get_direct_message_group_hash(user_id_list)
    return direct_message_group_hash


class ExportFile(ZulipTestCase):
    """This class is a container for shared helper functions
    used for both the realm-level and user-level export tests."""

    @override
    def setUp(self) -> None:
        super().setUp()
        assert settings.LOCAL_UPLOADS_DIR is not None
        self.rm_tree(settings.LOCAL_UPLOADS_DIR)

        # Deleting LOCAL_UPLOADS_DIR results in the test database
        # having RealmEmoji records without associated files.
        #
        # Even if we didn't delete them, the way that the test runner
        # varies settings.LOCAL_UPLOADS_DIR for each test worker
        # process would likely result in this being necessary anyway.
        RealmEmoji.objects.all().delete()

    def upload_files_for_user(
        self, user_profile: UserProfile, *, emoji_name: str = "whatever"
    ) -> None:
        message = most_recent_message(user_profile)
        url = upload_message_attachment("dummy.txt", "text/plain", b"zulip!", user_profile)[0]
        attachment_path_id = url.replace("/user_uploads/", "")
        claim_attachment(
            path_id=attachment_path_id,
            message=message,
            is_message_realm_public=True,
        )

        with get_test_image_file("img.png") as img_file:
            upload_avatar_image(img_file, user_profile, future=False)

        user_profile.avatar_source = "U"
        user_profile.save()

        realm = user_profile.realm

        with get_test_image_file("img.png") as img_file:
            check_add_realm_emoji(realm, emoji_name, user_profile, img_file, "image/png")

    def upload_files_for_realm(self, user_profile: UserProfile) -> None:
        realm = user_profile.realm

        with get_test_image_file("img.png") as img_file:
            upload.upload_backend.upload_realm_icon_image(img_file, user_profile, "image/png")
            do_change_icon_source(realm, Realm.ICON_UPLOADED, acting_user=None)

        with get_test_image_file("img.png") as img_file:
            upload.upload_backend.upload_realm_logo_image(
                img_file, user_profile, night=False, content_type="image/png"
            )
            do_change_logo_source(realm, Realm.LOGO_UPLOADED, False, acting_user=user_profile)
        with get_test_image_file("img.png") as img_file:
            upload.upload_backend.upload_realm_logo_image(
                img_file, user_profile, night=True, content_type="image/png"
            )
            do_change_logo_source(realm, Realm.LOGO_UPLOADED, True, acting_user=user_profile)

    def verify_attachment_json(self, user: UserProfile) -> None:
        attachment = Attachment.objects.get(owner=user)
        (record,) = read_json("attachment.json")["zerver_attachment"]
        self.assertEqual(record["path_id"], attachment.path_id)
        self.assertEqual(record["owner"], attachment.owner_id)
        self.assertEqual(record["realm"], attachment.realm_id)

    def verify_uploads(self, user: UserProfile, is_s3: bool) -> None:
        realm = user.realm

        attachment = Attachment.objects.get(owner=user)
        path_id = attachment.path_id

        # Test uploads
        fn = export_fn(f"uploads/{path_id}")
        with open(fn) as f:
            self.assertEqual(f.read(), "zulip!")
        (record,) = read_json("uploads/records.json")
        self.assertEqual(record["path"], path_id)
        self.assertEqual(record["s3_path"], path_id)

        if is_s3:
            realm_str, random_hash, file_name = path_id.split("/")
            self.assertEqual(realm_str, str(realm.id))
            self.assert_length(random_hash, 24)
            self.assertEqual(file_name, "dummy.txt")

            self.assertEqual(record["realm_id"], realm.id)
            self.assertEqual(record["user_profile_id"], user.id)
        else:
            realm_str, slot, random_hash, file_name = path_id.split("/")
            self.assertEqual(realm_str, str(realm.id))
            # We randomly pick a number between 0 and 255 and turn it into
            # hex in order to avoid large directories.
            assert len(slot) <= 2
            self.assert_length(random_hash, 24)
            self.assertEqual(file_name, "dummy.txt")

    def verify_emojis(self, user: UserProfile, is_s3: bool) -> None:
        realm = user.realm

        realm_emoji = RealmEmoji.objects.get(author=user)
        file_name = realm_emoji.file_name
        assert file_name is not None
        assert file_name.endswith(".png")

        emoji_path = f"{realm.id}/emoji/images/{file_name}"
        emoji_dir = export_fn(f"emoji/{realm.id}/emoji/images")
        self.assertEqual(set(os.listdir(emoji_dir)), {file_name, file_name + ".original"})

        (record1, record2) = read_json("emoji/records.json")
        # The return order is not guaranteed, so sort it so that we can reliably
        # know which record is for the .original file and which for the actual emoji.
        record, record_original = sorted(
            (record1, record2), key=lambda r: r["path"].endswith(".original")
        )

        self.assertEqual(record["file_name"], file_name)
        self.assertEqual(record["path"], emoji_path)
        self.assertEqual(record["s3_path"], emoji_path)
        self.assertEqual(record_original["file_name"], file_name)
        self.assertEqual(record_original["path"], emoji_path + ".original")
        self.assertEqual(record_original["s3_path"], emoji_path + ".original")

        if is_s3:
            self.assertEqual(record["realm_id"], realm.id)
            self.assertEqual(record["user_profile_id"], user.id)
            self.assertEqual(record_original["realm_id"], realm.id)
            self.assertEqual(record_original["user_profile_id"], user.id)

    def verify_realm_logo_and_icon(self) -> None:
        records = read_json("realm_icons/records.json")
        image_files = set()

        for record in records:
            self.assertEqual(record["path"], record["s3_path"])
            image_path = export_fn(f"realm_icons/{record['path']}")
            if image_path.endswith(".original"):
                with open(image_path, "rb") as image_file:
                    image_data = image_file.read()
                self.assertEqual(image_data, read_test_image_file("img.png"))
            else:
                self.assertTrue(os.path.exists(image_path))

            image_files.add(os.path.basename(image_path))

        self.assertEqual(
            set(image_files),
            {
                "night_logo.png",
                "logo.original",
                "logo.png",
                "icon.png",
                "night_logo.original",
                "icon.original",
            },
        )

    def verify_avatars(self, user: UserProfile) -> None:
        records = read_json("avatars/records.json")
        exported_paths = set()

        # Make sure all files in records.json got written.
        for record in records:
            self.assertEqual(record["path"], record["s3_path"])
            path = record["path"]
            fn = export_fn(f"avatars/{path}")
            assert os.path.exists(fn)

            if path.endswith(".original"):
                exported_paths.add(path)

                # For now we know that all our tests use
                # emojis based on img.png.  This may change some
                # day.
                with open(fn, "rb") as fb:
                    fn_data = fb.read()

                self.assertEqual(fn_data, read_test_image_file("img.png"))

        assert exported_paths

        # Right now we expect only our user to have an uploaded avatar.
        db_paths = {user_avatar_path(user) + ".original"}
        self.assertEqual(exported_paths, db_paths)

    def get_applied_migrations_fixture(self, fixture_name: str) -> AppMigrations:
        fixture = orjson.loads(
            self.fixture_data(fixture_name, "import_fixtures/applied_migrations_fixtures")
        )
        return fixture

    def get_applied_migrations_error_message(self, fixture_name: str) -> str:
        fixture = self.fixture_data(fixture_name, "import_fixtures/check_migrations_errors")
        fixture = fixture.format(version_placeholder=ZULIP_VERSION)
        return fixture.strip()

    def verify_migration_status_json(self) -> None:
        # This function asserts that the generated migration_status.json
        # is structurally familiar for it to be used for assertion at
        # import_realm.py. Hence, it doesn't really matter if the individual
        # apps' migrations in migration_status.json fixture are outdated as
        # long as they have the same format.
        exported: MigrationStatusJson = read_json("migration_status.json")

        applied_migrations_fixtures = os.listdir(
            self.fixture_file_name("", "import_fixtures/applied_migrations_fixtures")
        )

        for fixture in applied_migrations_fixtures:
            migration_by_app: AppMigrations = self.get_applied_migrations_fixture(fixture)
            with self.subTest(migration_fixture=fixture):
                self.assertTrue(
                    set(migration_by_app).issubset(set(exported["migrations_by_app"])),
                    f"""
                    Please make sure the `{fixture}` fixture represents the actual
                    `migration_status.json` file. If the format for the same migration
                    status differs, this fixture is probably stale and needs
                    updating.

                    If this variation is needed for testing purposes feel free to
                    exempt the fixture from this test.""",
                )

        # Make sure export doesn't produce a migration_status.json with stale
        # migrations.
        stale_migrations = []
        for app, stale_migration in STALE_MIGRATIONS:
            installed_app = exported["migrations_by_app"].get(app)
            if installed_app:
                stale_migrations = [mig for mig in installed_app if mig.endswith(stale_migration)]
        self.assert_length(stale_migrations, 0)


class RealmImportExportTest(ExportFile):
    def create_user_and_login(self, email: str, realm: Realm) -> None:
        self.register(email, "test", subdomain=realm.subdomain)

    def export_realm(
        self,
        realm: Realm,
        export_type: int,
        exportable_user_ids: set[int] | None = None,
    ) -> None:
        output_dir = make_export_output_dir()
        if export_type == RealmExport.EXPORT_FULL_WITH_CONSENT:
            assert exportable_user_ids is not None

        with patch("zerver.lib.export.create_soft_link"), self.assertLogs(level="INFO"):
            do_export_realm(
                realm=realm,
                output_dir=output_dir,
                threads=0,
                export_type=export_type,
                exportable_user_ids=exportable_user_ids,
            )

            # This is a unique field and thus the cycle of export->import
            # within the same server (which is what happens in our tests)
            # will cause a conflict - so rotate it.
            realm.uuid = uuid.uuid4()
            realm.save()

            export_usermessages_batch(
                input_path=os.path.join(output_dir, "messages-000001.json.partial"),
                output_path=os.path.join(output_dir, "messages-000001.json"),
                export_full_with_consent=export_type == RealmExport.EXPORT_FULL_WITH_CONSENT,
                consented_user_ids=exportable_user_ids,
            )

    def export_realm_and_create_auditlog(
        self,
        original_realm: Realm,
        export_type: int = RealmExport.EXPORT_FULL_WITHOUT_CONSENT,
        exportable_user_ids: set[int] | None = None,
    ) -> None:
        RealmAuditLog.objects.create(
            realm=original_realm,
            event_type=AuditLogEventType.REALM_EXPORTED,
            event_time=timezone_now(),
        )
        self.export_realm(original_realm, export_type, exportable_user_ids)

    def test_export_files_from_local(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm
        self.upload_files_for_user(user)
        self.upload_files_for_realm(user)
        self.export_realm_and_create_auditlog(realm)

        self.verify_attachment_json(user)
        self.verify_uploads(user, is_s3=False)
        self.verify_avatars(user)
        self.verify_emojis(user, is_s3=False)
        self.verify_realm_logo_and_icon()
        self.verify_migration_status_json()

    def test_public_only_export_files_private_uploads_not_included(self) -> None:
        """
        This test verifies that when doing a public_only export, private uploads
        don't get included in the exported data.
        """

        user_profile = self.example_user("hamlet")
        realm = user_profile.realm

        # We create an attachment tied to a personal message. That means it shouldn't be
        # included in a public export, as it's private data.
        personal_message_id = self.send_personal_message(user_profile, self.example_user("othello"))
        url = upload_message_attachment("dummy.txt", "text/plain", b"zulip!", user_profile)[0]
        attachment_path_id = url.replace("/user_uploads/", "")
        attachment = claim_attachment(
            path_id=attachment_path_id,
            message=Message.objects.get(id=personal_message_id),
            is_message_realm_public=True,
        )

        self.export_realm_and_create_auditlog(realm, export_type=RealmExport.EXPORT_PUBLIC)

        # The attachment row shouldn't have been exported:
        self.assertEqual(read_json("attachment.json")["zerver_attachment"], [])

        # Aside of the attachment row, we also need to verify that the file itself
        # isn't included.
        fn = export_fn(f"uploads/{attachment.path_id}")
        self.assertFalse(os.path.exists(fn))

    @use_s3_backend
    def test_export_files_from_s3(self) -> None:
        create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET, settings.S3_AVATAR_BUCKET)

        user = self.example_user("hamlet")
        realm = user.realm

        self.upload_files_for_user(user)
        self.upload_files_for_realm(user)
        self.export_realm_and_create_auditlog(realm)

        self.verify_attachment_json(user)
        self.verify_uploads(user, is_s3=True)
        self.verify_avatars(user)
        self.verify_emojis(user, is_s3=True)
        self.verify_realm_logo_and_icon()
        self.verify_migration_status_json()

    def test_zulip_realm(self) -> None:
        realm = Realm.objects.get(string_id="zulip")

        default_bot = self.example_user("default_bot")
        pm_a_msg_id = self.send_personal_message(self.example_user("AARON"), default_bot)
        pm_b_msg_id = self.send_personal_message(default_bot, self.example_user("iago"))
        pm_c_msg_id = self.send_personal_message(
            self.example_user("othello"), self.example_user("hamlet")
        )

        realm_user_default = RealmUserDefault.objects.get(realm=realm)
        realm_user_default.default_language = "de"
        realm_user_default.save()

        welcome_bot = get_system_bot(settings.WELCOME_BOT, realm.id)
        onboarding_message_id = self.send_stream_message(
            welcome_bot, str(Realm.ZULIP_SANDBOX_CHANNEL_NAME), recipient_realm=realm
        )
        OnboardingUserMessage.objects.create(
            realm=realm,
            message_id=onboarding_message_id,
            flags=OnboardingUserMessage.flags.starred,
        )

        self.export_realm_and_create_auditlog(realm)

        data = read_json("realm.json")
        self.assert_length(data["zerver_userprofile_crossrealm"], 3)
        self.assert_length(data["zerver_userprofile_mirrordummy"], 0)

        exported_user_emails = self.get_set(data["zerver_userprofile"], "delivery_email")
        self.assertIn(self.example_email("cordelia"), exported_user_emails)
        self.assertIn("default-bot@zulip.com", exported_user_emails)

        exported_streams = self.get_set(data["zerver_stream"], "name")
        self.assertEqual(
            exported_streams,
            {
                "Denmark",
                "Rome",
                "Scotland",
                "Venice",
                "Verona",
                "core team",
                "Zulip",
                "sandbox",
            },
        )

        exported_alert_words = data["zerver_alertword"]

        # We set up 4 alert words for Hamlet, Cordelia, etc.
        # when we populate the test database.
        num_zulip_users = 10
        self.assert_length(exported_alert_words, num_zulip_users * 4)

        self.assertIn("robotics", {r["word"] for r in exported_alert_words})

        exported_realm_user_default = data["zerver_realmuserdefault"]
        self.assert_length(exported_realm_user_default, 1)
        self.assertEqual(exported_realm_user_default[0]["default_language"], "de")

        exported_usergroups = data["zerver_usergroup"]
        self.assert_length(exported_usergroups, 14)
        self.assertFalse("direct_members" in exported_usergroups[2])
        self.assertFalse("direct_subgroups" in exported_usergroups[2])

        exported_namedusergroups = data["zerver_namedusergroup"]
        self.assert_length(exported_namedusergroups, 9)
        self.assertEqual(exported_namedusergroups[2]["name"], "role:administrators")
        self.assertTrue("usergroup_ptr" in exported_namedusergroups[2])
        self.assertTrue("realm_for_sharding" in exported_namedusergroups[2])
        self.assertFalse("realm" in exported_namedusergroups[2])
        self.assertFalse("direct_members" in exported_namedusergroups[2])
        self.assertFalse("direct_subgroups" in exported_namedusergroups[2])

        exported_onboarding_usermessages = data["zerver_onboardingusermessage"]
        self.assert_length(exported_onboarding_usermessages, 1)
        self.assertEqual(exported_onboarding_usermessages[0]["message"], onboarding_message_id)
        self.assertEqual(
            exported_onboarding_usermessages[0]["flags_mask"],
            OnboardingUserMessage.flags.starred.mask,
        )
        self.assertEqual(exported_onboarding_usermessages[0]["realm"], realm.id)

        data = read_json("messages-000001.json")
        um = UserMessage.objects.all()[0]
        exported_um = self.find_by_id(data["zerver_usermessage"], um.id)
        self.assertEqual(exported_um["message"], um.message_id)
        self.assertEqual(exported_um["user_profile"], um.user_profile_id)

        exported_message = self.find_by_id(data["zerver_message"], um.message_id)
        self.assertEqual(exported_message["content"], um.message.content)

        exported_message_ids = self.get_set(data["zerver_message"], "id")
        self.assertIn(pm_a_msg_id, exported_message_ids)
        self.assertIn(pm_b_msg_id, exported_message_ids)
        self.assertIn(pm_c_msg_id, exported_message_ids)

    def test_export_realm_with_exportable_user_ids(self) -> None:
        realm = Realm.objects.get(string_id="zulip")

        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        polonius = self.example_user("polonius")
        iago = self.example_user("iago")
        othello = self.example_user("othello")

        do_change_user_setting(cordelia, "allow_private_data_export", True, acting_user=cordelia)
        do_change_user_setting(hamlet, "allow_private_data_export", True, acting_user=hamlet)
        exportable_user_ids = {cordelia.id, hamlet.id}

        pm_a_msg_id = self.send_personal_message(polonius, othello)
        pm_b_msg_id = self.send_personal_message(cordelia, iago)
        pm_c_msg_id = self.send_personal_message(hamlet, othello)
        pm_d_msg_id = self.send_personal_message(iago, hamlet)

        self.export_realm_and_create_auditlog(
            realm,
            export_type=RealmExport.EXPORT_FULL_WITH_CONSENT,
            exportable_user_ids=exportable_user_ids,
        )

        realm_data = read_json("realm.json")

        exported_user_emails = self.get_set(realm_data["zerver_userprofile"], "delivery_email")
        self.assertIn(cordelia.delivery_email, exported_user_emails)
        self.assertIn(hamlet.delivery_email, exported_user_emails)
        self.assertNotIn("default-bot@zulip.com", exported_user_emails)
        self.assertNotIn(iago.delivery_email, exported_user_emails)
        self.assertNotIn(polonius.delivery_email, exported_user_emails)

        dummy_user_emails = self.get_set(
            realm_data["zerver_userprofile_mirrordummy"], "delivery_email"
        )
        self.assertIn(iago.delivery_email, dummy_user_emails)
        self.assertIn(othello.delivery_email, dummy_user_emails)
        self.assertIn(polonius.delivery_email, dummy_user_emails)
        self.assertIn("default-bot@zulip.com", dummy_user_emails)
        self.assertNotIn(cordelia.delivery_email, dummy_user_emails)
        self.assertNotIn(hamlet.delivery_email, dummy_user_emails)

        message_data = read_json("messages-000001.json")

        exported_message_ids = self.get_set(message_data["zerver_message"], "id")
        self.assertNotIn(pm_a_msg_id, exported_message_ids)
        self.assertIn(pm_b_msg_id, exported_message_ids)
        self.assertIn(pm_c_msg_id, exported_message_ids)
        self.assertIn(pm_d_msg_id, exported_message_ids)

        personal_recipient_type_ids = (
            r["type_id"] for r in realm_data["zerver_recipient"] if r["type"] == Recipient.PERSONAL
        )
        for user_profile_id in [cordelia.id, hamlet.id, iago.id, othello.id, polonius.id]:
            self.assertIn(user_profile_id, personal_recipient_type_ids)

    def test_get_consented_user_ids(self) -> None:
        realm = get_realm("zulip")
        consented_user = self.example_user("iago")
        do_change_user_setting(consented_user, "allow_private_data_export", True, acting_user=None)

        non_consented_user = self.example_user("hamlet")
        do_change_user_setting(
            non_consented_user, "allow_private_data_export", False, acting_user=None
        )

        bot_of_consented_user = self.create_test_bot(
            "bot-of-consented-user", consented_user, full_name="Bot of consented user"
        )
        # Bots don't really use allow_private_data_export setting (and it should be False by default)
        # but set explicitly just to be clear on the setup.
        # A bot of a consented user is considered consented no matter what.
        do_change_user_setting(
            bot_of_consented_user, "allow_private_data_export", False, acting_user=None
        )

        deactivated_bot_of_consented_user = self.create_test_bot(
            "deactivated-bot-of-consented-user",
            consented_user,
            full_name="Deactivated bot of consented user",
        )
        do_change_user_setting(
            deactivated_bot_of_consented_user, "allow_private_data_export", False, acting_user=None
        )
        do_deactivate_user(deactivated_bot_of_consented_user, acting_user=None)

        # A bot of a non-consented user is considered not consented.
        bot_of_non_consented_user = self.create_test_bot(
            "bot-of-non-consented-user", non_consented_user, full_name="Bot of non-consented user"
        )
        do_change_user_setting(
            bot_of_consented_user, "allow_private_data_export", False, acting_user=None
        )

        # Unless the bot has allow_private_data_export explicitly set to True. This is a rather
        # unlikely case to encounter, since bots don't have a UI for editing such settings; but it could
        # be flipped by a server admin.
        consented_bot_of_non_consented_user = self.create_test_bot(
            "consented-bot-of-non-consented-user",
            non_consented_user,
            full_name="Consented bot of non-consented user",
        )
        do_change_user_setting(
            consented_bot_of_non_consented_user, "allow_private_data_export", True, acting_user=None
        )

        consented_user_ids = get_consented_user_ids(realm)

        self.assertIn(consented_user.id, consented_user_ids)
        self.assertNotIn(non_consented_user.id, consented_user_ids)

        self.assertIn(bot_of_consented_user.id, consented_user_ids)
        self.assertIn(deactivated_bot_of_consented_user.id, consented_user_ids)

        self.assertNotIn(bot_of_non_consented_user.id, consented_user_ids)
        self.assertIn(consented_bot_of_non_consented_user.id, consented_user_ids)

        # A deactivated consented user is still considered consented.
        do_deactivate_user(consented_user, acting_user=None)
        self.assertIn(consented_user.id, get_consented_user_ids(realm))

        # A mirror dummy is always considered consented, no matter the setting.
        do_deactivate_user(non_consented_user, acting_user=None)
        non_consented_user.is_mirror_dummy = True
        non_consented_user.save(update_fields=["is_mirror_dummy"])
        self.assertIn(non_consented_user.id, get_consented_user_ids(realm))

    def test_client_objects_export(self) -> None:
        """
        Client objects require some special handling when exporting. They aren't
        scoped to a realm - e.g. a Client object "website" can be used by multiple
        realms. Any Message sent from the web app in any realm will have sending_client
        pointing to the "website" Client row.

        However, we cannot just export the whole server table when exporting a realm,
        as it'll leak information about Clients which might only be used by some other realm(s).
        Instead, the export system needs to carefully determine the set of Clients which are pointed
        to by other objects in the export and only export those.

        In an export with consent, this means only exporting Clients which were used by at least
        one consented user in the realm - omitting those that may have only been used by a non-consenting
        user, as those should be considered private.
        """

        realm = get_realm("zulip")
        lear_realm = get_realm("lear")

        # Set up a message in the lear realm for more ease of testing.
        cordelia_lear = self.lear_user("cordelia")
        king_lear = self.lear_user("king")
        self.send_personal_message(cordelia_lear, king_lear)

        # Consented users:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        # Iago will be non-consenting.
        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")
        do_change_user_setting(hamlet, "allow_private_data_export", True, acting_user=None)
        do_change_user_setting(othello, "allow_private_data_export", True, acting_user=None)
        do_change_user_setting(iago, "allow_private_data_export", False, acting_user=None)

        a_message_id = self.send_personal_message(hamlet, othello)

        # This Client won't be used by the realm.
        non_realm_client = Client.objects.create(name="Non-realm client")

        # This Client will be used by both of the realms.
        realm_shared_client = Client.objects.create(name="Client shared between realms")
        last_realm_message = Message.objects.get(id=a_message_id)
        last_second_realm_message = Message.objects.filter(realm=lear_realm).latest("id")
        last_realm_message.sending_client = realm_shared_client
        last_second_realm_message.sending_client = realm_shared_client
        last_realm_message.save()
        last_second_realm_message.save()

        # This Client will be used by a message sent to a consenting user.
        b_message_id = self.send_personal_message(iago, hamlet)
        consented_user_client = Client.objects.create(name="Consented user client")
        b_message = Message.objects.get(id=b_message_id)
        b_message.sending_client = consented_user_client
        b_message.save()

        # This Client will be used in a message sent between non-consented users
        # and therefore should not be exported an export with consent.
        c_message_id = self.send_personal_message(iago, cordelia)
        non_consented_user_client = Client.objects.create(name="Non-consented user client")
        c_message = Message.objects.get(id=c_message_id)
        c_message.sending_client = non_consented_user_client
        c_message.save()

        all_our_client_ids = [
            non_realm_client.id,
            realm_shared_client.id,
            consented_user_client.id,
            non_consented_user_client.id,
        ]
        Client.objects.exclude(id__in=all_our_client_ids).delete()

        self.export_realm_and_create_auditlog(
            realm,
            export_type=RealmExport.EXPORT_FULL_WITH_CONSENT,
            exportable_user_ids=get_consented_user_ids(realm),
        )

        realm_data = read_json("realm.json")

        exported_client_ids = self.get_set(realm_data["zerver_client"], "id")
        self.assertEqual({realm_shared_client.id, consented_user_client.id}, exported_client_ids)

        # Now verify that in a full export without consent, also the non_consented_user_client
        # is included.
        self.export_realm_and_create_auditlog(
            realm,
            export_type=RealmExport.EXPORT_FULL_WITHOUT_CONSENT,
        )

        realm_data = read_json("realm.json")

        exported_client_ids = self.get_set(realm_data["zerver_client"], "id")
        self.assertEqual(
            {non_consented_user_client.id, realm_shared_client.id, consented_user_client.id},
            exported_client_ids,
        )

    def test_public_export_private_and_public_data(self) -> None:
        """
        Public exports are essentially a special case of exports with consent: where
        none of the users are consenting. The difference is that in a public export
        we don't turn these non-consenting users into is_mirror_dummy=True.

        Therefore it's enough to just test the basics here, as the detailed logic
        is covered in tests for exports with consent.
        """

        realm = get_realm("zulip")

        # Consented users:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        # Iago will be non-consenting.
        iago = self.example_user("iago")

        do_change_user_setting(hamlet, "allow_private_data_export", True, acting_user=None)
        do_change_user_setting(othello, "allow_private_data_export", True, acting_user=None)
        do_change_user_setting(iago, "allow_private_data_export", False, acting_user=None)

        # Despite both hamlet and othello having consent enabled, in a public export
        # everyone is non-consenting - so a Client object used only in a DM will not
        # be exported.
        a_message_id = self.send_personal_message(hamlet, othello)
        private_client = Client.objects.create(name="private client")
        a_message = Message.objects.get(id=a_message_id)
        a_message.sending_client = private_client
        a_message.save()

        # SavedSnippets are private content - so in a public export, despite
        # hamlet having consent enabled, such objects should not be exported.
        saved_snippet = do_create_saved_snippet("test", "test", hamlet)

        # Data of some other tables (e.g. UserPresence) is public, so will
        # be exported regardless of consent - even in a public export.
        iago_presence = UserPresence.objects.create(user_profile=iago, realm=realm)

        self.export_realm_and_create_auditlog(realm, export_type=RealmExport.EXPORT_PUBLIC)

        realm_data = read_json("realm.json")

        exported_client_ids = self.get_set(realm_data["zerver_client"], "id")
        self.assertNotEqual(len(exported_client_ids), 0)
        self.assertNotIn(private_client.id, exported_client_ids)

        exported_saved_snippet_ids = self.get_set(realm_data["zerver_savedsnippet"], "id")
        self.assertNotIn(saved_snippet.id, exported_saved_snippet_ids)
        self.assertEqual(exported_saved_snippet_ids, set())

        exported_user_presence_ids = self.get_set(realm_data["zerver_userpresence"], "id")
        self.assertIn(iago_presence.id, exported_user_presence_ids)

    def test_export_realm_with_member_consent(self) -> None:
        realm = Realm.objects.get(string_id="zulip")

        # Create private streams and subscribe users for testing export
        create_stream_if_needed(realm, "Private A", invite_only=True)
        self.subscribe(self.example_user("iago"), "Private A")
        self.subscribe(self.example_user("othello"), "Private A")
        self.send_stream_message(self.example_user("iago"), "Private A", "Hello stream A")

        create_stream_if_needed(realm, "Private B", invite_only=True)
        self.subscribe(self.example_user("prospero"), "Private B")
        stream_b_first_message_id = self.send_stream_message(
            self.example_user("prospero"), "Private B", "Hello stream B"
        )
        # Hamlet subscribes now, so due to protected history, will not have access to the first message.
        # This means that his consent will not be sufficient for the export of that message.
        self.subscribe(self.example_user("hamlet"), "Private B")
        stream_b_second_message_id = self.send_stream_message(
            self.example_user("prospero"), "Private B", "Hello again stream B"
        )

        create_stream_if_needed(realm, "Private C", invite_only=True)
        self.subscribe(self.example_user("othello"), "Private C")
        self.subscribe(self.example_user("prospero"), "Private C")
        stream_c_message_id = self.send_stream_message(
            self.example_user("othello"), "Private C", "Hello stream C"
        )

        create_stream_if_needed(
            realm, "Private D", invite_only=True, history_public_to_subscribers=True
        )
        self.subscribe(self.example_user("prospero"), "Private D")
        self.send_stream_message(self.example_user("prospero"), "Private D", "Hello stream D")
        # Hamlet subscribes now, but due to the stream having public history to subscribers, that doesn't
        # matter and he his consent is sufficient to export also messages sent before he was added
        # to the stream.
        self.subscribe(self.example_user("hamlet"), "Private D")
        self.send_stream_message(self.example_user("prospero"), "Private D", "Hello again stream D")

        # Create direct message groups
        self.send_group_direct_message(
            self.example_user("iago"), [self.example_user("cordelia"), self.example_user("AARON")]
        )
        direct_message_group_a = DirectMessageGroup.objects.last()
        self.send_group_direct_message(
            self.example_user("ZOE"),
            [self.example_user("hamlet"), self.example_user("AARON"), self.example_user("othello")],
        )
        direct_message_group_b = DirectMessageGroup.objects.last()

        direct_message_group_c_message_id = self.send_group_direct_message(
            self.example_user("AARON"),
            [self.example_user("cordelia"), self.example_user("ZOE"), self.example_user("othello")],
        )
        direct_message_group_c = DirectMessageGroup.objects.last()

        # Create direct messages
        pm_a_msg_id = self.send_personal_message(
            self.example_user("AARON"), self.example_user("othello")
        )
        pm_b_msg_id = self.send_personal_message(
            self.example_user("cordelia"), self.example_user("iago")
        )
        pm_c_msg_id = self.send_personal_message(
            self.example_user("hamlet"), self.example_user("othello")
        )
        pm_d_msg_id = self.send_personal_message(
            self.example_user("iago"), self.example_user("hamlet")
        )

        # Create some non-message private data for users. We will use SavedSnippet objects as they're simple
        # to create and are private data that should not be exported for non-consenting users. There are many
        # such private types of data (e.g. UserTopic, Draft) - we could test any of them equivalently.
        iago_saved_snippet = do_create_saved_snippet("test", "test", self.example_user("iago"))
        cordelia_saved_snippet = do_create_saved_snippet(
            "test", "test", self.example_user("cordelia")
        )

        # Iago and Hamlet consented to export their private data.
        do_change_user_setting(
            self.example_user("iago"), "allow_private_data_export", True, acting_user=None
        )
        do_change_user_setting(
            self.example_user("hamlet"), "allow_private_data_export", True, acting_user=None
        )

        # Additionally, we set prospero's email visibility to NOBODY in order to test this is respected by the
        # export. His real email value should not be exported.
        non_consented_user_with_private_email = self.example_user("prospero")
        do_change_user_setting(
            non_consented_user_with_private_email,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY,
            acting_user=None,
        )
        # Do the same for the consenting iago, just to verify consent causes the private email address to be
        # exported
        do_change_user_setting(
            self.example_user("iago"),
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY,
            acting_user=None,
        )

        # default-bot is a bot of a non-consenting user - let's also set up a bot for a consenting user
        # to verify the bot gets treated as consenting.
        consented_bot = self.create_test_bot(
            "non-consented-bot", self.example_user("iago"), "Non consented bot"
        )
        consented_user_ids = {self.example_user(user).id for user in ["iago", "hamlet"]}
        consented_user_ids.add(consented_bot.id)

        # Set up a non-consented, deactivated user to test the special behavior we have for them. In order to prevent
        # originally deactivated users from being able to reactivate their account via signup after
        # export->import cycle, we don't turn them into mirror dummies. Instead, they stay as regular deactivated
        # users.
        # At the same time, we have to be careful - despite ending up in zerver_userprofile in the export,
        # they might not be consented to exporting their private data - so we have to test that this is handled
        # correctly.
        deactivated_non_consented_user = self.example_user("polonius")
        deactivated_non_consented_user_saved_snippet = do_create_saved_snippet(
            "test", "test", deactivated_non_consented_user
        )
        do_deactivate_user(deactivated_non_consented_user, acting_user=None)

        self.assertEqual(get_consented_user_ids(realm), consented_user_ids)

        self.export_realm_and_create_auditlog(
            realm,
            export_type=RealmExport.EXPORT_FULL_WITH_CONSENT,
            exportable_user_ids=consented_user_ids,
        )

        realm_data = read_json("realm.json")

        user_count = UserProfile.objects.filter(realm=realm).count()

        self.assert_length(realm_data["zerver_userprofile_crossrealm"], 3)
        # Non-consenting users will become mirror dummy users - with the exception of deactivated users.
        # Those stay as regular, deactivated users.
        # We offset the counts below by 1 exactly to account for deactivated_non_consented_user.
        self.assert_length(
            realm_data["zerver_userprofile_mirrordummy"], user_count - len(consented_user_ids) - 1
        )
        self.assert_length(realm_data["zerver_userprofile"], len(consented_user_ids) + 1)

        exported_user_emails = self.get_set(realm_data["zerver_userprofile"], "delivery_email")
        exported_mirror_dummy_user_emails = self.get_set(
            realm_data["zerver_userprofile_mirrordummy"], "delivery_email"
        )

        self.assertIn(self.example_email("cordelia"), exported_mirror_dummy_user_emails)
        self.assertIn(self.example_email("hamlet"), exported_user_emails)
        self.assertIn(self.example_email("iago"), exported_user_emails)
        self.assertIn(consented_bot.delivery_email, exported_user_emails)
        self.assertIn(self.example_email("othello"), exported_mirror_dummy_user_emails)
        self.assertIn(deactivated_non_consented_user.delivery_email, exported_user_emails)
        self.assertIn("default-bot@zulip.com", exported_mirror_dummy_user_emails)

        # Verify that the _mirrordummy tables is the table of mirror dummy users, as expected.
        self.assertTrue(
            all(row["is_active"] is False for row in realm_data["zerver_userprofile_mirrordummy"])
        )
        self.assertTrue(
            all(
                row["is_mirror_dummy"] is True
                for row in realm_data["zerver_userprofile_mirrordummy"]
            )
        )
        self.assertTrue(
            all(row["is_mirror_dummy"] is False for row in realm_data["zerver_userprofile"])
        )

        # Verify that the deactivated_non_consented_user did not not become a mirror dummy.
        exported_deactivated_non_consented_user = next(
            user
            for user in realm_data["zerver_userprofile"]
            if user["id"] == deactivated_non_consented_user.id
        )
        self.assertEqual(exported_deactivated_non_consented_user["is_active"], False)
        self.assertEqual(exported_deactivated_non_consented_user["is_mirror_dummy"], False)

        exported_non_consented_user_with_private_email = next(
            user
            for user in realm_data["zerver_userprofile_mirrordummy"]
            if user["id"] == non_consented_user_with_private_email.id
        )
        self.assertRegex(
            exported_non_consented_user_with_private_email["delivery_email"],
            r"exported-user-[a-zA-Z0-9]+@zulip\.testserver",
        )

        exported_streams = self.get_set(realm_data["zerver_stream"], "name")
        self.assertEqual(
            exported_streams,
            {
                "core team",
                "Denmark",
                "Rome",
                "Scotland",
                "Venice",
                "Verona",
                "Zulip",
                "sandbox",
                "Private A",
                "Private B",
                "Private C",
                "Private D",
            },
        )

        data = read_json("messages-000001.json")
        exported_usermessages = UserMessage.objects.filter(
            user_profile__in=[self.example_user("iago"), self.example_user("hamlet")]
        )
        um = exported_usermessages[0]
        self.assert_length(data["zerver_usermessage"], len(exported_usermessages))
        exported_um = self.find_by_id(data["zerver_usermessage"], um.id)
        self.assertEqual(exported_um["message"], um.message_id)
        self.assertEqual(exported_um["user_profile"], um.user_profile_id)

        exported_message = self.find_by_id(data["zerver_message"], um.message_id)
        self.assertEqual(exported_message["content"], um.message.content)

        public_stream_names = [
            "Denmark",
            "Rome",
            "Scotland",
            "Venice",
            "Verona",
            "Zulip",
            "sandbox",
        ]
        public_stream_ids = Stream.objects.filter(name__in=public_stream_names).values_list(
            "id", flat=True
        )
        public_stream_recipients = Recipient.objects.filter(
            type_id__in=public_stream_ids, type=Recipient.STREAM
        )
        public_stream_message_ids = Message.objects.filter(
            realm_id=realm.id, recipient__in=public_stream_recipients
        ).values_list("id", flat=True)

        # Messages from Private stream C are not exported since no member gave consent
        # Only the second message from Private stream B is exported, so that gets handled
        # separately.
        private_stream_ids = Stream.objects.filter(
            name__in=["Private A", "Private D", "core team"]
        ).values_list("id", flat=True)
        private_stream_recipients = Recipient.objects.filter(
            type_id__in=private_stream_ids, type=Recipient.STREAM
        )
        private_stream_message_ids = Message.objects.filter(
            realm_id=realm.id, recipient__in=private_stream_recipients
        ).values_list("id", flat=True)

        pm_recipients = Recipient.objects.filter(
            type_id__in=consented_user_ids, type=Recipient.PERSONAL
        )
        pm_query = Q(recipient__in=pm_recipients) | Q(sender__in=consented_user_ids)
        exported_pm_ids = (
            Message.objects.filter(pm_query, realm=realm.id)
            .values_list("id", flat=True)
            .values_list("id", flat=True)
        )

        assert (
            direct_message_group_a is not None
            and direct_message_group_b is not None
            and direct_message_group_c is not None
        )
        # Third direct message group is not exported since none of
        # the members gave consent
        direct_message_group_recipients = Recipient.objects.filter(
            type_id__in=[direct_message_group_a.id, direct_message_group_b.id],
            type=Recipient.DIRECT_MESSAGE_GROUP,
        )
        pm_query = Q(recipient__in=direct_message_group_recipients) | Q(
            sender__in=consented_user_ids
        )
        exported_dm_group_message_ids = (
            Message.objects.filter(pm_query, realm=realm.id)
            .values_list("id", flat=True)
            .values_list("id", flat=True)
        )

        exported_msg_ids = {
            *public_stream_message_ids,
            *private_stream_message_ids,
            stream_b_second_message_id,
            *exported_pm_ids,
            *exported_dm_group_message_ids,
        }
        self.assertEqual(self.get_set(data["zerver_message"], "id"), exported_msg_ids)

        self.assertNotIn(stream_b_first_message_id, exported_msg_ids)

        self.assertNotIn(stream_c_message_id, exported_msg_ids)
        self.assertNotIn(direct_message_group_c_message_id, exported_msg_ids)

        self.assertNotIn(pm_a_msg_id, exported_msg_ids)
        self.assertIn(pm_b_msg_id, exported_msg_ids)
        self.assertIn(pm_c_msg_id, exported_msg_ids)
        self.assertIn(pm_d_msg_id, exported_msg_ids)

        # iago is the only consented user with a SavedSnippet. cordelia didn't consent so her SavedSnippet
        # should not be exported.
        exported_saved_snippet_ids = self.get_set(realm_data["zerver_savedsnippet"], "id")
        self.assertNotIn(cordelia_saved_snippet.id, exported_saved_snippet_ids)
        self.assertNotIn(
            deactivated_non_consented_user_saved_snippet.id, exported_saved_snippet_ids
        )
        self.assertEqual(exported_saved_snippet_ids, {iago_saved_snippet.id})

        exported_direct_message_group_ids = self.get_set(realm_data["zerver_huddle"], "id")
        self.assertNotIn(direct_message_group_c.id, exported_direct_message_group_ids)
        self.assertEqual(
            exported_direct_message_group_ids,
            {direct_message_group_a.id, direct_message_group_b.id},
        )

        # We also want to verify Subscriptions to the DirectMessageGroups were exported correctly.
        # As long as a DirectMessageGroup is exported (due to having at least one consenting user
        # in it), *all* the Subscriptions to it should be exported - to maintain the expected
        # structure of the data.
        exported_direct_message_group_a_recipient = next(
            huddle["recipient"]
            for huddle in realm_data["zerver_huddle"]
            if huddle["id"] == direct_message_group_a.id
        )
        exported_direct_message_group_a_sub_ids = [
            sub["id"]
            for sub in realm_data["zerver_subscription"]
            if sub["recipient"] == exported_direct_message_group_a_recipient
        ]
        self.assert_length(exported_direct_message_group_a_sub_ids, 3)

        exported_direct_message_group_b_recipient = next(
            huddle["recipient"]
            for huddle in realm_data["zerver_huddle"]
            if huddle["id"] == direct_message_group_b.id
        )
        exported_direct_message_group_b_sub_ids = [
            sub["id"]
            for sub in realm_data["zerver_subscription"]
            if sub["recipient"] == exported_direct_message_group_b_recipient
        ]
        self.assert_length(exported_direct_message_group_b_sub_ids, 4)

    def test_export_realm_data_scrubbing(self) -> None:
        realm = get_realm("zulip")
        consented_user = self.example_user("iago")
        non_consented_user = self.example_user("hamlet")
        do_change_user_setting(
            non_consented_user,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY,
            acting_user=None,
        )

        # Change some user settings to test the scrubbing of settings for non-consenting users.
        do_change_user_setting(consented_user, "web_font_size_px", 123, acting_user=None)
        do_change_user_setting(non_consented_user, "web_font_size_px", 456, acting_user=None)

        # For testing the scrubbing of RealmAuditLogs, we generate some events that will get
        # RealmAuditLog events.
        # RealmAuditLogs where the modified_user is consenting will be preserved, while those
        # where the modified_user is not consenting will not be included in the export, with
        # the exception of a few event types such as SUBSCRIPTION_CREATED - which are exported.
        do_change_user_delivery_email(consented_user, "iago-new@zulip.com", acting_user=None)
        consented_user_email_change_log = RealmAuditLog.objects.last()
        assert consented_user_email_change_log is not None

        self.subscribe(consented_user, "some-new-stream")
        consented_user_subscription_event = RealmAuditLog.objects.last()
        assert consented_user_subscription_event is not None
        assert (
            consented_user_subscription_event.event_type == AuditLogEventType.SUBSCRIPTION_CREATED
        )

        do_change_user_delivery_email(non_consented_user, "hamlet-new@zulip.com", acting_user=None)
        non_consented_user_email_change_log = RealmAuditLog.objects.last()
        assert non_consented_user_email_change_log is not None

        self.subscribe(non_consented_user, "some-new-stream")
        non_consented_user_subscription_event = RealmAuditLog.objects.last()
        assert non_consented_user_subscription_event is not None
        assert (
            non_consented_user_subscription_event.event_type
            == AuditLogEventType.SUBSCRIPTION_CREATED
        )

        # Make sure we also have a RealmAuditLog of a type with modified_user=None to test that edge case
        # and ensure we don't accidentally drop such entries.
        stream = get_stream("Denmark", realm)
        do_change_stream_description(
            # Ensure that logs with non-consenting acting_acting user aren't accidentally dropped either.
            stream,
            "some new description",
            acting_user=non_consented_user,
        )
        stream_description_change_log = RealmAuditLog.objects.last()
        assert stream_description_change_log is not None

        consented_user_original_subs_count = Subscription.objects.filter(
            user_profile=consented_user
        ).count()
        non_consented_user_original_subs_count = Subscription.objects.filter(
            user_profile=non_consented_user
        ).count()

        self.assertNotEqual(consented_user_original_subs_count, 0)
        self.assertNotEqual(non_consented_user_original_subs_count, 0)

        # Change the color of subscription as an easy reference point to use to detect if they Subscription
        # attributes are getting scrubbed or not.
        Subscription.objects.filter(user_profile__in=[consented_user, non_consented_user]).update(
            color="#foo"
        )
        consented_user_ids = {consented_user.id}
        do_change_user_setting(consented_user, "allow_private_data_export", True, acting_user=None)

        self.export_realm_and_create_auditlog(
            realm,
            export_type=RealmExport.EXPORT_FULL_WITH_CONSENT,
            exportable_user_ids=consented_user_ids,
        )

        realm_data = read_json("realm.json")

        exported_realm_audit_logs = realm_data["zerver_realmauditlog"]
        exported_realm_audit_log_ids = self.get_set(exported_realm_audit_logs, "id")
        self.assertNotIn(non_consented_user_email_change_log.id, exported_realm_audit_log_ids)
        self.assertIn(non_consented_user_subscription_event.id, exported_realm_audit_log_ids)
        self.assertIn(consented_user_subscription_event.id, exported_realm_audit_log_ids)
        self.assertIn(consented_user_email_change_log.id, exported_realm_audit_log_ids)
        self.assertIn(stream_description_change_log.id, exported_realm_audit_log_ids)

        # More general assertions on the entire sets of audit logs pertaining to our users.
        for log in RealmAuditLog.objects.filter(modified_user=non_consented_user).exclude(
            event_type__in=PRESERVED_AUDIT_LOG_EVENT_TYPES
        ):
            self.assertNotIn(log.id, exported_realm_audit_log_ids)
        for log in RealmAuditLog.objects.filter(modified_user=consented_user):
            self.assertIn(log.id, exported_realm_audit_log_ids)

        # Now check scrubbing of Subscriptions data.
        consented_user_exported_subscriptions = {
            sub["id"]: sub
            for sub in realm_data["zerver_subscription"]
            if sub["user_profile"] == consented_user.id
        }
        non_consented_user_exported_subscriptions = {
            sub["id"]: sub
            for sub in realm_data["zerver_subscription"]
            if sub["user_profile"] == non_consented_user.id
        }
        self.assertEqual(
            len(consented_user_exported_subscriptions), consented_user_original_subs_count
        )
        self.assertEqual(
            len(non_consented_user_exported_subscriptions), non_consented_user_original_subs_count
        )
        for sub in Subscription.objects.filter(user_profile=consented_user):
            original_sub = model_to_dict(sub)
            exported_sub = consented_user_exported_subscriptions[sub.id]
            # Subscriptions of the consenting users get exported fully as they are,
            # so the #foo color should be preserved.
            self.assertEqual(original_sub, exported_sub)
            self.assertEqual(exported_sub["color"], "#foo")
        for sub in Subscription.objects.filter(user_profile=non_consented_user):
            original_sub = model_to_dict(sub)
            exported_sub = non_consented_user_exported_subscriptions[sub.id]
            self.assertNotEqual(original_sub, exported_sub)
            # Subscriptions of the non-consenting users get get scrubbed to replace
            # "user setting"-type attributes with default values, so the #foo color
            # will be overwritten in the process.
            self.assertNotEqual(exported_sub["color"], "#foo")

        # Verify the export/scrubbing of user settings for consenting/non-consenting users.
        realm_user_default = RealmUserDefault.objects.get(realm=realm)
        exported_consented_user = next(
            user for user in realm_data["zerver_userprofile"] if user["id"] == consented_user.id
        )
        exported_non_consented_user = next(
            user
            for user in realm_data["zerver_userprofile_mirrordummy"]
            if user["id"] == non_consented_user.id
        )

        # Settings get exported with the user-set values for consenting users, but are
        # scrubbed to realm default values for non-consenting users.
        self.assertEqual(exported_consented_user["web_font_size_px"], 123)
        self.assertNotEqual(exported_non_consented_user["web_font_size_px"], 456)
        self.assertEqual(
            exported_non_consented_user["web_font_size_px"], realm_user_default.web_font_size_px
        )
        # Email visibility is an exception, as we should preserve user's choice in who to show their real
        # email address to across the export->import cycle - regardless of export consent.
        self.assertEqual(
            exported_non_consented_user["email_address_visibility"],
            UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY,
        )
        # Sanity check that this doesn't match the realm default -
        # since with a matching realm default, the above assertion
        # would be moot and not testing the preservation of the
        # email_address_visibility setting.
        self.assertNotEqual(
            realm_user_default.email_address_visibility, UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY
        )

    """
    Tests for import_realm
    """

    def test_import_realm(self) -> None:
        original_realm = Realm.objects.get(string_id="zulip")

        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        denmark_stream = get_stream("Denmark", original_realm)
        denmark_stream.creator = hamlet
        denmark_stream.save(update_fields=["creator"])

        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        cross_realm_bot = get_system_bot(settings.WELCOME_BOT, internal_realm.id)

        with get_test_image_file("img.png") as img_file:
            realm_emoji = check_add_realm_emoji(
                realm=hamlet.realm,
                name="hawaii",
                author=hamlet,
                image_file=img_file,
                content_type="image/png",
            )
            self.assertEqual(realm_emoji.name, "hawaii")

        # We want to set up some image data to verify image attachment thumbnailing works correctly
        # in the import.
        # We'll create a new user to use as the sender of the messages with such images,
        # so that we can easily find them after importing - by fetching messages sent
        # by the thumbnailing_test_user_email account.
        thumbnailing_test_user_email = "thumbnailing_test@zulip.com"
        self.create_user_and_login(thumbnailing_test_user_email, original_realm)
        thumbnailing_test_user = get_user_by_delivery_email(
            thumbnailing_test_user_email, original_realm
        )

        # Send a message with the image. After the import, we'll verify that this message
        # and the associated ImageAttachment have been created correctly.
        image_path_id = self.upload_and_thumbnail_image("img.png")
        self.send_stream_message(
            sender=thumbnailing_test_user,
            stream_name="Verona",
            content=f"An [image](/user_uploads/{image_path_id})",
        )
        image_attachment = ImageAttachment.objects.get(path_id=image_path_id)
        # Malform some ImageAttachment info. These shouldn't get exported (and certainly not imported!)
        # anyway, so we can test that this misinformation doesn't make its way into the imported realm.
        image_attachment.original_width_px = 9999
        image_attachment.original_height_px = 9999
        image_attachment.save()

        # Deactivate a user to ensure such a case is covered.
        do_deactivate_user(self.example_user("aaron"), acting_user=None)
        # Turn another user into a mirror dummy
        prospero = self.example_user("prospero")
        prospero_email = prospero.delivery_email
        do_deactivate_user(prospero, acting_user=None)
        prospero.is_mirror_dummy = True
        prospero.save()

        # Change some authentication_methods so that some are enabled and some disabled
        # for this to be properly tested, as opposed to some special case
        # with e.g. everything enabled.
        authentication_methods = original_realm.authentication_methods_dict()
        authentication_methods["Email"] = False
        authentication_methods["Dev"] = True

        do_set_realm_authentication_methods(
            original_realm, authentication_methods, acting_user=None
        )

        # Set up an edge-case RealmAuditLog with acting_user in a different realm. Such an acting_user can't be covered
        # by the export, so we'll test that it is handled by getting set to None.
        self.assertTrue(
            RealmAuditLog.objects.filter(
                modified_user=hamlet, event_type=AuditLogEventType.USER_CREATED
            ).count(),
            1,
        )
        RealmAuditLog.objects.filter(
            modified_user=hamlet, event_type=AuditLogEventType.USER_CREATED
        ).update(acting_user_id=cross_realm_bot.id)

        # data to test import of direct message groups
        direct_message_group = [
            self.example_user("hamlet"),
            self.example_user("othello"),
        ]
        self.send_group_direct_message(
            self.example_user("cordelia"),
            direct_message_group,
            "test group direct message",
        )

        user_mention_message = "@**King Hamlet** Hello"
        self.send_stream_message(self.example_user("iago"), "Verona", user_mention_message)

        stream_mention_message = "Subscribe to #**Denmark**"
        self.send_stream_message(self.example_user("hamlet"), "Verona", stream_mention_message)

        user_group_mention_message = "Hello @*hamletcharacters*"
        self.send_stream_message(self.example_user("othello"), "Verona", user_group_mention_message)

        special_characters_message = "```\n'\n```\n@**Polonius**"
        self.send_stream_message(self.example_user("iago"), "Denmark", special_characters_message)

        sample_user = self.example_user("hamlet")

        check_add_reaction(
            user_profile=cordelia,
            message_id=most_recent_message(hamlet).id,
            emoji_name="hawaii",
            emoji_code=None,
            reaction_type=None,
        )
        reaction = Reaction.objects.order_by("id").last()
        assert reaction

        # Verify strange invariant for Reaction/RealmEmoji.
        self.assertEqual(reaction.emoji_code, str(realm_emoji.id))

        # data to test import of onboaring step
        OnboardingStep.objects.filter(user=sample_user).delete()
        OnboardingStep.objects.create(
            user=sample_user,
            onboarding_step="intro_inbox_view_modal",
        )

        # data to test import of muted topic
        stream = get_stream("Verona", original_realm)
        do_set_user_topic_visibility_policy(
            sample_user,
            stream,
            "Verona2",
            visibility_policy=UserTopic.VisibilityPolicy.MUTED,
        )

        # data to test import of muted users
        do_mute_user(hamlet, cordelia)
        do_mute_user(cordelia, hamlet)
        do_mute_user(cordelia, othello)

        client = get_client("website")

        do_update_user_presence(
            sample_user, client, timezone_now(), UserPresence.LEGACY_STATUS_ACTIVE_INT
        )
        user_presence_last_update_ids = set(
            UserPresence.objects.filter(realm=original_realm)
            .values_list("last_update_id", flat=True)
            .distinct("last_update_id")
        )
        presence_sequence = PresenceSequence.objects.get(realm=original_realm)

        # Set up scheduled messages.
        ScheduledMessage.objects.filter(realm=original_realm).delete()
        check_schedule_message(
            sender=hamlet,
            client=get_client("website"),
            recipient_type_name="stream",
            message_to=[Stream.objects.get(name="Denmark", realm=original_realm).id],
            topic_name="test-import",
            message_content="test message",
            deliver_at=timezone_now() + timedelta(days=365),
            realm=original_realm,
        )
        original_scheduled_message = ScheduledMessage.objects.filter(realm=original_realm).last()
        assert original_scheduled_message is not None

        # send Cordelia to the islands
        do_update_user_status(
            user_profile=cordelia,
            away=True,
            status_text="in Hawaii",
            client_id=client.id,
            emoji_name="hawaii",
            emoji_code=str(realm_emoji.id),
            reaction_type=Reaction.REALM_EMOJI,
            scheduled_end_time=None,
        )

        do_add_navigation_view(
            hamlet,
            "inbox",
            True,
        )
        do_add_navigation_view(
            hamlet,
            "recent",
            False,
        )

        user_status = UserStatus.objects.order_by("id").last()
        assert user_status

        # Verify strange invariant for UserStatus/RealmEmoji.
        self.assertEqual(user_status.emoji_code, str(realm_emoji.id))

        # data to test import of botstoragedata and botconfigdata
        bot_profile = do_create_user(
            email="bot-1@zulip.com",
            password="test",
            realm=original_realm,
            full_name="bot",
            bot_type=UserProfile.EMBEDDED_BOT,
            bot_owner=sample_user,
            acting_user=None,
        )
        storage = StateHandler(bot_profile)
        storage.put("some key", "some value")

        set_bot_config(bot_profile, "entry 1", "value 1")

        realm_user_default = RealmUserDefault.objects.get(realm=original_realm)
        realm_user_default.default_language = "de"
        realm_user_default.twenty_four_hour_time = True
        realm_user_default.save()

        # Data to test import of onboarding usermessages
        onboarding_message_id = self.send_stream_message(
            cross_realm_bot,
            str(Realm.ZULIP_SANDBOX_CHANNEL_NAME),
            "onboarding message",
            recipient_realm=original_realm,
        )
        OnboardingUserMessage.objects.create(
            realm=original_realm,
            message_id=onboarding_message_id,
            flags=OnboardingUserMessage.flags.starred,
        )

        channel_folder = ChannelFolder.objects.create(
            realm=original_realm,
            name="Frontend",
            description="Frontend channels",
            creator=self.example_user("iago"),
        )
        stream.folder = channel_folder
        stream.save()

        # We want to have an extra, malformed RealmEmoji with no .author
        # to test that upon import that gets fixed.
        with get_test_image_file("img.png") as img_file:
            new_realm_emoji = check_add_realm_emoji(
                realm=hamlet.realm,
                name="hawaii2",
                author=hamlet,
                image_file=img_file,
                content_type="image/png",
            )
            assert new_realm_emoji is not None
        original_realm_emoji_count = RealmEmoji.objects.count()
        self.assertGreaterEqual(original_realm_emoji_count, 2)
        new_realm_emoji.author = None
        new_realm_emoji.save()

        RealmAuditLog.objects.create(
            realm=original_realm,
            event_type=AuditLogEventType.REALM_EXPORTED,
            event_time=timezone_now(),
        )

        getters = self.get_realm_getters()

        snapshots: dict[str, object] = {}

        for f in getters:
            snapshots[f.__name__] = f(original_realm)

        self.export_realm(original_realm, export_type=RealmExport.EXPORT_FULL_WITHOUT_CONSENT)

        with (
            self.settings(BILLING_ENABLED=False),
            self.assertLogs(level="INFO"),
            # With captureOnCommitCallbacks we ensure that tasks delegated to the queue workers
            # are executed immediately. We use this to make thumbnailing runs in the import
            # process in this test.
            self.captureOnCommitCallbacks(execute=True),
        ):
            do_import_realm(get_output_dir(), "test-zulip")

        # Make sure our export/import didn't somehow leak info into the
        # original realm.
        for f in getters:
            # One way this will fail is if you make a getter that doesn't
            # properly restrict its results to a single realm.
            if f(original_realm) != snapshots[f.__name__]:
                raise AssertionError(
                    f"""
                    The export/import process is corrupting your
                    original realm according to {f.__name__}!

                    If you wrote that getter, are you sure you
                    are only grabbing objects from one realm?
                    """
                )

        imported_realm = Realm.objects.get(string_id="test-zulip")

        # test realm
        self.assertTrue(Realm.objects.filter(string_id="test-zulip").exists())
        self.assertNotEqual(imported_realm.id, original_realm.id)

        def assert_realm_values(f: Callable[[Realm], object]) -> None:
            orig_realm_result = f(original_realm)
            imported_realm_result = f(imported_realm)
            # orig_realm_result should be truthy and have some values, otherwise
            # the test is kind of meaningless
            assert orig_realm_result

            # It may be helpful to do print(f.__name__) if you are having
            # trouble debugging this.

            # print(f.__name__, orig_realm_result, imported_realm_result)
            self.assertEqual(orig_realm_result, imported_realm_result)

        for f in getters:
            assert_realm_values(f)

        self.verify_emoji_code_foreign_keys()

        # Our direct message group hashes change, because hashes
        # use ids that change.
        self.assertNotEqual(
            get_direct_message_group_hashes(original_realm),
            get_direct_message_group_hashes(imported_realm),
        )

        # test to highlight that bs4 which we use to do data-**id
        # replacements modifies the HTML sometimes. eg replacing <br>
        # with </br>, &#39; with \' etc. The modifications doesn't
        # affect how the browser displays the rendered_content so we
        # are okay with using bs4 for this.  lxml package also has
        # similar behavior.
        orig_polonius_user = self.example_user("polonius")
        original_msg = Message.objects.get(
            content=special_characters_message, sender__realm=original_realm
        )
        self.assertEqual(
            original_msg.rendered_content,
            '<div class="codehilite"><pre><span></span><code>&#39;\n</code></pre></div>\n'
            f'<p><span class="user-mention" data-user-id="{orig_polonius_user.id}">@Polonius</span></p>',
        )
        imported_polonius_user = UserProfile.objects.get(
            delivery_email=self.example_email("polonius"), realm=imported_realm
        )
        imported_msg = Message.objects.get(
            content=special_characters_message, sender__realm=imported_realm
        )
        self.assertEqual(
            imported_msg.rendered_content,
            '<div class="codehilite"><pre><span></span><code>\'\n</code></pre></div>\n'
            f'<p><span class="user-mention" data-user-id="{imported_polonius_user.id}">@Polonius</span></p>',
        )

        imported_hamlet_user = UserProfile.objects.get(
            delivery_email=self.example_email("hamlet"), realm=imported_realm
        )
        imported_denmark_stream = Stream.objects.get(name="Denmark", realm=imported_realm)
        self.assertEqual(imported_denmark_stream.creator, imported_hamlet_user)

        # Check recipient_id was generated correctly for the imported users and streams.
        for user_profile in UserProfile.objects.filter(realm=imported_realm):
            self.assertEqual(
                user_profile.recipient_id,
                Recipient.objects.get(type=Recipient.PERSONAL, type_id=user_profile.id).id,
            )
        for stream in Stream.objects.filter(realm=imported_realm):
            self.assertEqual(
                stream.recipient_id,
                Recipient.objects.get(type=Recipient.STREAM, type_id=stream.id).id,
            )

        # Check folder field for imported streams
        for stream in Stream.objects.filter(realm=imported_realm):
            if stream.name == "Verona":
                # Folder was only set for "Verona" stream in original realm.
                assert stream.folder is not None
                self.assertEqual(stream.folder.name, "Frontend")
            else:
                self.assertIsNone(stream.folder_id)

        for dm_group in DirectMessageGroup.objects.all():
            # Direct Message groups don't have a realm column, so we just test all
            # Direct Message groups for simplicity.
            self.assertEqual(
                dm_group.recipient_id,
                Recipient.objects.get(type=Recipient.DIRECT_MESSAGE_GROUP, type_id=dm_group.id).id,
            )

        self.assertEqual(ScheduledMessage.objects.filter(realm=imported_realm).count(), 1)
        imported_scheduled_message = ScheduledMessage.objects.first()
        assert imported_scheduled_message is not None
        self.assertEqual(imported_scheduled_message.content, original_scheduled_message.content)
        self.assertEqual(
            imported_scheduled_message.scheduled_timestamp,
            original_scheduled_message.scheduled_timestamp,
        )

        for user_profile in UserProfile.objects.filter(realm=imported_realm):
            # Check that all Subscriptions have the correct is_user_active set.
            self.assertEqual(
                Subscription.objects.filter(
                    user_profile=user_profile, is_user_active=user_profile.is_active
                ).count(),
                Subscription.objects.filter(user_profile=user_profile).count(),
            )
        # Verify that we've actually tested something meaningful instead of a blind import
        # with is_user_active=True used for everything.
        self.assertTrue(Subscription.objects.filter(is_user_active=False).exists())

        all_imported_realm_emoji = RealmEmoji.objects.filter(realm=imported_realm)
        self.assertEqual(all_imported_realm_emoji.count(), original_realm_emoji_count)
        for imported_realm_emoji in all_imported_realm_emoji:
            self.assertNotEqual(imported_realm_emoji.author, None)

        self.assertEqual(
            original_realm.authentication_methods_dict(),
            imported_realm.authentication_methods_dict(),
        )

        imported_hamlet = get_user_by_delivery_email(hamlet.delivery_email, imported_realm)
        realmauditlog = RealmAuditLog.objects.get(
            modified_user=imported_hamlet, event_type=AuditLogEventType.USER_CREATED
        )
        self.assertEqual(realmauditlog.realm, imported_realm)
        # As explained above when setting up the RealmAuditLog row, the .acting_user should have been
        # set to None due to being unexportable.
        self.assertEqual(realmauditlog.acting_user, None)

        # Verify the PresenceSequence for the realm got imported correctly.
        imported_presence_sequence = PresenceSequence.objects.get(realm=imported_realm)
        self.assertEqual(
            presence_sequence.last_update_id, imported_presence_sequence.last_update_id
        )
        imported_last_update_ids = set(
            UserPresence.objects.filter(realm=imported_realm)
            .values_list("last_update_id", flat=True)
            .distinct("last_update_id")
        )
        self.assertEqual(user_presence_last_update_ids, imported_last_update_ids)
        self.assertEqual(imported_presence_sequence.last_update_id, max(imported_last_update_ids))

        self.assertEqual(
            Message.objects.filter(realm=original_realm).count(),
            Message.objects.filter(realm=imported_realm).count(),
        )

        # Verify thumbnailing.
        imported_thumbnailing_test_user = get_user_by_delivery_email(
            thumbnailing_test_user_email, imported_realm
        )
        imported_messages_with_thumbnail = Message.objects.filter(
            sender=imported_thumbnailing_test_user, realm=imported_realm
        )
        imported_message_with_thumbnail = imported_messages_with_thumbnail.latest("id")
        attachment_with_thumbnail = Attachment.objects.get(
            owner=imported_thumbnailing_test_user, messages=imported_message_with_thumbnail
        )

        path_id = attachment_with_thumbnail.path_id
        # An ImageAttachment has been created in the import process.
        imported_image_attachment = ImageAttachment.objects.get(
            path_id=path_id, realm=imported_realm
        )

        # It figured out the dimensions correctly and didn't inherit the bad data in the
        # original ImageAttachment.
        self.assertEqual(imported_image_attachment.original_width_px, 128)
        self.assertEqual(imported_image_attachment.original_height_px, 128)
        # ImageAttachment.thumbnail_metadata contains information about thumbnails that actually
        # got generated. By asserting it's not empty, we make sure thumbnailing ran for the image
        # and that we didn't merely create the ImageAttachment row in the database.
        self.assertNotEqual(len(imported_image_attachment.thumbnail_metadata), 0)
        self.assertTrue(imported_image_attachment.thumbnail_metadata[0])

        # Content and rendered_content got updated correctly, to point to the correct, new path_id
        # and include the HTML for image preview using the thumbnail.
        self.assertEqual(
            imported_message_with_thumbnail.content, f"An [image](/user_uploads/{path_id})"
        )
        expected_rendered_preview = (
            f'<p>An <a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            "<img"
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            f' src="/user_uploads/thumbnail/{path_id}/840x560.webp"></a></div>'
        )
        self.assertEqual(
            imported_message_with_thumbnail.rendered_content, expected_rendered_preview
        )

        imported_prospero_user = get_user_by_delivery_email(prospero_email, imported_realm)
        self.assertIsNotNone(imported_prospero_user.recipient)

    def test_import_message_edit_history(self) -> None:
        realm = get_realm("zulip")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        user_mention_message = f"@**King Hamlet|{hamlet.id}** Hello"

        self.login_user(iago)
        message_id = self.send_stream_message(
            self.example_user("iago"), "Verona", user_mention_message
        )

        new_content = "new content"
        result = self.client_patch(
            f"/json/messages/{message_id}",
            {
                "content": new_content,
            },
        )
        self.assert_json_success(result)

        self.export_realm_and_create_auditlog(realm)
        with self.settings(BILLING_ENABLED=False), self.assertLogs(level="INFO"):
            do_import_realm(get_output_dir(), "test-zulip")
        imported_realm = Realm.objects.get(string_id="test-zulip")

        imported_message = Message.objects.filter(realm=imported_realm).latest("id")
        imported_hamlet_id = UserProfile.objects.get(
            delivery_email=hamlet.delivery_email, realm=imported_realm
        ).id
        imported_iago_id = UserProfile.objects.get(
            delivery_email=iago.delivery_email, realm=imported_realm
        ).id

        edit_history_json = imported_message.edit_history
        assert edit_history_json is not None
        edit_history = orjson.loads(edit_history_json)
        self.assert_length(edit_history, 1)

        prev_version_of_message = edit_history[0]
        # Ensure the "user_id" (of the sender) was updated correctly
        # to the imported id in the data.
        self.assertEqual(prev_version_of_message["user_id"], imported_iago_id)

        # The mention metadata in the rendered content should be updated.
        self.assertIn(
            f'data-user-id="{imported_hamlet_id}"', prev_version_of_message["prev_rendered_content"]
        )

    def get_realm_getters(self) -> list[Callable[[Realm], object]]:
        names = set()
        getters: list[Callable[[Realm], object]] = []

        def getter(f: Callable[[Realm], object]) -> Callable[[Realm], object]:
            getters.append(f)
            assert f.__name__.startswith("get_")

            # Avoid dups
            assert f.__name__ not in names
            names.add(f.__name__)
            return f

        @getter
        def get_admin_bot_emails(r: Realm) -> set[str]:
            return {user.email for user in r.get_admin_users_and_bots()}

        @getter
        def get_active_emails(r: Realm) -> set[str]:
            return {user.email for user in r.get_active_users()}

        @getter
        def get_active_stream_names(r: Realm) -> set[str]:
            return {stream.name for stream in get_active_streams(r)}

        @getter
        def get_group_names_for_group_settings(r: Realm) -> set[str]:
            return {
                getattr(r, permission_name).named_user_group.name
                for permission_name in Realm.REALM_PERMISSION_GROUP_SETTINGS
            }

        # test recipients
        def get_recipient_stream(r: Realm) -> Recipient:
            recipient = Stream.objects.get(name="Verona", realm=r).recipient
            assert recipient is not None
            return recipient

        def get_recipient_user(r: Realm) -> Recipient:
            return assert_is_not_none(UserProfile.objects.get(full_name="Iago", realm=r).recipient)

        @getter
        def get_stream_recipient_type(r: Realm) -> int:
            return get_recipient_stream(r).type

        @getter
        def get_user_recipient_type(r: Realm) -> int:
            return get_recipient_user(r).type

        # test subscription
        def get_subscribers(recipient: Recipient) -> set[str]:
            subscriptions = Subscription.objects.filter(recipient=recipient)
            users = {sub.user_profile.email for sub in subscriptions}
            return users

        @getter
        def get_stream_subscribers(r: Realm) -> set[str]:
            return get_subscribers(get_recipient_stream(r))

        @getter
        def get_user_subscribers(r: Realm) -> set[str]:
            return get_subscribers(get_recipient_user(r))

        # test custom profile fields
        @getter
        def get_custom_profile_field_names(r: Realm) -> set[str]:
            custom_profile_fields = CustomProfileField.objects.filter(realm=r)
            custom_profile_field_names = {field.name for field in custom_profile_fields}
            return custom_profile_field_names

        @getter
        def get_custom_profile_with_field_type_user(
            r: Realm,
        ) -> tuple[set[str], set[str], set[frozenset[str]]]:
            fields = CustomProfileField.objects.filter(field_type=CustomProfileField.USER, realm=r)

            def get_email(user_id: int) -> str:
                return UserProfile.objects.get(id=user_id).email

            def get_email_from_value(field_value: CustomProfileFieldValue) -> set[str]:
                user_id_list = orjson.loads(field_value.value)
                return {get_email(user_id) for user_id in user_id_list}

            def custom_profile_field_values_for(
                fields: Iterable[CustomProfileField],
            ) -> set[frozenset[str]]:
                return {
                    frozenset(get_email_from_value(value))
                    for value in CustomProfileFieldValue.objects.filter(field__in=fields)
                }

            field_names, field_hints = (set() for i in range(2))
            for field in fields:
                field_names.add(field.name)
                field_hints.add(field.hint)

            return (field_hints, field_names, custom_profile_field_values_for(fields))

        # test realmauditlog
        @getter
        def get_realm_audit_log_event_type(r: Realm) -> set[int]:
            realmauditlogs = RealmAuditLog.objects.filter(realm=r).exclude(
                event_type__in=[
                    AuditLogEventType.REALM_PLAN_TYPE_CHANGED,
                    AuditLogEventType.CHANNEL_CREATED,
                    AuditLogEventType.REALM_IMPORTED,
                ]
            )
            realmauditlog_event_type = {log.event_type for log in realmauditlogs}
            return realmauditlog_event_type

        @getter
        def get_group_direct_message(r: Realm) -> str:
            direct_message_group_hash = get_direct_message_group_hashes(r)
            direct_message_group_id = DirectMessageGroup.objects.get(
                huddle_hash=direct_message_group_hash
            ).id
            direct_message_group_recipient = Recipient.objects.get(
                type_id=direct_message_group_id, type=3
            )
            group_direct_message = Message.objects.get(recipient=direct_message_group_recipient)
            self.assertEqual(group_direct_message.content, "test group direct message")
            return group_direct_message.content

        @getter
        def get_alertwords(r: Realm) -> set[str]:
            return {rec.word for rec in AlertWord.objects.filter(realm_id=r.id)}

        @getter
        def get_realm_emoji_names(r: Realm) -> set[str]:
            names = {rec.name for rec in RealmEmoji.objects.filter(realm_id=r.id)}
            assert "hawaii" in names
            return names

        @getter
        def get_realm_user_statuses(r: Realm) -> set[tuple[str, str, str]]:
            cordelia = self.example_user("cordelia")
            tups = {
                (rec.user_profile.full_name, rec.emoji_name, rec.status_text)
                for rec in UserStatus.objects.filter(user_profile__realm_id=r.id)
            }
            assert (cordelia.full_name, "hawaii", "in Hawaii") in tups
            return tups

        @getter
        def get_realm_emoji_reactions(r: Realm) -> set[tuple[str, str]]:
            cordelia = self.example_user("cordelia")
            tups = {
                (rec.emoji_name, rec.user_profile.full_name)
                for rec in Reaction.objects.filter(
                    user_profile__realm_id=r.id, reaction_type=Reaction.REALM_EMOJI
                )
            }
            self.assertEqual(tups, {("hawaii", cordelia.full_name)})
            return tups

        # test onboarding step
        @getter
        def get_onboarding_steps(r: Realm) -> set[str]:
            user_id = get_user_id(r, "King Hamlet")
            onboarding_steps = set(
                OnboardingStep.objects.filter(user_id=user_id).values_list(
                    "onboarding_step", flat=True
                )
            )
            return onboarding_steps

        @getter
        def get_navigation_views(r: Realm) -> set[str]:
            user_id = get_user_id(r, "King Hamlet")
            navigation_views = set(
                NavigationView.objects.filter(user_id=user_id).values_list("fragment", flat=True)
            )
            return navigation_views

        # test muted topics
        @getter
        def get_muted_topics(r: Realm) -> set[str]:
            user_profile_id = get_user_id(r, "King Hamlet")
            muted_topics = UserTopic.objects.filter(
                user_profile_id=user_profile_id, visibility_policy=UserTopic.VisibilityPolicy.MUTED
            )
            topic_names = {muted_topic.topic_name for muted_topic in muted_topics}
            return topic_names

        @getter
        def get_muted_users(r: Realm) -> set[tuple[str, str, str]]:
            mute_objects = MutedUser.objects.filter(user_profile__realm=r)
            muter_tuples = {
                (
                    mute_object.user_profile.full_name,
                    mute_object.muted_user.full_name,
                    str(mute_object.date_muted),
                )
                for mute_object in mute_objects
            }
            return muter_tuples

        @getter
        def get_user_group_names(r: Realm) -> set[str]:
            result = set()
            for group in UserGroup.objects.filter(realm=r):
                if hasattr(group, "named_user_group"):
                    result.add(group.named_user_group.name)

            return result

        @getter
        def get_named_user_group_names(r: Realm) -> set[str]:
            return {group.name for group in NamedUserGroup.objects.filter(realm=r)}

        @getter
        def get_user_membership(r: Realm) -> set[str]:
            usergroup = NamedUserGroup.objects.get(realm=r, name="hamletcharacters")
            usergroup_membership = UserGroupMembership.objects.filter(user_group=usergroup)
            users = {membership.user_profile.email for membership in usergroup_membership}
            return users

        @getter
        def get_group_group_membership(r: Realm) -> set[str]:
            usergroup = NamedUserGroup.objects.get(realm=r, name="role:members")
            group_group_membership = GroupGroupMembership.objects.filter(supergroup=usergroup)
            subgroups = {
                membership.subgroup.named_user_group.name for membership in group_group_membership
            }
            return subgroups

        @getter
        def get_user_group_direct_members(r: Realm) -> set[str]:
            # We already check the members of the group through UserGroupMembership
            # objects, but we also want to check direct_members field is set
            # correctly since we do not include this in export data.
            usergroup = NamedUserGroup.objects.get(realm=r, name="hamletcharacters")
            direct_members = usergroup.direct_members.all()
            direct_member_emails = {user.email for user in direct_members}
            return direct_member_emails

        @getter
        def get_user_group_direct_subgroups(r: Realm) -> set[str]:
            # We already check the subgroups of the group through GroupGroupMembership
            # objects, but we also want to check that direct_subgroups field is set
            # correctly since we do not include this in export data.
            usergroup = NamedUserGroup.objects.get(realm=r, name="role:members")
            direct_subgroups = usergroup.direct_subgroups.all()
            direct_subgroup_names = {group.named_user_group.name for group in direct_subgroups}
            return direct_subgroup_names

        @getter
        def get_user_group_can_mention_group_setting(r: Realm) -> str:
            user_group = NamedUserGroup.objects.get(realm=r, name="hamletcharacters")
            return user_group.can_mention_group.named_user_group.name

        # test botstoragedata and botconfigdata
        @getter
        def get_botstoragedata(r: Realm) -> dict[str, object]:
            bot_profile = UserProfile.objects.get(full_name="bot", realm=r)
            bot_storage_data = BotStorageData.objects.get(bot_profile=bot_profile)
            return {"key": bot_storage_data.key, "data": bot_storage_data.value}

        @getter
        def get_botconfigdata(r: Realm) -> dict[str, object]:
            bot_profile = UserProfile.objects.get(full_name="bot", realm=r)
            bot_config_data = BotConfigData.objects.get(bot_profile=bot_profile)
            return {"key": bot_config_data.key, "data": bot_config_data.value}

        # test messages
        def get_stream_messages(r: Realm) -> QuerySet[Message]:
            recipient = get_recipient_stream(r)
            messages = Message.objects.filter(realm_id=r.id, recipient=recipient)
            return messages

        @getter
        def get_stream_topics(r: Realm) -> set[str]:
            messages = get_stream_messages(r)
            topic_names = {m.topic_name() for m in messages}
            return topic_names

        # test usermessages
        @getter
        def get_usermessages_user(r: Realm) -> set[str]:
            messages = get_stream_messages(r).order_by("content")
            usermessage = UserMessage.objects.filter(message=messages[0])
            usermessage_user = {
                um.user_profile.email for um in usermessage if not um.user_profile.is_mirror_dummy
            }
            return usermessage_user

        # tests to make sure that various data-*-ids in rendered_content
        # are replaced correctly with the values of newer realm.

        @getter
        def get_user_mention(r: Realm) -> str:
            mentioned_user = UserProfile.objects.get(
                delivery_email=self.example_email("hamlet"), realm=r
            )
            data_user_id = f'data-user-id="{mentioned_user.id}"'
            mention_message = get_stream_messages(r).get(rendered_content__contains=data_user_id)
            return mention_message.content

        @getter
        def get_stream_mention(r: Realm) -> str:
            mentioned_stream = get_stream("Denmark", r)
            data_stream_id = f'data-stream-id="{mentioned_stream.id}"'
            mention_message = get_stream_messages(r).get(rendered_content__contains=data_stream_id)
            return mention_message.content

        @getter
        def get_user_group_mention(r: Realm) -> str:
            user_group = NamedUserGroup.objects.get(realm=r, name="hamletcharacters")
            data_usergroup_id = f'data-user-group-id="{user_group.id}"'
            mention_message = get_stream_messages(r).get(
                rendered_content__contains=data_usergroup_id
            )
            return mention_message.content

        @getter
        def get_userpresence_timestamp(r: Realm) -> set[object]:
            # It should be sufficient to compare UserPresence timestamps to verify
            # they got exported/imported correctly.
            return set(
                UserPresence.objects.filter(realm=r).values_list(
                    "last_active_time", "last_connected_time"
                )
            )

        @getter
        def get_realm_user_default_values(r: Realm) -> dict[str, object]:
            realm_user_default = RealmUserDefault.objects.get(realm=r)
            return {
                "default_language": realm_user_default.default_language,
                "twenty_four_hour_time": realm_user_default.twenty_four_hour_time,
            }

        @getter
        def get_onboarding_usermessages(r: Realm) -> set[tuple[str, Any]]:
            tups = {
                (rec.message.content, rec.flags.mask)
                for rec in OnboardingUserMessage.objects.filter(realm_id=r.id)
            }
            self.assertEqual(
                tups, {("onboarding message", OnboardingUserMessage.flags.starred.mask)}
            )
            return tups

        @getter
        def get_channel_folders(r: Realm) -> set[str]:
            return set(ChannelFolder.objects.filter(realm=r).values_list("name", flat=True))

        return getters

    def test_import_realm_with_invalid_email_addresses_fails_validation(self) -> None:
        realm = get_realm("zulip")

        self.export_realm_and_create_auditlog(realm)
        data = read_json("realm.json")

        data["zerver_userprofile"][0]["delivery_email"] = "invalid_email_address"

        output_dir = get_output_dir()
        full_fn = os.path.join(output_dir, "realm.json")
        with open(full_fn, "wb") as f:
            f.write(orjson.dumps(data))

        with self.assertRaises(ValidationError), self.assertLogs(level="INFO"):
            do_import_realm(output_dir, "test-zulip")

        # Now test a weird case where delivery_email is valid, but .email is not.
        # Such data should never reasonably get generated, but we should still
        # be defensive against it (since it can still happen due to bugs or manual edition
        # of export files in an attempt to get us to import malformed data).
        self.export_realm_and_create_auditlog(realm)
        data = read_json("realm.json")
        data["zerver_userprofile"][0]["email"] = "invalid_email_address"

        output_dir = get_output_dir()
        full_fn = os.path.join(output_dir, "realm.json")
        with open(full_fn, "wb") as f:
            f.write(orjson.dumps(data))

        with self.assertRaises(ValidationError), self.assertLogs(level="INFO"):
            do_import_realm(output_dir, "test-zulip2")

    def test_import_realm_with_no_realm_user_default_table(self) -> None:
        original_realm = Realm.objects.get(string_id="zulip")

        self.export_realm_and_create_auditlog(original_realm)

        # We want to remove the RealmUserDefault object from the export.
        realm_data = read_json("realm.json")
        realm_data["zerver_realmuserdefault"] = []
        output_dir = get_output_dir()
        full_fn = os.path.join(output_dir, "realm.json")
        with open(full_fn, "wb") as f:
            f.write(orjson.dumps(realm_data))

        with self.settings(BILLING_ENABLED=False), self.assertLogs(level="INFO"):
            do_import_realm(get_output_dir(), "test-zulip")

        self.assertTrue(Realm.objects.filter(string_id="test-zulip").exists())
        imported_realm = Realm.objects.get(string_id="test-zulip")

        # RealmUserDefault table with default values is created, if it is not present in
        # the import data.
        self.assertTrue(RealmUserDefault.objects.filter(realm=imported_realm).exists())

        realm_user_default = RealmUserDefault.objects.get(realm=imported_realm)
        self.assertEqual(realm_user_default.default_language, "en")
        self.assertEqual(realm_user_default.twenty_four_hour_time, False)

    @activate_push_notification_service()
    def test_import_realm_notify_bouncer(self) -> None:
        original_realm = Realm.objects.get(string_id="zulip")

        self.export_realm_and_create_auditlog(original_realm)

        with (
            self.settings(BILLING_ENABLED=False),
            self.assertLogs(level="INFO"),
            patch("zerver.lib.remote_server.send_to_push_bouncer") as m,
        ):
            get_response = {
                "last_realm_count_id": 0,
                "last_installation_count_id": 0,
                "last_realmauditlog_id": 0,
            }

            def mock_send_to_push_bouncer_response(  # type: ignore[return]
                method: str, *args: Any
            ) -> dict[str, int] | None:
                if method == "GET":
                    return get_response

            m.side_effect = mock_send_to_push_bouncer_response

            with self.captureOnCommitCallbacks(execute=True):
                new_realm = do_import_realm(get_output_dir(), "test-zulip")

        self.assertTrue(Realm.objects.filter(string_id="test-zulip").exists())
        calls_args_for_assert = m.call_args_list[1][0]
        self.assertEqual(calls_args_for_assert[0], "POST")
        self.assertEqual(calls_args_for_assert[1], "server/analytics")
        self.assertIn(
            new_realm.id, [realm["id"] for realm in json.loads(m.call_args_list[1][0][2]["realms"])]
        )

    def test_import_emoji_error(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm

        self.upload_files_for_user(user)
        self.upload_files_for_realm(user)

        self.export_realm_and_create_auditlog(realm)

        with (
            self.settings(BILLING_ENABLED=False),
            self.assertLogs(level="WARNING") as mock_log,
            patch("zerver.lib.import_realm.upload_emoji_image", side_effect=BadImageError("test")),
        ):
            do_import_realm(get_output_dir(), "test-zulip")
        self.assert_length(mock_log.output, 1)
        self.assertIn("Could not thumbnail emoji image", mock_log.output[0])

    def test_import_files_from_local(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm

        self.upload_files_for_user(user)
        self.upload_files_for_realm(user)

        self.export_realm_and_create_auditlog(realm)

        with self.settings(BILLING_ENABLED=False), self.assertLogs(level="INFO"):
            do_import_realm(get_output_dir(), "test-zulip")
        imported_realm = Realm.objects.get(string_id="test-zulip")

        # Test attachments
        uploaded_file = Attachment.objects.get(realm=imported_realm)
        self.assert_length(b"zulip!", uploaded_file.size)

        assert settings.LOCAL_UPLOADS_DIR is not None
        assert settings.LOCAL_FILES_DIR is not None
        assert settings.LOCAL_AVATARS_DIR is not None

        attachment_file_path = os.path.join(settings.LOCAL_FILES_DIR, uploaded_file.path_id)
        self.assertTrue(os.path.isfile(attachment_file_path))

        test_image_data = read_test_image_file("img.png")
        self.assertIsNotNone(test_image_data)

        # Test emojis
        realm_emoji = RealmEmoji.objects.get(realm=imported_realm)
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=imported_realm.id,
            emoji_file_name=realm_emoji.file_name,
        )
        emoji_file_path = os.path.join(settings.LOCAL_AVATARS_DIR, emoji_path)
        with open(emoji_file_path + ".original", "rb") as f:
            self.assertEqual(f.read(), test_image_data)
        self.assertTrue(os.path.isfile(emoji_file_path))

        # Test avatars
        user_profile = UserProfile.objects.get(full_name=user.full_name, realm=imported_realm)
        avatar_path_id = user_avatar_path(user_profile) + ".original"
        avatar_file_path = os.path.join(settings.LOCAL_AVATARS_DIR, avatar_path_id)
        self.assertTrue(os.path.isfile(avatar_file_path))

        # Test realm icon and logo
        upload_path = upload.upload_backend.realm_avatar_and_logo_path(imported_realm)
        full_upload_path = os.path.join(settings.LOCAL_AVATARS_DIR, upload_path)

        with open(os.path.join(full_upload_path, "icon.original"), "rb") as f:
            self.assertEqual(f.read(), test_image_data)
        self.assertTrue(os.path.isfile(os.path.join(full_upload_path, "icon.png")))
        self.assertEqual(imported_realm.icon_source, Realm.ICON_UPLOADED)

        with open(os.path.join(full_upload_path, "logo.original"), "rb") as f:
            self.assertEqual(f.read(), test_image_data)
        self.assertTrue(os.path.isfile(os.path.join(full_upload_path, "logo.png")))
        self.assertEqual(imported_realm.logo_source, Realm.LOGO_UPLOADED)

        with open(os.path.join(full_upload_path, "night_logo.original"), "rb") as f:
            self.assertEqual(f.read(), test_image_data)
        self.assertTrue(os.path.isfile(os.path.join(full_upload_path, "night_logo.png")))
        self.assertEqual(imported_realm.night_logo_source, Realm.LOGO_UPLOADED)

    @use_s3_backend
    def test_import_files_from_s3(self) -> None:
        uploads_bucket, avatar_bucket = create_s3_buckets(
            settings.S3_AUTH_UPLOADS_BUCKET, settings.S3_AVATAR_BUCKET
        )

        user = self.example_user("hamlet")
        realm = user.realm

        self.upload_files_for_realm(user)
        self.upload_files_for_user(user)
        self.export_realm_and_create_auditlog(realm)

        with self.settings(BILLING_ENABLED=False), self.assertLogs(level="INFO"):
            do_import_realm(get_output_dir(), "test-zulip")

        imported_realm = Realm.objects.get(string_id="test-zulip")
        test_image_data = read_test_image_file("img.png")

        # Test attachments
        uploaded_file = Attachment.objects.get(realm=imported_realm)
        self.assert_length(b"zulip!", uploaded_file.size)

        attachment_content = uploads_bucket.Object(uploaded_file.path_id).get()["Body"].read()
        self.assertEqual(b"zulip!", attachment_content)

        # Test emojis
        realm_emoji = RealmEmoji.objects.get(realm=imported_realm)
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=imported_realm.id,
            emoji_file_name=realm_emoji.file_name,
        )
        resized_emoji_key = avatar_bucket.Object(emoji_path)
        self.assertIsNotNone(resized_emoji_key.get()["Body"].read())
        self.assertEqual(resized_emoji_key.key, emoji_path)
        original_emoji_path_id = emoji_path + ".original"
        original_emoji_key = avatar_bucket.Object(original_emoji_path_id)
        self.assertEqual(original_emoji_key.get()["Body"].read(), test_image_data)
        self.assertEqual(original_emoji_key.key, original_emoji_path_id)

        # Test avatars
        user_profile = UserProfile.objects.get(full_name=user.full_name, realm=imported_realm)
        avatar_path_id = user_avatar_path(user_profile) + ".original"
        original_image_key = avatar_bucket.Object(avatar_path_id)
        self.assertEqual(original_image_key.key, avatar_path_id)
        image_data = avatar_bucket.Object(avatar_path_id).get()["Body"].read()
        self.assertEqual(image_data, test_image_data)

        # Test realm icon and logo
        upload_path = upload.upload_backend.realm_avatar_and_logo_path(imported_realm)

        original_icon_path_id = os.path.join(upload_path, "icon.original")
        original_icon_key = avatar_bucket.Object(original_icon_path_id)
        self.assertEqual(original_icon_key.get()["Body"].read(), test_image_data)
        resized_icon_path_id = os.path.join(upload_path, "icon.png")
        resized_icon_key = avatar_bucket.Object(resized_icon_path_id)
        self.assertEqual(resized_icon_key.key, resized_icon_path_id)
        self.assertEqual(imported_realm.icon_source, Realm.ICON_UPLOADED)

        original_logo_path_id = os.path.join(upload_path, "logo.original")
        original_logo_key = avatar_bucket.Object(original_logo_path_id)
        self.assertEqual(original_logo_key.get()["Body"].read(), test_image_data)
        resized_logo_path_id = os.path.join(upload_path, "logo.png")
        resized_logo_key = avatar_bucket.Object(resized_logo_path_id)
        self.assertEqual(resized_logo_key.key, resized_logo_path_id)
        self.assertEqual(imported_realm.logo_source, Realm.LOGO_UPLOADED)

        night_logo_original_path_id = os.path.join(upload_path, "night_logo.original")
        night_logo_original_key = avatar_bucket.Object(night_logo_original_path_id)
        self.assertEqual(night_logo_original_key.get()["Body"].read(), test_image_data)
        resized_night_logo_path_id = os.path.join(upload_path, "night_logo.png")
        resized_night_logo_key = avatar_bucket.Object(resized_night_logo_path_id)
        self.assertEqual(resized_night_logo_key.key, resized_night_logo_path_id)
        self.assertEqual(imported_realm.night_logo_source, Realm.LOGO_UPLOADED)

    def test_get_incoming_message_ids(self) -> None:
        import_dir = os.path.join(
            settings.DEPLOY_ROOT, "zerver", "tests", "fixtures", "import_fixtures"
        )
        message_ids = get_incoming_message_ids(
            import_dir=import_dir,
            sort_by_date=True,
        )

        self.assertEqual(message_ids, [888, 999, 555])

        message_ids = get_incoming_message_ids(
            import_dir=import_dir,
            sort_by_date=False,
        )

        self.assertEqual(message_ids, [555, 888, 999])

    def test_import_of_authentication_methods(self) -> None:
        with self.settings(
            AUTHENTICATION_BACKENDS=(
                "zproject.backends.EmailAuthBackend",
                "zproject.backends.AzureADAuthBackend",
                "zproject.backends.SAMLAuthBackend",
            )
        ):
            realm = get_realm("zulip")
            authentication_methods_dict = realm.authentication_methods_dict()
            for auth_method in authentication_methods_dict:
                authentication_methods_dict[auth_method] = True
            do_set_realm_authentication_methods(
                realm, authentication_methods_dict, acting_user=None
            )

            self.export_realm_and_create_auditlog(realm)

            with self.settings(BILLING_ENABLED=False), self.assertLogs(level="INFO"):
                do_import_realm(get_output_dir(), "test-zulip")

            imported_realm = Realm.objects.get(string_id="test-zulip")
            self.assertEqual(
                realm.authentication_methods_dict(),
                imported_realm.authentication_methods_dict(),
            )

            self.export_realm_and_create_auditlog(realm)

            with self.settings(BILLING_ENABLED=True), self.assertLogs(level="WARN") as mock_warn:
                do_import_realm(get_output_dir(), "test-zulip2")

            imported_realm = Realm.objects.get(string_id="test-zulip2")

            self.assertEqual(
                imported_realm.authentication_methods_dict(),
                {"Email": True, "AzureAD": False, "SAML": False},
            )
            self.assertEqual(
                mock_warn.output,
                [
                    "WARNING:root:Dropped restricted authentication method: AzureAD",
                    "WARNING:root:Dropped restricted authentication method: SAML",
                ],
            )

    def test_plan_type(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm
        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)

        self.upload_files_for_user(user)
        self.export_realm_and_create_auditlog(realm)

        with self.settings(BILLING_ENABLED=True), self.assertLogs(level="INFO"):
            imported_realm = do_import_realm(get_output_dir(), "test-zulip-1")
            self.assertEqual(imported_realm.plan_type, Realm.PLAN_TYPE_LIMITED)
            self.assertEqual(imported_realm.max_invites, 100)
            self.assertEqual(imported_realm.upload_quota_gb, 5)
            self.assertEqual(imported_realm.message_visibility_limit, 10000)
            self.assertTrue(
                RealmAuditLog.objects.filter(
                    realm=imported_realm, event_type=AuditLogEventType.REALM_PLAN_TYPE_CHANGED
                ).exists()
            )

        # Importing the same export data twice would cause conflict on unique fields,
        # so instead re-export the original realm via self.export_realm, which handles
        # this issue.
        self.export_realm_and_create_auditlog(realm)

        with self.settings(BILLING_ENABLED=False), self.assertLogs(level="INFO"):
            imported_realm = do_import_realm(get_output_dir(), "test-zulip-2")
            self.assertEqual(imported_realm.plan_type, Realm.PLAN_TYPE_SELF_HOSTED)
            self.assertEqual(imported_realm.max_invites, 100)
            self.assertEqual(imported_realm.upload_quota_gb, None)
            self.assertEqual(imported_realm.message_visibility_limit, None)
            self.assertTrue(
                RealmAuditLog.objects.filter(
                    realm=imported_realm, event_type=AuditLogEventType.REALM_PLAN_TYPE_CHANGED
                ).exists()
            )

    def test_system_usergroup_audit_logs(self) -> None:
        realm = get_realm("zulip")
        self.export_realm_and_create_auditlog(realm)

        # Simulate an external export where user groups are missing.
        data = read_json("realm.json")
        data.pop("zerver_usergroup")
        data.pop("zerver_namedusergroup")
        data.pop("zerver_realmauditlog")
        data["zerver_realm"][0]["zulip_update_announcements_level"] = None
        data["zerver_realm"][0]["zulip_update_announcements_stream"] = None

        # User groups data is missing. So, all the realm group based settings
        # should be None.
        for setting_name in Realm.REALM_PERMISSION_GROUP_SETTINGS:
            data["zerver_realm"][0][setting_name] = None

        with open(export_fn("realm.json"), "wb") as f:
            f.write(orjson.dumps(data))

        with self.assertLogs(level="INFO"):
            imported_realm = do_import_realm(get_output_dir(), "test-zulip-1")
        user_membership_logs = RealmAuditLog.objects.filter(
            realm=imported_realm,
            event_type=AuditLogEventType.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
        ).values_list("modified_user_id", "modified_user_group__name")
        logged_membership_by_user_id = defaultdict(set)
        for user_id, user_group_name in user_membership_logs:
            logged_membership_by_user_id[user_id].add(user_group_name)

        # Make sure that all users get logged as a member in their
        # corresponding system groups.
        for user in UserProfile.objects.filter(realm=imported_realm):
            expected_group_names = {NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP[user.role]["name"]}
            if SystemGroups.MEMBERS in expected_group_names:
                expected_group_names.add(SystemGroups.FULL_MEMBERS)
            self.assertSetEqual(logged_membership_by_user_id[user.id], expected_group_names)

    def test_import_realm_with_unapplied_migrations(self) -> None:
        realm = get_realm("zulip")
        with (
            self.assertRaises(Exception) as e,
            self.assertLogs(level="INFO"),
            patch("zerver.lib.export.parse_migration_status") as mock_export,
            patch("zerver.lib.import_realm.parse_migration_status") as mock_import,
        ):
            mock_export.return_value = self.get_applied_migrations_fixture(
                "with_unapplied_migrations.json"
            )
            mock_import.return_value = self.get_applied_migrations_fixture(
                "with_complete_migrations.json"
            )
            self.export_realm(
                realm,
                export_type=RealmExport.EXPORT_FULL_WITH_CONSENT,
                exportable_user_ids=get_consented_user_ids(realm),
            )
            do_import_realm(get_output_dir(), "test-zulip")

        expected_error_message = self.get_applied_migrations_error_message(
            "unapplied_migrations_error.txt"
        )
        error_message = str(e.exception).strip()
        self.assertEqual(expected_error_message, error_message)

    def test_import_realm_with_extra_migrations(self) -> None:
        realm = get_realm("zulip")
        with (
            self.assertRaises(Exception) as e,
            self.assertLogs(level="INFO"),
            patch("zerver.lib.export.parse_migration_status") as mock_export,
            patch("zerver.lib.import_realm.parse_migration_status") as mock_import,
        ):
            mock_export.return_value = self.get_applied_migrations_fixture(
                "with_complete_migrations.json"
            )
            mock_import.return_value = self.get_applied_migrations_fixture(
                "with_unapplied_migrations.json"
            )
            self.export_realm(
                realm,
                export_type=RealmExport.EXPORT_FULL_WITH_CONSENT,
                exportable_user_ids=get_consented_user_ids(realm),
            )
            do_import_realm(get_output_dir(), "test-zulip")
        expected_error_message = self.get_applied_migrations_error_message(
            "extra_migrations_error.txt"
        )
        error_message = str(e.exception).strip()
        self.assertEqual(expected_error_message, error_message)

    def test_import_realm_with_extra_exported_apps(self) -> None:
        realm = get_realm("zulip")
        with (
            self.settings(BILLING_ENABLED=False),
            self.assertLogs(level="WARNING") as mock_log,
            patch("zerver.lib.export.parse_migration_status") as mock_export,
            patch("zerver.lib.import_realm.parse_migration_status") as mock_import,
        ):
            mock_export.return_value = self.get_applied_migrations_fixture(
                "with_complete_migrations.json"
            )
            mock_import.return_value = self.get_applied_migrations_fixture("with_missing_apps.json")
            self.export_realm_and_create_auditlog(
                realm,
                export_type=RealmExport.EXPORT_FULL_WITH_CONSENT,
                exportable_user_ids=get_consented_user_ids(realm),
            )
            do_import_realm(get_output_dir(), "test-zulip")
        missing_apps_log = [
            "WARNING:root:Exported realm has 'phonenumber' app installed, but this server does not.",
            "WARNING:root:Exported realm has 'sessions' app installed, but this server does not.",
        ]
        # The log output is sorted because it's order is nondeterministic.
        self.assertEqual(sorted(mock_log.output), sorted(missing_apps_log))
        self.assertTrue(Realm.objects.filter(string_id="test-zulip").exists())
        imported_realm = Realm.objects.get(string_id="test-zulip")
        self.assertNotEqual(imported_realm.id, realm.id)

    def test_import_realm_with_missing_apps(self) -> None:
        realm = get_realm("zulip")
        with (
            self.settings(BILLING_ENABLED=False),
            self.assertLogs(level="WARNING") as mock_log,
            patch("zerver.lib.export.parse_migration_status") as mock_export,
            patch("zerver.lib.import_realm.parse_migration_status") as mock_import,
        ):
            mock_export.return_value = self.get_applied_migrations_fixture("with_missing_apps.json")
            mock_import.return_value = self.get_applied_migrations_fixture(
                "with_complete_migrations.json"
            )
            self.export_realm_and_create_auditlog(
                realm,
                export_type=RealmExport.EXPORT_FULL_WITH_CONSENT,
                exportable_user_ids=get_consented_user_ids(realm),
            )
            do_import_realm(get_output_dir(), "test-zulip")
        missing_apps_log = [
            "WARNING:root:This server has 'phonenumber' app installed, but exported realm does not.",
            "WARNING:root:This server has 'sessions' app installed, but exported realm does not.",
        ]
        self.assertEqual(sorted(mock_log.output), sorted(missing_apps_log))
        self.assertTrue(Realm.objects.filter(string_id="test-zulip").exists())
        imported_realm = Realm.objects.get(string_id="test-zulip")
        self.assertNotEqual(imported_realm.id, realm.id)

    def test_check_migration_for_zulip_cloud_realm(self) -> None:
        # This test ensures that `check_migrations_status` correctly handles
        # checking the migrations of a Zulip Cloud-like realm (with zilencer/
        # corporate apps installed) when importing into a self-hosted realm
        # (where these apps are not installed).
        realm = get_realm("zulip")
        with (
            self.settings(BILLING_ENABLED=False),
            self.assertLogs(level="INFO"),
            patch("zerver.lib.export.parse_migration_status") as mock_export,
            patch("zerver.lib.import_realm.parse_migration_status") as mock_import,
        ):
            mock_export.return_value = self.get_applied_migrations_fixture(
                "with_complete_migrations.json"
            )
            self_hosted_migrations = self.get_applied_migrations_fixture(
                "with_complete_migrations.json"
            )
            for key in ["zilencer", "corporate"]:
                self_hosted_migrations.pop(key, None)
            mock_import.return_value = self_hosted_migrations
            self.export_realm_and_create_auditlog(
                realm,
                export_type=RealmExport.EXPORT_FULL_WITH_CONSENT,
                exportable_user_ids=get_consented_user_ids(realm),
            )
            do_import_realm(get_output_dir(), "test-zulip")

        self.assertTrue(Realm.objects.filter(string_id="test-zulip").exists())
        imported_realm = Realm.objects.get(string_id="test-zulip")
        self.assertNotEqual(imported_realm.id, realm.id)

    def test_import_realm_without_migration_status_file(self) -> None:
        realm = get_realm("zulip")
        with patch("zerver.lib.export.export_migration_status"):
            self.export_realm_and_create_auditlog(realm)

        with self.assertRaises(Exception) as e, self.assertLogs(level="INFO"):
            do_import_realm(
                get_output_dir(),
                "test-zulip",
            )
        expected_error_message = "Missing migration_status.json file! Make sure you're using the same Zulip version as the exported realm."
        self.assertEqual(expected_error_message, str(e.exception))

    def test_import_realm_with_different_stated_zulip_version(self) -> None:
        realm = get_realm("zulip")
        self.export_realm_and_create_auditlog(realm)

        with (
            patch("zerver.lib.import_realm.ZULIP_VERSION", "8.0"),
            self.assertRaises(CommandError) as e,
            self.assertLogs(level="INFO"),
        ):
            do_import_realm(
                get_output_dir(),
                "test-zulip",
            )
        expected_error_message = (
            "Error: Export was generated on a different Zulip major version.\n"
            f"Export version: {ZULIP_VERSION}\n"
            "Server version: 8.0"
        )
        self.assertEqual(expected_error_message, str(e.exception))

    def test_import_realm_with_identical_but_unsorted_migrations(self) -> None:
        # Two identical migration sets should pass `check_migrations_status`
        # regardless of how the list of migrations are ordered in
        # `migrations_status.json`.
        realm = get_realm("zulip")
        with (
            self.assertLogs(level="INFO"),
            patch("zerver.lib.export.parse_migration_status") as mock_export,
            patch("zerver.lib.import_realm.parse_migration_status") as mock_import,
        ):
            mock_export.return_value = self.get_applied_migrations_fixture(
                "with_unsorted_migrations_list.json"
            )
            mock_import.return_value = self.get_applied_migrations_fixture(
                "with_complete_migrations.json"
            )
            self.export_realm_and_create_auditlog(
                realm,
                export_type=RealmExport.EXPORT_FULL_WITH_CONSENT,
                exportable_user_ids=get_consented_user_ids(realm),
            )
            do_import_realm(get_output_dir(), "test-zulip")


class SingleUserExportTest(ExportFile):
    def do_files_test(self, is_s3: bool) -> None:
        output_dir = make_export_output_dir()

        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        self.upload_files_for_user(cordelia)
        self.upload_files_for_user(othello, emoji_name="bogus")  # try to pollute export

        with self.assertLogs(level="INFO"):
            do_export_user(cordelia, output_dir)

        self.verify_uploads(cordelia, is_s3=is_s3)
        self.verify_avatars(cordelia)
        self.verify_emojis(cordelia, is_s3=is_s3)

    def test_local_files(self) -> None:
        self.do_files_test(is_s3=False)

    @use_s3_backend
    def test_s3_files(self) -> None:
        create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET, settings.S3_AVATAR_BUCKET)
        self.do_files_test(is_s3=True)

    def test_message_data(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        polonius = self.example_user("polonius")

        self.subscribe(cordelia, "Denmark")

        smile_message_id = self.send_stream_message(hamlet, "Denmark", "SMILE!")

        check_add_reaction(
            user_profile=cordelia,
            message_id=smile_message_id,
            emoji_name="smile",
            emoji_code=None,
            reaction_type=None,
        )
        reaction = Reaction.objects.order_by("id").last()
        assert reaction

        # Send a message that Cordelia should not have in the export.
        self.send_stream_message(othello, "Denmark", "bogus")

        hi_stream_message_id = self.send_stream_message(cordelia, "Denmark", "hi stream")
        assert most_recent_usermessage(cordelia).message_id == hi_stream_message_id

        # Try to fool the export again
        self.send_personal_message(othello, hamlet)
        self.send_group_direct_message(othello, [hamlet, polonius])

        hi_hamlet_message_id = self.send_personal_message(cordelia, hamlet, "hi hamlet")

        hi_peeps_message_id = self.send_group_direct_message(
            cordelia, [hamlet, othello], "hi peeps"
        )
        bye_peeps_message_id = self.send_group_direct_message(
            othello, [cordelia, hamlet], "bye peeps"
        )

        bye_hamlet_message_id = self.send_personal_message(cordelia, hamlet, "bye hamlet")

        hi_myself_message_id = self.send_personal_message(cordelia, cordelia, "hi myself")
        bye_stream_message_id = self.send_stream_message(cordelia, "Denmark", "bye stream")

        output_dir = make_export_output_dir()
        cordelia = self.example_user("cordelia")

        with self.assertLogs(level="INFO"):
            do_export_user(cordelia, output_dir)

        messages = read_json("messages-000001.json")

        direct_message_group_name = (
            "Cordelia, Lear's daughter, King Hamlet, Othello, the Moor of Venice"
        )

        excerpt = [
            (rec["id"], rec["content"], rec["recipient_name"])
            for rec in messages["zerver_message"][-8:]
        ]
        self.assertEqual(
            excerpt,
            [
                (smile_message_id, "SMILE!", "Denmark"),
                (hi_stream_message_id, "hi stream", "Denmark"),
                (hi_hamlet_message_id, "hi hamlet", hamlet.full_name),
                (hi_peeps_message_id, "hi peeps", direct_message_group_name),
                (bye_peeps_message_id, "bye peeps", direct_message_group_name),
                (bye_hamlet_message_id, "bye hamlet", hamlet.full_name),
                (hi_myself_message_id, "hi myself", cordelia.full_name),
                (bye_stream_message_id, "bye stream", "Denmark"),
            ],
        )

    def test_user_data(self) -> None:
        # We register checkers during test setup, and then we call them at the end.
        checkers = {}

        def checker(f: Callable[[list[Record]], None]) -> Callable[[list[Record]], None]:
            # Every checker function that gets decorated here should be named
            # after one of the tables that we export in the single-user
            # export. The table name then is used by code toward the end of the
            # test to determine which portion of the data from users.json
            # to pass into the checker.
            table_name = f.__name__
            assert table_name not in checkers
            checkers[table_name] = f
            return f

        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        realm = cordelia.realm
        scotland = get_stream("Scotland", realm)
        client = get_client("some_app")
        now = timezone_now()

        @checker
        def zerver_userprofile(records: list[Record]) -> None:
            (rec,) = records
            self.assertEqual(rec["id"], cordelia.id)
            self.assertEqual(rec["email"], cordelia.email)
            self.assertEqual(rec["full_name"], cordelia.full_name)

        """
        Try to set up the test data roughly in order of table name, where
        possible, just to make it a bit easier to read the test.
        """

        do_add_alert_words(cordelia, ["pizza"])
        do_add_alert_words(hamlet, ["bogus"])

        @checker
        def zerver_alertword(records: list[Record]) -> None:
            self.assertEqual(records[-1]["word"], "pizza")

        favorite_city = try_add_realm_custom_profile_field(
            realm,
            "Favorite city",
            CustomProfileField.SHORT_TEXT,
        )

        def set_favorite_city(user: UserProfile, city: str) -> None:
            do_update_user_custom_profile_data_if_changed(
                user, [dict(id=favorite_city.id, value=city)]
            )

        set_favorite_city(cordelia, "Seattle")
        set_favorite_city(othello, "Moscow")

        @checker
        def zerver_customprofilefieldvalue(records: list[Record]) -> None:
            (rec,) = records
            self.assertEqual(rec["field"], favorite_city.id)
            self.assertEqual(rec["rendered_value"], "<p>Seattle</p>")

        do_mute_user(cordelia, othello)
        do_mute_user(hamlet, cordelia)  # should be ignored

        @checker
        def zerver_muteduser(records: list[Record]) -> None:
            self.assertEqual(records[-1]["muted_user"], othello.id)

        do_add_navigation_view(hamlet, "inbox", True)
        do_add_navigation_view(cordelia, "recent", False)

        @checker
        def zerver_navigationview(records: list[Record]) -> None:
            self.assertEqual(records[-1]["fragment"], "recent")
            self.assertEqual(records[-1]["is_pinned"], False)

        smile_message_id = self.send_stream_message(hamlet, "Denmark")

        check_add_reaction(
            user_profile=cordelia,
            message_id=smile_message_id,
            emoji_name="smile",
            emoji_code=None,
            reaction_type=None,
        )
        reaction = Reaction.objects.order_by("id").last()

        @checker
        def zerver_reaction(records: list[Record]) -> None:
            assert reaction
            self.assertEqual(
                records[-1],
                dict(
                    id=reaction.id,
                    user_profile=cordelia.id,
                    emoji_name="smile",
                    reaction_type="unicode_emoji",
                    emoji_code=reaction.emoji_code,
                    message=smile_message_id,
                ),
            )

        # We violate alphabetical order here but this creates a RealmAuditLog entry and we want the stream
        # subscription event which will occur next to be the last RealmAuditLog entry.
        do_create_saved_snippet("snippet title", "snippet content", cordelia)

        @checker
        def zerver_savedsnippet(records: list[Record]) -> None:
            self.assertEqual(records[-1]["title"], "snippet title")
            self.assertEqual(records[-1]["content"], "snippet content")

        self.subscribe(cordelia, "Scotland")

        create_stream_if_needed(realm, "bogus")
        self.subscribe(othello, "bogus")

        @checker
        def zerver_recipient(records: list[Record]) -> None:
            last_recipient = Recipient.objects.get(id=records[-1]["id"])
            self.assertEqual(last_recipient.type, Recipient.STREAM)
            stream_id = last_recipient.type_id
            self.assertEqual(stream_id, get_stream("Scotland", realm).id)

        @checker
        def zerver_stream(records: list[Record]) -> None:
            streams = {rec["name"] for rec in records}
            self.assertEqual(streams, {"Scotland", "Verona"})

        @checker
        def zerver_subscription(records: list[Record]) -> None:
            last_recipient = Recipient.objects.get(id=records[-1]["recipient"])
            self.assertEqual(last_recipient.type, Recipient.STREAM)
            stream_id = last_recipient.type_id
            self.assertEqual(stream_id, get_stream("Scotland", realm).id)

        UserActivity.objects.create(
            user_profile_id=cordelia.id,
            client_id=client.id,
            query="/some/endpoint",
            count=5,
            last_visit=now,
        )
        UserActivity.objects.create(
            user_profile_id=othello.id,
            client_id=client.id,
            query="/bogus",
            count=20,
            last_visit=now,
        )

        @checker
        def zerver_useractivity(records: list[Record]) -> None:
            (rec,) = records
            self.assertEqual(
                rec,
                dict(
                    client=client.id,
                    count=5,
                    id=rec["id"],
                    last_visit=rec["last_visit"],
                    query="/some/endpoint",
                    user_profile=cordelia.id,
                ),
            )
            self.assertEqual(make_datetime(rec["last_visit"]), now)

        do_update_user_activity_interval(cordelia, now)
        do_update_user_activity_interval(othello, now)

        @checker
        def zerver_useractivityinterval(records: list[Record]) -> None:
            (rec,) = records
            self.assertEqual(rec["user_profile"], cordelia.id)
            self.assertEqual(make_datetime(rec["start"]), now)

        do_update_user_presence(cordelia, client, now, UserPresence.LEGACY_STATUS_ACTIVE_INT)
        do_update_user_presence(othello, client, now, UserPresence.LEGACY_STATUS_IDLE_INT)

        @checker
        def zerver_userpresence(records: list[Record]) -> None:
            self.assertEqual(make_datetime(records[-1]["last_connected_time"]), now)
            self.assertEqual(make_datetime(records[-1]["last_active_time"]), now)

        do_update_user_status(
            user_profile=cordelia,
            away=None,
            status_text="on vacation",
            client_id=client.id,
            emoji_name=None,
            emoji_code=None,
            reaction_type=None,
            scheduled_end_time=None,
        )

        do_update_user_status(
            user_profile=othello,
            away=False,
            status_text="at my desk",
            client_id=client.id,
            emoji_name=None,
            emoji_code=None,
            reaction_type=None,
            scheduled_end_time=None,
        )

        @checker
        def zerver_userstatus(records: list[Record]) -> None:
            rec = records[-1]
            self.assertEqual(rec["status_text"], "on vacation")

        do_set_user_topic_visibility_policy(
            cordelia,
            scotland,
            "bagpipe music",
            visibility_policy=UserTopic.VisibilityPolicy.MUTED,
        )
        do_set_user_topic_visibility_policy(
            othello, scotland, "nessie", visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )

        @checker
        def zerver_usertopic(records: list[Record]) -> None:
            rec = records[-1]
            self.assertEqual(rec["topic_name"], "bagpipe music")
            self.assertEqual(rec["visibility_policy"], UserTopic.VisibilityPolicy.MUTED)

        """
        For some tables we don't bother with super realistic test data
        setup.
        """
        UserCount.objects.create(
            user=cordelia, realm=realm, property="whatever", value=42, end_time=now
        )
        UserCount.objects.create(
            user=othello, realm=realm, property="bogus", value=999999, end_time=now
        )

        @checker
        def analytics_usercount(records: list[Record]) -> None:
            (rec,) = records
            self.assertEqual(rec["value"], 42)

        OnboardingStep.objects.create(user=cordelia, onboarding_step="topics")
        OnboardingStep.objects.create(user=othello, onboarding_step="bogus")

        @checker
        def zerver_onboardingstep(records: list[Record]) -> None:
            self.assertEqual(records[-1]["onboarding_step"], "topics")

        """
        The zerver_realmauditlog checker basically assumes that
        we subscribed Cordelia to Scotland.
        """

        @checker
        def zerver_realmauditlog(records: list[Record]) -> None:
            self.assertEqual(records[-1]["modified_stream"], scotland.id)

        output_dir = make_export_output_dir()

        with self.assertLogs(level="INFO"):
            do_export_user(cordelia, output_dir)

        user = read_json("user.json")

        for table_name, f in checkers.items():
            f(user[table_name])

        for table_name in user:
            if table_name not in checkers:
                raise AssertionError(
                    f"""
                    Please create a checker called "{table_name}"
                    to check the user["{table_name}"] data in users.json.

                    Please be thoughtful about where you introduce
                    the new code--if you read the test, the patterns
                    for how to test table data should be clear.
                    Try to mostly keep checkers in alphabetical order.
                    """
                )


class GetFKFieldNameTest(ZulipTestCase):
    def test_get_fk_field_name(self) -> None:
        self.assertEqual(get_fk_field_name(UserProfile, Realm), "realm")
        self.assertEqual(get_fk_field_name(Reaction, Stream), None)
        self.assertEqual(get_fk_field_name(Message, UserProfile), "sender")
