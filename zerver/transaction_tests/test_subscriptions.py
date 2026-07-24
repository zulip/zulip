import threading
import time
from collections.abc import Callable
from typing import Any
from unittest import mock

import orjson
from django.db import connections, transaction
from django.http import HttpRequest, HttpResponse
from typing_extensions import override

import zerver.actions.streams
from zerver.lib.test_classes import ZulipTransactionTestCase
from zerver.lib.test_helpers import HostRequestMock
from zerver.models import Stream, Subscription, UserProfile
from zerver.models.realms import get_realm
from zerver.views.streams import add_subscriptions_backend, remove_subscriptions_backend


def call_subscription_endpoint(
    view: Callable[..., HttpResponse], request: HttpRequest, acting_user: UserProfile
) -> None:
    # add_subscriptions_backend / remove_subscriptions_backend are
    # @typed_endpoint views that read their parameters from `request`, so we
    # invoke them with just (request, acting_user).  The Callable[...] type
    # lets us do that without mypy expecting the request-supplied arguments.
    view(request, acting_user)


class RacingRequest(threading.Thread):
    """Runs a single (un)subscription request and records whatever exception
    it raised, so the test can assert that the lock let both requests through
    cleanly."""

    def __init__(self, make_request: Callable[[], object]) -> None:
        threading.Thread.__init__(self)
        self.make_request = make_request
        self.error: Exception | None = None

    @override
    def run(self) -> None:
        try:
            self.make_request()
        except Exception as e:  # nocoverage -- only reached if the lock regresses
            self.error = e
        finally:
            # Close this thread's database connection so it doesn't leak.
            connections.close_all()


class SubscriptionRaceConditionTest(ZulipTransactionTestCase):
    created_streams: list[Stream] = []

    @override
    def tearDown(self) -> None:
        # ZulipTransactionTestCase commits to the database, so clean up
        # the streams (and their subscriptions) created by each test.
        with transaction.atomic(durable=True):
            for stream in self.created_streams:
                recipient = stream.recipient
                assert recipient is not None
                Subscription.objects.filter(recipient=recipient).delete()
                stream.delete()
                recipient.delete()
            transaction.on_commit(self.created_streams.clear)

        super().tearDown()

    def assert_racing_requests_serialize(
        self, pause_target: str, make_request: Callable[[], object]
    ) -> None:
        """Fire the same (un)subscription request from two threads and assert
        the user-row lock serialized them so neither errored.

        Unlike the user-group race test, we can't synchronize the threads
        with a threading.Barrier: those locks use nowait=True and conflicts
        raise immediately, whereas our (un)subscription locks block, so a
        shared barrier would deadlock.  Instead we pause the first request
        inside `pause_target` -- a function in zerver.actions.streams patched
        to block on its first call, which runs after the subscription state
        is read but before it is written -- while it still holds the user-row
        lock.  That forces the second request to block on the lock until the
        first commits.  With the lock both requests succeed; without it the
        second write collides (a duplicate-key error, or the subscriber_count
        check constraint).
        """
        first_request_holds_lock = threading.Event()
        release_first_request = threading.Event()
        original = getattr(zerver.actions.streams, pause_target)
        first_call = True
        first_call_lock = threading.Lock()

        def pause_first_request(*args: Any, **kwargs: Any) -> object:
            nonlocal first_call
            with first_call_lock:
                is_first = first_call
                first_call = False
            if is_first:
                first_request_holds_lock.set()
                assert release_first_request.wait(timeout=15)
            return original(*args, **kwargs)

        with mock.patch(f"zerver.actions.streams.{pause_target}", side_effect=pause_first_request):
            first = RacingRequest(make_request)
            second = RacingRequest(make_request)
            first.start()
            # Wait until the first request holds the lock and is paused.
            assert first_request_holds_lock.wait(timeout=15)
            second.start()
            # Give the second request time to block on the user-row lock.
            time.sleep(1)
            release_first_request.set()
            first.join()
            second.join()

        self.assertIsNone(first.error)
        self.assertIsNone(second.error)

    def test_concurrent_self_subscribe_serializes(self) -> None:
        """Two concurrent requests subscribing the same user to a channel
        must not both create a Subscription row and violate the
        (user_profile, recipient) unique constraint."""
        user = self.example_user("hamlet")
        stream = self.make_stream("subscribe_race", get_realm("zulip"))
        self.created_streams.append(stream)

        def subscribe() -> None:
            request = HostRequestMock(
                {
                    "subscriptions": orjson.dumps([{"name": stream.name}]).decode(),
                    "send_new_subscription_messages": "false",
                },
                user_profile=user,
            )
            call_subscription_endpoint(add_subscriptions_backend, request, user)

        self.assert_racing_requests_serialize("bulk_add_subs_to_db_with_logging", subscribe)

        self.assertEqual(
            Subscription.objects.filter(
                user_profile=user, recipient=stream.recipient, active=True
            ).count(),
            1,
        )
        stream.refresh_from_db()
        self.assertEqual(stream.subscriber_count, 1)

    def test_concurrent_self_unsubscribe_serializes(self) -> None:
        """Two concurrent requests unsubscribing the same user from a channel
        must not both decrement Stream.subscriber_count -- which under-counts
        subscribers and trips the subscriber_count check constraint when it
        would go negative, as it does here where the count starts at one."""
        user = self.example_user("hamlet")
        stream = self.make_stream("unsubscribe_race", get_realm("zulip"))
        self.created_streams.append(stream)
        self.subscribe(user, stream.name)
        stream.refresh_from_db()
        self.assertEqual(stream.subscriber_count, 1)

        def unsubscribe() -> None:
            request = HostRequestMock(
                {"subscriptions": orjson.dumps([stream.name]).decode()},
                user_profile=user,
            )
            call_subscription_endpoint(remove_subscriptions_backend, request, user)

        self.assert_racing_requests_serialize("bulk_update_subscriber_counts", unsubscribe)

        self.assertEqual(
            Subscription.objects.filter(
                user_profile=user, recipient=stream.recipient, active=True
            ).count(),
            0,
        )
        stream.refresh_from_db()
        self.assertEqual(stream.subscriber_count, 0)

    def test_concurrent_subscribe_other_user_serializes(self) -> None:
        """Same as the self-subscribe case, but for an admin subscribing
        another user via `principals`, which takes the user-row lock in
        bulk_access_users_by_id rather than in the view directly."""
        admin = self.example_user("iago")
        target = self.example_user("hamlet")
        stream = self.make_stream("subscribe_other_race", get_realm("zulip"))
        self.created_streams.append(stream)

        def subscribe() -> None:
            request = HostRequestMock(
                {
                    "subscriptions": orjson.dumps([{"name": stream.name}]).decode(),
                    "principals": orjson.dumps([target.id]).decode(),
                    "send_new_subscription_messages": "false",
                },
                user_profile=admin,
            )
            call_subscription_endpoint(add_subscriptions_backend, request, admin)

        self.assert_racing_requests_serialize("bulk_add_subs_to_db_with_logging", subscribe)

        self.assertEqual(
            Subscription.objects.filter(
                user_profile=target, recipient=stream.recipient, active=True
            ).count(),
            1,
        )
        stream.refresh_from_db()
        self.assertEqual(stream.subscriber_count, 1)

    def test_concurrent_unsubscribe_other_user_serializes(self) -> None:
        """Same as the self-unsubscribe case, but for an admin unsubscribing
        another user via `principals`, which takes the user-row lock in
        bulk_access_users_by_id rather than in the view directly."""
        admin = self.example_user("iago")
        target = self.example_user("hamlet")
        stream = self.make_stream("unsubscribe_other_race", get_realm("zulip"))
        self.created_streams.append(stream)
        self.subscribe(target, stream.name)
        stream.refresh_from_db()
        self.assertEqual(stream.subscriber_count, 1)

        def unsubscribe() -> None:
            request = HostRequestMock(
                {
                    "subscriptions": orjson.dumps([stream.name]).decode(),
                    "principals": orjson.dumps([target.id]).decode(),
                },
                user_profile=admin,
            )
            call_subscription_endpoint(remove_subscriptions_backend, request, admin)

        self.assert_racing_requests_serialize("bulk_update_subscriber_counts", unsubscribe)

        self.assertEqual(
            Subscription.objects.filter(
                user_profile=target, recipient=stream.recipient, active=True
            ).count(),
            0,
        )
        stream.refresh_from_db()
        self.assertEqual(stream.subscriber_count, 0)
