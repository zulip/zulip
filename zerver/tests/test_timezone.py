from datetime import datetime

import pytz
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timezone import canonicalize_timezone, common_timezones


class TimeZoneTest(ZulipTestCase):
    def test_canonicalize_timezone(self) -> None:
        self.assertEqual(canonicalize_timezone("America/Los_Angeles"), "America/Los_Angeles")
        self.assertEqual(canonicalize_timezone("US/Pacific"), "America/Los_Angeles")
        self.assertEqual(canonicalize_timezone("Gondor/Minas_Tirith"), "Gondor/Minas_Tirith")

    def test_common_timezones(self) -> None:
        ambiguous_abbrevs = [
            ("CDT", -18000),  # Central Daylight Time
            ("CDT", -14400),  # Cuba Daylight Time
            ("CST", -21600),  # Central Standard Time
            ("CST", +28800),  # China Standard Time
            ("CST", -18000),  # Cuba Standard Time
            ("PST", -28800),  # Pacific Standard Time
            ("PST", +28800),  # Phillipine Standard Time
            ("IST", +19800),  # India Standard Time
            ("IST", +7200),  # Israel Standard Time
            ("IST", +3600),  # Ireland Standard Time
        ]
        missing = set(dict(reversed(ambiguous_abbrevs)).items()) - set(
            common_timezones.items()
        )
        assert not missing, missing

        now = timezone_now()
        dates = [datetime(now.year, 6, 21), datetime(now.year, 12, 21)]
        extra = {*common_timezones.items(), *ambiguous_abbrevs}
        for name in pytz.all_timezones:
            tz = pytz.timezone(name)
            for date in dates:
                abbrev = tz.tzname(date)
                if abbrev.startswith(("-", "+")):
                    continue
                delta = tz.utcoffset(date)
                assert delta is not None
                offset = delta.total_seconds()
                assert (
                    common_timezones[abbrev] == offset
                    or (abbrev, offset) in ambiguous_abbrevs
                ), (name, abbrev, offset)
                extra.discard((abbrev, offset))
        assert not extra, extra
