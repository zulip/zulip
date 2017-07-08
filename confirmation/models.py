# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: models.py 28 2009-10-22 15:03:02Z jarek.zgoda $'

import datetime
import re

from django.db import models
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils.timezone import now as timezone_now

from zerver.lib.send_email import send_email
from zerver.lib.utils import generate_random_token
from zerver.models import PreregistrationUser, EmailChangeStatus
from typing import Any, Dict, Optional, Text, Union

B16_RE = re.compile('^[a-f0-9]{40}$')

def generate_key():
    # type: () -> str
    return generate_random_token(40)

def get_object_from_key(confirmation_key):
    # type: (str) -> Union[bool, PreregistrationUser, EmailChangeStatus]
    if B16_RE.search(confirmation_key):
        try:
            confirmation = Confirmation.objects.get(confirmation_key=confirmation_key)
        except Confirmation.DoesNotExist:
            return False

        time_elapsed = timezone_now() - confirmation.date_sent
        if time_elapsed.total_seconds() > settings.EMAIL_CONFIRMATION_DAYS * 24 * 3600:
            return False

        obj = confirmation.content_object
        obj.status = getattr(settings, 'STATUS_ACTIVE', 1)
        obj.save(update_fields=['status'])
        return obj
    return False

def create_confirmation_link(obj, host, confirmation_type):
    # type: (Union[ContentType, int], str, int) -> str
    key = generate_key()
    Confirmation.objects.create(content_object=obj, date_sent=timezone_now(), confirmation_key=key,
                                type=confirmation_type)
    return confirmation_url(key, host, confirmation_type)

def confirmation_url(confirmation_key, host, confirmation_type):
    # type: (str, str, int) -> str
    return '%s%s%s' % (settings.EXTERNAL_URI_SCHEME,
                       host,
                       reverse(_properties[confirmation_type].url_name,
                               kwargs={'confirmation_key': confirmation_key}))

class Confirmation(models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()  # type: int
    content_object = GenericForeignKey('content_type', 'object_id')
    date_sent = models.DateTimeField()  # type: datetime.datetime
    confirmation_key = models.CharField(max_length=40)  # type: str

    # The following list is the set of valid types
    USER_REGISTRATION = 1
    INVITATION = 2
    EMAIL_CHANGE = 3
    UNSUBSCRIBE = 4
    SERVER_REGISTRATION = 5
    type = models.PositiveSmallIntegerField()  # type: int

    def __unicode__(self):
        # type: () -> Text
        return '<Confirmation: %s>' % (self.content_object,)

class ConfirmationType(object):
    def __init__(self, url_name):
        # type: (str) -> None
        self.url_name = url_name

_properties = {
    Confirmation.USER_REGISTRATION: ConfirmationType('confirmation.views.confirm'),
    Confirmation.INVITATION: ConfirmationType('confirmation.views.confirm'),
    Confirmation.EMAIL_CHANGE: ConfirmationType('zerver.views.user_settings.confirm_email_change'),
}

# Conirmation pathways for which there is no content_object that we need to
# keep track of.

def check_key_is_valid(creation_key):
    # type: (Text) -> bool
    if not RealmCreationKey.objects.filter(creation_key=creation_key).exists():
        return False
    days_sofar = (timezone_now() - RealmCreationKey.objects.get(creation_key=creation_key).date_created).days
    # Realm creation link expires after settings.REALM_CREATION_LINK_VALIDITY_DAYS
    if days_sofar <= settings.REALM_CREATION_LINK_VALIDITY_DAYS:
        return True
    return False

def generate_realm_creation_url():
    # type: () -> Text
    key = generate_key()
    RealmCreationKey.objects.create(creation_key=key, date_created=timezone_now())
    return u'%s%s%s' % (settings.EXTERNAL_URI_SCHEME,
                        settings.EXTERNAL_HOST,
                        reverse('zerver.views.create_realm',
                                kwargs={'creation_key': key}))

class RealmCreationKey(models.Model):
    creation_key = models.CharField('activation key', max_length=40)
    date_created = models.DateTimeField('created', default=timezone_now)
