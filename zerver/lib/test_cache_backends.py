import itertools
import pickle
from typing import Any

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.locmem import LocMemCache
from typing_extensions import override

# Per-cache-name dict of {key: cas_token} and a per-cache-name monotonic
# counter for issuing new tokens.  Keyed the same way LocMemCache keys
# its _caches global so that multiple backend instances sharing a name --
# including the per-thread instances Django's CacheHandler creates --
# also share cas tokens and a single counter, consistent with a real
# memcached server's globally-monotonic cas semantics.
_cas_tokens: dict[str, dict[str, int]] = {}
_cas_counters: dict[str, "itertools.count[int]"] = {}


class CASCapableLocMemCache(LocMemCache):
    """LocMemCache with memcached-style gets/cas.

    The production backend (bmemcached.Client) exposes gets/cas natively,
    but LocMemCache does not. Tests of CAS-based read-through code paths
    use this backend instead so they don't require a real memcached server.

    Implementation approach: every write goes through LocMemCache._set,
    which we override to also bump a per-key cas token under the same
    lock.  incr() writes to self._cache directly instead of going through
    _set, so it gets its own override.
    """

    def __init__(self, name: str, params: dict[str, Any]) -> None:
        super().__init__(name, params)
        self._cas_tokens = _cas_tokens.setdefault(name, {})
        self._cas_counter = _cas_counters.setdefault(name, itertools.count(1))

    # LocMemCache's _set / _delete / _cache / _lock / _has_expired / _expire_info
    # are private and not declared in django-stubs, so mypy can't see them. The
    # attribute-access ignores below are for that reason only.

    def _set(self, key: str, value: bytes, timeout: Any = DEFAULT_TIMEOUT) -> None:
        super()._set(key, value, timeout)  # type: ignore[misc] # not in stubs
        self._cas_tokens[key] = next(self._cas_counter)

    def _delete(self, key: str) -> bool:
        self._cas_tokens.pop(key, None)
        return super()._delete(key)  # type: ignore[misc] # not in stubs

    @override
    def clear(self) -> None:
        super().clear()
        self._cas_tokens.clear()

    def gets(self, key: str, version: Any = None) -> tuple[Any, int | None]:
        raw_key = self.make_and_validate_key(key, version=version)
        with self._lock:  # type: ignore[attr-defined] # not in stubs
            if self._has_expired(raw_key):  # type: ignore[attr-defined] # not in stubs
                self._delete(raw_key)
                return None, None
            pickled = self._cache[raw_key]  # type: ignore[attr-defined] # not in stubs
            cas_id = self._cas_tokens.get(raw_key)
            self._cache.move_to_end(raw_key, last=False)  # type: ignore[attr-defined] # not in stubs
        return pickle.loads(pickled), cas_id  # noqa: S301

    def cas(
        self,
        key: str,
        value: Any,
        cas_id: int,
        timeout: Any = DEFAULT_TIMEOUT,
        version: Any = None,
    ) -> bool:
        raw_key = self.make_and_validate_key(key, version=version)
        pickled = pickle.dumps(value, self.pickle_protocol)
        with self._lock:  # type: ignore[attr-defined] # not in stubs
            if self._has_expired(raw_key):  # type: ignore[attr-defined] # not in stubs
                return False
            if self._cas_tokens.get(raw_key) != cas_id:
                return False
            # _set is our override, so this also refreshes the cas token.
            self._set(raw_key, pickled, timeout)
            return True

    def add_cas(
        self, key: str, value: Any, timeout: Any = DEFAULT_TIMEOUT, version: Any = None
    ) -> tuple[bool, int | None]:
        """Add-if-absent that returns the cas id of the just-added value.

        Mirrors bmemcached.Client.add(get_cas=True) so callers don't need a
        follow-up gets() to recover the cas id of their own write.  Returns
        (True, cas_id) on success, (False, None) if the slot was already set.
        """
        raw_key = self.make_and_validate_key(key, version=version)
        pickled = pickle.dumps(value, self.pickle_protocol)
        with self._lock:  # type: ignore[attr-defined] # not in stubs
            if not self._has_expired(raw_key):  # type: ignore[attr-defined] # not in stubs
                return False, None
            self._set(raw_key, pickled, timeout)
            return True, self._cas_tokens[raw_key]

    # The multi-key variants below are sequential in this in-memory test
    # backend, but mirror the interface that bmemcached implements via
    # pipelined memcached commands, so callers can be exercised by the
    # test suite without spinning up a real memcached.

    def gets_multi(self, keys: list[str], version: Any = None) -> dict[str, tuple[Any, int]]:
        result: dict[str, tuple[Any, int]] = {}
        for key in keys:
            val, cas_id = self.gets(key, version=version)
            if cas_id is not None:
                result[key] = (val, cas_id)
        return result

    def add_multi_cas(
        self, items: dict[str, Any], timeout: Any = DEFAULT_TIMEOUT, version: Any = None
    ) -> dict[str, int]:
        """Pipelined add returning the new cas id for each successful add.

        Mirrors bmemcached.Client.set_multi_cas with (key, 0) tuples (which
        the protocol turns into pipelined add operations) -- on success the
        per-key new cas id is returned to the caller.
        """
        result: dict[str, int] = {}
        for key, value in items.items():
            success, cas_id = self.add_cas(key, value, timeout=timeout, version=version)
            if success:
                assert cas_id is not None
                result[key] = cas_id
        return result

    def cas_multi(
        self,
        items: dict[str, tuple[Any, int]],
        timeout: Any = DEFAULT_TIMEOUT,
        version: Any = None,
    ) -> set[str]:
        return {
            key
            for key, (value, cas_id) in items.items()
            if self.cas(key, value, cas_id, timeout=timeout, version=version)
        }
