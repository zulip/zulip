from typing import Annotated, Literal

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from pydantic import AfterValidator, BaseModel

from zerver.lib.types import AnonymousSettingGroupDict


def check_url(val: str) -> str:
    try:
        URLValidator()(val)
    except ValidationError:  # nocoverage
        raise AssertionError(f"{val} is not a URL")
    return val


Url = Annotated[str, AfterValidator(check_url)]


class EventAlertWords(BaseModel):
    type: Literal["alert_words"]
    alert_words: list[str]
    id: int


class AttachmentMessage(BaseModel):
    id: int
    date_sent: int


class Attachment(BaseModel):
    id: int
    name: str
    size: int
    path_id: str
    create_time: int
    messages: list[AttachmentMessage]


class EventAttachmentAdd(BaseModel):
    type: Literal["attachment"]
    op: Literal["add"]
    attachment: Attachment
    upload_space_used: int
    id: int


class AttachmentFieldForEventAttachmentRemove(BaseModel):
    id: int


class EventAttachmentRemove(BaseModel):
    type: Literal["attachment"]
    op: Literal["remove"]
    attachment: AttachmentFieldForEventAttachmentRemove
    upload_space_used: int
    id: int


class EventAttachmentUpdate(BaseModel):
    type: Literal["attachment"]
    op: Literal["update"]
    attachment: Attachment
    upload_space_used: int
    id: int


class DetailedCustomProfileCore(BaseModel):
    id: int
    type: int
    name: str
    hint: str
    field_data: str
    order: int
    required: bool
    editable_by_user: bool


class DetailedCustomProfile(DetailedCustomProfileCore):
    # TODO: fix types to avoid optional fields
    display_in_profile_summary: bool | None = None


class EventCustomProfileFields(BaseModel):
    type: Literal["custom_profile_fields"]
    fields: list[DetailedCustomProfile]
    id: int


class StreamGroup(BaseModel):
    name: str
    id: int
    description: str
    streams: list[int]


class EventDefaultStreamGroups(BaseModel):
    type: Literal["default_stream_groups"]
    default_stream_groups: list[StreamGroup]
    id: int


class EventDefaultStreams(BaseModel):
    type: Literal["default_streams"]
    default_streams: list[int]
    id: int


class EventDeleteMessageCore(BaseModel):
    type: Literal["delete_message"]
    message_type: Literal["private", "stream"]
    id: int


class EventDeleteMessage(EventDeleteMessageCore):
    # TODO: fix types to avoid optional fields
    message_id: int | None = None
    message_ids: list[int] | None = None
    stream_id: int | None = None
    topic: str | None = None


class TopicLink(BaseModel):
    text: str
    url: str


class DirectMessageDisplayRecipient(BaseModel):
    id: int
    is_mirror_dummy: bool
    email: str
    full_name: str


class MessageFieldForEventDirectMessage(BaseModel):
    avatar_url: str | None
    client: str
    content: str
    content_type: Literal["text/html"]
    id: int
    is_me_message: bool
    reactions: list[dict[str, object]]
    recipient_id: int
    sender_realm_str: str
    sender_email: str
    sender_full_name: str
    sender_id: int
    subject: str
    topic_links: list[TopicLink]
    submessages: list[dict[str, object]]
    timestamp: int
    type: str
    display_recipient: list[DirectMessageDisplayRecipient]


class EventDirectMessage(BaseModel):
    type: Literal["message"]
    flags: list[str]
    message: MessageFieldForEventDirectMessage
    id: int


class DraftFieldsCore(BaseModel):
    id: int
    type: Literal["", "private", "stream"]
    to: list[int]
    topic: str
    content: str


class DraftFields(DraftFieldsCore):
    # TODO: fix types to avoid optional fields
    timestamp: int | None = None


class EventDraftsAdd(BaseModel):
    type: Literal["drafts"]
    op: Literal["add"]
    drafts: list[DraftFields]
    id: int


class EventDraftsRemove(BaseModel):
    type: Literal["drafts"]
    op: Literal["remove"]
    draft_id: int
    id: int


class EventDraftsUpdate(BaseModel):
    type: Literal["drafts"]
    op: Literal["update"]
    draft: DraftFields
    id: int


class EventHasZoomToken(BaseModel):
    type: Literal["has_zoom_token"]
    value: bool
    id: int


class EventHeartbeat(BaseModel):
    type: Literal["heartbeat"]
    id: int


class EventInvitesChanged(BaseModel):
    type: Literal["invites_changed"]
    id: int


class MessageFieldForEventMessage(BaseModel):
    avatar_url: str | None
    client: str
    content: str
    content_type: Literal["text/html"]
    id: int
    is_me_message: bool
    reactions: list[dict[str, object]]
    recipient_id: int
    sender_realm_str: str
    sender_email: str
    sender_full_name: str
    sender_id: int
    subject: str
    topic_links: list[TopicLink]
    submessages: list[dict[str, object]]
    timestamp: int
    type: str
    display_recipient: str
    stream_id: int


class EventMessage(BaseModel):
    type: Literal["message"]
    flags: list[str]
    message: MessageFieldForEventMessage
    id: int


class EventMutedTopics(BaseModel):
    type: Literal["muted_topics"]
    muted_topics: list[tuple[str, str, int]]
    id: int


class MutedUser(BaseModel):
    id: int
    timestamp: int


class EventMutedUsers(BaseModel):
    type: Literal["muted_users"]
    muted_users: list[MutedUser]
    id: int


class OnboardingSteps(BaseModel):
    type: str
    name: str


class EventOnboardingSteps(BaseModel):
    type: Literal["onboarding_steps"]
    onboarding_steps: list[OnboardingSteps]
    id: int


class Presence(BaseModel):
    status: Literal["active", "idle"]
    timestamp: int
    client: str
    pushable: bool


class EventPresenceCore(BaseModel):
    type: Literal["presence"]
    user_id: int
    server_timestamp: float | int
    presence: dict[str, Presence]
    id: int


class EventPresence(EventPresenceCore):
    # TODO: fix types to avoid optional fields
    email: str | None = None


# Type for the legacy user field; the `user_id` field is intended to
# replace this and we expect to remove this once clients have migrated
# to support the modern API.
class ReactionLegacyUserType(BaseModel):
    email: str
    full_name: str
    user_id: int


class EventReactionAdd(BaseModel):
    type: Literal["reaction"]
    op: Literal["add"]
    message_id: int
    emoji_name: str
    emoji_code: str
    reaction_type: Literal["realm_emoji", "unicode_emoji", "zulip_extra_emoji"]
    user_id: int
    user: ReactionLegacyUserType
    id: int


class EventReactionRemove(BaseModel):
    type: Literal["reaction"]
    op: Literal["remove"]
    message_id: int
    emoji_name: str
    emoji_code: str
    reaction_type: Literal["realm_emoji", "unicode_emoji", "zulip_extra_emoji"]
    user_id: int
    user: ReactionLegacyUserType
    id: int


class BotServicesOutgoing(BaseModel):
    base_url: Url
    interface: int
    token: str


class BotServicesEmbedded(BaseModel):
    service_name: str
    config_data: dict[str, str]


class Bot(BaseModel):
    user_id: int
    api_key: str
    avatar_url: str
    bot_type: int
    default_all_public_streams: bool
    default_events_register_stream: str | None
    default_sending_stream: str | None
    email: str
    full_name: str
    is_active: bool
    owner_id: int
    services: list[BotServicesOutgoing | BotServicesEmbedded]


class EventRealmBotAdd(BaseModel):
    type: Literal["realm_bot"]
    op: Literal["add"]
    bot: Bot
    id: int


class BotTypeForDelete(BaseModel):
    user_id: int


class EventRealmBotDelete(BaseModel):
    type: Literal["realm_bot"]
    op: Literal["delete"]
    bot: BotTypeForDelete
    id: int


class BotTypeForUpdateCore(BaseModel):
    user_id: int


class BotTypeForUpdate(BotTypeForUpdateCore):
    # TODO: fix types to avoid optional fields
    api_key: str | None = None
    avatar_url: str | None = None
    default_all_public_streams: bool | None = None
    default_events_register_stream: str | None = None
    default_sending_stream: str | None = None
    full_name: str | None = None
    is_active: bool | None = None
    owner_id: int | None = None
    services: list[BotServicesOutgoing | BotServicesEmbedded] | None = None


class EventRealmBotUpdate(BaseModel):
    type: Literal["realm_bot"]
    op: Literal["update"]
    bot: BotTypeForUpdate
    id: int


class EventRealmDeactivated(BaseModel):
    type: Literal["realm"]
    op: Literal["deactivated"]
    realm_id: int
    id: int


class RealmDomain(BaseModel):
    domain: str
    allow_subdomains: bool


class EventRealmDomainsAdd(BaseModel):
    type: Literal["realm_domains"]
    op: Literal["add"]
    realm_domain: RealmDomain
    id: int


class EventRealmDomainsChange(BaseModel):
    type: Literal["realm_domains"]
    op: Literal["change"]
    realm_domain: RealmDomain
    id: int


class EventRealmDomainsRemove(BaseModel):
    type: Literal["realm_domains"]
    op: Literal["remove"]
    domain: str
    id: int


class RealmEmoji(BaseModel):
    id: str
    name: str
    source_url: str
    deactivated: bool
    author_id: int
    still_url: str | None


class EventRealmEmojiUpdate(BaseModel):
    type: Literal["realm_emoji"]
    op: Literal["update"]
    realm_emoji: dict[str, RealmEmoji]
    id: int


class EventRealmExportConsent(BaseModel):
    type: Literal["realm_export_consent"]
    user_id: int
    consented: bool
    id: int


class Export(BaseModel):
    id: int
    export_time: float | int
    acting_user_id: int
    export_url: str | None
    deleted_timestamp: float | int | None
    failed_timestamp: float | int | None
    pending: bool
    export_type: int


class EventRealmExport(BaseModel):
    type: Literal["realm_export"]
    exports: list[Export]
    id: int


class RealmLinkifier(BaseModel):
    pattern: str
    url_template: str
    id: int


class EventRealmLinkifiers(BaseModel):
    type: Literal["realm_linkifiers"]
    realm_linkifiers: list[RealmLinkifier]
    id: int


class RealmPlayground(BaseModel):
    id: int
    name: str
    pygments_language: str
    url_template: str


class EventRealmPlaygrounds(BaseModel):
    type: Literal["realm_playgrounds"]
    realm_playgrounds: list[RealmPlayground]
    id: int


class AllowMessageEditingData(BaseModel):
    allow_message_editing: bool


class AuthenticationMethodDictCore(BaseModel):
    enabled: bool
    available: bool


class AuthenticationMethodDict(AuthenticationMethodDictCore):
    # TODO: fix types to avoid optional fields
    unavailable_reason: str | None = None


class AuthenticationDict(BaseModel):
    Google: AuthenticationMethodDict
    Dev: AuthenticationMethodDict
    LDAP: AuthenticationMethodDict
    GitHub: AuthenticationMethodDict
    Email: AuthenticationMethodDict


class AuthenticationData(BaseModel):
    authentication_methods: AuthenticationDict


class IconData(BaseModel):
    icon_url: str
    icon_source: str


class LogoData(BaseModel):
    logo_url: str
    logo_source: str


class MessageContentEditLimitSecondsData(BaseModel):
    message_content_edit_limit_seconds: int | None


class NightLogoData(BaseModel):
    night_logo_url: str
    night_logo_source: str


class GroupSettingUpdateDataCore(BaseModel):
    pass


class GroupSettingUpdateData(GroupSettingUpdateDataCore):
    # TODO: fix types to avoid optional fields
    create_multiuse_invite_group: int | AnonymousSettingGroupDict | None = None
    can_access_all_users_group: int | AnonymousSettingGroupDict | None = None
    can_add_custom_emoji_group: int | AnonymousSettingGroupDict | None = None
    can_create_groups: int | AnonymousSettingGroupDict | None = None
    can_create_public_channel_group: int | AnonymousSettingGroupDict | None = None
    can_create_private_channel_group: int | AnonymousSettingGroupDict | None = None
    can_create_web_public_channel_group: int | AnonymousSettingGroupDict | None = None
    can_delete_any_message_group: int | AnonymousSettingGroupDict | None = None
    can_delete_own_message_group: int | AnonymousSettingGroupDict | None = None
    can_invite_users_group: int | AnonymousSettingGroupDict | None = None
    can_manage_all_groups: int | AnonymousSettingGroupDict | None = None
    can_move_messages_between_channels_group: int | AnonymousSettingGroupDict | None = None
    can_move_messages_between_topics_group: int | AnonymousSettingGroupDict | None = None
    direct_message_initiator_group: int | AnonymousSettingGroupDict | None = None
    direct_message_permission_group: int | AnonymousSettingGroupDict | None = None


class PlanTypeData(BaseModel):
    plan_type: int
    upload_quota_mib: int | None
    max_file_upload_size_mib: int


class EventRealmUpdateDict(BaseModel):
    type: Literal["realm"]
    op: Literal["update_dict"]
    property: Literal["default", "icon", "logo", "night_logo"]
    data: (
        AllowMessageEditingData
        | AuthenticationData
        | IconData
        | LogoData
        | MessageContentEditLimitSecondsData
        | NightLogoData
        | GroupSettingUpdateData
        | PlanTypeData
    )
    id: int


class EventRealmUpdate(BaseModel):
    type: Literal["realm"]
    op: Literal["update"]
    property: str
    value: bool | int | str
    id: int


class RealmUser(BaseModel):
    user_id: int
    email: str
    avatar_url: str | None
    avatar_version: int
    full_name: str
    is_admin: bool
    is_billing_admin: bool
    is_owner: bool
    is_bot: bool
    is_guest: bool
    role: Literal[100, 200, 300, 400, 600]
    is_active: bool
    profile_data: dict[str, dict[str, object]]
    timezone: str
    date_joined: str
    delivery_email: str | None


class EventRealmUserAdd(BaseModel):
    type: Literal["realm_user"]
    op: Literal["add"]
    person: RealmUser
    id: int


class RemovedUser(BaseModel):
    user_id: int
    full_name: str


class EventRealmUserRemove(BaseModel):
    type: Literal["realm_user"]
    op: Literal["remove"]
    person: RemovedUser
    id: int


class EventRealmUserSettingsDefaultsUpdate(BaseModel):
    type: Literal["realm_user_settings_defaults"]
    op: Literal["update"]
    property: str
    value: bool | int | str
    id: int


class PersonAvatarFields(BaseModel):
    user_id: int
    avatar_source: str
    avatar_url: str | None
    avatar_url_medium: str | None
    avatar_version: int


class PersonBotOwnerId(BaseModel):
    user_id: int
    bot_owner_id: int


class CustomProfileFieldCore(BaseModel):
    id: int
    value: str | None


class CustomProfileField(CustomProfileFieldCore):
    # TODO: fix types to avoid optional fields
    rendered_value: str | None = None


class PersonCustomProfileField(BaseModel):
    user_id: int
    custom_profile_field: CustomProfileField


class PersonDeliveryEmail(BaseModel):
    user_id: int
    delivery_email: str | None


class PersonEmail(BaseModel):
    user_id: int
    new_email: str


class PersonFullName(BaseModel):
    user_id: int
    full_name: str


class PersonIsBillingAdmin(BaseModel):
    user_id: int
    is_billing_admin: bool


class PersonRole(BaseModel):
    user_id: int
    role: Literal[100, 200, 300, 400, 600]


class PersonTimezone(BaseModel):
    user_id: int
    email: str
    timezone: str


class PersonIsActive(BaseModel):
    user_id: int
    is_active: bool


class EventRealmUserUpdate(BaseModel):
    type: Literal["realm_user"]
    op: Literal["update"]
    person: (
        PersonAvatarFields
        | PersonBotOwnerId
        | PersonCustomProfileField
        | PersonDeliveryEmail
        | PersonEmail
        | PersonFullName
        | PersonIsBillingAdmin
        | PersonRole
        | PersonTimezone
        | PersonIsActive
    )
    id: int


class EventRestart(BaseModel):
    type: Literal["restart"]
    zulip_version: str
    zulip_merge_base: str
    zulip_feature_level: int
    server_generation: int
    id: int


class SavedSnippetFields(BaseModel):
    id: int
    title: str
    content: str
    date_created: int


class EventSavedSnippetsAdd(BaseModel):
    type: Literal["saved_snippets"]
    op: Literal["add"]
    saved_snippet: SavedSnippetFields
    id: int


class EventSavedSnippetsRemove(BaseModel):
    type: Literal["saved_snippets"]
    op: Literal["remove"]
    saved_snippet_id: int
    id: int


class ScheduledMessageFieldsCore(BaseModel):
    scheduled_message_id: int
    type: Literal["private", "stream"]
    to: list[int] | int
    content: str
    rendered_content: str
    scheduled_delivery_timestamp: int
    failed: bool


class ScheduledMessageFields(ScheduledMessageFieldsCore):
    # TODO: fix types to avoid optional fields
    topic: str | None = None


class EventScheduledMessagesAdd(BaseModel):
    type: Literal["scheduled_messages"]
    op: Literal["add"]
    scheduled_messages: list[ScheduledMessageFields]
    id: int


class EventScheduledMessagesRemove(BaseModel):
    type: Literal["scheduled_messages"]
    op: Literal["remove"]
    scheduled_message_id: int
    id: int


class EventScheduledMessagesUpdate(BaseModel):
    type: Literal["scheduled_messages"]
    op: Literal["update"]
    scheduled_message: ScheduledMessageFields
    id: int


class BasicStreamFields(BaseModel):
    is_archived: bool
    can_administer_channel_group: int | AnonymousSettingGroupDict
    can_remove_subscribers_group: int | AnonymousSettingGroupDict
    can_send_message_group: int | AnonymousSettingGroupDict
    creator_id: int | None
    date_created: int
    description: str
    first_message_id: int | None
    is_recently_active: bool
    history_public_to_subscribers: bool
    invite_only: bool
    is_announcement_only: bool
    is_web_public: bool
    message_retention_days: int | None
    name: str
    rendered_description: str
    stream_id: int
    stream_post_policy: int
    stream_weekly_traffic: int | None


class EventStreamCreate(BaseModel):
    type: Literal["stream"]
    op: Literal["create"]
    streams: list[BasicStreamFields]
    id: int


class EventStreamDelete(BaseModel):
    type: Literal["stream"]
    op: Literal["delete"]
    streams: list[BasicStreamFields]
    id: int


class EventStreamUpdateCore(BaseModel):
    type: Literal["stream"]
    op: Literal["update"]
    property: str
    value: bool | int | str | AnonymousSettingGroupDict | Literal[None]
    name: str
    stream_id: int
    id: int


class EventStreamUpdate(EventStreamUpdateCore):
    # TODO: fix types to avoid optional fields
    rendered_description: str | None = None
    history_public_to_subscribers: bool | None = None
    is_web_public: bool | None = None


class EventSubmessage(BaseModel):
    type: Literal["submessage"]
    message_id: int
    submessage_id: int
    sender_id: int
    msg_type: str
    content: str
    id: int


class SingleSubscription(BaseModel):
    is_archived: bool
    can_administer_channel_group: int | AnonymousSettingGroupDict
    can_remove_subscribers_group: int | AnonymousSettingGroupDict
    can_send_message_group: int | AnonymousSettingGroupDict
    creator_id: int | None
    date_created: int
    description: str
    first_message_id: int | None
    is_recently_active: bool
    history_public_to_subscribers: bool
    invite_only: bool
    is_announcement_only: bool
    is_web_public: bool
    message_retention_days: int | None
    name: str
    rendered_description: str
    stream_id: int
    stream_post_policy: int
    stream_weekly_traffic: int | None
    audible_notifications: bool | None
    color: str
    desktop_notifications: bool | None
    email_notifications: bool | None
    in_home_view: bool
    is_muted: bool
    pin_to_top: bool
    push_notifications: bool | None
    subscribers: list[int]
    wildcard_mentions_notify: bool | None


class EventSubscriptionAdd(BaseModel):
    type: Literal["subscription"]
    op: Literal["add"]
    subscriptions: list[SingleSubscription]
    id: int


class EventSubscriptionPeerAdd(BaseModel):
    type: Literal["subscription"]
    op: Literal["peer_add"]
    user_ids: list[int]
    stream_ids: list[int]
    id: int


class EventSubscriptionPeerRemove(BaseModel):
    type: Literal["subscription"]
    op: Literal["peer_remove"]
    user_ids: list[int]
    stream_ids: list[int]
    id: int


class RemoveSub(BaseModel):
    name: str
    stream_id: int


class EventSubscriptionRemove(BaseModel):
    type: Literal["subscription"]
    op: Literal["remove"]
    subscriptions: list[RemoveSub]
    id: int


class EventSubscriptionUpdate(BaseModel):
    type: Literal["subscription"]
    op: Literal["update"]
    property: str
    stream_id: int
    value: bool | int | str
    id: int


class TypingPerson(BaseModel):
    email: str
    user_id: int


class EventTypingStartCore(BaseModel):
    type: Literal["typing"]
    op: Literal["start"]
    message_type: Literal["direct", "stream"]
    sender: TypingPerson
    id: int


class EventTypingStart(EventTypingStartCore):
    # TODO: fix types to avoid optional fields
    recipients: list[TypingPerson] | None = None
    stream_id: int | None = None
    topic: str | None = None


class EventTypingStopCore(BaseModel):
    type: Literal["typing"]
    op: Literal["stop"]
    message_type: Literal["direct", "stream"]
    sender: TypingPerson
    id: int


class EventTypingStop(EventTypingStopCore):
    # TODO: fix types to avoid optional fields
    recipients: list[TypingPerson] | None = None
    stream_id: int | None = None
    topic: str | None = None


class EventUpdateDisplaySettingsCore(BaseModel):
    type: Literal["update_display_settings"]
    setting_name: str
    setting: bool | int | str
    user: str
    id: int


class EventUpdateDisplaySettings(EventUpdateDisplaySettingsCore):
    # TODO: fix types to avoid optional fields
    language_name: str | None = None


class EventUpdateGlobalNotifications(BaseModel):
    type: Literal["update_global_notifications"]
    notification_name: str
    setting: bool | int | str
    user: str
    id: int


class EventUpdateMessageCore(BaseModel):
    type: Literal["update_message"]
    user_id: int | None
    edit_timestamp: int
    message_id: int
    flags: list[str]
    message_ids: list[int]
    rendering_only: bool
    id: int


class EventUpdateMessage(EventUpdateMessageCore):
    # TODO: fix types to avoid optional fields
    stream_id: int | None = None
    stream_name: str | None = None
    is_me_message: bool | None = None
    orig_content: str | None = None
    orig_rendered_content: str | None = None
    content: str | None = None
    rendered_content: str | None = None
    topic_links: list[TopicLink] | None = None
    subject: str | None = None
    new_stream_id: int | None = None
    propagate_mode: Literal["change_all", "change_later", "change_one"] | None = None
    orig_subject: str | None = None


class EventUpdateMessageFlagsAdd(BaseModel):
    type: Literal["update_message_flags"]
    op: Literal["add"]
    operation: Literal["add"]
    flag: str
    messages: list[int]
    all: bool
    id: int


class MessageDetailsCore(BaseModel):
    type: Literal["private", "stream"]


class MessageDetails(MessageDetailsCore):
    # TODO: fix types to avoid optional fields
    mentioned: bool | None = None
    user_ids: list[int] | None = None
    stream_id: int | None = None
    topic: str | None = None
    unmuted_stream_msg: bool | None = None


class EventUpdateMessageFlagsRemoveCore(BaseModel):
    type: Literal["update_message_flags"]
    op: Literal["remove"]
    operation: Literal["remove"]
    flag: str
    messages: list[int]
    all: bool
    id: int


class EventUpdateMessageFlagsRemove(EventUpdateMessageFlagsRemoveCore):
    # TODO: fix types to avoid optional fields
    message_details: dict[str, MessageDetails] | None = None


class Group(BaseModel):
    id: int
    name: str
    creator_id: int | None
    date_created: int | None
    members: list[int]
    direct_subgroup_ids: list[int]
    description: str
    is_system_group: bool
    can_add_members_group: int | AnonymousSettingGroupDict
    can_join_group: int | AnonymousSettingGroupDict
    can_leave_group: int | AnonymousSettingGroupDict
    can_manage_group: int | AnonymousSettingGroupDict
    can_mention_group: int | AnonymousSettingGroupDict
    can_remove_members_group: int | AnonymousSettingGroupDict
    deactivated: bool


class EventUserGroupAdd(BaseModel):
    type: Literal["user_group"]
    op: Literal["add"]
    group: Group
    id: int


class EventUserGroupAddMembers(BaseModel):
    type: Literal["user_group"]
    op: Literal["add_members"]
    group_id: int
    user_ids: list[int]
    id: int


class EventUserGroupAddSubgroups(BaseModel):
    type: Literal["user_group"]
    op: Literal["add_subgroups"]
    group_id: int
    direct_subgroup_ids: list[int]
    id: int


class EventUserGroupRemove(BaseModel):
    type: Literal["user_group"]
    op: Literal["remove"]
    group_id: int
    id: int


class EventUserGroupRemoveMembers(BaseModel):
    type: Literal["user_group"]
    op: Literal["remove_members"]
    group_id: int
    user_ids: list[int]
    id: int


class EventUserGroupRemoveSubgroups(BaseModel):
    type: Literal["user_group"]
    op: Literal["remove_subgroups"]
    group_id: int
    direct_subgroup_ids: list[int]
    id: int


class UserGroupDataCore(BaseModel):
    pass


class UserGroupData(UserGroupDataCore):
    # TODO: fix types to avoid optional fields
    name: str | None = None
    description: str | None = None
    can_add_members_group: int | AnonymousSettingGroupDict | None = None
    can_join_group: int | AnonymousSettingGroupDict | None = None
    can_leave_group: int | AnonymousSettingGroupDict | None = None
    can_manage_group: int | AnonymousSettingGroupDict | None = None
    can_mention_group: int | AnonymousSettingGroupDict | None = None
    can_remove_members_group: int | AnonymousSettingGroupDict | None = None
    deactivated: bool | None = None


class EventUserGroupUpdate(BaseModel):
    type: Literal["user_group"]
    op: Literal["update"]
    group_id: int
    data: UserGroupData
    id: int


class EventUserSettingsUpdateCore(BaseModel):
    type: Literal["user_settings"]
    op: Literal["update"]
    property: str
    value: bool | int | str
    id: int


class EventUserSettingsUpdate(EventUserSettingsUpdateCore):
    # TODO: fix types to avoid optional fields
    language_name: str | None = None


class EventUserStatusCore(BaseModel):
    type: Literal["user_status"]
    user_id: int
    id: int


class EventUserStatus(EventUserStatusCore):
    # TODO: fix types to avoid optional fields
    away: bool | None = None
    status_text: str | None = None
    emoji_name: str | None = None
    emoji_code: str | None = None
    reaction_type: Literal["realm_emoji", "unicode_emoji", "zulip_extra_emoji"] | None = None


class EventUserTopic(BaseModel):
    id: int
    type: Literal["user_topic"]
    stream_id: int
    topic_name: str
    last_updated: int
    visibility_policy: int


class EventWebReloadClient(BaseModel):
    type: Literal["web_reload_client"]
    immediate: bool
    id: int
