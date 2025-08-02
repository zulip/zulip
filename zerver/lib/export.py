# This is the main code for the `./manage.py export` data export tool.
# User docs: https://zulip.readthedocs.io/en/latest/production/export-and-import.html
#
# Most developers will interact with this primarily when they add a
# new table to the schema, in which case they likely need to (1) add
# it the lists in `ALL_ZULIP_TABLES` and similar data structures and
# (2) if it doesn't belong in EXCLUDED_TABLES, add a Config object for
# it to get_realm_config.
import glob
import hashlib
import logging
import os
import random
import secrets
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from datetime import datetime
from email.headerregistry import Address
from functools import cache
from typing import TYPE_CHECKING, Any, Optional, TypeAlias, TypedDict, cast
from urllib.parse import urlsplit

import orjson
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.models import Exists, Model, OuterRef, Q
from django.forms.models import model_to_dict
from django.utils.timezone import is_naive as timezone_is_naive
from django.utils.timezone import now as timezone_now
from psycopg2 import sql

import zerver.lib.upload
from analytics.models import RealmCount, StreamCount, UserCount
from scripts.lib.zulip_tools import overwrite_symlink
from version import ZULIP_VERSION
from zerver.lib.avatar_hash import user_avatar_base_path_from_ids
from zerver.lib.migration_status import MigrationStatusJson, parse_migration_status
from zerver.lib.pysa import mark_sanitized
from zerver.lib.stream_color import STREAM_ASSIGNMENT_COLORS
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.upload.s3 import get_bucket
from zerver.lib.utils import get_fk_field_name
from zerver.models import (
    AlertWord,
    Attachment,
    BotConfigData,
    BotStorageData,
    ChannelFolder,
    Client,
    CustomProfileField,
    CustomProfileFieldValue,
    DefaultStream,
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
    RealmAuthenticationMethod,
    RealmDomain,
    RealmEmoji,
    RealmExport,
    RealmFilter,
    RealmPlayground,
    RealmUserDefault,
    Recipient,
    ScheduledMessage,
    Service,
    Stream,
    Subscription,
    UserActivity,
    UserActivityInterval,
    UserGroup,
    UserGroupMembership,
    UserMessage,
    UserPresence,
    UserProfile,
    UserStatus,
    UserTopic,
)
from zerver.models.presence import PresenceSequence
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_fake_email_domain, get_realm
from zerver.models.saved_snippets import SavedSnippet
from zerver.models.users import ExternalAuthID, get_system_bot, get_user_profile_by_id

if TYPE_CHECKING:
    from mypy_boto3_s3.service_resource import Object

# Custom mypy types follow:
Record: TypeAlias = dict[str, Any]
TableName = str
TableData: TypeAlias = dict[TableName, list[Record]]
Field = str
Path = str
Context: TypeAlias = dict[str, Any]
FilterArgs: TypeAlias = dict[str, Any]
IdSource: TypeAlias = tuple[TableName, Field]
SourceFilter: TypeAlias = Callable[[Record], bool]

CustomFetch: TypeAlias = Callable[[TableData, Context], None]
CustomReturnIds: TypeAlias = Callable[[TableData], set[int]]
CustomProcessResults: TypeAlias = Callable[[list[Record], Context], list[Record]]


class MessagePartial(TypedDict):
    zerver_message: list[Record]
    zerver_userprofile_ids: list[int]
    realm_id: int


MESSAGE_BATCH_CHUNK_SIZE = 1000

ALL_ZULIP_TABLES = {
    "analytics_fillstate",
    "analytics_installationcount",
    "analytics_realmcount",
    "analytics_streamcount",
    "analytics_usercount",
    "otp_static_staticdevice",
    "otp_static_statictoken",
    "otp_totp_totpdevice",
    "social_auth_association",
    "social_auth_code",
    "social_auth_nonce",
    "social_auth_partial",
    "social_auth_usersocialauth",
    "two_factor_phonedevice",
    "zerver_alertword",
    "zerver_archivedattachment",
    "zerver_archivedattachment_messages",
    "zerver_archivedmessage",
    "zerver_archivedusermessage",
    "zerver_attachment",
    "zerver_attachment_messages",
    "zerver_attachment_scheduled_messages",
    "zerver_archivedreaction",
    "zerver_archivedsubmessage",
    "zerver_archivetransaction",
    "zerver_botconfigdata",
    "zerver_botstoragedata",
    "zerver_channelemailaddress",
    "zerver_channelfolder",
    "zerver_client",
    "zerver_customprofilefield",
    "zerver_customprofilefieldvalue",
    "zerver_defaultstream",
    "zerver_defaultstreamgroup",
    "zerver_defaultstreamgroup_streams",
    "zerver_draft",
    "zerver_emailchangestatus",
    "zerver_externalauthid",
    "zerver_groupgroupmembership",
    "zerver_huddle",
    "zerver_imageattachment",
    "zerver_message",
    "zerver_missedmessageemailaddress",
    "zerver_multiuseinvite",
    "zerver_multiuseinvite_streams",
    "zerver_multiuseinvite_groups",
    "zerver_namedusergroup",
    "zerver_navigationview",
    "zerver_onboardingstep",
    "zerver_onboardingusermessage",
    "zerver_preregistrationrealm",
    "zerver_preregistrationuser",
    "zerver_preregistrationuser_streams",
    "zerver_preregistrationuser_groups",
    "zerver_presencesequence",
    "zerver_pushdevice",
    "zerver_pushdevicetoken",
    "zerver_reaction",
    "zerver_realm",
    "zerver_realmauditlog",
    "zerver_realmauthenticationmethod",
    "zerver_realmdomain",
    "zerver_realmemoji",
    "zerver_realmexport",
    "zerver_realmfilter",
    "zerver_realmplayground",
    "zerver_realmreactivationstatus",
    "zerver_realmuserdefault",
    "zerver_recipient",
    "zerver_savedsnippet",
    "zerver_scheduledemail",
    "zerver_scheduledemail_users",
    "zerver_scheduledmessage",
    "zerver_scheduledmessagenotificationemail",
    "zerver_service",
    "zerver_stream",
    "zerver_submessage",
    "zerver_subscription",
    "zerver_useractivity",
    "zerver_useractivityinterval",
    "zerver_usergroup",
    "zerver_usergroupmembership",
    "zerver_usermessage",
    "zerver_userpresence",
    "zerver_userprofile",
    "zerver_userprofile_groups",
    "zerver_userprofile_user_permissions",
    "zerver_userstatus",
    "zerver_usertopic",
    "zerver_muteduser",
}

# This set contains those database tables that we expect to not be
# included in the export.  This tool does validation to ensure that
# every table in the database is either exported or listed here, to
# ensure we never accidentally fail to export a table.
NON_EXPORTED_TABLES = {
    # These invitation/confirmation flow tables don't make sense to
    # export, since invitations links will be broken by the server URL
    # change anyway:
    "zerver_emailchangestatus",
    "zerver_multiuseinvite",
    "zerver_multiuseinvite_streams",
    "zerver_multiuseinvite_groups",
    "zerver_preregistrationrealm",
    "zerver_preregistrationuser",
    "zerver_preregistrationuser_streams",
    "zerver_preregistrationuser_groups",
    "zerver_realmreactivationstatus",
    # Missed message addresses are low value to export since
    # missed-message email addresses include the server's hostname and
    # expire after a few days.
    "zerver_missedmessageemailaddress",
    # Scheduled message notification email data is for internal use by the server.
    "zerver_scheduledmessagenotificationemail",
    # When switching servers, clients will need to re-log in and
    # reregister for push notifications anyway.
    "zerver_pushdevice",
    "zerver_pushdevicetoken",
    # We don't use these generated Django tables
    "zerver_userprofile_groups",
    "zerver_userprofile_user_permissions",
    # These is used for scheduling future activity; it could make
    # sense to export, but is relatively low value.
    "zerver_scheduledemail",
    "zerver_scheduledemail_users",
    # These tables are related to a user's 2FA authentication
    # configuration, which will need to be set up again on the new
    # server.
    "two_factor_phonedevice",
    "otp_static_staticdevice",
    "otp_static_statictoken",
    "otp_totp_totpdevice",
    # These archive tables should not be exported (they are to support
    # restoring content accidentally deleted due to software bugs in
    # the retention policy feature)
    "zerver_archivedmessage",
    "zerver_archivedusermessage",
    "zerver_archivedattachment",
    "zerver_archivedattachment_messages",
    "zerver_archivedreaction",
    "zerver_archivedsubmessage",
    "zerver_archivetransaction",
    # Social auth tables are not needed post-export, since we don't
    # use any of this state outside of a direct authentication flow.
    "social_auth_association",
    "social_auth_code",
    "social_auth_nonce",
    "social_auth_partial",
    "social_auth_usersocialauth",
    # We will likely never want to migrate this table, since it's a
    # total of all the realmcount values on the server.  Might need to
    # recompute it after a fillstate import.
    "analytics_installationcount",
    # Fillstate will require some cleverness to do the right partial export.
    "analytics_fillstate",
    # These are for unfinished features; we'll want to add them to the
    # export before they reach full production status.
    "zerver_defaultstreamgroup",
    "zerver_defaultstreamgroup_streams",
    "zerver_submessage",
    # Drafts don't need to be exported as they are supposed to be more ephemeral.
    "zerver_draft",
    # The importer cannot trust ImageAttachment objects anyway and needs to check
    # and process images for thumbnailing on its own.
    "zerver_imageattachment",
    # ChannelEmailAddress entries are low value to export since
    # channel email addresses include the server's hostname.
    "zerver_channelemailaddress",
    # For any tables listed below here, it's a bug that they are not present in the export.
}

IMPLICIT_TABLES = {
    # ManyToMany relationships are exported implicitly when importing
    # the parent table.
    "zerver_attachment_messages",
    "zerver_attachment_scheduled_messages",
}

ATTACHMENT_TABLES = {
    "zerver_attachment",
}

MESSAGE_TABLES = {
    # message tables get special treatment, because they're by far our
    # largest tables and need to be paginated.
    "zerver_message",
    "zerver_usermessage",
    # zerver_reaction belongs here, since it's added late because it
    # has a foreign key into the Message table.
    "zerver_reaction",
}

# These get their own file as analytics data can be quite large and
# would otherwise make realm.json unpleasant to manually inspect
ANALYTICS_TABLES = {
    "analytics_realmcount",
    "analytics_streamcount",
    "analytics_usercount",
}

# This data structure lists all the Django DateTimeField fields in the
# data model.  These are converted to floats during the export process
# via floatify_datetime_fields, and back during the import process.
#
# TODO: This data structure could likely eventually be replaced by
# inspecting the corresponding Django models
DATE_FIELDS: dict[TableName, list[Field]] = {
    "analytics_installationcount": ["end_time"],
    "analytics_realmcount": ["end_time"],
    "analytics_streamcount": ["end_time"],
    "analytics_usercount": ["end_time"],
    "zerver_attachment": ["create_time"],
    "zerver_channelfolder": ["date_created"],
    "zerver_externalauthid": ["date_created"],
    "zerver_message": ["last_edit_time", "date_sent"],
    "zerver_muteduser": ["date_muted"],
    "zerver_realmauditlog": ["event_time"],
    "zerver_realm": ["date_created"],
    "zerver_realmexport": [
        "date_requested",
        "date_started",
        "date_succeeded",
        "date_failed",
        "date_deleted",
    ],
    "zerver_savedsnippet": ["date_created"],
    "zerver_scheduledmessage": ["scheduled_timestamp", "request_timestamp"],
    "zerver_stream": ["date_created"],
    "zerver_namedusergroup": ["date_created"],
    "zerver_useractivityinterval": ["start", "end"],
    "zerver_useractivity": ["last_visit"],
    "zerver_onboardingstep": ["timestamp"],
    "zerver_userpresence": ["last_active_time", "last_connected_time"],
    "zerver_userprofile": ["date_joined", "last_login", "last_reminder"],
    "zerver_userprofile_mirrordummy": ["date_joined", "last_login", "last_reminder"],
    "zerver_userstatus": ["timestamp"],
    "zerver_usertopic": ["last_updated"],
}


def sanity_check_output(data: TableData) -> None:
    # First, we verify that the export tool has a declared
    # configuration for every table declared in the `models` modules.
    target_models = [
        *apps.get_app_config("analytics").get_models(include_auto_created=True),
        *apps.get_app_config("django_otp").get_models(include_auto_created=True),
        *apps.get_app_config("otp_static").get_models(include_auto_created=True),
        *apps.get_app_config("otp_totp").get_models(include_auto_created=True),
        *apps.get_app_config("phonenumber").get_models(include_auto_created=True),
        *apps.get_app_config("social_django").get_models(include_auto_created=True),
        *apps.get_app_config("two_factor").get_models(include_auto_created=True),
        *apps.get_app_config("zerver").get_models(include_auto_created=True),
    ]
    all_tables_db = {model._meta.db_table for model in target_models}

    # These assertion statements will fire when we add a new database
    # table that is not included in Zulip's data exports.  Generally,
    # you can add your new table to `ALL_ZULIP_TABLES` and
    # `NON_EXPORTED_TABLES` during early work on a new feature so that
    # CI passes.
    #
    # We'll want to make sure we handle it for exports before
    # releasing the new feature, but doing so correctly requires some
    # expertise on this export system.
    error_message = f"""
    It appears you've added a new database table, but haven't yet
    registered it in ALL_ZULIP_TABLES and the related declarations
    in {__file__} for what to include in data exports.
    """

    assert all_tables_db == ALL_ZULIP_TABLES, error_message
    assert NON_EXPORTED_TABLES.issubset(ALL_ZULIP_TABLES), error_message
    assert IMPLICIT_TABLES.issubset(ALL_ZULIP_TABLES), error_message
    assert ATTACHMENT_TABLES.issubset(ALL_ZULIP_TABLES), error_message
    assert ANALYTICS_TABLES.issubset(ALL_ZULIP_TABLES), error_message

    tables = set(ALL_ZULIP_TABLES)
    tables -= NON_EXPORTED_TABLES
    tables -= IMPLICIT_TABLES
    tables -= MESSAGE_TABLES
    tables -= ATTACHMENT_TABLES
    tables -= ANALYTICS_TABLES

    for table in tables:
        if table not in data:
            logging.warning("??? NO DATA EXPORTED FOR TABLE %s!!!", table)


def write_data_to_file(output_file: Path, data: Any) -> None:
    """
    IMPORTANT: You generally don't want to call this directly.

    Instead use one of the higher level helpers:

        write_table_data
        write_records_json_file

    The one place we call this directly is for message partials.
    """
    with open(output_file, "wb") as f:
        # Because we don't pass a default handler, OPT_PASSTHROUGH_DATETIME
        # actually causes orjson to raise a TypeError on datetime objects. This
        # is what we want, because it helps us check that we correctly
        # post-processed them to serialize to UNIX timestamps rather than ISO
        # 8601 strings for historical reasons.
        f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2 | orjson.OPT_PASSTHROUGH_DATETIME))
    logging.info("Finished writing %s", output_file)


def write_table_data(output_file: str, data: dict[str, Any]) -> None:
    # We sort by ids mostly so that humans can quickly do diffs
    # on two export jobs to see what changed (either due to new
    # data arriving or new code being deployed).
    for value in data.values():
        if isinstance(value, list):
            value.sort(key=lambda row: row["id"])

    assert output_file.endswith(".json")

    write_data_to_file(output_file, data)


def write_records_json_file(output_dir: str, records: list[dict[str, Any]]) -> None:
    # We want a somewhat deterministic sorting order here. All of our
    # versions of records.json include a "path" field in each element,
    # even though there's some variation among avatars/emoji/realm_icons/uploads
    # in other fields that get written.
    #
    # The sorting order of paths isn't entirely sensical to humans,
    # because they include ids and even some random numbers,
    # but if you export the same realm twice, you should get identical results.
    records.sort(key=lambda record: record["path"])

    output_file = os.path.join(output_dir, "records.json")
    with open(output_file, "wb") as f:
        # For legacy reasons we allow datetime objects here, unlike
        # write_data_to_file.
        f.write(orjson.dumps(records, option=orjson.OPT_INDENT_2))
    logging.info("Finished writing %s", output_file)


def make_raw(query: Any, exclude: list[Field] | None = None) -> list[Record]:
    """
    Takes a Django query and returns a JSONable list
    of dictionaries corresponding to the database rows.
    """
    rows = []
    for instance in query:
        data = model_to_dict(instance, exclude=exclude)
        """
        In Django 1.11.5, model_to_dict evaluates the QuerySet of
        many-to-many field to give us a list of instances. We require
        a list of primary keys, so we get the primary keys from the
        instances below.
        """
        for field in instance._meta.many_to_many:
            if exclude is not None and field.name in exclude:
                continue
            value = data[field.name]
            data[field.name] = [row.id for row in value]

        rows.append(data)

    return rows


def floatify_datetime_fields(data: TableData, table: TableName) -> None:
    for item in data[table]:
        for field in DATE_FIELDS[table]:
            dt = item[field]
            if dt is None:
                continue
            assert isinstance(dt, datetime)
            assert not timezone_is_naive(dt)
            item[field] = dt.timestamp()


class Config:
    """A Config object configures a single table for exporting (and, maybe
    some day importing as well.  This configuration defines what
    process needs to be followed to correctly extract the set of
    objects to export.

    You should never mutate Config objects as part of the export;
    instead use the data to determine how you populate other
    data structures.

    There are parent/children relationships between Config objects.
    The parent should be instantiated first.  The child will
    append itself to the parent's list of children.

    """

    def __init__(
        self,
        table: str | None = None,
        model: Any | None = None,
        normal_parent: Optional["Config"] = None,
        virtual_parent: Optional["Config"] = None,
        filter_args: FilterArgs | None = None,
        custom_fetch: CustomFetch | None = None,
        custom_tables: list[TableName] | None = None,
        custom_return_ids: CustomReturnIds | None = None,
        custom_process_results: CustomProcessResults | None = None,
        concat_and_destroy: list[TableName] | None = None,
        id_source: IdSource | None = None,
        source_filter: SourceFilter | None = None,
        include_rows: Field | None = None,
        is_seeded: bool = False,
        exclude: list[Field] | None = None,
        limit_to_consenting_users: bool | None = None,
        collect_client_ids: bool = False,
    ) -> None:
        assert table or custom_tables
        self.table = table
        self.model = model
        self.normal_parent = normal_parent
        self.virtual_parent = virtual_parent
        self.filter_args = filter_args
        self.include_rows = include_rows
        self.is_seeded = is_seeded
        self.exclude = exclude
        self.custom_fetch = custom_fetch
        self.custom_tables = custom_tables
        self.custom_return_ids = custom_return_ids
        self.custom_process_results = custom_process_results
        self.concat_and_destroy = concat_and_destroy
        self.id_source = id_source
        self.source_filter = source_filter
        self.limit_to_consenting_users = limit_to_consenting_users
        self.collect_client_ids = collect_client_ids
        self.children: list[Config] = []

        if self.include_rows:
            assert self.include_rows.endswith("_id__in")

        if self.custom_fetch:
            # enforce a naming convention
            assert self.custom_fetch.__name__.startswith("custom_fetch_")
            if self.normal_parent is not None:
                raise AssertionError(
                    """
                    If you have a custom fetcher, then specify
                    your parent as a virtual_parent.
                    """
                )

            if self.collect_client_ids:
                raise AssertionError(
                    """
                    If you're using custom_fetch with collect_client_ids, you need to
                    extend the related logic to handle how to collect Client ids with your
                    customer fetcher.
                    """
                )

        if normal_parent is not None:
            self.parent: Config | None = normal_parent
        else:
            self.parent = None

        if virtual_parent is not None and normal_parent is not None:
            raise AssertionError(
                """
                If you specify a normal_parent, please
                do not create a virtual_parent.
                """
            )

        if normal_parent is not None:
            normal_parent.children.append(self)
        elif virtual_parent is not None:
            virtual_parent.children.append(self)
        elif is_seeded is None:
            raise AssertionError(
                """
                You must specify a parent if you are
                not using is_seeded.
                """
            )

        if (
            (parent := normal_parent or virtual_parent) is not None
            and parent.table == "zerver_userprofile"
            and limit_to_consenting_users is None
        ):
            raise AssertionError(
                """
                Config having UserProfile as a parent must pass limit_to_consenting_users
                explicitly.
                """
            )

        if self.id_source is not None:
            if self.virtual_parent is None:
                raise AssertionError(
                    """
                    You must specify a virtual_parent if you are
                    using id_source."""
                )
            if self.id_source[0] != self.virtual_parent.table:
                raise AssertionError(
                    f"""
                    Configuration error.  To populate {self.table}, you
                    want data from {self.id_source[0]}, but that differs from
                    the table name of your virtual parent ({self.virtual_parent.table}),
                    which suggests you many not have set up
                    the ordering correctly.  You may simply
                    need to assign a virtual_parent, or there
                    may be deeper issues going on."""
                )

        if self.limit_to_consenting_users:
            # Combining these makes no sense. limit_to_consenting_users is used to restrict queries
            # for Configs which use include_rows="user_profile_id__in" to only pass user ids of users
            # who have consented to private data export.
            # If a Config defines its own custom_fetch, then it is fully responsible for doing its own
            # queries - so it doesn't integrate with limit_to_consenting_users.
            assert not self.custom_fetch

            assert include_rows in ["user_profile_id__in", "user_id__in", "bot_profile_id__in"]
            assert normal_parent is not None and normal_parent.table == "zerver_userprofile"

    def return_ids(self, response: TableData) -> set[int]:
        if self.custom_return_ids is not None:
            return self.custom_return_ids(response)
        else:
            assert self.table is not None
            return {row["id"] for row in response[self.table]}


def export_from_config(
    response: TableData,
    config: Config,
    seed_object: Any | None = None,
    context: Context | None = None,
) -> None:
    table = config.table
    parent = config.parent
    model = config.model

    if context is None:
        context = {}

    if config.custom_tables:
        exported_tables = config.custom_tables
    else:
        assert table is not None, """
            You must specify config.custom_tables if you
            are not specifying config.table"""
        exported_tables = [table]

    for t in exported_tables:
        logging.info("Exporting via export_from_config:  %s", t)

    rows = None
    if config.is_seeded:
        rows = [seed_object]

    elif config.custom_fetch:
        config.custom_fetch(
            response,
            context,
        )
        if config.custom_tables:
            for t in config.custom_tables:
                if t not in response:
                    raise AssertionError(f"Custom fetch failed to populate {t}")

    elif config.concat_and_destroy:
        # When we concat_and_destroy, we are working with
        # temporary "tables" that are lists of records that
        # should already be ready to export.
        data: list[Record] = []
        for t in config.concat_and_destroy:
            data += response[t]
            del response[t]
            logging.info("Deleted temporary %s", t)
        assert table is not None
        response[table] = data

    elif config.normal_parent:
        # In this mode, our current model is figuratively Article,
        # and normal_parent is figuratively Blog, and
        # now we just need to get all the articles
        # contained by the blogs.
        model = config.model
        assert parent is not None
        assert parent.table is not None
        assert config.include_rows is not None
        parent_ids = parent.return_ids(response)
        filter_params: dict[str, object] = {config.include_rows: parent_ids}

        if config.filter_args is not None:
            filter_params.update(config.filter_args)
        if config.limit_to_consenting_users:
            if "realm" in context:
                realm = context["realm"]
                export_type = context["export_type"]
                assert isinstance(realm, Realm)
                if export_type == RealmExport.EXPORT_PUBLIC:
                    # In a public export, no private data is exported, so
                    # no users are considered consenting.
                    consenting_user_ids: set[int] | None = set()
                elif export_type == RealmExport.EXPORT_FULL_WITH_CONSENT:
                    consenting_user_ids = context["exportable_user_ids"]
                else:
                    assert export_type == RealmExport.EXPORT_FULL_WITHOUT_CONSENT
                    # In a full export without consent, the concept is meaningless,
                    # so set this to None. All private data will be exported without consulting
                    # consenting_user_ids so we set this to None so that any code in this flow
                    # which (incorrectly) tries to access them fails explicitly.
                    consenting_user_ids = None
            else:
                # Single user export. This should not be really relevant, because
                # limit_to_consenting_users is unlikely to be used in Configs in that codepath,
                # as we should be exporting only a single user's data anyway; but it's still
                # useful to have this case written correctly for robustness.
                assert "user" in context
                assert isinstance(context["user"], UserProfile)
                export_type = None
                consenting_user_ids = {context["user"].id}

            user_profile_id_in_key = config.include_rows

            # Sanity check.
            assert user_profile_id_in_key in [
                "user_profile_id__in",
                "user_id__in",
                "bot_profile_id__in",
            ]

            user_profile_id_in = filter_params[user_profile_id_in_key]
            assert isinstance(user_profile_id_in, set)

            if export_type != RealmExport.EXPORT_FULL_WITHOUT_CONSENT:
                assert consenting_user_ids is not None
                filter_params[user_profile_id_in_key] = consenting_user_ids.intersection(
                    user_profile_id_in
                )

        assert model is not None
        try:
            query = model.objects.filter(**filter_params)
        except Exception:
            print(
                f"""
                Something about your Config seems to make it difficult
                to construct a query.

                table: {table}
                parent: {parent.table}

                filter_params: {filter_params}
                """
            )
            raise

        rows = list(query)

    elif config.id_source:
        # In this mode, we are the figurative Blog, and we now
        # need to look at the current response to get all the
        # blog ids from the Article rows we fetched previously.
        model = config.model
        assert model is not None
        # This will be a tuple of the form ('zerver_article', 'blog').
        (child_table, field) = config.id_source
        child_rows = response[child_table]
        if config.source_filter:
            child_rows = [r for r in child_rows if config.source_filter(r)]
        lookup_ids = [r[field] for r in child_rows]
        filter_params = dict(id__in=lookup_ids)
        if config.filter_args:
            filter_params.update(config.filter_args)
        query = model.objects.filter(**filter_params)
        rows = list(query)

    if rows is not None:
        assert table is not None  # Hint for mypy
        response[table] = make_raw(rows, exclude=config.exclude)
        if config.collect_client_ids and "collected_client_ids_set" in context:
            model = cast(type[Model], model)
            assert issubclass(model, Model)
            client_id_field_name = get_fk_field_name(model, Client)
            assert client_id_field_name is not None
            context["collected_client_ids_set"].update(
                {row[client_id_field_name] for row in response[table]}
            )

    # Post-process rows
    custom_process_results = config.custom_process_results
    for t in exported_tables:
        if custom_process_results is not None:
            # The config might specify a function to do final processing
            # of the exported data for the tables - e.g. to strip out private data.
            response[t] = custom_process_results(response[t], context)
        if t in DATE_FIELDS:
            floatify_datetime_fields(response, t)

    # Now walk our children.  It's extremely important to respect
    # the order of children here.
    for child_config in config.children:
        export_from_config(
            response=response,
            config=child_config,
            context=context,
        )


def get_realm_config() -> Config:
    # This function generates the main Config object that defines how
    # to do a full-realm export of a single realm from a Zulip server.

    realm_config = Config(
        table="zerver_realm",
        is_seeded=True,
    )

    Config(
        table="zerver_realmauthenticationmethod",
        model=RealmAuthenticationMethod,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    Config(
        table="zerver_presencesequence",
        model=PresenceSequence,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    Config(
        custom_tables=["zerver_scheduledmessage"],
        virtual_parent=realm_config,
        custom_fetch=custom_fetch_scheduled_messages,
    )

    Config(
        table="zerver_defaultstream",
        model=DefaultStream,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    Config(
        table="zerver_customprofilefield",
        model=CustomProfileField,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    Config(
        table="zerver_realmauditlog",
        virtual_parent=realm_config,
        custom_fetch=custom_fetch_realm_audit_logs_for_realm,
    )

    Config(
        table="zerver_realmemoji",
        model=RealmEmoji,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    Config(
        table="zerver_realmdomain",
        model=RealmDomain,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    Config(
        table="zerver_realmexport",
        model=RealmExport,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    Config(
        table="zerver_realmfilter",
        model=RealmFilter,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    Config(
        table="zerver_realmplayground",
        model=RealmPlayground,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    Config(
        table="zerver_realmuserdefault",
        model=RealmUserDefault,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    Config(
        table="zerver_onboardingusermessage",
        model=OnboardingUserMessage,
        virtual_parent=realm_config,
        custom_fetch=custom_fetch_onboarding_usermessage,
    )

    user_profile_config = Config(
        custom_tables=[
            "zerver_userprofile",
            "zerver_userprofile_mirrordummy",
        ],
        # When child tables want to fetch the list of ids of objects exported from
        # the parent table, they should get ids from both zerver_userprofile and
        # zerver_userprofile_mirrordummy:
        custom_return_ids=lambda table_data: {
            row["id"] for row in table_data["zerver_userprofile"]
        }.union({row["id"] for row in table_data["zerver_userprofile_mirrordummy"]}),
        # set table for children who treat us as normal parent
        table="zerver_userprofile",
        virtual_parent=realm_config,
        custom_fetch=custom_fetch_user_profile,
    )

    user_groups_config = Config(
        table="zerver_usergroup",
        model=UserGroup,
        normal_parent=realm_config,
        include_rows="realm_id__in",
        exclude=["direct_members", "direct_subgroups"],
    )

    Config(
        table="zerver_namedusergroup",
        model=NamedUserGroup,
        normal_parent=realm_config,
        include_rows="realm_for_sharding_id__in",
        exclude=["realm", "direct_members", "direct_subgroups"],
    )

    Config(
        table="zerver_usergroupmembership",
        model=UserGroupMembership,
        normal_parent=user_groups_config,
        include_rows="user_group_id__in",
    )

    Config(
        table="zerver_groupgroupmembership",
        model=GroupGroupMembership,
        normal_parent=user_groups_config,
        include_rows="supergroup_id__in",
    )

    Config(
        custom_tables=[
            "zerver_userprofile_crossrealm",
        ],
        virtual_parent=user_profile_config,
        custom_fetch=custom_fetch_user_profile_cross_realm,
        # This is just a Config for exporting cross-realm bots;
        # the concept of limit_to_consenting_users is not applicable here.
        limit_to_consenting_users=False,
    )

    Config(
        table="zerver_service",
        model=Service,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        limit_to_consenting_users=True,
    )

    Config(
        table="zerver_botstoragedata",
        model=BotStorageData,
        normal_parent=user_profile_config,
        include_rows="bot_profile_id__in",
        limit_to_consenting_users=True,
    )

    Config(
        table="zerver_botconfigdata",
        model=BotConfigData,
        normal_parent=user_profile_config,
        include_rows="bot_profile_id__in",
        limit_to_consenting_users=True,
    )

    # Some of these tables are intermediate "tables" that we
    # create only for the export.  Think of them as similar to views.

    user_subscription_config = Config(
        table="_user_subscription",
        model=Subscription,
        normal_parent=user_profile_config,
        filter_args={"recipient__type": Recipient.PERSONAL},
        include_rows="user_profile_id__in",
        # This is merely for fetching Subscriptions to users' own PERSONAL Recipient.
        # It is just "glue" data for internal data model consistency purposes
        # with no user-specific information.
        limit_to_consenting_users=False,
    )

    Config(
        table="_user_recipient",
        model=Recipient,
        virtual_parent=user_subscription_config,
        id_source=("_user_subscription", "recipient"),
    )

    stream_config = Config(
        table="zerver_stream",
        model=Stream,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    stream_recipient_config = Config(
        table="_stream_recipient",
        model=Recipient,
        normal_parent=stream_config,
        include_rows="type_id__in",
        filter_args={"type": Recipient.STREAM},
    )

    Config(
        table="_stream_subscription",
        model=Subscription,
        normal_parent=stream_recipient_config,
        include_rows="recipient_id__in",
    )

    Config(
        custom_tables=[
            "_huddle_recipient",
            "_huddle_subscription",
            "zerver_huddle",
        ],
        virtual_parent=user_profile_config,
        custom_fetch=custom_fetch_direct_message_groups,
        # It is the custom_fetch function that must handle consent logic if applicable.
        # limit_to_consenting_users can't be used here.
        limit_to_consenting_users=False,
    )

    # Now build permanent tables from our temp tables.
    Config(
        table="zerver_recipient",
        virtual_parent=realm_config,
        concat_and_destroy=[
            "_user_recipient",
            "_stream_recipient",
            "_huddle_recipient",
        ],
    )

    Config(
        table="zerver_subscription",
        virtual_parent=realm_config,
        concat_and_destroy=[
            "_user_subscription",
            "_stream_subscription",
            "_huddle_subscription",
        ],
        custom_process_results=custom_process_subscription_in_realm_config,
    )

    Config(
        table="zerver_channelfolder",
        model=ChannelFolder,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    add_user_profile_child_configs(user_profile_config)

    return realm_config


def custom_process_subscription_in_realm_config(
    subscriptions: list[Record], context: Context
) -> list[Record]:
    export_type = context["export_type"]
    if export_type == RealmExport.EXPORT_FULL_WITHOUT_CONSENT:
        return subscriptions

    exportable_user_ids_from_context = context["exportable_user_ids"]
    if export_type == RealmExport.EXPORT_FULL_WITH_CONSENT:
        assert exportable_user_ids_from_context is not None
        consented_user_ids = exportable_user_ids_from_context
    else:
        assert export_type == RealmExport.EXPORT_PUBLIC
        assert exportable_user_ids_from_context is None
        consented_user_ids = set()

    def scrub_subscription_if_needed(subscription: Record) -> Record:
        if subscription["user_profile"] in consented_user_ids:
            return subscription
        # We create a replacement Subscription, setting only the essential fields,
        # while allowing all the other ones to fall back to the defaults
        # defined in the model.
        scrubbed_subscription = Subscription(
            id=subscription["id"],
            user_profile_id=subscription["user_profile"],
            recipient_id=subscription["recipient"],
            active=subscription["active"],
            is_user_active=subscription["is_user_active"],
            # Letting the color be the default color for every stream would create a visually
            # jarring experience. Instead, we can pick colors randomly for a normal-feeling
            # experience, without leaking any information about the user's preferences.
            color=random.choice(STREAM_ASSIGNMENT_COLORS),
        )
        subscription_dict = model_to_dict(scrubbed_subscription)
        return subscription_dict

    processed_rows = map(scrub_subscription_if_needed, subscriptions)
    return list(processed_rows)


def add_user_profile_child_configs(user_profile_config: Config) -> None:
    """
    We add tables here that are keyed by user, and for which
    we fetch rows using the same scheme whether we are
    exporting a realm or a single user.

    For any table where there is nuance between how you
    fetch for realms vs. single users, it's best to just
    keep things simple and have each caller maintain its
    own slightly different 4/5 line Config (while still
    possibly calling common code deeper in the stack).

    As of now, we do NOT include bot tables like Service.
    """

    Config(
        table="zerver_alertword",
        model=AlertWord,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        limit_to_consenting_users=True,
    )

    Config(
        table="zerver_customprofilefieldvalue",
        model=CustomProfileFieldValue,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        # Values of a user's custom profile fields are public.
        limit_to_consenting_users=False,
    )

    Config(
        table="zerver_muteduser",
        model=MutedUser,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        limit_to_consenting_users=True,
    )

    Config(
        table="zerver_navigationview",
        model=NavigationView,
        normal_parent=user_profile_config,
        include_rows="user_id__in",
        limit_to_consenting_users=True,
    )

    Config(
        table="zerver_onboardingstep",
        model=OnboardingStep,
        normal_parent=user_profile_config,
        include_rows="user_id__in",
        limit_to_consenting_users=True,
    )

    Config(
        table="zerver_savedsnippet",
        model=SavedSnippet,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        limit_to_consenting_users=True,
    )

    Config(
        table="zerver_useractivity",
        model=UserActivity,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        limit_to_consenting_users=True,
        collect_client_ids=True,
    )

    Config(
        table="zerver_useractivityinterval",
        model=UserActivityInterval,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        # Note that only exporting UserActivityInterval data for consenting
        # users means it will be impossible to re-compute certain analytics
        # CountStat statistics from the raw data. This is an acceptable downside
        # of this class of data export.
        limit_to_consenting_users=True,
    )

    Config(
        table="zerver_userpresence",
        model=UserPresence,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        # Presence data is public.
        limit_to_consenting_users=False,
    )

    Config(
        table="zerver_userstatus",
        model=UserStatus,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        limit_to_consenting_users=True,
        collect_client_ids=True,
    )

    Config(
        table="zerver_usertopic",
        model=UserTopic,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        limit_to_consenting_users=True,
    )

    Config(
        table="zerver_externalauthid",
        model=ExternalAuthID,
        normal_parent=user_profile_config,
        include_rows="user_id__in",
        limit_to_consenting_users=True,
    )


# We exclude these fields for the following reasons:
# * api_key is a secret.
# * password is a secret.
# * uuid is unlikely to be useful if the domain changes.
EXCLUDED_USER_PROFILE_FIELDS = ["api_key", "password", "uuid"]


def get_randomized_exported_user_dummy_email_address(realm: Realm) -> str:
    random_token = secrets.token_hex(16)
    return Address(
        username=f"exported-user-{random_token}", domain=get_fake_email_domain(realm.host)
    ).addr_spec


def custom_fetch_user_profile(response: TableData, context: Context) -> None:
    realm = context["realm"]
    export_type = context["export_type"]
    exportable_user_ids = context["exportable_user_ids"]
    if export_type != RealmExport.EXPORT_FULL_WITH_CONSENT:
        # exportable_user_ids should only be passed for consent exports.
        assert exportable_user_ids is None

    if export_type == RealmExport.EXPORT_PUBLIC:
        # In a public export, none of the users are considered "exportable",
        # as we're not exporting anybody's private data.
        # The only difference between PUBLIC and a theoretical EXPORT_FULL_WITH_CONSENT
        # where 0 users are consenting is that in a PUBLIC export we won't turn users
        # into mirrr dummy users. A public export is meant to provide useful accounts
        # for everybody after importing; just with all private data removed.
        # The only exception to that will be users with email visibility set to "nobody",
        # as they can't be functional accounts without a real delivery email - which can't
        # be exported.
        exportable_user_ids = set()

    query = UserProfile.objects.filter(realm_id=realm.id).exclude(
        # These were, in some early versions of Zulip, inserted into
        # the first realm that was created.  In those cases, rather
        # than include them here, we will include them in the
        # crossrealm user list, below.
        email__in=settings.CROSS_REALM_BOT_EMAILS,
    )
    exclude = EXCLUDED_USER_PROFILE_FIELDS
    rows = make_raw(list(query), exclude=exclude)

    normal_rows: list[Record] = []
    dummy_rows: list[Record] = []

    realm_user_default = RealmUserDefault.objects.get(realm=realm)
    for row in rows:
        if exportable_user_ids is not None:
            if row["id"] in exportable_user_ids:
                pass
            else:
                # In a consent export, non-exportable users should be turned into mirror dummies, with the
                # notable exception of users who were already deactivated. Mirror dummies can sign up with the
                # matching email address to reactivate their account. However, deactivated users are
                # specifically meant to be prevented from re-entering the organization with the deactivated
                # account. In order to maintain that restriction through the export->import cycle, we need to
                # keep deactivated accounts as just deactivated - without flipping is_mirror_dummy=True.
                if export_type == RealmExport.EXPORT_FULL_WITH_CONSENT and row["is_active"]:
                    row["is_mirror_dummy"] = True
                    row["is_active"] = False

                if row["email_address_visibility"] == UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY:
                    # The user chose not to make their email address visible even to the realm administrators.
                    # Generate a dummy email address for them so that this preference can't be bypassed
                    # through the export feature.
                    row["delivery_email"] = get_randomized_exported_user_dummy_email_address(realm)
                    if export_type == RealmExport.EXPORT_PUBLIC:
                        # In a public export, this account obviously becomes unusable due to not having
                        # a functional delivery_email.
                        row["is_mirror_dummy"] = True
                        row["is_active"] = False

                for settings_name in RealmUserDefault.property_types:
                    if settings_name == "email_address_visibility":
                        # We should respect users' preference for whether to show their email
                        # address to others across the export->import cycle.
                        continue

                    value = getattr(realm_user_default, settings_name)
                    row[settings_name] = value

        if row["is_mirror_dummy"]:
            dummy_rows.append(row)
        else:
            normal_rows.append(row)

    response["zerver_userprofile"] = normal_rows
    response["zerver_userprofile_mirrordummy"] = dummy_rows


def custom_fetch_user_profile_cross_realm(response: TableData, context: Context) -> None:
    realm = context["realm"]
    response["zerver_userprofile_crossrealm"] = []

    bot_name_to_default_email = {
        "NOTIFICATION_BOT": "notification-bot@zulip.com",
        "EMAIL_GATEWAY_BOT": "emailgateway@zulip.com",
        "WELCOME_BOT": "welcome-bot@zulip.com",
    }

    if realm.string_id == settings.SYSTEM_BOT_REALM:
        return

    internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
    for bot in settings.INTERNAL_BOTS:
        bot_name = bot["var_name"]
        if bot_name not in bot_name_to_default_email:
            continue

        bot_email = bot["email_template"] % (settings.INTERNAL_BOT_DOMAIN,)
        bot_default_email = bot_name_to_default_email[bot_name]
        bot_user_id = get_system_bot(bot_email, internal_realm.id).id

        recipient_id = Recipient.objects.get(type_id=bot_user_id, type=Recipient.PERSONAL).id
        response["zerver_userprofile_crossrealm"].append(
            dict(
                email=bot_default_email,
                id=bot_user_id,
                recipient_id=recipient_id,
            )
        )


def fetch_attachment_data(
    response: TableData, realm_id: int, message_ids: set[int], scheduled_message_ids: set[int]
) -> list[Attachment]:
    attachments = list(
        Attachment.objects.filter(
            Q(messages__in=message_ids) | Q(scheduled_messages__in=scheduled_message_ids),
            realm_id=realm_id,
        ).distinct()
    )
    response["zerver_attachment"] = make_raw(attachments)
    floatify_datetime_fields(response, "zerver_attachment")

    """
    We usually export most messages for the realm, but not
    quite ALL messages for the realm.  So, we need to
    clean up our attachment data to have correct
    values for response['zerver_attachment'][<n>]['messages'].

    Same reasoning applies to scheduled_messages.
    """
    for row in response["zerver_attachment"]:
        filtered_message_ids = set(row["messages"]).intersection(message_ids)
        row["messages"] = sorted(filtered_message_ids)

        filtered_scheduled_message_ids = set(row["scheduled_messages"]).intersection(
            scheduled_message_ids
        )
        row["scheduled_messages"] = sorted(filtered_scheduled_message_ids)

    return attachments


def custom_fetch_realm_audit_logs_for_user(response: TableData, context: Context) -> None:
    """To be expansive, we include audit log entries for events that
    either modified the target user or where the target user modified
    something (E.g. if they changed the settings for a stream).
    """
    user = context["user"]
    query = RealmAuditLog.objects.filter(Q(modified_user_id=user.id) | Q(acting_user_id=user.id))
    rows = make_raw(list(query))
    response["zerver_realmauditlog"] = rows


def fetch_reaction_data(response: TableData, message_ids: set[int]) -> None:
    query = Reaction.objects.filter(message_id__in=list(message_ids))
    response["zerver_reaction"] = make_raw(list(query))


def fetch_client_data(response: TableData, client_ids: set[int]) -> None:
    query = Client.objects.filter(id__in=list(client_ids))
    response["zerver_client"] = make_raw(list(query))


def custom_fetch_direct_message_groups(response: TableData, context: Context) -> None:
    realm = context["realm"]
    export_type = context["export_type"]
    exportable_user_ids_from_context = context["exportable_user_ids"]

    if export_type == RealmExport.EXPORT_FULL_WITH_CONSENT:
        assert exportable_user_ids_from_context is not None
        consented_user_ids = exportable_user_ids_from_context
    elif export_type == RealmExport.EXPORT_FULL_WITHOUT_CONSENT:
        assert exportable_user_ids_from_context is None
    else:
        assert export_type == RealmExport.EXPORT_PUBLIC
        consented_user_ids = set()

    user_profile_ids = {
        r["id"] for r in response["zerver_userprofile"] + response["zerver_userprofile_mirrordummy"]
    }

    recipient_filter = Q()
    if export_type != RealmExport.EXPORT_FULL_WITHOUT_CONSENT:
        # First we find the set of recipient ids of DirectMessageGroups which can be exported.
        # A DirectMessageGroup can be exported only if at least one of its users is consenting
        # to the export of private data.
        # We can find this set by gathering all the Subscriptions of consenting users to
        # DirectMessageGroups and collecting the set of recipient_ids from those Subscriptions.
        exportable_direct_message_group_recipient_ids = set(
            Subscription.objects.filter(
                recipient__type=Recipient.DIRECT_MESSAGE_GROUP, user_profile__in=consented_user_ids
            )
            .distinct("recipient_id")
            .values_list("recipient_id", flat=True)
        )
        recipient_filter = Q(recipient_id__in=exportable_direct_message_group_recipient_ids)

    # Now we fetch all the Subscription objects to the exportable DireMessageGroups in the realm.
    realm_direct_message_group_subs = (
        Subscription.objects.select_related("recipient")
        .filter(
            recipient__type=Recipient.DIRECT_MESSAGE_GROUP,
            user_profile__in=user_profile_ids,
        )
        .filter(recipient_filter)
    )
    realm_direct_message_group_recipient_ids = {
        sub.recipient_id for sub in realm_direct_message_group_subs
    }

    # Mark all Direct Message groups whose recipient ID contains a cross-realm user.
    unsafe_direct_message_group_recipient_ids = set()
    for sub in Subscription.objects.select_related("user_profile").filter(
        recipient__in=realm_direct_message_group_recipient_ids
    ):
        if sub.user_profile.realm_id != realm.id:
            # In almost every case the other realm will be zulip.com
            unsafe_direct_message_group_recipient_ids.add(sub.recipient_id)

    # Now filter down to just those direct message groups that are
    # entirely within the realm.
    #
    # This is important for ensuring that the User objects needed
    # to import it on the other end exist (since we're only
    # exporting the users from this realm), at the cost of losing
    # some of these cross-realm messages.
    direct_message_group_subs = [
        sub
        for sub in realm_direct_message_group_subs
        if sub.recipient_id not in unsafe_direct_message_group_recipient_ids
    ]
    direct_message_group_recipient_ids = {sub.recipient_id for sub in direct_message_group_subs}
    direct_message_group_ids = {sub.recipient.type_id for sub in direct_message_group_subs}

    direct_message_group_subscription_dicts = make_raw(direct_message_group_subs)
    direct_message_group_recipients = make_raw(
        Recipient.objects.filter(id__in=direct_message_group_recipient_ids)
    )

    response["_huddle_recipient"] = direct_message_group_recipients
    response["_huddle_subscription"] = direct_message_group_subscription_dicts
    response["zerver_huddle"] = make_raw(
        DirectMessageGroup.objects.filter(id__in=direct_message_group_ids)
    )
    if export_type == RealmExport.EXPORT_PUBLIC and any(
        response[t] for t in ["_huddle_recipient", "_huddle_subscription", "zerver_huddle"]
    ):
        raise AssertionError(
            "Public export should not result in exporting any data in _huddle tables"
        )


def custom_fetch_scheduled_messages(response: TableData, context: Context) -> None:
    """
    Simple custom fetch function to fetch only the ScheduledMessage objects that we're allowed to.
    """
    realm = context["realm"]
    exportable_scheduled_message_ids = context["exportable_scheduled_message_ids"]

    query = ScheduledMessage.objects.filter(realm=realm, id__in=exportable_scheduled_message_ids)
    rows = make_raw(list(query))

    response["zerver_scheduledmessage"] = rows


PRESERVED_AUDIT_LOG_EVENT_TYPES = [
    AuditLogEventType.SUBSCRIPTION_CREATED,
    AuditLogEventType.SUBSCRIPTION_ACTIVATED,
    AuditLogEventType.SUBSCRIPTION_DEACTIVATED,
]


def custom_fetch_realm_audit_logs_for_realm(response: TableData, context: Context) -> None:
    """
    Simple custom fetch function to fix up .acting_user for some RealmAuditLog objects
    and limit what objects are fetched when doing export with consent.

    Certain RealmAuditLog objects have an acting_user that is in a different .realm, due to
    the possibility of server administrators (typically with the .is_staff permission) taking
    certain actions to modify UserProfiles or Realms, which will set the .acting_user to
    the administrator's UserProfile, which can be in a different realm. Such an acting_user
    cannot be imported during organization import on another server, so we need to just set it
    to None.
    """
    realm = context["realm"]
    export_type = context["export_type"]
    exportable_user_ids_from_context = context["exportable_user_ids"]
    if export_type == RealmExport.EXPORT_FULL_WITHOUT_CONSENT:
        assert exportable_user_ids_from_context is None
    elif export_type == RealmExport.EXPORT_FULL_WITH_CONSENT:
        assert exportable_user_ids_from_context is not None
        consenting_user_ids = exportable_user_ids_from_context
    else:
        assert export_type == RealmExport.EXPORT_PUBLIC
        assert exportable_user_ids_from_context is None
        consenting_user_ids = set()

    query = RealmAuditLog.objects.filter(realm=realm).select_related("acting_user")
    realmauditlog_objects = list(query)
    for realmauditlog in realmauditlog_objects:
        if realmauditlog.acting_user is not None and realmauditlog.acting_user.realm_id != realm.id:
            realmauditlog.acting_user = None

    # We want to drop all RealmAuditLog objects where modified_user is not a consenting
    # user, except those of event_type in PRESERVED_AUDIT_LOG_EVENT_TYPES.
    realmauditlog_objects_for_export = []
    for realmauditlog in realmauditlog_objects:
        if (
            export_type == RealmExport.EXPORT_FULL_WITHOUT_CONSENT
            or (realmauditlog.event_type in PRESERVED_AUDIT_LOG_EVENT_TYPES)
            or (realmauditlog.modified_user_id is None)
            or (realmauditlog.modified_user_id in consenting_user_ids)
        ):
            realmauditlog_objects_for_export.append(realmauditlog)
            continue

    rows = make_raw(realmauditlog_objects_for_export)

    response["zerver_realmauditlog"] = rows


def custom_fetch_onboarding_usermessage(response: TableData, context: Context) -> None:
    realm = context["realm"]
    response["zerver_onboardingusermessage"] = []

    onboarding_usermessage_query = OnboardingUserMessage.objects.filter(realm=realm)
    for onboarding_usermessage in onboarding_usermessage_query:
        onboarding_usermessage_obj = model_to_dict(onboarding_usermessage)
        onboarding_usermessage_obj["flags_mask"] = onboarding_usermessage.flags.mask
        del onboarding_usermessage_obj["flags"]
        response["zerver_onboardingusermessage"].append(onboarding_usermessage_obj)


def fetch_usermessages(
    realm: Realm,
    message_ids: set[int],
    user_profile_ids: set[int],
    message_filename: Path,
    export_full_with_consent: bool,
    consented_user_ids: set[int] | None = None,
) -> list[Record]:
    # UserMessage export security rule: You can export UserMessages
    # for the messages you exported for the users in your realm.
    user_message_query = UserMessage.objects.filter(
        user_profile__realm=realm, message_id__in=message_ids
    )
    if export_full_with_consent:
        assert consented_user_ids is not None
        user_profile_ids = consented_user_ids & user_profile_ids
    user_message_chunk = []
    for user_message in user_message_query:
        if user_message.user_profile_id not in user_profile_ids:
            continue
        user_message_obj = model_to_dict(user_message)
        user_message_obj["flags_mask"] = user_message.flags.mask
        del user_message_obj["flags"]
        user_message_chunk.append(user_message_obj)
    logging.info("Fetched UserMessages for %s", message_filename)
    return user_message_chunk


def export_usermessages_batch(
    input_path: Path,
    output_path: Path,
    export_full_with_consent: bool,
    consented_user_ids: set[int] | None = None,
) -> None:
    """As part of the system for doing parallel exports, this runs on one
    batch of Message objects and adds the corresponding UserMessage
    objects. (This is called by the export_usermessage_batch
    management command).

    See write_message_partial_for_query for more context."""
    assert input_path.endswith((".partial", ".locked"))
    assert output_path.endswith(".json")

    with open(input_path, "rb") as input_file:
        input_data: MessagePartial = orjson.loads(input_file.read())

    message_ids = {item["id"] for item in input_data["zerver_message"]}
    user_profile_ids = set(input_data["zerver_userprofile_ids"])
    realm = Realm.objects.get(id=input_data["realm_id"])
    zerver_usermessage_data = fetch_usermessages(
        realm,
        message_ids,
        user_profile_ids,
        output_path,
        export_full_with_consent,
        consented_user_ids=consented_user_ids,
    )

    output_data: TableData = dict(
        zerver_message=input_data["zerver_message"],
        zerver_usermessage=zerver_usermessage_data,
    )
    write_table_data(output_path, output_data)
    os.unlink(input_path)


def export_partial_message_files(
    realm: Realm,
    response: TableData,
    export_type: int,
    collected_client_ids: set[int],
    exportable_user_ids: set[int] | None,
    chunk_size: int = MESSAGE_BATCH_CHUNK_SIZE,
    output_dir: Path | None = None,
) -> set[int]:
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="zulip-export")

    def get_ids(records: Iterable[Mapping[str, Any]]) -> set[int]:
        return {x["id"] for x in records}

    # Basic security rule: You can export everything either...
    #   - sent by someone in your exportable_user_ids
    #        OR
    #   - received by someone in your exportable_user_ids (which
    #     equates to a recipient object we are exporting)
    #
    # TODO: In theory, you should be able to export messages in
    # cross-realm direct message threads; currently, this only
    # exports cross-realm messages received by your realm that
    # were sent by Zulip system bots (e.g. emailgateway,
    # notification-bot).

    # Here, "we" and "us" refers to the inner circle of users who
    # were specified as being allowed to be exported.  "Them"
    # refers to other users.
    user_ids_for_us = get_ids(
        response["zerver_userprofile"],
    )
    ids_of_our_possible_senders = get_ids(
        response["zerver_userprofile"]
        + response["zerver_userprofile_mirrordummy"]
        + response["zerver_userprofile_crossrealm"]
    )

    consented_user_ids: set[int] = set()
    if export_type == RealmExport.EXPORT_FULL_WITH_CONSENT:
        assert exportable_user_ids is not None
        consented_user_ids = exportable_user_ids

    if export_type == RealmExport.EXPORT_PUBLIC:
        recipient_streams = Stream.objects.filter(realm=realm, invite_only=False)
        recipient_ids = Recipient.objects.filter(
            type=Recipient.STREAM, type_id__in=recipient_streams
        ).values_list("id", flat=True)
        recipient_ids_for_us = get_ids(response["zerver_recipient"]) & set(recipient_ids)
    elif export_type == RealmExport.EXPORT_FULL_WITH_CONSENT:
        public_streams = Stream.objects.filter(realm=realm, invite_only=False)
        public_stream_recipient_ids = Recipient.objects.filter(
            type=Recipient.STREAM, type_id__in=public_streams
        ).values_list("id", flat=True)

        streams_with_protected_history_recipient_ids = Stream.objects.filter(
            realm=realm, history_public_to_subscribers=False
        ).values_list("recipient_id", flat=True)

        consented_recipient_ids = Subscription.objects.filter(
            user_profile_id__in=consented_user_ids
        ).values_list("recipient_id", flat=True)

        recipient_ids_set = set(public_stream_recipient_ids) | set(consented_recipient_ids) - set(
            streams_with_protected_history_recipient_ids
        )
        recipient_ids_for_us = get_ids(response["zerver_recipient"]) & recipient_ids_set
    else:
        recipient_ids_for_us = get_ids(response["zerver_recipient"])
        # For a full export, we have implicit consent for all users in the export.
        consented_user_ids = user_ids_for_us

    if export_type == RealmExport.EXPORT_PUBLIC:
        messages_we_received = Message.objects.filter(
            # Uses index: zerver_message_realm_sender_recipient
            realm_id=realm.id,
            sender__in=ids_of_our_possible_senders,
            recipient__in=recipient_ids_for_us,
        )

        # For the public stream export, we only need the messages those streams received.
        message_queries = [
            messages_we_received,
        ]
    else:
        message_queries = []

        # We capture most messages here: Messages that were sent by
        # anyone in the export and received by any of the users who we
        # have consent to export.
        messages_we_received = Message.objects.filter(
            # Uses index: zerver_message_realm_sender_recipient
            realm_id=realm.id,
            sender__in=ids_of_our_possible_senders,
            recipient__in=recipient_ids_for_us,
        )
        message_queries.append(messages_we_received)

        if export_type == RealmExport.EXPORT_FULL_WITH_CONSENT:
            # Export with member consent requires some careful handling to make sure
            # we only include messages that a consenting user can access.
            has_usermessage_expression = Exists(
                UserMessage.objects.filter(
                    user_profile_id__in=consented_user_ids, message_id=OuterRef("id")
                )
            )
            messages_we_received_in_protected_history_streams = Message.objects.alias(
                has_usermessage=has_usermessage_expression
            ).filter(
                # Uses index: zerver_message_realm_sender_recipient
                realm_id=realm.id,
                sender__in=ids_of_our_possible_senders,
                recipient_id__in=(
                    set(consented_recipient_ids) & set(streams_with_protected_history_recipient_ids)
                ),
                has_usermessage=True,
            )

            message_queries.append(messages_we_received_in_protected_history_streams)

        # The above query is missing some messages that consenting
        # users have access to, namely, direct messages sent by one
        # of the users in our export to another user (since the only
        # subscriber to a Recipient object for Recipient.PERSONAL is
        # the recipient, not the sender). The `consented_user_ids`
        # list has precisely those users whose Recipient.PERSONAL
        # recipient ID was already present in recipient_ids_for_us
        # above.
        ids_of_non_exported_possible_recipients = ids_of_our_possible_senders - consented_user_ids

        recipients_for_them = Recipient.objects.filter(
            type=Recipient.PERSONAL, type_id__in=ids_of_non_exported_possible_recipients
        ).values("id")
        recipient_ids_for_them = get_ids(recipients_for_them)

        messages_we_sent_to_them = Message.objects.filter(
            # Uses index: zerver_message_realm_sender_recipient
            realm_id=realm.id,
            sender__in=consented_user_ids,
            recipient__in=recipient_ids_for_them,
        )

        message_queries.append(messages_we_sent_to_them)

    all_message_ids: set[int] = set()

    for message_query in message_queries:
        message_ids = set(get_id_list_gently_from_database(base_query=message_query, id_field="id"))

        # We expect our queries to be disjoint, although this assertion
        # isn't strictly necessary if you don't mind a little bit of
        # overhead.
        assert len(message_ids.intersection(all_message_ids)) == 0

        all_message_ids |= message_ids

    message_id_chunks = chunkify(sorted(all_message_ids), chunk_size=MESSAGE_BATCH_CHUNK_SIZE)

    write_message_partials(
        realm=realm,
        message_id_chunks=message_id_chunks,
        output_dir=output_dir,
        user_profile_ids=user_ids_for_us,
        collected_client_ids=collected_client_ids,
    )

    return all_message_ids


def write_message_partials(
    *,
    realm: Realm,
    message_id_chunks: list[list[int]],
    output_dir: Path,
    user_profile_ids: set[int],
    collected_client_ids: set[int],
) -> None:
    dump_file_id = 1

    for message_id_chunk in message_id_chunks:
        # Uses index: zerver_message_pkey
        actual_query = Message.objects.filter(id__in=message_id_chunk).order_by("id")
        message_chunk = make_raw(actual_query)

        for row in message_chunk:
            collected_client_ids.add(row["sending_client"])

        # Figure out the name of our shard file.
        message_filename = os.path.join(output_dir, f"messages-{dump_file_id:06}.json")
        message_filename += ".partial"
        logging.info("Fetched messages for %s", message_filename)

        # Clean up our messages.
        table_data: TableData = {}
        table_data["zerver_message"] = message_chunk
        floatify_datetime_fields(table_data, "zerver_message")

        # Build up our output for the .partial file, which needs
        # a list of user_profile_ids to search for (as well as
        # the realm id).
        output: MessagePartial = dict(
            zerver_message=table_data["zerver_message"],
            zerver_userprofile_ids=list(user_profile_ids),
            realm_id=realm.id,
        )

        # And write the data.
        write_data_to_file(message_filename, output)
        dump_file_id += 1


def export_uploads_and_avatars(
    realm: Realm,
    *,
    attachments: list[Attachment] | None = None,
    user: UserProfile | None,
    output_dir: Path,
) -> None:
    uploads_output_dir = os.path.join(output_dir, "uploads")
    avatars_output_dir = os.path.join(output_dir, "avatars")
    realm_icons_output_dir = os.path.join(output_dir, "realm_icons")
    emoji_output_dir = os.path.join(output_dir, "emoji")

    for dir_path in (
        uploads_output_dir,
        avatars_output_dir,
        emoji_output_dir,
    ):
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    # Avoid creating realm_icons_output_dir for single user exports
    if user is None and not os.path.exists(realm_icons_output_dir):
        os.makedirs(realm_icons_output_dir)

    if user is None:
        handle_system_bots = True
        users = list(UserProfile.objects.filter(realm=realm))
        assert attachments is not None
        realm_emojis = list(RealmEmoji.objects.filter(realm_id=realm.id))
    else:
        handle_system_bots = False
        users = [user]
        attachments = list(Attachment.objects.filter(owner_id=user.id))
        realm_emojis = list(RealmEmoji.objects.filter(author_id=user.id))

    if settings.LOCAL_UPLOADS_DIR:
        assert settings.LOCAL_FILES_DIR
        assert settings.LOCAL_AVATARS_DIR
        # Small installations and developers will usually just store files locally.
        export_uploads_from_local(
            realm,
            local_dir=settings.LOCAL_FILES_DIR,
            output_dir=uploads_output_dir,
            attachments=attachments,
        )
        export_avatars_from_local(
            realm,
            local_dir=settings.LOCAL_AVATARS_DIR,
            output_dir=avatars_output_dir,
            users=users,
            handle_system_bots=handle_system_bots,
        )
        export_emoji_from_local(
            realm,
            local_dir=settings.LOCAL_AVATARS_DIR,
            output_dir=emoji_output_dir,
            realm_emojis=realm_emojis,
        )

        if user is None:
            export_realm_icons(
                realm,
                local_dir=settings.LOCAL_AVATARS_DIR,
                output_dir=realm_icons_output_dir,
            )
    else:
        user_ids = {user.id for user in users}

        # Some bigger installations will have their data stored on S3.

        path_ids = {attachment.path_id for attachment in attachments}

        export_files_from_s3(
            realm,
            handle_system_bots=handle_system_bots,
            flavor="upload",
            bucket_name=settings.S3_AUTH_UPLOADS_BUCKET,
            object_prefix=f"{realm.id}/",
            output_dir=uploads_output_dir,
            user_ids=user_ids,
            valid_hashes=path_ids,
        )

        avatar_hash_values = set()
        for avatar_user in users:
            avatar_path = user_avatar_base_path_from_ids(
                avatar_user.id, avatar_user.avatar_version, realm.id
            )
            avatar_hash_values.add(avatar_path)
            avatar_hash_values.add(avatar_path + ".original")

        export_files_from_s3(
            realm,
            handle_system_bots=handle_system_bots,
            flavor="avatar",
            bucket_name=settings.S3_AVATAR_BUCKET,
            object_prefix=f"{realm.id}/",
            output_dir=avatars_output_dir,
            user_ids=user_ids,
            valid_hashes=avatar_hash_values,
        )

        emoji_paths = set()
        for realm_emoji in realm_emojis:
            emoji_path = get_emoji_path(realm_emoji)
            emoji_paths.add(emoji_path)
            emoji_paths.add(emoji_path + ".original")

        export_files_from_s3(
            realm,
            handle_system_bots=handle_system_bots,
            flavor="emoji",
            bucket_name=settings.S3_AVATAR_BUCKET,
            object_prefix=f"{realm.id}/emoji/images/",
            output_dir=emoji_output_dir,
            user_ids=user_ids,
            valid_hashes=emoji_paths,
        )

        if user is None:
            export_files_from_s3(
                realm,
                handle_system_bots=handle_system_bots,
                flavor="realm_icon_or_logo",
                bucket_name=settings.S3_AVATAR_BUCKET,
                object_prefix=f"{realm.id}/realm/",
                output_dir=realm_icons_output_dir,
                user_ids=user_ids,
                valid_hashes=None,
            )


def _get_exported_s3_record(
    bucket_name: str, key: "Object", processing_emoji: bool
) -> dict[str, Any]:
    # Helper function for export_files_from_s3
    record: dict[str, Any] = dict(
        s3_path=key.key,
        bucket=bucket_name,
        size=key.content_length,
        last_modified=key.last_modified,
        content_type=key.content_type,
        md5=key.e_tag,
    )
    record.update(key.metadata)

    if processing_emoji:
        file_name = os.path.basename(key.key)
        # Both the main emoji file and the .original version should have the same
        # file_name value in the record, as they reference the same emoji.
        file_name = file_name.removesuffix(".original")
        record["file_name"] = file_name

    if "user_profile_id" in record:
        user_profile = get_user_profile_by_id(int(record["user_profile_id"]))
        record["user_profile_email"] = user_profile.email

        # Fix the record ids
        record["user_profile_id"] = int(record["user_profile_id"])

        # A few early avatars don't have 'realm_id' on the object; fix their metadata
        if "realm_id" not in record:
            record["realm_id"] = user_profile.realm_id
    else:
        # There are some rare cases in which 'user_profile_id' may not be present
        # in S3 metadata. Eg: Exporting an organization which was created
        # initially from a local export won't have the "user_profile_id" metadata
        # set for realm_icons and realm_logos.
        pass

    if "realm_id" in record:
        record["realm_id"] = int(record["realm_id"])
    else:
        raise Exception("Missing realm_id")

    if "avatar_version" in record:
        record["avatar_version"] = int(record["avatar_version"])

    return record


def _save_s3_object_to_file(
    key: "Object",
    output_dir: str,
    processing_uploads: bool,
) -> None:
    # Helper function for export_files_from_s3
    if not processing_uploads:
        filename = os.path.join(output_dir, key.key)
    else:
        fields = key.key.split("/")
        if len(fields) != 3:
            raise AssertionError(f"Suspicious key with invalid format {key.key}")
        filename = os.path.join(output_dir, key.key)

    if "../" in filename:
        raise AssertionError(f"Suspicious file with invalid format {filename}")

    # Use 'mark_sanitized' to cause Pysa to ignore the flow of user controlled
    # data into the filesystem sink, because we've already prevented directory
    # traversal with our assertion above.
    dirname = mark_sanitized(os.path.dirname(filename))

    if not os.path.exists(dirname):
        os.makedirs(dirname)
    key.download_file(Filename=filename)


def export_files_from_s3(
    realm: Realm,
    handle_system_bots: bool,
    flavor: str,
    bucket_name: str,
    object_prefix: str,
    output_dir: Path,
    user_ids: set[int],
    valid_hashes: set[str] | None,
) -> None:
    processing_uploads = flavor == "upload"
    processing_emoji = flavor == "emoji"

    bucket = get_bucket(bucket_name)
    records = []

    logging.info("Downloading %s files from %s", flavor, bucket_name)

    email_gateway_bot: UserProfile | None = None

    if handle_system_bots and settings.EMAIL_GATEWAY_BOT is not None:
        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        email_gateway_bot = get_system_bot(settings.EMAIL_GATEWAY_BOT, internal_realm.id)
        user_ids.add(email_gateway_bot.id)

    count = 0
    for bkey in bucket.objects.filter(Prefix=object_prefix):
        if valid_hashes is not None and bkey.Object().key not in valid_hashes:
            continue

        key = bucket.Object(bkey.key)

        """
        For very old realms we may not have proper metadata. If you really need
        an export to bypass these checks, flip the following flag.
        """
        checking_metadata = True
        if checking_metadata:
            if "realm_id" not in key.metadata:
                raise AssertionError(f"Missing realm_id in key metadata: {key.metadata}")

            if "user_profile_id" not in key.metadata:
                raise AssertionError(f"Missing user_profile_id in key metadata: {key.metadata}")

            if int(key.metadata["user_profile_id"]) not in user_ids:
                continue

            # This can happen if an email address has moved realms
            if key.metadata["realm_id"] != str(realm.id):
                if email_gateway_bot is None or key.metadata["user_profile_id"] != str(
                    email_gateway_bot.id
                ):
                    raise AssertionError(
                        f"Key metadata problem: {key.key} / {key.metadata} / {realm.id}"
                    )
                # Email gateway bot sends messages, potentially including attachments, cross-realm.
                print(f"File uploaded by email gateway bot: {key.key} / {key.metadata}")

        record = _get_exported_s3_record(bucket_name, key, processing_emoji)

        record["path"] = key.key
        _save_s3_object_to_file(key, output_dir, processing_uploads)

        records.append(record)
        count += 1

        if count % 100 == 0:
            logging.info("Finished %s", count)

    write_records_json_file(output_dir, records)


def export_uploads_from_local(
    realm: Realm, local_dir: Path, output_dir: Path, attachments: list[Attachment]
) -> None:
    records = []
    for count, attachment in enumerate(attachments, 1):
        # Use 'mark_sanitized' to work around false positive caused by Pysa
        # thinking that 'realm' (and thus 'attachment' and 'attachment.path_id')
        # are user controlled
        path_id = mark_sanitized(attachment.path_id)

        local_path = os.path.join(local_dir, path_id)
        output_path = os.path.join(output_dir, path_id)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy2(local_path, output_path)
        stat = os.stat(local_path)
        record = dict(
            realm_id=attachment.realm_id,
            user_profile_id=attachment.owner.id,
            user_profile_email=attachment.owner.email,
            s3_path=path_id,
            path=path_id,
            size=stat.st_size,
            last_modified=stat.st_mtime,
            content_type=None,
        )
        records.append(record)

        if count % 100 == 0:
            logging.info("Finished %s", count)

    write_records_json_file(output_dir, records)


def export_avatars_from_local(
    realm: Realm,
    local_dir: Path,
    output_dir: Path,
    users: list[UserProfile],
    handle_system_bots: bool,
) -> None:
    count = 0
    records = []

    if handle_system_bots:
        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        users += [
            get_system_bot(settings.NOTIFICATION_BOT, internal_realm.id),
            get_system_bot(settings.EMAIL_GATEWAY_BOT, internal_realm.id),
            get_system_bot(settings.WELCOME_BOT, internal_realm.id),
        ]

    for user in users:
        if user.avatar_source == UserProfile.AVATAR_FROM_GRAVATAR:
            continue

        avatar_path = user_avatar_base_path_from_ids(user.id, user.avatar_version, realm.id)
        wildcard = os.path.join(local_dir, avatar_path + ".*")

        for local_path in glob.glob(wildcard):
            logging.info(
                "Copying avatar file for user %s from %s",
                user.email,
                local_path,
            )
            fn = os.path.relpath(local_path, local_dir)
            output_path = os.path.join(output_dir, fn)
            os.makedirs(str(os.path.dirname(output_path)), exist_ok=True)
            shutil.copy2(str(local_path), str(output_path))
            stat = os.stat(local_path)
            record = dict(
                realm_id=realm.id,
                user_profile_id=user.id,
                user_profile_email=user.email,
                avatar_version=user.avatar_version,
                s3_path=fn,
                path=fn,
                size=stat.st_size,
                last_modified=stat.st_mtime,
                content_type=None,
            )
            records.append(record)

            count += 1

            if count % 100 == 0:
                logging.info("Finished %s", count)

    write_records_json_file(output_dir, records)


def export_realm_icons(realm: Realm, local_dir: Path, output_dir: Path) -> None:
    records = []
    dir_relative_path = zerver.lib.upload.upload_backend.realm_avatar_and_logo_path(realm)
    icons_wildcard = os.path.join(local_dir, dir_relative_path, "*")
    for icon_absolute_path in glob.glob(icons_wildcard):
        icon_file_name = os.path.basename(icon_absolute_path)
        icon_relative_path = os.path.join(str(realm.id), icon_file_name)
        output_path = os.path.join(output_dir, icon_relative_path)
        os.makedirs(str(os.path.dirname(output_path)), exist_ok=True)
        shutil.copy2(str(icon_absolute_path), str(output_path))
        record = dict(realm_id=realm.id, path=icon_relative_path, s3_path=icon_relative_path)
        records.append(record)

    write_records_json_file(output_dir, records)


def get_emoji_path(realm_emoji: RealmEmoji) -> str:
    return RealmEmoji.PATH_ID_TEMPLATE.format(
        realm_id=realm_emoji.realm_id,
        emoji_file_name=realm_emoji.file_name,
    )


def export_emoji_from_local(
    realm: Realm, local_dir: Path, output_dir: Path, realm_emojis: list[RealmEmoji]
) -> None:
    records = []

    realm_emoji_helper_tuples: list[tuple[RealmEmoji, str]] = []
    for realm_emoji in realm_emojis:
        realm_emoji_path = get_emoji_path(realm_emoji)

        # Use 'mark_sanitized' to work around false positive caused by Pysa
        # thinking that 'realm' (and thus 'attachment' and 'attachment.path_id')
        # are user controlled
        realm_emoji_path = mark_sanitized(realm_emoji_path)

        realm_emoji_path_original = realm_emoji_path + ".original"

        realm_emoji_helper_tuples.append((realm_emoji, realm_emoji_path))
        realm_emoji_helper_tuples.append((realm_emoji, realm_emoji_path_original))

    for count, realm_emoji_helper_tuple in enumerate(realm_emoji_helper_tuples, 1):
        realm_emoji_object, emoji_path = realm_emoji_helper_tuple

        local_path = os.path.join(local_dir, emoji_path)
        output_path = os.path.join(output_dir, emoji_path)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy2(local_path, output_path)
        # Realm emoji author is optional.
        author = realm_emoji_object.author
        author_id = None
        if author:
            author_id = author.id
        record = dict(
            realm_id=realm.id,
            author=author_id,
            path=emoji_path,
            s3_path=emoji_path,
            file_name=realm_emoji_object.file_name,
            name=realm_emoji_object.name,
            deactivated=realm_emoji_object.deactivated,
        )
        records.append(record)

        if count % 100 == 0:
            logging.info("Finished %s", count)

    write_records_json_file(output_dir, records)


def do_write_stats_file_for_realm_export(output_dir: Path) -> dict[str, int | dict[str, int]]:
    stats_file = os.path.join(output_dir, "stats.json")
    realm_file = os.path.join(output_dir, "realm.json")
    attachment_file = os.path.join(output_dir, "attachment.json")
    analytics_file = os.path.join(output_dir, "analytics.json")
    message_files = glob.glob(os.path.join(output_dir, "messages-*.json"))
    filenames = sorted([analytics_file, attachment_file, *message_files, realm_file])

    logging.info("Writing stats file: %s\n", stats_file)

    stats: dict[str, int | dict[str, int]] = {}
    for filename in filenames:
        name = os.path.splitext(os.path.basename(filename))[0]
        with open(filename, "rb") as json_file:
            data = orjson.loads(json_file.read())
        stats[name] = {k: len(data[k]) for k in sorted(data)}

    for category in ["avatars", "uploads", "emoji", "realm_icons"]:
        filename = os.path.join(output_dir, category, "records.json")
        with open(filename, "rb") as json_file:
            data = orjson.loads(json_file.read())
        stats[f"{category}_records"] = len(data)

    with open(stats_file, "wb") as f:
        f.write(orjson.dumps(stats, option=orjson.OPT_INDENT_2))

    return stats


def get_exportable_scheduled_message_ids(
    realm: Realm, export_type: int, exportable_user_ids: set[int] | None
) -> set[int]:
    """
    Scheduled messages are private to the sender, so which ones we export depends on the
    public/consent/full export mode.
    """

    if export_type == RealmExport.EXPORT_PUBLIC:
        return set()

    if export_type == RealmExport.EXPORT_FULL_WITH_CONSENT:
        assert exportable_user_ids is not None
        sender_ids = exportable_user_ids
        return set(
            ScheduledMessage.objects.filter(sender_id__in=sender_ids, realm=realm).values_list(
                "id", flat=True
            )
        )

    return set(ScheduledMessage.objects.filter(realm=realm).values_list("id", flat=True))


def do_export_realm(
    realm: Realm,
    output_dir: Path,
    threads: int,
    export_type: int,
    exportable_user_ids: set[int] | None = None,
    export_as_active: bool | None = None,
) -> tuple[str, dict[str, int | dict[str, int]]]:
    response: TableData = {}
    if exportable_user_ids is not None:
        # We only use this arg for consent exports. Any other usage
        # indicates a bug.
        assert export_type == RealmExport.EXPORT_FULL_WITH_CONSENT

    # We need at least one thread running to export
    # UserMessage rows.  The management command should
    # enforce this for us.
    if not settings.TEST_SUITE:
        assert threads >= 1

    realm_config = get_realm_config()

    create_soft_link(source=output_dir, in_progress=True)

    exportable_scheduled_message_ids = get_exportable_scheduled_message_ids(
        realm, export_type, exportable_user_ids
    )
    collected_client_ids = set(
        ScheduledMessage.objects.filter(id__in=exportable_scheduled_message_ids)
        .order_by("sending_client_id")
        .distinct("sending_client_id")
        .values_list("sending_client_id", flat=True)
    )

    logging.info("Exporting data from get_realm_config()...")
    export_from_config(
        response=response,
        config=realm_config,
        seed_object=realm,
        context=dict(
            realm=realm,
            export_type=export_type,
            exportable_user_ids=exportable_user_ids,
            exportable_scheduled_message_ids=exportable_scheduled_message_ids,
            collected_client_ids_set=collected_client_ids,
        ),
    )
    logging.info("...DONE with get_realm_config() data")

    sanity_check_output(response)

    # We (sort of) export zerver_message rows here.  We write
    # them to .partial files that are subsequently fleshed out
    # by parallel processes to add in zerver_usermessage data.
    # This is for performance reasons, of course.  Some installations
    # have millions of messages.
    logging.info("Exporting .partial files messages")
    message_ids = export_partial_message_files(
        realm,
        response,
        export_type=export_type,
        exportable_user_ids=exportable_user_ids,
        output_dir=output_dir,
        collected_client_ids=collected_client_ids,
    )
    logging.info("%d messages were exported", len(message_ids))

    # zerver_reaction
    zerver_reaction: TableData = {}
    fetch_reaction_data(response=zerver_reaction, message_ids=message_ids)
    response.update(zerver_reaction)

    zerver_client: TableData = {}
    fetch_client_data(response=zerver_client, client_ids=collected_client_ids)
    response.update(zerver_client)

    # Override the "deactivated" flag on the realm
    if export_as_active is not None:
        response["zerver_realm"][0]["deactivated"] = not export_as_active

    response["import_source"] = "zulip"  # type: ignore[assignment]  # this is an extra info field, not TableData

    # Write realm data
    export_file = os.path.join(output_dir, "realm.json")
    write_table_data(output_file=export_file, data=response)

    # Write analytics data
    export_analytics_tables(realm=realm, output_dir=output_dir)

    # zerver_attachment
    attachments = export_attachment_table(
        realm=realm,
        output_dir=output_dir,
        message_ids=message_ids,
        scheduled_message_ids=exportable_scheduled_message_ids,
    )

    logging.info("Exporting uploaded files and avatars")
    export_uploads_and_avatars(realm, attachments=attachments, user=None, output_dir=output_dir)

    # Start parallel jobs to export the UserMessage objects.
    launch_user_message_subprocesses(
        threads=threads,
        output_dir=output_dir,
        export_full_with_consent=export_type == RealmExport.EXPORT_FULL_WITH_CONSENT,
        exportable_user_ids=exportable_user_ids,
    )

    do_common_export_processes(output_dir)

    logging.info("Finished exporting %s", realm.string_id)
    create_soft_link(source=output_dir, in_progress=False)

    stats = do_write_stats_file_for_realm_export(output_dir)

    logging.info("Compressing tarball...")
    tarball_path = output_dir.rstrip("/") + ".tar.gz"
    subprocess.check_call(
        [
            "tar",
            f"-czf{tarball_path}",
            f"-C{os.path.dirname(output_dir)}",
            os.path.basename(output_dir),
        ]
    )
    return tarball_path, stats


def export_attachment_table(
    realm: Realm, output_dir: Path, message_ids: set[int], scheduled_message_ids: set[int]
) -> list[Attachment]:
    response: TableData = {}
    attachments = fetch_attachment_data(
        response=response,
        realm_id=realm.id,
        message_ids=message_ids,
        scheduled_message_ids=scheduled_message_ids,
    )
    output_file = os.path.join(output_dir, "attachment.json")
    write_table_data(output_file=output_file, data=response)
    return attachments


def create_soft_link(source: Path, in_progress: bool = True) -> None:
    is_done = not in_progress
    if settings.DEVELOPMENT:
        in_progress_link = os.path.join(settings.DEPLOY_ROOT, "var", "export-in-progress")
        done_link = os.path.join(settings.DEPLOY_ROOT, "var", "export-most-recent")
    else:
        in_progress_link = "/home/zulip/export-in-progress"
        done_link = "/home/zulip/export-most-recent"

    if in_progress:
        new_target = in_progress_link
    else:
        with suppress(FileNotFoundError):
            os.remove(in_progress_link)
        new_target = done_link

    overwrite_symlink(source, new_target)
    if is_done:
        logging.info("See %s for output files", new_target)


def launch_user_message_subprocesses(
    threads: int,
    output_dir: Path,
    export_full_with_consent: bool,
    exportable_user_ids: set[int] | None,
) -> None:
    logging.info("Launching %d PARALLEL subprocesses to export UserMessage rows", threads)
    pids = {}

    if export_full_with_consent:
        assert exportable_user_ids is not None
        consented_user_ids_filepath = os.path.join(output_dir, "consented_user_ids.json")
        with open(consented_user_ids_filepath, "wb") as f:
            f.write(orjson.dumps(list(exportable_user_ids)))
        logging.info("Created consented_user_ids.json file.")

    for shard_id in range(threads):
        arguments = [
            os.path.join(settings.DEPLOY_ROOT, "manage.py"),
            "export_usermessage_batch",
            f"--path={output_dir}",
            f"--thread={shard_id}",
        ]
        if export_full_with_consent:
            arguments.append("--export-full-with-consent")

        process = subprocess.Popen(arguments)
        pids[process.pid] = shard_id

    while pids:
        pid, status = os.wait()
        shard = pids.pop(pid)
        print(f"Shard {shard} finished, status {status}")


def do_export_user(user_profile: UserProfile, output_dir: Path) -> None:
    response: TableData = {}

    export_single_user(user_profile, response)
    export_file = os.path.join(output_dir, "user.json")
    write_table_data(output_file=export_file, data=response)

    reaction_message_ids: set[int] = {row["message"] for row in response["zerver_reaction"]}

    logging.info("Exporting messages")
    export_messages_single_user(
        user_profile, output_dir=output_dir, reaction_message_ids=reaction_message_ids
    )

    logging.info("Exporting images")
    export_uploads_and_avatars(user_profile.realm, user=user_profile, output_dir=output_dir)


def export_single_user(user_profile: UserProfile, response: TableData) -> None:
    config = get_single_user_config()
    export_from_config(
        response=response,
        config=config,
        seed_object=user_profile,
        context=dict(user=user_profile),
    )


def get_single_user_config() -> Config:
    # This function defines the limited configuration for what data to
    # export when exporting all data that a single Zulip user has
    # access to in an organization.

    # zerver_userprofile
    user_profile_config = Config(
        table="zerver_userprofile",
        is_seeded=True,
        exclude=EXCLUDED_USER_PROFILE_FIELDS,
    )

    # zerver_subscription
    subscription_config = Config(
        table="zerver_subscription",
        model=Subscription,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        # Exports with consent are not relevant in the context of exporting
        # a single user.
        limit_to_consenting_users=False,
    )

    # zerver_recipient
    recipient_config = Config(
        table="zerver_recipient",
        model=Recipient,
        virtual_parent=subscription_config,
        id_source=("zerver_subscription", "recipient"),
    )

    # zerver_stream
    #
    # TODO: We currently export the existence of private streams, but
    # not their message history, in the "export with partial member
    # consent" code path.  This consistent with our documented policy,
    # since that data is available to the organization administrator
    # who initiated the export, but unnecessary and potentially
    # confusing; it'd be better to just skip those streams from the
    # export (which would require more complex export logic for the
    # subscription/recipient/stream tables to exclude private streams
    # with no consenting subscribers).
    Config(
        table="zerver_stream",
        model=Stream,
        virtual_parent=recipient_config,
        id_source=("zerver_recipient", "type_id"),
        source_filter=lambda r: r["type"] == Recipient.STREAM,
    )

    Config(
        table="analytics_usercount",
        model=UserCount,
        normal_parent=user_profile_config,
        include_rows="user_id__in",
        limit_to_consenting_users=False,
    )

    Config(
        table="zerver_realmauditlog",
        model=RealmAuditLog,
        virtual_parent=user_profile_config,
        # See the docstring for why we use a custom fetch here.
        custom_fetch=custom_fetch_realm_audit_logs_for_user,
        limit_to_consenting_users=False,
    )

    Config(
        table="zerver_reaction",
        model=Reaction,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
        limit_to_consenting_users=False,
    )

    add_user_profile_child_configs(user_profile_config)

    return user_profile_config


def get_id_list_gently_from_database(*, base_query: Any, id_field: str) -> list[int]:
    """
    Use this function if you need a HUGE number of ids from
    the database, and you don't mind a few extra trips.  Particularly
    for exports, we don't really care about a little extra time
    to finish the export--the much bigger concern is that we don't
    want to overload our database all at once, nor do we want to
    keep a whole bunch of Django objects around in memory.

    So our general process is to call this function first, and then
    we call chunkify to break our ids into small chunks for "fat query"
    batches.

    Even if you are not working at huge scale, this function can
    also be used for the convenience of its API.
    """
    min_id = -1
    all_ids = []
    batch_size = 10000  # we are just getting ints

    assert id_field == "id" or id_field.endswith("_id")

    while True:
        filter_args = {f"{id_field}__gt": min_id}
        new_ids = list(
            base_query.values_list(id_field, flat=True)
            .filter(**filter_args)
            .order_by(id_field)[:batch_size]
        )
        if len(new_ids) == 0:
            break
        all_ids += new_ids
        min_id = new_ids[-1]

    return all_ids


def chunkify(lst: list[int], chunk_size: int) -> list[list[int]]:
    # chunkify([1,2,3,4,5], 2) == [[1,2], [3,4], [5]]
    result = []
    i = 0
    while True:
        chunk = lst[i : i + chunk_size]
        if len(chunk) == 0:
            break
        else:
            result.append(chunk)
            i += chunk_size

    return result


def export_messages_single_user(
    user_profile: UserProfile, *, output_dir: Path, reaction_message_ids: set[int]
) -> None:
    @cache
    def get_recipient(recipient_id: int) -> str:
        recipient = Recipient.objects.get(id=recipient_id)

        if recipient.type == Recipient.STREAM:
            stream = Stream.objects.values("name").get(id=recipient.type_id)
            return stream["name"]

        user_names = (
            UserProfile.objects.filter(
                subscription__recipient_id=recipient.id,
            )
            .order_by("full_name")
            .values_list("full_name", flat=True)
        )

        return ", ".join(user_names)

    messages_from_me = Message.objects.filter(
        # Uses index: zerver_message_realm_sender_recipient (prefix)
        realm_id=user_profile.realm_id,
        sender=user_profile,
    )

    my_subscriptions = Subscription.objects.filter(
        user_profile=user_profile,
        recipient__type__in=[Recipient.PERSONAL, Recipient.DIRECT_MESSAGE_GROUP],
    )
    my_recipient_ids = [sub.recipient_id for sub in my_subscriptions]
    messages_to_me = Message.objects.filter(
        # Uses index: zerver_message_realm_recipient_id (prefix)
        realm_id=user_profile.realm_id,
        recipient_id__in=my_recipient_ids,
    )

    # Find all message ids that pertain to us.
    all_message_ids: set[int] = set()

    for query in [messages_from_me, messages_to_me]:
        all_message_ids |= set(get_id_list_gently_from_database(base_query=query, id_field="id"))

    all_message_ids |= reaction_message_ids

    dump_file_id = 1
    for message_id_chunk in chunkify(sorted(all_message_ids), MESSAGE_BATCH_CHUNK_SIZE):
        fat_query = (
            UserMessage.objects.select_related("message", "message__sending_client")
            .filter(user_profile=user_profile, message_id__in=message_id_chunk)
            .order_by("message_id")
        )

        user_message_chunk = list(fat_query)

        message_chunk = []
        for user_message in user_message_chunk:
            item = model_to_dict(user_message.message)
            item["flags"] = user_message.flags_list()
            item["flags_mask"] = user_message.flags.mask
            # Add a few nice, human-readable details
            item["sending_client_name"] = user_message.message.sending_client.name
            item["recipient_name"] = get_recipient(user_message.message.recipient_id)
            message_chunk.append(item)

        message_filename = os.path.join(output_dir, f"messages-{dump_file_id:06}.json")
        logging.info("Fetched messages for %s", message_filename)

        output = {"zerver_message": message_chunk}
        floatify_datetime_fields(output, "zerver_message")

        write_table_data(message_filename, output)
        dump_file_id += 1


def export_analytics_tables(realm: Realm, output_dir: Path) -> None:
    response: TableData = {}

    logging.info("Fetching analytics table data")
    config = get_analytics_config()
    export_from_config(
        response=response,
        config=config,
        seed_object=realm,
    )

    # The seeding logic results in a duplicate zerver_realm object
    # being included in the analytics data.  We don't want it, as that
    # data is already in `realm.json`, so we just delete it here
    # before writing to disk.
    del response["zerver_realm"]

    export_file = os.path.join(output_dir, "analytics.json")
    write_table_data(output_file=export_file, data=response)


def get_analytics_config() -> Config:
    # The Config function defines what data to export for the
    # analytics.json file in a full-realm export.

    analytics_config = Config(
        table="zerver_realm",
        is_seeded=True,
    )

    Config(
        table="analytics_realmcount",
        model=RealmCount,
        normal_parent=analytics_config,
        include_rows="realm_id__in",
    )

    Config(
        table="analytics_usercount",
        model=UserCount,
        normal_parent=analytics_config,
        include_rows="realm_id__in",
    )

    Config(
        table="analytics_streamcount",
        model=StreamCount,
        normal_parent=analytics_config,
        include_rows="realm_id__in",
    )

    return analytics_config


def get_consented_user_ids(realm: Realm) -> set[int]:
    # A UserProfile is consenting to private data export if either:
    # 1) It is a human account and enabled allow_private_data_export.
    # 2) It is a bot account with allow_private_data_export toggled on.
    # 3) It is a bot whose owner is (1).
    # 4) It is a mirror dummy. This is a special case that requires some
    #    explanation. There are two cases where an account will be a mirror dummy:
    #    a) It comes from a 3rd party export (e.g. from Slack) - in some cases,
    #       certain limited accounts are turned into Zulip mirror dummy accounts.
    #       For such an account, the admins already have access to all the original data,
    #       so we can freely consider the user as consenting and export everything.
    #    b) It was imported from another Zulip export; and it was a non-consented user
    #       in it. Thus, only public data of the user was exported->imported.
    #       Therefore, again we can consider the user as consenting and export
    #       everything - all this data is public by construction.

    query = sql.SQL("""
        WITH consenting_humans AS (
            SELECT id
            FROM zerver_userprofile
            WHERE allow_private_data_export
              AND NOT is_bot
              AND realm_id = {realm_id}
        )
        SELECT id
        FROM zerver_userprofile
        WHERE
            (id IN (SELECT id FROM consenting_humans))
            OR (allow_private_data_export AND is_bot AND realm_id = {realm_id})
            OR (
                bot_owner_id IN (SELECT id FROM consenting_humans)
                AND is_bot
                AND realm_id = {realm_id}
            )
            OR (is_mirror_dummy AND realm_id = {realm_id})
    """).format(realm_id=sql.Literal(realm.id))

    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    return {row[0] for row in rows}


def export_realm_wrapper(
    export_row: RealmExport,
    output_dir: str,
    threads: int,
    upload: bool,
    percent_callback: Callable[[Any], None] | None = None,
    export_as_active: bool | None = None,
) -> str | None:
    try:
        export_row.status = RealmExport.STARTED
        export_row.date_started = timezone_now()
        export_row.save(update_fields=["status", "date_started"])

        exportable_user_ids = None
        if export_row.type == RealmExport.EXPORT_FULL_WITH_CONSENT:
            exportable_user_ids = get_consented_user_ids(export_row.realm)

        tarball_path, stats = do_export_realm(
            realm=export_row.realm,
            output_dir=output_dir,
            threads=threads,
            export_type=export_row.type,
            export_as_active=export_as_active,
            exportable_user_ids=exportable_user_ids,
        )

        RealmAuditLog.objects.create(
            acting_user=export_row.acting_user,
            realm=export_row.realm,
            event_type=AuditLogEventType.REALM_EXPORTED,
            event_time=timezone_now(),
            extra_data={"realm_export_id": export_row.id},
        )

        shutil.rmtree(output_dir)
        print(f"Tarball written to {tarball_path}")

        print("Calculating SHA-256 checksum of tarball...")

        # TODO: We can directly use 'hashlib.file_digest'. (New in Python 3.11)
        sha256_hash = hashlib.sha256()
        with open(tarball_path, "rb") as f:
            buf = bytearray(2**18)
            view = memoryview(buf)
            while True:
                size = f.readinto(buf)
                if size == 0:
                    break
                sha256_hash.update(view[:size])

        export_row.sha256sum_hex = sha256_hash.hexdigest()
        export_row.tarball_size_bytes = os.path.getsize(tarball_path)
        export_row.status = RealmExport.SUCCEEDED
        export_row.date_succeeded = timezone_now()
        export_row.stats = stats

        print(f"SHA-256 checksum is {export_row.sha256sum_hex}")

        if not upload:
            export_row.save(
                update_fields=[
                    "sha256sum_hex",
                    "tarball_size_bytes",
                    "status",
                    "date_succeeded",
                    "stats",
                ]
            )
            return None

        print("Uploading export tarball...")
        public_url = zerver.lib.upload.upload_backend.upload_export_tarball(
            export_row.realm, tarball_path, percent_callback=percent_callback
        )
        print(f"\nUploaded to {public_url}")

        # Update the export_path field now that the export is complete.
        export_row.export_path = urlsplit(public_url).path
        export_row.save(
            update_fields=[
                "sha256sum_hex",
                "tarball_size_bytes",
                "status",
                "date_succeeded",
                "stats",
                "export_path",
            ]
        )

        os.remove(tarball_path)
        print(f"Successfully deleted the tarball at {tarball_path}")
        return public_url
    except Exception:
        export_row.status = RealmExport.FAILED
        export_row.date_failed = timezone_now()
        export_row.save(update_fields=["status", "date_failed"])
        raise


def get_realm_exports_serialized(realm: Realm) -> list[dict[str, Any]]:
    # Exclude exports made via shell. 'acting_user=None', since they
    # aren't supported in the current API format.
    #
    # TODO: We should return those via the API as well, with an
    # appropriate way to express for who issued them; this requires an
    # API change.
    all_exports = RealmExport.objects.filter(realm=realm).exclude(acting_user=None)
    exports_dict = {}
    for export in all_exports:
        export_url = None
        export_path = export.export_path
        pending = export.status in [RealmExport.REQUESTED, RealmExport.STARTED]

        if export.status == RealmExport.SUCCEEDED:
            assert export_path is not None
            export_url = zerver.lib.upload.upload_backend.get_export_tarball_url(realm, export_path)

        deleted_timestamp = (
            datetime_to_timestamp(export.date_deleted) if export.date_deleted else None
        )
        failed_timestamp = datetime_to_timestamp(export.date_failed) if export.date_failed else None
        acting_user = export.acting_user
        assert acting_user is not None
        exports_dict[export.id] = dict(
            id=export.id,
            export_time=datetime_to_timestamp(export.date_requested),
            acting_user_id=acting_user.id,
            export_url=export_url,
            deleted_timestamp=deleted_timestamp,
            failed_timestamp=failed_timestamp,
            pending=pending,
            export_type=export.type,
        )
    return sorted(exports_dict.values(), key=lambda export_dict: export_dict["id"])


def export_migration_status(output_dir: str) -> None:
    migration_status_json = MigrationStatusJson(
        migrations_by_app=parse_migration_status(),
        zulip_version=ZULIP_VERSION,
    )
    output_file = os.path.join(output_dir, "migration_status.json")
    with open(output_file, "wb") as f:
        f.write(orjson.dumps(migration_status_json, option=orjson.OPT_INDENT_2))


def do_common_export_processes(output_dir: str) -> None:
    # Performs common task(s) necessary for preparing Zulip data exports.
    # This function is typically shared with migration tools in the
    # `zerver/data_import` directory.

    logging.info("Exporting migration status")
    export_migration_status(output_dir)


def check_export_with_consent_is_usable(realm: Realm) -> bool:
    # Users without consent enabled will end up deactivated in the exported
    # data. An organization without a consenting Owner would therefore not be
    # functional after export->import. That's most likely not desired by the user
    # so check for such a case.
    consented_user_ids = get_consented_user_ids(realm)
    return UserProfile.objects.filter(
        id__in=consented_user_ids, role=UserProfile.ROLE_REALM_OWNER, realm=realm
    ).exists()


def check_public_export_is_usable(realm: Realm) -> bool:
    # Since users with email visibility set to NOBODY won't have their real emails
    # exported, this could result in a lack of functional Owner accounts.
    # We make sure that at least one Owner can have their real email address exported.
    return UserProfile.objects.filter(
        role=UserProfile.ROLE_REALM_OWNER,
        email_address_visibility__in=[
            UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            UserProfile.EMAIL_ADDRESS_VISIBILITY_MEMBERS,
            UserProfile.EMAIL_ADDRESS_VISIBILITY_MODERATORS,
            UserProfile.EMAIL_ADDRESS_VISIBILITY_ADMINS,
        ],
        realm=realm,
    ).exists()
