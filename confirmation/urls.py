# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: urls.py 3 2008-11-18 07:33:52Z jarek.zgoda $'


from django.conf.urls.defaults import *

from confirmation.views import confirm


urlpatterns = patterns('',
    (r'^(?P<confirmation_key>\w+)/$', confirm),
)