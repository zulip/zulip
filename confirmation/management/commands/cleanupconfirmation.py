# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: cleanupconfirmation.py 5 2008-11-18 09:10:12Z jarek.zgoda $'


from django.core.management.base import NoArgsCommand

from confirmation.models import Confirmation


class Command(NoArgsCommand):
    help = 'Delete expired confirmations from database'

    def handle_noargs(self, **options):
        Confirmation.objects.delete_expired_confirmations()
