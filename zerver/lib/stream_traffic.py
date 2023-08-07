import datetime
from typing import Dict, Optional, Set

from django.db.models import Sum
from django.utils.timezone import now as timezone_now

from analytics.lib.counts import COUNT_STATS
from analytics.models import StreamCount
from zerver.models import Realm


def get_streams_traffic(
    stream_ids: Set[int], realm: Optional[Realm] = None
) -> Optional[Dict[int, int]]:
    if realm is not None and realm.is_zephyr_mirror_realm:
        # We do not need traffic data for streams in zephyr mirroring realm.
        return None

    stat = COUNT_STATS["messages_in_stream:is_bot:day"]
    traffic_from = timezone_now() - datetime.timedelta(days=28)

    query = StreamCount.objects.filter(property=stat.property, end_time__gt=traffic_from)
    query = query.filter(stream_id__in=stream_ids)

    traffic_list = query.values("stream_id").annotate(value=Sum("value"))
    traffic_dict = {}
    for traffic in traffic_list:
        traffic_dict[traffic["stream_id"]] = traffic["value"]

    return traffic_dict


def round_to_2_significant_digits(number: int) -> int:
    return int(round(number, 2 - len(str(number))))


STREAM_TRAFFIC_CALCULATION_MIN_AGE_DAYS = 7


def get_average_weekly_stream_traffic(
    stream_id: int, stream_date_created: datetime.datetime, recent_traffic: Dict[int, int]
) -> Optional[int]:
    try:
        stream_traffic = recent_traffic[stream_id]
    except KeyError:
        stream_traffic = 0

    stream_age = (timezone_now() - stream_date_created).days

    if stream_age >= 28:
        average_weekly_traffic = int(stream_traffic // 4)
    elif stream_age >= STREAM_TRAFFIC_CALCULATION_MIN_AGE_DAYS:
        average_weekly_traffic = int(stream_traffic * 7 // stream_age)
    else:
        return None

    if average_weekly_traffic == 0 and stream_traffic > 0:
        average_weekly_traffic = 1

    return round_to_2_significant_digits(average_weekly_traffic)
