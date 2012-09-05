from django.core.management.base import BaseCommand
from django.utils.timezone import utc

from django.contrib.auth.models import User
from zephyr.models import Zephyr, UserProfile, ZephyrClass, Recipient, \
    Subscription, Huddle, get_huddle

import datetime
import random
from optparse import make_option

class Command(BaseCommand):
    help = "Populate a test database"

    option_list = BaseCommand.option_list + (
        make_option('-n', '--num-zephyrs',
                    dest='num_zephyrs',
                    type='int',
                    default=120,
                    help='The number of zephyrs to create.'),
        make_option('--huddles',
                    dest='num_huddles',
                    type='int',
                    default=3,
                    help='The number of huddles to create.'),
        make_option('--personals',
                    dest='num_personals',
                    type='int',
                    default=6,
                    help='The number of personal pairs to create.'),
        make_option('--percent-huddles',
                    dest='percent_huddles',
                    type='float',
                    default=15,
                    help='The percent of messages to be huddles.'),
        make_option('--percent-personals',
                    dest='percent_personals',
                    type='float',
                    default=15,
                    help='The percent of messages to be personals.'),

        )

    def handle(self, **options):
        if options["percent_huddles"] + options["percent_personals"] > 100:
            self.stderr.write("Error!  More than 100% of messages allocated.\n")
            return

        for klass in [Zephyr, ZephyrClass, UserProfile, User, Recipient, Subscription, Huddle]:
            klass.objects.all().delete()

        # Create test Users (UserProfiles are automatically created,
        # as are subscriptions to the ability to receive personals).
        usernames = ["othello", "iago", "prospero", "cordelia", "hamlet"]
        for username in usernames:
            u = User.objects.create_user(username=username, password=username)
            u.save()
        users = [user.id for user in User.objects.all()]

        # Create public classes.
        for name in ["Verona", "Denmark", "Scotland", "Venice", "Rome"]:
            new_class = ZephyrClass(name=name)
            new_class.save()

            recipient = Recipient(type_id=new_class.pk, type="class")
            recipient.save()

        # Create several initial huddles
        huddle_members = {}
        for i in range(0, options["num_huddles"]):
            user_ids = random.sample(users, random.randint(3, 4))
            huddle_members[get_huddle(user_ids).id] = user_ids

        # Create several initial pairs for personals
        personals_pairs = []
        for i in range(0, options["num_personals"]):
            personals_pairs.append(random.sample(users, 2))

        recipient_classes = [klass.type_id for klass in Recipient.objects.filter(type="class")]
        recipient_huddles = [h.type_id for h in Recipient.objects.filter(type="huddle")]

        # Create subscriptions to classes
        profiles = UserProfile.objects.all()
        for i, profile in enumerate(profiles):
            # Subscribe to some classes.
            for recipient in recipient_classes[:int(len(recipient_classes) * float(i)/len(profiles)) + 1]:
                new_subscription = Subscription(userprofile_id=profile,
                                                recipient_id=Recipient.objects.get(type="class",
                                                                                   type_id=recipient))
                new_subscription.save()

        # Create some test zephyrs, including:
        # - multiple classes
        # - multiple instances per class
        # - multiple zephyrs per instance
        # - both single and multi-line content

        texts = file("zephyr/management/commands/test_zephyrs.txt", "r").readlines()
        offset = 0
        num_zephyrs = 0
        random_max = 1000000
        while num_zephyrs < options["num_zephyrs"]:
            new_zephyr = Zephyr()
            length = random.randint(1, 5)
            new_zephyr.content = "".join(texts[offset: offset + length])
            offset += length
            offset = offset % len(texts)

            randkey = random.randint(1, random_max)
            if (randkey <= random_max * options["percent_huddles"] / 100.):
                # huddle
                new_zephyr.recipient = Recipient.objects.get(type="huddle", type_id=random.choice(recipient_huddles))
                new_zephyr.sender = UserProfile.objects.get(id=random.choice(huddle_members[new_zephyr.recipient.type_id]))
            elif (randkey <= random_max * (options["percent_huddles"] + options["percent_personals"]) / 100.):
                # personals
                pair = random.choice(personals_pairs)
                random.shuffle(pair)
                new_zephyr.recipient = Recipient.objects.get(type="personal", type_id=pair[0])
                new_zephyr.sender = UserProfile.objects.get(id=pair[1])
            elif (randkey <= random_max * 1.0):
                # class
                new_zephyr.recipient = Recipient.objects.get(type="class", type_id=random.choice(recipient_classes))
                zephyr_class = ZephyrClass.objects.get(pk=new_zephyr.recipient.type_id)
                new_zephyr.sender = UserProfile.objects.get(id=random.choice(users))
                new_zephyr.instance = zephyr_class.name + str(random.randint(1, 3))
            new_zephyr.pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)
            new_zephyr.save()
            num_zephyrs += 1

        self.stdout.write("Successfully populated test database.\n")
