# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: models.py 28 2009-10-22 15:03:02Z jarek.zgoda $'

import re

from django.db import models
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.conf import settings
from django.template import loader, Context
from django.contrib.sites.models import Site
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone

from confirmation.util import get_status_field
from zerver.lib.utils import generate_random_token
from zerver.models import PreregistrationUser, EmailChangeStatus
from typing import Any, Dict, Optional, Text, Union

B16_RE = re.compile('^[a-f0-9]{40}$')

def check_key_is_valid(creation_key):
    # type: (Text) -> bool
    if not RealmCreationKey.objects.filter(creation_key=creation_key).exists():
        return False
    days_sofar = (timezone.now() - RealmCreationKey.objects.get(creation_key=creation_key).date_created).days
    # Realm creation link expires after settings.REALM_CREATION_LINK_VALIDITY_DAYS
    if days_sofar <= settings.REALM_CREATION_LINK_VALIDITY_DAYS:
        return True
    return False

def generate_key():
    # type: () -> Text
    return generate_random_token(40)

def generate_activation_url(key, host=None):
    # type: (Text, Optional[str]) -> Text
    if host is None:
        host = settings.EXTERNAL_HOST
    return u'%s%s%s' % (settings.EXTERNAL_URI_SCHEME,
                        host,
                        reverse('confirmation.views.confirm',
                                kwargs={'confirmation_key': key}))

def generate_realm_creation_url():
    # type: () -> Text
    key = generate_key()
    RealmCreationKey.objects.create(creation_key=key, date_created=timezone.now())
    return u'%s%s%s' % (settings.EXTERNAL_URI_SCHEME,
                        settings.EXTERNAL_HOST,
                        reverse('zerver.views.create_realm',
                                kwargs={'creation_key': key}))

class ConfirmationManager(models.Manager):

    def confirm(self, confirmation_key):
        # type: (str) -> Union[bool, PreregistrationUser, EmailChangeStatus]
        if B16_RE.search(confirmation_key):
            try:
                confirmation = self.get(confirmation_key=confirmation_key)
            except self.model.DoesNotExist:
                return False

            max_days = self.get_link_validity_in_days()
            time_elapsed = timezone.now() - confirmation.date_sent
            if time_elapsed.total_seconds() > max_days * 24 * 3600:
                return False

            obj = confirmation.content_object
            status_field = get_status_field(obj._meta.app_label, obj._meta.model_name)
            setattr(obj, status_field, getattr(settings, 'STATUS_ACTIVE', 1))
            obj.save()
            return obj
        return False

    def get_link_for_object(self, obj, host=None):
        # type: (Union[ContentType, int], Optional[str]) -> Text
        key = generate_key()
        self.create(content_object=obj, date_sent=timezone.now(), confirmation_key=key)
        return self.get_activation_url(key, host=host)

    def get_activation_url(self, confirmation_key, host=None):
        # type: (Text, Optional[str]) -> Text
        return generate_activation_url(confirmation_key, host=host)

    def get_link_validity_in_days(self):
        # type: () -> int
        return getattr(settings, 'EMAIL_CONFIRMATION_DAYS', 10)

    def send_confirmation(self, obj, email_address, additional_context=None,
                          subject_template_path=None, body_template_path=None, html_body_template_path=None,
                          host=None, custom_body=None):
        # type: (ContentType, Text, Optional[Dict[str, Any]], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]) -> Confirmation
        confirmation_key = generate_key()
        current_site = Site.objects.get_current()
        activate_url = self.get_activation_url(confirmation_key, host=host)
        context = Context({
            'activate_url': activate_url,
            'current_site': current_site,
            'confirmation_key': confirmation_key,
            'target': obj,
            'days': getattr(settings, 'EMAIL_CONFIRMATION_DAYS', 10),
            'custom_body': custom_body,
        })
        if additional_context is not None:
            context.update(additional_context)
        if obj.realm is not None and obj.realm.is_zephyr_mirror_realm:
            template_name = "mituser"
        else:
            template_name = obj._meta.model_name
        templates = [
            'confirmation/%s_confirmation_email.subject' % (template_name,),
            'confirmation/confirmation_email.subject',
        ]
        if subject_template_path:
            template = loader.get_template(subject_template_path)
        else:
            template = loader.select_template(templates)
        subject = template.render(context).strip().replace(u'\n', u' ') # no newlines, please
        templates = [
            'confirmation/%s_confirmation_email.txt' % (template_name,),
            'confirmation/confirmation_email.txt',
        ]
        if body_template_path:
            template = loader.get_template(body_template_path)
        else:
            template = loader.select_template(templates)
        if html_body_template_path:
            html_template = loader.get_template(html_body_template_path)
        else:
            html_template = loader.get_template('confirmation/%s_confirmation_email.html' % (template_name,))
        body = template.render(context)
        if html_template:
            html_content = html_template.render(context)
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email_address], html_message=html_content)
        return self.create(content_object=obj, date_sent=timezone.now(), confirmation_key=confirmation_key)

class EmailChangeConfirmationManager(ConfirmationManager):
    def get_activation_url(self, key, host=None):
        # type: (Text, Optional[str]) -> Text
        if host is None:
            # This will raise exception if the key doesn't exist.
            host = self.get(confirmation_key=key).content_object.realm.host
        return u'%s%s%s' % (settings.EXTERNAL_URI_SCHEME,
                            host,
                            reverse('zerver.views.user_settings.confirm_email_change',
                                    kwargs={'confirmation_key': key}))

    def get_link_validity_in_days(self):
        # type: () -> int
        return settings.EMAIL_CHANGE_CONFIRMATION_DAYS

class Confirmation(models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    date_sent = models.DateTimeField('sent')
    confirmation_key = models.CharField('activation key', max_length=40)

    objects = ConfirmationManager()

    class Meta(object):
        verbose_name = 'confirmation email'
        verbose_name_plural = 'confirmation emails'

    def __unicode__(self):
        # type: () -> Text
        return 'confirmation email for %s' % (self.content_object,)

class EmailChangeConfirmation(Confirmation):
    class Meta(object):
        proxy = True

    objects = EmailChangeConfirmationManager()

class RealmCreationKey(models.Model):
    creation_key = models.CharField('activation key', max_length=40)
    date_created = models.DateTimeField('created', default=timezone.now)
