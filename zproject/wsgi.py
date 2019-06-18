"""
WSGI config for zulip project.

This module contains the WSGI application used by Django's development server
and any production WSGI deployments. It should expose a module-level variable
named ``application``. Django's ``runserver`` and ``runfcgi`` commands discover
this application via the ``WSGI_APPLICATION`` setting.

Usually you will have the standard Django WSGI application here, but it also
might make sense to replace the whole Django WSGI application with a custom one
that later delegates to the Django one. For example, you could introduce WSGI
middleware here, or combine a Django application with an application of another
framework.

"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
import scripts.lib.setup_path_on_import

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")

import django
try:
    django.setup()
except Exception as e:
    # If /etc/zulip/settings.py contains invalid syntax, Django
    # initialization will fail in django.setup().  In this case, our
    # normal configuration to logs errors to /var/log/zulip/errors.log
    # won't have been initialized.  Since it's really valuable for the
    # debugging process for a Zulip 500 error to always be "check
    # /var/log/zulip/errors.log", we log to that file directly here.
    import logging
    logging.basicConfig(filename='/var/log/zulip/errors.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    logger = logging.getLogger(__name__)
    logger.exception(e)
    raise

# Because import_module does not correctly handle safe circular imports we
# need to import zerver.models first before the middleware tries to import it.

import zerver.models
zerver.models

# This application object is used by any WSGI server configured to use this
# file. This includes Django's development server, if the WSGI_APPLICATION
# setting points here.
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
