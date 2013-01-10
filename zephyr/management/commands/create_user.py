import sys

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.utils.timezone import now
from django.core import validators

from zephyr.models import Realm
from zephyr.lib.actions import do_send_message, do_create_user
from zephyr.views import notify_new_user
from zephyr.lib.initial_password import initial_password

class Command(BaseCommand):
    help = "Create the specified user with a default initial password."

    def handle(self, *args, **options):
        try:
            email, full_name = args
            try:
                validators.validate_email(email)
            except ValidationError:
                raise CommandError("Invalid email address.")
        except ValueError:
            if len(args) != 0:
                raise CommandError("Either specify an email and full name" + \
                        "as two parameters, or specify no parameters for" + \
                        "interactive user creation.")
                return 1
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
            realm = Realm.objects.get(domain=email.split('@')[-1])
        except Realm.DoesNotExist:
            raise CommandError("Realm does not exist.")

        try:
            notify_new_user(do_create_user(email, initial_password(email),
                realm, full_name, email.split('@')[0]),
                internal=True)
        except IntegrityError:
            raise CommandError("User already exists.")
