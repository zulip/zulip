from django.db.migrations.recorder import MigrationRecorder
from django.http import HttpRequest, HttpResponse
from django.utils.crypto import get_random_string
from django.utils.translation import gettext as _
from pika import BlockingConnection

from zerver.lib.cache import cache_delete, cache_get, cache_set
from zerver.lib.exceptions import ServerNotReadyError
from zerver.lib.queue import get_queue_client
from zerver.lib.redis_utils import get_redis_client
from zerver.lib.response import json_success


def check_database() -> None:
    try:
        if not MigrationRecorder.Migration.objects.exists():
            raise ServerNotReadyError(_("Database is empty"))  # nocoverage
    except ServerNotReadyError:  # nocoverage
        raise
    except Exception:  # nocoverage
        raise ServerNotReadyError(_("Cannot query postgresql"))


def check_rabbitmq() -> None:  # nocoverage
    try:
        conn = get_queue_client().connection
        if conn is None:
            raise ServerNotReadyError(_("Cannot connect to rabbitmq"))
        assert isinstance(conn, BlockingConnection)
        conn.process_data_events()
    except ServerNotReadyError:
        raise
    except Exception:
        raise ServerNotReadyError(_("Cannot query rabbitmq"))


def check_redis() -> None:
    try:
        get_redis_client().ping()
    except Exception:  # nocoverage
        raise ServerNotReadyError(_("Cannot query redis"))


def check_memcached() -> None:
    try:
        roundtrip_key = "health_check_" + get_random_string(32)
        roundtrip_value = get_random_string(32)
        cache_set(roundtrip_key, roundtrip_value)
        got_value = cache_get(roundtrip_key)[0]
        if got_value != roundtrip_value:
            raise ServerNotReadyError(_("Cannot write to memcached"))  # nocoverage
        cache_delete(roundtrip_key)
    except ServerNotReadyError:  # nocoverage
        raise
    except Exception:  # nocoverage
        raise ServerNotReadyError(_("Cannot query memcached"))


def health(request: HttpRequest) -> HttpResponse:
    check_database()
    check_rabbitmq()
    check_redis()
    check_memcached()

    return json_success(request)
