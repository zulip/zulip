TIME_ZONE="America/New_York"
ALLOWED_HOSTS=['graphite.humbughq.com', 'graphite.zulip.net', 'stats1.zulip.net']

DATABASES = {
    'default': {
        'NAME': '/opt/graphite/storage/graphite.db',
        'ENGINE': 'django.db.backends.sqlite3',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': ''
    }
}
