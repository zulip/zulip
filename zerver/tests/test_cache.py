import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import time_machine
from bmemcached.exceptions import MemcachedException
from django.conf import settings
from django.core.cache import caches
from django.db import transaction
from django.db.models import QuerySet
from typing_extensions import override

from zerver.apps import flush_cache
from zerver.lib import cache as cache_module
from zerver.lib.cache import (
    _CACHE_FILL_SENTINEL,
    CACHE_FILL_SENTINEL_TIMEOUT,
    MEMCACHED_MAX_KEY_LENGTH,
    InvalidCacheKeyError,
    _CacheFillSentinel,
    bulk_cached_fetch,
    cache_add,
    cache_cas,
    cache_delete,
    cache_delete_many,
    cache_get,
    cache_get_many,
    cache_gets,
    cache_set,
    cache_set_many,
    cache_with_key,
    get_cache_fill_counts,
    read_through_cache,
    safe_cache_get_many,
    safe_cache_set_many,
    user_profile_by_id_cache_key,
    validate_cache_key,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zerver.models.realms import get_realm
from zerver.models.users import get_system_bot, get_user, get_user_profile_by_id


class AppsTest(ZulipTestCase):
    def test_cache_gets_flushed(self) -> None:
        with self.assertLogs(level="INFO") as m:
            with patch("zerver.apps.cache.clear") as mock:
                # The argument to flush_cache doesn't matter
                flush_cache(Mock())
                mock.assert_called_once()
            self.assertEqual(m.output, ["INFO:root:Clearing memcached cache after migrations"])
            self.assert_length(m.output, 1)


class CacheKeyValidationTest(ZulipTestCase):
    def test_validate_cache_key(self) -> None:
        validate_cache_key("nice_Ascii:string!~")
        with self.assertRaises(InvalidCacheKeyError):
            validate_cache_key("utf8_character:ą")
        with self.assertRaises(InvalidCacheKeyError):
            validate_cache_key("new_line_character:\n")
        with self.assertRaises(InvalidCacheKeyError):
            validate_cache_key("control_character:\r")
        with self.assertRaises(InvalidCacheKeyError):
            validate_cache_key("whitespace_character: ")
        with self.assertRaises(InvalidCacheKeyError):
            validate_cache_key("too_long:" + "X" * MEMCACHED_MAX_KEY_LENGTH)

        with self.assertRaises(InvalidCacheKeyError):
            # validate_cache_key does validation on a key with the
            # KEY_PREFIX appended to the start, so even though we're
            # passing something "short enough" here, it becomes too
            # long after appending KEY_PREFIX.
            validate_cache_key("X" * (MEMCACHED_MAX_KEY_LENGTH - 2))

    def test_cache_functions_raise_exception(self) -> None:
        invalid_key = "invalid_character:\n"
        good_key = "good_key"
        with self.assertRaises(InvalidCacheKeyError):
            cache_get(invalid_key)
        with self.assertRaises(InvalidCacheKeyError):
            cache_set(invalid_key, 0)
        with self.assertRaises(InvalidCacheKeyError):
            cache_delete(invalid_key)

        with self.assertRaises(InvalidCacheKeyError):
            cache_get_many([good_key, invalid_key])
        with self.assertRaises(InvalidCacheKeyError):
            cache_set_many({good_key: 0, invalid_key: 1})
        with self.assertRaises(InvalidCacheKeyError):
            cache_delete_many([good_key, invalid_key])


class CacheWithKeyDecoratorTest(ZulipTestCase):
    def test_cache_with_key_invalid_character(self) -> None:
        def invalid_characters_cache_key_function(user_id: int) -> str:
            return f"CacheWithKeyDecoratorTest:invalid_character:ą:{user_id}"

        @cache_with_key(invalid_characters_cache_key_function, timeout=1000)
        def get_user_function_with_bad_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user("hamlet")
        with patch("zerver.lib.cache.cache_set") as mock_set, self.assertLogs(level="WARNING") as m:
            with self.assert_database_query_count(1):
                result = get_user_function_with_bad_cache_keys(hamlet.id)

            self.assert_length(m.output, 1)
            self.assertEqual(result, hamlet)
            mock_set.assert_not_called()

    def test_cache_with_key_key_too_long(self) -> None:
        def too_long_cache_key_function(user_id: int) -> str:
            return "CacheWithKeyDecoratorTest:very_long_key:{}:{}".format("a" * 250, user_id)

        @cache_with_key(too_long_cache_key_function, timeout=1000)
        def get_user_function_with_bad_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user("hamlet")

        with patch("zerver.lib.cache.cache_set") as mock_set, self.assertLogs(level="WARNING") as m:
            with self.assert_database_query_count(1):
                result = get_user_function_with_bad_cache_keys(hamlet.id)

            self.assert_length(m.output, 1)
            self.assertEqual(result, hamlet)
            mock_set.assert_not_called()

    def test_cache_with_key_good_key(self) -> None:
        def good_cache_key_function(user_id: int) -> str:
            return f"CacheWithKeyDecoratorTest:good_cache_key:{user_id}"

        @cache_with_key(good_cache_key_function, timeout=1000)
        def get_user_function_with_good_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user("hamlet")

        with self.assert_database_query_count(1):
            result = get_user_function_with_good_cache_keys(hamlet.id)

        self.assertEqual(result, hamlet)

        # The previous function call should have cached the result correctly, so now
        # no database queries should happen:
        with self.assert_database_query_count(0, keep_cache_warm=True):
            result_two = get_user_function_with_good_cache_keys(hamlet.id)

        self.assertEqual(result_two, hamlet)

    def test_cache_with_key_none_values(self) -> None:
        def cache_key_function(user_id: int) -> str:
            return f"CacheWithKeyDecoratorTest:test_cache_with_key_none_values:{user_id}"

        @cache_with_key(cache_key_function, timeout=1000)
        def get_user_function_can_return_none(user_id: int) -> UserProfile | None:
            try:
                return UserProfile.objects.get(id=user_id)
            except UserProfile.DoesNotExist:
                return None

        last_user = UserProfile.objects.last()
        assert last_user is not None
        last_user_id = last_user.id
        with self.assert_database_query_count(1):
            result = get_user_function_can_return_none(last_user_id + 1)

        self.assertEqual(result, None)

        with self.assert_database_query_count(0, keep_cache_warm=True):
            result_two = get_user_function_can_return_none(last_user_id + 1)

        self.assertEqual(result_two, None)

    def test_cache_with_key_rejects_queryset_return(self) -> None:
        """Returning a QuerySet from a @cache_with_key-decorated function
        raises AssertionError under TEST_SUITE / DEBUG; production skips
        the check."""

        def cache_key_function(user_id: int) -> str:
            return f"CacheWithKeyDecoratorTest:queryset_return:{user_id}"

        @cache_with_key(cache_key_function, timeout=1000)
        def buggy_returns_queryset(user_id: int) -> QuerySet[UserProfile]:
            return UserProfile.objects.filter(id=user_id)

        hamlet = self.example_user("hamlet")
        with self.assertRaises(AssertionError) as cm:
            buggy_returns_queryset(hamlet.id)
        self.assertIn("returned a QuerySet", str(cm.exception))


class SetCacheExceptionTest(ZulipTestCase):
    def test_set_cache_exception(self) -> None:
        with (
            patch("zerver.lib.cache.get_cache_backend") as mock_backend,
            self.assertLogs("", level="INFO") as logs,
        ):
            mock_backend.return_value.set.side_effect = MemcachedException(
                b"Out of memory during read", 130
            )
            cache_set("test-key", 1)
            mock_backend.assert_called_once()
            mock_backend.return_value.set.assert_called_once()
            self.assert_length(logs.output, 1)
            self.assertIn("Out of memory during read", logs.output[0])

    def test_set_many_cache_exception(self) -> None:
        with (
            patch("zerver.lib.cache.get_cache_backend") as mock_backend,
            self.assertLogs("", level="INFO") as logs,
        ):
            mock_backend.return_value.set_many.side_effect = MemcachedException(
                b"Out of memory during read", 130
            )
            cache_set_many({"test-key": 1, "other-key": 2})
            mock_backend.assert_called_once()
            mock_backend.return_value.set_many.assert_called_once()
            self.assert_length(logs.output, 1)
            self.assertIn("Out of memory during read", logs.output[0])


class SafeCacheFunctionsTest(ZulipTestCase):
    def test_safe_cache_functions_with_all_good_keys(self) -> None:
        items = {
            "SafeFunctionsTest:key1": 1,
            "SafeFunctionsTest:key2": 2,
            "SafeFunctionsTest:key3": 3,
        }
        safe_cache_set_many(items)

        result = safe_cache_get_many(list(items.keys()))
        for key, value in result.items():
            self.assertEqual(value, items[key])

    def test_safe_cache_functions_with_all_bad_keys(self) -> None:
        items = {"SafeFunctionsTest:\nbadkey1": 1, "SafeFunctionsTest:\nbadkey2": 2}
        with self.assertLogs(level="WARNING") as m:
            safe_cache_set_many(items)
            self.assertIn(
                "WARNING:root:Invalid cache key used: ['SafeFunctionsTest:\\nbadkey1', 'SafeFunctionsTest:\\nbadkey2']",
                m.output[0],
            )
            self.assert_length(m.output, 1)

        with self.assertLogs(level="WARNING") as m:
            result = safe_cache_get_many(list(items.keys()))
            self.assertEqual(result, {})
            self.assertIn(
                "WARNING:root:Invalid cache key used: ['SafeFunctionsTest:\\nbadkey1', 'SafeFunctionsTest:\\nbadkey2']",
                m.output[0],
            )
            self.assert_length(m.output, 1)

    def test_safe_cache_functions_with_good_and_bad_keys(self) -> None:
        bad_items = {"SafeFunctionsTest:\nbadkey1": 1, "SafeFunctionsTest:\nbadkey2": 2}
        good_items = {"SafeFunctionsTest:goodkey1": 3, "SafeFunctionsTest:goodkey2": 4}
        items = {**good_items, **bad_items}

        with self.assertLogs(level="WARNING") as m:
            safe_cache_set_many(items)
            self.assertIn(
                "WARNING:root:Invalid cache key used: ['SafeFunctionsTest:\\nbadkey1', 'SafeFunctionsTest:\\nbadkey2']",
                m.output[0],
            )
            self.assert_length(m.output, 1)

        with self.assertLogs(level="WARNING") as m:
            result = safe_cache_get_many(list(items.keys()))
            self.assertEqual(result, good_items)
            self.assertIn(
                "WARNING:root:Invalid cache key used: ['SafeFunctionsTest:\\nbadkey1', 'SafeFunctionsTest:\\nbadkey2']",
                m.output[0],
            )
            self.assert_length(m.output, 1)


class BotCacheKeyTest(ZulipTestCase):
    def test_bot_profile_key_deleted_on_save(self) -> None:
        realm = get_realm(settings.SYSTEM_BOT_REALM)
        # Get the profile cached on both cache keys:
        user_profile = get_user(settings.EMAIL_GATEWAY_BOT, realm)
        bot_profile = get_system_bot(settings.EMAIL_GATEWAY_BOT, realm.id)
        self.assertEqual(user_profile, bot_profile)

        # Flip the setting and save:
        flipped_setting = not bot_profile.can_forge_sender
        bot_profile.can_forge_sender = flipped_setting
        bot_profile.save()

        # The .save() should have deleted cache keys, so if we fetch again,
        # the returned objects should have can_forge_sender set correctly.
        bot_profile2 = get_system_bot(settings.EMAIL_GATEWAY_BOT, realm.id)
        self.assertEqual(bot_profile2.can_forge_sender, flipped_setting)

        user_profile2 = get_user(settings.EMAIL_GATEWAY_BOT, realm)
        self.assertEqual(user_profile2.can_forge_sender, flipped_setting)


def get_user_id(user: UserProfile) -> int:
    return user.id  # nocoverage


def get_user_email(user: UserProfile) -> str:
    return user.email  # nocoverage


class GenericBulkCachedFetchTest(ZulipTestCase):
    def test_query_function_called_only_if_needed(self) -> None:
        hamlet = self.example_user("hamlet")
        # Get the user cached:
        get_user_profile_by_id(hamlet.id)

        class CustomError(Exception):
            pass

        def query_function(ids: list[int]) -> list[UserProfile]:
            raise CustomError("The query function was called")

        # query_function shouldn't be called, because the only requested object
        # is already cached:
        result: dict[int, UserProfile] = bulk_cached_fetch(
            cache_key_function=user_profile_by_id_cache_key,
            query_function=query_function,
            object_ids=[hamlet.id],
            id_fetcher=get_user_id,
        )
        self.assertEqual(result, {hamlet.id: hamlet})
        with self.assertLogs(level="INFO") as info_log:
            flush_cache(Mock())
        self.assertEqual(info_log.output, ["INFO:root:Clearing memcached cache after migrations"])

        # With the cache flushed, the query_function should get called:
        with self.assertRaises(CustomError):
            result = bulk_cached_fetch(
                cache_key_function=user_profile_by_id_cache_key,
                query_function=query_function,
                object_ids=[hamlet.id],
                id_fetcher=get_user_id,
            )

    def test_empty_object_ids_list(self) -> None:
        class CustomError(Exception):
            pass

        def cache_key_function(
            email: str,
        ) -> str:  # nocoverage -- this is just here to make sure it's not called
            raise CustomError("The cache key function was called")

        def query_function(
            emails: list[str],
        ) -> list[UserProfile]:  # nocoverage -- this is just here to make sure it's not called
            raise CustomError("The query function was called")

        # query_function and cache_key_function shouldn't be called, because
        # objects_ids is empty, so there's nothing to do.
        result: dict[str, UserProfile] = bulk_cached_fetch(
            cache_key_function=cache_key_function,
            query_function=query_function,
            object_ids=[],
            id_fetcher=get_user_email,
        )
        self.assertEqual(result, {})

    def test_hit_miss_mix_only_queries_missing_ids(self) -> None:
        """A bulk fetch of N ids where some are pre-populated should only
        call query_function for the missing ones, fill the cache for
        those, and return all N."""
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        othello = self.example_user("othello")

        # Warm the cache for hamlet and iago only.
        get_user_profile_by_id(hamlet.id)
        get_user_profile_by_id(iago.id)
        cache_delete(user_profile_by_id_cache_key(othello.id))

        queried_ids: list[int] = []

        def query_function(ids: list[int]) -> list[UserProfile]:
            queried_ids.extend(ids)
            return list(UserProfile.objects.filter(id__in=ids))

        result = bulk_cached_fetch(
            cache_key_function=user_profile_by_id_cache_key,
            query_function=query_function,
            object_ids=[hamlet.id, iago.id, othello.id],
            id_fetcher=get_user_id,
        )
        self.assertEqual(set(result), {hamlet.id, iago.id, othello.id})
        self.assertEqual(queried_ids, [othello.id])

        # othello should now be cached; a second bulk fetch doesn't
        # re-query.
        queried_ids.clear()
        result = bulk_cached_fetch(
            cache_key_function=user_profile_by_id_cache_key,
            query_function=query_function,
            object_ids=[hamlet.id, iago.id, othello.id],
            id_fetcher=get_user_id,
        )
        self.assertEqual(queried_ids, [])

    def test_race_writer_delete_during_bulk_query(self) -> None:
        """If a writer invalidates a key while the reader's query_function
        is running, the reader's cas() must fail and the stale value
        must not be cached."""
        hamlet = self.example_user("hamlet")
        key = user_profile_by_id_cache_key(hamlet.id)
        cache_delete(key)

        counts_before = get_cache_fill_counts()

        def racing_query(ids: list[int]) -> list[UserProfile]:
            # Simulate the writer's invalidation landing while we're
            # "reading" from the database.
            cache_delete(key)
            return list(UserProfile.objects.filter(id__in=ids))

        result = bulk_cached_fetch(
            cache_key_function=user_profile_by_id_cache_key,
            query_function=racing_query,
            object_ids=[hamlet.id],
            id_fetcher=get_user_id,
        )

        # The caller still gets the fetched value...
        self.assertIn(hamlet.id, result)
        # ...but the cache is NOT populated, and the race was detected.
        self.assertIsNone(cache_get(key))
        self.assertEqual(
            get_cache_fill_counts()["race_detected"] - counts_before["race_detected"],
            1,
        )

    def test_race_bulk_writer_delete_then_other_reader_adds(self) -> None:
        """Bulk analog of ReadThroughCacheTest.test_race_writer_delete_then_other_reader_adds:
        during our query_function, a writer deletes our sentinel and another
        reader (simulated) adds their own.  The cas id we got back from our
        own add no longer matches the slot's current cas, so cache_cas_many
        rejects the write and the stale DB value is not cached."""
        hamlet = self.example_user("hamlet")
        key = user_profile_by_id_cache_key(hamlet.id)
        cache_delete(key)

        counts_before = get_cache_fill_counts()

        def racing_query(ids: list[int]) -> list[UserProfile]:
            cache_delete(key)
            added, _cas = cache_add(key, _CACHE_FILL_SENTINEL, CACHE_FILL_SENTINEL_TIMEOUT)
            self.assertTrue(added)
            return list(UserProfile.objects.filter(id__in=ids))

        result = bulk_cached_fetch(
            cache_key_function=user_profile_by_id_cache_key,
            query_function=racing_query,
            object_ids=[hamlet.id],
            id_fetcher=get_user_id,
        )

        # Caller gets the fetched value, cache holds the other reader's
        # sentinel (not our stale 1-tuple), and the race was counted.
        # cache_gets exposes the raw value; cache_get filters sentinels.
        self.assertIn(hamlet.id, result)
        raw, _cas = cache_gets(key)
        self.assertIsInstance(raw, _CacheFillSentinel)
        self.assertEqual(
            get_cache_fill_counts()["race_detected"] - counts_before["race_detected"],
            1,
        )


class CASCapableBackendTest(ZulipTestCase):
    """Round-trip tests for the gets/cas/add backend operations that the
    read-through race-protection code relies on. These exercise the test
    suite's CASCapableLocMemCache directly, since LocMemCache has no
    gets/cas of its own."""

    @override
    def setUp(self) -> None:
        super().setUp()
        from zerver.lib.test_cache_backends import CASCapableLocMemCache

        backend = caches["default"]
        assert isinstance(backend, CASCapableLocMemCache)
        self.backend = backend
        self.key = "CASCapableBackendTest:key"
        # Ensure a clean slate; prior tests may have populated this key.
        self.backend.delete(self.key)

    def test_gets_miss_returns_none_none(self) -> None:
        value, cas_id = self.backend.gets(self.key)
        self.assertIsNone(value)
        self.assertIsNone(cas_id)

    def test_gets_hit_returns_value_and_token(self) -> None:
        self.backend.set(self.key, "hello")
        value, cas_id = self.backend.gets(self.key)
        self.assertEqual(value, "hello")
        self.assertIsNotNone(cas_id)

    def test_cas_succeeds_with_matching_token(self) -> None:
        self.backend.set(self.key, "v1")
        _, cas_id = self.backend.gets(self.key)
        assert cas_id is not None
        self.assertTrue(self.backend.cas(self.key, "v2", cas_id))
        self.assertEqual(self.backend.get(self.key), "v2")

    def test_cas_fails_after_concurrent_write(self) -> None:
        self.backend.set(self.key, "v1")
        _, stale_cas_id = self.backend.gets(self.key)
        assert stale_cas_id is not None
        self.backend.set(self.key, "intervening")
        self.assertFalse(self.backend.cas(self.key, "v2", stale_cas_id))
        self.assertEqual(self.backend.get(self.key), "intervening")

    def test_cas_fails_after_delete(self) -> None:
        self.backend.set(self.key, "v1")
        _, cas_id = self.backend.gets(self.key)
        assert cas_id is not None
        self.backend.delete(self.key)
        self.assertFalse(self.backend.cas(self.key, "v2", cas_id))
        self.assertIsNone(self.backend.get(self.key))

    def test_add_is_atomic(self) -> None:
        self.assertTrue(self.backend.add(self.key, "first"))
        self.assertFalse(self.backend.add(self.key, "second"))
        self.assertEqual(self.backend.get(self.key), "first")

    def test_gets_multi_absent_keys_omitted(self) -> None:
        self.backend.set(self.key, "v1")
        other_key = self.key + ":other"
        self.backend.delete(other_key)
        got = self.backend.gets_multi([self.key, other_key])
        self.assertIn(self.key, got)
        self.assertEqual(got[self.key][0], "v1")
        self.assertNotIn(other_key, got)

    def test_add_multi_cas_returns_cas_for_added_keys_only(self) -> None:
        other_key = self.key + ":other"
        self.backend.set(self.key, "existing")
        self.backend.delete(other_key)
        added = self.backend.add_multi_cas({self.key: "nope", other_key: "added"})
        self.assertEqual(set(added), {other_key})
        # The cas id we got back matches what gets() would return for the
        # newly-added value.
        _, cas_id = self.backend.gets(other_key)
        self.assertEqual(added[other_key], cas_id)
        # The prior value at self.key wasn't overwritten.
        self.assertEqual(self.backend.get(self.key), "existing")
        self.assertEqual(self.backend.get(other_key), "added")

    def test_cas_multi_commits_only_matching_cas(self) -> None:
        other_key = self.key + ":other"
        self.backend.set(self.key, "v1")
        self.backend.set(other_key, "v1")
        _, good_cas = self.backend.gets(self.key)
        _, stale_cas = self.backend.gets(other_key)
        assert good_cas is not None and stale_cas is not None
        # Invalidate one of the cas ids by an intervening write.
        self.backend.set(other_key, "intervening")
        committed = self.backend.cas_multi(
            {self.key: ("v2", good_cas), other_key: ("v2", stale_cas)}
        )
        self.assertEqual(committed, {self.key})
        self.assertEqual(self.backend.get(self.key), "v2")
        self.assertEqual(self.backend.get(other_key), "intervening")


class ReadThroughCacheTest(ZulipTestCase):
    """Tests for read_through_cache() and its mark-then-fill race protection."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.key = "ReadThroughCacheTest:key"
        cache_delete(self.key)
        # Snapshot counters so assertions can compare deltas.
        self._counts_before = get_cache_fill_counts()

    def _delta(self, name: str) -> int:
        return get_cache_fill_counts()[name] - self._counts_before[name]

    def test_hit_returns_cached_value(self) -> None:
        cache_set(self.key, "stored")
        fetcher = Mock()
        result = read_through_cache(self.key, fetcher)
        self.assertEqual(result, "stored")
        fetcher.assert_not_called()
        self.assertEqual(self._delta("hit"), 1)

    def test_miss_fills_cache(self) -> None:
        fetcher = Mock(return_value="fetched")
        result = read_through_cache(self.key, fetcher)
        self.assertEqual(result, "fetched")
        fetcher.assert_called_once()
        self.assertEqual(self._delta("won"), 1)

        # Second read is a hit.
        fetcher.reset_mock()
        result = read_through_cache(self.key, fetcher)
        self.assertEqual(result, "fetched")
        fetcher.assert_not_called()

    def test_writer_delete_during_fill_is_detected(self) -> None:
        """The core race test: writer deletes during the reader's fetch,
        reader's cas() must fail and the stale value must not be cached."""

        def fetcher() -> str:
            cache_delete(self.key)
            return "stale"

        result = read_through_cache(self.key, fetcher)
        self.assertEqual(result, "stale")
        self.assertEqual(self._delta("race_detected"), 1)
        self.assertEqual(self._delta("won"), 0)

        # Cache is empty; the next read causes a fresh fetch.
        next_fetcher = Mock(return_value="fresh")
        self.assertEqual(read_through_cache(self.key, next_fetcher), "fresh")
        next_fetcher.assert_called_once()

    def test_concurrent_readers_only_one_fills(self) -> None:
        """Two readers miss simultaneously; only one wins the add()."""
        reader_a_in_fetcher = threading.Event()
        allow_a_to_finish = threading.Event()
        fetcher_call_count = 0
        call_count_lock = threading.Lock()

        def slow_fetcher() -> str:
            nonlocal fetcher_call_count
            with call_count_lock:
                fetcher_call_count += 1
            reader_a_in_fetcher.set()
            allow_a_to_finish.wait(timeout=5)
            return "A-value"

        results: dict[str, str] = {}

        def reader_a() -> None:
            results["A"] = read_through_cache(self.key, slow_fetcher)

        thread = threading.Thread(target=reader_a)
        thread.start()
        self.assertTrue(reader_a_in_fetcher.wait(timeout=5))

        # Reader B arrives mid-fill; it must see the sentinel and bypass.
        def fast_fetcher() -> str:
            nonlocal fetcher_call_count
            with call_count_lock:
                fetcher_call_count += 1
            return "B-value"

        results["B"] = read_through_cache(self.key, fast_fetcher)
        self.assertEqual(results["B"], "B-value")

        allow_a_to_finish.set()
        thread.join(timeout=5)
        self.assertEqual(results["A"], "A-value")

        # Both fetchers ran.  B's path was saw_sentinel, not claim_lost,
        # because the sentinel was visible when B arrived.
        self.assertEqual(fetcher_call_count, 2)
        self.assertEqual(self._delta("saw_sentinel"), 1)
        self.assertEqual(self._delta("won"), 1)

    def test_sentinel_expires_if_filler_crashes(self) -> None:
        """If the filler raises before cas(), the sentinel must expire
        so that the next reader can fill normally."""

        class FillerError(Exception):
            pass

        def crashing_fetcher() -> str:
            raise FillerError

        t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        with time_machine.travel(t0, tick=False) as traveller:
            with self.assertRaises(FillerError):
                read_through_cache(self.key, crashing_fetcher)

            # While the sentinel is still live, the next reader bypasses
            # (saw_sentinel) and does not write to the cache.
            recovered = Mock(return_value="recovered")
            self.assertEqual(read_through_cache(self.key, recovered), "recovered")
            recovered.assert_called_once()

            # Advance past the sentinel's TTL.
            traveller.shift(timedelta(seconds=CACHE_FILL_SENTINEL_TIMEOUT + 1))

            recovered.reset_mock()
            self.assertEqual(read_through_cache(self.key, recovered), "recovered")
            recovered.assert_called_once()
            # The cache is now populated with the recovered value.
            self.assertEqual(cache_get(self.key), ("recovered",))

    def test_cache_get_of_sentinel_is_not_exposed_to_callers(self) -> None:
        """Belt-and-suspenders: a raw cache_get of a key mid-fill must not
        leak the sentinel into application code via read_through_cache."""
        # Manually plant a sentinel.
        added, _cas = cache_add(self.key, _CACHE_FILL_SENTINEL, CACHE_FILL_SENTINEL_TIMEOUT)
        self.assertTrue(added)

        fetcher = Mock(return_value="real-value")
        result = read_through_cache(self.key, fetcher)
        self.assertEqual(result, "real-value")
        fetcher.assert_called_once()
        self.assertEqual(self._delta("saw_sentinel"), 1)

    def test_cache_get_filters_sentinel(self) -> None:
        """cache_get hides the in-progress-fill marker; an in-progress fill
        looks the same as a missing key from the public API."""
        added, _cas = cache_add(self.key, _CACHE_FILL_SENTINEL, CACHE_FILL_SENTINEL_TIMEOUT)
        self.assertTrue(added)
        self.assertIsNone(cache_get(self.key))

    def test_cache_get_many_filters_sentinel(self) -> None:
        """cache_get_many drops sentinel entries from the result dict, the
        same way cache_get returns None for a sentinel."""
        cache_set(self.key + ":real", "real-value")
        added, _cas = cache_add(
            self.key + ":fill", _CACHE_FILL_SENTINEL, CACHE_FILL_SENTINEL_TIMEOUT
        )
        self.assertTrue(added)

        result = cache_get_many([self.key + ":real", self.key + ":fill", self.key + ":missing"])
        # cache_set wraps with pickled_tupled=True, so the value is a 1-tuple.
        self.assertEqual(result, {self.key + ":real": ("real-value",)})

    def test_fetcher_raise_does_not_leak_sentinel_via_cache_get(self) -> None:
        """If the read_through_cache fetcher raises, the sentinel is left to
        expire on its TTL.  A subsequent raw cache_get must not return it."""
        fetcher = Mock(side_effect=RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            read_through_cache(self.key, fetcher)
        self.assertIsNone(cache_get(self.key))

    def test_race_writer_delete_then_other_reader_adds(self) -> None:
        """The subtle race: while we're fetching, a writer deletes our sentinel
        and another reader adds their own in the now-empty slot.  Our cas-
        commit uses the cas id we got from our own add, so the slot's new
        cas (assigned to the other reader's add) won't match and the cas
        will fail -- we must not cache the stale value."""

        def racing_fetcher() -> str:
            # While we "fetch", simulate writer-delete + other-reader-add
            # landing on the same key.
            cache_delete(self.key)
            added, _cas = cache_add(self.key, _CACHE_FILL_SENTINEL, CACHE_FILL_SENTINEL_TIMEOUT)
            self.assertTrue(added)
            return "stale"

        result = read_through_cache(self.key, racing_fetcher)
        self.assertEqual(result, "stale")
        self.assertEqual(self._delta("race_detected"), 1)
        self.assertEqual(self._delta("won"), 0)
        # The slot holds the other reader's sentinel, not our stale 1-tuple.
        # cache_gets exposes the raw value; cache_get filters sentinels.
        raw, _cas = cache_gets(self.key)
        self.assertIsInstance(raw, _CacheFillSentinel)


class _ResultThread(threading.Thread):
    """threading.Thread that re-raises target's exception in the caller
    when join() is called.  Plain Thread silently swallows exceptions
    into a stderr message, which lets test-thread assertion failures
    masquerade as test passes (the failing test method's main-thread
    assertions can succeed for unrelated reasons)."""

    def __init__(self, target: Callable[[], None]) -> None:
        super().__init__(target=target)
        self._exc: BaseException | None = None

    @override
    def run(self) -> None:
        try:
            super().run()
        except BaseException as e:  # nocoverage
            self._exc = e

    @override
    def join(self, timeout: float | None = None) -> None:
        super().join(timeout)
        if self.is_alive():
            raise AssertionError(f"thread {self.name} did not complete in {timeout}s")
        if self._exc is not None:
            raise self._exc  # nocoverage


class TransactionCacheBufferTest(ZulipTestCase):
    """Cache mutations inside an atomic block are buffered and applied
    only at outermost commit; rollback discards them.  Within the
    transaction, reads of buffered keys see the buffered state
    (read-your-writes)."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.key = "TransactionCacheBufferTest:" + self.id().rsplit(".", 1)[-1]
        cache_delete(self.key)

    def _raw_memcached_get(self) -> object:
        """Read the slot directly from memcached, bypassing the buffer."""
        return caches["default"].get(cache_module.KEY_PREFIX + self.key)

    def test_set_inside_transaction_is_buffered_until_commit(self) -> None:
        with transaction.atomic(savepoint=True):
            cache_set(self.key, "value")
            # Buffered: visible to this thread via cache_get, NOT visible
            # to a raw memcached read.  cache_set wraps with pickled_tupled,
            # so the buffered (and stored) value is a 1-tuple.
            self.assertEqual(cache_get(self.key), ("value",))
            self.assertIsNone(self._raw_memcached_get())
        # Committed: now in memcached.
        self.assertEqual(cache_get(self.key), ("value",))
        self.assertEqual(self._raw_memcached_get(), ("value",))

    def test_delete_inside_transaction_is_buffered_until_commit(self) -> None:
        cache_set(self.key, "value")
        self.assertEqual(self._raw_memcached_get(), ("value",))
        with transaction.atomic(savepoint=True):
            cache_delete(self.key)
            # Buffered: this thread sees a miss, but memcached still has it.
            self.assertIsNone(cache_get(self.key))
            self.assertEqual(self._raw_memcached_get(), ("value",))
        # Committed: delete now flushed.
        self.assertIsNone(self._raw_memcached_get())

    def test_rollback_discards_buffered_set(self) -> None:
        with self.assertRaises(RuntimeError), transaction.atomic(savepoint=True):
            cache_set(self.key, "rolled-back")
            raise RuntimeError("boom")
        self.assertIsNone(self._raw_memcached_get())

    def test_rollback_discards_buffered_delete(self) -> None:
        cache_set(self.key, "preserved")
        with self.assertRaises(RuntimeError), transaction.atomic(savepoint=True):
            cache_delete(self.key)
            raise RuntimeError("boom")
        # Memcached untouched: the original value survives.
        self.assertEqual(self._raw_memcached_get(), ("preserved",))

    def test_savepoint_rollback_discards_inner_frame(self) -> None:
        with transaction.atomic(savepoint=True):
            cache_set(self.key, "outer")
            with self.assertRaises(RuntimeError), transaction.atomic(savepoint=True):
                cache_set(self.key, "inner")
                raise RuntimeError("boom")
            # Inner rolled back; outer's buffered set survives.
            self.assertEqual(cache_get(self.key), ("outer",))
        self.assertEqual(self._raw_memcached_get(), ("outer",))

    def test_savepoint_commit_promotes_to_parent(self) -> None:
        cache_set(self.key, "preserved")
        with self.assertRaises(RuntimeError), transaction.atomic(savepoint=True):
            with transaction.atomic(savepoint=True):
                cache_delete(self.key)
            # Inner committed; the delete is now in the outer frame.
            self.assertIsNone(cache_get(self.key))
            raise RuntimeError("boom")
        # Outer rolled back: the (savepoint-merged) delete is discarded.
        self.assertEqual(self._raw_memcached_get(), ("preserved",))

    def test_set_then_delete_collapses_to_delete(self) -> None:
        cache_set(self.key, "old")
        with transaction.atomic(savepoint=True):
            cache_set(self.key, "transient")
            cache_delete(self.key)
        self.assertIsNone(self._raw_memcached_get())

    def test_delete_then_set_collapses_to_set(self) -> None:
        cache_set(self.key, "old")
        with transaction.atomic(savepoint=True):
            cache_delete(self.key)
            cache_set(self.key, "fresh")
        self.assertEqual(self._raw_memcached_get(), ("fresh",))

    def test_read_through_fill_inside_transaction(self) -> None:
        """Read-through fill: cache_add writes the sentinel direct to
        memcached (so other connections see "fill in progress" and bypass),
        but the val landed by cache_cas is buffered until commit and only
        then flushed via cas-conditional set."""
        fetcher = Mock(return_value="filled")
        with transaction.atomic(savepoint=True):
            result = read_through_cache(self.key, fetcher)
            self.assertEqual(result, "filled")
            # Inside the tx: the sentinel from cache_add is in memcached;
            # the fetched val is only in our buffer.
            self.assertIsInstance(self._raw_memcached_get(), _CacheFillSentinel)
            # Our own re-read sees the buffered val (read-your-writes).
            # read_through_cache stores the cas-payload as a 1-tuple.
            self.assertEqual(cache_get(self.key), ("filled",))
        # On commit the cas-conditional flush replaces the sentinel.
        self.assertEqual(self._raw_memcached_get(), ("filled",))

    def test_writer_rollback_leaves_no_value_in_memcached(self) -> None:
        """A writer that fills the cache from its own pre-commit DB
        snapshot and then rolls back must not leave that value cached.
        Only the short-TTL sentinel from cache_add can persist, and that
        expires on its own."""
        fetcher = Mock(return_value="from-rolled-back-tx")
        with self.assertRaises(RuntimeError), transaction.atomic(savepoint=True):
            read_through_cache(self.key, fetcher)
            # The sentinel is in memcached but the val is only buffered.
            self.assertIsInstance(self._raw_memcached_get(), _CacheFillSentinel)
            raise RuntimeError("boom")
        # The buffer was discarded at rollback; only the sentinel remains
        # in memcached, so the writer's pre-commit val never lands.
        self.assertIsInstance(self._raw_memcached_get(), _CacheFillSentinel)
        # cache_get filters sentinels, so application code sees a miss
        # and the next reader will refill from the (rolled-back) DB.
        self.assertIsNone(cache_get(self.key))

    def test_concurrent_invalidation_during_fill_fails_flush(self) -> None:
        """If another connection invalidates the key between our cache_add
        and our commit, our flush's cas-conditional set must fail -- the
        buffer must NOT overwrite the other writer's invalidation."""
        from django.db import connections

        a_buffered = threading.Event()
        b_invalidated = threading.Event()

        def thread_a() -> None:
            try:
                with transaction.atomic(savepoint=True):
                    read_through_cache(self.key, Mock(return_value="from-A"))
                    a_buffered.set()
                    b_invalidated.wait(timeout=5)
                # On commit, the buffered cas-conditional set should fail
                # because B's cache_delete bumped memcached's cas.
            finally:
                connections.close_all()

        def thread_b() -> None:
            try:
                a_buffered.wait(timeout=5)
                # Concurrent invalidation lands on the slot.
                cache_delete(self.key)
                b_invalidated.set()
            finally:
                connections.close_all()

        ta = _ResultThread(target=thread_a)
        tb = _ResultThread(target=thread_b)
        ta.start()
        tb.start()
        ta.join(timeout=10)
        tb.join(timeout=10)

        # Thread B's delete won; thread A's flush did not overwrite it.
        self.assertIsNone(self._raw_memcached_get())

    def test_concurrent_fill_in_other_connection_is_preserved(self) -> None:
        """When a transaction's read-through fill is in flight, a fresh
        value written to memcached by another connection (e.g. a different
        reader's mark-then-fill that got there first) must not be
        overwritten.  This is what mark-then-fill's CAS guarantees;
        buffering fills would defeat it."""
        from django.db import connections

        a_claimed = threading.Event()
        b_committed = threading.Event()

        def thread_a() -> None:
            try:
                with transaction.atomic(savepoint=True):
                    # Manually walk the read_through_cache steps so we
                    # can interleave thread B between add and cas.
                    added, our_cas = cache_add(
                        self.key, _CACHE_FILL_SENTINEL, CACHE_FILL_SENTINEL_TIMEOUT
                    )
                    self.assertTrue(added)
                    assert our_cas is not None
                    a_claimed.set()
                    b_committed.wait(timeout=5)
                    # The buffer cas succeeds (the buffer doesn't see B's
                    # direct memcached write); the actual CAS is enforced
                    # at commit-time flush against memcached's bumped
                    # cas_id, which the assertEqual at the bottom of the
                    # test verifies indirectly via B's value surviving.
                    self.assertTrue(cache_cas(self.key, ("from-A-stale",), our_cas))
            finally:
                connections.close_all()

        def thread_b() -> None:
            try:
                a_claimed.wait(timeout=5)
                # B is not in a transaction, so cache_set goes direct.
                cache_set(self.key, "from-B-fresh")
                b_committed.set()
            finally:
                connections.close_all()

        ta = _ResultThread(target=thread_a)
        tb = _ResultThread(target=thread_b)
        ta.start()
        tb.start()
        ta.join(timeout=10)
        tb.join(timeout=10)

        # Thread B's fresh value must survive: A's cas correctly failed and
        # nothing buffered for self.key gets flushed at A's commit.
        self.assertEqual(self._raw_memcached_get(), ("from-B-fresh",))

    def test_writer_invalidate_after_fill_collapses_to_delete(self) -> None:
        """The realistic writer path: a read-through fill happens early in a
        transaction (e.g. an @cache_with_key access), then the writer mutates
        the row and the post_save signal calls cache_delete.  The buffer's
        last-wins-per-key must produce a delete on flush, not a set with the
        pre-write value."""
        cache_set(self.key, "before")
        with transaction.atomic(savepoint=True):
            # Simulate: a read-through fill writes into the cache.
            cache_set(self.key, "filled-during-tx")
            # Then a writer-side invalidation lands.
            cache_delete(self.key)
        # Memcached should reflect the final invalidation, not the fill.
        self.assertIsNone(self._raw_memcached_get())

    def test_inner_savepoint_false_rollback_does_not_flush_outer(self) -> None:
        """An inner `atomic(savepoint=False)` whose body raises sets
        `connection.needs_rollback`.  When the exception is caught between the
        two `with` blocks, the outer `__exit__` is called with `exc_type=None`
        but Django still rolls back the whole transaction.  The buffer must
        treat that as a rollback and discard, not flush, the buffered ops."""
        with transaction.atomic(savepoint=True):
            cache_set(self.key, "should-not-survive")
            try:
                with transaction.atomic(savepoint=False):
                    raise RuntimeError("inner failure")
            except RuntimeError:
                pass
            # The outer atomic exits next with exc_type=None, but Django's
            # connection.needs_rollback is True, so it will roll back.
        self.assertIsNone(self._raw_memcached_get())

    def test_thread_isolation(self) -> None:
        """Each thread has its own buffer.  A buffered set in thread A must be
        invisible to thread B until A's transaction commits."""
        from django.db import connections

        from zerver.lib.cache_invalidation_buffer import get_buffer

        a_recorded = threading.Event()
        b_observed = threading.Event()
        b_observation: list[object] = []

        def thread_a() -> None:
            try:
                # Drive the buffer directly to avoid opening a second DB
                # connection from this worker (which would block teardown).
                buf = get_buffer()
                buf.enter_atomic()
                buf.record_set(self.key, ("thread-a",), None)
                a_recorded.set()
                b_observed.wait(timeout=5)
                buf.exit_atomic(committed=False)
            finally:
                connections.close_all()

        def thread_b() -> None:
            try:
                a_recorded.wait(timeout=5)
                b_observation.append(cache_get(self.key))
                b_observation.append(self._raw_memcached_get())
                b_observed.set()
            finally:
                connections.close_all()

        ta = _ResultThread(target=thread_a)
        tb = _ResultThread(target=thread_b)
        ta.start()
        tb.start()
        ta.join(timeout=10)
        tb.join(timeout=10)

        # B's buffer is its own (empty) stack, so cache_get falls through to
        # memcached, which has nothing -- A's buffered value is invisible.
        self.assertEqual(b_observation, [None, None])

    def test_stale_pending_ops_cleared_on_next_atomic_enter(self) -> None:
        """If a previous transaction's ops were stashed and Django then
        silently rolled back (so the on_commit drain never ran), the next
        atomic must not flush those stale ops on its own commit."""
        from zerver.lib.cache_invalidation_buffer import get_buffer

        # Plant a stale stash directly to simulate the post-rollback state.
        buf = get_buffer()
        buf._pending_flush_ops = {self.key: ("set", ("stale-from-prior-tx",), None, 0)}

        with transaction.atomic(savepoint=True):
            cache_set(self.key, "fresh")
        # The fresh value flushed; the stale-stash ops are gone, not merged.
        self.assertEqual(self._raw_memcached_get(), ("fresh",))
