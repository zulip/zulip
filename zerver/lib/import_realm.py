import collections
import logging
import os
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from difflib import unified_diff
from typing import Any

import bmemcached
import orjson
import pyvips
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import CommandError
from django.core.validators import validate_email
from django.db import connection, transaction
from django.db.backends.utils import CursorWrapper
from django.db.models import Count, Q
from django.utils.timezone import now as timezone_now
from psycopg2.extras import execute_values
from psycopg2.sql import SQL, Identifier

from analytics.models import RealmCount, StreamCount, UserCount
from version import ZULIP_VERSION
from zerver.actions.create_realm import set_default_for_realm_permission_group_settings
from zerver.actions.realm_settings import (
    do_change_realm_plan_type,
    do_set_realm_new_stream_announcements_stream,
    do_set_realm_zulip_update_announcements_stream,
)
from zerver.actions.user_settings import do_change_avatar_fields
from zerver.lib.avatar_hash import user_avatar_base_path_from_ids
from zerver.lib.bulk_create import bulk_set_users_or_streams_recipient_fields
from zerver.lib.export import DATE_FIELDS, Field, Path, Record, TableData, TableName
from zerver.lib.markdown import markdown_convert
from zerver.lib.markdown import version as markdown_version
from zerver.lib.message import get_last_message_id
from zerver.lib.migration_status import MigrationStatusJson, parse_migration_status
from zerver.lib.mime_types import guess_type
from zerver.lib.onboarding import (
    OnboardingMessageTypeEnum,
    send_initial_direct_message,
    send_initial_realm_messages,
)
from zerver.lib.partial import partial
from zerver.lib.push_notifications import sends_notifications_directly
from zerver.lib.remote_server import maybe_enqueue_audit_log_upload
from zerver.lib.server_initialization import create_internal_realm, server_initialized
from zerver.lib.streams import (
    get_stream_permission_default_group,
    render_stream_description,
    update_stream_active_status_for_realm,
)
from zerver.lib.thumbnail import (
    THUMBNAIL_ACCEPT_IMAGE_TYPES,
    BadImageError,
    get_user_upload_previews,
    maybe_thumbnail,
)
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.upload import ensure_avatar_image, sanitize_name, upload_backend, upload_emoji_image
from zerver.lib.upload.s3 import get_bucket
from zerver.lib.user_counts import realm_user_count_by_role
from zerver.lib.user_groups import create_system_user_groups_for_realm
from zerver.lib.user_message import UserMessageLite, bulk_insert_ums
from zerver.lib.utils import generate_api_key, process_list_in_batches
from zerver.lib.zulip_update_announcements import send_zulip_update_announcements_to_realm
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
    RealmFilter,
    RealmPlayground,
    RealmUserDefault,
    Recipient,
    SavedSnippet,
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
from zerver.models.groups import SystemGroups
from zerver.models.presence import PresenceSequence
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zerver.models.recipients import get_direct_message_group_hash
from zerver.models.users import get_system_bot, get_user_profile_by_id
from zproject.backends import AUTH_BACKEND_NAME_MAP

realm_tables = [
    ("zerver_realmauthenticationmethod", RealmAuthenticationMethod, "realmauthenticationmethod"),
    ("zerver_defaultstream", DefaultStream, "defaultstream"),
    ("zerver_realmemoji", RealmEmoji, "realmemoji"),
    ("zerver_realmdomain", RealmDomain, "realmdomain"),
    ("zerver_realmfilter", RealmFilter, "realmfilter"),
    ("zerver_realmplayground", RealmPlayground, "realmplayground"),
]  # List[Tuple[TableName, Any, str]]


# ID_MAP is a dictionary that maps table names to dictionaries
# that map old ids to new ids.  We use this in
# re_map_foreign_keys and other places.
#
# We explicitly initialize ID_MAP with the tables that support
# id re-mapping.
#
# Code reviewers: give these tables extra scrutiny, as we need to
# make sure to reload related tables AFTER we re-map the ids.
ID_MAP: dict[str, dict[int, int]] = {
    "alertword": {},
    "client": {},
    "user_profile": {},
    "huddle": {},
    "realm": {},
    "stream": {},
    "recipient": {},
    "subscription": {},
    "defaultstream": {},
    "onboardingstep": {},
    "presencesequence": {},
    "reaction": {},
    "realmauthenticationmethod": {},
    "realmemoji": {},
    "realmdomain": {},
    "realmfilter": {},
    "realmplayground": {},
    "message": {},
    "user_presence": {},
    "userstatus": {},
    "useractivity": {},
    "useractivityinterval": {},
    "usermessage": {},
    "customprofilefield": {},
    "customprofilefieldvalue": {},
    "attachment": {},
    "realmauditlog": {},
    "recipient_to_huddle_map": {},
    "usertopic": {},
    "muteduser": {},
    "service": {},
    "usergroup": {},
    "usergroupmembership": {},
    "groupgroupmembership": {},
    "botstoragedata": {},
    "botconfigdata": {},
    "analytics_realmcount": {},
    "analytics_streamcount": {},
    "analytics_usercount": {},
    "realmuserdefault": {},
    "scheduledmessage": {},
    "onboardingusermessage": {},
    "savedsnippet": {},
    "channelfolder": {},
    "navigationview": {},
}

id_map_to_list: dict[str, dict[int, list[int]]] = {
    "huddle_to_user_list": {},
}

path_maps: dict[str, dict[str, str]] = {
    # Maps original attachment path pre-import to the final, post-import
    # attachment path.
    "old_attachment_path_to_new_path": {},
    # Inverse of old_attachment_path_to_new_path.
    "new_attachment_path_to_old_path": {},
    # Maps the new (post-import) attachment path to the absolute path to the file
    # in the on-disk export data that we're importing.
    # Allows code running after this is filled to access file contents
    # without needing to go through S3 to get it.
    "new_attachment_path_to_local_data_path": {},
}

message_id_to_attachments: dict[str, dict[int, list[str]]] = {
    "zerver_message": collections.defaultdict(list),
    "zerver_scheduledmessage": collections.defaultdict(list),
}


def map_messages_to_attachments(data: TableData) -> None:
    for attachment in data["zerver_attachment"]:
        for message_id in attachment["messages"]:
            message_id_to_attachments["zerver_message"][message_id].append(attachment["path_id"])

        for scheduled_message_id in attachment["scheduled_messages"]:
            message_id_to_attachments["zerver_scheduledmessage"][scheduled_message_id].append(
                attachment["path_id"]
            )


def update_id_map(table: TableName, old_id: int, new_id: int) -> None:
    if table not in ID_MAP:
        raise Exception(
            f"""
            Table {table} is not initialized in ID_MAP, which could
            mean that we have not thought through circular
            dependencies.
            """
        )
    ID_MAP[table][old_id] = new_id


def fix_datetime_fields(data: TableData, table: TableName) -> None:
    for item in data[table]:
        for field_name in DATE_FIELDS[table]:
            if item[field_name] is not None:
                item[field_name] = datetime.fromtimestamp(item[field_name], tz=timezone.utc)


def fix_upload_links(data: TableData, message_table: TableName) -> None:
    """
    Because the URLs for uploaded files encode the realm ID of the
    organization being imported (which is only determined at import
    time), we need to rewrite the URLs of links to uploaded files
    during the import process.

    Applied to attachments path_id found in messages of zerver_message and zerver_scheduledmessage tables.
    """
    for message in data[message_table]:
        if message["has_attachment"] is True:
            for attachment_path in message_id_to_attachments[message_table][message["id"]]:
                old_path = path_maps["new_attachment_path_to_old_path"][attachment_path]
                message["content"] = message["content"].replace(old_path, attachment_path)

                if message["rendered_content"]:
                    message["rendered_content"] = message["rendered_content"].replace(
                        old_path, attachment_path
                    )


def fix_stream_permission_group_settings(
    data: TableData, system_groups_name_dict: dict[str, NamedUserGroup]
) -> None:
    table = get_db_table(Stream)
    for stream in data[table]:
        for setting_name in Stream.stream_permission_group_settings:
            if setting_name == "can_send_message_group" and "stream_post_policy" in stream:
                # This block is needed when importing data for Rocket.Chat.
                # While converting the data into Zulip supported format,
                # stream_post_policy for read-only Rocket.Chat channel is
                # set to STREAM_POST_POLICY_MODERATORS and so we need to
                # set the can_send_message_group setting accordingly.
                if stream["stream_post_policy"] == Stream.STREAM_POST_POLICY_MODERATORS:
                    stream[setting_name] = system_groups_name_dict[SystemGroups.MODERATORS]
                else:
                    stream[setting_name] = get_stream_permission_default_group(
                        setting_name, system_groups_name_dict
                    )

                # Delete the stream_post_policy once can_send_message_group
                # field is set correctly.
                del stream["stream_post_policy"]

                continue

            stream[setting_name] = get_stream_permission_default_group(
                setting_name, system_groups_name_dict
            )


def create_subscription_events(data: TableData, realm_id: int) -> None:
    """
    When the export data doesn't contain the table `zerver_realmauditlog`,
    this function creates RealmAuditLog objects for `subscription_created`
    type event for all the existing Stream subscriptions.

    This is needed for all the export tools which do not include the
    table `zerver_realmauditlog` (e.g. Slack) because the appropriate
    data about when a user was subscribed is not exported by the third-party
    service.
    """
    all_subscription_logs = []

    event_last_message_id = get_last_message_id()
    event_time = timezone_now()

    recipient_id_to_stream_id = {
        d["id"]: d["type_id"] for d in data["zerver_recipient"] if d["type"] == Recipient.STREAM
    }

    for sub in data["zerver_subscription"]:
        recipient_id = sub["recipient_id"]
        stream_id = recipient_id_to_stream_id.get(recipient_id)

        if stream_id is None:
            continue

        user_id = sub["user_profile_id"]

        all_subscription_logs.append(
            RealmAuditLog(
                realm_id=realm_id,
                acting_user_id=user_id,
                modified_user_id=user_id,
                modified_stream_id=stream_id,
                event_last_message_id=event_last_message_id,
                event_time=event_time,
                event_type=AuditLogEventType.SUBSCRIPTION_CREATED,
            )
        )
    RealmAuditLog.objects.bulk_create(all_subscription_logs)


def fix_service_tokens(data: TableData, table: TableName) -> None:
    """
    The tokens in the services are created by 'generate_api_key'.
    As the tokens are unique, they should be re-created for the imports.
    """
    for item in data[table]:
        item["token"] = generate_api_key()


def process_direct_message_group_hash(data: TableData, table: TableName) -> None:
    """
    Build new direct message group hashes with the updated ids of the users
    """
    for direct_message_group in data[table]:
        user_id_list = id_map_to_list["huddle_to_user_list"][direct_message_group["id"]]
        direct_message_group["huddle_hash"] = get_direct_message_group_hash(user_id_list)


def get_direct_message_groups_from_subscription(data: TableData, table: TableName) -> None:
    """
    Extract the IDs of the user_profiles involved in a direct message group from
    the subscription object
    This helps to generate a unique direct message group hash from the updated
    user_profile ids
    """
    id_map_to_list["huddle_to_user_list"] = {
        value: [] for value in ID_MAP["recipient_to_huddle_map"].values()
    }

    for subscription in data[table]:
        if subscription["recipient"] in ID_MAP["recipient_to_huddle_map"]:
            direct_message_group_id = ID_MAP["recipient_to_huddle_map"][subscription["recipient"]]
            id_map_to_list["huddle_to_user_list"][direct_message_group_id].append(
                subscription["user_profile_id"]
            )


def fix_customprofilefield(data: TableData) -> None:
    """
    In CustomProfileField with 'field_type' like 'USER', the IDs need to be
    re-mapped.
    """
    field_type_USER_ids = {
        item["id"]
        for item in data["zerver_customprofilefield"]
        if item["field_type"] == CustomProfileField.USER
    }

    for item in data["zerver_customprofilefieldvalue"]:
        if item["field_id"] in field_type_USER_ids:
            old_user_id_list = orjson.loads(item["value"])

            new_id_list = re_map_foreign_keys_many_to_many_internal(
                table="zerver_customprofilefieldvalue",
                field_name="value",
                related_table="user_profile",
                old_id_list=old_user_id_list,
            )
            item["value"] = orjson.dumps(new_id_list).decode()


def fix_message_rendered_content(
    realm: Realm,
    sender_map: dict[int, Record],
    messages: list[Record],
    content_key: str = "content",
    rendered_content_key: str = "rendered_content",
) -> None:
    """
    This function sets the rendered_content of the messages we're importing.
    """
    for message in messages:
        if content_key not in message:
            # Message-edit entries include topic moves, which don't
            # have any content changes to process.
            continue

        if message[rendered_content_key] is not None:
            # For Zulip->Zulip imports, we use the original rendered
            # Markdown; this avoids issues where e.g. a mention can no
            # longer render properly because a user has changed their
            # name.
            #
            # However, we still need to update the data-user-id and
            # similar values stored on mentions, stream mentions, and
            # similar syntax in the rendered HTML.
            soup = BeautifulSoup(message[rendered_content_key], "html.parser")

            user_mentions = soup.find_all("span", {"class": "user-mention"})
            if len(user_mentions) != 0:
                user_id_map = ID_MAP["user_profile"]
                for mention in user_mentions:
                    if not mention.has_attr("data-user-id"):
                        # Legacy mentions don't have a data-user-id
                        # field; we should just import them
                        # unmodified.
                        continue
                    if mention["data-user-id"] == "*":
                        # No rewriting is required for wildcard mentions
                        continue
                    old_user_id = int(mention["data-user-id"])
                    if old_user_id in user_id_map:
                        mention["data-user-id"] = str(user_id_map[old_user_id])
                message[rendered_content_key] = str(soup)

            stream_mentions = soup.find_all("a", {"class": "stream"})
            if len(stream_mentions) != 0:
                stream_id_map = ID_MAP["stream"]
                for mention in stream_mentions:
                    old_stream_id = int(mention["data-stream-id"])
                    if old_stream_id in stream_id_map:
                        mention["data-stream-id"] = str(stream_id_map[old_stream_id])
                message[rendered_content_key] = str(soup)

            user_group_mentions = soup.find_all("span", {"class": "user-group-mention"})
            if len(user_group_mentions) != 0:
                user_group_id_map = ID_MAP["usergroup"]
                for mention in user_group_mentions:
                    old_user_group_id = int(mention["data-user-group-id"])
                    if old_user_group_id in user_group_id_map:
                        mention["data-user-group-id"] = str(user_group_id_map[old_user_group_id])
                message[rendered_content_key] = str(soup)

            # Enqueue thumbnailing of all thumbnails in the message.
            # We do this without taking a lock on the ImageAttachment
            # rows, because the race here is that the images
            # referenced by this message were encountered previously,
            # and are currently being thumbnailed -- which will
            # worst-case result in the images being enqueued a second
            # time, and a no-op when those are processed.  The return
            # value will also be out of date -- but that is irrelevant
            # in this use case.
            get_user_upload_previews(realm.id, message[content_key])

            continue

        try:
            content = message[content_key]

            sender_id = message["sender_id"]
            sender = sender_map[sender_id]
            sent_by_bot = sender["is_bot"]
            translate_emoticons = sender["translate_emoticons"]

            # We don't handle alert words on import from third-party
            # platforms, since they generally don't have an "alert
            # words" type feature, and notifications aren't important anyway.
            realm_alert_words_automaton = None

            # This also enqueues thumbnailing for images that are referenced
            rendered_content = markdown_convert(
                content=content,
                realm_alert_words_automaton=realm_alert_words_automaton,
                message_realm=realm,
                sent_by_bot=sent_by_bot,
                translate_emoticons=translate_emoticons,
            ).rendered_content

            message[rendered_content_key] = rendered_content
            if "scheduled_timestamp" not in message:
                # This logic runs also for ScheduledMessage, which doesn't use
                # the rendered_content_version field.
                message["rendered_content_version"] = markdown_version
        except Exception:
            # This generally happens with two possible causes:
            # * rendering Markdown throwing an uncaught exception
            # * rendering Markdown failing with the exception being
            #   caught in Markdown (which then returns None, causing the
            #   rendered_content assert above to fire).
            logging.warning(
                "Error in Markdown rendering for message ID %s; continuing", message["id"]
            )


def fix_message_edit_history(
    realm: Realm, sender_map: dict[int, Record], messages: list[Record]
) -> None:
    user_id_map = ID_MAP["user_profile"]
    for message in messages:
        edit_history_json = message.get("edit_history")
        if not edit_history_json:
            continue

        edit_history = orjson.loads(edit_history_json)
        for edit_history_message_dict in edit_history:
            edit_history_message_dict["user_id"] = user_id_map[edit_history_message_dict["user_id"]]

        fix_message_rendered_content(
            realm,
            sender_map,
            messages=edit_history,
            content_key="prev_content",
            rendered_content_key="prev_rendered_content",
        )

        message["edit_history"] = orjson.dumps(edit_history).decode()


def current_table_ids(data: TableData, table: TableName) -> list[int]:
    """
    Returns the ids present in the current table
    """
    return [item["id"] for item in data[table]]


def idseq(model_class: Any, cursor: CursorWrapper) -> str:
    sequences = connection.introspection.get_sequences(cursor, model_class._meta.db_table)
    for sequence in sequences:
        if sequence["column"] == "id":
            return sequence["name"]
    raise Exception(f"No sequence found for 'id' of {model_class}")


def allocate_ids(model_class: Any, count: int) -> list[int]:
    """
    Increases the sequence number for a given table by the amount of objects being
    imported into that table. Hence, this gives a reserved range of IDs to import the
    converted Slack objects into the tables.
    """
    with connection.cursor() as cursor:
        sequence = idseq(model_class, cursor)
        cursor.execute("select nextval(%s) from generate_series(1, %s)", [sequence, count])
        query = cursor.fetchall()  # Each element in the result is a tuple like (5,)

    # convert List[Tuple[int]] to List[int]
    return [item[0] for item in query]


def convert_to_id_fields(data: TableData, table: TableName, field_name: Field) -> None:
    """
    When Django gives us dict objects via model_to_dict, the foreign
    key fields are `foo`, but we want `foo_id` for the bulk insert.
    This function handles the simple case where we simply rename
    the fields.  For cases where we need to munge ids in the
    database, see re_map_foreign_keys.
    """
    for item in data[table]:
        item[field_name + "_id"] = item[field_name]
        del item[field_name]


def re_map_foreign_keys(
    data: TableData,
    table: TableName,
    field_name: Field,
    related_table: TableName,
    verbose: bool = False,
    id_field: bool = False,
    recipient_field: bool = False,
) -> None:
    """
    This is a wrapper function for all the realm data tables
    and only avatar and attachment records need to be passed through the internal function
    because of the difference in data format (TableData corresponding to realm data tables
    and List[Record] corresponding to the avatar and attachment records)
    """

    # See comments in bulk_import_user_message_data.
    assert related_table != "usermessage"

    re_map_foreign_keys_internal(
        data[table],
        table,
        field_name,
        related_table,
        verbose,
        id_field,
        recipient_field,
    )


def re_map_foreign_keys_internal(
    data_table: list[Record],
    table: TableName,
    field_name: Field,
    related_table: TableName,
    verbose: bool = False,
    id_field: bool = False,
    recipient_field: bool = False,
) -> None:
    """
    We occasionally need to assign new ids to rows during the
    import/export process, to accommodate things like existing rows
    already being in tables.  See bulk_import_client for more context.

    The tricky part is making sure that foreign key references
    are in sync with the new ids, and this fixer function does
    the re-mapping.  (It also appends `_id` to the field.)
    """
    lookup_table = ID_MAP[related_table]
    for item in data_table:
        old_id = item[field_name]
        if recipient_field:
            if related_table == "stream" and item["type"] == 2:
                pass
            elif related_table == "user_profile" and item["type"] == 1:
                pass
            elif related_table == "huddle" and item["type"] == 3:
                # save the recipient id with the direct message group id, so that
                # we can extract the user_profile ids involved in a direct message
                # group with the help of the subscription object
                # check function 'get_direct_message_groups_from_subscription'
                ID_MAP["recipient_to_huddle_map"][item["id"]] = lookup_table[old_id]
            else:
                continue
        old_id = item[field_name]
        if old_id in lookup_table:
            new_id = lookup_table[old_id]
            if verbose:
                logging.info(
                    "Remapping %s %s from %s to %s", table, field_name + "_id", old_id, new_id
                )
        else:
            new_id = old_id
        if not id_field:
            item[field_name + "_id"] = new_id
            del item[field_name]
        else:
            item[field_name] = new_id


def re_map_realm_emoji_codes(data: TableData, *, table_name: str) -> None:
    """
    Some tables, including Reaction and UserStatus, contain a form of
    foreign key reference to the RealmEmoji table in the form of
    `str(realm_emoji.id)` when `reaction_type="realm_emoji"`.

    See the block comment for emoji_code in the AbstractEmoji
    definition for more details.
    """
    realm_emoji_dct = {}

    for row in data["zerver_realmemoji"]:
        realm_emoji_dct[row["id"]] = row

    for row in data[table_name]:
        if row["reaction_type"] == Reaction.REALM_EMOJI:
            old_realm_emoji_id = int(row["emoji_code"])

            # Fail hard here if we didn't map correctly here
            new_realm_emoji_id = ID_MAP["realmemoji"][old_realm_emoji_id]

            # This is a very important sanity check.
            realm_emoji_row = realm_emoji_dct[new_realm_emoji_id]
            assert realm_emoji_row["name"] == row["emoji_name"]

            # Now update emoji_code to the new id.
            row["emoji_code"] = str(new_realm_emoji_id)


def re_map_foreign_keys_many_to_many(
    data: TableData,
    table: TableName,
    field_name: Field,
    related_table: TableName,
    verbose: bool = False,
) -> None:
    """
    We need to assign new ids to rows during the import/export
    process.

    The tricky part is making sure that foreign key references
    are in sync with the new ids, and this wrapper function does
    the re-mapping only for ManyToMany fields.
    """
    for item in data[table]:
        old_id_list = item[field_name]
        new_id_list = re_map_foreign_keys_many_to_many_internal(
            table, field_name, related_table, old_id_list, verbose
        )
        item[field_name] = new_id_list
        del item[field_name]


def re_map_foreign_keys_many_to_many_internal(
    table: TableName,
    field_name: Field,
    related_table: TableName,
    old_id_list: list[int],
    verbose: bool = False,
) -> list[int]:
    """
    This is an internal function for tables with ManyToMany fields,
    which takes the old ID list of the ManyToMany relation and returns the
    new updated ID list.
    """
    lookup_table = ID_MAP[related_table]
    new_id_list = []
    for old_id in old_id_list:
        if old_id in lookup_table:
            new_id = lookup_table[old_id]
            if verbose:
                logging.info(
                    "Remapping %s %s from %s to %s", table, field_name + "_id", old_id, new_id
                )
        else:
            new_id = old_id
        new_id_list.append(new_id)
    return new_id_list


def fix_bitfield_keys(data: TableData, table: TableName, field_name: Field) -> None:
    for item in data[table]:
        item[field_name] = item[field_name + "_mask"]
        del item[field_name + "_mask"]


def remove_denormalized_recipient_column_from_data(data: TableData) -> None:
    """
    The recipient column shouldn't be imported, we'll set the correct values
    when Recipient table gets imported.
    """
    for stream_dict in data["zerver_stream"]:
        if "recipient" in stream_dict:
            del stream_dict["recipient"]

    for user_profile_dict in data["zerver_userprofile"]:
        if "recipient" in user_profile_dict:
            del user_profile_dict["recipient"]

    for direct_message_group_dict in data["zerver_huddle"]:
        if "recipient" in direct_message_group_dict:
            del direct_message_group_dict["recipient"]


def get_db_table(model_class: Any) -> str:
    """E.g. (RealmDomain -> 'zerver_realmdomain')"""
    return model_class._meta.db_table


def update_model_ids(model: Any, data: TableData, related_table: TableName) -> None:
    table = get_db_table(model)

    # Important: remapping usermessage rows is
    # not only unnecessary, it's expensive and can cause
    # memory errors. We don't even use ids from ID_MAP.
    assert table != "usermessage"

    old_id_list = current_table_ids(data, table)
    allocated_id_list = allocate_ids(model, len(data[table]))
    for item in range(len(data[table])):
        update_id_map(related_table, old_id_list[item], allocated_id_list[item])
    re_map_foreign_keys(data, table, "id", related_table=related_table, id_field=True)


def bulk_import_user_message_data(data: TableData, dump_file_id: int) -> None:
    model = UserMessage
    table = "zerver_usermessage"
    lst = data[table]

    # IMPORTANT NOTE: We do not use any primary id
    # data from either the import itself or ID_MAP.
    # We let the DB itself generate ids.  Note that
    # no tables use user_message.id as a foreign key,
    # so we can safely avoid all re-mapping complexity.

    def process_batch(items: list[dict[str, Any]]) -> None:
        ums = [
            UserMessageLite(
                user_profile_id=item["user_profile_id"],
                message_id=item["message_id"],
                flags=item["flags"],
            )
            for item in items
        ]
        bulk_insert_ums(ums)

    chunk_size = 10000

    process_list_in_batches(
        lst=lst,
        chunk_size=chunk_size,
        process_batch=process_batch,
    )

    logging.info("Successfully imported %s from %s[%s].", model, table, dump_file_id)


def bulk_import_model(data: TableData, model: Any, dump_file_id: str | None = None) -> None:
    table = get_db_table(model)
    # TODO, deprecate dump_file_id
    model.objects.bulk_create(model(**item) for item in data[table])
    if dump_file_id is None:
        logging.info("Successfully imported %s from %s.", model, table)
    else:
        logging.info("Successfully imported %s from %s[%s].", model, table, dump_file_id)


def bulk_import_named_user_groups(data: TableData) -> None:
    vals = [
        (
            group["usergroup_ptr_id"],
            group["realm_for_sharding_id"],
            group["name"],
            group["description"],
            group["is_system_group"],
            group["can_add_members_group_id"],
            group["can_join_group_id"],
            group["can_leave_group_id"],
            group["can_manage_group_id"],
            group["can_mention_group_id"],
            group["can_remove_members_group_id"],
            group["deactivated"],
            group["date_created"],
        )
        for group in data["zerver_namedusergroup"]
    ]

    query = SQL(
        """
        INSERT INTO zerver_namedusergroup (usergroup_ptr_id, realm_id, name, description, is_system_group, can_add_members_group_id, can_join_group_id,  can_leave_group_id, can_manage_group_id, can_mention_group_id, can_remove_members_group_id, deactivated, date_created)
        VALUES %s
        """
    )
    with connection.cursor() as cursor:
        execute_values(cursor.cursor, query, vals)


# Client is a table shared by multiple realms, so in order to
# correctly import multiple realms into the same server, we need to
# check if a Client object already exists, and so we need to support
# remap all Client IDs to the values in the new DB.
def bulk_import_client(data: TableData, model: Any, table: TableName) -> None:
    for item in data[table]:
        try:
            client = Client.objects.get(name=item["name"])
        except Client.DoesNotExist:
            client = Client.objects.create(name=item["name"])
        update_id_map(table="client", old_id=item["id"], new_id=client.id)


def fix_subscriptions_is_user_active_column(
    data: TableData, user_profiles: list[UserProfile], crossrealm_user_ids: set[int]
) -> None:
    table = get_db_table(Subscription)
    user_id_to_active_status = {user.id: user.is_active for user in user_profiles}
    for sub in data[table]:
        if sub["user_profile_id"] in crossrealm_user_ids:
            sub["is_user_active"] = True
        else:
            sub["is_user_active"] = user_id_to_active_status[sub["user_profile_id"]]


def process_avatars(record: dict[str, Any]) -> None:
    if not record["s3_path"].endswith(".original"):
        return None
    user_profile = get_user_profile_by_id(record["user_profile_id"])
    if settings.LOCAL_AVATARS_DIR is not None:
        avatar_path = user_avatar_base_path_from_ids(
            user_profile.id, user_profile.avatar_version, record["realm_id"]
        )
        medium_file_path = os.path.join(settings.LOCAL_AVATARS_DIR, avatar_path) + "-medium.png"
        if os.path.exists(medium_file_path):
            # We remove the image here primarily to deal with
            # issues when running the import script multiple
            # times in development (where one might reuse the
            # same realm ID from a previous iteration).
            os.remove(medium_file_path)
    try:
        ensure_avatar_image(user_profile=user_profile, medium=True)
        if record.get("importer_should_thumbnail"):
            ensure_avatar_image(user_profile=user_profile)
    except BadImageError:
        logging.warning(
            "Could not thumbnail avatar image for user %s; ignoring",
            user_profile.id,
        )
        # Delete the record of the avatar to avoid 404s.
        do_change_avatar_fields(user_profile, UserProfile.AVATAR_FROM_GRAVATAR, acting_user=None)


def process_emojis(
    import_dir: str,
    default_user_profile_id: int | None,
    filename_to_has_original: dict[str, bool],
    record: dict[str, Any],
) -> None:
    # 3rd party exports may not provide .original files. In that case we want to just
    # treat whatever file we have as the original.
    should_use_as_original = not filename_to_has_original[record["file_name"]]
    if not (record["s3_path"].endswith(".original") or should_use_as_original):
        return

    if "author_id" in record and record["author_id"] is not None:
        user_profile = get_user_profile_by_id(record["author_id"])
    else:
        assert default_user_profile_id is not None
        user_profile = get_user_profile_by_id(default_user_profile_id)

    # file_name has the proper file extension without the
    # .original suffix.
    # application/octet-stream will be rejected by upload_emoji_image,
    # but it's easier to use it here as the sensible default value
    # and let upload_emoji_image figure out the exact error; or handle
    # the file somehow anyway if it's ever changed to do that.
    content_type = guess_type(record["file_name"])[0] or "application/octet-stream"
    emoji_import_data_file_dath = os.path.join(import_dir, record["path"])
    with open(emoji_import_data_file_dath, "rb") as f:
        try:
            # This will overwrite the files that got copied to the appropriate paths
            # for emojis (whether in S3 or in the local uploads dir), ensuring to
            # thumbnail them and generate stills for animated emojis.
            is_animated = upload_emoji_image(f, record["file_name"], user_profile, content_type)
        except BadImageError:
            logging.warning(
                "Could not thumbnail emoji image %s; ignoring",
                record["s3_path"],
            )
            # TODO:: should we delete the RealmEmoji object, or keep it with the files
            # that did get copied; even though they do generate this error?
            return

    if is_animated and not record.get("deactivated", False):
        # We only update the is_animated field if the emoji is not deactivated.
        # That's because among deactivated emojis (name, realm_id) may not be
        # unique, making the implementation here a bit hairier.
        # Anyway, for Zulip exports, is_animated should be set correctly from the start,
        # while 3rd party exports don't use the deactivated field, so this shouldn't
        # particularly matter.
        RealmEmoji.objects.filter(
            file_name=record["file_name"], realm_id=user_profile.realm_id, deactivated=False
        ).update(is_animated=True)


def import_uploads(
    realm: Realm,
    import_dir: Path,
    processes: int,
    default_user_profile_id: int | None = None,
    processing_avatars: bool = False,
    processing_emojis: bool = False,
    processing_realm_icons: bool = False,
) -> None:
    if processing_avatars and processing_emojis:
        raise AssertionError("Cannot import avatars and emojis at the same time!")
    if processing_avatars:
        logging.info("Importing avatars")
    elif processing_emojis:
        logging.info("Importing emojis")
    elif processing_realm_icons:
        logging.info("Importing realm icons and logos")
    else:
        logging.info("Importing uploaded files")

    records_filename = os.path.join(import_dir, "records.json")
    with open(records_filename, "rb") as records_file:
        records: list[dict[str, Any]] = orjson.loads(records_file.read())
    timestamp = datetime_to_timestamp(timezone_now())

    re_map_foreign_keys_internal(
        records, "records", "realm_id", related_table="realm", id_field=True
    )
    if not processing_emojis and not processing_realm_icons:
        re_map_foreign_keys_internal(
            records, "records", "user_profile_id", related_table="user_profile", id_field=True
        )
    if processing_emojis:
        # We need to build a mapping telling us which emojis have an .original file.
        # This will be used when thumbnailing them later, to know whether we have that
        # file available or whether we should just treat the regular image as the original
        # for thumbnailing.
        filename_to_has_original = {record["file_name"]: False for record in records}
        for record in records:
            if record["s3_path"].endswith(".original"):
                filename_to_has_original[record["file_name"]] = True

        if records and "author" in records[0]:
            # This condition only guarantees author field appears in the generated
            # records. Potentially the value of it might be None though. In that
            # case, this will be ignored by the remap below.
            # Any code further down the codepath that wants to use the author value
            # needs to be mindful of it potentially being None and use a fallback
            # value, most likely default_user_profile_id being the right choice.
            re_map_foreign_keys_internal(
                records, "records", "author", related_table="user_profile", id_field=False
            )

    s3_uploads = settings.LOCAL_UPLOADS_DIR is None

    if s3_uploads:
        if processing_avatars or processing_emojis or processing_realm_icons:
            bucket_name = settings.S3_AVATAR_BUCKET
        else:
            bucket_name = settings.S3_AUTH_UPLOADS_BUCKET
        bucket = get_bucket(bucket_name)

    for count, record in enumerate(records, 1):
        if processing_avatars:
            # For avatars, we need to rehash the user ID with the
            # new server's avatar salt
            relative_path = user_avatar_base_path_from_ids(
                record["user_profile_id"], record["avatar_version"], record["realm_id"]
            )
            if record["s3_path"].endswith(".original"):
                relative_path += ".original"
            else:
                relative_path = upload_backend.get_avatar_path(relative_path, medium=False)
        elif processing_emojis:
            # For emojis we follow the function 'upload_emoji_image'
            relative_path = RealmEmoji.PATH_ID_TEMPLATE.format(
                realm_id=record["realm_id"], emoji_file_name=record["file_name"]
            )
            if record["s3_path"].endswith(".original"):
                relative_path += ".original"
            record["last_modified"] = timestamp
        elif processing_realm_icons:
            icon_name = os.path.basename(record["path"])
            relative_path = os.path.join(str(record["realm_id"]), "realm", icon_name)
            record["last_modified"] = timestamp
        else:
            # This relative_path is basically the new location of the file,
            # which will later be copied from its original location as
            # specified in record["s3_path"].
            relative_path = upload_backend.generate_message_upload_path(
                str(record["realm_id"]), sanitize_name(os.path.basename(record["path"]))
            )
            path_maps["old_attachment_path_to_new_path"][record["s3_path"]] = relative_path
            path_maps["new_attachment_path_to_old_path"][relative_path] = record["s3_path"]
            path_maps["new_attachment_path_to_local_data_path"][relative_path] = os.path.join(
                import_dir, record["path"]
            )

        if s3_uploads:
            key = bucket.Object(relative_path)
            metadata = {}
            if "user_profile_id" not in record:
                # This should never happen for uploads or avatars; if
                # so, it is an error, default_user_profile_id will be
                # None, and we assert.  For emoji / realm icons, we
                # fall back to default_user_profile_id.
                assert default_user_profile_id is not None
                metadata["user_profile_id"] = str(default_user_profile_id)
            else:
                user_profile_id = int(record["user_profile_id"])
                # Support email gateway bot and other cross-realm messages
                if user_profile_id in ID_MAP["user_profile"]:
                    logging.info("Uploaded by ID mapped user: %s!", user_profile_id)
                    user_profile_id = ID_MAP["user_profile"][user_profile_id]
                user_profile = get_user_profile_by_id(user_profile_id)
                metadata["user_profile_id"] = str(user_profile.id)

            if "last_modified" in record:
                metadata["orig_last_modified"] = str(record["last_modified"])
            metadata["realm_id"] = str(record["realm_id"])

            # Zulip exports will always have a content-type, but third-party exports might not.
            content_type = record.get("content_type")
            if content_type is None:
                content_type = guess_type(record["s3_path"])[0]
                if content_type is None:
                    # This is the default for unknown data.  Note that
                    # for `.original` files, this is the value we'll
                    # set; that is OK, because those are never served
                    # directly anyway.
                    content_type = "application/octet-stream"

            key.upload_file(
                Filename=os.path.join(import_dir, record["path"]),
                ExtraArgs={"ContentType": content_type, "Metadata": metadata},
            )
        else:
            assert settings.LOCAL_UPLOADS_DIR is not None
            assert settings.LOCAL_AVATARS_DIR is not None
            assert settings.LOCAL_FILES_DIR is not None
            if processing_avatars or processing_emojis or processing_realm_icons:
                file_path = os.path.join(settings.LOCAL_AVATARS_DIR, relative_path)
            else:
                file_path = os.path.join(settings.LOCAL_FILES_DIR, relative_path)
            orig_file_path = os.path.join(import_dir, record["path"])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            shutil.copy(orig_file_path, file_path)

        if count % 1000 == 0:
            logging.info("Processed %s/%s uploads", count, len(records))

    if processing_avatars or processing_emojis:
        if processing_avatars:
            process_func = process_avatars
        else:
            assert processing_emojis

            process_func = partial(
                process_emojis,
                import_dir,
                default_user_profile_id,
                filename_to_has_original,
            )

        # Ensure that we have medium-size avatar images for every
        # avatar and properly thumbnailed emojis with stills (for animated emoji).
        # TODO: This implementation is hacky, both in that it
        # does get_user_profile_by_id for each user, and in that it
        # might be better to require the export to just have these.
        if processes == 1:
            for record in records:
                process_func(record)
        else:
            connection.close()
            _cache = cache._cache  # type: ignore[attr-defined] # not in stubs
            assert isinstance(_cache, bmemcached.Client)
            _cache.disconnect_all()
            with ProcessPoolExecutor(max_workers=processes) as executor:
                for future in as_completed(
                    executor.submit(process_func, record) for record in records
                ):
                    future.result()


def disable_restricted_authentication_methods(data: TableData) -> None:
    """
    Should run only with settings.BILLING_ENABLED. Ensures that we only
    enable authentication methods that are available without needing a plan.
    If the organization upgrades to a paid plan, or gets a sponsorship,
    they can enable the restricted authentication methods in their settings.
    """
    realm_authentication_methods = data["zerver_realmauthenticationmethod"]
    non_restricted_methods = []
    for auth_method in realm_authentication_methods:
        if AUTH_BACKEND_NAME_MAP[auth_method["name"]].available_for_cloud_plans is None:
            non_restricted_methods.append(auth_method)
        else:
            logging.warning("Dropped restricted authentication method: %s", auth_method["name"])

    data["zerver_realmauthenticationmethod"] = non_restricted_methods


# Importing data suffers from a difficult ordering problem because of
# models that reference each other circularly.  Here is a correct order.
#
# (Note that this list is not exhaustive and only talks about the main,
# most important models. There's a bunch of minor models that are handled
# separately and not mentioned here - but following the principle that we
# have to import the dependencies first.)
#
# * Client [no deps]
# * Realm [-announcements_streams,-group_permissions]
# * UserGroup
# * Stream [only depends on realm]
# * Realm's announcements_streams and group_permissions
# * UserProfile, in order by ID to avoid bot loop issues
# * Now can do all realm_tables
# * DirectMessageGroup
# * Recipient
# * Subscription
# * Message
# * UserMessage
#
# Because the Python object => JSON conversion process is not fully
# faithful, we have to use a set of fixers (e.g. on DateTime objects
# and foreign keys) to do the import correctly.
def do_import_realm(import_dir: Path, subdomain: str, processes: int = 1) -> Realm:
    logging.info("Importing realm dump %s", import_dir)
    if not os.path.exists(import_dir):
        raise Exception("Missing import directory!")

    migration_status_filename = os.path.join(import_dir, "migration_status.json")
    if not os.path.exists(migration_status_filename):
        raise Exception(
            "Missing migration_status.json file! Make sure you're using the same Zulip version as the exported realm."
        )
    logging.info("Checking migration status of exported realm")
    with open(migration_status_filename) as f:
        migration_status: MigrationStatusJson = orjson.loads(f.read())
    check_migration_status(migration_status)

    realm_data_filename = os.path.join(import_dir, "realm.json")
    if not os.path.exists(realm_data_filename):
        raise Exception("Missing realm.json file!")

    if not server_initialized():
        create_internal_realm()

    logging.info("Importing realm data from %s", realm_data_filename)
    with open(realm_data_filename, "rb") as f:
        data = orjson.loads(f.read())

    # Export data has an extra key with info about which app it's from.
    import_source = data.pop("import_source")

    # Merge in zerver_userprofile_mirrordummy
    data["zerver_userprofile"] += data["zerver_userprofile_mirrordummy"]
    del data["zerver_userprofile_mirrordummy"]
    data["zerver_userprofile"].sort(key=lambda r: r["id"])

    remove_denormalized_recipient_column_from_data(data)

    sort_by_date = data.get("sort_by_date", False)

    bulk_import_client(data, Client, "zerver_client")

    # Remap the user IDs for notification_bot and friends to their
    # appropriate IDs on this server
    internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
    crossrealm_user_ids = set()
    for item in data["zerver_userprofile_crossrealm"]:
        logging.info(
            "Adding to ID map: %s %s",
            item["id"],
            get_system_bot(item["email"], internal_realm.id).id,
        )
        new_user_id = get_system_bot(item["email"], internal_realm.id).id
        update_id_map(table="user_profile", old_id=item["id"], new_id=new_user_id)
        crossrealm_user_ids.add(new_user_id)
        new_recipient_id = Recipient.objects.get(type=Recipient.PERSONAL, type_id=new_user_id).id
        update_id_map(table="recipient", old_id=item["recipient_id"], new_id=new_recipient_id)

    # We first do a pass of updating model IDs for the cluster of
    # major models that have foreign keys into each other.
    # TODO: Should we just do this for all tables at the start?
    update_model_ids(Realm, data, "realm")
    update_model_ids(Stream, data, "stream")
    update_model_ids(UserProfile, data, "user_profile")
    if "zerver_usergroup" in data:
        update_model_ids(UserGroup, data, "usergroup")
    if "zerver_presencesequence" in data:
        update_model_ids(PresenceSequence, data, "presencesequence")
    if "zerver_channelfolder" in data:
        update_model_ids(ChannelFolder, data, "channelfolder")

    # Now we prepare to import the Realm table
    re_map_foreign_keys(data, "zerver_realm", "moderation_request_channel", related_table="stream")
    re_map_foreign_keys(
        data, "zerver_realm", "new_stream_announcements_stream", related_table="stream"
    )
    re_map_foreign_keys(data, "zerver_realm", "signup_announcements_stream", related_table="stream")
    re_map_foreign_keys(
        data, "zerver_realm", "zulip_update_announcements_stream", related_table="stream"
    )
    if "zerver_usergroup" in data:
        for setting_name in Realm.REALM_PERMISSION_GROUP_SETTINGS:
            re_map_foreign_keys(data, "zerver_realm", setting_name, related_table="usergroup")

    fix_datetime_fields(data, "zerver_realm")
    # Fix realm subdomain information
    data["zerver_realm"][0]["string_id"] = subdomain
    data["zerver_realm"][0]["name"] = subdomain

    # Create the realm, but mark it deactivated for now, while we
    # import the supporting data structures, which may take a bit.
    realm_properties = dict(**data["zerver_realm"][0])
    realm_properties["deactivated"] = True

    # Initialize whether we expect push notifications to work.
    realm_properties["push_notifications_enabled"] = sends_notifications_directly()

    with transaction.atomic(durable=True):
        realm = Realm(**realm_properties)
        if "zerver_usergroup" not in data:
            # For now a dummy value of -1 is given to groups fields which
            # is changed later before the transaction is committed.
            for setting_name in Realm.REALM_PERMISSION_GROUP_SETTINGS:
                setattr(realm, setting_name + "_id", -1)

        realm.save()

        if "zerver_presencesequence" in data:
            re_map_foreign_keys(data, "zerver_presencesequence", "realm", related_table="realm")
            bulk_import_model(data, PresenceSequence)
        else:
            # We need to enforce the invariant that every realm must have a PresenceSequence.
            PresenceSequence.objects.create(realm=realm, last_update_id=0)

        named_user_group_id_to_creator_id = {}
        if "zerver_usergroup" in data:
            re_map_foreign_keys(data, "zerver_usergroup", "realm", related_table="realm")
            bulk_import_model(data, UserGroup)

            if "zerver_namedusergroup" in data:
                re_map_foreign_keys(
                    data, "zerver_namedusergroup", "creator", related_table="user_profile"
                )
                fix_datetime_fields(data, "zerver_namedusergroup")
                re_map_foreign_keys(
                    data, "zerver_namedusergroup", "usergroup_ptr", related_table="usergroup"
                )
                re_map_foreign_keys(
                    data, "zerver_namedusergroup", "realm_for_sharding", related_table="realm"
                )
                for group in data["zerver_namedusergroup"]:
                    creator_id = group.pop("creator_id", None)
                    named_user_group_id_to_creator_id[group["id"]] = creator_id
                for setting_name in NamedUserGroup.GROUP_PERMISSION_SETTINGS:
                    re_map_foreign_keys(
                        data,
                        "zerver_namedusergroup",
                        setting_name,
                        related_table="usergroup",
                    )
                bulk_import_named_user_groups(data)

        # We expect Zulip server exports to contain these system groups,
        # this logic here is needed to handle the imports from other services.
        system_groups_name_dict: dict[str, NamedUserGroup] | None = None
        if "zerver_usergroup" not in data:
            system_groups_name_dict = create_system_user_groups_for_realm(realm)

        channel_folder_id_to_creator_id = {}
        if "zerver_channelfolder" in data:
            fix_datetime_fields(data, "zerver_channelfolder")
            re_map_foreign_keys(data, "zerver_channelfolder", "realm", related_table="realm")
            re_map_foreign_keys(
                data, "zerver_channelfolder", "creator", related_table="user_profile"
            )

            # To correctly set .folder attribute for streams, we
            # would need to create ChannelFolder objects before
            # creating Stream objects. So we retain the .creator
            # attribute data in a mapping, so that we can update it
            # once the UserProfile objects are created.
            for channel_folder in data["zerver_channelfolder"]:
                creator_id = channel_folder.pop("creator_id", None)
                channel_folder_id_to_creator_id[channel_folder["id"]] = creator_id

            bulk_import_model(data, ChannelFolder)

        # Email tokens will automatically be randomly generated when the
        # Stream objects are created by Django.
        fix_datetime_fields(data, "zerver_stream")
        re_map_foreign_keys(data, "zerver_stream", "realm", related_table="realm")

        re_map_foreign_keys(data, "zerver_stream", "creator", related_table="user_profile")
        re_map_foreign_keys(data, "zerver_stream", "folder", related_table="channelfolder")

        # There's a circular dependency between Stream and UserProfile due to
        # the .creator attribute. We untangle it by first remembering the creator_id
        # for all the streams and then removing those fields from the data.
        # That allows us to successfully import streams, and then later after users
        # are imported, we can set the .creator_id for all these streams correctly.
        stream_id_to_creator_id = {}
        for stream in data["zerver_stream"]:
            creator_id = stream.pop("creator_id", None)
            stream_id_to_creator_id[stream["id"]] = creator_id

        if system_groups_name_dict is not None:
            # Because the system user groups are missing, we manually set up
            # the defaults for stream permission settings for all the
            # streams.
            fix_stream_permission_group_settings(data, system_groups_name_dict)
        else:
            for setting_name in Stream.stream_permission_group_settings:
                re_map_foreign_keys(data, "zerver_stream", setting_name, related_table="usergroup")
        # Handle rendering of stream descriptions for import from non-Zulip
        for stream in data["zerver_stream"]:
            stream["rendered_description"] = render_stream_description(stream["description"], realm)
            stream["name"] = stream["name"][: Stream.MAX_NAME_LENGTH]
        bulk_import_model(data, Stream)

        if "zerver_usergroup" not in data:
            set_default_for_realm_permission_group_settings(realm)

    # To remap foreign key for UserProfile.last_active_message_id
    update_message_foreign_keys(import_dir=import_dir, sort_by_date=sort_by_date)

    fix_datetime_fields(data, "zerver_userprofile")
    re_map_foreign_keys(data, "zerver_userprofile", "realm", related_table="realm")
    re_map_foreign_keys(data, "zerver_userprofile", "bot_owner", related_table="user_profile")
    re_map_foreign_keys(
        data, "zerver_userprofile", "default_sending_stream", related_table="stream"
    )
    re_map_foreign_keys(
        data, "zerver_userprofile", "default_events_register_stream", related_table="stream"
    )
    re_map_foreign_keys(
        data, "zerver_userprofile", "last_active_message_id", related_table="message", id_field=True
    )
    for user_profile_dict in data["zerver_userprofile"]:
        user_profile_dict["password"] = None
        user_profile_dict["api_key"] = generate_api_key()
        # Since Zulip doesn't use these permissions, drop them
        del user_profile_dict["user_permissions"]
        del user_profile_dict["groups"]
        # The short_name field is obsolete in Zulip, but it's
        # convenient for third party exports to populate it.
        if "short_name" in user_profile_dict:
            del user_profile_dict["short_name"]

    user_profiles = [UserProfile(**item) for item in data["zerver_userprofile"]]
    for user_profile in user_profiles:
        # Validate both email attributes to be defensive
        # against any malformed data, where .delivery_email
        # might be set correctly, but .email not.
        validate_email(user_profile.delivery_email)
        validate_email(user_profile.email)
        user_profile.set_unusable_password()
        user_profile.tos_version = UserProfile.TOS_VERSION_BEFORE_FIRST_LOGIN
    UserProfile.objects.bulk_create(user_profiles)

    # UserProfiles have been loaded, so now we're ready to set .creator_id
    # for streams based on the mapping we saved earlier.
    streams = Stream.objects.filter(id__in=stream_id_to_creator_id.keys())
    for stream in streams:
        stream.creator_id = stream_id_to_creator_id[stream.id]
    Stream.objects.bulk_update(streams, ["creator_id"])

    channel_folders = ChannelFolder.objects.filter(id__in=channel_folder_id_to_creator_id.keys())
    for channel_folder in channel_folders:
        channel_folder.creator_id = channel_folder_id_to_creator_id[channel_folder.id]
    ChannelFolder.objects.bulk_update(channel_folders, ["creator_id"])

    if "zerver_namedusergroup" in data:
        # UserProfiles have been loaded, so now we're ready to set .creator_id
        # for groups based on the mapping we saved earlier.
        named_user_groups = NamedUserGroup.objects.filter(
            id__in=named_user_group_id_to_creator_id.keys()
        )
        for group in named_user_groups:
            group.creator_id = named_user_group_id_to_creator_id[group.id]
        NamedUserGroup.objects.bulk_update(named_user_groups, ["creator_id"])

    re_map_foreign_keys(data, "zerver_defaultstream", "stream", related_table="stream")
    re_map_foreign_keys(data, "zerver_realmemoji", "author", related_table="user_profile")

    if settings.BILLING_ENABLED:
        disable_restricted_authentication_methods(data)

    for table, model, related_table in realm_tables:
        re_map_foreign_keys(data, table, "realm", related_table="realm")
        update_model_ids(model, data, related_table)
        bulk_import_model(data, model)

    # Ensure RealmEmoji get the .author set to a reasonable default, if the value
    # wasn't provided in the import data.
    first_user_profile = (
        UserProfile.objects.filter(realm=realm, is_active=True, role=UserProfile.ROLE_REALM_OWNER)
        .order_by("id")
        .first()
    )
    for realm_emoji in RealmEmoji.objects.filter(realm=realm):
        if realm_emoji.author_id is None:
            assert first_user_profile is not None
            realm_emoji.author_id = first_user_profile.id
            realm_emoji.save(update_fields=["author_id"])

    if "zerver_huddle" in data:
        update_model_ids(DirectMessageGroup, data, "huddle")
        # We don't import DirectMessageGroup yet, since we don't have
        # the data to compute direct message group hashes until we've
        # imported some of the tables below.
        # We can't get direct message group hashes without processing
        # subscriptions first, during which
        # get_direct_message_groups_from_subscription is called.

    re_map_foreign_keys(
        data,
        "zerver_recipient",
        "type_id",
        related_table="stream",
        recipient_field=True,
        id_field=True,
    )
    re_map_foreign_keys(
        data,
        "zerver_recipient",
        "type_id",
        related_table="user_profile",
        recipient_field=True,
        id_field=True,
    )
    re_map_foreign_keys(
        data,
        "zerver_recipient",
        "type_id",
        related_table="huddle",
        recipient_field=True,
        id_field=True,
    )
    update_model_ids(Recipient, data, "recipient")
    bulk_import_model(data, Recipient)
    bulk_set_users_or_streams_recipient_fields(Stream, Stream.objects.filter(realm=realm))
    bulk_set_users_or_streams_recipient_fields(UserProfile, UserProfile.objects.filter(realm=realm))

    re_map_foreign_keys(data, "zerver_subscription", "user_profile", related_table="user_profile")
    get_direct_message_groups_from_subscription(data, "zerver_subscription")
    re_map_foreign_keys(data, "zerver_subscription", "recipient", related_table="recipient")
    update_model_ids(Subscription, data, "subscription")
    fix_subscriptions_is_user_active_column(data, user_profiles, crossrealm_user_ids)
    bulk_import_model(data, Subscription)

    if "zerver_realmauditlog" in data:
        fix_datetime_fields(data, "zerver_realmauditlog")
        re_map_foreign_keys(data, "zerver_realmauditlog", "realm", related_table="realm")
        re_map_foreign_keys(
            data, "zerver_realmauditlog", "modified_user", related_table="user_profile"
        )
        re_map_foreign_keys(
            data, "zerver_realmauditlog", "acting_user", related_table="user_profile"
        )
        re_map_foreign_keys(data, "zerver_realmauditlog", "modified_stream", related_table="stream")
        re_map_foreign_keys(
            data, "zerver_realmauditlog", "modified_user_group", related_table="usergroup"
        )
        re_map_foreign_keys(
            data, "zerver_realmauditlog", "modified_channel_folder", related_table="channelfolder"
        )
        update_model_ids(RealmAuditLog, data, related_table="realmauditlog")
        bulk_import_model(data, RealmAuditLog)
    else:
        logging.info("about to call create_subscription_events")
        create_subscription_events(
            data=data,
            realm_id=realm.id,
        )
        logging.info("done with create_subscription_events")

    # Ensure the invariant that there's always a realm-creation audit
    # log event, even if the export was generated by an export tool
    # that does not create RealmAuditLog events.
    if not RealmAuditLog.objects.filter(
        realm=realm, event_type=AuditLogEventType.REALM_CREATED
    ).exists():
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=AuditLogEventType.REALM_CREATED,
            event_time=realm.date_created,
            # Mark these as backfilled, since they weren't created
            # when the realm was actually created, and thus do not
            # have the creating user associated with them.
            backfilled=True,
        )

    if "zerver_huddle" in data:
        process_direct_message_group_hash(data, "zerver_huddle")
        bulk_import_model(data, DirectMessageGroup)
        for direct_message_group in DirectMessageGroup.objects.filter(recipient=None):
            recipient = Recipient.objects.get(
                type=Recipient.DIRECT_MESSAGE_GROUP, type_id=direct_message_group.id
            )
            direct_message_group.recipient = recipient
            direct_message_group.save(update_fields=["recipient"])

    if "zerver_alertword" in data:
        re_map_foreign_keys(data, "zerver_alertword", "user_profile", related_table="user_profile")
        re_map_foreign_keys(data, "zerver_alertword", "realm", related_table="realm")
        update_model_ids(AlertWord, data, "alertword")
        bulk_import_model(data, AlertWord)

    if "zerver_navigationview" in data:
        re_map_foreign_keys(data, "zerver_navigationview", "user", related_table="user_profile")
        update_model_ids(NavigationView, data, "navigationview")
        bulk_import_model(data, NavigationView)

    if "zerver_savedsnippet" in data:
        fix_datetime_fields(data, "zerver_savedsnippet")
        re_map_foreign_keys(
            data, "zerver_savedsnippet", "user_profile", related_table="user_profile"
        )
        re_map_foreign_keys(data, "zerver_savedsnippet", "realm", related_table="realm")
        update_model_ids(SavedSnippet, data, "savedsnippet")
        bulk_import_model(data, SavedSnippet)

    if "zerver_onboardingstep" in data:
        fix_datetime_fields(data, "zerver_onboardingstep")
        re_map_foreign_keys(data, "zerver_onboardingstep", "user", related_table="user_profile")
        update_model_ids(OnboardingStep, data, "onboardingstep")
        bulk_import_model(data, OnboardingStep)

    if "zerver_usertopic" in data:
        fix_datetime_fields(data, "zerver_usertopic")
        re_map_foreign_keys(data, "zerver_usertopic", "user_profile", related_table="user_profile")
        re_map_foreign_keys(data, "zerver_usertopic", "stream", related_table="stream")
        re_map_foreign_keys(data, "zerver_usertopic", "recipient", related_table="recipient")
        update_model_ids(UserTopic, data, "usertopic")
        bulk_import_model(data, UserTopic)

    if "zerver_muteduser" in data:
        fix_datetime_fields(data, "zerver_muteduser")
        re_map_foreign_keys(data, "zerver_muteduser", "user_profile", related_table="user_profile")
        re_map_foreign_keys(data, "zerver_muteduser", "muted_user", related_table="user_profile")
        update_model_ids(MutedUser, data, "muteduser")
        bulk_import_model(data, MutedUser)

    if "zerver_service" in data:
        re_map_foreign_keys(data, "zerver_service", "user_profile", related_table="user_profile")
        fix_service_tokens(data, "zerver_service")
        update_model_ids(Service, data, "service")
        bulk_import_model(data, Service)

    if "zerver_usergroup" in data:
        re_map_foreign_keys(
            data, "zerver_usergroupmembership", "user_group", related_table="usergroup"
        )
        re_map_foreign_keys(
            data, "zerver_usergroupmembership", "user_profile", related_table="user_profile"
        )
        update_model_ids(UserGroupMembership, data, "usergroupmembership")
        bulk_import_model(data, UserGroupMembership)

        re_map_foreign_keys(
            data, "zerver_groupgroupmembership", "supergroup", related_table="usergroup"
        )
        re_map_foreign_keys(
            data, "zerver_groupgroupmembership", "subgroup", related_table="usergroup"
        )
        update_model_ids(GroupGroupMembership, data, "groupgroupmembership")
        bulk_import_model(data, GroupGroupMembership)

    # We expect Zulip server exports to contain UserGroupMembership objects
    # for system groups, this logic here is needed to handle the imports from
    # other services.
    if system_groups_name_dict is not None:
        add_users_to_system_user_groups(realm, user_profiles, system_groups_name_dict)

    if "zerver_botstoragedata" in data:
        re_map_foreign_keys(
            data, "zerver_botstoragedata", "bot_profile", related_table="user_profile"
        )
        update_model_ids(BotStorageData, data, "botstoragedata")
        bulk_import_model(data, BotStorageData)

    if "zerver_botconfigdata" in data:
        re_map_foreign_keys(
            data, "zerver_botconfigdata", "bot_profile", related_table="user_profile"
        )
        update_model_ids(BotConfigData, data, "botconfigdata")
        bulk_import_model(data, BotConfigData)

    if "zerver_realmuserdefault" in data:
        re_map_foreign_keys(data, "zerver_realmuserdefault", "realm", related_table="realm")
        update_model_ids(RealmUserDefault, data, "realmuserdefault")
        bulk_import_model(data, RealmUserDefault)

    # Create RealmUserDefault table with default values if not created
    # already from the import data; this can happen when importing
    # data from another product.
    if not RealmUserDefault.objects.filter(realm=realm).exists():
        RealmUserDefault.objects.create(realm=realm)

    fix_datetime_fields(data, "zerver_userpresence")
    re_map_foreign_keys(data, "zerver_userpresence", "user_profile", related_table="user_profile")
    re_map_foreign_keys(data, "zerver_userpresence", "realm", related_table="realm")
    update_model_ids(UserPresence, data, "user_presence")
    bulk_import_model(data, UserPresence)

    fix_datetime_fields(data, "zerver_useractivity")
    re_map_foreign_keys(data, "zerver_useractivity", "user_profile", related_table="user_profile")
    re_map_foreign_keys(data, "zerver_useractivity", "client", related_table="client")
    update_model_ids(UserActivity, data, "useractivity")
    bulk_import_model(data, UserActivity)

    fix_datetime_fields(data, "zerver_useractivityinterval")
    re_map_foreign_keys(
        data, "zerver_useractivityinterval", "user_profile", related_table="user_profile"
    )
    update_model_ids(UserActivityInterval, data, "useractivityinterval")
    bulk_import_model(data, UserActivityInterval)

    re_map_foreign_keys(data, "zerver_customprofilefield", "realm", related_table="realm")
    update_model_ids(CustomProfileField, data, related_table="customprofilefield")
    bulk_import_model(data, CustomProfileField)

    re_map_foreign_keys(
        data, "zerver_customprofilefieldvalue", "user_profile", related_table="user_profile"
    )
    re_map_foreign_keys(
        data, "zerver_customprofilefieldvalue", "field", related_table="customprofilefield"
    )
    fix_customprofilefield(data)
    update_model_ids(CustomProfileFieldValue, data, related_table="customprofilefieldvalue")
    bulk_import_model(data, CustomProfileFieldValue)

    # Import uploaded files and avatars
    import_uploads(
        realm,
        os.path.join(import_dir, "avatars"),
        processes,
        default_user_profile_id=None,  # Fail if there is no user set
        processing_avatars=True,
    )
    import_uploads(
        realm,
        os.path.join(import_dir, "uploads"),
        processes,
        default_user_profile_id=None,  # Fail if there is no user set
    )

    # We need to have this check as the emoji files may not
    # be present in import data from other services.
    if os.path.exists(os.path.join(import_dir, "emoji")):
        import_uploads(
            realm,
            os.path.join(import_dir, "emoji"),
            processes,
            default_user_profile_id=first_user_profile.id if first_user_profile else None,
            processing_emojis=True,
        )

    if os.path.exists(os.path.join(import_dir, "realm_icons")):
        import_uploads(
            realm,
            os.path.join(import_dir, "realm_icons"),
            processes,
            default_user_profile_id=first_user_profile.id if first_user_profile else None,
            processing_realm_icons=True,
        )

    sender_map = {user["id"]: user for user in data["zerver_userprofile"]}

    # TODO: de-dup how we read these json files.
    attachments_file = os.path.join(import_dir, "attachment.json")
    if not os.path.exists(attachments_file):
        raise Exception("Missing attachment.json file!")

    # Important: map_messages_to_attachments should be called before fix_upload_links
    # which is called by import_message_data and another for zerver_scheduledmessage.
    with open(attachments_file, "rb") as f:
        attachment_data = orjson.loads(f.read())

    # We need to import ImageAttachments before messages, as the message rendering logic
    # checks for existence of ImageAttachment records to determine if HTML content for image
    # preview needs to be added to a message.
    # In order for ImageAttachments to be correctly created, we need to know the new path_ids
    # and content_types of the attachments.
    #
    # Begin by fixing up the Attachment data.
    fix_attachments_data(attachment_data)
    # Now we're ready create ImageAttachment rows; thumbnailing is
    # enqueued when the messages are rendered, to prevent races if the
    # thumbnailing can run _during_ rendering.  This order ensures
    # that during message import, rendered_content will be generated
    # with placeholders for all image previews, which are updated into
    # their thumbnails as thumbnailing comes along after.  The
    # important detail here is that **only** ImageAttachment rows (not
    # Attachment rows) are ready (or needed) at the time of message
    # import.
    create_image_attachments(realm, attachment_data)
    map_messages_to_attachments(attachment_data)

    # Import zerver_message and zerver_usermessage
    import_message_data(realm=realm, sender_map=sender_map, import_dir=import_dir)

    if "zerver_onboardingusermessage" in data:
        fix_bitfield_keys(data, "zerver_onboardingusermessage", "flags")
        re_map_foreign_keys(data, "zerver_onboardingusermessage", "realm", related_table="realm")
        re_map_foreign_keys(
            data, "zerver_onboardingusermessage", "message", related_table="message"
        )
        update_model_ids(OnboardingUserMessage, data, "onboardingusermessage")
        bulk_import_model(data, OnboardingUserMessage)

    if "zerver_scheduledmessage" in data:
        fix_datetime_fields(data, "zerver_scheduledmessage")
        re_map_foreign_keys(data, "zerver_scheduledmessage", "sender", related_table="user_profile")
        re_map_foreign_keys(data, "zerver_scheduledmessage", "recipient", related_table="recipient")
        re_map_foreign_keys(
            data, "zerver_scheduledmessage", "sending_client", related_table="client"
        )
        re_map_foreign_keys(data, "zerver_scheduledmessage", "stream", related_table="stream")
        re_map_foreign_keys(data, "zerver_scheduledmessage", "realm", related_table="realm")
        re_map_foreign_keys(
            data, "zerver_scheduledmessage", "delivered_message", related_table="message"
        )

        fix_upload_links(data, "zerver_scheduledmessage")

        fix_message_rendered_content(
            realm=realm,
            sender_map=sender_map,
            messages=data["zerver_scheduledmessage"],
        )

        update_model_ids(ScheduledMessage, data, "scheduledmessage")
        bulk_import_model(data, ScheduledMessage)

    re_map_foreign_keys(data, "zerver_reaction", "message", related_table="message")
    re_map_foreign_keys(data, "zerver_reaction", "user_profile", related_table="user_profile")
    re_map_realm_emoji_codes(data, table_name="zerver_reaction")
    update_model_ids(Reaction, data, "reaction")
    bulk_import_model(data, Reaction)

    # Similarly, we need to recalculate the first_message_id for stream objects.
    update_first_message_id_query = SQL(
        """
    UPDATE zerver_stream
    SET first_message_id = subquery.first_message_id
    FROM (
        SELECT r.type_id id, min(m.id) first_message_id
        FROM zerver_message m
        JOIN zerver_recipient r ON
        r.id = m.recipient_id
        WHERE r.type = 2 AND m.realm_id = %(realm_id)s
        GROUP BY r.type_id
        ) AS subquery
    WHERE zerver_stream.id = subquery.id
    """
    )

    with connection.cursor() as cursor:
        cursor.execute(update_first_message_id_query, {"realm_id": realm.id})

    if "zerver_userstatus" in data:
        fix_datetime_fields(data, "zerver_userstatus")
        re_map_foreign_keys(data, "zerver_userstatus", "user_profile", related_table="user_profile")
        re_map_foreign_keys(data, "zerver_userstatus", "client", related_table="client")
        update_model_ids(UserStatus, data, "userstatus")
        re_map_realm_emoji_codes(data, table_name="zerver_userstatus")
        bulk_import_model(data, UserStatus)

    # Do attachments AFTER message data is loaded.
    logging.info("Importing attachment data from %s", attachments_file)
    import_attachments(attachment_data)

    # Import the analytics file.
    import_analytics_data(
        realm=realm, import_dir=import_dir, crossrealm_user_ids=crossrealm_user_ids
    )

    if settings.BILLING_ENABLED:
        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)
    else:
        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_SELF_HOSTED, acting_user=None)

    # Activate the realm
    realm.deactivated = data["zerver_realm"][0]["deactivated"]
    realm.save()

    # If realm is active, update the stream active status.
    if not realm.deactivated:
        number_of_days = Stream.LAST_ACTIVITY_DAYS_BEFORE_FOR_ACTIVE
        date_days_ago = timezone_now() - timedelta(days=number_of_days)
        update_stream_active_status_for_realm(realm, date_days_ago)

    # This helps to have an accurate user count data for the billing
    # system if someone tries to signup just after doing import.
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=AuditLogEventType.REALM_IMPORTED,
        event_time=timezone_now(),
        extra_data={
            RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(realm),
            "import_source": import_source,
        },
    )

    # Ask the push notifications service if this realm can send
    # notifications, if we're using it. Needs to happen after the
    # Realm object is reactivated.
    maybe_enqueue_audit_log_upload(realm)

    is_realm_imported_from_other_zulip_server = import_source == "zulip"
    if not is_realm_imported_from_other_zulip_server:
        if None in [realm.new_stream_announcements_stream, realm.zulip_update_announcements_stream]:
            fallback_default_announcements_channel = (
                Stream.objects.filter(realm=realm, deactivated=False)
                .annotate(
                    num_subs=Count(
                        "recipient__subscription", filter=Q(recipient__subscription__active=True)
                    )
                )
                .order_by("-num_subs", "id")
                .first()
            )
            if (
                fallback_default_announcements_channel is not None
                and realm.new_stream_announcements_stream is None
            ):
                do_set_realm_new_stream_announcements_stream(
                    realm,
                    fallback_default_announcements_channel,
                    fallback_default_announcements_channel.id,
                    acting_user=None,
                )
            if (
                fallback_default_announcements_channel is not None
                and realm.zulip_update_announcements_stream is None
            ):
                do_set_realm_zulip_update_announcements_stream(
                    realm,
                    fallback_default_announcements_channel,
                    fallback_default_announcements_channel.id,
                    acting_user=None,
                )

        # If the export was NOT generated by another zulip server, the
        # 'zulip_update_announcements_level' is set to None by default.
        # Set it to the latest level to avoid receiving older update messages.
        send_zulip_update_announcements_to_realm(realm, skip_delay=False)
        # Exports from others tools naturally don't have the initial Welcome Bot
        # messages for users, so we need to create them.
        #
        # Such exports use the default general-type channel such as "general" for
        # announcements - which happens to be also the channel we want for the initial messages.
        send_zulip_initial_messages_after_import(
            realm, target_channel=realm.zulip_update_announcements_stream
        )

    return realm


def send_zulip_initial_messages_after_import(realm: Realm, target_channel: Stream | None) -> None:
    if target_channel is not None:
        send_initial_realm_messages(
            realm,
            override_channel_name_map={
                OnboardingMessageTypeEnum.moving_messages: target_channel.name,
                OnboardingMessageTypeEnum.welcome_to_zulip: target_channel.name,
                OnboardingMessageTypeEnum.experiments: target_channel.name,
                OnboardingMessageTypeEnum.greetings: target_channel.name,
                # We shouldn't encourage people to start random threads in their organization's #general-type channel,
                # so we skip sending these initial messages at all.
                OnboardingMessageTypeEnum.start_conversation: None,
            },
        )

    BATCH_SIZE = 1000
    lower_bound_id = 0

    # We use batching to avoid fetching a large number of UserProfile objects
    # in one go, if the realm is huge.
    # TODO: Instead, it would be much more efficient to just generate these messages
    # on the fly for each imported user during their first login.
    while user_profiles_batch := list(
        UserProfile.objects.filter(
            realm=realm, is_active=True, is_bot=False, id__gt=lower_bound_id
        ).order_by("id")[:BATCH_SIZE]
    ):
        for user_profile in user_profiles_batch:
            send_initial_direct_message(user_profile)
        lower_bound_id = user_profiles_batch[-1].id


def update_message_foreign_keys(import_dir: Path, sort_by_date: bool) -> None:
    old_id_list = get_incoming_message_ids(
        import_dir=import_dir,
        sort_by_date=sort_by_date,
    )

    count = len(old_id_list)

    new_id_list = allocate_ids(model_class=Message, count=count)

    for old_id, new_id in zip(old_id_list, new_id_list, strict=False):
        update_id_map(
            table="message",
            old_id=old_id,
            new_id=new_id,
        )

    # We don't touch user_message keys here; that happens later when
    # we're actually read the files a second time to get actual data.


def get_incoming_message_ids(import_dir: Path, sort_by_date: bool) -> list[int]:
    """
    This function reads in our entire collection of message
    ids, which can be millions of integers for some installations.
    And then we sort the list.  This is necessary to ensure
    that the sort order of incoming ids matches the sort order
    of date_sent, which isn't always guaranteed by our
    utilities that convert third party chat data.  We also
    need to move our ids to a new range if we're dealing
    with a server that has data for other realms.
    """

    if sort_by_date:
        tups: list[tuple[int, int]] = []
    else:
        message_ids: list[int] = []

    dump_file_id = 1
    while True:
        message_filename = os.path.join(import_dir, f"messages-{dump_file_id:06}.json")
        if not os.path.exists(message_filename):
            break

        with open(message_filename, "rb") as f:
            data = orjson.loads(f.read())

        # Aggressively free up memory.
        del data["zerver_usermessage"]

        for row in data["zerver_message"]:
            # We truncate date_sent to int to theoretically
            # save memory and speed up the sort.  For
            # Zulip-to-Zulip imports, the
            # message_id will generally be a good tiebreaker.
            # If we occasionally misorder the ids for two
            # messages from the same second, it's not the
            # end of the world, as it's likely those messages
            # arrived to the original server in somewhat
            # arbitrary order.

            message_id = row["id"]

            if sort_by_date:
                date_sent = int(row["date_sent"])
                tup = (date_sent, message_id)
                tups.append(tup)
            else:
                message_ids.append(message_id)

        dump_file_id += 1

    if sort_by_date:
        tups.sort()
        message_ids = [tup[1] for tup in tups]

    return message_ids


def import_message_data(realm: Realm, sender_map: dict[int, Record], import_dir: Path) -> None:
    dump_file_id = 1
    while True:
        message_filename = os.path.join(import_dir, f"messages-{dump_file_id:06}.json")
        if not os.path.exists(message_filename):
            break

        with open(message_filename, "rb") as f:
            data = orjson.loads(f.read())

        logging.info("Importing message dump %s", message_filename)
        re_map_foreign_keys(data, "zerver_message", "sender", related_table="user_profile")
        re_map_foreign_keys(data, "zerver_message", "recipient", related_table="recipient")
        re_map_foreign_keys(data, "zerver_message", "sending_client", related_table="client")
        fix_datetime_fields(data, "zerver_message")
        # Parser to update message content with the updated attachment URLs
        fix_upload_links(data, "zerver_message")

        # We already create mappings for zerver_message ids
        # in update_message_foreign_keys(), so here we simply
        # apply them.
        message_id_map = ID_MAP["message"]
        for row in data["zerver_message"]:
            del row["realm"]
            row["realm_id"] = realm.id
            row["id"] = message_id_map[row["id"]]

        for row in data["zerver_usermessage"]:
            assert row["message"] in message_id_map

        fix_message_rendered_content(
            realm=realm,
            sender_map=sender_map,
            messages=data["zerver_message"],
        )
        logging.info("Successfully rendered Markdown for message batch")

        fix_message_edit_history(
            realm=realm, sender_map=sender_map, messages=data["zerver_message"]
        )
        # A LOT HAPPENS HERE.
        # This is where we actually import the message data.
        bulk_import_model(data, Message)

        # Due to the structure of these message chunks, we're
        # guaranteed to have already imported all the Message objects
        # for this batch of UserMessage objects.
        re_map_foreign_keys(data, "zerver_usermessage", "message", related_table="message")
        re_map_foreign_keys(
            data, "zerver_usermessage", "user_profile", related_table="user_profile"
        )
        fix_bitfield_keys(data, "zerver_usermessage", "flags")

        bulk_import_user_message_data(data, dump_file_id)
        dump_file_id += 1


def import_attachments(data: TableData) -> None:
    # Clean up the data in zerver_attachment that is not
    # relevant to our many-to-many import.
    fix_datetime_fields(data, "zerver_attachment")
    re_map_foreign_keys(data, "zerver_attachment", "owner", related_table="user_profile")
    re_map_foreign_keys(data, "zerver_attachment", "realm", related_table="realm")

    # Configure ourselves.  Django models many-to-many (m2m)
    # relations asymmetrically. The parent here refers to the
    # Model that has the ManyToManyField.  It is assumed here
    # the child models have been loaded, but we are in turn
    # responsible for loading the parents and the m2m rows.
    parent_model = Attachment
    parent_db_table_name = "zerver_attachment"
    parent_singular = "attachment"
    parent_id = "attachment_id"

    update_model_ids(parent_model, data, "attachment")
    # We don't bulk_import_model yet, because we need to first compute
    # the many-to-many for this table.

    # First, build our list of many-to-many (m2m) rows.
    # We do this in a slightly convoluted way to anticipate
    # a future where we may need to call re_map_foreign_keys.

    def format_m2m_data(
        child_singular: str, child_plural: str, m2m_table_name: str, child_id: str
    ) -> tuple[str, list[Record], str]:
        m2m_rows = [
            {
                parent_singular: parent_row["id"],
                # child_singular will generally match the model name (e.g. Message, ScheduledMessage)
                # after lowercasing, and that's what we enter as ID_MAP keys, so this should be
                # a reasonable assumption to make.
                child_singular: ID_MAP[child_singular][fk_id],
            }
            for parent_row in data[parent_db_table_name]
            for fk_id in parent_row[child_plural]
        ]

        # Create our table data for insert.
        m2m_data: TableData = {m2m_table_name: m2m_rows}
        convert_to_id_fields(m2m_data, m2m_table_name, parent_singular)
        convert_to_id_fields(m2m_data, m2m_table_name, child_singular)
        m2m_rows = m2m_data[m2m_table_name]

        # Next, delete out our child data from the parent rows.
        for parent_row in data[parent_db_table_name]:
            del parent_row[child_plural]

        return m2m_table_name, m2m_rows, child_id

    messages_m2m_tuple = format_m2m_data(
        "message", "messages", "zerver_attachment_messages", "message_id"
    )
    scheduled_messages_m2m_tuple = format_m2m_data(
        "scheduledmessage",
        "scheduled_messages",
        "zerver_attachment_scheduled_messages",
        "scheduledmessage_id",
    )

    # Next, load the parent rows.
    bulk_import_model(data, parent_model)

    # Now, go back to our m2m rows.
    # TODO: Do this the kosher Django way.  We may find a
    # better way to do this in Django 1.9 particularly.
    with connection.cursor() as cursor:
        for m2m_table_name, m2m_rows, child_id in [
            messages_m2m_tuple,
            scheduled_messages_m2m_tuple,
        ]:
            sql_template = SQL(
                """
                INSERT INTO {m2m_table_name} ({parent_id}, {child_id}) VALUES %s
            """
            ).format(
                m2m_table_name=Identifier(m2m_table_name),
                parent_id=Identifier(parent_id),
                child_id=Identifier(child_id),
            )
            tups = [(row[parent_id], row[child_id]) for row in m2m_rows]
            execute_values(cursor.cursor, sql_template, tups)

            logging.info("Successfully imported M2M table %s", m2m_table_name)


def fix_attachments_data(attachment_data: TableData) -> None:
    for attachment in attachment_data["zerver_attachment"]:
        attachment["path_id"] = path_maps["old_attachment_path_to_new_path"][attachment["path_id"]]

        # In the case of images, content_type needs to be set for thumbnailing.
        # Zulip exports set this, but third-party exports may not.
        if attachment.get("content_type") is None:
            guessed_content_type = guess_type(attachment["path_id"])[0]
            if guessed_content_type in THUMBNAIL_ACCEPT_IMAGE_TYPES:
                attachment["content_type"] = guessed_content_type


def create_image_attachments(realm: Realm, attachment_data: TableData) -> None:
    for attachment in attachment_data["zerver_attachment"]:
        if attachment["content_type"] not in THUMBNAIL_ACCEPT_IMAGE_TYPES:
            continue

        path_id = attachment["path_id"]
        content_type = attachment["content_type"]

        # Since we have it, use the on-disk version of the file to
        # examine the header and determine if it needs thumbnailing;
        # the actual thumbnail worker will still need to re-fetch the
        # image from S3.
        local_filename = path_maps["new_attachment_path_to_local_data_path"][path_id]
        pyvips_source = pyvips.Source.new_from_file(local_filename)
        maybe_thumbnail(pyvips_source, content_type, path_id, realm.id, skip_events=True)


def import_analytics_data(realm: Realm, import_dir: Path, crossrealm_user_ids: set[int]) -> None:
    analytics_filename = os.path.join(import_dir, "analytics.json")
    if not os.path.exists(analytics_filename):
        return

    logging.info("Importing analytics data from %s", analytics_filename)
    with open(analytics_filename, "rb") as f:
        data = orjson.loads(f.read())

    # Process the data through the fixer functions.
    fix_datetime_fields(data, "analytics_realmcount")
    re_map_foreign_keys(data, "analytics_realmcount", "realm", related_table="realm")
    update_model_ids(RealmCount, data, "analytics_realmcount")
    bulk_import_model(data, RealmCount)

    fix_datetime_fields(data, "analytics_usercount")
    re_map_foreign_keys(data, "analytics_usercount", "realm", related_table="realm")
    re_map_foreign_keys(data, "analytics_usercount", "user", related_table="user_profile")
    data["analytics_usercount"] = [
        row for row in data["analytics_usercount"] if row["user_id"] not in crossrealm_user_ids
    ]
    update_model_ids(UserCount, data, "analytics_usercount")
    bulk_import_model(data, UserCount)

    fix_datetime_fields(data, "analytics_streamcount")
    re_map_foreign_keys(data, "analytics_streamcount", "realm", related_table="realm")
    re_map_foreign_keys(data, "analytics_streamcount", "stream", related_table="stream")
    update_model_ids(StreamCount, data, "analytics_streamcount")
    bulk_import_model(data, StreamCount)


def add_users_to_system_user_groups(
    realm: Realm,
    user_profiles: list[UserProfile],
    system_groups_name_dict: dict[str, NamedUserGroup],
) -> None:
    full_members_system_group = NamedUserGroup.objects.get(
        name=SystemGroups.FULL_MEMBERS,
        realm=realm,
        is_system_group=True,
    )

    role_system_groups_dict: dict[int, NamedUserGroup] = dict()
    for role in NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP:
        group_name = NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP[role]["name"]
        role_system_groups_dict[role] = system_groups_name_dict[group_name]

    usergroup_memberships = []
    for user_profile in user_profiles:
        user_group = role_system_groups_dict[user_profile.role]
        usergroup_memberships.append(
            UserGroupMembership(user_profile=user_profile, user_group=user_group)
        )
        if user_profile.role == UserProfile.ROLE_MEMBER and not user_profile.is_provisional_member:
            usergroup_memberships.append(
                UserGroupMembership(user_profile=user_profile, user_group=full_members_system_group)
            )
    UserGroupMembership.objects.bulk_create(usergroup_memberships)
    now = timezone_now()
    RealmAuditLog.objects.bulk_create(
        RealmAuditLog(
            realm=realm,
            modified_user=membership.user_profile,
            modified_user_group=membership.user_group.named_user_group,
            event_type=AuditLogEventType.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
            event_time=now,
            acting_user=None,
        )
        for membership in usergroup_memberships
    )


ZULIP_CLOUD_ONLY_APP_NAMES = ["zilencer", "corporate"]


def check_migration_status(exported_migration_status: MigrationStatusJson) -> None:
    """
    This function checks the compatibility of an exported realm with the local
    server's migration status. It asserts that the two realms have identical
    migration statuses for both applied and on-disk migrations.

    However, it does not explicitly check the exact details of individual
    migrations, such as their dependencies, replacements (if any), or whether
    custom migrations are identical.
    """
    mismatched_migrations_log: dict[str, str] = {}
    local_migration_status = MigrationStatusJson(
        migrations_by_app=parse_migration_status(), zulip_version=ZULIP_VERSION
    )

    # Different major versions are the most common form of mismatch
    # and should get a nice error message focused on that, not
    # migrations.
    #
    # We could split on `-`, to get the maintenance release version,
    # but unless migrations are different, it should generally be safe
    # to import across minor release differences.
    exported_primary_version = exported_migration_status["zulip_version"].split(".")[0]
    local_primary_version = local_migration_status["zulip_version"].split(".")[0]
    if exported_primary_version != local_primary_version:
        raise CommandError(
            "Error: Export was generated on a different Zulip major version.\n"
            f"Export version: {exported_migration_status['zulip_version']}\n"
            f"Server version: {local_migration_status['zulip_version']}"
        )
    exported_migrations_by_app = exported_migration_status["migrations_by_app"]
    local_migrations_by_app = local_migration_status["migrations_by_app"]
    all_apps = set(exported_migrations_by_app.keys()).union(set(local_migrations_by_app.keys()))

    for app in all_apps:
        exported_app_migrations = exported_migrations_by_app.get(app)
        local_app_migrations = local_migrations_by_app.get(app)

        if app in ZULIP_CLOUD_ONLY_APP_NAMES and (
            local_app_migrations is None or exported_app_migrations is None
        ):
            # This applications are expected to be present only on
            # Zulip Cloud, so don't warn about them.
            continue

        if not exported_app_migrations:
            logging.warning("This server has '%s' app installed, but exported realm does not.", app)
        elif not local_app_migrations:
            logging.warning("Exported realm has '%s' app installed, but this server does not.", app)
        elif set(local_app_migrations) != set(exported_app_migrations):
            # We sort the list of migrations to ensure the same sets of
            # migrations don't somehow ordered differently. This has been
            # reported to happen when importing Zulip Cloud to self-host.
            #
            # The order of migrations listed in `migration_status.json`
            # don't actually matter, migrations specify which other
            # migrations they depend on.
            diff = list(
                unified_diff(
                    sorted(exported_app_migrations), sorted(local_app_migrations), lineterm="", n=1
                )
            )
            mismatched_migrations_log[f"\n'{app}' app:\n"] = "\n".join(diff[3:])

    if mismatched_migrations_log:
        # The order of the list output by the diff is nondeterministic, so the
        # error logs needs to be sorted first.
        sorted_error_log: list[str] = [
            f"{key}{value}" for key, value in sorted(mismatched_migrations_log.items())
        ]

        error_message = (
            "Error: Export was generated on a different Zulip version.\n"
            f"Export version: {exported_migration_status['zulip_version']}\n"
            f"Server version: {local_migration_status['zulip_version']}\n"
            "\n"
            "Database formats differ between the exported realm and this server.\n"
            "Printing migrations that differ between the versions:\n"
            "--- exported realm\n"
            "+++ this server"
        ) + "\n".join(sorted_error_log)
        raise CommandError(error_message)
