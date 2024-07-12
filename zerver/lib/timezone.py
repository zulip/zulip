from functools import cache

from scripts.lib.zulip_tools import get_tzdata_zi


@cache
def get_canonical_timezone_map() -> dict[str, str]:
    canonical = {}
    with get_tzdata_zi() as f:
        for line in f:
            fields = line.split()
            if fields and "link".startswith(fields[0].lower()):  # zic(8) accepts any prefix of Link
                code, name, alias = fields
                canonical[alias] = name
    return canonical


def canonicalize_timezone(key: str) -> str:
    return get_canonical_timezone_map().get(key, key)


# Note: some of these abbreviations are fundamentally ambiguous (see
# zerver/tests/test_timezone.py), so you should never rely on them as
# anything more than a heuristic.
common_timezones = {
    "SST": -39600,
    "HST": -36000,
    "AKST": -32400,
    "HDT": -32400,
    "AKDT": -28800,
    "PST": -28800,
    "MST": -25200,
    "PDT": -25200,
    "CST": -21600,
    "MDT": -21600,
    "CDT": -18000,
    "EST": -18000,
    "AST": -14400,
    "EDT": -14400,
    "NST": -12600,
    "ADT": -10800,
    "NDT": -9000,
    "GMT": 0,
    "UTC": 0,
    "WET": 0,
    "BST": +3600,
    "CET": +3600,
    "MET": +3600,
    "WAT": +3600,
    "WEST": +3600,
    "CAT": +7200,
    "CEST": +7200,
    "EET": +7200,
    "MEST": +7200,
    "SAST": +7200,
    "EAT": +10800,
    "EEST": +10800,
    "IDT": +10800,
    "MSK": +10800,
    "PKT": +18000,
    "IST": +19800,
    "WIB": +25200,
    "AWST": +28800,
    "HKT": +28800,
    "WITA": +28800,
    "JST": +32400,
    "KST": +32400,
    "WIT": +32400,
    "ACST": +34200,
    "AEST": +36000,
    "ChST": +36000,
    "ACDT": +37800,
    "AEDT": +39600,
    "NZST": +43200,
    "NZDT": +46800,
}
