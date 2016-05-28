from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt

from zerver.models import realm_filters_for_domain
from zerver.lib.actions import do_add_realm_filter, do_remove_realm_filter
from zerver.lib.response import json_success, json_error
from zerver.lib.rest import rest_dispatch as _rest_dispatch
rest_dispatch = csrf_exempt((lambda request, *args, **kwargs: _rest_dispatch(request, globals(), *args, **kwargs)))


# Custom realm filters
def list_filters(request, user_profile):
    filters = realm_filters_for_domain(user_profile.realm.domain)
    return json_success({'filters': filters})

def create_filter(request, user_profile):
    pattern = request.POST.get('pattern', None)
    url_format_string = request.POST.get('url_format_string', None)
    try:
        filter_id = do_add_realm_filter(
            realm=user_profile.realm,
            pattern=pattern,
            url_format_string=url_format_string
        )
        return json_success({'id': filter_id})
    except ValidationError as e:
        return json_error(e.message_dict)

def delete_filter(request, user_profile, filter_id):
    do_remove_realm_filter(realm=user_profile.realm, id=filter_id)
    return json_success({})
