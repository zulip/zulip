from typing import Any, Dict, Optional
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_GET

from zerver.decorator import require_realm_admin, to_non_negative_int, to_not_negative_int_or_none
from zerver.lib.actions import (
    do_set_realm_message_editing,
    do_set_realm_message_deleting,
    do_set_realm_authentication_methods,
    do_set_realm_notifications_stream,
    do_set_realm_signup_notifications_stream,
    do_set_realm_property,
    do_deactivate_realm,
    do_reactivate_realm,
)
from zerver.lib.i18n import get_available_language_codes
from zerver.lib.request import has_request_variables, REQ, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_string, check_dict, check_bool, check_int
from zerver.lib.streams import access_stream_by_id
from zerver.lib.domains import validate_domain
from zerver.lib.video_calls import request_zoom_video_call_url
from zerver.models import Realm, UserProfile
from zerver.forms import check_subdomain_available as check_subdomain
from confirmation.models import get_object_from_key, Confirmation, ConfirmationKeyException

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
        inline_image_preview: Optional[bool]=REQ(validator=check_bool, default=None),
        inline_url_embed_preview: Optional[bool]=REQ(validator=check_bool, default=None),
        create_stream_by_admins_only: Optional[bool]=REQ(validator=check_bool, default=None),
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
        authentication_methods: Optional[Dict[Any, Any]]=REQ(validator=check_dict([]), default=None),
        notifications_stream_id: Optional[int]=REQ(validator=check_int, default=None),
        signup_notifications_stream_id: Optional[int]=REQ(validator=check_int, default=None),
        message_retention_days: Optional[int]=REQ(converter=to_not_negative_int_or_none, default=None),
        send_welcome_emails: Optional[bool]=REQ(validator=check_bool, default=None),
        message_content_allowed_in_email_notifications:
        Optional[bool]=REQ(validator=check_bool, default=None),
        bot_creation_policy: Optional[int]=REQ(converter=to_not_negative_int_or_none, default=None),
        email_address_visibility: Optional[int]=REQ(converter=to_not_negative_int_or_none, default=None),
        default_twenty_four_hour_time: Optional[bool]=REQ(validator=check_bool, default=None),
        video_chat_provider: Optional[str]=REQ(validator=check_string, default=None),
        google_hangouts_domain: Optional[str]=REQ(validator=check_string, default=None),
        zoom_user_id: Optional[str]=REQ(validator=check_string, default=None),
        zoom_api_key: Optional[str]=REQ(validator=check_string, default=None),
        zoom_api_secret: Optional[str]=REQ(validator=check_string, default=None),
) -> HttpResponse:
    realm = user_profile.realm

    # Additional validation/error checking beyond types go here, so
    # the entire request can succeed or fail atomically.
    if default_language is not None and default_language not in get_available_language_codes():
        raise JsonableError(_("Invalid language '%s'" % (default_language,)))
    if description is not None and len(description) > 1000:
        return json_error(_("Organization description is too long."))
    if name is not None and len(name) > Realm.MAX_REALM_NAME_LENGTH:
        return json_error(_("Organization name is too long."))
    if authentication_methods is not None and True not in list(authentication_methods.values()):
        return json_error(_("At least one authentication method must be enabled."))
    if video_chat_provider == "Google Hangouts":
        try:
            validate_domain(google_hangouts_domain)
        except ValidationError as e:
            return json_error(_('Invalid domain: {}').format(e.messages[0]))
    if video_chat_provider == "Zoom":
        if not zoom_api_secret:
            # Use the saved Zoom API secret if a new value isn't being sent
            zoom_api_secret = user_profile.realm.zoom_api_secret
        if not zoom_user_id:
            return json_error(_('User ID cannot be empty'))
        if not zoom_api_key:
            return json_error(_('API key cannot be empty'))
        if not zoom_api_secret:
            return json_error(_('API secret cannot be empty'))
        # If any of the Zoom settings have changed, validate the Zoom credentials.
        #
        # Technically, we could call some other API endpoint that
        # doesn't create a video call link, but this is a nicer
        # end-to-end test, since it verifies that the Zoom API user's
        # scopes includes the ability to create video calls, which is
        # the only capabiility we use.
        if ((zoom_user_id != realm.zoom_user_id or
             zoom_api_key != realm.zoom_api_key or
             zoom_api_secret != realm.zoom_api_secret) and
                not request_zoom_video_call_url(zoom_user_id, zoom_api_key, zoom_api_secret)):
            return json_error(_('Invalid credentials for the %(third_party_service)s API.') % dict(
                third_party_service="Zoom"))

    # Additional validation of enum-style values
    if bot_creation_policy is not None and bot_creation_policy not in Realm.BOT_CREATION_POLICY_TYPES:
        return json_error(_("Invalid bot creation policy"))
    if email_address_visibility is not None and \
            email_address_visibility not in Realm.EMAIL_ADDRESS_VISIBILITY_TYPES:
        return json_error(_("Invalid email address visibility policy"))

    # The user of `locals()` here is a bit of a code smell, but it's
    # restricted to the elements present in realm.property_types.
    #
    # TODO: It should be possible to deduplicate this function up
    # further by some more advanced usage of the
    # `REQ/has_request_variables` extraction.
    req_vars = {k: v for k, v in list(locals().items()) if k in realm.property_types}
    data = {}  # type: Dict[str, Any]

    for k, v in list(req_vars.items()):
        if v is not None and getattr(realm, k) != v:
            do_set_realm_property(realm, k, v)
            if isinstance(v, str):
                data[k] = 'updated'
            else:
                data[k] = v

    # The following realm properties do not fit the pattern above
    # authentication_methods is not supported by the do_set_realm_property
    # framework because of its bitfield.
    if authentication_methods is not None and (realm.authentication_methods_dict() !=
                                               authentication_methods):
        do_set_realm_authentication_methods(realm, authentication_methods)
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
                                     allow_community_topic_editing)
        data['allow_message_editing'] = allow_message_editing
        data['message_content_edit_limit_seconds'] = message_content_edit_limit_seconds
        data['allow_community_topic_editing'] = allow_community_topic_editing

    if (message_content_delete_limit_seconds is not None and
            realm.message_content_delete_limit_seconds != message_content_delete_limit_seconds):
        do_set_realm_message_deleting(realm, message_content_delete_limit_seconds)
        data['message_content_delete_limit_seconds'] = message_content_delete_limit_seconds
    # Realm.notifications_stream and Realm.signup_notifications_stream are not boolean,
    # str or integer field, and thus doesn't fit into the do_set_realm_property framework.
    if notifications_stream_id is not None:
        if realm.notifications_stream is None or (realm.notifications_stream.id !=
                                                  notifications_stream_id):
            new_notifications_stream = None
            if notifications_stream_id >= 0:
                (new_notifications_stream, recipient, sub) = access_stream_by_id(
                    user_profile, notifications_stream_id)
            do_set_realm_notifications_stream(realm, new_notifications_stream,
                                              notifications_stream_id)
            data['notifications_stream_id'] = notifications_stream_id

    if signup_notifications_stream_id is not None:
        if realm.signup_notifications_stream is None or (realm.signup_notifications_stream.id !=
                                                         signup_notifications_stream_id):
            new_signup_notifications_stream = None
            if signup_notifications_stream_id >= 0:
                (new_signup_notifications_stream, recipient, sub) = access_stream_by_id(
                    user_profile, signup_notifications_stream_id)
            do_set_realm_signup_notifications_stream(realm, new_signup_notifications_stream,
                                                     signup_notifications_stream_id)
            data['signup_notifications_stream_id'] = signup_notifications_stream_id

    return json_success(data)

@require_realm_admin
@has_request_variables
def deactivate_realm(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    realm = user_profile.realm
    do_deactivate_realm(realm)
    return json_success()

@require_GET
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
