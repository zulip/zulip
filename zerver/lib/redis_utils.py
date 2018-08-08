
from django.conf import settings

if False:
    import redis

def get_redis_client() -> 'redis.StrictRedis':
    import redis
    return redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT,
                             password=settings.REDIS_PASSWORD, db=0)
