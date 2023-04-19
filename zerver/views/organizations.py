from typing import Any, Dict, List
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_int, check_string
from zerver.models import UserProfile, Realm, get_realm

#This endpoint should get a list of all self-hosted communities that opted in to be listed
@has_request_variables
def list_communities(request: HttpRequest, user_profile: UserProfile,
                     page: int=REQ(default=1, validator=check_int),
                     num_per_page: int=REQ(default=10, validator=check_int)) -> HttpResponse:

    #Obtain the correct bounds for the page
    start = (page - 1) * num_per_page
    end = start + num_per_page

    communities: List[Dict[str, Any]] = []

    # add self-hosted organizations to list
    for realm in Realm.objects.filter(deactivated=False, opt_in=True):
        if not realm.is_zulip_com and not realm.is_guest_user_realm:
            communities.append({
                'name': realm.name,
                'id': realm.string_id,
                'description': realm.description,
                'date_created': realm.date_created.timestamp(),
                'realm_icon': realm.icon_source,
                'is_in_zulip_com': False,
                'is_realm_pending': False,
            })

    # After appending the communities that opted in, sort them and store in json format
    communities = sorted(communities, key=lambda c: c['date_created'], reverse=True)

    result = {'total': len(communities), 'page': page, 'communities': communities[start:end]}
    return json_success(result)
