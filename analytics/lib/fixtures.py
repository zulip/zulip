from __future__ import division, absolute_import

from zerver.models import Realm, UserProfile, Stream, Message
from analytics.models import InstallationCount, RealmCount, UserCount, StreamCount
from analytics.lib.counts import CountStat
from analytics.lib.time_utils import time_range

from datetime import datetime
from math import sqrt
from random import gauss, random, seed
from typing import List

from six.moves import range, zip

def generate_time_series_data(days=100, business_hours_base=10, non_business_hours_base=10,
                              growth=1, autocorrelation=0, spikiness=1, holiday_rate=0,
                              frequency=CountStat.DAY, is_gauge=False, random_seed=26):
    # type: (int, float, float, float, float, float, float, str, bool, int) -> List[int]
    """
    Generate semi-realistic looking time series data for testing analytics graphs.

    days -- Number of days of data. Is the number of data points generated if
        frequency is CountStat.DAY.
    business_hours_base -- Average value during a business hour (or day) at beginning of
        time series, if frequency is CountStat.HOUR (CountStat.DAY, respectively).
    non_business_hours_base -- The above, for non-business hours/days.
    growth -- Ratio between average values at end of time series and beginning of time series.
    autocorrelation -- Makes neighboring data points look more like each other. At 0 each
        point is unaffected by the previous point, and at 1 each point is a deterministic
        function of the previous point.
    spikiness -- 0 means no randomness (other than holiday_rate), higher values increase
        the variance.
    holiday_rate -- Fraction of days randomly set to 0, largely for testing how we handle 0s.
    frequency -- Should be CountStat.HOUR or CountStat.DAY.
    is_gauge -- If True, return partial sum of the series.
    random_seed -- Seed for random number generator.
    """
    if frequency == CountStat.HOUR:
        length = days*24
        seasonality = [non_business_hours_base] * 24 * 7
        for day in range(5):
            for hour in range(8):
                seasonality[24*day + hour] = business_hours_base
        holidays  = []
        for i in range(days):
            holidays.extend([random() < holiday_rate] * 24)
    elif frequency == CountStat.DAY:
        length = days
        seasonality = [8*business_hours_base + 16*non_business_hours_base] * 5 + \
                      [24*non_business_hours_base] * 2
        holidays = [random() < holiday_rate for i in range(days)]
    else:
        raise AssertionError("Unknown frequency: %s" % (frequency,))
    if length < 2:
        raise AssertionError("Must be generating at least 2 data points. "
                             "Currently generating %s" % (length,))
    growth_base = growth ** (1. / (length-1))
    values_no_noise = [seasonality[i % len(seasonality)] * (growth_base**i) for i in range(length)]

    seed(random_seed)
    noise_scalars = [gauss(0, 1)]
    for i in range(1, length):
        noise_scalars.append(noise_scalars[-1]*autocorrelation + gauss(0, 1)*(1-autocorrelation))

    values = [0 if holiday else int(v + sqrt(v)*noise_scalar*spikiness)
              for v, noise_scalar, holiday in zip(values_no_noise, noise_scalars, holidays)]
    if is_gauge:
        for i in range(1, length):
            values[i] = values[i-1] + values[i]
    return [max(v, 0) for v in values]
