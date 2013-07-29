from __future__ import absolute_import

import sys
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.core import validators

from zerver.models import Realm, email_to_username
from zerver.lib.actions import do_create_user
from zerver.views import notify_new_user
from zerver.lib.initial_password import initial_password

class Command(BaseCommand):
    help = """Create the specified user with a default initial password.

A user MUST have ALREADY accepted the Terms of Service before creating their
account this way.
"""

    option_list = BaseCommand.option_list + (
        make_option('--this-user-has-accepted-the-tos',
                    dest='tos',
                    action="store_true",
                    default=False,
                    help='Acknowledgement that the user has already accepted the ToS.'),
        make_option('--domain',
                    dest='domain',
                    type='str',
                    help='The name of the existing realm to which to add the user.'),
        )

    def handle(self, *args, **options):
        if not options["tos"]:
            raise CommandError("""You must confirm that this user has accepted the
Terms of Service by passing --this-user-has-accepted-the-tos.""")

        if not options["domain"]:
            raise CommandError("""Please specify a realm by passing --domain.""")

        try:
            realm = Realm.objects.get(domain=options["domain"])
        except Realm.DoesNotExist:
            raise CommandError("Realm does not exist.")

        try:
            email, full_name = args
            try:
                validators.validate_email(email)
            except ValidationError:
                raise CommandError("Invalid email address.")
        except ValueError:
            if len(args) != 0:
                raise CommandError("""Either specify an email and full name as two
parameters, or specify no parameters for interactive user creation.""")
            else:
                while True:
                    email = raw_input("Email: ")
                    try:
                        validators.validate_email(email)
                        break
                    except ValidationError:
                        print >> sys.stderr, "Invalid email address."
                full_name = raw_input("Full name: ")

        try:
            notify_new_user(do_create_user(email, initial_password(email),
                realm, full_name, email_to_username(email)),
                internal=True)
        except IntegrityError:
            raise CommandError("User already exists.")
