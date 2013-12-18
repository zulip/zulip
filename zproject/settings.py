# Django settings for zulip project.
#
# DO NOT PUT ANY SECRETS IN THIS FILE.
# Those belong in local_settings.py.
import os
import platform
import time
import sys
import ConfigParser

from zerver.openid import openid_failure_handler

config_file = ConfigParser.RawConfigParser()
config_file.read("/etc/zulip/zulip.conf")

# Whether we're running in a production environment. Note that DEPLOYED does
# **not** mean hosted by us; customer sites are DEPLOYED and ENTERPRISE
# and as such should not for example assume they are the main Zulip site.
DEPLOYED = config_file.has_option('machine', 'deploy_type')
STAGING_DEPLOYED = DEPLOYED and config_file.get('machine', 'deploy_type') == 'staging'
TESTING_DEPLOYED = DEPLOYED and config_file.get('machine', 'deploy_type') == 'test'

ENTERPRISE = DEPLOYED and config_file.get('machine', 'deploy_type') == 'enterprise'

# Import variables like secrets from the local_settings file
# Import local_settings after determining the deployment/machine type
from local_settings import *

SERVER_GENERATION = int(time.time())

if not 'DEBUG' in globals():
    # Uncomment end of next line to test JS/CSS minification.
    DEBUG = not DEPLOYED # and platform.node() != 'your-machine'

TEMPLATE_DEBUG = DEBUG
TEST_SUITE = False

if DEBUG:
    INTERNAL_IPS = ('127.0.0.1',)
if TESTING_DEPLOYED or ENTERPRISE:
    # XXX we should probably tighten this for ENTERPRISE
    # Allow any hosts for our test instances, to reduce 500 spam
    ALLOWED_HOSTS = ['*']
elif DEPLOYED:
    # The IP addresses are for app.zulip.{com,net} and staging.zulip.{com,net}
    ALLOWED_HOSTS = ['localhost', '.humbughq.com', '54.214.48.144', '54.213.44.54',
                     '54.213.41.54', '54.213.44.58', '54.213.44.73',
                     '54.200.19.65', '54.201.95.104', '54.201.95.206',
                     '54.201.186.29', "54.200.111.22",
                     '54.245.120.64', '54.213.44.83', '.zulip.com', '.zulip.net']
else:
    ALLOWED_HOSTS = ['localhost']

DATABASES = {"default": {
    'ENGINE': 'django.db.backends.postgresql_psycopg2',
    'NAME': 'zulip',
    'USER': 'zulip',
    'PASSWORD': '', # Authentication done via certificates
    'HOST': 'postgres.zulip.net',
    'SCHEMA': 'zulip',
    'CONN_MAX_AGE': 600,
    'OPTIONS': {
        'sslmode': 'verify-full',
        'autocommit': True,
        },
    },
}

if ENTERPRISE:
    DATABASES["default"].update({
            # Host = '' => connect through a local socket
            'HOST': '',
            'OPTIONS': {
                'autocommit': True,
            }
            })
elif not DEPLOYED:
    DATABASES["default"].update({
            'PASSWORD': LOCAL_DATABASE_PASSWORD,
            'HOST': 'localhost',
            'OPTIONS': {
                'autocommit': True,
            }
            })
    INTERNAL_ZULIP_USERS = []

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
# We set this site's domain to 'zulip.com' in populate_db.
SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

DEPLOY_ROOT = os.path.join(os.path.realpath(os.path.dirname(__file__)), '..')
TEMPLATE_DIRS = ( os.path.join(DEPLOY_ROOT, 'templates'), )

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

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
CSRF_FAILURE_VIEW = 'zerver.middleware.csrf_failure'

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
if DEPLOYED:
    TEMPLATE_LOADERS = (
        ('django.template.loaders.cached.Loader',
         TEMPLATE_LOADERS),
        )

MIDDLEWARE_CLASSES = (
    # Our logging middleware should be the first middleware item.
    'zerver.middleware.TagRequests',
    'zerver.middleware.LogRequests',
    'zerver.middleware.JsonErrorHandler',
    'zerver.middleware.RateLimitMiddleware',
    'zerver.middleware.FlushDisplayRecipientCache',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)

ANONYMOUS_USER_ID = None

AUTH_USER_MODEL = "zerver.UserProfile"

TEST_RUNNER = 'zerver.tests.Runner'

ROOT_URLCONF = 'zproject.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'zproject.wsgi.application'

INSTALLED_APPS = [
    'django.contrib.auth',
    'zproject.authhack',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'south',
    'django_openid_auth',
    'confirmation',
    'guardian',
    'pipeline',
    'zerver',
]

if not ENTERPRISE:
    INSTALLED_APPS += [
        'analytics',
        'zilencer',
    ]

LOCAL_STATSD = (False)
USING_STATSD = (DEPLOYED and not TESTING_DEPLOYED and not ENTERPRISE) or LOCAL_STATSD

# These must be named STATSD_PREFIX for the statsd module
# to pick them up
if STAGING_DEPLOYED:
    STATSD_PREFIX = 'staging'
elif DEPLOYED:
    STATSD_PREFIX = 'app'
else:
    STATSD_PREFIX = 'user'

if USING_STATSD:
    if LOCAL_STATSD:
        STATSD_HOST = 'localhost'
    else:
        STATSD_HOST = 'stats.zulip.net'

    INSTALLED_APPS += ['django_statsd']
    STATSD_PORT = 8125
    STATSD_CLIENT = 'django_statsd.clients.normal'

RATE_LIMITING = True
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379

RATE_LIMITING_RULES = [
    (60, 100),     # 100 requests max every minute
    ]

# For any settings that are not defined in local_settings.py,
# we want to initialize them to sane default
DEFAULT_SETTINGS = {'TWITTER_CONSUMER_KEY': '',
                    'TWITTER_CONSUMER_SECRET': '',
                    'TWITTER_ACCESS_TOKEN_KEY': '',
                    'TWITTER_ACCESS_TOKEN_SECRET': '',
                    'EMBEDLY_KEY': '',
                    'EMAIL_GATEWAY_PATTERN': '',
                    'EMAIL_GATEWAY_EXAMPLE': '',
                    'EMAIL_GATEWAY_BOT': None,
                    'EMAIL_GATEWAY_LOGIN': None,
                    'EMAIL_GATEWAY_PASSWORD': None,
                    'EMAIL_GATEWAY_IMAP_SERVER': None,
                    'EMAIL_GATEWAY_IMAP_PORT': None,
                    'EMAIL_GATEWAY_IMAP_FOLDER': None,
                    'MANDRILL_API_KEY': '',
                    'S3_KEY': '',
                    'S3_SECRET_KEY': '',
                    'S3_BUCKET': '',
                    'S3_AVATAR_BUCKET': '',
                    'MIXPANEL_TOKEN': '',
                    'MAILCHIMP_API_KEY': '',
                    'LOCAL_UPLOADS_DIR': None,
                    'DROPBOX_APP_KEY': '',
                    'ERROR_REPORTING': True,
                    'NAME_CHANGES_DISABLED': False,
                    'DEPLOYMENT_ROLE_NAME': ADMIN_DOMAIN,
                    # The following bots only exist in non-ENTERPRISE installs
                    'ERROR_BOT': None,
                    'NEW_USER_BOT': None,
                    'NAGIOS_STAGING_SEND_BOT': None,
                    'NAGIOS_STAGING_RECEIVE_BOT': None,
                    'APNS_CERT_FILE': None,
                    'ANDROID_GCM_API_KEY': None,
                    'INITIAL_PASSWORD_SALT': None,
                    'FEEDBACK_BOT': 'feedback@zulip.com',
                    'FEEDBACK_BOT_NAME': 'Zulip Feedback Bot',
                    'API_SUPER_USERS': set(),
                    'ADMINS': '',
                    'INLINE_IMAGE_PREVIEW': True,
                    'CAMO_URI': None,
                    'ENABLE_FEEDBACK': True,
                    'FEEDBACK_EMAIL': None,
                    'ENABLE_GRAVATAR': True,
                    'DEFAULT_AVATAR_URI': '/static/images/default-avatar.png',
                    'AUTH_LDAP_SERVER_URI': "",
                    'EXTERNAL_URI_SCHEME': "https://",
                    }

for setting_name, setting_val in DEFAULT_SETTINGS.iteritems():
    if not setting_name in vars():
        vars()[setting_name] = setting_val

if ADMINS == "":
    ADMINS = (("Zulip Administrator", ZULIP_ADMINISTRATOR),)
MANAGERS = ADMINS

# These are the settings that manage.py checkconfig will check that
# user has filled in before starting the app.  It consists of a series
# of pairs of (setting name, default value that it must be changed from)
REQUIRED_SETTINGS = [("EXTERNAL_HOST", ""),
                     ("ZULIP_ADMINISTRATOR", ""),
                     ("ADMIN_DOMAIN", ""),
                     ("DEPLOYMENT_ROLE_KEY", ""),
                     # SECRET_KEY doesn't really need to be here, in
                     # that we set it automatically, but just in
                     # case, it seems worth having in this list
                     ("SECRET_KEY", ""),
                     ("AUTHENTICATION_BACKENDS", ()),
                     ("NOREPLY_EMAIL_ADDRESS", ""),
                     ("DEFAULT_FROM_EMAIL", ""),
                     ]

if "EXTERNAL_API_PATH" not in vars():
    EXTERNAL_API_PATH = EXTERNAL_HOST + "/api"
EXTERNAL_API_URI = EXTERNAL_URI_SCHEME + EXTERNAL_API_PATH

INTERNAL_BOTS = [ {'var_name': 'NOTIFICATION_BOT',
                   'email_template': 'notification-bot@%s',
                   'name': 'Notification Bot'},
                  {'var_name': 'EMAIL_GATEWAY_BOT',
                   'email_template': 'emailgateway@%s',
                   'name': 'Email Gateway'},
                  {'var_name': 'NAGIOS_SEND_BOT',
                   'email_template': 'nagios-send-bot@%s',
                   'name': 'Nagios Send Bot'},
                  {'var_name': 'NAGIOS_RECEIVE_BOT',
                   'email_template': 'nagios-receive-bot@%s',
                   'name': 'Nagios Receive Bot'} ]

INTERNAL_BOT_DOMAIN = "zulip.com"

# Set the realm-specific bot names
for bot in INTERNAL_BOTS:
    if not bot['var_name'] in vars():
        bot_email = bot['email_template'] % (INTERNAL_BOT_DOMAIN,)
        vars()[bot['var_name'] ] = bot_email

if EMAIL_GATEWAY_BOT not in API_SUPER_USERS:
    API_SUPER_USERS.add(EMAIL_GATEWAY_BOT)
if EMAIL_GATEWAY_PATTERN != "":
    EMAIL_GATEWAY_EXAMPLE = EMAIL_GATEWAY_PATTERN % ("support+abcdefg",)

if DEPLOYED:
    FEEDBACK_TARGET="https://staging.zulip.com/api"
else:
    FEEDBACK_TARGET="http://localhost:9991/api"

# Static files and minification

STATIC_URL = '/static/'

# ZulipStorage is a modified version of PipelineCachedStorage,
# and, like that class, it inserts a file hash into filenames
# to prevent the browser from using stale files from cache.
#
# Unlike PipelineStorage, it requires the files to exist in
# STATIC_ROOT even for dev servers.  So we only use
# ZulipStorage when not DEBUG.

# This is the default behavior from Pipeline, but we set it
# here so that urls.py can read it.
PIPELINE = not DEBUG

if DEBUG:
    STATICFILES_STORAGE = 'pipeline.storage.PipelineStorage'
    STATICFILES_FINDERS = (
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    )
    if PIPELINE:
        STATIC_ROOT = 'prod-static/serve'
    else:
        STATIC_ROOT = 'static/'
else:
    STATICFILES_STORAGE = 'zerver.storage.ZulipStorage'
    STATICFILES_FINDERS = (
        'zerver.finders.ZulipFinder',
    )
    if DEPLOYED or ENTERPRISE:
        STATIC_ROOT = '/home/zulip/prod-static'
    else:
        STATIC_ROOT = 'prod-static/serve'

STATICFILES_DIRS = ['static/']
STATIC_HEADER_FILE = 'zerver/static_header.txt'

# To use minified files in dev, set PIPELINE = True.  For the full
# cache-busting behavior, you must also set DEBUG = False.
#
# You will need to run update-prod-static after changing
# static files.

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
            'styles/thirdparty-fonts.css',
            'styles/fonts.css',
        ),
        'output_filename': 'min/portico.css'
    },
    # Two versions of the app CSS exist because of QTBUG-3467
    'app-fontcompat': {
        'source_filenames': (
            'third/bootstrap-notify/css/bootstrap-notify.css',
            'third/spectrum/spectrum.css',
            'styles/zulip.css',
            'styles/pygments.css',
            'styles/thirdparty-fonts.css',
            # We don't want fonts.css on QtWebKit, so its omitted here
        ),
        'output_filename': 'min/app-fontcompat.css'
    },
    'app': {
        'source_filenames': (
            'third/bootstrap-notify/css/bootstrap-notify.css',
            'third/spectrum/spectrum.css',
            'styles/zulip.css',
            'styles/pygments.css',
            'styles/thirdparty-fonts.css',
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

JS_SPECS = {
    'common': {
        'source_filenames': (
            'third/jquery/jquery-1.7.2.js',
            'third/underscore/underscore.js',
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
    'initial_invite': {
        'source_filenames': (
            'third/jquery-validate/jquery.validate.js',
            'js/initial_invite.js',
            ),
        'output_filename':  'min/initial_invite.js'
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
            'third/bootstrap-notify/js/bootstrap-notify.js',
            'third/html5-formdata/formdata.js',
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
            'third/lazyload/lazyload.js',
            'third/spectrum/spectrum.js',
            'third/winchan/winchan.js',
            'third/sockjs/sockjs-0.3.4.js',
            ('third/handlebars/handlebars.runtime.js'
                if PIPELINE
                else 'third/handlebars/handlebars.js'),

            'js/feature_flags.js',
            'js/summary.js',
            'js/util.js',
            'js/dict.js',
            'js/channel.js',
            'js/muting.js',
            'js/muting_ui.js',
            'js/setup.js',
            'js/viewport.js',
            'js/rows.js',
            'js/unread.js',
            'js/stream_list.js',
            'js/filter.js',
            'js/narrow.js',
            'js/reload.js',
            'js/notifications_bar.js',
            'js/compose_fade.js',
            'js/socket.js',
            'js/compose.js',
            'js/stream_color.js',
            'js/admin.js',
            'js/stream_data.js',
            'js/subs.js',
            'js/message_edit.js',
            'js/ui.js',
            'js/popovers.js',
            'js/typeahead_helper.js',
            'js/search_suggestion.js',
            'js/search.js',
            'js/composebox_typeahead.js',
            'js/navigate.js',
            'js/hotkey.js',
            'js/notifications.js',
            'js/hashchange.js',
            'js/invite.js',
            'js/message_list_view.js',
            'js/message_list.js',
            'js/alert_words.js',
            'js/alert_words_ui.js',
            'js/zulip.js',
            'js/activity.js',
            'js/colorspace.js',
            'js/timerender.js',
            'js/tutorial.js',
            'js/templates.js',
            'js/avatar.js',
            'js/settings.js',
            'js/tab_bar.js',
            'js/emoji.js',
            'js/referral.js'
        ],
        'output_filename': 'min/app.js'
    },
    'activity': {
        'source_filenames': (
            'third/sorttable/sorttable.js',
        ),
        'output_filename': 'min/activity.js'
    },
    # We also want to minify sockjs separately for the sockjs iframe transport
    'sockjs': {
        'source_filenames': ('third/sockjs/sockjs-0.3.4.js',),
        'output_filename': 'min/sockjs-0.3.4.min.js'
    },
}

app_srcs = JS_SPECS['app']['source_filenames']

if not DEBUG:
    # This file is generated by update-prod-static.
    # In dev we fetch individual templates using Ajax.
    app_srcs.insert(app_srcs.index('third/handlebars/handlebars.runtime.js') + 1,
                    'templates/compiled.js')

if MIXPANEL_TOKEN:
    # Mixpanel is not used on enterprise and throws an error when the
    # library is not included
    app_srcs.append('js/metrics.js')

PIPELINE_JS = {}  # Now handled in tools/minify-js
PIPELINE_JS_COMPRESSOR  = None

PIPELINE_CSS_COMPRESSOR = 'pipeline.compressors.yui.YUICompressor'
PIPELINE_YUI_BINARY     = '/usr/bin/env yui-compressor'

USING_RABBITMQ = DEPLOYED
RABBITMQ_USERNAME = 'zulip'

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

CACHES = {
    'default': {
        'BACKEND':  'django.core.cache.backends.memcached.PyLibMCCache',
        'LOCATION': '127.0.0.1:11211',
        'TIMEOUT':  3600
    },
    'database': {
        'BACKEND':  'django.core.cache.backends.db.DatabaseCache',
        'LOCATION':  'third_party_api_results',
        # Basically never timeout.  Setting to 0 isn't guaranteed
        # to work, see https://code.djangoproject.com/ticket/9595
        'TIMEOUT': 2000000000,
        'OPTIONS': {
            'MAX_ENTRIES': 100000000,
            'CULL_FREQUENCY': 10,
        }
    },
}

ZULIP_PATHS = [
    ("SERVER_LOG_PATH", "/var/log/zulip/server.log"),
    ("ERROR_FILE_LOG_PATH", "/var/log/zulip/errors.log"),
    ("MANAGEMENT_LOG_PATH", "/var/log/zulip/manage.log"),
    ("WORKER_LOG_PATH", "/var/log/zulip/workers.log"),
    ("PERSISTENT_QUEUE_FILENAME", "/home/zulip/tornado/event_queues.pickle"),
    ("JSON_PERSISTENT_QUEUE_FILENAME", "/home/zulip/tornado/event_queues.json"),
    ("EMAIL_MIRROR_LOG_PATH", "/var/log/zulip/email-mirror.log"),
    ("EMAIL_DELIVERER_LOG_PATH", "/var/log/zulip/email-deliverer.log"),
    ("LDAP_SYNC_LOG_PATH", "/var/log/zulip/sync_ldap_user_data.log"),
    ("QUEUE_ERROR_DIR", "/var/log/zulip/queue_error"),
    ("STATS_DIR", "/home/zulip/stats"),
    ("DIGEST_LOG_PATH", "/var/log/zulip/digest.log"),
    ]

if ENTERPRISE:
    EVENT_LOG_DIR = None
else:
    ZULIP_PATHS.append(("EVENT_LOG_DIR", "/home/zulip/logs/event_log"))

for (var, path) in ZULIP_PATHS:
    if not DEPLOYED:
        # if not DEPLOYED, store these files in the Zulip checkout
        path = os.path.basename(path)
    vars()[var] = path

ZULIP_WORKER_TEST_FILE = '/tmp/zulip-worker-test-file'


if len(sys.argv) > 2 and sys.argv[0].endswith('manage.py') and sys.argv[1] == 'process_queue':
    FILE_LOG_PATH = WORKER_LOG_PATH
else:
    FILE_LOG_PATH = SERVER_LOG_PATH

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'default': {
            'format': '%(asctime)s %(levelname)-8s %(message)s'
        }
    },
    'filters': {
        'ZulipLimiter': {
            '()': 'zerver.lib.logging_util.ZulipLimiter',
        },
        'EmailLimiter': {
            '()': 'zerver.lib.logging_util.EmailLimiter',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'nop': {
            '()': 'zerver.lib.logging_util.ReturnTrue',
        },
        'require_really_deployed': {
            '()': 'zerver.lib.logging_util.RequireReallyDeployed',
        },
    },
    'handlers': {
        'zulip_admins': {
            'level':     'ERROR',
            'class':     'zerver.handlers.AdminZulipHandler',
            # For testing the handler delete the next line
            'filters':   ['ZulipLimiter', 'require_debug_false', 'require_really_deployed'],
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
            'filename':    FILE_LOG_PATH,
            'when':        'D',
            'interval':    7,
            'backupCount': 100000000,
        },
        'errors_file': {
            'level':       'WARNING',
            'class':       'logging.handlers.TimedRotatingFileHandler',
            'formatter':   'default',
            'filename':    ERROR_FILE_LOG_PATH,
            'when':        'D',
            'interval':    7,
            'backupCount': 100000000,
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file', 'errors_file'],
            'level':    'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': (['zulip_admins'] if ERROR_REPORTING else [])
                        + ['console', 'file', 'errors_file'],
            'level':    'INFO',
            'propagate': False,
        },
        'zulip.requests': {
            'handlers': ['console', 'file', 'errors_file'],
            'level':    'INFO',
            'propagate': False,
        },
        'zulip.management': {
            'handlers': ['file', 'errors_file'],
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
    'zerver.context_processors.add_settings',
    'zerver.context_processors.add_metrics',
)

ACCOUNT_ACTIVATION_DAYS=7

LOGIN_REDIRECT_URL='/'
OPENID_SSO_SERVER_URL = 'https://www.google.com/accounts/o8/id'
OPENID_CREATE_USERS = True
OPENID_RENDER_FAILURE = openid_failure_handler

# Client-side polling timeout for get_events, in milliseconds.
# We configure this here so that the client test suite can override it.
# We already kill the connection server-side with heartbeat events,
# but it's good to have a safety.  This value should be greater than
# (HEARTBEAT_MIN_FREQ_SECS + 10)
POLL_TIMEOUT = 90 * 1000

# The new user tutorial is enabled by default, and disabled for
# client tests.
TUTORIAL_ENABLED = True

USING_SSO = ('zproject.backends.ZulipRemoteUserBackend' in AUTHENTICATION_BACKENDS)

if (len(AUTHENTICATION_BACKENDS) == 1 and
    AUTHENTICATION_BACKENDS[0] == "zproject.backends.ZulipRemoteUserBackend"):
    HOME_NOT_LOGGED_IN = "/accounts/login/sso"
    ONLY_SSO = True
else:
    HOME_NOT_LOGGED_IN = '/login'
    ONLY_SSO = False
AUTHENTICATION_BACKENDS += ('guardian.backends.ObjectPermissionBackend',)
AUTHENTICATION_BACKENDS += ('zproject.backends.ZulipDummyBackend',)

POPULATE_PROFILE_VIA_LDAP = bool(AUTH_LDAP_SERVER_URI)

if POPULATE_PROFILE_VIA_LDAP and \
       not 'zproject.backends.ZulipLDAPAuthBackend' in AUTHENTICATION_BACKENDS:
    AUTHENTICATION_BACKENDS += ('zproject.backends.ZulipLDAPUserPopulator',)
else:
    POPULATE_PROFILE_VIA_LDAP = 'zproject.backends.ZulipLDAPAuthBackend' in AUTHENTICATION_BACKENDS or POPULATE_PROFILE_VIA_LDAP

if DEPLOYED:
    FULL_NAVBAR    = False
else:
    FULL_NAVBAR    = True

# If an email host is not specified, fail silently and gracefully
if not EMAIL_HOST and DEPLOYED:
    EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
elif not DEPLOYED:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# For testing, you may want to have emails be printed to the console.
if not DEPLOYED:
    # Use fast password hashing for creating testing users when not
    # DEPLOYED
    PASSWORD_HASHERS = (
                'django.contrib.auth.hashers.SHA1PasswordHasher',
                'django.contrib.auth.hashers.PBKDF2PasswordHasher'
            )

if DEPLOYED:
    # Filter out user data
    DEFAULT_EXCEPTION_REPORTER_FILTER = 'zerver.filters.ZulipExceptionReporterFilter'

# We want all temporary uploaded files to be stored on disk.

FILE_UPLOAD_MAX_MEMORY_SIZE = 0

# We are not currently using embedly due to some performance issues, but
# we are keeping the code on master for now, behind this launch flag.
# If you turn this back on for dev, you will want it to be still False
# for running the tests, or you will need to ensure that embedly_client.is_supported()
# gets called before the tests run.
USING_EMBEDLY = False

# This is a debugging option only
PROFILE_ALL_REQUESTS = False
