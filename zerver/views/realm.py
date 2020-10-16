from typing import Any, Dict, Optional, Union

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_safe

from confirmation.models import Confirmation, ConfirmationKeyException, get_object_from_key
from zerver.decorator import require_realm_admin, require_realm_owner
from zerver.forms import check_subdomain_available as check_subdomain
from zerver.lib.actions import (
    do_deactivate_realm,
    do_reactivate_realm,
    do_set_realm_authentication_methods,
    do_set_realm_message_editing,
    do_set_realm_notifications_stream,
    do_set_realm_property,
    do_set_realm_signup_notifications_stream,
)
from zerver.lib.exceptions import OrganizationOwnerRequired
from zerver.lib.i18n import get_available_language_codes
from zerver.lib.request import REQ, JsonableError, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.retention import parse_message_retention_days
from zerver.lib.streams import access_stream_by_id
from zerver.lib.validator import (
    check_bool,
    check_dict,
    check_int,
    check_int_in,
    check_string,
    check_string_or_int,
    to_non_negative_int,
)
from zerver.models import Realm, UserProfile


@require_realm_admin
@has_request_variables
def update_realm(
        request: HttpRequest, user_profile: UserProfile,
        name: Optional[str]=REQ(validator=check_string, default=None),
        description: Optional[str]=REQ(validator=check_string, default=None),
        emails_restricted_to_domains: Optional[bool]=REQ(validator=check_bool, default=None),
        disallow_disposable_email_addresses: Optional[bool]=REQ(validator=check_bool, default=None),
        invite_required: Optional[bool]=REQ(validator=check_bool, default=None),
        invite_by_admins_only: Optional[bool]=REQ(validator=check_bool, default=None),
        name_changes_disabled: Optional[bool]=REQ(validator=check_bool, default=None),
        email_changes_disabled: Optional[bool]=REQ(validator=check_bool, default=None),
        avatar_changes_disabled: Optional[bool]=REQ(validator=check_bool, default=None),
        inline_image_preview: Optional[bool]=REQ(validator=check_bool, default=None),
        inline_url_embed_preview: Optional[bool]=REQ(validator=check_bool, default=None),
        add_emoji_by_admins_only: Optional[bool]=REQ(validator=check_bool, default=None),
        allow_message_deleting: Optional[bool]=REQ(validator=check_bool, default=None),
        message_content_delete_limit_seconds: Optional[int]=REQ(converter=to_non_negative_int, default=None),
        allow_message_editing: Optional[bool]=REQ(validator=check_bool, default=None),
        allow_community_topic_editing: Optional[bool]=REQ(validator=check_bool, default=None),
        mandatory_topics: Optional[bool]=REQ(validator=check_bool, default=None),
        message_content_edit_limit_seconds: Optional[int]=REQ(converter=to_non_negative_int, default=None),
        allow_edit_history: Optional[bool]=REQ(validator=check_bool, default=None),
        default_language: Optional[str]=REQ(validator=check_string, default=None),
        waiting_period_threshold: Optional[int]=REQ(converter=to_non_negative_int, default=None),
        authentication_methods: Optional[Dict[str, Any]]=REQ(validator=check_dict([]), default=None),
        notifications_stream_id: Optional[int]=REQ(validator=check_int, default=None),
        signup_notifications_stream_id: Optional[int]=REQ(validator=check_int, default=None),
        message_retention_days_raw: Optional[Union[int, str]] = REQ(
            "message_retention_days", validator=check_string_or_int, default=None),
        send_welcome_emails: Optional[bool]=REQ(validator=check_bool, default=None),
        digest_emails_enabled: Optional[bool]=REQ(validator=check_bool, default=None),
        message_content_allowed_in_email_notifications: Optional[bool]=REQ(
            validator=check_bool, default=None),
        bot_creation_policy: Optional[int]=REQ(validator=check_int_in(
            Realm.BOT_CREATION_POLICY_TYPES), default=None),
        create_stream_policy: Optional[int]=REQ(validator=check_int_in(
            Realm.COMMON_POLICY_TYPES), default=None),
        invite_to_stream_policy: Optional[int]=REQ(validator=check_int_in(
            Realm.COMMON_POLICY_TYPES), default=None),
        user_group_edit_policy: Optional[int]=REQ(validator=check_int_in(
            Realm.USER_GROUP_EDIT_POLICY_TYPES), default=None),
        private_message_policy: Optional[int]=REQ(validator=check_int_in(
            Realm.PRIVATE_MESSAGE_POLICY_TYPES), default=None),
        wildcard_mention_policy: Optional[int]=REQ(validator=check_int_in(
            Realm.WILDCARD_MENTION_POLICY_TYPES), default=None),
        email_address_visibility: Optional[int]=REQ(validator=check_int_in(
            Realm.EMAIL_ADDRESS_VISIBILITY_TYPES), default=None),
        default_twenty_four_hour_time: Optional[bool]=REQ(validator=check_bool, default=None),
        video_chat_provider: Optional[int]=REQ(validator=check_int, default=None),
        default_code_block_language: Optional[str]=REQ(validator=check_string, default=None),
        digest_weekday: Optional[int]=REQ(validator=check_int_in(Realm.DIGEST_WEEKDAY_VALUES), default=None),
) -> HttpResponse:
    realm = user_profile.realm

    # Additional validation/error checking beyond types go here, so
    # the entire request can succeed or fail atomically.
    if default_language is not None and default_language not in get_available_language_codes():
        raise JsonableError(_("Invalid language '{}'").format(default_language))
    if description is not None and len(description) > 1000:
        return json_error(_("Organization description is too long."))
    if name is not None and len(name) > Realm.MAX_REALM_NAME_LENGTH:
        return json_error(_("Organization name is too long."))
    if authentication_methods is not None:
        if not user_profile.is_realm_owner:
            raise OrganizationOwnerRequired()
        if True not in list(authentication_methods.values()):
            return json_error(_("At least one authentication method must be enabled."))
    if (video_chat_provider is not None and
            video_chat_provider not in {p['id'] for p in Realm.VIDEO_CHAT_PROVIDERS.values()}):
        return json_error(_("Invalid video_chat_provider {}").format(video_chat_provider))

    message_retention_days: Optional[int] = None
    if message_retention_days_raw is not None:
        if not user_profile.is_realm_owner:
            raise OrganizationOwnerRequired()
        realm.ensure_not_on_limited_plan()
        message_retention_days = parse_message_retention_days(
            message_retention_days_raw, Realm.MESSAGE_RETENTION_SPECIAL_VALUES_MAP)

    # The user of `locals()` here is a bit of a code smell, but it's
    # restricted to the elements present in realm.property_types.
    #
    # TODO: It should be possible to deduplicate this function up
    # further by some more advanced usage of the
    # `REQ/has_request_variables` extraction.
    req_vars = {k: v for k, v in list(locals().items()) if k in realm.property_types}
    data: Dict[str, Any] = {}

    for k, v in list(req_vars.items()):
        if v is not None and getattr(realm, k) != v:
            do_set_realm_property(realm, k, v, acting_user=user_profile)
            if isinstance(v, str):
                data[k] = 'updated'
            else:
                data[k] = v

    # The following realm properties do not fit the pattern above
    # authentication_methods is not supported by the do_set_realm_property
    # framework because of its bitfield.
    if authentication_methods is not None and (realm.authentication_methods_dict() !=
                                               authentication_methods):
        do_set_realm_authentication_methods(realm, authentication_methods, acting_user=user_profile)
        data['authentication_methods'] = authentication_methods
    # The message_editing settings are coupled to each other, and thus don't fit
    # into the do_set_realm_property framework.
    if ((allow_message_editing is not None and realm.allow_message_editing != allow_message_editing) or
        (message_content_edit_limit_seconds is not None and
            realm.message_content_edit_limit_seconds != message_content_edit_limit_seconds) or
        (allow_community_topic_editing is not None and
            realm.allow_community_topic_editing != allow_community_topic_editing)):
        if allow_message_editing is None:
            allow_message_editing = realm.allow_message_editing
        if message_content_edit_limit_seconds is None:
            message_content_edit_limit_seconds = realm.message_content_edit_limit_seconds
        if allow_community_topic_editing is None:
            allow_community_topic_editing = realm.allow_community_topic_editing
        do_set_realm_message_editing(realm, allow_message_editing,
                                     message_content_edit_limit_seconds,
                                     allow_community_topic_editing,
                                     acting_user=user_profile)
        data['allow_message_editing'] = allow_message_editing
        data['message_content_edit_limit_seconds'] = message_content_edit_limit_seconds
        data['allow_community_topic_editing'] = allow_community_topic_editing

    # Realm.notifications_stream and Realm.signup_notifications_stream are not boolean,
    # str or integer field, and thus doesn't fit into the do_set_realm_property framework.
    if notifications_stream_id is not None:
        if realm.notifications_stream is None or (realm.notifications_stream.id !=
                                                  notifications_stream_id):
            new_notifications_stream = None
            if notifications_stream_id >= 0:
                (new_notifications_stream, sub) = access_stream_by_id(
                    user_profile, notifications_stream_id)
            do_set_realm_notifications_stream(realm, new_notifications_stream,
                                              notifications_stream_id,
                                              acting_user=user_profile)
            data['notifications_stream_id'] = notifications_stream_id

    if signup_notifications_stream_id is not None:
        if realm.signup_notifications_stream is None or (realm.signup_notifications_stream.id !=
                                                         signup_notifications_stream_id):
            new_signup_notifications_stream = None
            if signup_notifications_stream_id >= 0:
                (new_signup_notifications_stream, sub) = access_stream_by_id(
                    user_profile, signup_notifications_stream_id)
            do_set_realm_signup_notifications_stream(realm, new_signup_notifications_stream,
                                                     signup_notifications_stream_id,
                                                     acting_user=user_profile)
            data['signup_notifications_stream_id'] = signup_notifications_stream_id

    if default_code_block_language is not None:
        # Migrate '', used in the API to encode the default/None behavior of this feature.
        if default_code_block_language == '':
            data['default_code_block_language'] = None
        else:
            data['default_code_block_language'] = default_code_block_language

    return json_success(data)

@require_realm_owner
@has_request_variables
def deactivate_realm(request: HttpRequest, user: UserProfile) -> HttpResponse:
    realm = user.realm
    do_deactivate_realm(realm, user)
    return json_success()

@require_safe
def check_subdomain_available(request: HttpRequest, subdomain: str) -> HttpResponse:
    try:
        check_subdomain(subdomain)
        return json_success({"msg": "available"})
    except ValidationError as e:
        return json_success({"msg": e.message})

def realm_reactivation(request: HttpRequest, confirmation_key: str) -> HttpResponse:
    try:
        realm = get_object_from_key(confirmation_key, Confirmation.REALM_REACTIVATION)
    except ConfirmationKeyException:
        return render(request, 'zerver/realm_reactivation_link_error.html')
    do_reactivate_realm(realm)
    context = {"realm": realm}
    return render(request, 'zerver/realm_reactivation.html', context)
