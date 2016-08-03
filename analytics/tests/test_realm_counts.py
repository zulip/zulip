from zerver.lib.actions import do_create_stream
from zerver.models import Realm, UserProfile
from six import text_type

class TestPopulateRealmCount(TestCase):
    def setUp(self):
        # type: () -> None

        def create_user(realm, name, day_joined, **kwargs):
            # type: (Realm, text_type, bool, int) -> UserProfile
            return UserProfile.objects.create(email=name + '@domain.com', full_name=name, short_name=name, realm=realm, date_joined=realm.date_created + timedelta(day=day_joined), **kwargs)

        realmA = Realm.objects.create(domain="domainA.com", name="Realm Name",
                                      date_created=datetime(year=2062, month=8, day=16, minutes=42, seconds=31))
        realmB = Realm.objects.create(domain="domainB.com", name="Realm Name",
                                      date_created=datetime(year=2063, month=4, day=29, minutes=8, seconds=27))
        usersA = {"A1 human" : create_user(realmA, "A1 human", 2),
                  "A2 human" : create_user(realmA, "A2 human", 5),
                  "A3 human" : create_user(realmA, "A3 human", 5),
                  "A10 bot"  : create_user(realmA, "A10 bot", 2, is_bot=True),
                  "A11 bot"  : create_user(realmA, "A11 bot", 5, is_bot=True)}
        usersB = {"B1 human" : create_user(realmB, "B1 human", 25),
                  "B2 human" : create_user(realmB, "B2 human", 50),
                  "B3 human" : create_user(realmB, "B3 human", 50),
                  "B10 bot"  : create_user(realmB, "B10 bot", 25, is_bot=True),
                  "B11 bot"  : create_user(realmB, "B11 bot", 50, is_bot=True)}
        do_create_stream(realmA, 'A123 stream') # subscribes all active non-bots
        usersA["A1 human"].is_active = False
        usersA["A1 human"].save()
        do_create_stream(realmA, 'A23 stream') # subscribes all active non-bots

        # more set-up

    def test_total_users_by_realm():
        pass
