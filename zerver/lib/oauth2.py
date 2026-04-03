import oauth2_provider.views as oauth2_views
from django.urls import path

# The access token validation happens in zerver.decorator.authenticated_rest_api_view
# and in zerver.views.tusd.authenticate_user
# The oauth2_provider package from django-oauth-toolkit supplies the database models,
# migrations, and OAuth2 views out of the box.
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
