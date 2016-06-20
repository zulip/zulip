# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: util.py 3 2008-11-18 07:33:52Z jarek.zgoda $'

from django.conf import settings

def get_status_field(app_label, model_name):
    model = '%s.%s' % (app_label, model_name)
    mapping = getattr(settings, 'STATUS_FIELDS', {})
    return mapping.get(model, 'status')
