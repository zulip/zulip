from zerver.lib.db import TimeTrackingCursor
from zerver.lib import cache
from zerver import tornado_callbacks
from zerver.worker import queue_processors

import base64
import os
import re
import time
import ujson
import urllib

from contextlib import contextmanager

API_KEYS = {}

@contextmanager
def stub(obj, name, f):
    old_f = getattr(obj, name)
    setattr(obj, name, f)
    yield
    setattr(obj, name, old_f)

@contextmanager
def simulated_queue_client(client):
    real_SimpleQueueClient = queue_processors.SimpleQueueClient
    queue_processors.SimpleQueueClient = client
    yield
    queue_processors.SimpleQueueClient = real_SimpleQueueClient

@contextmanager
def tornado_redirected_to_list(lst):
    real_tornado_callbacks_process_notification = tornado_callbacks.process_notification
    tornado_callbacks.process_notification = lst.append
    yield
    tornado_callbacks.process_notification = real_tornado_callbacks_process_notification

@contextmanager
def simulated_empty_cache():
    cache_queries = []
    def my_cache_get(key, cache_name=None):
        cache_queries.append(('get', key, cache_name))
        return None

    def my_cache_get_many(keys, cache_name=None):
        cache_queries.append(('getmany', keys, cache_name))
        return None

    old_get = cache.cache_get
    old_get_many = cache.cache_get_many
    cache.cache_get = my_cache_get
    cache.cache_get_many = my_cache_get_many
    yield cache_queries
    cache.cache_get = old_get
    cache.cache_get_many = old_get_many

@contextmanager
def queries_captured():
    '''
    Allow a user to capture just the queries executed during
    the with statement.
    '''

    queries = []

    def wrapper_execute(self, action, sql, params=()):
        start = time.time()
        try:
            return action(sql, params)
        finally:
            stop = time.time()
            duration = stop - start
            queries.append({
                    'sql': self.mogrify(sql, params),
                    'time': "%.3f" % duration,
                    })

    old_execute = TimeTrackingCursor.execute
    old_executemany = TimeTrackingCursor.executemany

    def cursor_execute(self, sql, params=()):
        return wrapper_execute(self, super(TimeTrackingCursor, self).execute, sql, params)
    TimeTrackingCursor.execute = cursor_execute

    def cursor_executemany(self, sql, params=()):
        return wrapper_execute(self, super(TimeTrackingCursor, self).executemany, sql, params)
    TimeTrackingCursor.executemany = cursor_executemany

    yield queries

    TimeTrackingCursor.execute = old_execute
    TimeTrackingCursor.executemany = old_executemany

