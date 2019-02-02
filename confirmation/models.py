# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: models.py 28 2009-10-22 15:03:02Z jarek.zgoda $'

import datetime

from django.db import models
from django.db.models import CASCADE
from django.urls import reverse
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.timezone import now as timezone_now

from zerver.models import PreregistrationUser, EmailChangeStatus, MultiuseInvite, \
    UserProfile, Realm
from random import SystemRandom
import string
from typing import Dict, Optional, Union

class ConfirmationKeyException(Exception):
    WRONG_LENGTH = 1
    EXPIRED = 2
    DOES_NOT_EXIST = 3

    def __init__(self, error_type: int) -> None:
        super().__init__()
        self.error_type = error_type

def render_confirmation_key_error(request: HttpRequest, exception: ConfirmationKeyException) -> HttpResponse:
    if exception.error_type == ConfirmationKeyException.WRONG_LENGTH:
        return render(request, 'confirmation/link_malformed.html')
    if exception.error_type == ConfirmationKeyException.EXPIRED:
        return render(request, 'confirmation/link_expired.html')
    return render(request, 'confirmation/link_does_not_exist.html')

def generate_key() -> str:
    generator = SystemRandom()
    # 24 characters * 5 bits of entropy/character = 120 bits of entropy
    return ''.join(generator.choice(string.ascii_lowercase + string.digits) for _ in range(24))

ConfirmationObjT = Union[MultiuseInvite, PreregistrationUser, EmailChangeStatus]
def get_object_from_key(confirmation_key: str,
                        confirmation_type: int) -> ConfirmationObjT:
    # Confirmation keys used to be 40 characters
    if len(confirmation_key) not in (24, 40):
        raise ConfirmationKeyException(ConfirmationKeyException.WRONG_LENGTH)
    try:
        confirmation = Confirmation.objects.get(confirmation_key=confirmation_key,
                                                type=confirmation_type)
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

def create_confirmation_link(obj: ContentType, host: str,
                             confirmation_type: int,
                             url_args: Optional[Dict[str, str]]=None) -> str:
    key = generate_key()
    realm = None
    if hasattr(obj, 'realm'):
        realm = obj.realm
    Confirmation.objects.create(content_object=obj, date_sent=timezone_now(), confirmation_key=key,
                                realm=realm, type=confirmation_type)
    return confirmation_url(key, host, confirmation_type, url_args)

def confirmation_url(confirmation_key: str, host: str,
                     confirmation_type: int,
                     url_args: Optional[Dict[str, str]]=None) -> str:
    if url_args is None:
        url_args = {}
    url_args['confirmation_key'] = confirmation_key
    return '%s%s%s' % (settings.EXTERNAL_URI_SCHEME, host,
                       reverse(_properties[confirmation_type].url_name, kwargs=url_args))

class Confirmation(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=CASCADE)
    object_id = models.PositiveIntegerField()  # type: int
    content_object = GenericForeignKey('content_type', 'object_id')
    date_sent = models.DateTimeField()  # type: datetime.datetime
    confirmation_key = models.CharField(max_length=40)  # type: str
    realm = models.ForeignKey(Realm, null=True, on_delete=CASCADE)  # type: Optional[Realm]

    # The following list is the set of valid types
    USER_REGISTRATION = 1
    INVITATION = 2
    EMAIL_CHANGE = 3
    UNSUBSCRIBE = 4
    SERVER_REGISTRATION = 5
    MULTIUSE_INVITE = 6
    REALM_CREATION = 7
    REALM_REACTIVATION = 8
    type = models.PositiveSmallIntegerField()  # type: int

    def __str__(self) -> str:
        return '<Confirmation: %s>' % (self.content_object,)

class ConfirmationType:
    def __init__(self, url_name: str,
                 validity_in_days: int=settings.CONFIRMATION_LINK_DEFAULT_VALIDITY_DAYS) -> None:
        self.url_name = url_name
        self.validity_in_days = validity_in_days

_properties = {
    Confirmation.USER_REGISTRATION: ConfirmationType('check_prereg_key_and_redirect'),
    Confirmation.INVITATION: ConfirmationType('check_prereg_key_and_redirect',
                                              validity_in_days=settings.INVITATION_LINK_VALIDITY_DAYS),
    Confirmation.EMAIL_CHANGE: ConfirmationType('zerver.views.user_settings.confirm_email_change'),
    Confirmation.UNSUBSCRIBE: ConfirmationType('zerver.views.unsubscribe.email_unsubscribe',
                                               validity_in_days=1000000),  # should never expire
    Confirmation.MULTIUSE_INVITE: ConfirmationType(
        'zerver.views.registration.accounts_home_from_multiuse_invite',
        validity_in_days=settings.INVITATION_LINK_VALIDITY_DAYS),
    Confirmation.REALM_CREATION: ConfirmationType('check_prereg_key_and_redirect'),
    Confirmation.REALM_REACTIVATION: ConfirmationType('zerver.views.realm.realm_reactivation'),
}

def one_click_unsubscribe_link(user_profile: UserProfile, email_type: str) -> str:
    """
    Generate a unique link that a logged-out user can visit to unsubscribe from
    Zulip e-mails without having to first log in.
    """
    return create_confirmation_link(user_profile, user_profile.realm.host,
                                    Confirmation.UNSUBSCRIBE,
                                    url_args = {'email_type': email_type})

# Functions related to links generated by the generate_realm_creation_link.py
# management command.
# Note that being validated here will just allow the user to access the create_realm
# form, where they will enter their email and go through the regular
# Confirmation.REALM_CREATION pathway.
# Arguably RealmCreationKey should just be another ConfirmationObjT and we should
# add another Confirmation.type for this; it's this way for historical reasons.

def validate_key(creation_key: Optional[str]) -> Optional['RealmCreationKey']:
    """Get the record for this key, raising InvalidCreationKey if non-None but invalid."""
    if creation_key is None:
        return None
    try:
        key_record = RealmCreationKey.objects.get(creation_key=creation_key)
    except RealmCreationKey.DoesNotExist:
        raise RealmCreationKey.Invalid()
    time_elapsed = timezone_now() - key_record.date_created
    if time_elapsed.total_seconds() > settings.REALM_CREATION_LINK_VALIDITY_DAYS * 24 * 3600:
        raise RealmCreationKey.Invalid()
    return key_record

def generate_realm_creation_url(by_admin: bool=False) -> str:
    key = generate_key()
    RealmCreationKey.objects.create(creation_key=key,
                                    date_created=timezone_now(),
                                    presume_email_valid=by_admin)
    return '%s%s%s' % (settings.EXTERNAL_URI_SCHEME,
                       settings.EXTERNAL_HOST,
                       reverse('zerver.views.create_realm',
                               kwargs={'creation_key': key}))

class RealmCreationKey(models.Model):
    creation_key = models.CharField('activation key', max_length=40)
    date_created = models.DateTimeField('created', default=timezone_now)

    # True just if we should presume the email address the user enters
    # is theirs, and skip sending mail to it to confirm that.
    presume_email_valid = models.BooleanField(default=False)  # type: bool

    class Invalid(Exception):
        pass
