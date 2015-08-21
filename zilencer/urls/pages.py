from django.conf.urls import patterns, url, include

urlpatterns = patterns('zilencer.views',
    # SSO dispatch page for desktop app with SSO
    # Allows the user to enter their email address only,
    # and then redirects the user to the proper deployment
    # SSO-login page
    url(r'^accounts/deployment_dispatch$', 'account_deployment_dispatch', {'template_name': 'zerver/login.html'}),
)
