import json
from typing import Any, Dict, Tuple

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.models import UserProfile
from zerver.decorator import api_key_only_webhook_view
from zerver.lib.webhooks.common import check_send_webhook_message, \
    ThirdPartyAPIAmbassador, generate_api_token_auth_handler
from zerver.lib.bot_config import get_bot_config, ConfigError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success, json_error

phabricator_authentication_handler = generate_api_token_auth_handler(
    mode="form", param_key="api.token", config_element_key="phabricator_api_key"
)

def get_commit_subject_and_body(payload: Dict[str, Any], user_profile: UserProfile,
                                config: Dict[str, str]) -> Tuple[str, str]:
    # If the bot was configured as a Phabricator Integration bot then it
    # would definitely have these keys and any extra checking would be
    # unnecessary.
    root_url = config["phabricator_root_url"]

    # Now, with the object PHID, we will need to begin a series of calls to the
    # Phabricator API to get any more basic information about what happened.
    ambassador = ThirdPartyAPIAmbassador(user_profile, root_url,
                                         authentication_handler=phabricator_authentication_handler)

    # First get information about the author
    object_phid = payload["object"]["phid"]
    response = ambassador.http_api_callback("/api/diffusion.commit.search",
                                            data={"constraints[phids][0]": object_phid})
    response_content = json.loads(response.content.decode('utf-8'))["data"][0]["fields"]
    cid = response_content["identifier"][0:9]
    author = response_content["author"]["name"]
    committer = response_content["committer"]["name"]

    # Then get information about the repository
    object_phid = response_content["repositoryPHID"]
    response = ambassador.http_api_callback("/api/diffusion.repository.search",
                                            data={"constraints[phids][0]": object_phid})
    response_content = json.loads(response.content.decode('utf-8'))
    repository_name = response_content["data"][0]["fields"]["name"]

    subject = repository_name
    if author == committer:
        body = "{} authored and committed commit {} to {}".format(
            author, cid, repository_name
        )
    else:  # nocoverage # there's no need to create another fixture to test this.
        body = "{} authored and {} committed commit {} to {}".format(
            author, committer, cid, repository_name
        )

    return (subject, body)

EVENT_HANDLERS = {
    "CMIT": get_commit_subject_and_body
}

@api_key_only_webhook_view('Phabricator')
@has_request_variables
def api_phabricator_webhook(request: HttpRequest, user_profile: UserProfile,
                            payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    event_type = payload["object"]["type"]
    event_handler = EVENT_HANDLERS.get(event_type, None)
    if event_handler is None:  # nocoverage
        return json_success()

    try:
        config = get_bot_config(user_profile)
    except ConfigError:
        config = {}
    if not config.get("integration_id", "") == "phabricator":
        # If this exists then we can assume the bot was configured with
        # the right keys.
        return json_error(_("The \"{}\" bot was not setup as a Phabricator \
integration bot.").format(user_profile.full_name))

    subject, body = event_handler(payload, user_profile, config)
    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()
