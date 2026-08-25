from functools import cache

from scripts.lib.zulip_tools import get_tzdata_zi


@cache
def get_canonical_timezone_map() -> dict[str, str]:
    canonical = {}
    with get_tzdata_zi() as f:
        for line in f:
            fields = line.split()
            if fields and "link".startswith(fields[0].lower()):  # zic(8) accepts any prefix of Link
                _code, name, alias = fields
                canonical[alias] = name
    return canonical


def canonicalize_timezone(key: str) -> str:
    return get_canonical_timezone_map().get(key, key)
