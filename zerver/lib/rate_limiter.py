from __future__ import absolute_import

from six import text_type
from typing import Any, Iterator, Tuple

from django.conf import settings
from zerver.lib.redis_utils import get_redis_client
from six.moves import zip

from zerver.models import UserProfile

import redis
import time
import logging

# Implement a rate-limiting scheme inspired by the one described here, but heavily modified
# http://blog.domaintools.com/2013/04/rate-limiting-with-redis/

client = get_redis_client()
rules = settings.RATE_LIMITING_RULES # type: List[Tuple[int, int]]
def _rules_for_user(user):
    # type: (UserProfile) -> List[Tuple[int, int]]
    if user.rate_limits != "":
        result = [] # type: List[Tuple[int, int]]
        for limit in user.rate_limits.split(','):
            (seconds, requests) = limit.split(':', 2)
            result.append((int(seconds), int(requests)))
        return result
    return rules

def redis_key(user, domain):
    # type: (UserProfile, text_type) -> List[text_type]
    """Return the redis keys for this user"""
    return ["ratelimit:%s:%s:%s:%s" % (type(user), user.id, domain, keytype) for keytype in ['list', 'zset', 'block']]

def max_api_calls(user):
    # type: (UserProfile) -> int
    "Returns the API rate limit for the highest limit"
    return _rules_for_user(user)[-1][1]

def max_api_window(user):
    # type: (UserProfile) -> int
    "Returns the API time window for the highest limit"
    return _rules_for_user(user)[-1][0]

def add_ratelimit_rule(range_seconds, num_requests):
    # type: (int , int) -> None
    "Add a rate-limiting rule to the ratelimiter"
    global rules

    rules.append((range_seconds, num_requests))
    rules.sort(key=lambda x: x[0])

def remove_ratelimit_rule(range_seconds, num_requests):
    # type: (int , int) -> None
    global rules
    rules = [x for x in rules if x[0] != range_seconds and x[1] != num_requests]

def block_user(user, seconds, domain='all'):
    # type: (UserProfile, int, text_type) -> None
    "Manually blocks a user id for the desired number of seconds"
    _, _, blocking_key = redis_key(user, domain)
    with client.pipeline() as pipe:
        pipe.set(blocking_key, 1)
        pipe.expire(blocking_key, seconds)
        pipe.execute()

def unblock_user(user, domain='all'):
    # type: (UserProfile, str) -> None
    _, _, blocking_key = redis_key(user, domain)
    client.delete(blocking_key)

def clear_user_history(user, domain='all'):
    # type: (UserProfile, text_type) -> None
    '''
    This is only used by test code now, where it's very helpful in
    allowing us to run tests quickly, by giving a user a clean slate.
    '''
    for key in redis_key(user, domain):
        client.delete(key)

def _get_api_calls_left(user, domain, range_seconds, max_calls):
    # type: (UserProfile, text_type, int, int) -> Tuple[int, float]
    list_key, set_key, _ = redis_key(user, domain)
    # Count the number of values in our sorted set
    # that are between now and the cutoff
    now = time.time()
    boundary = now - range_seconds

    with client.pipeline() as pipe:
        # Count how many API calls in our range have already been made
        pipe.zcount(set_key, boundary, now)
        # Get the newest call so we can calculate when the ratelimit
        # will reset to 0
        pipe.lindex(list_key, 0)

        results = pipe.execute()

    count = results[0]
    newest_call = results[1]

    calls_left = max_calls - count
    if newest_call is not None:
        time_reset = now + (range_seconds - (now - float(newest_call)))
    else:
        time_reset = now

    return calls_left, time_reset

def api_calls_left(user, domain='all'):
    # type: (UserProfile, text_type) -> Tuple[int, float]
    """Returns how many API calls in this range this client has, as well as when
       the rate-limit will be reset to 0"""
    max_window = _rules_for_user(user)[-1][0]
    max_calls = _rules_for_user(user)[-1][1]
    return _get_api_calls_left(user, domain, max_window, max_calls)

def is_ratelimited(user, domain='all'):
    # type: (UserProfile, text_type) -> Tuple[bool, float]
    "Returns a tuple of (rate_limited, time_till_free)"
    list_key, set_key, blocking_key = redis_key(user, domain)

    rules = _rules_for_user(user)

    if len(rules) == 0:
        return False, 0.0

    # Go through the rules from shortest to longest,
    # seeing if this user has violated any of them. First
    # get the timestamps for each nth items
    with client.pipeline() as pipe:
        for _, request_count in rules:
            pipe.lindex(list_key, request_count - 1) # 0-indexed list

        # Get blocking info
        pipe.get(blocking_key)
        pipe.ttl(blocking_key)

        rule_timestamps = pipe.execute()

    # Check if there is a manual block on this API key
    blocking_ttl = rule_timestamps.pop()
    key_blocked = rule_timestamps.pop()

    if key_blocked is not None:
        # We are manually blocked. Report for how much longer we will be
        if blocking_ttl is None:
            blocking_ttl = 0.5
        else:
            blocking_ttl = int(blocking_ttl)
        return True, blocking_ttl

    now = time.time()
    for timestamp, (range_seconds, num_requests) in zip(rule_timestamps, rules):
        # Check if the nth timestamp is newer than the associated rule. If so,
        # it means we've hit our limit for this rule
        if timestamp is None:
            continue

        timestamp = float(timestamp)
        boundary = timestamp + range_seconds
        if boundary > now:
            free = boundary - now
            return True, free

    # No api calls recorded yet
    return False, 0.0

def incr_ratelimit(user, domain='all'):
    # type: (UserProfile, text_type) -> None
    """Increases the rate-limit for the specified user"""
    list_key, set_key, _ = redis_key(user, domain)
    now = time.time()

    # If we have no rules, we don't store anything
    if len(rules) == 0:
        return

    # Start redis transaction
    with client.pipeline() as pipe:
        count = 0
        while True:
            try:
                # To avoid a race condition between getting the element we might trim from our list
                # and removing it from our associated set, we abort this whole transaction if
                # another agent manages to change our list out from under us
                # When watching a value, the pipeline is set to Immediate mode
                pipe.watch(list_key)

                # Get the last elem that we'll trim (so we can remove it from our sorted set)
                last_val = pipe.lindex(list_key, max_api_calls(user) - 1)

                # Restart buffered execution
                pipe.multi()

                # Add this timestamp to our list
                pipe.lpush(list_key, now)

                # Trim our list to the oldest rule we have
                pipe.ltrim(list_key, 0, max_api_calls(user) - 1)

                # Add our new value to the sorted set that we keep
                # We need to put the score and val both as timestamp,
                # as we sort by score but remove by value
                pipe.zadd(set_key, now, now)

                # Remove the trimmed value from our sorted set, if there was one
                if last_val is not None:
                    pipe.zrem(set_key, last_val)

                # Set the TTL for our keys as well
                api_window = max_api_window(user)
                pipe.expire(list_key, api_window)
                pipe.expire(set_key, api_window)

                pipe.execute()

                # If no exception was raised in the execution, there were no transaction conflicts
                break
            except redis.WatchError:
                if count > 10:
                    logging.error("Failed to complete incr_ratelimit transaction without interference 10 times "
                                  "in a row! Aborting rate-limit increment")
                    break
                count += 1

                continue
