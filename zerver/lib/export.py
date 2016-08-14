from __future__ import absolute_import
from __future__ import print_function
import datetime
from boto.s3.key import Key
from boto.s3.connection import S3Connection
from django.conf import settings
from django.db import connection
from django.forms.models import model_to_dict
from django.utils import timezone
import glob
import logging
import os
import ujson
import shutil
import subprocess
import tempfile
from zerver.lib.avatar import user_avatar_hash
from zerver.lib.create_user import random_api_key
from zerver.models import UserProfile, Realm, Client, Huddle, Stream, \
    UserMessage, Subscription, Message, RealmEmoji, RealmFilter, \
    RealmAlias, Recipient, DefaultStream, get_user_profile_by_id, \
    UserPresence, UserActivity, UserActivityInterval, get_user_profile_by_email, \
    get_display_recipient, Attachment
from zerver.lib.parallel import run_parallel
from zerver.lib.utils import mkdir_p
from six import text_type
from six.moves import range
from typing import Any, Dict, List, Tuple

# Custom mypy types follow:
Record = Dict[str, Any]
TableName = str
TableData = Dict[TableName, List[Record]]
Field = str
Path = text_type
Context = Dict[str, Any]

# The keys of our MessageOutput variables are normally
# List[Record], but when we write partials, we can get
# lists of integers or a single integer.
# TODO: tighten this up with a union.
MessageOutput = Dict[str, Any]

realm_tables = [("zerver_defaultstream", DefaultStream),
                ("zerver_realmemoji", RealmEmoji),
                ("zerver_realmalias", RealmAlias),
                ("zerver_realmfilter", RealmFilter)] # List[Tuple[TableName, Any]]


ALL_ZERVER_TABLES = [
    # TODO: get a linter to ensure that this list is actually complete.
    'zerver_attachment',
    'zerver_attachment_messages',
    'zerver_client',
    'zerver_defaultstream',
    'zerver_huddle',
    'zerver_message',
    'zerver_preregistrationuser',
    'zerver_preregistrationuser_streams',
    'zerver_pushdevicetoken',
    'zerver_realm',
    'zerver_realmalias',
    'zerver_realmemoji',
    'zerver_realmfilter',
    'zerver_recipient',
    'zerver_referral',
    'zerver_scheduledjob',
    'zerver_stream',
    'zerver_subscription',
    'zerver_useractivity',
    'zerver_useractivityinterval',
    'zerver_usermessage',
    'zerver_userpresence',
    'zerver_userprofile',
    'zerver_userprofile_groups',
    'zerver_userprofile_user_permissions',
]

NON_EXPORTED_TABLES = [
    # These are known to either be altogether obsolete or
    # simply inappropriate for exporting (e.g. contains transient
    # data).
    'zerver_preregistrationuser',
    'zerver_preregistrationuser_streams',
    'zerver_pushdevicetoken',
    'zerver_referral',
    'zerver_scheduledjob',
    'zerver_userprofile_groups',
    'zerver_userprofile_user_permissions',
]
assert set(NON_EXPORTED_TABLES).issubset(set(ALL_ZERVER_TABLES))

IMPLICIT_TABLES = [
    # ManyToMany relationships are exported implicitly.
    'zerver_attachment_messages',
]
assert set(IMPLICIT_TABLES).issubset(set(ALL_ZERVER_TABLES))

ATTACHMENT_TABLES = [
    'zerver_attachment',
]
assert set(ATTACHMENT_TABLES).issubset(set(ALL_ZERVER_TABLES))

MESSAGE_TABLES = [
    # message tables get special treatment, because they're so big
    'zerver_message',
    'zerver_usermessage',
]

DATE_FIELDS = {
    'zerver_attachment': ['create_time'],
    'zerver_message': ['last_edit_time', 'pub_date'],
    'zerver_realm': ['date_created'],
    'zerver_stream': ['date_created'],
    'zerver_useractivity': ['last_visit'],
    'zerver_useractivityinterval': ['start', 'end'],
    'zerver_userpresence': ['timestamp'],
    'zerver_userprofile': ['date_joined', 'last_login', 'last_reminder'],
} # type: Dict[TableName, List[Field]]

def sanity_check_output(data):
    # (TableData) -> None
    tables = set(ALL_ZERVER_TABLES)
    tables -= set(NON_EXPORTED_TABLES)
    tables -= set(IMPLICIT_TABLES)
    tables -= set(MESSAGE_TABLES)
    tables -= set(ATTACHMENT_TABLES)

    for table in tables:
        if table not in data:
            logging.warn('??? NO DATA EXPORTED FOR TABLE %s!!!' % (table,))

def write_data_to_file(output_file, data):
    # type: (Path, Any) -> None
    with open(output_file, "w") as f:
        f.write(ujson.dumps(data, indent=4))

def make_raw(query, exclude=None):
    # type: (Any, List[Field]) -> List[Record]
    '''
    Takes a Django query and returns a JSONable list
    of dictionaries corresponding to the database rows.
    '''
    return [model_to_dict(x, exclude=exclude) for x in query]

def floatify_datetime_fields(data, table):
    # type: (TableData, TableName) -> None
    for item in data[table]:
        for field in DATE_FIELDS[table]:
            orig_dt = item[field]
            if orig_dt is None:
                continue
            if timezone.is_naive(orig_dt):
                logging.warning("Naive datetime:", item)
                dt = timezone.make_aware(orig_dt)
            else:
                dt = orig_dt
            utc_naive  = dt.replace(tzinfo=None) - dt.utcoffset()
            item[field] = (utc_naive - datetime.datetime(1970, 1, 1)).total_seconds()

class Config(object):
    '''
    A Config object configures a single table for exporting (and,
    maybe some day importing as well.

    You should never mutate Config objects as part of the export;
    instead use the data to determine how you populate other
    data structures.

    There are parent/children relationships between Config objects.
    The parent should be instantiated first.  The child will
    append itself to the parent's list of children.

    '''
    def __init__(self, table=None, model=None,
                normal_parent=None, virtual_parent=None,
                filter_args=None, custom_fetch=None, custom_tables=None,
                post_process_data=None,
                concat_and_destroy=None, id_source=None, source_filter=None,
                parent_key=None, use_all=False, is_seeded=False, exclude=None):
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
        self.source_filter= source_filter
        self.children = [] # type: List[Config]

        if normal_parent:
            self.parent = normal_parent
        else:
            self.parent = None

        if virtual_parent and normal_parent:
            raise Exception('''
                If you specify a normal_parent, please
                do not create a virtual_parent.
                ''')

        if normal_parent:
            normal_parent.children.append(self)
        elif virtual_parent:
            virtual_parent.children.append(self)
        elif not is_seeded:
            raise Exception('''
                You must specify a parent if you are
                not using is_seeded.
                ''')

        if self.id_source:
            if self.id_source[0] != self.virtual_parent.table:
                raise Exception('''
                    Configuration error.  To populate %s, you
                    want data from %s, but that differs from
                    the table name of your virtual parent (%s),
                    which suggests you many not have set up
                    the ordering correctly.  You may simply
                    need to assign a virtual_parent, or there
                    may be deeper issues going on.''' % (
                        self.table,
                        self.id_source[0],
                        self.virtual_parent.table,
                    ))


def export_from_config(response, config, seed_object=None, context=None):
    table = config.table
    parent = config.parent
    model = config.model

    if context is None:
        context = {}


    if table:
        exported_tables = [table]
    else:
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
                    raise Exception('Custom fetch failed to populate %s' % (t,))

    elif config.concat_and_destroy:
        # When we concat_and_destroy, we are working with
        # temporary "tables" that are lists of records that
        # should already be ready to export.
        data = [] # type: List[Record]
        for t in config.concat_and_destroy:
            data += response[t]
            del response[t]
            logging.info('Deleted temporary %s' % (t,))
        response[table] = data

    elif config.use_all:
        query = model.objects.all()
        rows = list(query)

    elif config.normal_parent:
        # In this mode, our current model is figuratively Article,
        # and normal_parent is figuratively Blog, and
        # now we just need to get all the articles
        # contained by the blogs.
        model = config.model
        parent_ids = [r['id'] for r in response[parent.table]]
        filter_parms = {config.parent_key: parent_ids}
        if config.filter_args:
            filter_parms.update(config.filter_args)
        query = model.objects.filter(**filter_parms)
        rows = list(query)

    elif config.id_source:
        # In this mode,  we are the figurative Blog, and we now
        # need to look at the current response to get all the
        # blog ids from the Article rows we fetched previously.
        model = config.model
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

def get_realm_config():
    # type: () -> Config
    # This is common, public information about the realm that we can share
    # with all realm users.

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
        table='zerver_realmemoji',
        model=RealmEmoji,
        normal_parent=realm_config,
        parent_key='realm_id__in',
    )

    Config(
        table='zerver_realmalias',
        model=RealmAlias,
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

def sanity_check_stream_data(response, config, context):
    # type: (TableData, Config, Context) -> None

    if context['exportable_user_ids'] is not None:
        # If we restrict which user ids are exportable,
        # the way that we find # streams is a little too
        # complex to have a sanity check.
        return

    actual_streams = set([stream.name for stream in Stream.objects.filter(realm=response["zerver_realm"][0]['id'])])
    streams_in_response = set([stream['name'] for stream in response['zerver_stream']])

    if streams_in_response != actual_streams:
        print(streams_in_response - actual_streams)
        print(actual_streams - streams_in_response)
        raise Exception('''
            zerver_stream data does not match
            Stream.objects.all().

            Please investigate!
            ''')

def fetch_user_profile(response, config, context):
    # type: (TableData, Config, Context) -> None
    realm = context['realm']
    exportable_user_ids = context['exportable_user_ids']

    query = UserProfile.objects.filter(realm_id=realm.id)
    exclude=['password', 'api_key']
    rows = make_raw(list(query), exclude=exclude)

    normal_rows = [] # type: List[Record]
    dummy_rows = [] # type: List[Record]

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

def fetch_user_profile_cross_realm(response, config, context):
    # type: (TableData, Config, Context) -> None
    realm = context['realm']

    if realm.domain == "zulip.com":
        response['zerver_userprofile_crossrealm'] = []
    else:
        response['zerver_userprofile_crossrealm'] = [dict(email=x.email, id=x.id) for x in [
        get_user_profile_by_email(settings.NOTIFICATION_BOT),
        get_user_profile_by_email(settings.EMAIL_GATEWAY_BOT),
        get_user_profile_by_email(settings.WELCOME_BOT),
    ]]

def fetch_attachment_data(response, realm_id, message_ids):
    # type: (TableData, int, Set[int]) -> None
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

def fetch_huddle_objects(response, config, context):
    # type: (TableData, Config, Context) -> None

    realm = context['realm']
    user_profile_ids = set(r['id'] for r in response[config.parent.table])

    # First we get all huddles involving someone in the realm.
    realm_huddle_subs = Subscription.objects.select_related("recipient").filter(recipient__type=Recipient.HUDDLE,
                                                                                user_profile__in=user_profile_ids)
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

def fetch_usermessages(realm, message_ids, user_profile_ids, message_filename):
    # type: (Realm, Set[int], Set[int], Path) -> List[Record]
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

def export_usermessages_batch(input_path, output_path):
    # type: (Path, Path) -> None
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

def write_message_export(message_filename, output):
    # type: (Path, MessageOutput) -> None
    write_data_to_file(output_file=message_filename, data=output)
    logging.info("Dumped to %s" % (message_filename,))

def export_partial_message_files(realm, response, chunk_size=1000, output_dir=None):
    # type: (Realm, TableData, int, Path) -> Set[int]
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="zulip-export")

    def get_ids(records):
        # type: (List[Record]) -> Set[int]
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
    recipient_ids_for_us = get_ids(response['zerver_recipient'])

    ids_of_our_possible_senders = get_ids(
        response['zerver_userprofile'] +
        response['zerver_userprofile_mirrordummy'] +
        response['zerver_userprofile_crossrealm'])
    ids_of_non_exported_possible_recipients = ids_of_our_possible_senders - user_ids_for_us

    recipients_for_them = Recipient.objects.filter(
        type=Recipient.PERSONAL,
        type_id__in=ids_of_non_exported_possible_recipients).values("id")
    recipient_ids_for_them = get_ids(recipients_for_them)

    # We capture most messages here, since the
    # recipients we subscribe to are also the
    # recipients of most messages we send.
    messages_we_received = Message.objects.filter(
        sender__in=ids_of_our_possible_senders,
        recipient__in=recipient_ids_for_us,
    ).order_by('id')

    # This should pick up stragglers; messages we sent
    # where we the recipient wasn't subscribed to by any of
    # us (such as PMs to "them").
    messages_we_sent_to_them = Message.objects.filter(
        sender__in=user_ids_for_us,
        recipient__in=recipient_ids_for_them,
    ).order_by('id')

    message_queries = [
        messages_we_received,
        messages_we_sent_to_them
    ]

    all_message_ids = set() # type: Set[int]
    dump_file_id = 1

    for message_query in message_queries:
        dump_file_id = write_message_partial_for_query(
            realm=realm,
            message_query=message_query,
            dump_file_id=dump_file_id,
            all_message_ids=all_message_ids,
            output_dir=output_dir,
            chunk_size=chunk_size,
            user_profile_ids=user_ids_for_us,
        )

    return all_message_ids

def write_message_partial_for_query(realm, message_query, dump_file_id,
                                    all_message_ids, output_dir,
                                    chunk_size, user_profile_ids):
    # type: (Realm, Any, int, Set[int], Path, int, Set[int]) -> int
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
        table_data = {} # type: TableData
        table_data['zerver_message'] = message_chunk
        floatify_datetime_fields(table_data, 'zerver_message')

        # Build up our output for the .partial file, which needs
        # a list of user_profile_ids to search for (as well as
        # the realm id).
        output = {} # type: MessageOutput
        output['zerver_message'] = table_data['zerver_message']
        output['zerver_userprofile_ids'] = list(user_profile_ids)
        output['realm_id'] = realm.id

        # And write the data.
        write_message_export(message_filename, output)
        min_id = max(message_ids)
        dump_file_id += 1

    return dump_file_id

def export_uploads_and_avatars(realm, output_dir):
    # type: (Realm, Path) -> None
    uploads_output_dir = os.path.join(output_dir, 'uploads')
    avatars_output_dir = os.path.join(output_dir, 'avatars')

    for output_dir in (uploads_output_dir, avatars_output_dir):
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
    else:
        # Some bigger installations will have their data stored on S3.
        export_files_from_s3(realm,
                             settings.S3_AVATAR_BUCKET,
                             output_dir=avatars_output_dir,
                             processing_avatars=True)
        export_files_from_s3(realm,
                             settings.S3_AUTH_UPLOADS_BUCKET,
                             output_dir=uploads_output_dir)

def export_files_from_s3(realm, bucket_name, output_dir, processing_avatars=False):
    # type: (Realm, str, Path, bool) -> None
    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    bucket = conn.get_bucket(bucket_name, validate=True)
    records = []

    logging.info("Downloading uploaded files from %s" % (bucket_name))

    avatar_hash_values = set()
    user_ids = set()
    if processing_avatars:
        bucket_list = bucket.list()
        for user_profile in UserProfile.objects.filter(realm=realm):
            avatar_hash = user_avatar_hash(user_profile.email)
            avatar_hash_values.add(avatar_hash)
            avatar_hash_values.add(avatar_hash + ".original")
            user_ids.add(user_profile.id)
    else:
        bucket_list = bucket.list(prefix="%s/" % (realm.id,))

    if settings.EMAIL_GATEWAY_BOT is not None:
        email_gateway_bot = get_user_profile_by_email(settings.EMAIL_GATEWAY_BOT)
    else:
        email_gateway_bot = None

    count = 0
    for bkey in bucket_list:
        if processing_avatars and bkey.name not in avatar_hash_values:
            continue
        key = bucket.get_key(bkey.name)

        # This can happen if an email address has moved realms
        if 'realm_id' in key.metadata and key.metadata['realm_id'] != str(realm.id):
            if email_gateway_bot is None or key.metadata['user_profile_id'] != str(email_gateway_bot.id):
                raise Exception("Key metadata problem: %s %s / %s" % (key.name, key.metadata, realm.id))
            # Email gateway bot sends messages, potentially including attachments, cross-realm.
            print("File uploaded by email gateway bot: %s / %s" % (key.name, key.metadata))
        elif processing_avatars:
            if 'user_profile_id' not in key.metadata:
                raise Exception("Missing user_profile_id in key metadata: %s" % (key.metadata,))
            if int(key.metadata['user_profile_id']) not in user_ids:
                raise Exception("Wrong user_profile_id in key metadata: %s" % (key.metadata,))
        elif 'realm_id' not in key.metadata:
            raise Exception("Missing realm_id in key metadata: %s" % (key.metadata,))

        record = dict(s3_path=key.name, bucket=bucket_name,
                      size=key.size, last_modified=key.last_modified,
                      content_type=key.content_type, md5=key.md5)
        record.update(key.metadata)

        # A few early avatars don't have 'realm_id' on the object; fix their metadata
        user_profile = get_user_profile_by_id(record['user_profile_id'])
        if 'realm_id' not in record:
            record['realm_id'] = user_profile.realm_id
        record['user_profile_email'] = user_profile.email

        if processing_avatars:
            dirname = output_dir
            filename = os.path.join(dirname, key.name)
            record['path'] = key.name
        else:
            fields = key.name.split('/')
            if len(fields) != 3:
                raise Exception("Suspicious key %s" % (key.name))
            dirname = os.path.join(output_dir, fields[1])
            filename = os.path.join(dirname, fields[2])
            record['path'] = os.path.join(fields[1], fields[2])

        if not os.path.exists(dirname):
            os.makedirs(dirname)
        key.get_contents_to_filename(filename)

        records.append(record)
        count += 1

        if (count % 100 == 0):
            logging.info("Finished %s" % (count,))

    with open(os.path.join(output_dir, "records.json"), "w") as records_file:
        ujson.dump(records, records_file, indent=4)

def export_uploads_from_local(realm, local_dir, output_dir):
    # type: (Realm, Path, Path) -> None

    count = 0
    records = []
    for attachment in Attachment.objects.filter(realm_id=realm.id):
        local_path = os.path.join(local_dir, attachment.path_id)
        output_path = os.path.join(output_dir, attachment.path_id)
        mkdir_p(os.path.dirname(output_path))
        subprocess.check_call(["cp", "-a", local_path, output_path])
        stat = os.stat(local_path)
        record = dict(realm_id=attachment.realm.id,
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

def export_avatars_from_local(realm, local_dir, output_dir):
    # type: (Realm, Path, Path) -> None

    count = 0
    records = []

    users = list(UserProfile.objects.filter(realm=realm))
    users += [
        get_user_profile_by_email(settings.NOTIFICATION_BOT),
        get_user_profile_by_email(settings.EMAIL_GATEWAY_BOT),
        get_user_profile_by_email(settings.WELCOME_BOT),
    ]
    for user in users:
        if user.avatar_source == UserProfile.AVATAR_FROM_GRAVATAR:
            continue
        # NOTE: There is an avatar source called AVATAR_FROM_SYSTEM,
        #       but I'm not sure we support it any more.  If we
        #       have system-generated avatars, then arguably we
        #       don't need to export them, but it's probably
        #       expedient to just copy them over.  The more
        #       common case is AVATAR_FROM_USER, which is handled
        #       here as well.  AVATAR_FROM_GRAVATAR refers to
        #       avatars hosted by gravatar.com, and for them,
        #       we have no files to worry about exporting

        avatar_hash = user_avatar_hash(user.email)
        wildcard = os.path.join(local_dir, avatar_hash + '.*')

        for local_path in glob.glob(wildcard):
            logging.info('Copying avatar file for user %s from %s' % (
                user.email, local_path))
            fn = os.path.basename(local_path)
            output_path = os.path.join(output_dir, fn)
            mkdir_p(str(os.path.dirname(output_path)))
            subprocess.check_call(["cp", "-a", str(local_path), str(output_path)])
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

def do_write_stats_file_for_realm_export(output_dir):
    stats_file = os.path.join(output_dir, 'stats.txt')
    realm_file = os.path.join(output_dir, 'realm.json')
    attachment_file = os.path.join(output_dir, 'attachment.json')
    message_files = glob.glob(os.path.join(output_dir, 'messages-*.json'))
    fns = sorted([attachment_file] + message_files + [realm_file])

    logging.info('Writing stats file: %s\n' % (stats_file,))
    with open(stats_file, 'w') as f:
        for fn in fns:
            f.write(os.path.basename(fn) +'\n')
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

def do_export_realm(realm, output_dir, threads, exportable_user_ids=None):
    # type: (Realm, Path, int, Set[int]) -> None
    response = {} # type: TableData

    # We need at least one thread running to export
    # UserMessage rows.  The management command should
    # enforce this for us.
    if not settings.TEST_SUITE:
        assert threads >= 1

    assert os.path.exists("./manage.py")

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

    export_file = os.path.join(output_dir, "realm.json")
    write_data_to_file(output_file=export_file, data=response)

    sanity_check_output(response)

    logging.info("Exporting uploaded files and avatars")
    export_uploads_and_avatars(realm, output_dir)

    # We (sort of) export zerver_message rows here.  We write
    # them to .partial files that are subsequently fleshed out
    # by parallel processes to add in zerver_usermessage data.
    # This is for performance reasons, of course.  Some installations
    # have millions of messages.
    logging.info("Exporting .partial files messages")
    message_ids = export_partial_message_files(realm, response, output_dir=output_dir)
    logging.info('%d messages were exported' % (len(message_ids)))

    # zerver_attachment
    export_attachment_table(realm=realm, output_dir=output_dir, message_ids=message_ids)

    # Start parallel jobs to export the UserMessage objects.
    launch_user_message_subprocesses(threads=threads, output_dir=output_dir)

    logging.info("Finished exporting %s" % (realm.domain))
    create_soft_link(source=output_dir, in_progress=False)

def export_attachment_table(realm, output_dir, message_ids):
    # type: (Realm, Path, Set[int]) -> None
    response = {} # type: TableData
    fetch_attachment_data(response=response, realm_id=realm.id, message_ids=message_ids)
    output_file = os.path.join(output_dir, "attachment.json")
    logging.info('Writing attachment table data to %s' % (output_file,))
    write_data_to_file(output_file=output_file, data=response)

def create_soft_link(source, in_progress=True):
    is_done = not in_progress
    in_progress_link = '/tmp/zulip-export-in-progress'
    done_link = '/tmp/zulip-export-most-recent'

    if in_progress:
        new_target = in_progress_link
    else:
        subprocess.check_call(['rm', '-f', in_progress_link])
        new_target = done_link

    subprocess.check_call(["ln", "-nsf", source, new_target])
    if is_done:
        logging.info('See %s for output files' % (new_target,))


def launch_user_message_subprocesses(threads, output_dir):
    # type: (int, Path) -> None
    logging.info('Launching %d PARALLEL subprocesses to export UserMessage rows' % (threads,))
    def run_job(shard):
        # type: (str) -> int
        subprocess.call(["./manage.py", 'export_usermessage_batch', '--path',
                         str(output_dir), '--thread', shard])
        return 0

    for (status, job) in run_parallel(run_job,
                                      [str(x) for x in range(0, threads)],
                                      threads=threads):
        print("Shard %s finished, status %s" % (job, status))

def do_export_user(user_profile, output_dir):
    # type: (UserProfile, Path) -> None
    response = {} # type: TableData

    export_single_user(user_profile, response)
    export_file = os.path.join(output_dir, "user.json")
    write_data_to_file(output_file=export_file, data=response)
    logging.info("Exporting messages")
    export_messages_single_user(user_profile, output_dir=output_dir)

def export_single_user(user_profile, response):
    # type: (UserProfile, TableData) -> None

    config = get_single_user_config()
    export_from_config(
        response=response,
        config=config,
        seed_object=user_profile,
    )

def get_single_user_config():
    # type: () -> Config

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

def export_messages_single_user(user_profile, chunk_size=1000, output_dir=None):
    # type: (UserProfile, int, Path) -> None
    user_message_query = UserMessage.objects.filter(user_profile=user_profile).order_by("id")
    min_id = -1
    dump_file_id = 1
    while True:
        actual_query = user_message_query.select_related("message", "message__sending_client").filter(id__gt=min_id)[0:chunk_size]
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

        write_message_export(message_filename, output)
        min_id = max(user_message_ids)
        dump_file_id += 1

# Code from here is the realm import code path

# id_maps is a dictionary that maps table names to dictionaries
# that map old ids to new ids.  We use this in
# re_map_foreign_keys and other places.
#
# We explicity initialize id_maps with the tables that support
# id re-mapping.
#
# Code reviewers: give these tables extra scrutiny, as we need to
# make sure to reload related tables AFTER we re-map the ids.
id_maps = {
    'client': {},
    'user_profile': {},
} # type: Dict[str, Dict[int, int]]

def update_id_map(table, old_id, new_id):
    # type: (TableName, int, int) -> None
    if table not in id_maps:
        raise Exception('''
            Table %s is not initialized in id_maps, which could
            mean that we have not thought through circular
            dependencies.
            ''' % (table,))
    id_maps[table][old_id] = new_id

def fix_datetime_fields(data, table):
    # type: (TableData, TableName) -> None
    for item in data[table]:
        for field_name in DATE_FIELDS[table]:
            if item[field_name] is None:
                item[field_name] = None
            else:
                v = datetime.datetime.utcfromtimestamp(item[field_name])
                item[field_name] = timezone.make_aware(v, timezone=timezone.utc)

def convert_to_id_fields(data, table, field_name):
    # type: (TableData, TableName, Field) -> None
    '''
    When Django gives us dict objects via model_to_dict, the foreign
    key fields are `foo`, but we want `foo_id` for the bulk insert.
    This function handles the simple case where we simply rename
    the fields.  For cases where we need to munge ids in the
    database, see re_map_foreign_keys.
    '''
    for item in data[table]:
        item[field_name + "_id"] = item[field_name]
        del item[field_name]

def re_map_foreign_keys(data, table, field_name, related_table, verbose=False):
    # type: (TableData, TableName, Field, TableName, bool) -> None
    '''
    We occasionally need to assign new ids to rows during the
    import/export process, to accomodate things like existing rows
    already being in tables.  See bulk_import_client for more context.

    The tricky part is making sure that foreign key references
    are in sync with the new ids, and this fixer function does
    the re-mapping.  (It also appends `_id` to the field.)
    '''
    lookup_table = id_maps[related_table]
    for item in data[table]:
        old_id = item[field_name]
        if old_id in lookup_table:
            new_id = lookup_table[old_id]
            if verbose:
                logging.info('Remapping %s%s from %s to %s' % (table,
                                                              field_name + '_id',
                                                              old_id,
                                                              new_id))
        else:
            new_id = old_id
        item[field_name + "_id"] = new_id
        del item[field_name]

def fix_bitfield_keys(data, table, field_name):
    # type: (TableData, TableName, Field) -> None
    for item in data[table]:
        item[field_name] = item[field_name + '_mask']
        del item[field_name + '_mask']

def bulk_import_model(data, model, table, dump_file_id=None):
    # type: (TableData, Any, TableName, str) -> None
    # TODO, deprecate dump_file_id
    model.objects.bulk_create(model(**item) for item in data[table])
    if dump_file_id is None:
        logging.info("Successfully imported %s from %s." % (model, table))
    else:
        logging.info("Successfully imported %s from %s[%s]." % (model, table, dump_file_id))

# Client is a table shared by multiple realms, so in order to
# correctly import multiple realms into the same server, we need to
# check if a Client object already exists, and so we need to support
# remap all Client IDs to the values in the new DB.
def bulk_import_client(data, model, table):
    # type: (TableData, Any, TableName) -> None
    for item in data[table]:
        try:
            client = Client.objects.get(name=item['name'])
        except Client.DoesNotExist:
            client = Client.objects.create(name=item['name'])
        update_id_map(table='client', old_id=item['id'], new_id=client.id)

def import_uploads_local(import_dir, processing_avatars=False):
    # type: (Path, bool) -> None
    records_filename = os.path.join(import_dir, "records.json")
    with open(records_filename) as records_file:
        records = ujson.loads(records_file.read())

    for record in records:
        if processing_avatars:
            # For avatars, we need to rehash the user's email with the
            # new server's avatar salt
            avatar_hash = user_avatar_hash(record['user_profile_email'])
            file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", avatar_hash)
            if record['s3_path'].endswith('.original'):
                file_path += '.original'
            else:
                file_path += '.png'
        else:
            file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "files", record['s3_path'])

        orig_file_path = os.path.join(import_dir, record['path'])
        if not os.path.exists(os.path.dirname(file_path)):
            subprocess.check_call(["mkdir", "-p", os.path.dirname(file_path)])
        shutil.copy(orig_file_path, file_path)

def import_uploads_s3(bucket_name, import_dir, processing_avatars=False):
    # type: (str, Path, bool) -> None
    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    bucket = conn.get_bucket(bucket_name, validate=True)

    records_filename = os.path.join(import_dir, "records.json")
    with open(records_filename) as records_file:
        records = ujson.loads(records_file.read())

    for record in records:
        key = Key(bucket)

        if processing_avatars:
            # For avatars, we need to rehash the user's email with the
            # new server's avatar salt
            avatar_hash = user_avatar_hash(record['user_profile_email'])
            key.key = avatar_hash
            if record['s3_path'].endswith('.original'):
                key.key += '.original'
        else:
            key.key = record['s3_path']

        user_profile_id = int(record['user_profile_id'])
        # Support email gateway bot and other cross-realm messages
        if user_profile_id in id_maps["user_profile"]:
            logging.info("Uploaded by ID mapped user: %s!" % (user_profile_id,))
            user_profile_id = id_maps["user_profile"][user_profile_id]
        user_profile = get_user_profile_by_id(user_profile_id)
        key.set_metadata("user_profile_id", str(user_profile.id))
        key.set_metadata("realm_id", str(user_profile.realm.id))
        key.set_metadata("orig_last_modified", record['last_modified'])

        headers = {'Content-Type': record['content_type']}

        key.set_contents_from_filename(os.path.join(import_dir, record['path']), headers=headers)

def import_uploads(import_dir, processing_avatars=False):
    # type: (Path, bool) -> None
    if processing_avatars:
        logging.info("Importing avatars")
    else:
        logging.info("Importing uploaded files")
    if settings.LOCAL_UPLOADS_DIR:
        import_uploads_local(import_dir, processing_avatars=processing_avatars)
    else:
        if processing_avatars:
            bucket_name = settings.S3_AVATAR_BUCKET
        else:
            bucket_name = settings.S3_AUTH_UPLOADS_BUCKET
        import_uploads_s3(bucket_name, import_dir, processing_avatars=processing_avatars)

# Importing data suffers from a difficult ordering problem because of
# models that reference each other circularly.  Here is a correct order.
#
# * Client [no deps]
# * Realm [-notifications_stream]
# * Stream [only depends on realm]
# * Realm's notifications_stream
# * Now can do all realm_tables
# * UserProfile, in order by ID to avoid bot loop issues
# * Huddle
# * Recipient
# * Subscription
# * Message
# * UserMessage
#
# Because the Python object => JSON conversion process is not fully
# faithful, we have to use a set of fixers (e.g. on DateTime objects
# and Foreign Keys) to do the import correctly.
def do_import_realm(import_dir):
    # type: (Path) -> None
    logging.info("Importing realm dump %s" % (import_dir,))
    if not os.path.exists(import_dir):
        raise Exception("Missing import directory!")

    realm_data_filename = os.path.join(import_dir, "realm.json")
    if not os.path.exists(realm_data_filename):
        raise Exception("Missing realm.json file!")

    logging.info("Importing realm data from %s" % (realm_data_filename,))
    with open(realm_data_filename) as f:
        data = ujson.load(f)

    convert_to_id_fields(data, 'zerver_realm', 'notifications_stream')
    fix_datetime_fields(data, 'zerver_realm')
    realm = Realm(**data['zerver_realm'][0])
    if realm.notifications_stream_id is not None:
        notifications_stream_id = int(realm.notifications_stream_id)
    else:
        notifications_stream_id = None
    realm.notifications_stream_id = None
    realm.save()
    bulk_import_client(data, Client, 'zerver_client')

    # Email tokens will automatically be randomly generated when the
    # Stream objects are created by Django.
    fix_datetime_fields(data, 'zerver_stream')
    convert_to_id_fields(data, 'zerver_stream', 'realm')
    bulk_import_model(data, Stream, 'zerver_stream')

    realm.notifications_stream_id = notifications_stream_id
    realm.save()

    convert_to_id_fields(data, "zerver_defaultstream", 'stream')
    for (table, model) in realm_tables:
        convert_to_id_fields(data, table, 'realm')
        bulk_import_model(data, model, table)

    # Remap the user IDs for notification_bot and friends to their
    # appropriate IDs on this server
    for item in data['zerver_userprofile_crossrealm']:
        logging.info("Adding to ID map: %s %s" % (item['id'], get_user_profile_by_email(item['email']).id))
        new_user_id = get_user_profile_by_email(item['email']).id
        update_id_map(table='user_profile', old_id=item['id'], new_id=new_user_id)

    # Merge in zerver_userprofile_mirrordummy
    data['zerver_userprofile'] = data['zerver_userprofile'] + data['zerver_userprofile_mirrordummy']
    del data['zerver_userprofile_mirrordummy']
    data['zerver_userprofile'].sort(key=lambda r: r['id'])

    fix_datetime_fields(data, 'zerver_userprofile')
    convert_to_id_fields(data, 'zerver_userprofile', 'realm')
    re_map_foreign_keys(data, 'zerver_userprofile', 'bot_owner', related_table="user_profile")
    convert_to_id_fields(data, 'zerver_userprofile', 'default_sending_stream')
    convert_to_id_fields(data, 'zerver_userprofile', 'default_events_register_stream')
    for user_profile_dict in data['zerver_userprofile']:
        user_profile_dict['password'] = None
        user_profile_dict['api_key'] = random_api_key()
        # Since Zulip doesn't use these permissions, drop them
        del user_profile_dict['user_permissions']
        del user_profile_dict['groups']
    user_profiles = [UserProfile(**item) for item in data['zerver_userprofile']]
    for user_profile in user_profiles:
        user_profile.set_unusable_password()
    UserProfile.objects.bulk_create(user_profiles)

    if 'zerver_huddle' in data:
        bulk_import_model(data, Huddle, 'zerver_huddle')

    bulk_import_model(data, Recipient, 'zerver_recipient')
    re_map_foreign_keys(data, 'zerver_subscription', 'user_profile', related_table="user_profile")
    convert_to_id_fields(data, 'zerver_subscription', 'recipient')
    bulk_import_model(data, Subscription, 'zerver_subscription')

    fix_datetime_fields(data, 'zerver_userpresence')
    re_map_foreign_keys(data, 'zerver_userpresence', 'user_profile', related_table="user_profile")
    re_map_foreign_keys(data, 'zerver_userpresence', 'client', related_table='client')
    bulk_import_model(data, UserPresence, 'zerver_userpresence')

    fix_datetime_fields(data, 'zerver_useractivity')
    re_map_foreign_keys(data, 'zerver_useractivity', 'user_profile', related_table="user_profile")
    re_map_foreign_keys(data, 'zerver_useractivity', 'client', related_table='client')
    bulk_import_model(data, UserActivity, 'zerver_useractivity')

    fix_datetime_fields(data, 'zerver_useractivityinterval')
    re_map_foreign_keys(data, 'zerver_useractivityinterval', 'user_profile', related_table="user_profile")
    bulk_import_model(data, UserActivityInterval, 'zerver_useractivityinterval')

    # Import uploaded files and avatars
    import_uploads(os.path.join(import_dir, "avatars"), processing_avatars=True)
    import_uploads(os.path.join(import_dir, "uploads"))

    # Import zerver_message and zerver_usermessage
    import_message_data(import_dir)

    # Do attachments AFTER message data is loaded.
    # TODO: de-dup how we read these json files.
    fn = os.path.join(import_dir, "attachment.json")
    if not os.path.exists(fn):
        raise Exception("Missing attachment.json file!")

    logging.info("Importing attachment data from %s" % (fn,))
    with open(fn) as f:
        data = ujson.load(f)

    import_attachments(data)

def import_message_data(import_dir):
    # type: (Path) -> None
    dump_file_id = 1
    while True:
        message_filename = os.path.join(import_dir, "messages-%06d.json" % (dump_file_id,))
        if not os.path.exists(message_filename):
            break

        with open(message_filename) as f:
            data = ujson.load(f)

        logging.info("Importing message dump %s" % (message_filename,))
        re_map_foreign_keys(data, 'zerver_message', 'sender', related_table="user_profile")
        convert_to_id_fields(data, 'zerver_message', 'recipient')
        re_map_foreign_keys(data, 'zerver_message', 'sending_client', related_table='client')
        fix_datetime_fields(data, 'zerver_message')
        bulk_import_model(data, Message, 'zerver_message')

        # Due to the structure of these message chunks, we're
        # guaranteed to have already imported all the Message objects
        # for this batch of UserMessage objects.
        convert_to_id_fields(data, 'zerver_usermessage', 'message')
        re_map_foreign_keys(data, 'zerver_usermessage', 'user_profile', related_table="user_profile")
        fix_bitfield_keys(data, 'zerver_usermessage', 'flags')
        bulk_import_model(data, UserMessage, 'zerver_usermessage')

        dump_file_id += 1

def import_attachments(data):
    # type: (TableData) -> None

    # Clean up the data in zerver_attachment that is not
    # relevant to our many-to-many import.
    fix_datetime_fields(data, 'zerver_attachment')
    re_map_foreign_keys(data, 'zerver_attachment', 'owner', related_table="user_profile")
    convert_to_id_fields(data, 'zerver_attachment', 'realm')

    # Configure ourselves.  Django models many-to-many (m2m)
    # relations asymmetrically. The parent here refers to the
    # Model that has the ManyToManyField.  It is assumed here
    # the child models have been loaded, but we are in turn
    # responsible for loading the parents and the m2m rows.
    parent_model = Attachment
    parent_db_table_name = 'zerver_attachment'
    parent_singular = 'attachment'
    child_singular = 'message'
    child_plural = 'messages'
    m2m_table_name = 'zerver_attachment_messages'
    parent_id = 'attachment_id'
    child_id = 'message_id'

    # First, build our list of many-to-many (m2m) rows.
    # We do this in a slightly convoluted way to anticipate
    # a future where we may need to call re_map_foreign_keys.

    m2m_rows = [] # type: List[Record]
    for parent_row in data[parent_db_table_name]:
        for fk_id in parent_row[child_plural]:
            m2m_row = {} # type: Record
            m2m_row[parent_singular] = parent_row['id']
            m2m_row[child_singular] = fk_id
            m2m_rows.append(m2m_row)

    # Create our table data for insert.
    m2m_data = {m2m_table_name: m2m_rows} # type: TableData
    convert_to_id_fields(m2m_data, m2m_table_name, parent_singular)
    convert_to_id_fields(m2m_data, m2m_table_name, child_singular)
    m2m_rows = m2m_data[m2m_table_name]

    # Next, delete out our child data from the parent rows.
    for parent_row in data[parent_db_table_name]:
        del parent_row[child_plural]

    # Next, load the parent rows.
    bulk_import_model(data, parent_model, parent_db_table_name)

    # Now, go back to our m2m rows.
    # TODO: Do this the kosher Django way.  We may find a
    # better way to do this in Django 1.9 particularly.
    with connection.cursor() as cursor:
        sql_template = '''
            insert into %s (%s, %s) values(%%s, %%s);''' % (m2m_table_name,
                                                           parent_id,
                                                           child_id)
        tups = [(row[parent_id], row[child_id]) for row in m2m_rows]
        cursor.executemany(sql_template, tups)

    logging.info('Successfully imported M2M table %s' % (m2m_table_name,))

