from django.conf.urls import patterns, url, include

i18n_urlpatterns = [
    # SSO dispatch page for desktop app with SSO
    # Allows the user to enter their email address only,
    # and then redirects the user to the proper deployment
    # SSO-login page
    url(r'^accounts/deployment_dispatch$',
        'zilencer.views.account_deployment_dispatch',
        {'template_name': 'zerver/login.html'}),
]

# Zilencer views following the REST API style
v1_api_and_json_patterns = [
    url('^feedback$', 'zerver.lib.rest.rest_dispatch',
          {'POST': 'zilencer.views.submit_feedback'}),
    url('^report_error$', 'zerver.lib.rest.rest_dispatch',
          {'POST': 'zilencer.views.report_error'}),
    url('^endpoints$', 'zilencer.views.lookup_endpoints_for_user'),
]

urlpatterns = [
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
] + i18n_urlpatterns
