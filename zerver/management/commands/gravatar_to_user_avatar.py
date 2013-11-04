from __future__ import absolute_import

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

    def handle(self, *args, **kwargs):
        if len(args) == 0:
            raise CommandError("You must specify a user")
        if len(args) > 2:
            raise CommandError("Too many positional arguments")

        old_email = args[0]

        if len(args) == 2:
            new_email = args[1]
        elif len(args) == 1:
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
