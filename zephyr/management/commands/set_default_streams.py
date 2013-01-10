from django.core.management.base import BaseCommand

from zephyr.models import Realm
from zephyr.lib.actions import set_default_streams, log_event

from optparse import make_option
import sys
import time

class Command(BaseCommand):
    help = """Set default streams for a realm

Users created under this realm will start out with these streams. This
command is not additive: if you re-run it on a domain with a different
set of default streams, those will be the new complete set of default
streams.

For example:

python manage.py set_default_streams --domain=foo.com --streams=foo,bar,baz
python manage.py set_default_streams --domain=foo.com --streams="foo,bar,baz with space"
python manage.py set_default_streams --domain=foo.com --streams=
"""

    option_list = BaseCommand.option_list + (
        make_option('-d', '--domain',
                    dest='domain',
                    type='str',
                    help='The name of the existing realm to which to attach default streams.'),
        make_option('-s', '--streams',
                    dest='streams',
                    type='str',
                    help='A comma-separated list of stream names.'),
        )

    def handle(self, **options):
        if options["domain"] is None or options["streams"] is None:
            print >>sys.stderr, "Please provide both a domain name and a default \
set of streams (which can be empty, with `--streams=`)."
            exit(1)

        stream_names = [stream.strip() for stream in options["streams"].split(",")]
        realm = Realm.objects.get(domain=options["domain"])
        set_default_streams(realm, stream_names)

        log_event({'type': 'default_streams',
                   'domain': realm.domain,
                   'streams': stream_names})
