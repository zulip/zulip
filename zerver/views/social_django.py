from typing import Any
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpRequest, HttpResponse
from social_django.utils import psa
from social_core.utils import partial_pipeline_data, user_is_authenticated
from social_django.views import NAMESPACE

@never_cache
@csrf_exempt
@psa('{0}:complete'.format(NAMESPACE))
def complete(request: HttpRequest, backend_name: str,
             *args: Any, **kwargs: Any) -> HttpResponse:
    """Authentication complete view"""
    backend = request.backend

    user = request.user
    is_authenticated = user_is_authenticated(user)
    user = user if is_authenticated else None

    partial = partial_pipeline_data(backend, user, *args, **kwargs)
    if partial:
        user = backend.continue_pipeline(partial)
        # clean partial data after usage
        backend.strategy.clean_partial_pipeline(partial.token)
    else:
        user = backend.complete(user=user, *args, **kwargs)

    return backend.strategy.complete(user)
