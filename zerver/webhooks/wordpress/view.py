# Webhooks for external integrations.
from __future__ import absolute_import
from django.utils.translation import ugettext as _
from django.http import HttpRequest, HttpResponse
from zerver.models import get_client, UserProfile
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view

from six import text_type

PUBLISH_POST_OR_PAGE_TEMPLATE = 'New {type} published.\n[{title}]({url})'
USER_REGISTER_TEMPLATE = 'New blog user registered.\nName: {name}\nemail: {email}'
WP_LOGIN_TEMPLATE = 'User {name} logged in.'

@api_key_only_webhook_view("Wordpress")
@has_request_variables
def api_wordpress_webhook(request, user_profile,
                          stream=REQ(default="wordpress"),
                          topic=REQ(default="WordPress Notification"),
                          hook=REQ(default="WordPress Action"),
                          post_title=REQ(default="New WordPress Post"),
                          post_type=REQ(default="post"),
                          post_url=REQ(default="WordPress Post URL"),
                          display_name=REQ(default="New User Name"),
                          user_email=REQ(default="New User Email"),
                          user_login=REQ(default="Logged in User")):
    # type: (HttpRequest, UserProfile, text_type, text_type, text_type, text_type, text_type, text_type, text_type, text_type, text_type) -> HttpResponse

    # remove trailing whitespace (issue for some test fixtures)
    hook = hook.rstrip()

    if hook == 'publish_post' or hook == 'publish_page':
        data = PUBLISH_POST_OR_PAGE_TEMPLATE.format(type=post_type, title=post_title, url=post_url)

    elif hook == 'user_register':
        data = USER_REGISTER_TEMPLATE.format(name=display_name, email=user_email)

    elif hook == 'wp_login':
        data = WP_LOGIN_TEMPLATE.format(name=user_login)

    else:
        return json_error(_("Unknown WordPress webhook action: " + hook))

    check_send_message(user_profile, get_client("ZulipWordPressWebhook"), "stream",
                       [stream], topic, data)
    return json_success()
