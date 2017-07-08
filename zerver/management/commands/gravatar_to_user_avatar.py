from __future__ import absolute_import

from typing import Any

from argparse import ArgumentParser
import requests
from zerver.models import UserProfile
from zerver.lib.avatar_hash import gravatar_hash
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.upload import upload_avatar_image
from django.core.files.uploadedfile import SimpleUploadedFile

class Command(ZulipBaseCommand):
    help = """Migrate the specified user's Gravatar over to an avatar that we serve.  If two
email addresses are specified, use the Gravatar for the first and upload the image
for both email addresses."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('old_email', metavar='<old email>', type=str,
                            help="user whose Gravatar should be migrated")
        parser.add_argument('new_email', metavar='<new email>', type=str, nargs='?', default=None,
                            help="user to copy the Gravatar to")
        self.add_realm_args(parser)

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        old_email = options['old_email']

        if options['new_email']:
            new_email = options['new_email']
        else:
            new_email = old_email

        realm = self.get_realm(options)
        gravatar_url = "https://secure.gravatar.com/avatar/%s?d=identicon" % (gravatar_hash(old_email),)
        gravatar_data = requests.get(gravatar_url).content
        gravatar_file = SimpleUploadedFile('gravatar.jpg', gravatar_data, 'image/jpeg')

        user_profile = self.get_user(old_email, realm)
        upload_avatar_image(gravatar_file, user_profile, user_profile)
        user_profile.avatar_source = UserProfile.AVATAR_FROM_USER
        user_profile.save(update_fields=['avatar_source'])

        if old_email != new_email:
            gravatar_file.seek(0)
            user_profile = self.get_user(new_email, realm)
            upload_avatar_image(gravatar_file, user_profile, user_profile)
            user_profile.avatar_source = UserProfile.AVATAR_FROM_USER
            user_profile.save(update_fields=['avatar_source'])
