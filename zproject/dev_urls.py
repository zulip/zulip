from django.conf.urls import url
from django.conf import settings
import os.path

# These URLs are available only in the development environment

use_prod_static = getattr(settings, 'PIPELINE_ENABLED', False)
static_root = os.path.join(settings.DEPLOY_ROOT, 'prod-static/serve' if use_prod_static else 'static')

urls = [url(r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': static_root})]
i18n_urls = [url(r'^confirmation_key/$', 'zerver.views.confirmation_key')]

# These are used for voyager development. On a real voyager instance,
# these files would be served by nginx.
if settings.LOCAL_UPLOADS_DIR is not None:
    urls += [
        url(r'^user_avatars/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars")}),
    ]
