from __future__ import absolute_import

from typing import Any

from argparse import ArgumentParser
import requests
from zerver.models import get_user, get_realm, UserProfile
from zerver.lib.avatar_hash import gravatar_hash
from zerver.lib.upload import upload_avatar_image
from django.core.management.base import BaseCommand, CommandError
from django.core.files.uploadedfile import SimpleUploadedFile

class Command(BaseCommand):
    help = """Migrate the specified user's Gravatar over to an avatar that we serve.  If two
email addresses are specified, use the Gravatar for the first and upload the image
for both email addresses."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('old_email', metavar='<old email>', type=str,
                            help="user whose Gravatar should be migrated")
        parser.add_argument('new_email', metavar='<new email>', type=str, nargs='?', default=None,
                            help="user to copy the Gravatar to")
        parser.add_argument('--old-realm', dest='old_string_id', type=str,
                            help='The string_id of the realm for the old email')
        parser.add_argument('--new-realm', dest='new_string_id', type=str,
                            help='The string_id of the realm for the new email')

    def _get_user_profile(self, email, realm_string_id=None):
        if realm_string_id:
            realm = get_realm(realm_string_id)
            user_profile = get_user(email, realm)
        else:
            try:
                user_profile = UserProfile.objects.select_related().get(email__iexact=email.strip())
            except UserProfile.DoesNotExist:
                raise RuntimeError('No User Profile for email {}'.format(email))
            except UserProfile.MultipleObjectsReturned:
                raise RuntimeError(
                    'Multiple User Profiles for email {}. Please specify a realm string_id.'.format(email))
        return user_profile

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        old_email = options['old_email']
        old_string_id = options.get('old_string_id')

        if options['new_email']:
            new_email = options['new_email']
            new_string_id = options.get('new_string_id')
        else:
            new_email = old_email
            new_string_id = old_string_id

        gravatar_url = "https://secure.gravatar.com/avatar/%s?d=identicon" % (gravatar_hash(old_email),)
        gravatar_data = requests.get(gravatar_url).content
        gravatar_file = SimpleUploadedFile('gravatar.jpg', gravatar_data, 'image/jpeg')

        try:
            user_profile = self._get_user_profile(old_email, old_string_id)
            upload_avatar_image(gravatar_file, user_profile, user_profile)
            user_profile.avatar_source = UserProfile.AVATAR_FROM_USER
            user_profile.save(update_fields=['avatar_source'])
        except UserProfile.DoesNotExist:
            raise CommandError("Could not find specified user for email %s" % (old_email))

        if old_email != new_email:
            gravatar_file.seek(0)
            try:
                user_profile = self._get_user_profile(new_email, new_string_id)
                upload_avatar_image(gravatar_file, user_profile, user_profile)
                user_profile.avatar_source = UserProfile.AVATAR_FROM_USER
                user_profile.save(update_fields=['avatar_source'])
            except UserProfile.DoesNotExist:
                raise CommandError("Could not find specified user for email %s" % (new_email))
