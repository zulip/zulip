# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

from __future__ import absolute_import

__revision__ = '$Id: models.py 28 2009-10-22 15:03:02Z jarek.zgoda $'

import datetime

from django.db import models
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.timezone import now as timezone_now

from zerver.lib.send_email import send_email
from zerver.lib.utils import generate_random_token
from zerver.models import PreregistrationUser, EmailChangeStatus, MultiuseInvite
from random import SystemRandom
from six.moves import range
import string
from typing import Any, Dict, Optional, Text, Union

class ConfirmationKeyException(Exception):
    WRONG_LENGTH = 1
    EXPIRED = 2
    DOES_NOT_EXIST = 3

    def __init__(self, error_type):
        # type: (int) -> None
        super(ConfirmationKeyException, self).__init__()
        self.error_type = error_type

def render_confirmation_key_error(request, exception):
    # type: (HttpRequest, ConfirmationKeyException) -> HttpResponse
    if exception.error_type == ConfirmationKeyException.WRONG_LENGTH:
        return render(request, 'confirmation/link_malformed.html')
    if exception.error_type == ConfirmationKeyException.EXPIRED:
        return render(request, 'confirmation/link_expired.html')
    return render(request, 'confirmation/link_does_not_exist.html')

def generate_key():
    # type: () -> str
    generator = SystemRandom()
    # 24 characters * 5 bits of entropy/character = 120 bits of entropy
    return ''.join(generator.choice(string.ascii_lowercase + string.digits) for _ in range(24))

def get_object_from_key(confirmation_key):
    # type: (str) -> Union[MultiuseInvite, PreregistrationUser, EmailChangeStatus]
    # Confirmation keys used to be 40 characters
    if len(confirmation_key) not in (24, 40):
        raise ConfirmationKeyException(ConfirmationKeyException.WRONG_LENGTH)
    try:
        confirmation = Confirmation.objects.get(confirmation_key=confirmation_key)
    except Confirmation.DoesNotExist:
        raise ConfirmationKeyException(ConfirmationKeyException.DOES_NOT_EXIST)

    time_elapsed = timezone_now() - confirmation.date_sent
    if time_elapsed.total_seconds() > _properties[confirmation.type].validity_in_days * 24 * 3600:
        raise ConfirmationKeyException(ConfirmationKeyException.EXPIRED)

    obj = confirmation.content_object
    if hasattr(obj, "status"):
        obj.status = getattr(settings, 'STATUS_ACTIVE', 1)
        obj.save(update_fields=['status'])
    return obj

def create_confirmation_link(obj, host, confirmation_type, url_args=None):
    # type: (Union[ContentType, int], str, int, Optional[Dict[str, str]]) -> str
    key = generate_key()
    Confirmation.objects.create(content_object=obj, date_sent=timezone_now(), confirmation_key=key,
                                type=confirmation_type)
    return confirmation_url(key, host, confirmation_type, url_args)

def confirmation_url(confirmation_key, host, confirmation_type, url_args=None):
    # type: (str, str, int, Optional[Dict[str, str]]) -> str
    if url_args is None:
        url_args = {}
    url_args['confirmation_key'] = confirmation_key
    return '%s%s%s' % (settings.EXTERNAL_URI_SCHEME, host,
                       reverse(_properties[confirmation_type].url_name, kwargs=url_args))

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
    MULTIUSE_INVITE = 6
    type = models.PositiveSmallIntegerField()  # type: int

    def __unicode__(self):
        # type: () -> Text
        return '<Confirmation: %s>' % (self.content_object,)

class ConfirmationType(object):
    def __init__(self, url_name, validity_in_days=settings.CONFIRMATION_LINK_DEFAULT_VALIDITY_DAYS):
        # type: (str, int) -> None
        self.url_name = url_name
        self.validity_in_days = validity_in_days

_properties = {
    Confirmation.USER_REGISTRATION: ConfirmationType('confirmation.views.confirm'),
    Confirmation.INVITATION: ConfirmationType('confirmation.views.confirm',
                                              validity_in_days=settings.INVITATION_LINK_VALIDITY_DAYS),
    Confirmation.EMAIL_CHANGE: ConfirmationType('zerver.views.user_settings.confirm_email_change'),
    Confirmation.UNSUBSCRIBE: ConfirmationType('zerver.views.unsubscribe.email_unsubscribe',
                                               validity_in_days=1000000),  # should never expire
    Confirmation.MULTIUSE_INVITE: ConfirmationType('zerver.views.registration.accounts_home_from_multiuse_invite',
                                                   validity_in_days=settings.INVITATION_LINK_VALIDITY_DAYS)
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
