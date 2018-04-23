import datetime
import logging
import os
import ujson
import shutil
import subprocess

from boto.s3.connection import S3Connection
from boto.s3.key import Key
from django.conf import settings
from django.db import connection
from django.utils.timezone import utc as timezone_utc
from typing import Any, Dict, List, Optional, Set, Tuple, \
    Iterable, Text

from zerver.lib.avatar_hash import user_avatar_path_from_ids
from zerver.lib.bulk_create import bulk_create_users
from zerver.lib.create_user import random_api_key
from zerver.lib.export import DATE_FIELDS, realm_tables, \
    Record, TableData, TableName, Field, Path
from zerver.lib.upload import random_name, sanitize_name, \
    S3UploadBackend, LocalUploadBackend
from zerver.models import UserProfile, Realm, Client, Huddle, Stream, \
    UserMessage, Subscription, Message, RealmEmoji, \
    RealmDomain, Recipient, get_user_profile_by_id, \
    UserPresence, UserActivity, UserActivityInterval, Reaction, \
    CustomProfileField, CustomProfileFieldValue, \
    Attachment, get_system_bot, email_to_username

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
    'realm': {},
    'stream': {},
    'recipient': {},
    'subscription': {},
    'defaultstream': {},
    'reaction': {},
    'realmemoji': {},
    'realmdomain': {},
    'realmfilter': {},
    'message': {},
    'user_presence': {},
    'useractivity': {},
    'useractivityinterval': {},
    'usermessage': {},
    'customprofilefield': {},
    'customprofilefield_value': {},
    'attachment': {},
}  # type: Dict[str, Dict[int, int]]

path_maps = {
    'attachment_path': {},
}  # type: Dict[str, Dict[str, str]]

def update_id_map(table: TableName, old_id: int, new_id: int) -> None:
    if table not in id_maps:
        raise Exception('''
            Table %s is not initialized in id_maps, which could
            mean that we have not thought through circular
            dependencies.
            ''' % (table,))
    id_maps[table][old_id] = new_id

def fix_datetime_fields(data: TableData, table: TableName) -> None:
    for item in data[table]:
        for field_name in DATE_FIELDS[table]:
            if item[field_name] is not None:
                item[field_name] = datetime.datetime.fromtimestamp(item[field_name], tz=timezone_utc)

def fix_upload_links(data: TableData, message_table: TableName) -> None:
    """
    Because the URLs for uploaded files encode the realm ID of the
    organization being imported (which is only determined at import
    time), we need to rewrite the URLs of links to uploaded files
    during the import process.
    """
    for message in data[message_table]:
        if message['has_attachment'] is True:
            for key, value in path_maps['attachment_path'].items():
                if key in message['content']:
                    message['content'] = message['content'].replace(key, value)
                    if message['rendered_content']:
                        message['rendered_content'] = message['rendered_content'].replace(key, value)

def current_table_ids(data: TableData, table: TableName) -> List[int]:
    """
    Returns the ids present in the current table
    """
    id_list = []
    for item in data[table]:
        id_list.append(item["id"])
    return id_list

def idseq(model_class: Any) -> str:
    if model_class == RealmDomain:
        return 'zerver_realmalias_id_seq'
    return '{}_id_seq'.format(model_class._meta.db_table)

def allocate_ids(model_class: Any, count: int) -> List[int]:
    """
    Increases the sequence number for a given table by the amount of objects being
    imported into that table. Hence, this gives a reserved range of ids to import the
    converted slack objects into the tables.
    """
    conn = connection.cursor()
    sequence = idseq(model_class)
    conn.execute("select nextval('%s') from generate_series(1,%s)" %
                 (sequence, str(count)))
    query = conn.fetchall()  # Each element in the result is a tuple like (5,)
    conn.close()
    # convert List[Tuple[int]] to List[int]
    return [item[0] for item in query]

def convert_to_id_fields(data: TableData, table: TableName, field_name: Field) -> None:
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

def re_map_foreign_keys(data: TableData,
                        table: TableName,
                        field_name: Field,
                        related_table: TableName,
                        verbose: bool=False,
                        id_field: bool=False,
                        recipient_field: bool=False) -> None:
    """
    This is a wrapper function for all the realm data tables
    and only avatar and attachment records need to be passed through the internal function
    because of the difference in data format (TableData corresponding to realm data tables
    and List[Record] corresponding to the avatar and attachment records)
    """
    re_map_foreign_keys_internal(data[table], table, field_name, related_table, verbose, id_field,
                                 recipient_field)

def re_map_foreign_keys_internal(data_table: List[Record],
                                 table: TableName,
                                 field_name: Field,
                                 related_table: TableName,
                                 verbose: bool=False,
                                 id_field: bool=False,
                                 recipient_field: bool=False) -> None:
    '''
    We occasionally need to assign new ids to rows during the
    import/export process, to accommodate things like existing rows
    already being in tables.  See bulk_import_client for more context.

    The tricky part is making sure that foreign key references
    are in sync with the new ids, and this fixer function does
    the re-mapping.  (It also appends `_id` to the field.)
    '''
    lookup_table = id_maps[related_table]
    for item in data_table:
        if recipient_field:
            if related_table == "stream" and item['type'] == 2:
                pass
            elif related_table == "user_profile" and item['type'] == 1:
                pass
            else:
                continue
        old_id = item[field_name]
        if old_id in lookup_table:
            new_id = lookup_table[old_id]
            if verbose:
                logging.info('Remapping %s %s from %s to %s' % (table,
                                                                field_name + '_id',
                                                                old_id,
                                                                new_id))
        else:
            new_id = old_id
        if not id_field:
            item[field_name + "_id"] = new_id
            del item[field_name]
        else:
            item[field_name] = new_id

def fix_bitfield_keys(data: TableData, table: TableName, field_name: Field) -> None:
    for item in data[table]:
        item[field_name] = item[field_name + '_mask']
        del item[field_name + '_mask']

def fix_realm_authentication_bitfield(data: TableData, table: TableName, field_name: Field) -> None:
    """Used to fixup the authentication_methods bitfield to be a string"""
    for item in data[table]:
        values_as_bitstring = ''.join(['1' if field[1] else '0' for field in
                                       item[field_name]])
        values_as_int = int(values_as_bitstring, 2)
        item[field_name] = values_as_int

def update_model_ids(model: Any, data: TableData, table: TableName, related_table: TableName) -> None:
    old_id_list = current_table_ids(data, table)
    allocated_id_list = allocate_ids(model, len(data[table]))
    for item in range(len(data[table])):
        update_id_map(related_table, old_id_list[item], allocated_id_list[item])
    re_map_foreign_keys(data, table, 'id', related_table=related_table, id_field=True)

def bulk_import_model(data: TableData, model: Any, table: TableName,
                      dump_file_id: Optional[str]=None) -> None:
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
def bulk_import_client(data: TableData, model: Any, table: TableName) -> None:
    for item in data[table]:
        try:
            client = Client.objects.get(name=item['name'])
        except Client.DoesNotExist:
            client = Client.objects.create(name=item['name'])
        update_id_map(table='client', old_id=item['id'], new_id=client.id)

def import_uploads_local(import_dir: Path, processing_avatars: bool=False,
                         processing_emojis: bool=False) -> None:
    records_filename = os.path.join(import_dir, "records.json")
    with open(records_filename) as records_file:
        records = ujson.loads(records_file.read())

    re_map_foreign_keys_internal(records, 'records', 'realm_id', related_table="realm",
                                 id_field=True)
    if not processing_emojis:
        re_map_foreign_keys_internal(records, 'records', 'user_profile_id',
                                     related_table="user_profile", id_field=True)
    for record in records:
        if processing_avatars:
            # For avatars, we need to rehash the user ID with the
            # new server's avatar salt
            avatar_path = user_avatar_path_from_ids(record['user_profile_id'], record['realm_id'])
            file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", avatar_path)
            if record['s3_path'].endswith('.original'):
                file_path += '.original'
            else:
                file_path += '.png'
        elif processing_emojis:
            # For emojis we follow the function 'upload_emoji_image'
            emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
                realm_id=record['realm_id'],
                emoji_file_name=record['file_name'])
            file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", emoji_path)
        else:
            # Should be kept in sync with its equivalent in zerver/lib/uploads in the
            # function 'upload_message_image'
            s3_file_name = "/".join([
                str(record['realm_id']),
                random_name(18),
                sanitize_name(os.path.basename(record['path']))
            ])
            file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "files", s3_file_name)
            path_maps['attachment_path'][record['path']] = s3_file_name

        orig_file_path = os.path.join(import_dir, record['path'])
        if not os.path.exists(os.path.dirname(file_path)):
            subprocess.check_call(["mkdir", "-p", os.path.dirname(file_path)])
        shutil.copy(orig_file_path, file_path)

    if processing_avatars:
        # Ensure that we have medium-size avatar images for every
        # avatar.  TODO: This implementation is hacky, both in that it
        # does get_user_profile_by_id for each user, and in that it
        # might be better to require the export to just have these.
        upload_backend = LocalUploadBackend()
        for record in records:
            if record['s3_path'].endswith('.original'):
                user_profile = get_user_profile_by_id(record['user_profile_id'])
                avatar_path = user_avatar_path_from_ids(user_profile.id, record['realm_id'])
                medium_file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars",
                                                avatar_path) + '-medium.png'
                if os.path.exists(medium_file_path):
                    # We remove the image here primarily to deal with
                    # issues when running the import script multiple
                    # times in development (where one might reuse the
                    # same realm ID from a previous iteration).
                    os.remove(medium_file_path)
                upload_backend.ensure_medium_avatar_image(user_profile=user_profile)

def import_uploads_s3(bucket_name: str, import_dir: Path, processing_avatars: bool=False,
                      processing_emojis: bool=False) -> None:
    upload_backend = S3UploadBackend()
    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    bucket = conn.get_bucket(bucket_name, validate=True)

    records_filename = os.path.join(import_dir, "records.json")
    with open(records_filename) as records_file:
        records = ujson.loads(records_file.read())

    re_map_foreign_keys_internal(records, 'records', 'realm_id', related_table="realm",
                                 id_field=True)
    re_map_foreign_keys_internal(records, 'records', 'user_profile_id',
                                 related_table="user_profile", id_field=True)
    for record in records:
        key = Key(bucket)

        if processing_avatars:
            # For avatars, we need to rehash the user's email with the
            # new server's avatar salt
            avatar_path = user_avatar_path_from_ids(record['user_profile_id'], record['realm_id'])
            key.key = avatar_path
            if record['s3_path'].endswith('.original'):
                key.key += '.original'
        if processing_emojis:
            # For emojis we follow the function 'upload_emoji_image'
            emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
                realm_id=record['realm_id'],
                emoji_file_name=record['file_name'])
            key.key = emoji_path
        else:
            # Should be kept in sync with its equivalent in zerver/lib/uploads in the
            # function 'upload_message_image'
            s3_file_name = "/".join([
                str(record['realm_id']),
                random_name(18),
                sanitize_name(os.path.basename(record['path']))
            ])
            key.key = s3_file_name
            path_maps['attachment_path'][record['path']] = s3_file_name

        user_profile_id = int(record['user_profile_id'])
        # Support email gateway bot and other cross-realm messages
        if user_profile_id in id_maps["user_profile"]:
            logging.info("Uploaded by ID mapped user: %s!" % (user_profile_id,))
            user_profile_id = id_maps["user_profile"][user_profile_id]
        user_profile = get_user_profile_by_id(user_profile_id)
        key.set_metadata("user_profile_id", str(user_profile.id))
        key.set_metadata("realm_id", str(user_profile.realm_id))
        key.set_metadata("orig_last_modified", record['last_modified'])

        headers = {'Content-Type': record['content_type']}

        key.set_contents_from_filename(os.path.join(import_dir, record['path']), headers=headers)

        if processing_avatars:
            # TODO: Ideally, we'd do this in a separate pass, after
            # all the avatars have been uploaded, since we may end up
            # unnecssarily resizing images just before the medium-size
            # image in the export is uploaded.  See the local uplods
            # code path for more notes.
            upload_backend.ensure_medium_avatar_image(user_profile=user_profile)

def import_uploads(import_dir: Path, processing_avatars: bool=False,
                   processing_emojis: bool=False) -> None:
    if processing_avatars:
        logging.info("Importing avatars")
    elif processing_emojis:
        logging.info("Importing emojis")
    else:
        logging.info("Importing uploaded files")
    if settings.LOCAL_UPLOADS_DIR:
        import_uploads_local(import_dir, processing_avatars=processing_avatars,
                             processing_emojis=processing_emojis)
    else:
        if processing_avatars or processing_emojis:
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
def do_import_realm(import_dir: Path, subdomain: str) -> Realm:
    logging.info("Importing realm dump %s" % (import_dir,))
    if not os.path.exists(import_dir):
        raise Exception("Missing import directory!")

    realm_data_filename = os.path.join(import_dir, "realm.json")
    if not os.path.exists(realm_data_filename):
        raise Exception("Missing realm.json file!")

    logging.info("Importing realm data from %s" % (realm_data_filename,))
    with open(realm_data_filename) as f:
        data = ujson.load(f)

    update_model_ids(Stream, data, 'zerver_stream', 'stream')
    re_map_foreign_keys(data, 'zerver_realm', 'notifications_stream', related_table="stream")

    fix_datetime_fields(data, 'zerver_realm')
    # Fix realm subdomain information
    data['zerver_realm'][0]['string_id'] = subdomain
    data['zerver_realm'][0]['name'] = subdomain
    fix_realm_authentication_bitfield(data, 'zerver_realm', 'authentication_methods')
    update_model_ids(Realm, data, 'zerver_realm', 'realm')

    realm = Realm(**data['zerver_realm'][0])
    if realm.notifications_stream_id is not None:
        notifications_stream_id = int(realm.notifications_stream_id)  # type: Optional[int]
    else:
        notifications_stream_id = None
    realm.notifications_stream_id = None
    realm.save()
    bulk_import_client(data, Client, 'zerver_client')

    # Email tokens will automatically be randomly generated when the
    # Stream objects are created by Django.
    fix_datetime_fields(data, 'zerver_stream')
    re_map_foreign_keys(data, 'zerver_stream', 'realm', related_table="realm")
    bulk_import_model(data, Stream, 'zerver_stream')

    realm.notifications_stream_id = notifications_stream_id
    realm.save()

    re_map_foreign_keys(data, 'zerver_defaultstream', 'stream', related_table="stream")
    re_map_foreign_keys(data, 'zerver_realmemoji', 'author', related_table="user_profile")
    for (table, model, related_table) in realm_tables:
        re_map_foreign_keys(data, table, 'realm', related_table="realm")
        update_model_ids(model, data, table, related_table)
        bulk_import_model(data, model, table)

    # Remap the user IDs for notification_bot and friends to their
    # appropriate IDs on this server
    for item in data['zerver_userprofile_crossrealm']:
        logging.info("Adding to ID map: %s %s" % (item['id'], get_system_bot(item['email']).id))
        new_user_id = get_system_bot(item['email']).id
        update_id_map(table='user_profile', old_id=item['id'], new_id=new_user_id)

    # Merge in zerver_userprofile_mirrordummy
    data['zerver_userprofile'] = data['zerver_userprofile'] + data['zerver_userprofile_mirrordummy']
    del data['zerver_userprofile_mirrordummy']
    data['zerver_userprofile'].sort(key=lambda r: r['id'])

    # To remap foreign key for UserProfile.last_active_message_id
    update_message_foreign_keys(import_dir)

    fix_datetime_fields(data, 'zerver_userprofile')
    update_model_ids(UserProfile, data, 'zerver_userprofile', 'user_profile')
    re_map_foreign_keys(data, 'zerver_userprofile', 'realm', related_table="realm")
    re_map_foreign_keys(data, 'zerver_userprofile', 'bot_owner', related_table="user_profile")
    re_map_foreign_keys(data, 'zerver_userprofile', 'default_sending_stream',
                        related_table="stream")
    re_map_foreign_keys(data, 'zerver_userprofile', 'default_events_register_stream',
                        related_table="stream")
    re_map_foreign_keys(data, 'zerver_userprofile', 'last_active_message_id',
                        related_table="message", id_field=True)
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

    re_map_foreign_keys(data, 'zerver_recipient', 'type_id', related_table="stream",
                        recipient_field=True, id_field=True)
    re_map_foreign_keys(data, 'zerver_recipient', 'type_id', related_table="user_profile",
                        recipient_field=True, id_field=True)
    update_model_ids(Recipient, data, 'zerver_recipient', 'recipient')
    bulk_import_model(data, Recipient, 'zerver_recipient')

    re_map_foreign_keys(data, 'zerver_subscription', 'user_profile', related_table="user_profile")
    re_map_foreign_keys(data, 'zerver_subscription', 'recipient', related_table="recipient")
    update_model_ids(Subscription, data, 'zerver_subscription', 'subscription')
    bulk_import_model(data, Subscription, 'zerver_subscription')

    fix_datetime_fields(data, 'zerver_userpresence')
    re_map_foreign_keys(data, 'zerver_userpresence', 'user_profile', related_table="user_profile")
    re_map_foreign_keys(data, 'zerver_userpresence', 'client', related_table='client')
    update_model_ids(UserPresence, data, 'zerver_userpresence', 'user_presence')
    bulk_import_model(data, UserPresence, 'zerver_userpresence')

    fix_datetime_fields(data, 'zerver_useractivity')
    re_map_foreign_keys(data, 'zerver_useractivity', 'user_profile', related_table="user_profile")
    re_map_foreign_keys(data, 'zerver_useractivity', 'client', related_table='client')
    update_model_ids(UserActivity, data, 'zerver_useractivity', 'useractivity')
    bulk_import_model(data, UserActivity, 'zerver_useractivity')

    fix_datetime_fields(data, 'zerver_useractivityinterval')
    re_map_foreign_keys(data, 'zerver_useractivityinterval', 'user_profile', related_table="user_profile")
    update_model_ids(UserActivityInterval, data, 'zerver_useractivityinterval',
                     'useractivityinterval')
    bulk_import_model(data, UserActivityInterval, 'zerver_useractivityinterval')

    if 'zerver_customprofilefield' in data:
        # As the export of Custom Profile fields is not supported, Zulip exported
        # data would not contain this field.
        # However this is supported in slack importer script
        re_map_foreign_keys(data, 'zerver_customprofilefield', 'realm', related_table="realm")
        update_model_ids(CustomProfileField, data, 'zerver_customprofilefield',
                         related_table="customprofilefield")
        bulk_import_model(data, CustomProfileField, 'zerver_customprofilefield')

        re_map_foreign_keys(data, 'zerver_customprofilefield_value', 'user_profile',
                            related_table="user_profile")
        re_map_foreign_keys(data, 'zerver_customprofilefield_value', 'field',
                            related_table="customprofilefield")
        update_model_ids(CustomProfileFieldValue, data, 'zerver_customprofilefield_value',
                         related_table="customprofilefield_value")
        bulk_import_model(data, CustomProfileFieldValue, 'zerver_customprofilefield_value')

    # Import uploaded files and avatars
    import_uploads(os.path.join(import_dir, "avatars"), processing_avatars=True)
    import_uploads(os.path.join(import_dir, "uploads"))

    # We need to have this check as the emoji files are only present in the data
    # importer from slack
    # For Zulip export, this doesn't exist
    if os.path.exists(os.path.join(import_dir, "emoji")):
        import_uploads(os.path.join(import_dir, "emoji"), processing_emojis=True)

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
    return realm

# create_users and do_import_system_bots differ from their equivalent in
# zerver/management/commands/initialize_voyager_db.py because here we check if the bots
# don't already exist and only then create a user for these bots.
def do_import_system_bots(realm: Any) -> None:
    internal_bots = [(bot['name'], bot['email_template'] % (settings.INTERNAL_BOT_DOMAIN,))
                     for bot in settings.INTERNAL_BOTS]
    create_users(realm, internal_bots, bot_type=UserProfile.DEFAULT_BOT)
    names = [(settings.FEEDBACK_BOT_NAME, settings.FEEDBACK_BOT)]
    create_users(realm, names, bot_type=UserProfile.DEFAULT_BOT)
    print("Finished importing system bots.")

def create_users(realm: Realm, name_list: Iterable[Tuple[Text, Text]],
                 bot_type: Optional[int]=None) -> None:
    user_set = set()
    for full_name, email in name_list:
        short_name = email_to_username(email)
        if not UserProfile.objects.filter(email=email):
            user_set.add((email, full_name, short_name, True))
    bulk_create_users(realm, user_set, bot_type)

def update_message_foreign_keys(import_dir: Path) -> None:
    dump_file_id = 1
    while True:
        message_filename = os.path.join(import_dir, "messages-%06d.json" % (dump_file_id,))
        if not os.path.exists(message_filename):
            break

        with open(message_filename) as f:
            data = ujson.load(f)

        update_model_ids(Message, data, 'zerver_message', 'message')
        dump_file_id += 1

def import_message_data(import_dir: Path) -> None:
    dump_file_id = 1
    while True:
        message_filename = os.path.join(import_dir, "messages-%06d.json" % (dump_file_id,))
        if not os.path.exists(message_filename):
            break

        with open(message_filename) as f:
            data = ujson.load(f)

        logging.info("Importing message dump %s" % (message_filename,))
        re_map_foreign_keys(data, 'zerver_message', 'sender', related_table="user_profile")
        re_map_foreign_keys(data, 'zerver_message', 'recipient', related_table="recipient")
        re_map_foreign_keys(data, 'zerver_message', 'sending_client', related_table='client')
        fix_datetime_fields(data, 'zerver_message')
        # Parser to update message content with the updated attachment urls
        fix_upload_links(data, 'zerver_message')

        re_map_foreign_keys(data, 'zerver_message', 'id', related_table='message', id_field=True)
        bulk_import_model(data, Message, 'zerver_message')

        # Due to the structure of these message chunks, we're
        # guaranteed to have already imported all the Message objects
        # for this batch of UserMessage objects.
        re_map_foreign_keys(data, 'zerver_usermessage', 'message', related_table="message")
        re_map_foreign_keys(data, 'zerver_usermessage', 'user_profile', related_table="user_profile")
        fix_bitfield_keys(data, 'zerver_usermessage', 'flags')
        update_model_ids(UserMessage, data, 'zerver_usermessage', 'usermessage')
        bulk_import_model(data, UserMessage, 'zerver_usermessage')

        # As the export of Reactions is not supported, Zulip exported
        # data would not contain this field.
        # However this is supported in slack importer script
        if 'zerver_reaction' in data:
            re_map_foreign_keys(data, 'zerver_reaction', 'message', related_table="message")
            re_map_foreign_keys(data, 'zerver_reaction', 'user_profile', related_table="user_profile")
            for reaction in data['zerver_reaction']:
                if reaction['reaction_type'] == Reaction.REALM_EMOJI:
                    re_map_foreign_keys(data, 'zerver_reaction', 'emoji_code',
                                        related_table="realmemoji", id_field=True)
            update_model_ids(Reaction, data, 'zerver_reaction', 'reaction')
            bulk_import_model(data, Reaction, 'zerver_reaction')

        dump_file_id += 1

def import_attachments(data: TableData) -> None:

    # Clean up the data in zerver_attachment that is not
    # relevant to our many-to-many import.
    fix_datetime_fields(data, 'zerver_attachment')
    re_map_foreign_keys(data, 'zerver_attachment', 'owner', related_table="user_profile")
    re_map_foreign_keys(data, 'zerver_attachment', 'realm', related_table="realm")

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

    update_model_ids(parent_model, data, parent_db_table_name, 'attachment')
    # First, build our list of many-to-many (m2m) rows.
    # We do this in a slightly convoluted way to anticipate
    # a future where we may need to call re_map_foreign_keys.

    m2m_rows = []  # type: List[Record]
    for parent_row in data[parent_db_table_name]:
        for fk_id in parent_row[child_plural]:
            m2m_row = {}  # type: Record
            m2m_row[parent_singular] = parent_row['id']
            m2m_row[child_singular] = id_maps['message'][fk_id]
            m2m_rows.append(m2m_row)

    # Create our table data for insert.
    m2m_data = {m2m_table_name: m2m_rows}  # type: TableData
    convert_to_id_fields(m2m_data, m2m_table_name, parent_singular)
    convert_to_id_fields(m2m_data, m2m_table_name, child_singular)
    m2m_rows = m2m_data[m2m_table_name]

    # Next, delete out our child data from the parent rows.
    for parent_row in data[parent_db_table_name]:
        del parent_row[child_plural]

    # Update 'path_id' for the attachments
    for attachment in data[parent_db_table_name]:
        attachment['path_id'] = path_maps['attachment_path'][attachment['path_id']]

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
