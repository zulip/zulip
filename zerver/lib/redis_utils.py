from __future__ import absolute_import

from django.conf import settings

import redis

def get_redis_client():
    # type: () -> redis.StrictRedis
    return redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT,
                             password=settings.REDIS_PASSWORD, db=0)
