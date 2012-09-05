from django.core.management.base import BaseCommand
from django.utils.timezone import utc

from django.contrib.auth.models import User
from zephyr.models import Zephyr, UserProfile, ZephyrClass, Recipient, Subscription

import datetime
import random
from optparse import make_option

class Command(BaseCommand):
    help = "Populate a test database"

    option_list = BaseCommand.option_list + (
        make_option('-n', '--num-zephyrs',
                    dest='num_zephyrs',
                    type='int',
                    default=100,
                    help='The number of zephyrs to create.'),
        )

    def handle(self, **options):
        for klass in [Zephyr, ZephyrClass, UserProfile, User, Recipient, Subscription]:
            klass.objects.all().delete()

        # Create test Users (UserProfiles are automatically created,
        # as are subscriptions to the ability to receive personals).
        usernames = ["othello", "iago", "prospero", "cordelia", "hamlet"]
        for username in usernames:
            u = User.objects.create_user(username=username, password=username)
            u.save()

        # Create public classes.
        for name in ["Verona", "Denmark", "Scotland", "Venice", "Rome"]:
            new_class = ZephyrClass(name=name)
            new_class.save()

            recipient = Recipient(type_id=new_class.pk, type="class")
            recipient.save()

        # Create some test zephyrs, including:
        # - multiple classes
        # - multiple instances per class
        # - multiple zephyrs per instance
        # - both single and multi-line content
        users = [user.id for user in User.objects.all()]
        recipient_classes = [klass.id for klass in Recipient.objects.filter(type="class")]
        texts = file("zephyr/management/commands/test_zephyrs.txt", "r").readlines()
        offset = 0
        num_zephyrs = 0
        while num_zephyrs < options["num_zephyrs"]:
            new_zephyr = Zephyr()
            new_zephyr.sender = UserProfile.objects.get(id=random.choice(users))
            length = random.randint(1, 5)
            new_zephyr.content = "".join(texts[offset: offset + length])
            offset += length
            offset = offset % len(texts)
            new_zephyr.recipient = Recipient.objects.get(id=random.choice(recipient_classes))
            zephyr_class = ZephyrClass.objects.get(pk=new_zephyr.recipient.type_id)
            new_zephyr.instance = zephyr_class.name + str(random.randint(1, 3))
            new_zephyr.pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)
            new_zephyr.save()
            num_zephyrs += 1

        # Create subscriptions
        profiles = UserProfile.objects.all()
        for i, profile in enumerate(profiles):
            # Subscribe to some classes.
            for recipient in recipient_classes[:int(len(recipient_classes) * float(i)/len(profiles)) + 1]:
                new_subscription = Subscription(userprofile_id=profile,
                                                recipient_id=Recipient.objects.get(id=recipient))
                new_subscription.save()

        self.stdout.write("Successfully populated test database.\n")
