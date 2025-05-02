from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.channel_folders import get_channel_folder_dict, render_channel_folder_description
from zerver.models import ChannelFolder, RealmAuditLog, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def check_add_channel_folder(
    name: str, description: str, *, acting_user: UserProfile
) -> ChannelFolder:
    realm = acting_user.realm
    rendered_description = render_channel_folder_description(
        description, realm, acting_user=acting_user
    )
    channel_folder = ChannelFolder.objects.create(
        realm=realm,
        name=name,
        description=description,
        rendered_description=rendered_description,
        creator_id=acting_user.id,
    )

    creation_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=AuditLogEventType.CHANNEL_FOLDER_CREATED,
        event_time=creation_time,
        modified_channel_folder=channel_folder,
    )

    event = dict(
        type="channel_folder",
        op="add",
        channel_folder=get_channel_folder_dict(channel_folder),
    )
    send_event_on_commit(realm, event, active_user_ids(realm.id))

    return channel_folder
