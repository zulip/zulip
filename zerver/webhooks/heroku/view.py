# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

TEMPLATE = """
{user} deployed version {head} of [{app}]({url}):

``` quote
{git_log}
```
""".strip()


@webhook_view("Heroku", notify_bot_owner_on_invalid_json=False)
@typed_endpoint
def api_heroku_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    head: str,
    app: str,
    user: str,
    url: str,
    git_log: str,
) -> HttpResponse:
    content = TEMPLATE.format(user=user, head=head, app=app, url=url, git_log=git_log)

    check_send_webhook_message(request, user_profile, app, content)
    return json_success(request)
