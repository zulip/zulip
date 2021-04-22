import oauth2_provider.views as oauth2_views
from django.urls import path
from oauth2_provider.models import get_application_model

from zerver.lib.response import json_success
from zerver.models import UserProfile


def get_oauth_backend(request, y, oauth_id):
    user = UserProfile.objects.filter(id=oauth_id).first()
    # print(user)
    applications_list = get_application_model().objects.filter(user=user).first()
    print(applications_list)
    json_result = dict(
        user_id=applications_list.user.id,
        application_name=applications_list.name,
        client_id=applications_list.client_id,
        client_secret=applications_list.client_secret,
        redirect_uri=applications_list.redirect_uris,
    )
    print(json_result)
    return json_success(json_result)


oauth2_endpoint_views = [
    # OAuth2 Application Management endpoints
    path("applications/", oauth2_views.ApplicationList.as_view(), name="list"),
    path("applications/register/", oauth2_views.ApplicationRegistration.as_view(), name="register"),
    path("applications/<pk>/", oauth2_views.ApplicationDetail.as_view(), name="detail"),
    path("applications/<pk>/delete/", oauth2_views.ApplicationDelete.as_view(), name="delete"),
    path("applications/<pk>/update/", oauth2_views.ApplicationUpdate.as_view(), name="update"),
    # tokens
    path("authorize/", oauth2_views.AuthorizationView.as_view(), name="authorize"),
    path("token/", oauth2_views.TokenView.as_view(), name="token"),
    path("revoke-token/", oauth2_views.RevokeTokenView.as_view(), name="revoke-token"),
]
