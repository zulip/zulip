from __future__ import absolute_import

from typing import Any, Dict, Optional, List, Text
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import require_realm_admin, to_non_negative_int, to_not_negative_int_or_none
from zerver.lib.actions import (
    do_set_realm_message_editing,
    do_set_realm_authentication_methods,
    do_set_realm_notifications_stream,
    do_set_realm_property,
)
from zerver.lib.i18n import get_available_language_codes
from zerver.lib.request import has_request_variables, REQ, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_string, check_dict, check_bool, check_int
from zerver.lib.streams import access_stream_by_id
from zerver.models import Realm, UserProfile


@require_realm_admin
@has_request_variables
def update_realm(request, user_profile, name=REQ(validator=check_string, default=None),
                 description=REQ(validator=check_string, default=None),
                 restricted_to_domain=REQ(validator=check_bool, default=None),
                 invite_required=REQ(validator=check_bool, default=None),
                 invite_by_admins_only=REQ(validator=check_bool, default=None),
                 name_changes_disabled=REQ(validator=check_bool, default=None),
                 email_changes_disabled=REQ(validator=check_bool, default=None),
                 inline_image_preview=REQ(validator=check_bool, default=None),
                 inline_url_embed_preview=REQ(validator=check_bool, default=None),
                 create_stream_by_admins_only=REQ(validator=check_bool, default=None),
                 add_emoji_by_admins_only=REQ(validator=check_bool, default=None),
                 allow_message_editing=REQ(validator=check_bool, default=None),
                 mandatory_topics=REQ(validator=check_bool, default=None),
                 message_content_edit_limit_seconds=REQ(converter=to_non_negative_int, default=None),
                 allow_edit_history=REQ(validator=check_bool, default=None),
                 default_language=REQ(validator=check_string, default=None),
                 waiting_period_threshold=REQ(converter=to_non_negative_int, default=None),
                 authentication_methods=REQ(validator=check_dict([]), default=None),
                 notifications_stream_id=REQ(validator=check_int, default=None),
                 message_retention_days=REQ(converter=to_not_negative_int_or_none, default=None)):
    # type: (HttpRequest, UserProfile, Optional[str], Optional[str], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[int], Optional[bool], Optional[str], Optional[int], Optional[dict], Optional[int], Optional[int]) -> HttpResponse
    realm = user_profile.realm

    # Additional validation/error checking beyond types go here, so
    # the entire request can succeed or fail atomically.
    if default_language is not None and default_language not in get_available_language_codes():
        raise JsonableError(_("Invalid language '%s'" % (default_language,)))
    if description is not None and len(description) > 1000:
        return json_error(_("Realm description is too long."))
    if name is not None and len(name) > Realm.MAX_REALM_NAME_LENGTH:
        return json_error(_("Realm name is too long."))
    if authentication_methods is not None and True not in list(authentication_methods.values()):
        return json_error(_("At least one authentication method must be enabled."))

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
            if isinstance(v, Text):
                data[k] = 'updated'
            else:
                data[k] = v

    # The following realm properties do not fit the pattern above
    # authentication_methods is not supported by the do_set_realm_property
    # framework because of its bitfield.
    if authentication_methods is not None and realm.authentication_methods_dict() != authentication_methods:
        do_set_realm_authentication_methods(realm, authentication_methods)
        data['authentication_methods'] = authentication_methods
    # The message_editing settings are coupled to each other, and thus don't fit
    # into the do_set_realm_property framework.
    if (allow_message_editing is not None and realm.allow_message_editing != allow_message_editing) or \
       (message_content_edit_limit_seconds is not None and
            realm.message_content_edit_limit_seconds != message_content_edit_limit_seconds):
        if allow_message_editing is None:
            allow_message_editing = realm.allow_message_editing
        if message_content_edit_limit_seconds is None:
            message_content_edit_limit_seconds = realm.message_content_edit_limit_seconds
        do_set_realm_message_editing(realm, allow_message_editing, message_content_edit_limit_seconds)
        data['allow_message_editing'] = allow_message_editing
        data['message_content_edit_limit_seconds'] = message_content_edit_limit_seconds
    # Realm.notifications_stream is not a boolean, Text or integer field, and thus doesn't fit
    # into the do_set_realm_property framework.
    if notifications_stream_id is not None:
        if realm.notifications_stream is None or realm.notifications_stream.id != notifications_stream_id:
            new_notifications_stream = None
            if notifications_stream_id >= 0:
                (new_notifications_stream, recipient, sub) = access_stream_by_id(user_profile, notifications_stream_id)
            do_set_realm_notifications_stream(realm, new_notifications_stream, notifications_stream_id)
            data['notifications_stream_id'] = notifications_stream_id

    return json_success(data)
