from __future__ import absolute_import

from typing import Any, Dict, Optional
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import require_realm_admin, to_non_negative_int
from zerver.lib.actions import (
    do_set_realm_create_stream_by_admins_only,
    do_set_realm_name,
    do_set_realm_invite_by_admins_only,
    do_set_name_changes_disabled,
    do_set_email_changes_disabled,
    do_set_realm_add_emoji_by_admins_only,
    do_set_realm_invite_required,
    do_set_realm_message_editing,
    do_set_realm_restricted_to_domain,
    do_set_realm_default_language,
    do_set_realm_waiting_period_threshold,
    do_set_realm_authentication_methods
)
from zerver.lib.i18n import get_available_language_codes
from zerver.lib.request import has_request_variables, REQ, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_string, check_dict, check_bool
from zerver.models import UserProfile

@require_realm_admin
@has_request_variables
def update_realm(request, user_profile, name=REQ(validator=check_string, default=None),
                 restricted_to_domain=REQ(validator=check_bool, default=None),
                 invite_required=REQ(validator=check_bool, default=None),
                 invite_by_admins_only=REQ(validator=check_bool, default=None),
                 name_changes_disabled=REQ(validator=check_bool, default=None),
                 email_changes_disabled=REQ(validator=check_bool, default=None),
                 create_stream_by_admins_only=REQ(validator=check_bool, default=None),
                 add_emoji_by_admins_only=REQ(validator=check_bool, default=None),
                 allow_message_editing=REQ(validator=check_bool, default=None),
                 message_content_edit_limit_seconds=REQ(converter=to_non_negative_int, default=None),
                 default_language=REQ(validator=check_string, default=None),
                 waiting_period_threshold=REQ(converter=to_non_negative_int, default=None),
                 authentication_methods=REQ(validator=check_dict([]), default=None)):
    # type: (HttpRequest, UserProfile, Optional[str], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[int], Optional[str], Optional[int], Optional[dict]) -> HttpResponse
    # Validation for default_language
    if default_language is not None and default_language not in get_available_language_codes():
        raise JsonableError(_("Invalid language '%s'" % (default_language,)))
    realm = user_profile.realm
    data = {} # type: Dict[str, Any]
    if name is not None and realm.name != name:
        do_set_realm_name(realm, name)
        data['name'] = 'updated'
    if restricted_to_domain is not None and realm.restricted_to_domain != restricted_to_domain:
        do_set_realm_restricted_to_domain(realm, restricted_to_domain)
        data['restricted_to_domain'] = restricted_to_domain
    if invite_required is not None and realm.invite_required != invite_required:
        do_set_realm_invite_required(realm, invite_required)
        data['invite_required'] = invite_required
    if invite_by_admins_only is not None and realm.invite_by_admins_only != invite_by_admins_only:
        do_set_realm_invite_by_admins_only(realm, invite_by_admins_only)
        data['invite_by_admins_only'] = invite_by_admins_only
    if name_changes_disabled is not None and realm.name_changes_disabled != name_changes_disabled:
        do_set_name_changes_disabled(realm, name_changes_disabled)
        data['name_changes_disabled'] = name_changes_disabled
    if email_changes_disabled is not None and realm.email_changes_disabled != email_changes_disabled:
        do_set_email_changes_disabled(realm, email_changes_disabled)
        data['email_changes_disabled'] = email_changes_disabled
    if authentication_methods is not None and realm.authentication_methods_dict() != authentication_methods:
        if True not in list(authentication_methods.values()):
            return json_error(_("At least one authentication method must be enabled."),
                              data={"reason": "no authentication"}, status=403)
        else:
            do_set_realm_authentication_methods(realm, authentication_methods)
        data['authentication_methods'] = authentication_methods
    if create_stream_by_admins_only is not None and realm.create_stream_by_admins_only != create_stream_by_admins_only:
        do_set_realm_create_stream_by_admins_only(realm, create_stream_by_admins_only)
        data['create_stream_by_admins_only'] = create_stream_by_admins_only
    if add_emoji_by_admins_only is not None and realm.add_emoji_by_admins_only != add_emoji_by_admins_only:
        do_set_realm_add_emoji_by_admins_only(realm, add_emoji_by_admins_only)
        data['add_emoji_by_admins_only'] = add_emoji_by_admins_only
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
    if default_language is not None and realm.default_language != default_language:
        do_set_realm_default_language(realm, default_language)
        data['default_language'] = default_language
    if waiting_period_threshold is not None and realm.waiting_period_threshold != waiting_period_threshold:
        do_set_realm_waiting_period_threshold(realm, waiting_period_threshold)
        data['waiting_period_threshold'] = waiting_period_threshold
    return json_success(data)
