from django.core.management.base import NoArgsCommand

from django.contrib.auth.models import User
from zephyr.models import Zephyr, UserProfile, ZephyrClass

import datetime
import random

class Command(NoArgsCommand):
    help = "Populate a test database"

    def handle_noargs(self, **options):
        for klass in [Zephyr, ZephyrClass, UserProfile, User]:
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
        
        # Create some test zephyrs, including:
        # - multiple classes
        # - multiple instances per class
        # - multiple zephyrs per instance
        # - both single and multi-line content
        users = [user.id for user in User.objects.all()]
        zephyr_classes = [klass.id for klass in ZephyrClass.objects.all()]
        texts = file("zephyr/management/commands/test_zephyrs.txt", "r").readlines()
        offset = 0
        while offset < len(texts):
            new_zephyr = Zephyr()
            new_zephyr.sender = UserProfile.objects.get(id=random.choice(users))
            length = random.randint(1, 5)
            new_zephyr.content = "".join(texts[offset: offset + length])
            offset += length
            new_zephyr.zephyr_class = ZephyrClass.objects.get(id=random.choice(zephyr_classes))
            new_zephyr.instance = new_zephyr.zephyr_class.name + str(random.randint(1, 3))
            new_zephyr.pub_date = datetime.datetime.utcnow()
            new_zephyr.save()

        self.stdout.write("Successfully populated test database.")
