
from typing import Text, List

import pytz

def get_all_timezones() -> List[Text]:
    return sorted(pytz.all_timezones)

def get_timezone(tz: Text) -> pytz.datetime.tzinfo:
    return pytz.timezone(tz)
