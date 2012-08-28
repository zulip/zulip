from django.core.management.base import NoArgsCommand
from django.utils.timezone import utc

from django.contrib.auth.models import User
from zephyr.models import Zephyr, UserProfile, ZephyrClass, Recipient

import datetime
import random

class Command(NoArgsCommand):
    help = "Populate a test database"

    def handle_noargs(self, **options):
        for klass in [Zephyr, ZephyrClass, UserProfile, User, Recipient]:
            klass.objects.all().delete()
        
        # Create test Users (UserProfiles are automatically created).
        for username in ["othello", "iago", "prospero", "cordelia", "hamlet"]:
            u = User.objects.create_user(username=username, password=username)
            u.save()
        
        # Create classes.
        for name in ["Verona", "Denmark", "Scotland", "Venice", "Rome"]:
            new_class = ZephyrClass()
            new_class.name = name
            new_class.save()

            recipient = Recipient()
            recipient.user_or_class = new_class.pk
            recipient.type = "class"
            recipient.save()
        
        # Create some test zephyrs, including:
        # - multiple classes
        # - multiple instances per class
        # - multiple zephyrs per instance
        # - both single and multi-line content
        users = [user.id for user in User.objects.all()]
        recipients = [klass.id for klass in Recipient.objects.all()]
        texts = file("zephyr/management/commands/test_zephyrs.txt", "r").readlines()
        offset = 0
        while offset < len(texts):
            new_zephyr = Zephyr()
            new_zephyr.sender = UserProfile.objects.get(id=random.choice(users))
            length = random.randint(1, 5)
            new_zephyr.content = "".join(texts[offset: offset + length])
            offset += length
            new_zephyr.recipient = Recipient.objects.get(id=random.choice(recipients))
            zephyr_class = ZephyrClass.objects.get(pk=new_zephyr.recipient.pk)
            new_zephyr.instance = zephyr_class.name + str(random.randint(1, 3))
            new_zephyr.pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)
            new_zephyr.save()

        self.stdout.write("Successfully populated test database.\n")
