# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

PUBLISH_POST_OR_PAGE_TEMPLATE = """
New {type} published:
* [{title}]({url})
""".strip()
USER_REGISTER_TEMPLATE = """
New blog user registered:
* **Name**: {name}
* **Email**: {email}
""".strip()
WP_LOGIN_TEMPLATE = 'User {name} logged in.'

@webhook_view("Wordpress", notify_bot_owner_on_invalid_json=False)
@has_request_variables
def api_wordpress_webhook(request: HttpRequest, user_profile: UserProfile,
                          hook: str=REQ(default="WordPress Action"),
                          post_title: str=REQ(default="New WordPress Post"),
                          post_type: str=REQ(default="post"),
                          post_url: str=REQ(default="WordPress Post URL"),
                          display_name: str=REQ(default="New User Name"),
                          user_email: str=REQ(default="New User Email"),
                          user_login: str=REQ(default="Logged in User")) -> HttpResponse:
    # remove trailing whitespace (issue for some test fixtures)
    hook = hook.rstrip()

    if hook == 'publish_post' or hook == 'publish_page':
        data = PUBLISH_POST_OR_PAGE_TEMPLATE.format(type=post_type, title=post_title, url=post_url)

    elif hook == 'user_register':
        data = USER_REGISTER_TEMPLATE.format(name=display_name, email=user_email)

    elif hook == 'wp_login':
        data = WP_LOGIN_TEMPLATE.format(name=user_login)

    else:
        return json_error(_("Unknown WordPress webhook action: {}").format(hook))

    topic = 'WordPress Notification'

    check_send_webhook_message(request, user_profile, topic, data)
    return json_success()
