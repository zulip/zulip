from __future__ import absolute_import
from __future__ import print_function
from optparse import make_option

from typing import Any, Text

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from zerver.lib.actions import Realm, do_create_realm, set_default_streams
from zerver.models import RealmAlias, can_add_alias, get_realm_by_string_id

if settings.ZILENCER_ENABLED:
    from zilencer.models import Deployment

import re
import sys

class Command(BaseCommand):
    help = """Create a realm.

Usage: ./manage.py create_realm --string_id=acme --name='Acme'"""

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument('-d', '--domain',
                            dest='domain',
                            type=str,
                            help='The domain for the realm.')

        parser.add_argument('-s', '--string_id',
                            dest='string_id',
                            type=str,
                            help="A short name for the realm. If this "
                                 "installation uses subdomains, this will be "
                                 "used as the realm's subdomain.")

        parser.add_argument('-n', '--name',
                            dest='name',
                            type=str,
                            help='The user-visible name for the realm.')

        parser.add_argument('--corporate',
                            dest='org_type',
                            action="store_const",
                            const=Realm.CORPORATE,
                            help='Is a corporate org_type')

        parser.add_argument('--community',
                            dest='org_type',
                            action="store_const",
                            const=Realm.COMMUNITY,
                            default=None,
                            help='Is a community org_type. Is the default.')

        parser.add_argument('--deployment',
                            dest='deployment_id',
                            type=int,
                            default=None,
                            help='Optionally, the ID of the deployment you '
                                 'want to associate the realm with.')

    def validate_domain(self, domain):
        # type: (str) -> None
        # Domains can't contain whitespace if they are to be used in memcached
        # keys. Seems safer to leave that as the default case regardless of
        # which backing store we use.
        if re.search("\s", domain):
            raise ValueError("Domains can't contain whitespace")

        # Domains must look like domains, ie have the structure of
        # <subdomain(s)>.<tld>. One reason for this is that bots need
        # to have valid looking emails.
        if len(domain.split(".")) < 2:
            raise ValueError("Domains must contain a '.'")

        if not can_add_alias(domain):
            raise ValueError("Domain already assigned to an existing realm")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        string_id = options["string_id"]
        name = options["name"]
        domain = options["domain"]

        if not name or not string_id:
            print("\033[1;31mPlease provide a name and string_id.\033[0m\n", file=sys.stderr)
            self.print_help("./manage.py", "create_realm")
            exit(1)

        if options["deployment_id"] is not None and not settings.ZILENCER_ENABLED:
            print("\033[1;31mExternal deployments are not supported on voyager deployments.\033[0m\n", file=sys.stderr)
            exit(1)

        if domain is not None:
            self.validate_domain(domain)

        if get_realm_by_string_id(string_id) is not None:
            raise ValueError("string_id taken. Please choose another one.")

        realm, created = do_create_realm(string_id, name, org_type=options["org_type"])
        if created:
            print(string_id, "created.")
            if domain:
                RealmAlias.objects.create(realm=realm, domain=domain)
                print("RealmAlias %s created for realm %s" % (domain, string_id))
            if options["deployment_id"] is not None:
                deployment = Deployment.objects.get(id=options["deployment_id"])
                deployment.realms.add(realm)
                deployment.save()
                print("Added to deployment", str(deployment.id))
            elif settings.PRODUCTION and settings.ZILENCER_ENABLED:
                deployment = Deployment.objects.get(base_site_url="https://zulip.com/")
                deployment.realms.add(realm)
                deployment.save()
            # In the else case, we are not using the Deployments feature.
            stream_dict = {
                "social": {"description": "For socializing", "invite_only": False},
                "engineering": {"description": "For engineering", "invite_only": False}
            } # type: Dict[Text, Dict[Text, Any]]
            set_default_streams(realm, stream_dict)

            print("\033[1;36mDefault streams set to social,engineering,zulip!\033[0m")
        else:
            print(string_id, "already exists.")
