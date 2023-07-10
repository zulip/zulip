import gc
import timeit
from typing import Any, Dict, List, Set

from zerver.lib.cache import cache_with_key
from zerver.lib.streams import ensure_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.utils import make_safe_digest
from zerver.models import (
    Realm,
    Stream,
    UserGroup,
    bulk_get_streams,
    get_active_streams,
    get_realm,
    get_stream,
)


def get_fat_stream_from_db(stream_name: str, realm: Realm) -> Stream:
    return Stream.objects.select_related().get(name__iexact=stream_name.strip(), realm=realm)


def get_thin_stream_from_db(stream_name: str, realm: Realm) -> Stream:
    return Stream.objects.get(name__iexact=stream_name.strip(), realm=realm)


def thin_stream_cache_key(stream_name: str, realm_id: int) -> str:
    return f"thin_stream:{realm_id}:{make_safe_digest(stream_name.strip().lower())}"


@cache_with_key(thin_stream_cache_key, timeout=3600 * 24 * 7)
def _get_thin_stream_from_cache(stream_name: str, realm_id: int) -> Stream:
    return Stream.objects.get(name__iexact=stream_name.strip(), realm_id=realm_id)


def get_thin_stream_from_cache(stream_name: str, realm: Realm) -> Stream:
    return _get_thin_stream_from_cache(stream_name, realm.id)


def fetch_streams_by_name(stream_names: List[str], realm: Realm) -> Any:
    where_clause = "upper(zerver_stream.name::text) IN (SELECT upper(name) FROM unnest(%s) AS name)"
    return get_active_streams(realm).extra(where=[where_clause], params=(list(stream_names),))


def bulk_get_streams_db(realm: Realm, stream_names: Set[str]) -> Dict[str, Any]:
    if not stream_names:
        return {}
    lower_stream_names = [stream_name.lower() for stream_name in stream_names]
    streams = list(fetch_streams_by_name(lower_stream_names, realm))
    return {stream.name.lower(): stream for stream in streams}


class Whatever(ZulipTestCase):
    def test_db_tipping_point(self) -> None:
        realm = get_realm("zulip")

        stream_names = [f"stream{i}" for i in range(600)]

        for stream_name in stream_names:
            ensure_stream(realm, stream_name, acting_user=None)

        def test(count: int) -> None:
            gc.collect()
            f = lambda: [
                row.description for row in fetch_streams_by_name(stream_names[:count], realm)
            ]
            number = 20
            cost = min(timeit.repeat(f, number=number, repeat=3))
            print(count, cost)
            return cost

        startup_cost = test(1)
        for i in range(100, 600, 100):
            cost = test(i)
            if cost > startup_cost * 5:
                break

    def test_db_overhead(self) -> None:
        realm = get_realm("zulip")

        stream_names = [f"stream{i}" for i in range(3000)]

        print("making streams")
        for stream_name in stream_names:
            ensure_stream(realm, stream_name, acting_user=None)
        print("done")
        print()

        def test(count: int) -> None:
            gc.collect()
            print(count, "row(s)")
            f = lambda: [
                row.description for row in fetch_streams_by_name(stream_names[:count], realm)
            ]
            number = 20
            results = timeit.repeat(f, number=number, repeat=3)
            print([f"{t * 1_000 / number}ms per run" for t in results])
            print([f"{int(t * 1_000_000 / (number * count))}us per stream" for t in results])
            print()

        test(1)
        test(1000)
        test(2000)
        test(3000)

    def test_bulk_cache(self) -> None:
        # use for profiling
        realm = get_realm("zulip")

        stream_names = [f"stream{i}" for i in range(20)]

        for stream_name in stream_names:
            ensure_stream(realm, stream_name, acting_user=None)

        for i in range(1000):
            bulk_get_streams(realm, stream_names)

    def test_multi_stream_benchmarks(self) -> None:
        realm = get_realm("zulip")

        stream_names = [f"stream{i}" for i in range(200)]

        for stream_name in stream_names:
            ensure_stream(realm, stream_name, acting_user=None)

        def test(label: str, f: Any) -> None:
            gc.collect()
            f() # warm up any caches
            print(label, min(timeit.repeat(f, number=30, repeat=3)))

        print("Numbers are relative to each other")
        print()

        for n in [1, 5, 10, 30, 50, 70]:
            print(n)
            test("bulk cache", lambda: bulk_get_streams(realm, stream_names[:n]))
            test("bulk db   ", lambda: bulk_get_streams_db(realm, stream_names[:n]))
            print()

        # sanity check bulk_get_streams_db
        assert bulk_get_streams_db(realm, set(stream_names))["stream67"].name == "stream67"

    def test_single_stream_benchmarks(self) -> None:
        realm = get_realm("zulip")

        def get_some_streams(f: Any) -> List[Any]:
            return [
                f("Denmark", realm),
                f("Scotland", realm),
                f("Rome", realm),
                f("Verona", realm),
                f("Venice", realm),
                f("Denmark", realm),
                f("Scotland", realm),
                f("Rome", realm),
                f("Verona", realm),
                f("Venice", realm),
            ]

        get_thin_cache = lambda: get_some_streams(get_thin_stream_from_cache)
        get_thin_db = lambda: get_some_streams(get_thin_stream_from_db)
        get_fat_cache = lambda: get_some_streams(get_stream)
        get_fat_db = lambda: get_some_streams(get_fat_stream_from_db)

        def test(label: str, f: Any) -> None:
            gc.collect()
            print(label)
            print(timeit.repeat(f, number=100, repeat=3))
            print()

        test("thin cache", get_thin_cache)
        test("thin db", get_thin_db)
        test("fat cache", get_fat_cache)
        test("fat db", get_fat_db)

    def test_cache_invalidation_bug(self) -> None:
        realm = get_realm("zulip")
        stream = get_stream("Verona", realm)

        user_group = stream.can_remove_subscribers_group
        old_name = user_group.name

        assert stream.can_remove_subscribers_group.name == old_name

        # Now rename the user group.
        new_name = "fred"
        user_group = UserGroup.objects.get(id=user_group.id)
        user_group.name = new_name
        user_group.save()

        # The cached version fails!
        stream = get_stream("Verona", realm)
        assert stream.can_remove_subscribers_group.name == old_name

        # The uncached version succeeds.
        stream = get_thin_stream_from_db("Verona", realm)
        assert stream.can_remove_subscribers_group.name == new_name
