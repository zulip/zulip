# This is the main code for the `./manage.py export` data export tool.
# User docs: https://zulip.readthedocs.io/en/latest/production/export-and-import.html
#
# Most developers will interact with this primarily when they add a
# new table to the schema, in which case they likely need to (1) add
# it the lists in `ALL_ZULIP_TABLES` and similar data structures and
# (2) if it doesn't belong in EXCLUDED_TABLES, add a Config object for
# it to get_realm_config.
import glob
import logging
import os
import shutil
import subprocess
import tempfile
from contextlib import suppress
from datetime import datetime
from functools import cache
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple, TypedDict

import orjson
from django.apps import apps
from django.conf import settings
from django.db.models import Exists, OuterRef, Q
from django.forms.models import model_to_dict
from django.utils.timezone import is_naive as timezone_is_naive
from mypy_boto3_s3.service_resource import Object
from typing_extensions import TypeAlias

import zerver.lib.upload
from analytics.models import RealmCount, StreamCount, UserCount
from scripts.lib.zulip_tools import overwrite_symlink
from zerver.lib.avatar_hash import user_avatar_path_from_ids
from zerver.lib.pysa import mark_sanitized
from zerver.lib.upload.s3 import get_bucket
from zerver.models import (
    AlertWord,
    Attachment,
    BotConfigData,
    BotStorageData,
    Client,
    CustomProfileField,
    CustomProfileFieldValue,
    DefaultStream,
    GroupGroupMembership,
    Huddle,
    Message,
    MutedUser,
    NamedUserGroup,
    OnboardingStep,
    Reaction,
    Realm,
    RealmAuditLog,
    RealmAuthenticationMethod,
    RealmDomain,
    RealmEmoji,
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
from zerver.models.realms import get_realm
from zerver.models.users import get_system_bot, get_user_profile_by_id

# Custom mypy types follow:
Record: TypeAlias = Dict[str, Any]
TableName = str
TableData: TypeAlias = Dict[TableName, List[Record]]
Field = str
Path = str
Context: TypeAlias = Dict[str, Any]
FilterArgs: TypeAlias = Dict[str, Any]
IdSource: TypeAlias = Tuple[TableName, Field]
SourceFilter: TypeAlias = Callable[[Record], bool]

CustomFetch: TypeAlias = Callable[[TableData, Context], None]


class MessagePartial(TypedDict):
    zerver_message: List[Record]
    zerver_userprofile_ids: List[int]
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
    "zerver_client",
    "zerver_customprofilefield",
    "zerver_customprofilefieldvalue",
    "zerver_defaultstream",
    "zerver_defaultstreamgroup",
    "zerver_defaultstreamgroup_streams",
    "zerver_draft",
    "zerver_emailchangestatus",
    "zerver_groupgroupmembership",
    "zerver_huddle",
    "zerver_message",
    "zerver_missedmessageemailaddress",
    "zerver_multiuseinvite",
    "zerver_multiuseinvite_streams",
    "zerver_namedusergroup",
    "zerver_onboardingstep",
    "zerver_preregistrationrealm",
    "zerver_preregistrationuser",
    "zerver_preregistrationuser_streams",
    "zerver_pushdevicetoken",
    "zerver_reaction",
    "zerver_realm",
    "zerver_realmauditlog",
    "zerver_realmauthenticationmethod",
    "zerver_realmdomain",
    "zerver_realmemoji",
    "zerver_realmfilter",
    "zerver_realmplayground",
    "zerver_realmreactivationstatus",
    "zerver_realmuserdefault",
    "zerver_recipient",
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
    "zerver_preregistrationrealm",
    "zerver_preregistrationuser",
    "zerver_preregistrationuser_streams",
    "zerver_realmreactivationstatus",
    # Missed message addresses are low value to export since
    # missed-message email addresses include the server's hostname and
    # expire after a few days.
    "zerver_missedmessageemailaddress",
    # Scheduled message notification email data is for internal use by the server.
    "zerver_scheduledmessagenotificationemail",
    # When switching servers, clients will need to re-log in and
    # reregister for push notifications anyway.
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
DATE_FIELDS: Dict[TableName, List[Field]] = {
    "analytics_installationcount": ["end_time"],
    "analytics_realmcount": ["end_time"],
    "analytics_streamcount": ["end_time"],
    "analytics_usercount": ["end_time"],
    "zerver_attachment": ["create_time"],
    "zerver_message": ["last_edit_time", "date_sent"],
    "zerver_muteduser": ["date_muted"],
    "zerver_realmauditlog": ["event_time"],
    "zerver_realm": ["date_created"],
    "zerver_scheduledmessage": ["scheduled_timestamp"],
    "zerver_stream": ["date_created"],
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


def write_table_data(output_file: str, data: Dict[str, Any]) -> None:
    # We sort by ids mostly so that humans can quickly do diffs
    # on two export jobs to see what changed (either due to new
    # data arriving or new code being deployed).
    for table in data.values():
        table.sort(key=lambda row: row["id"])

    assert output_file.endswith(".json")

    write_data_to_file(output_file, data)


def write_records_json_file(output_dir: str, records: List[Dict[str, Any]]) -> None:
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


def make_raw(query: Any, exclude: Optional[List[Field]] = None) -> List[Record]:
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
        table: Optional[str] = None,
        model: Optional[Any] = None,
        normal_parent: Optional["Config"] = None,
        virtual_parent: Optional["Config"] = None,
        filter_args: Optional[FilterArgs] = None,
        custom_fetch: Optional[CustomFetch] = None,
        custom_tables: Optional[List[TableName]] = None,
        concat_and_destroy: Optional[List[TableName]] = None,
        id_source: Optional[IdSource] = None,
        source_filter: Optional[SourceFilter] = None,
        include_rows: Optional[Field] = None,
        use_all: bool = False,
        is_seeded: bool = False,
        exclude: Optional[List[Field]] = None,
    ) -> None:
        assert table or custom_tables
        self.table = table
        self.model = model
        self.normal_parent = normal_parent
        self.virtual_parent = virtual_parent
        self.filter_args = filter_args
        self.include_rows = include_rows
        self.use_all = use_all
        self.is_seeded = is_seeded
        self.exclude = exclude
        self.custom_fetch = custom_fetch
        self.custom_tables = custom_tables
        self.concat_and_destroy = concat_and_destroy
        self.id_source = id_source
        self.source_filter = source_filter
        self.children: List[Config] = []

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

        if normal_parent is not None:
            self.parent: Optional[Config] = normal_parent
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


def export_from_config(
    response: TableData,
    config: Config,
    seed_object: Optional[Any] = None,
    context: Optional[Context] = None,
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
        data: List[Record] = []
        for t in config.concat_and_destroy:
            data += response[t]
            del response[t]
            logging.info("Deleted temporary %s", t)
        assert table is not None
        response[table] = data

    elif config.use_all:
        assert model is not None
        query = model.objects.all()
        rows = list(query)

    elif config.normal_parent:
        # In this mode, our current model is figuratively Article,
        # and normal_parent is figuratively Blog, and
        # now we just need to get all the articles
        # contained by the blogs.
        model = config.model
        assert parent is not None
        assert parent.table is not None
        assert config.include_rows is not None
        parent_ids = [r["id"] for r in response[parent.table]]
        filter_params: Dict[str, Any] = {config.include_rows: parent_ids}
        if config.filter_args is not None:
            filter_params.update(config.filter_args)
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

    # Post-process rows
    for t in exported_tables:
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
        table="zerver_client",
        model=Client,
        virtual_parent=realm_config,
        use_all=True,
    )

    Config(
        table="zerver_realmuserdefault",
        model=RealmUserDefault,
        normal_parent=realm_config,
        include_rows="realm_id__in",
    )

    user_profile_config = Config(
        custom_tables=[
            "zerver_userprofile",
            "zerver_userprofile_mirrordummy",
        ],
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
    )

    Config(
        table="zerver_service",
        model=Service,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
    )

    Config(
        table="zerver_botstoragedata",
        model=BotStorageData,
        normal_parent=user_profile_config,
        include_rows="bot_profile_id__in",
    )

    Config(
        table="zerver_botconfigdata",
        model=BotConfigData,
        normal_parent=user_profile_config,
        include_rows="bot_profile_id__in",
    )

    # Some of these tables are intermediate "tables" that we
    # create only for the export.  Think of them as similar to views.

    user_subscription_config = Config(
        table="_user_subscription",
        model=Subscription,
        normal_parent=user_profile_config,
        filter_args={"recipient__type": Recipient.PERSONAL},
        include_rows="user_profile_id__in",
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
        exclude=["email_token"],
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
        custom_fetch=custom_fetch_huddle_objects,
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
    )

    add_user_profile_child_configs(user_profile_config)

    return realm_config


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
    )

    Config(
        table="zerver_customprofilefieldvalue",
        model=CustomProfileFieldValue,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
    )

    Config(
        table="zerver_muteduser",
        model=MutedUser,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
    )

    Config(
        table="zerver_onboardingstep",
        model=OnboardingStep,
        normal_parent=user_profile_config,
        include_rows="user_id__in",
    )

    Config(
        table="zerver_useractivity",
        model=UserActivity,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
    )

    Config(
        table="zerver_useractivityinterval",
        model=UserActivityInterval,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
    )

    Config(
        table="zerver_userpresence",
        model=UserPresence,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
    )

    Config(
        table="zerver_userstatus",
        model=UserStatus,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
    )

    Config(
        table="zerver_usertopic",
        model=UserTopic,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
    )


# We exclude these fields for the following reasons:
# * api_key is a secret.
# * password is a secret.
# * uuid is unlikely to be useful if the domain changes.
EXCLUDED_USER_PROFILE_FIELDS = ["api_key", "password", "uuid"]


def custom_fetch_user_profile(response: TableData, context: Context) -> None:
    realm = context["realm"]
    exportable_user_ids = context["exportable_user_ids"]

    query = UserProfile.objects.filter(realm_id=realm.id).exclude(
        # These were, in some early versions of Zulip, inserted into
        # the first realm that was created.  In those cases, rather
        # than include them here, we will include them in the
        # crossrealm user list, below.
        email__in=settings.CROSS_REALM_BOT_EMAILS,
    )
    exclude = EXCLUDED_USER_PROFILE_FIELDS
    rows = make_raw(list(query), exclude=exclude)

    normal_rows: List[Record] = []
    dummy_rows: List[Record] = []

    for row in rows:
        if exportable_user_ids is not None:
            if row["id"] in exportable_user_ids:
                assert not row["is_mirror_dummy"]
            else:
                # Convert non-exportable users to
                # inactive is_mirror_dummy users.
                row["is_mirror_dummy"] = True
                row["is_active"] = False

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
    response: TableData, realm_id: int, message_ids: Set[int], scheduled_message_ids: Set[int]
) -> List[Attachment]:
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


def fetch_reaction_data(response: TableData, message_ids: Set[int]) -> None:
    query = Reaction.objects.filter(message_id__in=list(message_ids))
    response["zerver_reaction"] = make_raw(list(query))


def custom_fetch_huddle_objects(response: TableData, context: Context) -> None:
    realm = context["realm"]
    user_profile_ids = {
        r["id"] for r in response["zerver_userprofile"] + response["zerver_userprofile_mirrordummy"]
    }

    # First we get all huddles involving someone in the realm.
    realm_huddle_subs = Subscription.objects.select_related("recipient").filter(
        recipient__type=Recipient.DIRECT_MESSAGE_GROUP, user_profile__in=user_profile_ids
    )
    realm_huddle_recipient_ids = {sub.recipient_id for sub in realm_huddle_subs}

    # Mark all Huddles whose recipient ID contains a cross-realm user.
    unsafe_huddle_recipient_ids = set()
    for sub in Subscription.objects.select_related("user_profile").filter(
        recipient__in=realm_huddle_recipient_ids
    ):
        if sub.user_profile.realm_id != realm.id:
            # In almost every case the other realm will be zulip.com
            unsafe_huddle_recipient_ids.add(sub.recipient_id)

    # Now filter down to just those huddles that are entirely within the realm.
    #
    # This is important for ensuring that the User objects needed
    # to import it on the other end exist (since we're only
    # exporting the users from this realm), at the cost of losing
    # some of these cross-realm messages.
    huddle_subs = [
        sub for sub in realm_huddle_subs if sub.recipient_id not in unsafe_huddle_recipient_ids
    ]
    huddle_recipient_ids = {sub.recipient_id for sub in huddle_subs}
    huddle_ids = {sub.recipient.type_id for sub in huddle_subs}

    huddle_subscription_dicts = make_raw(huddle_subs)
    huddle_recipients = make_raw(Recipient.objects.filter(id__in=huddle_recipient_ids))

    response["_huddle_recipient"] = huddle_recipients
    response["_huddle_subscription"] = huddle_subscription_dicts
    response["zerver_huddle"] = make_raw(Huddle.objects.filter(id__in=huddle_ids))


def custom_fetch_scheduled_messages(response: TableData, context: Context) -> None:
    """
    Simple custom fetch function to fetch only the ScheduledMessage objects that we're allowed to.
    """
    realm = context["realm"]
    exportable_scheduled_message_ids = context["exportable_scheduled_message_ids"]

    query = ScheduledMessage.objects.filter(realm=realm, id__in=exportable_scheduled_message_ids)
    rows = make_raw(list(query))

    response["zerver_scheduledmessage"] = rows


def custom_fetch_realm_audit_logs_for_realm(response: TableData, context: Context) -> None:
    """
    Simple custom fetch function to fix up .acting_user for some RealmAuditLog objects.

    Certain RealmAuditLog objects have an acting_user that is in a different .realm, due to
    the possibility of server administrators (typically with the .is_staff permission) taking
    certain actions to modify UserProfiles or Realms, which will set the .acting_user to
    the administrator's UserProfile, which can be in a different realm. Such an acting_user
    cannot be imported during organization import on another server, so we need to just set it
    to None.
    """
    realm = context["realm"]

    query = RealmAuditLog.objects.filter(realm=realm).select_related("acting_user")
    realmauditlog_objects = list(query)
    for realmauditlog in realmauditlog_objects:
        if realmauditlog.acting_user is not None and realmauditlog.acting_user.realm_id != realm.id:
            realmauditlog.acting_user = None

    rows = make_raw(realmauditlog_objects)

    response["zerver_realmauditlog"] = rows


def fetch_usermessages(
    realm: Realm,
    message_ids: Set[int],
    user_profile_ids: Set[int],
    message_filename: Path,
    consent_message_id: Optional[int] = None,
) -> List[Record]:
    # UserMessage export security rule: You can export UserMessages
    # for the messages you exported for the users in your realm.
    user_message_query = UserMessage.objects.filter(
        user_profile__realm=realm, message_id__in=message_ids
    )
    if consent_message_id is not None:
        consented_user_ids = get_consented_user_ids(consent_message_id)
        user_profile_ids = user_profile_ids & consented_user_ids
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
    input_path: Path, output_path: Path, consent_message_id: Optional[int] = None
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
        realm, message_ids, user_profile_ids, output_path, consent_message_id
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
    chunk_size: int = MESSAGE_BATCH_CHUNK_SIZE,
    output_dir: Optional[Path] = None,
    public_only: bool = False,
    consent_message_id: Optional[int] = None,
) -> Set[int]:
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="zulip-export")

    def get_ids(records: Iterable[Mapping[str, Any]]) -> Set[int]:
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

    consented_user_ids: Set[int] = set()
    if consent_message_id is not None:
        consented_user_ids = get_consented_user_ids(consent_message_id)

    if public_only:
        recipient_streams = Stream.objects.filter(realm=realm, invite_only=False)
        recipient_ids = Recipient.objects.filter(
            type=Recipient.STREAM, type_id__in=recipient_streams
        ).values_list("id", flat=True)
        recipient_ids_for_us = get_ids(response["zerver_recipient"]) & set(recipient_ids)
    elif consent_message_id is not None:
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

    if public_only:
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

        if consent_message_id is not None:
            # Export with member consent requires some careful handling to make sure
            # we only include messages that a consenting user can access.
            has_usermessage_expression = Exists(
                UserMessage.objects.filter(
                    user_profile_id__in=consented_user_ids, message_id=OuterRef("id")
                )
            )
            messages_we_received_in_protected_history_streams = Message.objects.annotate(
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

    all_message_ids: Set[int] = set()

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
    )

    return all_message_ids


def write_message_partials(
    *,
    realm: Realm,
    message_id_chunks: List[List[int]],
    output_dir: Path,
    user_profile_ids: Set[int],
) -> None:
    dump_file_id = 1

    for message_id_chunk in message_id_chunks:
        # Uses index: zerver_message_pkey
        actual_query = Message.objects.filter(id__in=message_id_chunk).order_by("id")
        message_chunk = make_raw(actual_query)

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
    attachments: Optional[List[Attachment]] = None,
    user: Optional[UserProfile],
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
        for user_id in user_ids:
            avatar_path = user_avatar_path_from_ids(user_id, realm.id)
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

        emoji_paths = {get_emoji_path(realm_emoji) for realm_emoji in realm_emojis}

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
    bucket_name: str, key: Object, processing_emoji: bool
) -> Dict[str, Any]:
    # Helper function for export_files_from_s3
    record: Dict[str, Any] = dict(
        s3_path=key.key,
        bucket=bucket_name,
        size=key.content_length,
        last_modified=key.last_modified,
        content_type=key.content_type,
        md5=key.e_tag,
    )
    record.update(key.metadata)

    if processing_emoji:
        record["file_name"] = os.path.basename(key.key)

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

    return record


def _save_s3_object_to_file(
    key: Object,
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
    user_ids: Set[int],
    valid_hashes: Optional[Set[str]],
) -> None:
    processing_uploads = flavor == "upload"
    processing_emoji = flavor == "emoji"

    bucket = get_bucket(bucket_name)
    records = []

    logging.info("Downloading %s files from %s", flavor, bucket_name)

    email_gateway_bot: Optional[UserProfile] = None

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
    realm: Realm, local_dir: Path, output_dir: Path, attachments: List[Attachment]
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
    users: List[UserProfile],
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

        avatar_path = user_avatar_path_from_ids(user.id, realm.id)
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
    realm: Realm, local_dir: Path, output_dir: Path, realm_emojis: List[RealmEmoji]
) -> None:
    records = []
    for count, realm_emoji in enumerate(realm_emojis, 1):
        emoji_path = get_emoji_path(realm_emoji)

        # Use 'mark_sanitized' to work around false positive caused by Pysa
        # thinking that 'realm' (and thus 'attachment' and 'attachment.path_id')
        # are user controlled
        emoji_path = mark_sanitized(emoji_path)

        local_path = os.path.join(local_dir, emoji_path)
        output_path = os.path.join(output_dir, emoji_path)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy2(local_path, output_path)
        # Realm emoji author is optional.
        author = realm_emoji.author
        author_id = None
        if author:
            author_id = author.id
        record = dict(
            realm_id=realm.id,
            author=author_id,
            path=emoji_path,
            s3_path=emoji_path,
            file_name=realm_emoji.file_name,
            name=realm_emoji.name,
            deactivated=realm_emoji.deactivated,
        )
        records.append(record)

        if count % 100 == 0:
            logging.info("Finished %s", count)

    write_records_json_file(output_dir, records)


def do_write_stats_file_for_realm_export(output_dir: Path) -> None:
    stats_file = os.path.join(output_dir, "stats.txt")
    realm_file = os.path.join(output_dir, "realm.json")
    attachment_file = os.path.join(output_dir, "attachment.json")
    analytics_file = os.path.join(output_dir, "analytics.json")
    message_files = glob.glob(os.path.join(output_dir, "messages-*.json"))
    fns = sorted([analytics_file, attachment_file, *message_files, realm_file])

    logging.info("Writing stats file: %s\n", stats_file)
    with open(stats_file, "w") as f:
        for fn in fns:
            f.write(os.path.basename(fn) + "\n")
            with open(fn, "rb") as filename:
                data = orjson.loads(filename.read())
            for k in sorted(data):
                f.write(f"{len(data[k]):5} {k}\n")
            f.write("\n")

        avatar_file = os.path.join(output_dir, "avatars/records.json")
        uploads_file = os.path.join(output_dir, "uploads/records.json")

        for fn in [avatar_file, uploads_file]:
            f.write(fn + "\n")
            with open(fn, "rb") as filename:
                data = orjson.loads(filename.read())
            f.write(f"{len(data):5} records\n")
            f.write("\n")


def get_exportable_scheduled_message_ids(
    realm: Realm, public_only: bool = False, consent_message_id: Optional[int] = None
) -> Set[int]:
    """
    Scheduled messages are private to the sender, so which ones we export depends on the
    public/consent/full export mode.
    """

    if public_only:
        return set()

    if consent_message_id:
        sender_ids = get_consented_user_ids(consent_message_id)
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
    exportable_user_ids: Optional[Set[int]] = None,
    public_only: bool = False,
    consent_message_id: Optional[int] = None,
    export_as_active: Optional[bool] = None,
) -> str:
    response: TableData = {}

    # We need at least one thread running to export
    # UserMessage rows.  The management command should
    # enforce this for us.
    if not settings.TEST_SUITE:
        assert threads >= 1

    realm_config = get_realm_config()

    create_soft_link(source=output_dir, in_progress=True)

    exportable_scheduled_message_ids = get_exportable_scheduled_message_ids(
        realm, public_only, consent_message_id
    )

    logging.info("Exporting data from get_realm_config()...")
    export_from_config(
        response=response,
        config=realm_config,
        seed_object=realm,
        context=dict(
            realm=realm,
            exportable_user_ids=exportable_user_ids,
            exportable_scheduled_message_ids=exportable_scheduled_message_ids,
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
        output_dir=output_dir,
        public_only=public_only,
        consent_message_id=consent_message_id,
    )
    logging.info("%d messages were exported", len(message_ids))

    # zerver_reaction
    zerver_reaction: TableData = {}
    fetch_reaction_data(response=zerver_reaction, message_ids=message_ids)
    response.update(zerver_reaction)

    # Override the "deactivated" flag on the realm
    if export_as_active is not None:
        response["zerver_realm"][0]["deactivated"] = not export_as_active

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
        threads=threads, output_dir=output_dir, consent_message_id=consent_message_id
    )

    logging.info("Finished exporting %s", realm.string_id)
    create_soft_link(source=output_dir, in_progress=False)

    do_write_stats_file_for_realm_export(output_dir)

    tarball_path = output_dir.rstrip("/") + ".tar.gz"
    subprocess.check_call(
        [
            "tar",
            f"-czf{tarball_path}",
            f"-C{os.path.dirname(output_dir)}",
            os.path.basename(output_dir),
        ]
    )
    return tarball_path


def export_attachment_table(
    realm: Realm, output_dir: Path, message_ids: Set[int], scheduled_message_ids: Set[int]
) -> List[Attachment]:
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
    threads: int, output_dir: Path, consent_message_id: Optional[int] = None
) -> None:
    logging.info("Launching %d PARALLEL subprocesses to export UserMessage rows", threads)
    pids = {}

    for shard_id in range(threads):
        arguments = [
            os.path.join(settings.DEPLOY_ROOT, "manage.py"),
            "export_usermessage_batch",
            f"--path={output_dir}",
            f"--thread={shard_id}",
        ]
        if consent_message_id is not None:
            arguments.append(f"--consent-message-id={consent_message_id}")

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

    reaction_message_ids: Set[int] = {row["message"] for row in response["zerver_reaction"]}

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
        exclude=["email_token"],
    )

    Config(
        table="analytics_usercount",
        model=UserCount,
        normal_parent=user_profile_config,
        include_rows="user_id__in",
    )

    Config(
        table="zerver_realmauditlog",
        model=RealmAuditLog,
        virtual_parent=user_profile_config,
        # See the docstring for why we use a custom fetch here.
        custom_fetch=custom_fetch_realm_audit_logs_for_user,
    )

    Config(
        table="zerver_reaction",
        model=Reaction,
        normal_parent=user_profile_config,
        include_rows="user_profile_id__in",
    )

    add_user_profile_child_configs(user_profile_config)

    return user_profile_config


def get_id_list_gently_from_database(*, base_query: Any, id_field: str) -> List[int]:
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


def chunkify(lst: List[int], chunk_size: int) -> List[List[int]]:
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
    user_profile: UserProfile, *, output_dir: Path, reaction_message_ids: Set[int]
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
    all_message_ids: Set[int] = set()

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


def get_consented_user_ids(consent_message_id: int) -> Set[int]:
    return set(
        Reaction.objects.filter(
            message_id=consent_message_id,
            reaction_type="unicode_emoji",
            # outbox = 1f4e4
            emoji_code="1f4e4",
        ).values_list("user_profile", flat=True)
    )


def export_realm_wrapper(
    realm: Realm,
    output_dir: str,
    threads: int,
    upload: bool,
    public_only: bool,
    percent_callback: Optional[Callable[[Any], None]] = None,
    consent_message_id: Optional[int] = None,
    export_as_active: Optional[bool] = None,
) -> Optional[str]:
    tarball_path = do_export_realm(
        realm=realm,
        output_dir=output_dir,
        threads=threads,
        public_only=public_only,
        consent_message_id=consent_message_id,
        export_as_active=export_as_active,
    )
    shutil.rmtree(output_dir)
    print(f"Tarball written to {tarball_path}")
    if not upload:
        return None

    # We upload to the `avatars` bucket because that's world-readable
    # without additional configuration.  We'll likely want to change
    # that in the future.
    print("Uploading export tarball...")
    public_url = zerver.lib.upload.upload_backend.upload_export_tarball(
        realm, tarball_path, percent_callback=percent_callback
    )
    print(f"\nUploaded to {public_url}")

    os.remove(tarball_path)
    print(f"Successfully deleted the tarball at {tarball_path}")
    return public_url


def get_realm_exports_serialized(user: UserProfile) -> List[Dict[str, Any]]:
    all_exports = RealmAuditLog.objects.filter(
        realm=user.realm, event_type=RealmAuditLog.REALM_EXPORTED
    )
    exports_dict = {}
    for export in all_exports:
        export_url = None
        deleted_timestamp = None
        failed_timestamp = None
        acting_user = export.acting_user

        export_data = export.extra_data

        deleted_timestamp = export_data.get("deleted_timestamp")
        failed_timestamp = export_data.get("failed_timestamp")
        export_path = export_data.get("export_path")

        pending = deleted_timestamp is None and failed_timestamp is None and export_path is None

        if export_path is not None and not deleted_timestamp:
            export_url = zerver.lib.upload.upload_backend.get_export_tarball_url(
                user.realm, export_path
            )

        assert acting_user is not None
        exports_dict[export.id] = dict(
            id=export.id,
            export_time=export.event_time.timestamp(),
            acting_user_id=acting_user.id,
            export_url=export_url,
            deleted_timestamp=deleted_timestamp,
            failed_timestamp=failed_timestamp,
            pending=pending,
        )
    return sorted(exports_dict.values(), key=lambda export_dict: export_dict["id"])
