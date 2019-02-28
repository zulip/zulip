# This is the main code for the `./manage.py export` data export tool.
# User docs: https://zulip.readthedocs.io/en/latest/production/export-and-import.html
#
# Most developers will interact with this primarily when they add a
# new table to the schema, in which case they likely need to (1) add
# it the lists in `ALL_ZULIP_TABLES` and similar data structures and
# (2) if it doesn't belong in EXCLUDED_TABLES, add a Config object for
# it to get_realm_config.
import datetime
from boto.s3.connection import S3Connection
from boto.s3.key import Key  # for mypy
from django.apps import apps
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import make_aware as timezone_make_aware
from django.utils.timezone import is_naive as timezone_is_naive
import glob
import logging
import os
import ujson
import subprocess
import tempfile
import shutil
from scripts.lib.zulip_tools import overwrite_symlink
from zerver.lib.avatar_hash import user_avatar_path_from_ids
from analytics.models import RealmCount, UserCount, StreamCount
from zerver.models import UserProfile, Realm, Client, Huddle, Stream, \
    UserMessage, Subscription, Message, RealmEmoji, RealmFilter, Reaction, \
    RealmDomain, Recipient, DefaultStream, get_user_profile_by_id, \
    UserPresence, UserActivity, UserActivityInterval, CustomProfileField, \
    CustomProfileFieldValue, get_display_recipient, Attachment, get_system_bot, \
    RealmAuditLog, UserHotspot, MutedTopic, Service, UserGroup, \
    UserGroupMembership, BotStorageData, BotConfigData
from zerver.lib.parallel import run_parallel
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, \
    Union

# Custom mypy types follow:
Record = Dict[str, Any]
TableName = str
TableData = Dict[TableName, List[Record]]
Field = str
Path = str
Context = Dict[str, Any]
FilterArgs = Dict[str, Any]
IdSource = Tuple[TableName, Field]
SourceFilter = Callable[[Record], bool]

# These next two types are callbacks, which mypy does not
# support well, because PEP 484 says "using callbacks
# with keyword arguments is not perceived as a common use case."
# CustomFetch = Callable[[TableData, Config, Context], None]
# PostProcessData = Callable[[TableData, Config, Context], None]
CustomFetch = Any  # TODO: make more specific, see above
PostProcessData = Any  # TODO: make more specific

# The keys of our MessageOutput variables are normally
# List[Record], but when we write partials, we can get
# lists of integers or a single integer.
# TODO: This could maybe be improved using TypedDict?
MessageOutput = Dict[str, Union[List[Record], List[int], int]]

MESSAGE_BATCH_CHUNK_SIZE = 1000

ALL_ZULIP_TABLES = {
    'analytics_fillstate',
    'analytics_installationcount',
    'analytics_realmcount',
    'analytics_streamcount',
    'analytics_usercount',
    'otp_static_staticdevice',
    'otp_static_statictoken',
    'otp_totp_totpdevice',
    'social_auth_association',
    'social_auth_code',
    'social_auth_nonce',
    'social_auth_partial',
    'social_auth_usersocialauth',
    'two_factor_phonedevice',
    'zerver_archivedattachment',
    'zerver_archivedattachment_messages',
    'zerver_archivedmessage',
    'zerver_archivedusermessage',
    'zerver_attachment',
    'zerver_attachment_messages',
    'zerver_botconfigdata',
    'zerver_botstoragedata',
    'zerver_client',
    'zerver_customprofilefield',
    'zerver_customprofilefieldvalue',
    'zerver_defaultstream',
    'zerver_defaultstreamgroup',
    'zerver_defaultstreamgroup_streams',
    'zerver_emailchangestatus',
    'zerver_huddle',
    'zerver_message',
    'zerver_multiuseinvite',
    'zerver_multiuseinvite_streams',
    'zerver_preregistrationuser',
    'zerver_preregistrationuser_streams',
    'zerver_pushdevicetoken',
    'zerver_reaction',
    'zerver_realm',
    'zerver_realmauditlog',
    'zerver_realmdomain',
    'zerver_realmemoji',
    'zerver_realmfilter',
    'zerver_recipient',
    'zerver_scheduledemail',
    'zerver_scheduledmessage',
    'zerver_service',
    'zerver_stream',
    'zerver_submessage',
    'zerver_subscription',
    'zerver_useractivity',
    'zerver_useractivityinterval',
    'zerver_usergroup',
    'zerver_usergroupmembership',
    'zerver_userhotspot',
    'zerver_usermessage',
    'zerver_userpresence',
    'zerver_userprofile',
    'zerver_userprofile_groups',
    'zerver_userprofile_user_permissions',
    'zerver_userstatus',
    'zerver_mutedtopic',
}

# This set contains those database tables that we expect to not be
# included in the export.  This tool does validation to ensure that
# every table in the database is either exported or listed here, to
# ensure we never accidentally fail to export a table.
NON_EXPORTED_TABLES = {
    # These invitation/confirmation flow tables don't make sense to
    # export, since invitations links will be broken by the server URL
    # change anyway:
    'zerver_emailchangestatus',
    'zerver_multiuseinvite',
    'zerver_multiuseinvite_streams',
    'zerver_preregistrationuser',
    'zerver_preregistrationuser_streams',

    # When switching servers, clients will need to re-login and
    # reregister for push notifications anyway.
    'zerver_pushdevicetoken',

    # We don't use these generated Django tables
    'zerver_userprofile_groups',
    'zerver_userprofile_user_permissions',

    # These is used for scheduling future activity; it could make
    # sense to export, but is relatively low value.
    'zerver_scheduledemail',
    'zerver_scheduledmessage',

    # These tables are related to a user's 2FA authentication
    # configuration, which will need to be re-setup on the new server.
    'two_factor_phonedevice',
    'otp_static_staticdevice',
    'otp_static_statictoken',
    'otp_totp_totpdevice',

    # These archive tables should not be exported (they are to support
    # restoring content accidentally deleted due to software bugs in
    # the retention policy feature)
    'zerver_archivedmessage',
    'zerver_archivedusermessage',
    'zerver_archivedattachment',
    'zerver_archivedattachment_messages',

    # Social auth tables are not needed post-export, since we don't
    # use any of this state outside of a direct authentication flow.
    'social_auth_association',
    'social_auth_code',
    'social_auth_nonce',
    'social_auth_partial',
    'social_auth_usersocialauth',

    # We will likely never want to migrate this table, since it's a
    # total of all the realmcount values on the server.  Might need to
    # recompute it after a fillstate import.
    'analytics_installationcount',

    # Fillstate will require some cleverness to do the right partial export.
    'analytics_fillstate',

    # These are for unfinished features; we'll want to add them ot the
    # export before they reach full production status.
    'zerver_defaultstreamgroup',
    'zerver_defaultstreamgroup_streams',
    'zerver_submessage',

    # This is low priority, since users can easily just reset themselves to away.
    'zerver_userstatus',

    # For any tables listed below here, it's a bug that they are not present in the export.
}

IMPLICIT_TABLES = {
    # ManyToMany relationships are exported implicitly when importing
    # the parent table.
    'zerver_attachment_messages',
}

ATTACHMENT_TABLES = {
    'zerver_attachment',
}

MESSAGE_TABLES = {
    # message tables get special treatment, because they're by far our
    # largest tables and need to be paginated.
    'zerver_message',
    'zerver_usermessage',
    # zerver_reaction belongs here, since it's added late because it
    # has a foreign key into the Message table.
    'zerver_reaction',
}

# These get their own file as analytics data can be quite large and
# would otherwise make realm.json unpleasant to manually inspect
ANALYTICS_TABLES = {
    'analytics_realmcount',
    'analytics_streamcount',
    'analytics_usercount',
}

# This data structure lists all the Django DateTimeField fields in the
# data model.  These are converted to floats during the export process
# via floatify_datetime_fields, and back during the import process.
#
# TODO: This data structure could likely eventually be replaced by
# inspecting the corresponding Django models
DATE_FIELDS = {
    'zerver_attachment': ['create_time'],
    'zerver_message': ['last_edit_time', 'pub_date'],
    'zerver_realm': ['date_created'],
    'zerver_stream': ['date_created'],
    'zerver_useractivity': ['last_visit'],
    'zerver_useractivityinterval': ['start', 'end'],
    'zerver_userpresence': ['timestamp'],
    'zerver_userprofile': ['date_joined', 'last_login', 'last_reminder'],
    'zerver_realmauditlog': ['event_time'],
    'zerver_userhotspot': ['timestamp'],
    'analytics_installationcount': ['end_time'],
    'analytics_realmcount': ['end_time'],
    'analytics_usercount': ['end_time'],
    'analytics_streamcount': ['end_time'],
}  # type: Dict[TableName, List[Field]]

def sanity_check_output(data: TableData) -> None:
    # First, we verify that the export tool has a declared
    # configuration for every table declared in the `models.py` files.
    target_models = (
        list(apps.get_app_config('analytics').get_models(include_auto_created=True)) +
        list(apps.get_app_config('django_otp').get_models(include_auto_created=True)) +
        list(apps.get_app_config('otp_static').get_models(include_auto_created=True)) +
        list(apps.get_app_config('otp_totp').get_models(include_auto_created=True)) +
        list(apps.get_app_config('social_django').get_models(include_auto_created=True)) +
        list(apps.get_app_config('two_factor').get_models(include_auto_created=True)) +
        list(apps.get_app_config('zerver').get_models(include_auto_created=True))
    )
    all_tables_db = set(model._meta.db_table for model in target_models)

    # These assertion statements will fire when we add a new database
    # table that is not included in Zulip's data exports.  Generally,
    # you can add your new table to `ALL_ZULIP_TABLES` and
    # `NON_EXPORTED_TABLES` during early work on a new feature so that
    # CI passes.
    #
    # We'll want to make sure we handle it for exports before
    # releasing the new feature, but doing so correctly requires some
    # expertise on this export system.
    assert ALL_ZULIP_TABLES == all_tables_db
    assert NON_EXPORTED_TABLES.issubset(ALL_ZULIP_TABLES)
    assert IMPLICIT_TABLES.issubset(ALL_ZULIP_TABLES)
    assert ATTACHMENT_TABLES.issubset(ALL_ZULIP_TABLES)
    assert ANALYTICS_TABLES.issubset(ALL_ZULIP_TABLES)

    tables = set(ALL_ZULIP_TABLES)
    tables -= NON_EXPORTED_TABLES
    tables -= IMPLICIT_TABLES
    tables -= MESSAGE_TABLES
    tables -= ATTACHMENT_TABLES
    tables -= ANALYTICS_TABLES

    for table in tables:
        if table not in data:
            logging.warning('??? NO DATA EXPORTED FOR TABLE %s!!!' % (table,))

def write_data_to_file(output_file: Path, data: Any) -> None:
    with open(output_file, "w") as f:
        f.write(ujson.dumps(data, indent=4))

def make_raw(query: Any, exclude: Optional[List[Field]]=None) -> List[Record]:
    '''
    Takes a Django query and returns a JSONable list
    of dictionaries corresponding to the database rows.
    '''
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
            value = data[field.name]
            data[field.name] = [row.id for row in value]

        rows.append(data)

    return rows

def floatify_datetime_fields(data: TableData, table: TableName) -> None:
    for item in data[table]:
        for field in DATE_FIELDS[table]:
            orig_dt = item[field]
            if orig_dt is None:
                continue
            if timezone_is_naive(orig_dt):
                logging.warning("Naive datetime:", item)
                dt = timezone_make_aware(orig_dt)
            else:
                dt = orig_dt
            utc_naive  = dt.replace(tzinfo=None) - dt.utcoffset()
            item[field] = (utc_naive - datetime.datetime(1970, 1, 1)).total_seconds()

class Config:
    '''A Config object configures a single table for exporting (and, maybe
    some day importing as well.  This configuration defines what
    process needs to be followed to correctly extract the set of
    objects to export.

    You should never mutate Config objects as part of the export;
    instead use the data to determine how you populate other
    data structures.

    There are parent/children relationships between Config objects.
    The parent should be instantiated first.  The child will
    append itself to the parent's list of children.

    '''

    def __init__(self, table: Optional[str]=None,
                 model: Optional[Any]=None,
                 normal_parent: Optional['Config']=None,
                 virtual_parent: Optional['Config']=None,
                 filter_args: Optional[FilterArgs]=None,
                 custom_fetch: Optional[CustomFetch]=None,
                 custom_tables: Optional[List[TableName]]=None,
                 post_process_data: Optional[PostProcessData]=None,
                 concat_and_destroy: Optional[List[TableName]]=None,
                 id_source: Optional[IdSource]=None,
                 source_filter: Optional[SourceFilter]=None,
                 parent_key: Optional[Field]=None,
                 use_all: bool=False,
                 is_seeded: bool=False,
                 exclude: Optional[List[Field]]=None) -> None:
        assert table or custom_tables
        self.table = table
        self.model = model
        self.normal_parent = normal_parent
        self.virtual_parent = virtual_parent
        self.filter_args = filter_args
        self.parent_key = parent_key
        self.use_all = use_all
        self.is_seeded = is_seeded
        self.exclude = exclude
        self.custom_fetch = custom_fetch
        self.custom_tables = custom_tables
        self.post_process_data = post_process_data
        self.concat_and_destroy = concat_and_destroy
        self.id_source = id_source
        self.source_filter = source_filter
        self.children = []  # type: List[Config]

        if normal_parent is not None:
            self.parent = normal_parent  # type: Optional[Config]
        else:
            self.parent = None

        if virtual_parent is not None and normal_parent is not None:
            raise AssertionError('''
                If you specify a normal_parent, please
                do not create a virtual_parent.
                ''')

        if normal_parent is not None:
            normal_parent.children.append(self)
        elif virtual_parent is not None:
            virtual_parent.children.append(self)
        elif is_seeded is None:
            raise AssertionError('''
                You must specify a parent if you are
                not using is_seeded.
                ''')

        if self.id_source is not None:
            if self.virtual_parent is None:
                raise AssertionError('''
                    You must specify a virtual_parent if you are
                    using id_source.''')
            if self.id_source[0] != self.virtual_parent.table:
                raise AssertionError('''
                    Configuration error.  To populate %s, you
                    want data from %s, but that differs from
                    the table name of your virtual parent (%s),
                    which suggests you many not have set up
                    the ordering correctly.  You may simply
                    need to assign a virtual_parent, or there
                    may be deeper issues going on.''' % (
                    self.table,
                    self.id_source[0],
                    self.virtual_parent.table))


def export_from_config(response: TableData, config: Config, seed_object: Optional[Any]=None,
                       context: Optional[Context]=None) -> None:
    table = config.table
    parent = config.parent
    model = config.model

    if context is None:
        context = {}

    if table:
        exported_tables = [table]
    else:
        if config.custom_tables is None:
            raise AssertionError('''
                You must specify config.custom_tables if you
                are not specifying config.table''')
        exported_tables = config.custom_tables

    for t in exported_tables:
        logging.info('Exporting via export_from_config:  %s' % (t,))

    rows = None
    if config.is_seeded:
        rows = [seed_object]

    elif config.custom_fetch:
        config.custom_fetch(
            response=response,
            config=config,
            context=context
        )
        if config.custom_tables:
            for t in config.custom_tables:
                if t not in response:
                    raise AssertionError('Custom fetch failed to populate %s' % (t,))

    elif config.concat_and_destroy:
        # When we concat_and_destroy, we are working with
        # temporary "tables" that are lists of records that
        # should already be ready to export.
        data = []  # type: List[Record]
        for t in config.concat_and_destroy:
            data += response[t]
            del response[t]
            logging.info('Deleted temporary %s' % (t,))
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
        assert config.parent_key is not None
        parent_ids = [r['id'] for r in response[parent.table]]
        filter_parms = {config.parent_key: parent_ids}  # type: Dict[str, Any]
        if config.filter_args is not None:
            filter_parms.update(config.filter_args)
        assert model is not None
        query = model.objects.filter(**filter_parms)
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
        filter_parms = dict(id__in=lookup_ids)
        if config.filter_args:
            filter_parms.update(config.filter_args)
        query = model.objects.filter(**filter_parms)
        rows = list(query)

    # Post-process rows (which won't apply to custom fetches/concats)
    if rows is not None:
        assert table is not None  # Hint for mypy
        response[table] = make_raw(rows, exclude=config.exclude)
        if table in DATE_FIELDS:
            floatify_datetime_fields(response, table)

    if config.post_process_data:
        config.post_process_data(
            response=response,
            config=config,
            context=context
        )

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
        table='zerver_realm',
        is_seeded=True
    )

    Config(
        table='zerver_defaultstream',
        model=DefaultStream,
        normal_parent=realm_config,
        parent_key='realm_id__in',
    )

    Config(
        table='zerver_customprofilefield',
        model=CustomProfileField,
        normal_parent=realm_config,
        parent_key='realm_id__in',
    )

    Config(
        table='zerver_realmemoji',
        model=RealmEmoji,
        normal_parent=realm_config,
        parent_key='realm_id__in',
    )

    Config(
        table='zerver_realmdomain',
        model=RealmDomain,
        normal_parent=realm_config,
        parent_key='realm_id__in',
    )

    Config(
        table='zerver_realmfilter',
        model=RealmFilter,
        normal_parent=realm_config,
        parent_key='realm_id__in',
    )

    Config(
        table='zerver_client',
        model=Client,
        virtual_parent=realm_config,
        use_all=True
    )

    user_profile_config = Config(
        custom_tables=[
            'zerver_userprofile',
            'zerver_userprofile_mirrordummy',
        ],
        # set table for children who treat us as normal parent
        table='zerver_userprofile',
        virtual_parent=realm_config,
        custom_fetch=fetch_user_profile,
    )

    user_groups_config = Config(
        table='zerver_usergroup',
        model=UserGroup,
        normal_parent=realm_config,
        parent_key='realm__in',
    )

    Config(
        table='zerver_usergroupmembership',
        model=UserGroupMembership,
        normal_parent=user_groups_config,
        parent_key='user_group__in',
    )

    Config(
        custom_tables=[
            'zerver_userprofile_crossrealm',
        ],
        virtual_parent=user_profile_config,
        custom_fetch=fetch_user_profile_cross_realm,
    )

    Config(
        table='zerver_userpresence',
        model=UserPresence,
        normal_parent=user_profile_config,
        parent_key='user_profile__in',
    )

    Config(
        table='zerver_customprofilefieldvalue',
        model=CustomProfileFieldValue,
        normal_parent=user_profile_config,
        parent_key='user_profile__in',
    )

    Config(
        table='zerver_useractivity',
        model=UserActivity,
        normal_parent=user_profile_config,
        parent_key='user_profile__in',
    )

    Config(
        table='zerver_useractivityinterval',
        model=UserActivityInterval,
        normal_parent=user_profile_config,
        parent_key='user_profile__in',
    )

    Config(
        table='zerver_realmauditlog',
        model=RealmAuditLog,
        normal_parent=user_profile_config,
        parent_key='modified_user__in',
    )

    Config(
        table='zerver_userhotspot',
        model=UserHotspot,
        normal_parent=user_profile_config,
        parent_key='user__in',
    )

    Config(
        table='zerver_mutedtopic',
        model=MutedTopic,
        normal_parent=user_profile_config,
        parent_key='user_profile__in',
    )

    Config(
        table='zerver_service',
        model=Service,
        normal_parent=user_profile_config,
        parent_key='user_profile__in',
    )

    Config(
        table='zerver_botstoragedata',
        model=BotStorageData,
        normal_parent=user_profile_config,
        parent_key='bot_profile__in',
    )

    Config(
        table='zerver_botconfigdata',
        model=BotConfigData,
        normal_parent=user_profile_config,
        parent_key='bot_profile__in',
    )

    # Some of these tables are intermediate "tables" that we
    # create only for the export.  Think of them as similar to views.

    user_subscription_config = Config(
        table='_user_subscription',
        model=Subscription,
        normal_parent=user_profile_config,
        filter_args={'recipient__type': Recipient.PERSONAL},
        parent_key='user_profile__in',
    )

    Config(
        table='_user_recipient',
        model=Recipient,
        virtual_parent=user_subscription_config,
        id_source=('_user_subscription', 'recipient'),
    )

    #
    stream_subscription_config = Config(
        table='_stream_subscription',
        model=Subscription,
        normal_parent=user_profile_config,
        filter_args={'recipient__type': Recipient.STREAM},
        parent_key='user_profile__in',
    )

    stream_recipient_config = Config(
        table='_stream_recipient',
        model=Recipient,
        virtual_parent=stream_subscription_config,
        id_source=('_stream_subscription', 'recipient'),
    )

    Config(
        table='zerver_stream',
        model=Stream,
        virtual_parent=stream_recipient_config,
        id_source=('_stream_recipient', 'type_id'),
        source_filter=lambda r: r['type'] == Recipient.STREAM,
        exclude=['email_token'],
        post_process_data=sanity_check_stream_data
    )

    #

    Config(
        custom_tables=[
            '_huddle_recipient',
            '_huddle_subscription',
            'zerver_huddle',
        ],
        normal_parent=user_profile_config,
        custom_fetch=fetch_huddle_objects,
    )

    # Now build permanent tables from our temp tables.
    Config(
        table='zerver_recipient',
        virtual_parent=user_profile_config,
        concat_and_destroy=[
            '_user_recipient',
            '_stream_recipient',
            '_huddle_recipient',
        ],
    )

    Config(
        table='zerver_subscription',
        virtual_parent=user_profile_config,
        concat_and_destroy=[
            '_user_subscription',
            '_stream_subscription',
            '_huddle_subscription',
        ]
    )

    return realm_config

def sanity_check_stream_data(response: TableData, config: Config, context: Context) -> None:

    if context['exportable_user_ids'] is not None:
        # If we restrict which user ids are exportable,
        # the way that we find # streams is a little too
        # complex to have a sanity check.
        return

    actual_streams = set([stream.name for stream in Stream.objects.filter(
        realm=response["zerver_realm"][0]['id'])])
    streams_in_response = set([stream['name'] for stream in response['zerver_stream']])

    if len(streams_in_response - actual_streams) > 0:
        print("Error: Streams not present in the realm were exported:")
        print("   ", streams_in_response - actual_streams)
        print("This is likely due to a bug in the export tool.")
        raise AssertionError("Aborting!  Please investigate.")
    if len(actual_streams - streams_in_response) > 0:
        print("Error: Some streams present in the realm were not exported:")
        print("    ", actual_streams - streams_in_response)
        print("Usually, this is caused by a stream having been created that never had subscribers.")
        print("(Due to a bug elsewhere in Zulip, not in the export tool)")
        raise AssertionError("Aborting!  Please investigate.")

def fetch_user_profile(response: TableData, config: Config, context: Context) -> None:
    realm = context['realm']
    exportable_user_ids = context['exportable_user_ids']

    query = UserProfile.objects.filter(realm_id=realm.id)
    exclude = ['password', 'api_key']
    rows = make_raw(list(query), exclude=exclude)

    normal_rows = []  # type: List[Record]
    dummy_rows = []  # type: List[Record]

    for row in rows:
        if exportable_user_ids is not None:
            if row['id'] in exportable_user_ids:
                assert not row['is_mirror_dummy']
            else:
                # Convert non-exportable users to
                # inactive is_mirror_dummy users.
                row['is_mirror_dummy'] = True
                row['is_active'] = False

        if row['is_mirror_dummy']:
            dummy_rows.append(row)
        else:
            normal_rows.append(row)

    response['zerver_userprofile'] = normal_rows
    response['zerver_userprofile_mirrordummy'] = dummy_rows

def fetch_user_profile_cross_realm(response: TableData, config: Config, context: Context) -> None:
    realm = context['realm']
    response['zerver_userprofile_crossrealm'] = []

    if realm.string_id == settings.SYSTEM_BOT_REALM:
        return

    for bot_user in [
            get_system_bot(settings.NOTIFICATION_BOT),
            get_system_bot(settings.EMAIL_GATEWAY_BOT),
            get_system_bot(settings.WELCOME_BOT),
    ]:
        recipient_id = Recipient.objects.get(type_id=bot_user.id, type=Recipient.PERSONAL).id
        response['zerver_userprofile_crossrealm'].append(dict(
            email=bot_user.email,
            id=bot_user.id,
            recipient_id=recipient_id,
        ))

def fetch_attachment_data(response: TableData, realm_id: int, message_ids: Set[int]) -> None:
    filter_args = {'realm_id': realm_id}
    query = Attachment.objects.filter(**filter_args)
    response['zerver_attachment'] = make_raw(list(query))
    floatify_datetime_fields(response, 'zerver_attachment')

    '''
    We usually export most messages for the realm, but not
    quite ALL messages for the realm.  So, we need to
    clean up our attachment data to have correct
    values for response['zerver_attachment'][<n>]['messages'].
    '''
    for row in response['zerver_attachment']:
        filterer_message_ids = set(row['messages']).intersection(message_ids)
        row['messages'] = sorted(list(filterer_message_ids))

    '''
    Attachments can be connected to multiple messages, although
    it's most common to have just one message. Regardless,
    if none of those message(s) survived the filtering above
    for a particular attachment, then we won't export the
    attachment row.
    '''
    response['zerver_attachment'] = [
        row for row in response['zerver_attachment']
        if row['messages']]

def fetch_reaction_data(response: TableData, message_ids: Set[int]) -> None:
    query = Reaction.objects.filter(message_id__in=list(message_ids))
    response['zerver_reaction'] = make_raw(list(query))

def fetch_huddle_objects(response: TableData, config: Config, context: Context) -> None:

    realm = context['realm']
    assert config.parent is not None
    assert config.parent.table is not None
    user_profile_ids = set(r['id'] for r in response[config.parent.table])

    # First we get all huddles involving someone in the realm.
    realm_huddle_subs = Subscription.objects.select_related("recipient").filter(
        recipient__type=Recipient.HUDDLE, user_profile__in=user_profile_ids)
    realm_huddle_recipient_ids = set(sub.recipient_id for sub in realm_huddle_subs)

    # Mark all Huddles whose recipient ID contains a cross-realm user.
    unsafe_huddle_recipient_ids = set()
    for sub in Subscription.objects.select_related().filter(recipient__in=realm_huddle_recipient_ids):
        if sub.user_profile.realm != realm:
            # In almost every case the other realm will be zulip.com
            unsafe_huddle_recipient_ids.add(sub.recipient_id)

    # Now filter down to just those huddles that are entirely within the realm.
    #
    # This is important for ensuring that the User objects needed
    # to import it on the other end exist (since we're only
    # exporting the users from this realm), at the cost of losing
    # some of these cross-realm messages.
    huddle_subs = [sub for sub in realm_huddle_subs if sub.recipient_id not in unsafe_huddle_recipient_ids]
    huddle_recipient_ids = set(sub.recipient_id for sub in huddle_subs)
    huddle_ids = set(sub.recipient.type_id for sub in huddle_subs)

    huddle_subscription_dicts = make_raw(huddle_subs)
    huddle_recipients = make_raw(Recipient.objects.filter(id__in=huddle_recipient_ids))

    response['_huddle_recipient'] = huddle_recipients
    response['_huddle_subscription'] = huddle_subscription_dicts
    response['zerver_huddle'] = make_raw(Huddle.objects.filter(id__in=huddle_ids))

def fetch_usermessages(realm: Realm,
                       message_ids: Set[int],
                       user_profile_ids: Set[int],
                       message_filename: Path) -> List[Record]:
    # UserMessage export security rule: You can export UserMessages
    # for the messages you exported for the users in your realm.
    user_message_query = UserMessage.objects.filter(user_profile__realm=realm,
                                                    message_id__in=message_ids)
    user_message_chunk = []
    for user_message in user_message_query:
        if user_message.user_profile_id not in user_profile_ids:
            continue
        user_message_obj = model_to_dict(user_message)
        user_message_obj['flags_mask'] = user_message.flags.mask
        del user_message_obj['flags']
        user_message_chunk.append(user_message_obj)
    logging.info("Fetched UserMessages for %s" % (message_filename,))
    return user_message_chunk

def export_usermessages_batch(input_path: Path, output_path: Path) -> None:
    """As part of the system for doing parallel exports, this runs on one
    batch of Message objects and adds the corresponding UserMessage
    objects. (This is called by the export_usermessage_batch
    management command)."""
    with open(input_path, "r") as input_file:
        output = ujson.loads(input_file.read())
    message_ids = [item['id'] for item in output['zerver_message']]
    user_profile_ids = set(output['zerver_userprofile_ids'])
    del output['zerver_userprofile_ids']
    realm = Realm.objects.get(id=output['realm_id'])
    del output['realm_id']
    output['zerver_usermessage'] = fetch_usermessages(realm, set(message_ids), user_profile_ids, output_path)
    write_message_export(output_path, output)
    os.unlink(input_path)

def write_message_export(message_filename: Path, output: MessageOutput) -> None:
    write_data_to_file(output_file=message_filename, data=output)
    logging.info("Dumped to %s" % (message_filename,))

def export_partial_message_files(realm: Realm,
                                 response: TableData,
                                 chunk_size: int=MESSAGE_BATCH_CHUNK_SIZE,
                                 output_dir: Optional[Path]=None,
                                 public_only: bool=False) -> Set[int]:
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="zulip-export")

    def get_ids(records: List[Record]) -> Set[int]:
        return set(x['id'] for x in records)

    # Basic security rule: You can export everything either...
    #   - sent by someone in your exportable_user_ids
    #        OR
    #   - received by someone in your exportable_user_ids (which
    #     equates to a recipient object we are exporting)
    #
    # TODO: In theory, you should be able to export messages in
    # cross-realm PM threads; currently, this only exports cross-realm
    # messages received by your realm that were sent by Zulip system
    # bots (e.g. emailgateway, notification-bot).

    # Here, "we" and "us" refers to the inner circle of users who
    # were specified as being allowed to be exported.  "Them"
    # refers to other users.
    user_ids_for_us = get_ids(
        response['zerver_userprofile']
    )
    ids_of_our_possible_senders = get_ids(
        response['zerver_userprofile'] +
        response['zerver_userprofile_mirrordummy'] +
        response['zerver_userprofile_crossrealm'])

    if public_only:
        recipient_streams = Stream.objects.filter(realm=realm, invite_only=False)
        recipient_ids = Recipient.objects.filter(
            type=Recipient.STREAM, type_id__in=recipient_streams).values_list("id", flat=True)
        recipient_ids_for_us = get_ids(response['zerver_recipient']) & set(recipient_ids)
    else:
        recipient_ids_for_us = get_ids(response['zerver_recipient'])

    # We capture most messages here, since the
    # recipients we subscribe to are also the
    # recipients of most messages we send.
    messages_we_received = Message.objects.filter(
        sender__in=ids_of_our_possible_senders,
        recipient__in=recipient_ids_for_us,
    ).order_by('id')

    if public_only:
        # For the public stream export, we only need the messages those streams received.
        message_queries = [
            messages_we_received,
        ]
    else:
        # This should pick up stragglers; messages we sent
        # where we the recipient wasn't subscribed to by any of
        # us (such as PMs to "them").
        ids_of_non_exported_possible_recipients = ids_of_our_possible_senders - user_ids_for_us

        recipients_for_them = Recipient.objects.filter(
            type=Recipient.PERSONAL,
            type_id__in=ids_of_non_exported_possible_recipients).values("id")
        recipient_ids_for_them = get_ids(recipients_for_them)

        messages_we_sent_to_them = Message.objects.filter(
            sender__in=user_ids_for_us,
            recipient__in=recipient_ids_for_them,
        ).order_by('id')

        message_queries = [
            messages_we_received,
            messages_we_sent_to_them,
        ]

    all_message_ids = set()  # type: Set[int]
    dump_file_id = 1

    for message_query in message_queries:
        dump_file_id = write_message_partial_for_query(
            realm=realm,
            message_query=message_query,
            dump_file_id=dump_file_id,
            all_message_ids=all_message_ids,
            output_dir=output_dir,
            user_profile_ids=user_ids_for_us,
            chunk_size=chunk_size,
        )

    return all_message_ids

def write_message_partial_for_query(realm: Realm, message_query: Any, dump_file_id: int,
                                    all_message_ids: Set[int], output_dir: Path,
                                    user_profile_ids: Set[int],
                                    chunk_size: int=MESSAGE_BATCH_CHUNK_SIZE) -> int:
    min_id = -1

    while True:
        actual_query = message_query.filter(id__gt=min_id)[0:chunk_size]
        message_chunk = make_raw(actual_query)
        message_ids = set(m['id'] for m in message_chunk)
        assert len(message_ids.intersection(all_message_ids)) == 0

        all_message_ids.update(message_ids)

        if len(message_chunk) == 0:
            break

        # Figure out the name of our shard file.
        message_filename = os.path.join(output_dir, "messages-%06d.json" % (dump_file_id,))
        message_filename += '.partial'
        logging.info("Fetched Messages for %s" % (message_filename,))

        # Clean up our messages.
        table_data = {}  # type: TableData
        table_data['zerver_message'] = message_chunk
        floatify_datetime_fields(table_data, 'zerver_message')

        # Build up our output for the .partial file, which needs
        # a list of user_profile_ids to search for (as well as
        # the realm id).
        output = {}  # type: MessageOutput
        output['zerver_message'] = table_data['zerver_message']
        output['zerver_userprofile_ids'] = list(user_profile_ids)
        output['realm_id'] = realm.id

        # And write the data.
        write_message_export(message_filename, output)
        min_id = max(message_ids)
        dump_file_id += 1

    return dump_file_id

def export_uploads_and_avatars(realm: Realm, output_dir: Path) -> None:
    uploads_output_dir = os.path.join(output_dir, 'uploads')
    avatars_output_dir = os.path.join(output_dir, 'avatars')
    emoji_output_dir = os.path.join(output_dir, 'emoji')

    for output_dir in (uploads_output_dir, avatars_output_dir, emoji_output_dir):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    if settings.LOCAL_UPLOADS_DIR:
        # Small installations and developers will usually just store files locally.
        export_uploads_from_local(realm,
                                  local_dir=os.path.join(settings.LOCAL_UPLOADS_DIR, "files"),
                                  output_dir=uploads_output_dir)
        export_avatars_from_local(realm,
                                  local_dir=os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars"),
                                  output_dir=avatars_output_dir)
        export_emoji_from_local(realm,
                                local_dir=os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars"),
                                output_dir=emoji_output_dir)
    else:
        # Some bigger installations will have their data stored on S3.
        export_files_from_s3(realm,
                             settings.S3_AVATAR_BUCKET,
                             output_dir=avatars_output_dir,
                             processing_avatars=True)
        export_files_from_s3(realm,
                             settings.S3_AUTH_UPLOADS_BUCKET,
                             output_dir=uploads_output_dir)
        export_files_from_s3(realm,
                             settings.S3_AVATAR_BUCKET,
                             output_dir=emoji_output_dir,
                             processing_emoji=True)

def _check_key_metadata(email_gateway_bot: Optional[UserProfile],
                        key: Key, processing_avatars: bool,
                        realm: Realm, user_ids: Set[int]) -> None:
    # Helper function for export_files_from_s3
    if 'realm_id' in key.metadata and key.metadata['realm_id'] != str(realm.id):
        if email_gateway_bot is None or key.metadata['user_profile_id'] != str(email_gateway_bot.id):
            raise AssertionError("Key metadata problem: %s %s / %s" % (key.name, key.metadata, realm.id))
        # Email gateway bot sends messages, potentially including attachments, cross-realm.
        print("File uploaded by email gateway bot: %s / %s" % (key.name, key.metadata))
    elif processing_avatars:
        if 'user_profile_id' not in key.metadata:
            raise AssertionError("Missing user_profile_id in key metadata: %s" % (key.metadata,))
        if int(key.metadata['user_profile_id']) not in user_ids:
            raise AssertionError("Wrong user_profile_id in key metadata: %s" % (key.metadata,))
    elif 'realm_id' not in key.metadata:
        raise AssertionError("Missing realm_id in key metadata: %s" % (key.metadata,))

def _get_exported_s3_record(
        bucket_name: str,
        key: Key,
        processing_avatars: bool,
        processing_emoji: bool) -> Dict[str, Union[str, int]]:
    # Helper function for export_files_from_s3
    record = dict(s3_path=key.name, bucket=bucket_name,
                  size=key.size, last_modified=key.last_modified,
                  content_type=key.content_type, md5=key.md5)
    record.update(key.metadata)

    if processing_emoji:
        record['file_name'] = os.path.basename(key.name)

    # A few early avatars don't have 'realm_id' on the object; fix their metadata
    user_profile = get_user_profile_by_id(record['user_profile_id'])
    if 'realm_id' not in record:
        record['realm_id'] = user_profile.realm_id
    record['user_profile_email'] = user_profile.email

    # Fix the record ids
    record['user_profile_id'] = int(record['user_profile_id'])
    record['realm_id'] = int(record['realm_id'])

    return record

def _save_s3_object_to_file(
        key: Key,
        output_dir: str,
        processing_avatars: bool,
        processing_emoji: bool) -> None:

    # Helper function for export_files_from_s3
    if processing_avatars or processing_emoji:
        filename = os.path.join(output_dir, key.name)
    else:
        fields = key.name.split('/')
        if len(fields) != 3:
            raise AssertionError("Suspicious key with invalid format %s" % (key.name))
        filename = os.path.join(output_dir, key.name)

    dirname = os.path.dirname(filename)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    key.get_contents_to_filename(filename)

def export_files_from_s3(realm: Realm, bucket_name: str, output_dir: Path,
                         processing_avatars: bool=False,
                         processing_emoji: bool=False) -> None:
    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    bucket = conn.get_bucket(bucket_name, validate=True)
    records = []

    logging.info("Downloading uploaded files from %s" % (bucket_name))

    avatar_hash_values = set()
    user_ids = set()
    if processing_avatars:
        bucket_list = bucket.list()
        for user_profile in UserProfile.objects.filter(realm=realm):
            avatar_path = user_avatar_path_from_ids(user_profile.id, realm.id)
            avatar_hash_values.add(avatar_path)
            avatar_hash_values.add(avatar_path + ".original")
            user_ids.add(user_profile.id)
    if processing_emoji:
        bucket_list = bucket.list(prefix="%s/emoji/images/" % (realm.id,))
    else:
        bucket_list = bucket.list(prefix="%s/" % (realm.id,))

    if settings.EMAIL_GATEWAY_BOT is not None:
        email_gateway_bot = get_system_bot(settings.EMAIL_GATEWAY_BOT)  # type: Optional[UserProfile]
    else:
        email_gateway_bot = None

    count = 0
    for bkey in bucket_list:
        if processing_avatars and bkey.name not in avatar_hash_values:
            continue
        key = bucket.get_key(bkey.name)

        # This can happen if an email address has moved realms
        _check_key_metadata(email_gateway_bot, key, processing_avatars, realm, user_ids)
        record = _get_exported_s3_record(bucket_name, key, processing_avatars, processing_emoji)

        record['path'] = key.name
        _save_s3_object_to_file(key, output_dir, processing_avatars, processing_emoji)

        records.append(record)
        count += 1

        if (count % 100 == 0):
            logging.info("Finished %s" % (count,))

    with open(os.path.join(output_dir, "records.json"), "w") as records_file:
        ujson.dump(records, records_file, indent=4)

def export_uploads_from_local(realm: Realm, local_dir: Path, output_dir: Path) -> None:

    count = 0
    records = []
    for attachment in Attachment.objects.filter(realm_id=realm.id):
        local_path = os.path.join(local_dir, attachment.path_id)
        output_path = os.path.join(output_dir, attachment.path_id)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy2(local_path, output_path)
        stat = os.stat(local_path)
        record = dict(realm_id=attachment.realm_id,
                      user_profile_id=attachment.owner.id,
                      user_profile_email=attachment.owner.email,
                      s3_path=attachment.path_id,
                      path=attachment.path_id,
                      size=stat.st_size,
                      last_modified=stat.st_mtime,
                      content_type=None)
        records.append(record)

        count += 1

        if (count % 100 == 0):
            logging.info("Finished %s" % (count,))
    with open(os.path.join(output_dir, "records.json"), "w") as records_file:
        ujson.dump(records, records_file, indent=4)

def export_avatars_from_local(realm: Realm, local_dir: Path, output_dir: Path) -> None:

    count = 0
    records = []

    users = list(UserProfile.objects.filter(realm=realm))
    users += [
        get_system_bot(settings.NOTIFICATION_BOT),
        get_system_bot(settings.EMAIL_GATEWAY_BOT),
        get_system_bot(settings.WELCOME_BOT),
    ]
    for user in users:
        if user.avatar_source == UserProfile.AVATAR_FROM_GRAVATAR:
            continue

        avatar_path = user_avatar_path_from_ids(user.id, realm.id)
        wildcard = os.path.join(local_dir, avatar_path + '.*')

        for local_path in glob.glob(wildcard):
            logging.info('Copying avatar file for user %s from %s' % (
                user.email, local_path))
            fn = os.path.relpath(local_path, local_dir)
            output_path = os.path.join(output_dir, fn)
            os.makedirs(str(os.path.dirname(output_path)), exist_ok=True)
            shutil.copy2(str(local_path), str(output_path))
            stat = os.stat(local_path)
            record = dict(realm_id=realm.id,
                          user_profile_id=user.id,
                          user_profile_email=user.email,
                          s3_path=fn,
                          path=fn,
                          size=stat.st_size,
                          last_modified=stat.st_mtime,
                          content_type=None)
            records.append(record)

            count += 1

            if (count % 100 == 0):
                logging.info("Finished %s" % (count,))

    with open(os.path.join(output_dir, "records.json"), "w") as records_file:
        ujson.dump(records, records_file, indent=4)

def export_emoji_from_local(realm: Realm, local_dir: Path, output_dir: Path) -> None:

    count = 0
    records = []
    for realm_emoji in RealmEmoji.objects.filter(realm_id=realm.id):
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=realm.id,
            emoji_file_name=realm_emoji.file_name
        )
        local_path = os.path.join(local_dir, emoji_path)
        output_path = os.path.join(output_dir, emoji_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy2(local_path, output_path)
        # Realm Emoji author is optional.
        author = realm_emoji.author
        author_id = None
        if author:
            author_id = realm_emoji.author.id
        record = dict(realm_id=realm.id,
                      author=author_id,
                      path=emoji_path,
                      s3_path=emoji_path,
                      file_name=realm_emoji.file_name,
                      name=realm_emoji.name,
                      deactivated=realm_emoji.deactivated)
        records.append(record)

        count += 1
        if (count % 100 == 0):
            logging.info("Finished %s" % (count,))
    with open(os.path.join(output_dir, "records.json"), "w") as records_file:
        ujson.dump(records, records_file, indent=4)

def do_write_stats_file_for_realm_export(output_dir: Path) -> None:
    stats_file = os.path.join(output_dir, 'stats.txt')
    realm_file = os.path.join(output_dir, 'realm.json')
    attachment_file = os.path.join(output_dir, 'attachment.json')
    analytics_file = os.path.join(output_dir, 'analytics.json')
    message_files = glob.glob(os.path.join(output_dir, 'messages-*.json'))
    fns = sorted([analytics_file] + [attachment_file] + message_files + [realm_file])

    logging.info('Writing stats file: %s\n' % (stats_file,))
    with open(stats_file, 'w') as f:
        for fn in fns:
            f.write(os.path.basename(fn) + '\n')
            payload = open(fn).read()
            data = ujson.loads(payload)
            for k in sorted(data):
                f.write('%5d %s\n' % (len(data[k]), k))
            f.write('\n')

        avatar_file = os.path.join(output_dir, 'avatars/records.json')
        uploads_file = os.path.join(output_dir, 'uploads/records.json')

        for fn in [avatar_file, uploads_file]:
            f.write(fn+'\n')
            payload = open(fn).read()
            data = ujson.loads(payload)
            f.write('%5d records\n' % len(data))
            f.write('\n')

def do_export_realm(realm: Realm, output_dir: Path, threads: int,
                    exportable_user_ids: Optional[Set[int]]=None,
                    public_only: bool=False) -> None:
    response = {}  # type: TableData

    # We need at least one thread running to export
    # UserMessage rows.  The management command should
    # enforce this for us.
    if not settings.TEST_SUITE:
        assert threads >= 1

    realm_config = get_realm_config()

    create_soft_link(source=output_dir, in_progress=True)

    logging.info("Exporting data from get_realm_config()...")
    export_from_config(
        response=response,
        config=realm_config,
        seed_object=realm,
        context=dict(realm=realm, exportable_user_ids=exportable_user_ids)
    )
    logging.info('...DONE with get_realm_config() data')

    sanity_check_output(response)

    logging.info("Exporting uploaded files and avatars")
    export_uploads_and_avatars(realm, output_dir)

    # We (sort of) export zerver_message rows here.  We write
    # them to .partial files that are subsequently fleshed out
    # by parallel processes to add in zerver_usermessage data.
    # This is for performance reasons, of course.  Some installations
    # have millions of messages.
    logging.info("Exporting .partial files messages")
    message_ids = export_partial_message_files(realm, response, output_dir=output_dir,
                                               public_only=public_only)
    logging.info('%d messages were exported' % (len(message_ids)))

    # zerver_reaction
    zerver_reaction = {}  # type: TableData
    fetch_reaction_data(response=zerver_reaction, message_ids=message_ids)
    response.update(zerver_reaction)

    # Write realm data
    export_file = os.path.join(output_dir, "realm.json")
    write_data_to_file(output_file=export_file, data=response)
    logging.info('Writing realm data to %s' % (export_file,))

    # Write analytics data
    export_analytics_tables(realm=realm, output_dir=output_dir)

    # zerver_attachment
    export_attachment_table(realm=realm, output_dir=output_dir, message_ids=message_ids)

    # Start parallel jobs to export the UserMessage objects.
    launch_user_message_subprocesses(threads=threads, output_dir=output_dir)

    logging.info("Finished exporting %s" % (realm.string_id))
    create_soft_link(source=output_dir, in_progress=False)

def export_attachment_table(realm: Realm, output_dir: Path, message_ids: Set[int]) -> None:
    response = {}  # type: TableData
    fetch_attachment_data(response=response, realm_id=realm.id, message_ids=message_ids)
    output_file = os.path.join(output_dir, "attachment.json")
    logging.info('Writing attachment table data to %s' % (output_file,))
    write_data_to_file(output_file=output_file, data=response)

def create_soft_link(source: Path, in_progress: bool=True) -> None:
    is_done = not in_progress
    if settings.DEVELOPMENT:
        in_progress_link = os.path.join(settings.DEPLOY_ROOT, 'var', 'export-in-progress')
        done_link = os.path.join(settings.DEPLOY_ROOT, 'var', 'export-most-recent')
    else:
        in_progress_link = '/home/zulip/export-in-progress'
        done_link = '/home/zulip/export-most-recent'

    if in_progress:
        new_target = in_progress_link
    else:
        try:
            os.remove(in_progress_link)
        except FileNotFoundError:
            pass
        new_target = done_link

    overwrite_symlink(source, new_target)
    if is_done:
        logging.info('See %s for output files' % (new_target,))


def launch_user_message_subprocesses(threads: int, output_dir: Path) -> None:
    logging.info('Launching %d PARALLEL subprocesses to export UserMessage rows' % (threads,))

    def run_job(shard: str) -> int:
        subprocess.call([os.path.join(settings.DEPLOY_ROOT, "manage.py"),
                         'export_usermessage_batch', '--path',
                         str(output_dir), '--thread', shard])
        return 0

    for (status, job) in run_parallel(run_job,
                                      [str(x) for x in range(0, threads)],
                                      threads=threads):
        print("Shard %s finished, status %s" % (job, status))

def do_export_user(user_profile: UserProfile, output_dir: Path) -> None:
    response = {}  # type: TableData

    export_single_user(user_profile, response)
    export_file = os.path.join(output_dir, "user.json")
    write_data_to_file(output_file=export_file, data=response)
    logging.info("Exporting messages")
    export_messages_single_user(user_profile, output_dir)

def export_single_user(user_profile: UserProfile, response: TableData) -> None:

    config = get_single_user_config()
    export_from_config(
        response=response,
        config=config,
        seed_object=user_profile,
    )

def get_single_user_config() -> Config:
    # This function defines the limited configuration for what data to
    # export when exporting all data that a single Zulip user has
    # access to in an organization.

    # zerver_userprofile
    user_profile_config = Config(
        table='zerver_userprofile',
        is_seeded=True,
        exclude=['password', 'api_key'],
    )

    # zerver_subscription
    subscription_config = Config(
        table='zerver_subscription',
        model=Subscription,
        normal_parent=user_profile_config,
        parent_key='user_profile__in',
    )

    # zerver_recipient
    recipient_config = Config(
        table='zerver_recipient',
        model=Recipient,
        virtual_parent=subscription_config,
        id_source=('zerver_subscription', 'recipient'),
    )

    # zerver_stream
    Config(
        table='zerver_stream',
        model=Stream,
        virtual_parent=recipient_config,
        id_source=('zerver_recipient', 'type_id'),
        source_filter=lambda r: r['type'] == Recipient.STREAM,
        exclude=['email_token'],
    )

    return user_profile_config

def export_messages_single_user(user_profile: UserProfile, output_dir: Path,
                                chunk_size: int=MESSAGE_BATCH_CHUNK_SIZE) -> None:
    user_message_query = UserMessage.objects.filter(user_profile=user_profile).order_by("id")
    min_id = -1
    dump_file_id = 1
    while True:
        actual_query = user_message_query.select_related(
            "message", "message__sending_client").filter(id__gt=min_id)[0:chunk_size]
        user_message_chunk = [um for um in actual_query]
        user_message_ids = set(um.id for um in user_message_chunk)

        if len(user_message_chunk) == 0:
            break

        message_chunk = []
        for user_message in user_message_chunk:
            item = model_to_dict(user_message.message)
            item['flags'] = user_message.flags_list()
            item['flags_mask'] = user_message.flags.mask
            # Add a few nice, human-readable details
            item['sending_client_name'] = user_message.message.sending_client.name
            item['display_recipient'] = get_display_recipient(user_message.message.recipient)
            message_chunk.append(item)

        message_filename = os.path.join(output_dir, "messages-%06d.json" % (dump_file_id,))
        logging.info("Fetched Messages for %s" % (message_filename,))

        output = {'zerver_message': message_chunk}
        floatify_datetime_fields(output, 'zerver_message')
        message_output = dict(output)  # type: MessageOutput

        write_message_export(message_filename, message_output)
        min_id = max(user_message_ids)
        dump_file_id += 1

def export_analytics_tables(realm: Realm, output_dir: Path) -> None:
    response = {}  # type: TableData

    export_file = os.path.join(output_dir, "analytics.json")
    logging.info("Writing analytics table data to %s", (export_file))
    config = get_analytics_config()
    export_from_config(
        response=response,
        config=config,
        seed_object=realm,
    )
    write_data_to_file(output_file=export_file, data=response)

def get_analytics_config() -> Config:
    # The Config function defines what data to export for the
    # analytics.json file in a full-realm export.

    analytics_config = Config(
        table='zerver_analytics',
        is_seeded=True,
    )

    Config(
        table='analytics_realmcount',
        model=RealmCount,
        normal_parent=analytics_config,
        parent_key='realm_id__in',
    )

    Config(
        table='analytics_usercount',
        model=UserCount,
        normal_parent=analytics_config,
        parent_key='realm_id__in',
    )

    Config(
        table='analytics_streamcount',
        model=StreamCount,
        normal_parent=analytics_config,
        parent_key='realm_id__in',
    )

    return analytics_config
