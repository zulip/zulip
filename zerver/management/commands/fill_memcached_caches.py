from __future__ import absolute_import

from optparse import make_option
from django.core.management.base import BaseCommand
from zerver.lib.cache_helpers import fill_memcached_cache, cache_fillers

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--cache', dest="cache", default=None),)
    help = "Populate the memcached cache of messages."

    def handle(self, *args, **options):
        if options["cache"] is not None:
            return fill_memcached_cache(options["cache"])

        for cache in cache_fillers.keys():
            fill_memcached_cache(cache)

