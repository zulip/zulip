# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: models.py 28 2009-10-22 15:03:02Z jarek.zgoda $'

import os
import re
import datetime
from hashlib import sha1

from django.db import models
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.conf import settings
from django.template import loader, Context
from django.contrib.sites.models import Site
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.utils.translation import ugettext_lazy as _

from confirmation.util import get_status_field

try:
    import mailer
    send_mail = mailer.send_mail
except ImportError:
    # no mailer app present, stick with default
    pass


SHA1_RE = re.compile('^[a-f0-9]{40}$')


class ConfirmationManager(models.Manager):

    def confirm(self, confirmation_key):
        if SHA1_RE.search(confirmation_key):
            try:
                confirmation = self.get(confirmation_key=confirmation_key)
            except self.model.DoesNotExist:
                return False
            obj = confirmation.content_object
            status_field = get_status_field(obj._meta.app_label, obj._meta.module_name)
            setattr(obj, status_field, getattr(settings, 'STATUS_ACTIVE', 1))
            obj.save()
            return obj
        return False

    def send_confirmation(self, obj, email_address):
        confirmation_key = sha1(str(os.urandom(12)) + str(email_address)).hexdigest()
        current_site = Site.objects.get_current()
        activate_url = u'https://%s%s' % (current_site.domain,
            reverse('confirmation.views.confirm', kwargs={'confirmation_key': confirmation_key}))
        context = Context({
            'activate_url': activate_url,
            'current_site': current_site,
            'confirmation_key': confirmation_key,
            'target': obj,
            'days': getattr(settings, 'EMAIL_CONFIRMATION_DAYS', 10),
        })
        templates = [
            'confirmation/%s_confirmation_email_subject.txt' % obj._meta.module_name,
            'confirmation/confirmation_email_subject.txt',
        ]
        template = loader.select_template(templates)
        subject = template.render(context).strip().replace(u'\n', u' ') # no newlines, please
        templates = [
            'confirmation/%s_confirmation_email_body.txt' % obj._meta.module_name,
            'confirmation/confirmation_email_body.txt',
        ]
        template = loader.select_template(templates)
        body = template.render(context)
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email_address])
        return self.create(content_object=obj, date_sent=datetime.datetime.now(), confirmation_key=confirmation_key)


class Confirmation(models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    date_sent = models.DateTimeField(_('sent'))
    confirmation_key = models.CharField(_('activation key'), max_length=40)

    objects = ConfirmationManager()

    class Meta:
        verbose_name = _('confirmation email')
        verbose_name_plural = _('confirmation emails')

    def __unicode__(self):
        return _('confirmation email for %s') % self.content_object
