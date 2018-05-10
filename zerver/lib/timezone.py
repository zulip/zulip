
from typing import List

import pytz

def get_all_timezones() -> List[str]:
    return sorted(pytz.all_timezones)

def get_timezone(tz: str) -> pytz.datetime.tzinfo:
    return pytz.timezone(tz)
