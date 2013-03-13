from optparse import make_option
from django.core.management.base import BaseCommand
from zephyr.lib.cache_helpers import fill_memcached_caches

class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = "Populate the memcached cache of messages."

    def handle(self, *args, **options):
        fill_memcached_caches()
