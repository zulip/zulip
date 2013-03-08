from optparse import make_option
from django.core.management.base import BaseCommand
from zephyr.models import UserProfile, User

class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = "Diff all the shared fields between User to UserProfile."

    def handle(self, *args, **options):
        for user_profile in UserProfile.objects.all():
            user = user_profile.user
            def diff_fields(user_version, user_profile_version):
                if user_version != user_profile_version:
                    print "Some values differ for %s!" % (user_profile.user.email,)
            diff_fields(user.email, user_profile.email)
            diff_fields(user.is_active, user_profile.is_active)
            diff_fields(user.is_staff, user_profile.is_staff)
            diff_fields(user.date_joined, user_profile.date_joined)

