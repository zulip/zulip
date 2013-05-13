#!/usr/bin/env python
#
# Generates % delta activity metrics from graphite/statsd data
#
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import optparse
from itertools import dropwhile, takewhile
from datetime import timedelta, datetime
from zephyr.lib.timestamp import datetime_to_timestamp
import requests

# This is the slightly-cleaned up JSON api version of https://graphiti.humbughq.com/graphs/945c7aafc2d
#
# Fetches 1 month worth of data
DATA_URL="https://graphite.humbughq.com/render/?from=-28d&target=stats.gauges.staging.users.active.all.12hr&\
target=stats.gauges.staging.users.active.all.168hr&target=stats.gauges.staging.users.active.all.24hr&\
target=stats.gauges.staging.users.active.all.2hr&target=stats.gauges.staging.users.active.all.48hr&\
target=stats.gauges.staging.users.active.all.0_16hr&format=json"

# Workaround to support the Python-requests 1.0 transition of .json
# from a property to a function
requests_json_is_function = callable(requests.Response.json)
def extract_json_response(resp):
    if requests_json_is_function:
        return resp.json()
    else:
        return resp.json

def get_data(url, username, pw):
    from requests.auth import HTTPDigestAuth

    res = requests.get(url, auth=HTTPDigestAuth(username, pw), verify=False)

    if res.status_code != 200:
        print "Failed to fetch data url: %s" % (res.error,)
        return []

    return extract_json_response(res)

def noon_of(day=datetime.now()):
    return datetime(year=day.year, month=day.month, day=day.day, hour=12)

def points_during_day(data, noon):
    """Returns all the points in the dataset that occur in the 12 hours around
    the datetime object that is passed in. data must be sorted."""
    before =datetime_to_timestamp(noon - timedelta(hours=12))
    after = datetime_to_timestamp(noon + timedelta(hours=12))

    between = filter(lambda pt: pt[1] > before and pt[1] < after, data)
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
    return  ((cur - prev) / prev) * 100

def parse_data(data, today):
    for metric in data:
        # print "Got %s with data points %s" % (metric['target'], len(metric['datapoints']))
        if metric['target'] in ('stats.gauges.staging.users.active.all.2hr',
                                'stats.gauges.staging.users.active.all.0_16hr',
                                'stats.gauges.staging.users.active.all.12hr'):
            # Calculate % between peak 2hr and 10min across each day and week
            metric['datapoints'].sort(key=lambda p: p[1])

            print "\nUsers active in %s span:\n" % (metric['target'].split('.')[-1],)

            best_today = best_during_day(metric['datapoints'], today)
            for i in xrange(1, 100):
                day = today - timedelta(days=i)
                week = today - timedelta(weeks=i*7)
                # Ignore weekends
                if day.weekday() not in [5, 6]:
                    best = best_during_day(metric['datapoints'], day)

                    if best is not None:
                        print "Change between today and last %s, %s days ago:\t%.02f%%\t\t(%.01f to %.01f users)" \
                                 % (day.strftime("%A"), i, percent_diff(best, best_today), best, best_today)

                best = best_during_day(metric['datapoints'], week)
                if best is not None:
                    print "Weekly %% change from %s weeks ago today:\t\t%.02f" \
                            % (i, percent_diff(best, best_today))



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


if __name__ == '__main__':
    (options, args) = parser.parse_args()

    if not options.user or not options.password:
        parser.error("You must enter a username and password to log into graphite with")

    startfrom = noon_of(day=datetime.now())
    if options.start_from != 'today':
        startfrom = noon_of(day=datetime.fromtimestamp(int(options.start_from)))
        print "Using baseline of today as %s" % (startfrom,)


    data = get_data(DATA_URL, options.user, options.password)


    parse_data(data, startfrom)
