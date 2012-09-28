# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: admin.py 3 2008-11-18 07:33:52Z jarek.zgoda $'


from django.contrib import admin

from confirmation.models import Confirmation


admin.site.register(Confirmation)