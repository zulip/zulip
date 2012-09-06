from django.contrib.auth.models import User
from django.test import TestCase
from django.utils.timezone import utc
from django.db.models import Q

from zephyr.models import Zephyr, UserProfile, ZephyrClass, Recipient, Subscription, \
    filter_by_subscriptions, Realm

import datetime
import os
import simplejson
import subprocess
subprocess.call("zephyr/tests/generate-fixtures");

class AuthedTestCase(TestCase):
    def login(self, username, password):
        return self.client.post('/accounts/login/',
                                {'username':username, 'password':password})

    def register(self, username, password):
        return self.client.post('/accounts/register/',
                                {'username':username, 'password':password, 'domain':'humbughq.com'})

    def get_userprofile(self, username):
        """
        Given a username, return the UserProfile object for the User that has
        that name.
        """
        # Usernames are unique, even across Realms.
        return UserProfile.objects.get(user=User.objects.get(username=username))

    def send_zephyr(self, sender_name, recipient_name, zephyr_type):
        sender = self.get_userprofile(sender_name)
        if zephyr_type == "personal":
            recipient = self.get_userprofile(recipient_name)
        else:
            recipient = ZephyrClass.objects.get(name=recipient_name, realm=sender.realm)
        recipient = Recipient.objects.get(type_id=recipient.id, type=zephyr_type)
        pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)
        Zephyr(sender=sender, recipient=recipient, instance="test", pub_date=pub_date).save()

    def users_subscribed_to_class(self, class_name, realm_domain):
        realm = Realm.objects.get(domain=realm_domain)
        zephyr_class = ZephyrClass.objects.get(name=class_name, realm=realm)
        recipient = Recipient.objects.get(type_id=zephyr_class.id, type="class")
        subscriptions = Subscription.objects.filter(recipient=recipient)

        return [subscription.userprofile.user for subscription in subscriptions]

    def zephyr_stream(self, user):
        return filter_by_subscriptions(Zephyr.objects.all(), user)

    def assert_json_success(self, result):
        """
        Successful POSTs return a 200 and JSON of the form {"result": "success",
        "msg": ""}.
        """
        self.assertEquals(result.status_code, 200)
        json = simplejson.loads(result.content)
        self.assertEquals(json.get("result"), "success")
        # We have a msg key for consistency with errors, but it typically has an
        # empty value.
        self.assertTrue("msg" in json)

    def assert_json_error(self, result, msg):
        """
        Invalid POSTs return a 400 and JSON of the form {"result": "error",
        "msg": "reason"}.
        """
        self.assertEquals(result.status_code, 400)
        json = simplejson.loads(result.content)
        self.assertEquals(json.get("result"), "error")
        self.assertEquals(json.get("msg"), msg)

class PublicURLTest(TestCase):
    """
    Account creation URLs are accessible even when not logged in. Authenticated
    URLs redirect to a page.
    """
    def fetch(self, urls, expected_status):
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, expected_status,
                             msg="Expected %d, received %d for %s" % (
                    expected_status, response.status_code, url))

    def test_public_urls(self):
        """
        Pages that should return a 200 when not logged in.
        """
        urls = {200: ["/accounts/home/", "/accounts/login/", "/accounts/logout/",
                      "/accounts/register/"],
                302: ["/", "/zephyr/", "/subscriptions/",
                      "/subscriptions/manage/", "/subscriptions/add/"]
                }
        for status_code, url_set in urls.iteritems():
            self.fetch(url_set, status_code)


class LoginTest(AuthedTestCase):
    """
    Logging in, registration, and logging out.
    """
    fixtures = ['zephyrs.json']

    def test_login(self):
        self.login("hamlet", "hamlet")
        user = User.objects.get(username='hamlet')
        self.assertEqual(self.client.session['_auth_user_id'], user.pk)

    def test_login_bad_password(self):
        self.login("hamlet", "wrongpassword")
        self.assertIsNone(self.client.session.get('_auth_user_id', None))

    def test_register(self):
        self.register("test", "test")
        user = User.objects.get(username='test')
        self.assertEqual(self.client.session['_auth_user_id'], user.pk)

    def test_logout(self):
        self.login("hamlet", "hamlet")
        self.client.post('/accounts/logout/')
        self.assertIsNone(self.client.session.get('_auth_user_id', None))


class PersonalZephyrsTest(AuthedTestCase):
    fixtures = ['zephyrs.json']

    def test_auto_subbed_to_personals(self):
        """
        Newly created users are auto-subbed to the ability to receive
        personals.
        """
        self.register("test", "test")
        user = User.objects.get(username='test')
        old_zephyrs = self.zephyr_stream(user)
        self.send_zephyr("test", "test", "personal")
        new_zephyrs = self.zephyr_stream(user)
        self.assertEqual(len(new_zephyrs) - len(old_zephyrs), 1)

        recipient = Recipient.objects.get(type_id=user.pk, type="personal")
        self.assertEqual(new_zephyrs[-1].recipient, recipient)

    def test_personal_to_self(self):
        """
        If you send a personal to yourself, only you see it.
        """
        old_users = list(User.objects.all())
        self.register("test1", "test1")

        old_zephyrs = []
        for user in old_users:
            old_zephyrs.append(len(self.zephyr_stream(user)))

        self.send_zephyr("test1", "test1", "personal")

        new_zephyrs = []
        for user in old_users:
            new_zephyrs.append(len(self.zephyr_stream(user)))

        self.assertEqual(old_zephyrs, new_zephyrs)

        user = User.objects.get(username="test1")
        recipient = Recipient.objects.get(type_id=user.pk, type="personal")
        self.assertEqual(self.zephyr_stream(user)[-1].recipient, recipient)

    def test_personal(self):
        """
        If you send a personal, only you and the recipient see it.
        """
        self.login("hamlet", "hamlet")

        old_sender = User.objects.filter(username="hamlet")
        old_sender_zephyrs = len(self.zephyr_stream(old_sender))

        old_recipient = User.objects.filter(username="othello")
        old_recipient_zephyrs = len(self.zephyr_stream(old_recipient))

        other_users = User.objects.filter(~Q(username="hamlet") & ~Q(username="othello"))
        old_other_zephyrs = []
        for user in other_users:
            old_other_zephyrs.append(len(self.zephyr_stream(user)))

        self.send_zephyr("hamlet", "othello", "personal")

        # Users outside the conversation don't get the zephyr.
        new_other_zephyrs = []
        for user in other_users:
            new_other_zephyrs.append(len(self.zephyr_stream(user)))

        self.assertEqual(old_other_zephyrs, new_other_zephyrs)

        # The personal zephyr is in the streams of both the sender and receiver.
        self.assertEqual(len(self.zephyr_stream(old_sender)),
                         old_sender_zephyrs + 1)
        self.assertEqual(len(self.zephyr_stream(old_recipient)),
                         old_recipient_zephyrs + 1)

        sender = User.objects.get(username="hamlet")
        receiver = User.objects.get(username="othello")
        recipient = Recipient.objects.get(type_id=receiver.pk, type="personal")
        self.assertEqual(self.zephyr_stream(sender)[-1].recipient, recipient)
        self.assertEqual(self.zephyr_stream(receiver)[-1].recipient, recipient)

    def test_personal_to_nonexistent_person(self):
        """
        """

class ClassZephyrsTest(AuthedTestCase):
    fixtures = ['zephyrs.json']

    def test_zephyr_to_class(self):
        """
        If you send a zephyr to a class, everyone subscribed to the class
        receives the zephyr.
        """
        subscribers = self.users_subscribed_to_class("Scotland", "humbughq.com")
        old_subscriber_zephyrs = []
        for subscriber in subscribers:
            old_subscriber_zephyrs.append(len(self.zephyr_stream(subscriber)))

        non_subscribers = [user for user in User.objects.all() if user not in subscribers]
        old_non_subscriber_zephyrs = []
        for non_subscriber in non_subscribers:
            old_non_subscriber_zephyrs.append(len(self.zephyr_stream(non_subscriber)))

        a_subscriber = subscribers[0].username
        self.login(a_subscriber, a_subscriber)
        self.send_zephyr(a_subscriber, "Scotland", "class")

        new_subscriber_zephyrs = []
        for subscriber in subscribers:
           new_subscriber_zephyrs.append(len(self.zephyr_stream(subscriber)))

        new_non_subscriber_zephyrs = []
        for non_subscriber in non_subscribers:
            new_non_subscriber_zephyrs.append(len(self.zephyr_stream(non_subscriber)))

        self.assertEqual(old_non_subscriber_zephyrs, new_non_subscriber_zephyrs)
        self.assertEqual(new_subscriber_zephyrs, [elt + 1 for elt in old_subscriber_zephyrs])

class PointerTest(AuthedTestCase):
    fixtures = ['zephyrs.json']

    def test_update_pointer(self):
        """
        Posting a pointer to /update (in the form {"pointer": pointer}) changes
        the pointer we store for your UserProfile.
        """
        self.login("hamlet", "hamlet")
        self.assertEquals(self.get_userprofile("hamlet").pointer, -1)
        result = self.client.post("/update", {"pointer": 1})
        self.assert_json_success(result)
        self.assertEquals(self.get_userprofile("hamlet").pointer, 1)

    def test_missing_pointer(self):
        """
        Posting json to /update which does not contain a pointer key/value pair
        returns a 400 and error message.
        """
        self.login("hamlet", "hamlet")
        self.assertEquals(self.get_userprofile("hamlet").pointer, -1)
        result = self.client.post("/update", {"foo": 1})
        self.assert_json_error(result, "Missing pointer")
        self.assertEquals(self.get_userprofile("hamlet").pointer, -1)

    def test_invalid_pointer(self):
        """
        Posting json to /update with an invalid pointer returns a 400 and error
        message.
        """
        self.login("hamlet", "hamlet")
        self.assertEquals(self.get_userprofile("hamlet").pointer, -1)
        result = self.client.post("/update", {"pointer": "foo"})
        self.assert_json_error(result, "Invalid pointer: must be an integer")
        self.assertEquals(self.get_userprofile("hamlet").pointer, -1)

    def test_pointer_out_of_range(self):
        """
        Posting json to /update with an out of range (< 0) pointer returns a 400
        and error message.
        """
        self.login("hamlet", "hamlet")
        self.assertEquals(self.get_userprofile("hamlet").pointer, -1)
        result = self.client.post("/update", {"pointer": -2})
        self.assert_json_error(result, "Invalid pointer value")
        self.assertEquals(self.get_userprofile("hamlet").pointer, -1)

class ZephyrPOSTTest(AuthedTestCase):
    fixtures = ['zephyrs.json']

    def test_zephyr_to_class(self):
        """
        Zephyring to a class to which you are subscribed is successful.
        """
        self.login("hamlet", "hamlet")
        result = self.client.post("/zephyr/", {"type": "class",
                                               "class": "Verona",
                                               "new_zephyr": "Test message",
                                               "instance": "Test instance"})
        self.assert_json_success(result)

    def test_zephyr_to_nonexistent_class(self):
        """
        Zephyring to a nonexistent class returns error JSON.
        """
        self.login("hamlet", "hamlet")
        result = self.client.post("/zephyr/", {"type": "class",
                                               "class": "foo nonexistent",
                                               "new_zephyr": "Test message",
                                               "instance": "Test instance"})
        self.assert_json_error(result, "Invalid class")

    def test_personal_zephyr(self):
        """
        Sending a personal zephyr to a valid username is successful.
        """
        self.login("hamlet", "hamlet")
        result = self.client.post("/zephyr/", {"type": "personal",
                                               "new_zephyr": "Test message",
                                               "recipient": "othello"})
        self.assert_json_success(result)

    def test_personal_zephyr_to_nonexistent_user(self):
        """
        Sending a personal zephyr to an invalid username returns error JSON.
        """
        self.login("hamlet", "hamlet")
        result = self.client.post("/zephyr/", {"type": "personal",
                                               "new_zephyr": "Test message",
                                               "recipient": "nonexistent"})
        self.assert_json_error(result, "Invalid username")

    def test_invalid_type(self):
        """
        Sending a zephyr of unknown type returns error JSON.
        """
        self.login("hamlet", "hamlet")
        result = self.client.post("/zephyr/", {"type": "invalid type"})
        self.assert_json_error(result, "Invalid zephyr type")
