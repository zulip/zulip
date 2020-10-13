# type: ignore  # Ignore this whole file because it is practically third party code.

import json

import oauth2_provider.views as oauth2_views
from django.http import HttpRequest, HttpResponse
from django.urls import path
from oauth2_provider.models import get_access_token_model
from oauth2_provider.signals import app_authorized

from zerver.decorator import validate_oauth_key


class TokenView(oauth2_views.TokenView):
    # Like a lot of other things, we have to copy paste the entire view code
    # just to make a small change here.

    def zulip_specific_code(self, token, request, body):
        # Create a fake request to call our OAuth decorator and get UserProfile
        req = HttpRequest()
        req.method = 'GET'
        req.META = request.META
        req.META['HTTP_BEARER'] = token
        profile = validate_oauth_key(req)
        body_dict = json.loads(body)
        body_dict['user_id'] = profile.id
        body_dict['full_name'] = profile.full_name
        return json.dumps(body_dict)

    def post(self, request, *args, **kwargs):
        url, headers, body, status = self.create_token_response(request)
        if status == 200:
            access_token = json.loads(body).get("access_token")
            if access_token is not None:
                token = get_access_token_model().objects.get(token=access_token)
                body = self.zulip_specific_code(token, request, body)
                app_authorized.send(sender=self, request=request, token=token)
        response = HttpResponse(content=body, status=status)
        for k, v in headers.items():
            response[k] = v
        return response

oauth2_endpoint_views = [
    # OAuth2 Application Management endpoints
    path('applications/', oauth2_views.ApplicationList.as_view(), name="list"),
    path('applications/register/', oauth2_views.ApplicationRegistration.as_view(), name="register"),
    path('applications/<pk>/', oauth2_views.ApplicationDetail.as_view(), name="detail"),
    path('applications/<pk>/delete/', oauth2_views.ApplicationDelete.as_view(), name="delete"),
    path('applications/<pk>/update/', oauth2_views.ApplicationUpdate.as_view(), name="update"),

    # tokens
    path('authorize/', oauth2_views.AuthorizationView.as_view(), name="authorize"),
    path('token/', TokenView.as_view(), name="token"),
    path('revoke-token/', oauth2_views.RevokeTokenView.as_view(), name="revoke-token"),
]
