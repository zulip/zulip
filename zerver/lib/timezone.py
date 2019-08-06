from typing import List

import pytz
import datetime

def get_all_timezones() -> List[str]:
    return sorted(pytz.all_timezones)

def get_timezone(tz: str) -> datetime.tzinfo:
    return pytz.timezone(tz)
