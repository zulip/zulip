#!/usr/bin/env python2.7
#
# Generates % delta activity metrics from graphite/statsd data
#
from __future__ import print_function
from __future__ import absolute_import
import os, sys
from six.moves import range

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import optparse
from datetime import timedelta, datetime
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.utils import statsd_key
import requests

# Workaround to support the Python-requests 1.0 transition of .json
# from a property to a function
requests_json_is_function = callable(requests.Response.json)
def extract_json_response(resp):
    if requests_json_is_function:
        return resp.json()
    else:
        return resp.json

def get_data_url(buckets, realm):
    realm_key = statsd_key(realm, True)

    # This is the slightly-cleaned up JSON api version of https://graphiti.zulip.net/graphs/945c7aafc2d
    #
    # Fetches 1 month worth of data
    DATA_URL="https://stats1.zulip.net:444/render/?from=-1000d&format=json"
    for bucket in buckets:
        if realm != 'all':
            statsd_target = "stats.gauges.staging.users.active.%s.%s" % (realm_key, bucket)
            DATA_URL += "&target=%s" % (statsd_target,)
        else:
            # all means adding up all realms, but exclude the .all. metrics since that would double things
            DATA_URL += "&target=sum(exclude(stats.gauges.staging.users.active.*.%s, 'all'))" % (bucket,)
    return DATA_URL

def get_data(url, username, pw):
    from requests.auth import HTTPDigestAuth

    res = requests.get(url, auth=HTTPDigestAuth(username, pw), verify=False)

    if res.status_code != 200:
        print("Failed to fetch data url: %s" % (res.error,))
        return []

    return extract_json_response(res)

def noon_of(day=datetime.now()):
    return datetime(year=day.year, month=day.month, day=day.day, hour=12)

def points_during_day(data, noon):
    """Returns all the points in the dataset that occur in the 12 hours around
    the datetime object that is passed in. data must be sorted."""
    before =datetime_to_timestamp(noon - timedelta(hours=12))
    after = datetime_to_timestamp(noon + timedelta(hours=12))

    between = [pt for pt in data if pt[1] > before and pt[1] < after]
    return between

def best_during_day(data, day):
    valid = sorted(points_during_day(data, day), key=lambda pt: pt[0], reverse=True)
    if len(valid):
        return valid[0][0]
    else:
        return None

def percent_diff(prev, cur):
    if prev is None or cur is None:
        return None
    if cur == 0 and prev == 0:
        return ""
    if prev == 0:
        return "NaN"
    return "%.02f%%" % (((cur - prev) / prev) * 100,)

def parse_data(data, today):
    def print_results(all_days, days, compare_with_last=False):
        first_data_point = True
        best_last_time = 0
        for i in all_days:
            day = today - timedelta(days=i)
            # Ignore weekends
            if day.weekday() in days:
                best = best_during_day(metric['datapoints'], day)
                if best is None:
                    continue

                if not compare_with_last:
                    percent = percent_diff(best, best_today)
                else:
                    if first_data_point:
                        percent = ""
                        first_data_point = False
                    else:
                        percent = percent_diff(best_last_time, best)

                if best is not None:
                    print("Last %s, %s %s ago:\t%.01f\t\t%s" \
                        % (day.strftime("%A"), i, "days", best, percent))
                best_last_time = best

    for metric in data:
        # print "Got %s with data points %s" % (metric['target'], len(metric['datapoints']))
        # Calculate % between peak 2hr and 10min across each day and week
        metric['datapoints'].sort(key=lambda p: p[1])

        best_today = best_during_day(metric['datapoints'], today)
        print("Date\t\t\t\tUsers\t\tChange from then to today")
        print("Today, 0 days ago:\t\t%.01f" % (best_today,))
        print_results(range(1, 1000), [0, 1, 2, 3, 4, 7])

        print("\n\nWeekly Wednesday results")
        print("Date\t\t\t\tUsers\t\tDelta from previous week")
        print_results(reversed(range(1, 1000)), [2], True)



parser = optparse.OptionParser(r"""

%prog --user username --password pw [--start-from unixtimestamp]

    Generates activity statistics with detailed week-over-week percentage change
""")

parser.add_option('--user',
                  help='Graphite usernarme',
                  metavar='USER')
parser.add_option('--password',
                  help='Graphite password',
                  metavar='PASSWORD')
parser.add_option('--start-from',
                  help='What day to consider as \'today\' when calculating stats as a Unix timestamp',
                  metavar='STARTDATE',
                  default='today')
parser.add_option('--realm',
                  help='Which realm to query',
                  default='all')
parser.add_option('--bucket',
                  help='Which bucket to query',
                  default='12hr')

if __name__ == '__main__':
    (options, args) = parser.parse_args()

    if not options.user or not options.password:
        parser.error("You must enter a username and password to log into graphite with")

    startfrom = noon_of(day=datetime.now())
    if options.start_from != 'today':
        startfrom = noon_of(day=datetime.fromtimestamp(int(options.start_from)))
        print("Using baseline of today as %s" % (startfrom,))

    realm_key = statsd_key(options.realm, True)
    buckets = [options.bucket]

    # This is the slightly-cleaned up JSON api version of https://graphiti.zulip.net/graphs/945c7aafc2d
    #
    # Fetches 1 month worth of data
    DATA_URL = get_data_url(buckets, options.realm)
    data = get_data(DATA_URL, options.user, options.password)


    parse_data(data, startfrom)
