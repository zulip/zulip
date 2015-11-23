from __future__ import absolute_import

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate

from zerver.decorator import authenticated_json_post_view, has_request_variables, REQ
from zerver.lib.actions import do_change_password, \
    do_change_full_name, do_change_enable_desktop_notifications, \
    do_change_enter_sends, do_change_enable_sounds, \
    do_change_enable_offline_email_notifications, do_change_enable_digest_emails, \
    do_change_enable_offline_push_notifications, do_change_autoscroll_forever, \
    do_change_default_desktop_notifications, \
    do_change_enable_stream_desktop_notifications, do_change_enable_stream_sounds, \
    do_regenerate_api_key, do_change_avatar_source, do_change_twenty_four_hour_time, do_change_left_side_userlist
from zerver.lib.avatar import avatar_url
from zerver.lib.response import json_success, json_error
from zerver.lib.upload import upload_avatar_image
from zerver.lib.validator import check_bool
from zerver.models import UserProfile

from zerver.lib.rest import rest_dispatch as _rest_dispatch
rest_dispatch = csrf_exempt((lambda request, *args, **kwargs: _rest_dispatch(request, globals(), *args, **kwargs)))

def name_changes_disabled(realm):
    return settings.NAME_CHANGES_DISABLED or realm.name_changes_disabled

@authenticated_json_post_view
@has_request_variables
def json_change_ui_settings(request, user_profile,
                            autoscroll_forever=REQ(validator=check_bool,
                                                   default=None),
                            default_desktop_notifications=REQ(validator=check_bool,
                                                              default=None)):

    result = {}

    if autoscroll_forever is not None and \
            user_profile.autoscroll_forever != autoscroll_forever:
        do_change_autoscroll_forever(user_profile, autoscroll_forever)
        result['autoscroll_forever'] = autoscroll_forever

    if default_desktop_notifications is not None and \
            user_profile.default_desktop_notifications != default_desktop_notifications:
        do_change_default_desktop_notifications(user_profile, default_desktop_notifications)
        result['default_desktop_notifications'] = default_desktop_notifications

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_change_settings(request, user_profile,
                         full_name=REQ,
                         old_password=REQ(default=""),
                         new_password=REQ(default=""),
                         confirm_password=REQ(default="")):
    if new_password != "" or confirm_password != "":
        if new_password != confirm_password:
            return json_error("New password must match confirmation password!")
        if not authenticate(username=user_profile.email, password=old_password):
            return json_error("Wrong password!")
        do_change_password(user_profile, new_password)

    result = {}
    if user_profile.full_name != full_name and full_name.strip() != "":
        if name_changes_disabled(user_profile.realm):
            # Failingly silently is fine -- they can't do it through the UI, so
            # they'd have to be trying to break the rules.
            pass
        else:
            new_full_name = full_name.strip()
            if len(new_full_name) > UserProfile.MAX_NAME_LENGTH:
                return json_error("Name too long!")
            do_change_full_name(user_profile, new_full_name)
            result['full_name'] = new_full_name

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_time_setting(request, user_profile, twenty_four_hour_time=REQ(validator=check_bool, default=None)):
    result = {}
    if twenty_four_hour_time is not None and \
        user_profile.twenty_four_hour_time != twenty_four_hour_time:
        do_change_twenty_four_hour_time(user_profile, twenty_four_hour_time)

    result['twenty_four_hour_time'] = twenty_four_hour_time

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_left_side_userlist(request, user_profile, left_side_userlist=REQ(validator=check_bool, default=None)):
    result = {}
    if left_side_userlist is not None and \
        user_profile.left_side_userlist != left_side_userlist:
        do_change_left_side_userlist(user_profile, left_side_userlist)

    result['left_side_userlist'] = left_side_userlist

    return json_success(result)

@authenticated_json_post_view
@has_request_variables
def json_change_notify_settings(request, user_profile,
                                enable_stream_desktop_notifications=REQ(validator=check_bool,
                                                                        default=None),
                                enable_stream_sounds=REQ(validator=check_bool,
                                                         default=None),
                                enable_desktop_notifications=REQ(validator=check_bool,
                                                                 default=None),
                                enable_sounds=REQ(validator=check_bool,
                                                  default=None),
                                enable_offline_email_notifications=REQ(validator=check_bool,
                                                                       default=None),
                                enable_offline_push_notifications=REQ(validator=check_bool,
                                                                      default=None),
                                enable_digest_emails=REQ(validator=check_bool,
                                                         default=None)):

    result = {}

    # Stream notification settings.

    if enable_stream_desktop_notifications is not None and \
            user_profile.enable_stream_desktop_notifications != enable_stream_desktop_notifications:
        do_change_enable_stream_desktop_notifications(
            user_profile, enable_stream_desktop_notifications)
        result['enable_stream_desktop_notifications'] = enable_stream_desktop_notifications

    if enable_stream_sounds is not None and \
            user_profile.enable_stream_sounds != enable_stream_sounds:
        do_change_enable_stream_sounds(user_profile, enable_stream_sounds)
        result['enable_stream_sounds'] = enable_stream_sounds

    # PM and @-mention settings.

    if enable_desktop_notifications is not None and \
            user_profile.enable_desktop_notifications != enable_desktop_notifications:
        do_change_enable_desktop_notifications(user_profile, enable_desktop_notifications)
        result['enable_desktop_notifications'] = enable_desktop_notifications

    if enable_sounds is not None and \
            user_profile.enable_sounds != enable_sounds:
        do_change_enable_sounds(user_profile, enable_sounds)
        result['enable_sounds'] = enable_sounds

    if enable_offline_email_notifications is not None and \
            user_profile.enable_offline_email_notifications != enable_offline_email_notifications:
        do_change_enable_offline_email_notifications(user_profile, enable_offline_email_notifications)
        result['enable_offline_email_notifications'] = enable_offline_email_notifications

    if enable_offline_push_notifications is not None and \
            user_profile.enable_offline_push_notifications != enable_offline_push_notifications:
        do_change_enable_offline_push_notifications(user_profile, enable_offline_push_notifications)
        result['enable_offline_push_notifications'] = enable_offline_push_notifications

    if enable_digest_emails is not None and \
            user_profile.enable_digest_emails != enable_digest_emails:
        do_change_enable_digest_emails(user_profile, enable_digest_emails)
        result['enable_digest_emails'] = enable_digest_emails

    return json_success(result)

@authenticated_json_post_view
def json_set_avatar(request, user_profile):
    if len(request.FILES) != 1:
        return json_error("You must upload exactly one avatar.")

    user_file = request.FILES.values()[0]
    upload_avatar_image(user_file, user_profile, user_profile.email)
    do_change_avatar_source(user_profile, UserProfile.AVATAR_FROM_USER)
    user_avatar_url = avatar_url(user_profile)

    json_result = dict(
        avatar_url = user_avatar_url
    )
    return json_success(json_result)

@has_request_variables
def regenerate_api_key(request, user_profile):
    do_regenerate_api_key(user_profile)
    json_result = dict(
        api_key = user_profile.api_key
    )
    return json_success(json_result)

@authenticated_json_post_view
@has_request_variables
def json_change_enter_sends(request, user_profile,
                            enter_sends=REQ('enter_sends', validator=check_bool)):
    do_change_enter_sends(user_profile, enter_sends)
    return json_success()
