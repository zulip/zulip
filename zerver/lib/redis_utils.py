from django.conf import settings
from typing import Any, Dict, Optional
from zerver.lib.utils import generate_random_token

import redis
import ujson

def get_redis_client() -> redis.StrictRedis:
    return redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT,
                             password=settings.REDIS_PASSWORD, db=0)

def put_dict_in_redis(redis_client: redis.StrictRedis, key_format: str,
                      data_to_store: Dict[str, Any],
                      expiration_seconds: int,
                      token_length: int=64) -> str:
    with redis_client.pipeline() as pipeline:
        token = generate_random_token(token_length)
        key = key_format.format(token=token)
        pipeline.set(key, ujson.dumps(data_to_store))
        pipeline.expire(key, expiration_seconds)
        pipeline.execute()

    return key

def get_dict_from_redis(redis_client: redis.StrictRedis, key: str) -> Optional[Dict[str, Any]]:
    data = redis_client.get(key)
    if data is None:
        return None
    return ujson.loads(data)
