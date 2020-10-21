import oauth2_provider.views as oauth2_views
from django.urls import path

oauth2_endpoint_views = [
    # OAuth2 Application Management endpoints
    path('applications/', oauth2_views.ApplicationList.as_view(), name="list"),
    path('applications/register/', oauth2_views.ApplicationRegistration.as_view(), name="register"),
    path('applications/<pk>/', oauth2_views.ApplicationDetail.as_view(), name="detail"),
    path('applications/<pk>/delete/', oauth2_views.ApplicationDelete.as_view(), name="delete"),
    path('applications/<pk>/update/', oauth2_views.ApplicationUpdate.as_view(), name="update"),

    # tokens
    path('authorize/', oauth2_views.AuthorizationView.as_view(), name="authorize"),
    path('token/', oauth2_views.TokenView.as_view(), name="token"),
    path('revoke-token/', oauth2_views.RevokeTokenView.as_view(), name="revoke-token"),
]
