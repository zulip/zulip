from django.conf.urls import url
from django.conf import settings
import os.path
from django.views.static import serve
import zerver.views.registration
import zerver.views.auth

# These URLs are available only in the development environment

use_prod_static = getattr(settings, 'PIPELINE_ENABLED', False)
static_root = os.path.join(settings.DEPLOY_ROOT, 'prod-static/serve' if use_prod_static else 'static')

urls = [
    url(r'^coverage/(?P<path>.*)$',
        serve, {'document_root':
                os.path.join(settings.DEPLOY_ROOT, 'var/coverage'),
                'show_indexes': True}),
    url(r'^docs/(?P<path>.*)$',
        serve, {'document_root':
                os.path.join(settings.DEPLOY_ROOT, 'docs/_build/html')}),
    url(r'^static/(?P<path>.*)$', serve, {'document_root': static_root}),
    url(r'^devlogin/$', zerver.views.auth.login_page,
        {'template_name': 'zerver/dev_login.html'}, name='zerver.views.auth.login_page'),
]

i18n_urls = [
    url(r'^confirmation_key/$', zerver.views.registration.confirmation_key),
]

# These are used for voyager development. On a real voyager instance,
# these files would be served by nginx.
if settings.LOCAL_UPLOADS_DIR is not None:
    urls += [
        url(r'^user_avatars/(?P<path>.*)$', serve,
            {'document_root': os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars")}),
    ]
