from __future__ import absolute_import

from typing import Any

from argparse import ArgumentParser
import requests
from zerver.models import get_user_profile_by_email, UserProfile
from zerver.lib.avatar import gravatar_hash
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

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        old_email = options['old_email']

        if options['new_email']:
            new_email = options['new_email']
        else:
            new_email = old_email

        gravatar_url = "https://secure.gravatar.com/avatar/%s?d=identicon" % (gravatar_hash(old_email),)
        gravatar_data = requests.get(gravatar_url).content
        gravatar_file = SimpleUploadedFile('gravatar.jpg', gravatar_data, 'image/jpeg')

        try:
            user_profile = get_user_profile_by_email(old_email)
        except UserProfile.DoesNotExist:
            try:
                user_profile = get_user_profile_by_email(new_email)
            except UserProfile.DoesNotExist:
                raise CommandError("Could not find specified user")

        upload_avatar_image(gravatar_file, user_profile, old_email)
        if old_email != new_email:
            gravatar_file.seek(0)
            upload_avatar_image(gravatar_file, user_profile, new_email)

        user_profile.avatar_source = UserProfile.AVATAR_FROM_USER
        user_profile.save(update_fields=['avatar_source'])
