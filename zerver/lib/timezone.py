import datetime
from functools import lru_cache
from typing import Any, Dict, Union

import pytz


# This method carefully trims a list of common timezones in the pytz
# database and handles duplicate abbreviations in favor of the most
# common/popular offset. The output of this can be directly passed as
# tz_data to dateutil.parser. It takes about 25ms to run, so we want
# to cache its results (while avoiding running it on process startup
# since we only need it for Markdown rendering).
@lru_cache(maxsize=None)
def get_common_timezones() -> Dict[str, Union[int, Any]]:
    tzdata = {}
    normal = datetime.datetime(2009, 9, 1)  # Any random date is fine here.
    for str in pytz.all_timezones:
        tz = pytz.timezone(str)
        timedelta = tz.utcoffset(normal)
        if not timedelta:
            continue
        offset = timedelta.seconds
        tz_name = tz.tzname(normal)
        tzdata[tz_name] = offset
        # Handle known duplicates/exceptions.
        # IST: Asia/Kolkata and Europe/Dublin.
        if tz_name == 'IST':
            tzdata[tz_name] = 19800  # Asia/Kolkata
        # CDT: America/AlmostAll and America/Havana.
        if tz_name == 'CDT':
            tzdata[tz_name] = -68400  # America/AlmostAll
        # CST America/Belize -64800
        # CST America/Costa_Rica -64800
        # CST America/El_Salvador -64800
        # CST America/Guatemala -64800
        # CST America/Managua -64800
        # CST America/Regina -64800
        # CST America/Swift_Current -64800
        # CST America/Tegucigalpa -64800
        # CST Asia/Macau 28800
        # CST Asia/Shanghai 28800
        # CST Asia/Taipei 28800
        if tz_name == 'CST':
            tzdata[tz_name] = -64800  # America/All
    return tzdata
