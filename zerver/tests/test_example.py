from datetime import timedelta
from unittest import mock

import orjson
import time_machine
from django.utils.timezone import now as timezone_now

from zerver.actions.users import do_change_can_create_users, do_change_user_role
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import access_stream_for_send_message
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message
from zerver.lib.users import is_administrator_role
from zerver.models import UserProfile, UserStatus
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.models.users import get_user_by_delivery_email


# Most Zulip tests use ZulipTestCase, which inherits from django.test.TestCase.
# We recommend learning Django basics first, so search the web for "django testing".
# A common first result is https://docs.djangoproject.com/en/3.2/topics/testing/
class TestBasics(ZulipTestCase):
    def test_basics(self) -> None:
        # Django's tests are based on Python's unittest module, so you
        # will see us use things like assertEqual, assertTrue, and assertRaisesRegex
        # quite often.
        # See https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertEqual
        self.assertEqual(7 * 6, 42)


class TestBasicUserStuff(ZulipTestCase):
    # Zulip has test fixtures with built-in users.  It's good to know
    # which users are special. For example, Iago is our built-in
    # realm administrator.  You can also modify users as needed.
    def test_users(self) -> None:
        # The example_user() helper returns a UserProfile object.
        hamlet = self.example_user("hamlet")
        self.assertEqual(hamlet.full_name, "King Hamlet")
        self.assertEqual(hamlet.role, UserProfile.ROLE_MEMBER)

        iago = self.example_user("iago")
        self.assertEqual(iago.role, UserProfile.ROLE_REALM_ADMINISTRATOR)

        polonius = self.example_user("polonius")
        self.assertEqual(polonius.role, UserProfile.ROLE_GUEST)

        self.assertEqual(self.example_email("cordelia"), "cordelia@zulip.com")

    def test_lib_functions(self) -> None:
        # This test is an example of testing a single library function.
        # Our tests aren't always at this level of granularity, but it's
        # often possible to write concise tests for library functions.

        # Get our UserProfile objects first.
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")

        # It is a good idea for your tests to clearly demonstrate a
        # **change** to a value.  So here we want to make sure that
        # do_change_user_role will change Hamlet such that
        # is_administrator_role becomes True, but we first assert it's
        # False.
        self.assertFalse(is_administrator_role(hamlet.role))

        # Tests should modify properties using the standard library
        # functions, like do_change_user_role. Modifying Django
        # objects and then using .save() can be buggy, as doing so can
        # fail to update caches, RealmAuditLog, or related tables properly.
        do_change_user_role(hamlet, UserProfile.ROLE_REALM_OWNER, acting_user=iago)
        self.assertTrue(is_administrator_role(hamlet.role))

        # After we promote Hamlet, we also demote him.  Testing state
        # changes like this in a single test can be a good technique,
        # although we also don't want tests to be too long.
        #
        # Important note: You don't need to undo changes done in the
        # test at the end. Every test is run inside a database
        # transaction, that is reverted after the test completes.
        # There are a few exceptions, where tests interact with the
        # filesystem (E.g. uploading files), which is generally
        # handled by the setUp/tearDown methods for the test class.
        do_change_user_role(hamlet, UserProfile.ROLE_MODERATOR, acting_user=iago)
        self.assertFalse(is_administrator_role(hamlet.role))


class TestFullStack(ZulipTestCase):
    # Zulip's backend tests are largely full-stack integration tests,
    # making use of some strategic mocking at times, though we do use
    # unit tests for some classes of low-level functions.
    #
    # See https://zulip.readthedocs.io/en/latest/testing/philosophy.html
    # for details on this and other testing design decisions.
    def test_client_get(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        # Most full-stack tests require you to log in the user.
        # The login_user helper basically wraps Django's client.login().
        self.login_user(hamlet)

        # Zulip's client_get is a very thin wrapper on Django's client.get.
        # We always use the Zulip wrappers for client_get and client_post.
        url = f"/json/users/{cordelia.id}"
        result = self.client_get(url)

        # Almost every meaningful full-stack test for a "happy path" situation
        # uses assert_json_success().
        self.assert_json_success(result)

        # When we unpack the result.content object, we prefer the orjson library.
        content = orjson.loads(result.content)

        # In this case we will validate the entire payload. It's good to use
        # concrete values where possible, but some things, like "cordelia.id",
        # are somewhat unpredictable, so we don't hard code values.
        #
        # Others, like email and full_name here, are fields we haven't
        # changed, and thus explicit values would just be hardcoding
        # test database defaults in additional places.
        self.assertEqual(
            content["user"],
            dict(
                avatar_url=content["user"]["avatar_url"],
                avatar_version=1,
                date_joined=content["user"]["date_joined"],
                delivery_email=None,
                email=cordelia.email,
                full_name=cordelia.full_name,
                is_active=True,
                is_admin=False,
                is_billing_admin=False,
                is_bot=False,
                is_guest=False,
                is_owner=False,
                role=UserProfile.ROLE_MEMBER,
                timezone="Etc/UTC",
                user_id=cordelia.id,
            ),
        )

    def test_client_post(self) -> None:
        # Here we're gonna test a POST call to /json/users, and it's
        # important that we not only check the payload, but we make
        # sure that the intended side effects actually happen.
        iago = self.example_user("iago")
        self.login_user(iago)

        realm = get_realm("zulip")
        self.assertEqual(realm.id, iago.realm_id)

        # Get our failing test first.
        self.assertRaises(
            UserProfile.DoesNotExist, lambda: get_user_by_delivery_email("romeo@zulip.net", realm)
        )

        # Before we can successfully post, we need to ensure
        # that Iago can create users.
        do_change_can_create_users(iago, True)

        params = dict(
            email="romeo@zulip.net",
            password="xxxx",
            full_name="Romeo Montague",
        )

        # Use the Zulip wrapper.
        result = self.client_post("/json/users", params)

        # Once again we check that the HTTP request was successful.
        self.assert_json_success(result)
        content = orjson.loads(result.content)

        # Finally we test the side effect of the post.
        user_id = content["user_id"]
        romeo = get_user_by_delivery_email("romeo@zulip.net", realm)
        self.assertEqual(romeo.id, user_id)

    def test_can_create_users(self) -> None:
        # Typically, when testing an API endpoint, we prefer a single
        # test covering both the happy path and common error paths.
        #
        # See https://zulip.readthedocs.io/en/latest/testing/philosophy.html#share-test-setup-code.
        iago = self.example_user("iago")
        self.login_user(iago)

        do_change_can_create_users(iago, False)
        valid_params = dict(
            email="romeo@zulip.net",
            password="xxxx",
            full_name="Romeo Montague",
        )

        # We often use assert_json_error for negative tests.
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result, "User not authorized to create users", 400)

        do_change_can_create_users(iago, True)
        incomplete_params = dict(
            full_name="Romeo Montague",
        )
        result = self.client_post("/json/users", incomplete_params)
        self.assert_json_error(result, "Missing 'email' argument", 400)

        # Verify that the original parameters were valid. Especially
        # for errors with generic error messages, this is important to
        # confirm that the original request with these parameters
        # failed because of incorrect permissions, and not because
        # valid_params weren't actually valid.
        result = self.client_post("/json/users", valid_params)
        self.assert_json_success(result)

        # Verify error handling when the user already exists.
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result, "Email 'romeo@zulip.net' already in use", 400)

    def test_tornado_redirects(self) -> None:
        # Let's poke a bit at Zulip's event system.
        # See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html
        # for context on the system itself and how it should be tested.
        #
        # Most specific features that might feel tricky to test have
        # similarly handy helpers, so find similar tests with `git grep` and read them!
        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)

        params = dict(status_text="on vacation")

        # Use the capture_send_event_calls context manager to capture events.
        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.api_post(cordelia, "/api/v1/users/me/status", params)

        self.assert_json_success(result)

        # Check that the POST to Zulip caused the expected events to be sent
        # to Tornado.
        self.assertEqual(
            events[0]["event"],
            dict(type="user_status", user_id=cordelia.id, status_text="on vacation"),
        )

        # Grabbing the last row in the table is OK here, but often it's
        # better to look up the object we created via its ID,
        # especially if there's risk of similar objects existing
        # (E.g. a message sent to that topic earlier in the test).
        row = UserStatus.objects.last()
        assert row is not None
        self.assertEqual(row.user_profile_id, cordelia.id)
        self.assertEqual(row.status_text, "on vacation")


class TestStreamHelpers(ZulipTestCase):
    # Streams are an important concept in Zulip, and ZulipTestCase
    # has helpers such as subscribe, users_subscribed_to_stream,
    # and make_stream.
    def test_new_streams(self) -> None:
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        realm = cordelia.realm

        stream_name = "Some new stream"
        self.subscribe(cordelia, stream_name)

        self.assertEqual(set(self.users_subscribed_to_stream(stream_name, realm)), {cordelia})

        self.subscribe(othello, stream_name)
        self.assertEqual(
            set(self.users_subscribed_to_stream(stream_name, realm)), {cordelia, othello}
        )

    def test_private_stream(self) -> None:
        # When we test stream permissions, it's very common to use at least
        # two users, so that you can see how different users are impacted.
        # We commonly use Othello to represent the "other" user from the primary user.
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        realm = cordelia.realm
        stream_name = "Some private stream"

        # Use the invite_only flag in make_stream to make a stream "private".
        stream = self.make_stream(stream_name=stream_name, invite_only=True)
        self.subscribe(cordelia, stream_name)

        self.assertEqual(set(self.users_subscribed_to_stream(stream_name, realm)), {cordelia})

        stream = get_stream(stream_name, realm)
        self.assertEqual(stream.name, stream_name)
        self.assertTrue(stream.invite_only)

        # We will now observe that Cordelia can access the stream...
        access_stream_for_send_message(cordelia, stream, forwarder_user_profile=None)

        # ...but Othello can't.
        with self.assertRaisesRegex(JsonableError, "Not authorized to send to channel"):
            access_stream_for_send_message(othello, stream, forwarder_user_profile=None)


class TestMessageHelpers(ZulipTestCase):
    # If you are testing behavior related to messages, then it's good
    # to know about send_stream_message, send_personal_message, and
    # most_recent_message.
    def test_stream_message(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        self.subscribe(hamlet, "Denmark")
        self.subscribe(iago, "Denmark")

        # The functions to send a message return the ID of the created
        # message, so you usually you don't need to look it up.
        sent_message_id = self.send_stream_message(
            sender=hamlet,
            stream_name="Denmark",
            topic_name="lunch",
            content="I want pizza!",
        )

        # But if you want to verify the most recent message received
        # by a user, there's a handy function for that.
        iago_message = most_recent_message(iago)

        # Here we check that the message we sent is the last one that
        # Iago received.  While we verify several properties of the
        # last message, the most important to verify is the unique ID,
        # since that protects us from bugs if this test were to be
        # extended to send multiple similar messages.
        self.assertEqual(iago_message.id, sent_message_id)
        self.assertEqual(iago_message.sender_id, hamlet.id)
        self.assert_message_stream_name(iago_message, "Denmark")
        self.assertEqual(iago_message.topic_name(), "lunch")
        self.assertEqual(iago_message.content, "I want pizza!")

    def test_personal_message(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        sent_message_id = self.send_personal_message(
            from_user=hamlet,
            to_user=cordelia,
            content="hello there!",
        )

        cordelia_message = most_recent_message(cordelia)

        self.assertEqual(cordelia_message.id, sent_message_id)
        self.assertEqual(cordelia_message.sender_id, hamlet.id)
        self.assertEqual(cordelia_message.content, "hello there!")


class TestQueryCounts(ZulipTestCase):
    def test_capturing_queries(self) -> None:
        # It's a common pitfall in Django to accidentally perform
        # database queries in a loop, due to lazy evaluation of
        # foreign keys. We use the assert_database_query_count
        # context manager to ensure our query count is predictable.
        #
        # When a test containing one of these query count assertions
        # fails, we'll want to understand the new queries and whether
        # they're necessary. You can investiate whether the changes
        # are expected/sensible by comparing print(queries) between
        # your branch and main.
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        with self.assert_database_query_count(15):
            self.send_personal_message(
                from_user=hamlet,
                to_user=cordelia,
                content="hello there!",
            )


class TestDevelopmentEmailsLog(ZulipTestCase):
    # We have development specific utilities that automate common tasks
    # to improve developer productivity.
    #
    # Ones such is /emails/generate/ endpoint that can be used to generate
    # all sorts of emails zulip sends. Those can be accessed at /emails/
    # in development server. Let's test that here.
    def test_generate_emails(self) -> None:
        # It is a common case where some functions that we test rely
        # on a certain setting's value. You can test those under the
        # context of a desired setting value as done below.
        # The endpoint we're testing here rely on these settings:
        #   * EMAIL_BACKEND: The backend class used to send emails.
        #   * DEVELOPMENT_LOG_EMAILS: Whether to log emails sent.
        # so, we set those to required values.
        #
        # If the code you're testing creates logs, it is best to capture them
        # and verify the log messages. That can be achieved with assertLogs()
        # as you'll see below. Read more about assertLogs() at:
        # https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertLogs
        with self.settings(EMAIL_BACKEND="zproject.email_backends.EmailLogBackEnd"), self.settings(
            DEVELOPMENT_LOG_EMAILS=True
        ), self.assertLogs(level="INFO") as logger, mock.patch(
            "zproject.email_backends.EmailLogBackEnd._do_send_messages", lambda *args: 1
        ):
            # Parts of this endpoint use transactions, and use
            # transaction.on_commit to run code when the transaction
            # commits.  Tests are run inside one big outer
            # transaction, so those never get a chance to run unless
            # we explicitly make a fake boundary to run them at; that
            # is what captureOnCommitCallbacks does.
            with self.captureOnCommitCallbacks(execute=True):
                result = self.client_get(
                    "/emails/generate/"
                )  # Generates emails and redirects to /emails/
            self.assertEqual("/emails/", result["Location"])  # Make sure redirect URL is correct.

            # The above call to /emails/generate/ creates the emails and
            # logs the below line for every email.
            output_log = (
                "INFO:root:Emails sent in development are available at http://testserver/emails"
            )
            # logger.output is a list of all the log messages captured. Verify it is as expected.
            self.assertEqual(logger.output, [output_log] * 18)

            # Now, lets actually go the URL the above call redirects to, i.e., /emails/
            result = self.client_get(result["Location"])

            # assert_in_success_response() is another helper that is commonly used to ensure
            # we are on the right page by verifying a string exists in the page's content.
            self.assert_in_success_response(["All emails sent in the Zulip"], result)


class TestMocking(ZulipTestCase):
    # Mocking, primarily used in testing, is a technique that allows you to
    # replace methods or objects with fake entities.
    #
    # Mocking is generally used in situations where
    # we want to avoid running original code for reasons
    # like skipping HTTP requests, saving execution time etc.
    #
    # Learn more about mocking in-depth at:
    # https://zulip.readthedocs.io/en/latest/testing/testing-with-django.html#testing-with-mocks
    #
    # The following test demonstrates a simple use case
    # where mocking is helpful in saving test-run time.
    def test_edit_message(self) -> None:
        """
        Verify if the time limit imposed on message editing is working correctly.
        """
        iago = self.example_user("iago")
        self.login("iago")

        # Set limit to edit message content.
        MESSAGE_CONTENT_EDIT_LIMIT = 5 * 60  # 5 minutes
        result = self.client_patch(
            "/json/realm",
            {
                "allow_message_editing": "true",
                "message_content_edit_limit_seconds": MESSAGE_CONTENT_EDIT_LIMIT,
            },
        )
        self.assert_json_success(result)

        sent_message_id = self.send_stream_message(
            iago,
            "Scotland",
            topic_name="lunch",
            content="I want pizza!",
        )
        message_sent_time = timezone_now()

        # Verify message sent.
        message = most_recent_message(iago)
        self.assertEqual(message.id, sent_message_id)
        self.assertEqual(message.content, "I want pizza!")

        # Edit message content now. This should work as we're editing
        # it immediately after sending i.e., before the limit exceeds.
        result = self.client_patch(
            f"/json/messages/{sent_message_id}", {"content": "I want burger!"}
        )
        self.assert_json_success(result)
        message = most_recent_message(iago)
        self.assertEqual(message.id, sent_message_id)
        self.assertEqual(message.content, "I want burger!")

        # Now that we tested message editing works within the limit,
        # we want to verify it doesn't work beyond the limit.
        #
        # To do that we'll have to wait for the time limit to pass which is
        # 5 minutes here. Easy, use time.sleep() but mind that it slows down the
        # test to a great extent which isn't good. This is when mocking comes to rescue.
        # We can check what the original code does to determine whether the time limit
        # exceeded and mock that here such that the code runs as if the time limit
        # exceeded without actually waiting for that long!
        #
        # In this case, it is timezone_now, an alias to django.utils.timezone.now,
        # to which the difference with message-sent-time is checked. So, we want
        # that timezone_now() call to return `datetime` object representing time
        # that is beyond the limit.
        #
        # Notice how mock.patch() is used here to do exactly the above mentioned.
        # mock.patch() here makes any calls to `timezone_now` in `zerver.actions.message_edit`
        # to return the value passed to `return_value` in the its context.
        # You can also use mock.patch() as a decorator depending on the
        # requirements. Read more at the documentation link provided above.

        time_beyond_edit_limit = message_sent_time + timedelta(
            seconds=MESSAGE_CONTENT_EDIT_LIMIT + 100
        )  # There's a buffer time applied to the limit, hence the extra 100s.

        with time_machine.travel(time_beyond_edit_limit, tick=False):
            result = self.client_patch(
                f"/json/messages/{sent_message_id}", {"content": "I actually want pizza."}
            )
            self.assert_json_error(result, msg="The time limit for editing this message has passed")
            message = most_recent_message(iago)
            self.assertEqual(message.id, sent_message_id)
            self.assertEqual(message.content, "I want burger!")
