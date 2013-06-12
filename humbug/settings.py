# Django settings for humbug project.
import os
import platform
import logging
import time
import re

from zephyr.openid import openid_failure_handler

SERVER_GENERATION = int(time.time())

DEPLOYED = (('humbughq.com' in platform.node())
            or os.path.exists('/etc/humbug-server'))
STAGING_DEPLOYED = (platform.node() == 'staging.humbughq.com')
TESTING_DEPLOYED = not not re.match(r'^test', platform.node())

DEBUG = not DEPLOYED
TEMPLATE_DEBUG = DEBUG
TEST_SUITE = False

if DEBUG:
    INTERNAL_IPS = ('127.0.0.1',)
if DEPLOYED and not TESTING_DEPLOYED:
    # The IP addresses are for app.humbughq.com and staging.humbughq.com
    ALLOWED_HOSTS = ['localhost', '.humbughq.com', '54.214.48.144', '54.245.120.64']
elif TESTING_DEPLOYED:
    # Allow any hosts for our test instances, to reduce 500 spam
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = ['localhost']

ADMINS = (
    ('Humbug Error Reports', 'errors@humbughq.com'),
)

MANAGERS = ADMINS

DATABASES = {"default": {
    'ENGINE': 'django.db.backends.postgresql_psycopg2',
    'NAME': 'humbug',
    'USER': 'humbug',
    'PASSWORD': '', # Authentication done via certificates
    'HOST': 'postgres.humbughq.com',
    'SCHEMA': 'humbug',
    'OPTIONS': {
        'sslmode': 'verify-full',
        },
    },
}

if not DEPLOYED:
    DATABASES["default"].update({
            'PASSWORD': 'xxxxxxxxxxxx',
            'HOST': 'localhost',
            'OPTIONS': {}
            })
    INTERNAL_HUMBUG_USERS = []

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'America/New_York'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# The ID, as an integer, of the current site in the django_site database table.
# This is used so that application data can hook into specific site(s) and a
# single database can manage content for multiple sites.
#
# We set this site's domain to 'humbughq.com' in populate_db.
SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
TEMPLATE_DIRS = ( os.path.join(SITE_ROOT, '..', 'templates'),)

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# A fixed salt used for hashing in certain places, e.g. email-based
# username generation.
HASH_SALT = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# Use this salt to hash a user's email into a filename for their user-uploaded
# avatar.  If this salt is discovered, attackers will only be able to determine
# that the owner of an email account has uploaded an avatar to Humbug, which isn't
# the end of the world.  Don't use the salt where there is more security exposure.
AVATAR_SALT = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# Tell the browser to never send our cookies without encryption, e.g.
# when executing the initial http -> https redirect.
#
# Turn it off for local testing because we don't have SSL.
if DEPLOYED:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE    = True

# Prevent Javascript from reading the CSRF token from cookies.  Our code gets
# the token from the DOM, which means malicious code could too.  But hiding the
# cookie will slow down some attackers.
CSRF_COOKIE_PATH = '/;HttpOnly'

# Used just for generating initial passwords (only used in testing environments).
INITIAL_PASSWORD_SALT = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# A shared secret, used to authenticate different parts of the app to each other.
# FIXME: store this password more securely
SHARED_SECRET = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# Base URL of the Tornado server
# We set it to None when running backend tests or populate_db.
# We override the port number when running frontend tests.
TORNADO_SERVER = 'http://localhost:9993'
RUNNING_INSIDE_TORNADO = False

# Make redirects work properly behind a reverse proxy
USE_X_FORWARDED_HOST = True

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    # Our logging middleware should be the first middleware item.
    'zephyr.middleware.LogRequests',
    'zephyr.middleware.JsonErrorHandler',
    'zephyr.middleware.RateLimitMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)

AUTHENTICATION_BACKENDS = ('humbug.backends.EmailAuthBackend',
                           'humbug.backends.GoogleBackend')
AUTH_USER_MODEL = "zephyr.UserProfile"

TEST_RUNNER = 'zephyr.tests.Runner'

ROOT_URLCONF = 'humbug.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'humbug.wsgi.application'

INSTALLED_APPS = (
    'django.contrib.auth',
    'humbug.authhack',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'south',
    'django_openid_auth',
    'confirmation',
    'pipeline',
    'zephyr',
)

LOCAL_STATSD = (False)
USING_STATSD = (DEPLOYED and not TESTING_DEPLOYED) or LOCAL_STATSD

if USING_STATSD:
    if LOCAL_STATSD:
        STATSD_HOST = 'localhost'
    else:
        STATSD_HOST = '10.252.2.167'

    INSTALLED_APPS = ('django_statsd',) + INSTALLED_APPS
    STATSD_PORT = 8125
    STATSD_CLIENT = 'django_statsd.clients.normal'

    if STAGING_DEPLOYED:
        STATSD_PREFIX = 'staging'
    elif DEPLOYED:
        STATSD_PREFIX = 'app'
    else:
        STATSD_PREFIX = 'user'

RATE_LIMITING = True
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379

RATE_LIMITING_RULES = [
    (60, 100),     # 100 requests max every minute
    ]

# Static files and minification

STATIC_URL = '/static/'

# PipelineCachedStorage inserts a file hash into filenames,
# to prevent the browser from using stale files from cache.
#
# Unlike PipelineStorage, it requires the files to exist in
# STATIC_ROOT even for dev servers.  So we only use
# PipelineCachedStorage when not DEBUG.

if DEBUG:
    STATICFILES_STORAGE = 'pipeline.storage.PipelineStorage'
    STATICFILES_FINDERS = (
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    )
    STATIC_ROOT = 'prod-static/serve'
else:
    STATICFILES_STORAGE = 'zephyr.storage.HumbugStorage'
    STATICFILES_FINDERS = (
        'zephyr.finders.HumbugFinder',
    )
    if DEPLOYED:
        STATIC_ROOT = '/home/humbug/prod-static'
    else:
        STATIC_ROOT = 'prod-static/serve'

STATIC_HEADER_FILE = 'zephyr/static_header.txt'

# This is the default behavior from Pipeline, but we set it
# here so that urls.py can read it.
PIPELINE = not DEBUG

# To use minified files in dev, set PIPELINE = True.
#
# You will need to run ./tools/update-prod-static after
# changing static files.

PIPELINE_CSS = {
    'activity': {
        'source_filenames': ('styles/activity.css',),
        'output_filename':  'min/activity.css'
    },
    'portico': {
        'source_filenames': (
            'third/zocial/zocial.css',
            'styles/portico.css',
            'styles/pygments.css',
            'styles/fonts.css',
        ),
        'output_filename': 'min/portico.css'
    },
    'app': {
        'source_filenames': (
            'third/spectrum/spectrum.css',
            'styles/zephyr.css',
            'styles/pygments.css',
            'styles/fonts.css',
        ),
        'output_filename': 'min/app.css'
    },
    'common': {
        'source_filenames': (
            'third/bootstrap/css/bootstrap.css',
            'third/bootstrap/css/bootstrap-responsive.css',
        ),
        'output_filename': 'min/common.css'
    },
}

PIPELINE_JS = {
    'common': {
        'source_filenames': (
            'third/jquery/jquery-1.7.2.js',
            'js/blueslip.js',
            'third/bootstrap/js/bootstrap.js',
            'js/common.js',
            ),
        'output_filename':  'min/common.js'
    },
    'landing-page': {
        'source_filenames': (
            'third/jquery-form/jquery.form.js',
            'js/landing-page.js',
            ),
        'output_filename':  'min/landing-page.js'
    },
    'signup': {
        'source_filenames': (
            'js/signup.js',
            'third/jquery-validate/jquery.validate.js',
            ),
        'output_filename':  'min/signup.js'
    },
    'api': {
        'source_filenames': ('js/api.js',),
        'output_filename':  'min/api.js'
    },
    'app_debug': {
        'source_filenames': ('js/debug.js',),
        'output_filename':  'min/app_debug.js'
    },
    'app': {
        'source_filenames': [
            'third/jquery-validate/jquery.validate.js',
            'third/jquery-form/jquery.form.js',
            'third/jquery-highlight/jquery.highlight.js',
            'third/jquery-filedrop/jquery.filedrop.js',
            'third/jquery-caret/jquery.caret.1.02.js',
            'third/xdate/xdate.dev.js',
            'third/spin/spin.js',
            'third/jquery-mousewheel/jquery.mousewheel.js',
            'third/jquery-throttle-debounce/jquery.ba-throttle-debounce.js',
            'third/jquery-idle/jquery.idle.js',
            'third/jquery-autosize/jquery.autosize.js',
            'third/spectrum/spectrum.js',
            ('third/handlebars/handlebars.runtime.js'
                if PIPELINE
                else 'third/handlebars/handlebars.js'),

            'js/util.js',
            'js/setup.js',
            'js/viewport.js',
            'js/rows.js',
            'js/unread.js',
            'js/stream_list.js',
            'js/narrow.js',
            'js/reload.js',
            'js/notifications_bar.js',
            'js/compose.js',
            'js/subs.js',
            'js/message_edit.js',
            'js/ui.js',
            'js/typeahead_helper.js',
            'js/search.js',
            'js/composebox_typeahead.js',
            'js/hotkey.js',
            'js/notifications.js',
            'js/hashchange.js',
            'js/invite.js',
            'js/message_list.js',
            'js/onboarding.js',
            'js/zephyr.js',
            'js/activity.js',
            'js/colorspace.js',
            'js/timerender.js',
            'js/tutorial.js',
            'js/templates.js',
            'js/settings.js',
            'js/tab_bar.js',
            'js/metrics.js'
        ],
        'output_filename': 'min/app.js'
    },
    'activity': {
        'source_filenames': (
            'third/sorttable/sorttable.js',
        ),
        'output_filename': 'min/activity.js'
    },
}

if PIPELINE:
    # This file is generated by update-prod-static.
    # In dev we fetch individual templates using Ajax.
    PIPELINE_JS['app']['source_filenames'].append('templates/compiled.js')

PIPELINE_CSS_COMPRESSOR = 'pipeline.compressors.yui.YUICompressor'
PIPELINE_YUI_BINARY     = '/usr/bin/env yui-compressor'

PIPELINE_JS_COMPRESSOR  = 'zephyr.lib.minify.ClosureSourceMapCompressor'
PIPELINE_CLOSURE_BINARY = os.path.join(SITE_ROOT, '../tools/closure-compiler/run')
PIPELINE_CLOSURE_SOURCE_MAP_DIR = 'prod-static/source-map'

# Disable stuffing the entire JavaScript codebase inside an anonymous function.
# We need modules to be externally visible, so that methods can be called from
# event handlers defined in HTML.
PIPELINE_DISABLE_WRAPPER = True


USING_RABBITMQ = DEPLOYED
# This password also appears in servers/configure-rabbitmq
RABBITMQ_PASSWORD = 'xxxxxxxxxxxxxxxx'

# Caching
if DEPLOYED:
    CACHES = {
        'default': {
            'BACKEND':  'django.core.cache.backends.memcached.PyLibMCCache',
            'LOCATION': '127.0.0.1:11211',
            'TIMEOUT':  3600
        },
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
else:
    CACHES = { 'default': {
        'BACKEND':  'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'humbug-default-local-cache',
        'TIMEOUT':  3600,
        'OPTIONS': {
            'MAX_ENTRIES': 100000
        }
    } }
CACHES['database'] = {
            'BACKEND':  'django.core.cache.backends.db.DatabaseCache',
            'LOCATION':  'third_party_api_results',
            # Basically never timeout.  Setting to 0 isn't guaranteed
            # to work, see https://code.djangoproject.com/ticket/9595
            'TIMEOUT': 2000000000,
            'OPTIONS': {
                'MAX_ENTRIES': 100000000,
                'CULL_FREQUENCY': 10,
            },
        }

if DEPLOYED:
    SERVER_LOG_PATH = "/home/humbug/logs/server.log"
    EVENT_LOG_DIR = '/home/humbug/logs/event_log'
    STATS_DIR = '/home/humbug/stats'
    PERSISTENT_QUEUE_FILENAME = "/home/humbug/tornado/event_queues.pickle"
else:
    EVENT_LOG_DIR = 'event_log'
    SERVER_LOG_PATH = "server.log"
    STATS_DIR = 'stats'
    PERSISTENT_QUEUE_FILENAME = "event_queues.pickle"

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'default': {
            'format': '%(asctime)s %(levelname)-8s %(message)s'
        }
    },
    'filters': {
        'HumbugLimiter': {
            '()': 'zephyr.lib.logging_util.HumbugLimiter',
        },
        'EmailLimiter': {
            '()': 'zephyr.lib.logging_util.EmailLimiter',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'nop': {
            '()': 'zephyr.lib.logging_util.ReturnTrue',
        },
        'require_really_deployed': {
            '()': 'zephyr.lib.logging_util.RequireReallyDeployed',
        },
    },
    'handlers': {
        'humbug_admins': {
            'level':     'ERROR',
            'class':     'zephyr.handlers.AdminHumbugHandler',
            # For testing the handler delete the next line
            'filters':   ['HumbugLimiter', 'require_debug_false', 'require_really_deployed'],
            'formatter': 'default'
        },
        'console': {
            'level':     'DEBUG',
            'class':     'logging.StreamHandler',
            'formatter': 'default'
        },
        'file': {
            'level':       'DEBUG',
            'class':       'logging.handlers.TimedRotatingFileHandler',
            'formatter':   'default',
            'filename':    SERVER_LOG_PATH,
            'when':        'D',
            'interval':    7,
            'backupCount': 100000000,
        },
        # Django has some hardcoded code to add the
        # require_debug_false filter to the mail_admins handler if no
        # filters are specified.  So for testing, one is recommended
        # to replace the list of filters for mail_admins with 'nop'.
        'mail_admins': {
            'level': 'ERROR',
            'class': 'zephyr.handlers.HumbugAdminEmailHandler',
            # For testing the handler replace the filters list with just 'nop'
            'filters': ['EmailLimiter', 'require_debug_false', 'require_really_deployed'],
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level':    'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['humbug_admins', 'console', 'file', 'mail_admins'],
            'level':    'INFO',
            'propagate': False,
        },
        'humbug.requests': {
            'handlers': ['console', 'file'],
            'level':    'INFO',
            'propagate': False,
        },
        ## Uncomment the following to get all database queries logged to the console
        # 'django.db': {
        #     'handlers': ['console'],
        #     'level': 'DEBUG',
        #     'propagate': False,
        # },
    }
}

TEMPLATE_CONTEXT_PROCESSORS = (
    'zephyr.context_processors.add_settings',
)

ACCOUNT_ACTIVATION_DAYS=7
EMAIL_USE_TLS = True
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = 'humbug@humbughq.com'
EMAIL_HOST_PASSWORD = 'xxxxxxxxxxxxxxxx'
EMAIL_PORT = 587

DEFAULT_FROM_EMAIL = "Humbug <humbug@humbughq.com>"

LOGIN_REDIRECT_URL='/'
OPENID_SSO_SERVER_URL = 'https://www.google.com/accounts/o8/id'
OPENID_CREATE_USERS = True
OPENID_RENDER_FAILURE = openid_failure_handler

MAILCHIMP_API_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-us4'
HUMBUG_FRIENDS_LIST_ID = '84b2f3da6b'

# Client-side polling timeout for get_events, in milliseconds.
# We configure this here so that the client test suite can override it.
# We already kill the connection server-side with heartbeat events,
# but it's good to have a safety.  This value should be greater than
# (HEARTBEAT_MIN_FREQ_SECS + 10)
POLL_TIMEOUT = 90 * 1000

# The new user tutorial is enabled by default, and disabled for
# client tests.
TUTORIAL_ENABLED = True

HOME_NOT_LOGGED_IN = '/login'
if DEPLOYED:
    ALLOW_REGISTER = False
    FULL_NAVBAR    = False
else:
    ALLOW_REGISTER = True
    FULL_NAVBAR    = True

# For testing, you may want to have emails be printed to the console.
if not DEPLOYED:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

    # Use fast password hashing for creating testing users when not
    # DEPLOYED
    PASSWORD_HASHERS = (
                'django.contrib.auth.hashers.SHA1PasswordHasher',
                'django.contrib.auth.hashers.PBKDF2PasswordHasher'
            )

if DEPLOYED:
    # Filter out user data
    DEFAULT_EXCEPTION_REPORTER_FILTER = 'zephyr.filters.HumbugExceptionReporterFilter'

# We want all temporary uploaded files to be stored on disk.

FILE_UPLOAD_MAX_MEMORY_SIZE = 0

EMBEDLY_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

if DEPLOYED:
    S3_KEY="xxxxxxxxxxxxxxxxxxxx"
    S3_SECRET_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    S3_BUCKET="humbug-user-uploads"
    S3_AVATAR_BUCKET="humbug-user-avatars"

    MIXPANEL_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
else:
    S3_KEY="xxxxxxxxxxxxxxxxxxxx"
    S3_SECRET_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    S3_BUCKET="humbug-user-uploads-test"
    S3_AVATAR_BUCKET="humbug-user-avatars-test"

    MIXPANEL_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
