# -*- coding: utf-8 -*-
from __future__ import absolute_import

import base64
import hashlib
import os
from time import sleep

from django.conf import settings
from six.moves import range

def statsd_key(val, clean_periods=False):
    if not isinstance(val, str):
        val = str(val)

    if ':' in val:
        val = val.split(':')[0]
    val = val.replace('-', "_")
    if clean_periods:
        val = val.replace('.', '_')

    return val

class StatsDWrapper(object):
    """Transparently either submit metrics to statsd
    or do nothing without erroring out"""

    # Backported support for gauge deltas
    # as our statsd server supports them but supporting
    # pystatsd is not released yet
    def _our_gauge(self, stat, value, rate=1, delta=False):
            """Set a gauge value."""
            from django_statsd.clients import statsd
            if delta:
                value = '%+g|g' % (value,)
            else:
                value = '%g|g' % (value,)
            statsd._send(stat, value, rate)

    def __getattr__(self, name):
        # Hand off to statsd if we have it enabled
        # otherwise do nothing
        if name in ['timer', 'timing', 'incr', 'decr', 'gauge']:
            if settings.STATSD_HOST != '':
                from django_statsd.clients import statsd
                if name == 'gauge':
                    return self._our_gauge
                else:
                    return getattr(statsd, name)
            else:
                return lambda *args, **kwargs: None

        raise AttributeError

statsd = StatsDWrapper()

# Runs the callback with slices of all_list of a given batch_size
def run_in_batches(all_list, batch_size, callback, sleep_time = 0, logger = None):
    if len(all_list) == 0:
        return

    limit = (len(all_list) / batch_size) + 1;
    for i in range(limit):
        start = i*batch_size
        end = (i+1) * batch_size
        if end >= len(all_list):
            end = len(all_list)
        batch = all_list[start:end]

        if logger:
            logger("Executing %s in batch %s of %s" % (end-start, i+1, limit))

        callback(batch)

        if i != limit - 1:
            sleep(sleep_time)

def make_safe_digest(string, hash_func=hashlib.sha1):
    """
    return a hex digest of `string`.
    """
    # hashlib.sha1, md5, etc. expect bytes, so non-ASCII strings must
    # be encoded.
    return hash_func(string.encode('utf-8')).hexdigest()


def log_statsd_event(name):
    """
    Sends a single event to statsd with the desired name and the current timestamp

    This can be used to provide vertical lines in generated graphs,
    for example when doing a prod deploy, bankruptcy request, or
    other one-off events

    Note that to draw this event as a vertical line in graphite
    you can use the drawAsInfinite() command
    """
    event_name = "events.%s" % (name,)
    statsd.incr(event_name)

def generate_random_token(length):
    return base64.b16encode(os.urandom(length / 2)).lower()
