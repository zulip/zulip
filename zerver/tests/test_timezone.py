import sys
from datetime import datetime, timezone

from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timezone import canonicalize_timezone, common_timezones

if sys.version_info < (3, 9):  # nocoverage
    from backports import zoneinfo
else:  # nocoverage
    import zoneinfo


class TimeZoneTest(ZulipTestCase):
    def test_canonicalize_timezone(self) -> None:
        self.assertEqual(canonicalize_timezone("America/Los_Angeles"), "America/Los_Angeles")
        self.assertEqual(canonicalize_timezone("US/Pacific"), "America/Los_Angeles")
        self.assertEqual(canonicalize_timezone("Gondor/Minas_Tirith"), "Gondor/Minas_Tirith")

    def test_common_timezones(self) -> None:
        ambiguous_abbrevs = [
            ("CDT", -18000.0),  # Central Daylight Time
            ("CDT", -14400.0),  # Cuba Daylight Time
            ("CST", -21600.0),  # Central Standard Time
            ("CST", +28800.0),  # China Standard Time
            ("CST", -18000.0),  # Cuba Standard Time
            ("PST", -28800.0),  # Pacific Standard Time
            ("PST", +28800.0),  # Philippine Standard Time
            ("IST", +19800.0),  # India Standard Time
            ("IST", +7200.0),  # Israel Standard Time
            ("IST", +3600.0),  # Ireland Standard Time
        ]
        missing = set(dict(reversed(ambiguous_abbrevs)).items()) - set(common_timezones.items())
        assert not missing, missing

        now = timezone_now()
        dates = [
            datetime(now.year, 6, 21, tzinfo=timezone.utc),
            datetime(now.year, 12, 21, tzinfo=timezone.utc),
        ]
        extra = {*common_timezones.items(), *ambiguous_abbrevs}
        for name in zoneinfo.available_timezones():
            tz = zoneinfo.ZoneInfo(name)
            for date in dates:
                abbrev = tz.tzname(date)
                assert abbrev is not None
                if abbrev.startswith(("-", "+")):
                    continue
                delta = tz.utcoffset(date)
                assert delta is not None
                offset = delta.total_seconds()
                assert (
                    common_timezones[abbrev] == offset or (abbrev, offset) in ambiguous_abbrevs
                ), (name, abbrev, offset)
                extra.discard((abbrev, offset))
        assert not extra, extra
