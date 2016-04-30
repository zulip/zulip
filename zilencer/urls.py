from django.conf.urls import patterns, url, include

urlpatterns = patterns('zilencer.views',
    # SSO dispatch page for desktop app with SSO
    # Allows the user to enter their email address only,
    # and then redirects the user to the proper deployment
    # SSO-login page
    url(r'^accounts/deployment_dispatch$', 'account_deployment_dispatch',
        {'template_name': 'zerver/login.html'}),
)

# Zilencer views following the REST API style
v1_api_and_json_patterns = patterns('zilencer.views',
    url('^feedback$', 'rest_dispatch',
          {'POST': 'submit_feedback'}),
    url('^report_error$', 'rest_dispatch',
          {'POST': 'report_error'}),
    url('^endpoints$', 'lookup_endpoints_for_user'),
)

urlpatterns += patterns('',
    url(r'^api/v1/', include(v1_api_and_json_patterns)),
    url(r'^json/', include(v1_api_and_json_patterns)),
)
