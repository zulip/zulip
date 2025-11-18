from collections.abc import Mapping
from typing import Annotated, Any, Literal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_safe
from pydantic import Json, NonNegativeInt, StringConstraints
from pydantic.functional_validators import AfterValidator

from confirmation.models import Confirmation, ConfirmationKeyError, get_object_from_key
from zerver.actions.create_realm import do_change_realm_subdomain
from zerver.actions.realm_settings import (
    do_change_realm_org_type,
    do_change_realm_permission_group_setting,
    do_deactivate_realm,
    do_reactivate_realm,
    do_set_realm_authentication_methods,
    do_set_realm_moderation_request_channel,
    do_set_realm_new_stream_announcements_stream,
    do_set_realm_property,
    do_set_realm_signup_announcements_stream,
    do_set_realm_user_default_setting,
    do_set_realm_zulip_update_announcements_stream,
    parse_and_set_setting_value_if_required,
    validate_authentication_methods_dict_from_api,
)
from zerver.decorator import require_post, require_realm_admin, require_realm_owner
from zerver.forms import check_subdomain_available as check_subdomain
from zerver.lib.demo_organizations import check_demo_organization_has_set_email
from zerver.lib.exceptions import JsonableError, OrganizationOwnerRequiredError
from zerver.lib.i18n import get_available_language_codes
from zerver.lib.response import json_success
from zerver.lib.retention import parse_message_retention_days
from zerver.lib.streams import access_stream_by_id
from zerver.lib.typed_endpoint import ApiParamConfig, typed_endpoint
from zerver.lib.typed_endpoint_validators import (
    check_int_in_validator,
    check_string_in_validator,
    parse_enum_from_string_value,
)
from zerver.lib.user_groups import (
    GroupSettingChangeRequest,
    access_user_group_for_setting,
    get_group_setting_value_for_api,
    get_system_user_group_by_name,
    parse_group_setting_value,
    validate_group_setting_value_change,
)
from zerver.lib.validator import check_capped_url, check_string
from zerver.models import Realm, RealmReactivationStatus, RealmUserDefault, UserProfile
from zerver.models.groups import SystemGroups
from zerver.models.realms import (
    DigestWeekdayEnum,
    MessageEditHistoryVisibilityPolicyEnum,
    OrgTypeEnum,
    RealmTopicsPolicyEnum,
)
from zerver.models.users import ResolvedTopicNoticeAutoReadPolicyEnum
from zerver.views.user_settings import check_settings_values


def parse_jitsi_server_url(value: str, special_values_map: Mapping[str, str | None]) -> str | None:
    if value in special_values_map:
        return special_values_map[value]

    return value


JITSI_SERVER_URL_MAX_LENGTH = 200


def check_jitsi_url(value: str) -> str:
    var_name = "jitsi_server_url"
    value = check_string(var_name, value)

    if value in list(Realm.JITSI_SERVER_SPECIAL_VALUES_MAP.keys()):
        return value

    validator = check_capped_url(JITSI_SERVER_URL_MAX_LENGTH)
    try:
        return validator(var_name, value)
    except ValidationError:
        raise JsonableError(_("{var_name} is not an allowed_type").format(var_name=var_name))


@require_realm_admin
@typed_endpoint
def update_realm(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    allow_message_editing: Json[bool] | None = None,
    authentication_methods: Json[dict[str, Any]] | None = None,
    avatar_changes_disabled: Json[bool] | None = None,
    can_access_all_users_group: Json[GroupSettingChangeRequest] | None = None,
    can_add_custom_emoji_group: Json[GroupSettingChangeRequest] | None = None,
    can_add_subscribers_group: Json[GroupSettingChangeRequest] | None = None,
    can_create_bots_group: Json[GroupSettingChangeRequest] | None = None,
    can_create_groups: Json[GroupSettingChangeRequest] | None = None,
    can_create_private_channel_group: Json[GroupSettingChangeRequest] | None = None,
    can_create_public_channel_group: Json[GroupSettingChangeRequest] | None = None,
    can_create_web_public_channel_group: Json[GroupSettingChangeRequest] | None = None,
    can_create_write_only_bots_group: Json[GroupSettingChangeRequest] | None = None,
    can_delete_any_message_group: Json[GroupSettingChangeRequest] | None = None,
    can_delete_own_message_group: Json[GroupSettingChangeRequest] | None = None,
    can_invite_users_group: Json[GroupSettingChangeRequest] | None = None,
    can_manage_all_groups: Json[GroupSettingChangeRequest] | None = None,
    can_manage_billing_group: Json[GroupSettingChangeRequest] | None = None,
    can_mention_many_users_group: Json[GroupSettingChangeRequest] | None = None,
    can_move_messages_between_channels_group: Json[GroupSettingChangeRequest] | None = None,
    can_move_messages_between_topics_group: Json[GroupSettingChangeRequest] | None = None,
    can_resolve_topics_group: Json[GroupSettingChangeRequest] | None = None,
    can_set_delete_message_policy_group: Json[GroupSettingChangeRequest] | None = None,
    can_set_topics_policy_group: Json[GroupSettingChangeRequest] | None = None,
    can_summarize_topics_group: Json[GroupSettingChangeRequest] | None = None,
    create_multiuse_invite_group: Json[GroupSettingChangeRequest] | None = None,
    default_code_block_language: str | None = None,
    default_language: str | None = None,
    description: Annotated[
        str | None, StringConstraints(max_length=Realm.MAX_REALM_DESCRIPTION_LENGTH)
    ] = None,
    digest_emails_enabled: Json[bool] | None = None,
    digest_weekday: Json[DigestWeekdayEnum] | None = None,
    direct_message_initiator_group: Json[GroupSettingChangeRequest] | None = None,
    direct_message_permission_group: Json[GroupSettingChangeRequest] | None = None,
    disallow_disposable_email_addresses: Json[bool] | None = None,
    email_changes_disabled: Json[bool] | None = None,
    emails_restricted_to_domains: Json[bool] | None = None,
    enable_guest_user_dm_warning: Json[bool] | None = None,
    enable_guest_user_indicator: Json[bool] | None = None,
    enable_read_receipts: Json[bool] | None = None,
    enable_spectator_access: Json[bool] | None = None,
    giphy_rating: Json[int] | None = None,
    inline_image_preview: Json[bool] | None = None,
    inline_url_embed_preview: Json[bool] | None = None,
    invite_required: Json[bool] | None = None,
    jitsi_server_url_raw: Annotated[
        Json[str] | None,
        AfterValidator(lambda val: check_jitsi_url(val)),
        ApiParamConfig("jitsi_server_url"),
    ] = None,
    message_content_allowed_in_email_notifications: Json[bool] | None = None,
    message_content_delete_limit_seconds_raw: Annotated[
        Json[int | str] | None,
        ApiParamConfig("message_content_delete_limit_seconds"),
    ] = None,
    message_content_edit_limit_seconds_raw: Annotated[
        Json[int | str] | None, ApiParamConfig("message_content_edit_limit_seconds")
    ] = None,
    message_edit_history_visibility_policy: Annotated[
        str | None,
        AfterValidator(
            lambda val: parse_enum_from_string_value(
                val,
                "message_edit_history_visibility_policy",
                MessageEditHistoryVisibilityPolicyEnum,
            )
        ),
    ] = None,
    message_retention_days_raw: Annotated[
        Json[int | str] | None, ApiParamConfig("message_retention_days")
    ] = None,
    moderation_request_channel_id: Json[int] | None = None,
    move_messages_between_streams_limit_seconds_raw: Annotated[
        Json[int | str] | None,
        ApiParamConfig("move_messages_between_streams_limit_seconds"),
    ] = None,
    move_messages_within_stream_limit_seconds_raw: Annotated[
        Json[int | str] | None,
        ApiParamConfig("move_messages_within_stream_limit_seconds"),
    ] = None,
    name: Annotated[str | None, StringConstraints(max_length=Realm.MAX_REALM_NAME_LENGTH)] = None,
    name_changes_disabled: Json[bool] | None = None,
    new_stream_announcements_stream_id: Json[int] | None = None,
    org_type: Json[OrgTypeEnum] | None = None,
    require_e2ee_push_notifications: Json[bool] | None = None,
    require_unique_names: Json[bool] | None = None,
    send_channel_events_messages: Json[bool] | None = None,
    send_welcome_emails: Json[bool] | None = None,
    signup_announcements_stream_id: Json[int] | None = None,
    string_id: Annotated[
        str | None, StringConstraints(max_length=Realm.MAX_REALM_SUBDOMAIN_LENGTH)
    ] = None,
    topics_policy: Annotated[
        str | None,
        AfterValidator(
            lambda val: parse_enum_from_string_value(
                val,
                "topics_policy",
                RealmTopicsPolicyEnum,
            )
        ),
    ] = None,
    video_chat_provider: Json[int] | None = None,
    waiting_period_threshold: Json[NonNegativeInt] | None = None,
    want_advertise_in_communities_directory: Json[bool] | None = None,
    zulip_update_announcements_stream_id: Json[int] | None = None,
    # Note: push_notifications_enabled and push_notifications_enabled_end_timestamp
    # are not offered here as it is maintained by the server, not via the API.
    welcome_message_custom_text: Annotated[
        str | None,
        StringConstraints(
            max_length=Realm.MAX_REALM_WELCOME_MESSAGE_CUSTOM_TEXT_LENGTH,
        ),
    ] = None,
) -> HttpResponse:
    # Realm object is being refetched here to make sure that we
    # do not use stale object from cache which can happen when a
    # previous request tried updating multiple settings in a single
    # request.
    #
    # TODO: Change the cache flushing strategy to make sure cache
    # does not contain stale objects.
    realm = Realm.objects.get(id=user_profile.realm_id)

    # Additional validation/error checking beyond types go here, so
    # the entire request can succeed or fail atomically.
    if default_language is not None and default_language not in get_available_language_codes():
        raise JsonableError(_("Invalid language '{language}'").format(language=default_language))
    if authentication_methods is not None:
        if not user_profile.is_realm_owner:
            raise OrganizationOwnerRequiredError

        validate_authentication_methods_dict_from_api(realm, authentication_methods)
        if True not in authentication_methods.values():
            raise JsonableError(_("At least one authentication method must be enabled."))

    if video_chat_provider is not None and video_chat_provider not in {
        p["id"] for p in realm.get_enabled_video_chat_providers().values()
    }:
        raise JsonableError(
            _("Invalid video_chat_provider {video_chat_provider}").format(
                video_chat_provider=video_chat_provider
            )
        )
    if giphy_rating is not None and giphy_rating not in {
        p["id"] for p in Realm.GIPHY_RATING_OPTIONS.values()
    }:
        raise JsonableError(
            _("Invalid giphy_rating {giphy_rating}").format(giphy_rating=giphy_rating)
        )

    message_retention_days: int | None = None
    if message_retention_days_raw is not None:
        if not user_profile.is_realm_owner:
            raise OrganizationOwnerRequiredError
        realm.ensure_not_on_limited_plan()
        message_retention_days = parse_message_retention_days(  # used by locals() below
            message_retention_days_raw, Realm.MESSAGE_RETENTION_SPECIAL_VALUES_MAP
        )

    if can_create_groups is not None:
        realm.ensure_not_on_limited_plan()

    if (
        invite_required is not None
        or create_multiuse_invite_group is not None
        or can_create_groups is not None
        or can_invite_users_group is not None
        or can_manage_all_groups is not None
        or can_manage_billing_group is not None
    ) and not user_profile.is_realm_owner:
        raise OrganizationOwnerRequiredError

    if (
        emails_restricted_to_domains is not None or disallow_disposable_email_addresses is not None
    ) and not user_profile.is_realm_owner:
        raise OrganizationOwnerRequiredError

    if waiting_period_threshold is not None and not user_profile.is_realm_owner:
        raise OrganizationOwnerRequiredError

    if realm.demo_organization_scheduled_deletion_date is not None and invite_required is not None:
        check_demo_organization_has_set_email(realm)

    if enable_spectator_access:
        realm.ensure_not_on_limited_plan()

    if can_access_all_users_group is not None:
        realm.can_enable_restricted_user_access_for_guests()

    data: dict[str, Any] = {}

    message_content_delete_limit_seconds: int | None = None
    if message_content_delete_limit_seconds_raw is not None:
        (
            message_content_delete_limit_seconds,
            setting_value_changed,
        ) = parse_and_set_setting_value_if_required(
            realm,
            "message_content_delete_limit_seconds",
            message_content_delete_limit_seconds_raw,
            acting_user=user_profile,
        )

        if setting_value_changed:
            data["message_content_delete_limit_seconds"] = message_content_delete_limit_seconds

    message_content_edit_limit_seconds: int | None = None
    if message_content_edit_limit_seconds_raw is not None:
        (
            message_content_edit_limit_seconds,
            setting_value_changed,
        ) = parse_and_set_setting_value_if_required(
            realm,
            "message_content_edit_limit_seconds",
            message_content_edit_limit_seconds_raw,
            acting_user=user_profile,
        )

        if setting_value_changed:
            data["message_content_edit_limit_seconds"] = message_content_edit_limit_seconds

    move_messages_within_stream_limit_seconds: int | None = None
    if move_messages_within_stream_limit_seconds_raw is not None:
        (
            move_messages_within_stream_limit_seconds,
            setting_value_changed,
        ) = parse_and_set_setting_value_if_required(
            realm,
            "move_messages_within_stream_limit_seconds",
            move_messages_within_stream_limit_seconds_raw,
            acting_user=user_profile,
        )

        if setting_value_changed:
            data["move_messages_within_stream_limit_seconds"] = (
                move_messages_within_stream_limit_seconds
            )

    move_messages_between_streams_limit_seconds: int | None = None
    if move_messages_between_streams_limit_seconds_raw is not None:
        (
            move_messages_between_streams_limit_seconds,
            setting_value_changed,
        ) = parse_and_set_setting_value_if_required(
            realm,
            "move_messages_between_streams_limit_seconds",
            move_messages_between_streams_limit_seconds_raw,
            acting_user=user_profile,
        )

        if setting_value_changed:
            data["move_messages_between_streams_limit_seconds"] = (
                move_messages_between_streams_limit_seconds
            )

    jitsi_server_url: str | None = None
    if jitsi_server_url_raw is not None:
        jitsi_server_url = parse_jitsi_server_url(
            jitsi_server_url_raw,
            Realm.JITSI_SERVER_SPECIAL_VALUES_MAP,
        )

        # We handle the "None" case separately here because
        # in the loop below, do_set_realm_property is called only when
        # the setting value is not "None". For values other than "None",
        # the loop itself sets the value of 'jitsi_server_url' by
        # calling do_set_realm_property.
        if jitsi_server_url is None and realm.jitsi_server_url is not None:
            do_set_realm_property(
                realm,
                "jitsi_server_url",
                jitsi_server_url,
                acting_user=user_profile,
            )

            data["jitsi_server_url"] = jitsi_server_url

    # The user of `locals()` here is a bit of a code smell, but it's
    # restricted to the elements present in realm.property_types.
    #
    # TODO: It should be possible to deduplicate this function up
    # further by some more advanced usage of the
    # `typed_endpoint` extraction.
    req_vars = {}
    req_group_setting_vars = {}

    for k, v in locals().items():
        if k in realm.property_types:
            req_vars[k] = v

        for setting_name in Realm.REALM_PERMISSION_GROUP_SETTINGS:
            if k == setting_name:
                req_group_setting_vars[k] = v

    for k, v in req_vars.items():
        if v is not None and getattr(realm, k) != v:
            do_set_realm_property(realm, k, v, acting_user=user_profile)
            if isinstance(v, str):
                data[k] = "updated"
            else:
                data[k] = v

    nobody_group = get_system_user_group_by_name(SystemGroups.NOBODY, user_profile.realm_id)
    for setting_name, permission_configuration in Realm.REALM_PERMISSION_GROUP_SETTINGS.items():
        expected_current_setting_value = None
        assert setting_name in req_group_setting_vars
        if req_group_setting_vars[setting_name] is None:
            continue

        setting_value = req_group_setting_vars[setting_name]
        new_setting_value = parse_group_setting_value(setting_value.new, nobody_group)

        if setting_value.old is not None:
            expected_current_setting_value = parse_group_setting_value(
                setting_value.old, nobody_group
            )

        current_value = getattr(realm, setting_name)
        current_setting_api_value = get_group_setting_value_for_api(current_value)

        if validate_group_setting_value_change(
            current_setting_api_value, new_setting_value, expected_current_setting_value
        ):
            with transaction.atomic(durable=True):
                user_group = access_user_group_for_setting(
                    new_setting_value,
                    user_profile,
                    setting_name=setting_name,
                    permission_configuration=permission_configuration,
                    current_setting_value=current_value,
                )
                do_change_realm_permission_group_setting(
                    realm,
                    setting_name,
                    user_group,
                    old_setting_api_value=current_setting_api_value,
                    acting_user=user_profile,
                )
            data[setting_name] = new_setting_value

    # The following realm properties do not fit the pattern above
    # authentication_methods is not supported by the do_set_realm_property
    # framework because it's tracked through the RealmAuthenticationMethod table.
    if authentication_methods is not None and (
        realm.authentication_methods_dict() != authentication_methods
    ):
        do_set_realm_authentication_methods(realm, authentication_methods, acting_user=user_profile)
        data["authentication_methods"] = authentication_methods

    # Channel-valued settings are not yet fully supported by the
    # property_types framework, and thus have explicit blocks here.
    if moderation_request_channel_id is not None and (
        realm.moderation_request_channel is None
        or realm.moderation_request_channel.id != moderation_request_channel_id
    ):
        new_moderation_request_channel_id = None
        if moderation_request_channel_id >= 0:
            (new_moderation_request_channel_id, sub) = access_stream_by_id(
                user_profile, moderation_request_channel_id, require_content_access=False
            )
        do_set_realm_moderation_request_channel(
            realm,
            new_moderation_request_channel_id,
            moderation_request_channel_id,
            acting_user=user_profile,
        )
        data["moderation_request_channel_id"] = moderation_request_channel_id

    if new_stream_announcements_stream_id is not None and (
        realm.new_stream_announcements_stream is None
        or (realm.new_stream_announcements_stream.id != new_stream_announcements_stream_id)
    ):
        new_stream_announcements_stream_new = None
        if new_stream_announcements_stream_id >= 0:
            (new_stream_announcements_stream_new, sub) = access_stream_by_id(
                user_profile,
                new_stream_announcements_stream_id,
                require_content_access=False,
            )
        do_set_realm_new_stream_announcements_stream(
            realm,
            new_stream_announcements_stream_new,
            new_stream_announcements_stream_id,
            acting_user=user_profile,
        )
        data["new_stream_announcements_stream_id"] = new_stream_announcements_stream_id

    if signup_announcements_stream_id is not None and (
        realm.signup_announcements_stream is None
        or realm.signup_announcements_stream.id != signup_announcements_stream_id
    ):
        new_signup_announcements_stream = None
        if signup_announcements_stream_id >= 0:
            (new_signup_announcements_stream, sub) = access_stream_by_id(
                user_profile, signup_announcements_stream_id, require_content_access=False
            )
        do_set_realm_signup_announcements_stream(
            realm,
            new_signup_announcements_stream,
            signup_announcements_stream_id,
            acting_user=user_profile,
        )
        data["signup_announcements_stream_id"] = signup_announcements_stream_id

    if zulip_update_announcements_stream_id is not None and (
        realm.zulip_update_announcements_stream is None
        or realm.zulip_update_announcements_stream.id != zulip_update_announcements_stream_id
    ):
        new_zulip_update_announcements_stream = None
        if zulip_update_announcements_stream_id >= 0:
            (new_zulip_update_announcements_stream, sub) = access_stream_by_id(
                user_profile,
                zulip_update_announcements_stream_id,
                require_content_access=False,
            )
        do_set_realm_zulip_update_announcements_stream(
            realm,
            new_zulip_update_announcements_stream,
            zulip_update_announcements_stream_id,
            acting_user=user_profile,
        )
        data["zulip_update_announcements_stream_id"] = zulip_update_announcements_stream_id

    if string_id is not None:
        if not user_profile.is_realm_owner:
            raise OrganizationOwnerRequiredError
        if realm.demo_organization_scheduled_deletion_date is None:
            raise JsonableError(_("Must be a demo organization."))
        check_demo_organization_has_set_email(realm)
        try:
            check_subdomain(string_id)
        except ValidationError as err:
            raise JsonableError(str(err.message))

        do_change_realm_subdomain(realm, string_id, acting_user=user_profile)
        data["realm_uri"] = realm.url
        data["realm_url"] = realm.url

    if org_type is not None:
        do_change_realm_org_type(realm, org_type, acting_user=user_profile)
        data["org_type"] = org_type

    return json_success(request, data)


@require_realm_owner
@typed_endpoint
def deactivate_realm(
    request: HttpRequest, user: UserProfile, *, deletion_delay_days: Json[int | None] = None
) -> HttpResponse:
    if settings.MAX_DEACTIVATED_REALM_DELETION_DAYS is not None and (
        deletion_delay_days is None
        or deletion_delay_days > settings.MAX_DEACTIVATED_REALM_DELETION_DAYS
    ):
        raise JsonableError(
            _("Data deletion time must be at most {max_allowed_days} days in the future.").format(
                max_allowed_days=settings.MAX_DEACTIVATED_REALM_DELETION_DAYS,
            )
        )

    if (
        settings.MIN_DEACTIVATED_REALM_DELETION_DAYS is not None
        and deletion_delay_days is not None
        and deletion_delay_days < settings.MIN_DEACTIVATED_REALM_DELETION_DAYS
    ):
        raise JsonableError(
            _("Data deletion time must be at least {min_allowed_days} days in the future.").format(
                min_allowed_days=settings.MIN_DEACTIVATED_REALM_DELETION_DAYS,
            )
        )

    realm = user.realm
    do_deactivate_realm(
        realm,
        acting_user=user,
        deactivation_reason="owner_request",
        email_owners=True,
        deletion_delay_days=deletion_delay_days,
    )
    return json_success(request)


@require_safe
def check_subdomain_available(request: HttpRequest, subdomain: str) -> HttpResponse:
    try:
        check_subdomain(subdomain)
        return json_success(request, data={"msg": "available"})
    except ValidationError as e:
        return json_success(request, data={"msg": e.message})


def realm_reactivation_get(request: HttpRequest, confirmation_key: str) -> HttpResponse:
    try:
        get_object_from_key(
            confirmation_key, [Confirmation.REALM_REACTIVATION], mark_object_used=False
        )
    except ConfirmationKeyError:  # nocoverage
        return render(request, "zerver/realm_reactivation_link_error.html", status=404)

    return render(
        request,
        "confirmation/redirect_to_post.html",
        context={
            "target_url": reverse("realm_reactivation"),
            "key": confirmation_key,
        },
    )


@require_post
@typed_endpoint
def realm_reactivation(request: HttpRequest, *, key: str) -> HttpResponse:
    try:
        obj = get_object_from_key(key, [Confirmation.REALM_REACTIVATION], mark_object_used=True)
    except ConfirmationKeyError:
        return render(request, "zerver/realm_reactivation_link_error.html", status=404)

    assert isinstance(obj, RealmReactivationStatus)
    realm = obj.realm

    do_reactivate_realm(realm)

    context = {"realm": realm}
    return render(request, "zerver/realm_reactivation.html", context)


emojiset_choices = {emojiset["key"] for emojiset in RealmUserDefault.emojiset_choices()}


@require_realm_admin
@typed_endpoint
def update_realm_user_settings_defaults(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    automatically_follow_topics_policy: Json[
        Annotated[
            int,
            check_int_in_validator(UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES),
        ]
    ]
    | None = None,
    automatically_follow_topics_where_mentioned: Json[bool] | None = None,
    automatically_unmute_topics_in_muted_streams_policy: Json[
        Annotated[
            int,
            check_int_in_validator(UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES),
        ]
    ]
    | None = None,
    color_scheme: Json[Annotated[int, check_int_in_validator(UserProfile.COLOR_SCHEME_CHOICES)]]
    | None = None,
    demote_inactive_streams: Json[
        Annotated[int, check_int_in_validator(UserProfile.DEMOTE_STREAMS_CHOICES)]
    ]
    | None = None,
    desktop_icon_count_display: Json[
        Annotated[int, check_int_in_validator(UserProfile.DESKTOP_ICON_COUNT_DISPLAY_CHOICES)]
    ]
    | None = None,
    display_emoji_reaction_users: Json[bool] | None = None,
    email_address_visibility: Json[
        Annotated[int, check_int_in_validator(UserProfile.EMAIL_ADDRESS_VISIBILITY_TYPES)]
    ]
    | None = None,
    email_notifications_batching_period_seconds: Json[int] | None = None,
    emojiset: Annotated[str, check_string_in_validator(emojiset_choices)] | None = None,
    enable_desktop_notifications: Json[bool] | None = None,
    enable_digest_emails: Json[bool] | None = None,
    enable_drafts_synchronization: Json[bool] | None = None,
    enable_followed_topic_audible_notifications: Json[bool] | None = None,
    enable_followed_topic_desktop_notifications: Json[bool] | None = None,
    enable_followed_topic_email_notifications: Json[bool] | None = None,
    enable_followed_topic_push_notifications: Json[bool] | None = None,
    enable_followed_topic_wildcard_mentions_notify: Json[bool] | None = None,
    enable_offline_email_notifications: Json[bool] | None = None,
    enable_offline_push_notifications: Json[bool] | None = None,
    enable_online_push_notifications: Json[bool] | None = None,
    enable_sounds: Json[bool] | None = None,
    enable_stream_audible_notifications: Json[bool] | None = None,
    enable_stream_desktop_notifications: Json[bool] | None = None,
    enable_stream_email_notifications: Json[bool] | None = None,
    enable_stream_push_notifications: Json[bool] | None = None,
    # enable_login_emails is not included here, because we don't want
    # security-related settings to be controlled by organization administrators.
    # enable_marketing_emails is not included here, since we don't at
    # present allow organizations to customize this. (The user's selection
    # in the signup form takes precedence over RealmUserDefault).
    #
    # We may want to change this model in the future, since some SSO signups
    # do not offer an opportunity to prompt the user at all during signup.
    enter_sends: Json[bool] | None = None,
    fluid_layout_width: Json[bool] | None = None,
    hide_ai_features: Json[bool] | None = None,
    high_contrast_mode: Json[bool] | None = None,
    left_side_userlist: Json[bool] | None = None,
    message_content_in_email_notifications: Json[bool] | None = None,
    notification_sound: str | None = None,
    pm_content_in_desktop_notifications: Json[bool] | None = None,
    presence_enabled: Json[bool] | None = None,
    realm_name_in_email_notifications_policy: Json[
        Annotated[
            int,
            check_int_in_validator(UserProfile.REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_CHOICES),
        ]
    ]
    | None = None,
    receives_typing_notifications: Json[bool] | None = None,
    resolved_topic_notice_auto_read_policy: Annotated[
        str | None,
        AfterValidator(
            lambda val: parse_enum_from_string_value(
                val,
                "resolved_topic_notice_auto_read_policy",
                ResolvedTopicNoticeAutoReadPolicyEnum,
            )
        ),
    ] = None,
    send_private_typing_notifications: Json[bool] | None = None,
    send_read_receipts: Json[bool] | None = None,
    send_stream_typing_notifications: Json[bool] | None = None,
    starred_message_counts: Json[bool] | None = None,
    translate_emoticons: Json[bool] | None = None,
    twenty_four_hour_time: Json[bool] | None = None,
    user_list_style: Json[
        Annotated[int, check_int_in_validator(UserProfile.USER_LIST_STYLE_CHOICES)]
    ]
    | None = None,
    web_animate_image_previews: Literal["always", "on_hover", "never"] | None = None,
    web_channel_default_view: Json[
        Annotated[int, check_int_in_validator(UserProfile.WEB_CHANNEL_DEFAULT_VIEW_CHOICES)]
    ]
    | None = None,
    web_escape_navigates_to_home_view: Json[bool] | None = None,
    web_font_size_px: Json[int] | None = None,
    web_home_view: Literal["recent_topics", "inbox", "all_messages"] | None = None,
    web_inbox_show_channel_folders: Json[bool] | None = None,
    web_left_sidebar_show_channel_folders: Json[bool] | None = None,
    web_left_sidebar_unreads_count_summary: Json[bool] | None = None,
    web_line_height_percent: Json[int] | None = None,
    web_mark_read_on_scroll_policy: Json[
        Annotated[
            int,
            check_int_in_validator(UserProfile.WEB_MARK_READ_ON_SCROLL_POLICY_CHOICES),
        ]
    ]
    | None = None,
    web_navigate_to_sent_message: Json[bool] | None = None,
    web_stream_unreads_count_display_policy: Json[
        Annotated[
            int,
            check_int_in_validator(UserProfile.WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_CHOICES),
        ]
    ]
    | None = None,
    web_suggest_update_timezone: Json[bool] | None = None,
    wildcard_mentions_notify: Json[bool] | None = None,
) -> HttpResponse:
    if notification_sound is not None or email_notifications_batching_period_seconds is not None:
        check_settings_values(notification_sound, email_notifications_batching_period_seconds)

    realm_user_default = RealmUserDefault.objects.get(realm=user_profile.realm)

    request_settings = {k: v for k, v in locals().items() if k in RealmUserDefault.property_types}
    for k, v in request_settings.items():
        if v is not None and getattr(realm_user_default, k) != v:
            do_set_realm_user_default_setting(realm_user_default, k, v, acting_user=user_profile)

    return json_success(request)
