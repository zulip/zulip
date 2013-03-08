from optparse import make_option
from django.core.management.base import BaseCommand
from zephyr.models import UserProfile, User

class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = "Copy all the shared fields from User to UserProfile."

    def handle(self, *args, **options):
        for user_profile in UserProfile.objects.all():
            user = user_profile.user
            user_profile.email = user.email
            user_profile.is_active = user.is_active
            user_profile.is_staff = user.is_staff
            user_profile.date_joined = user.date_joined
            user_profile.password = user.password
            user_profile.save(update_fields=["email", "is_active", "is_staff", "date_joined", "password"])

