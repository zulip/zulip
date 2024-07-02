#!/usr/bin/env python3
import os
import sys
import timeit

import django
from django.db import connection

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ZULIP_PATH)
os.chdir(ZULIP_PATH)

# check for the venv
from tools.lib import sanity_check

sanity_check.check_venv(__file__)

os.environ["DJANGO_SETTINGS_MODULE"] = "zproject.settings"
django.setup()

from zerver.lib.cache import (
    cache_delete,
    display_recipient_cache_key,
    generic_bulk_cached_fetch,
    to_dict_cache_key_id,
)
from zerver.lib.display_recipient import (
    display_recipient_fields,
    single_user_display_recipient_cache_key,
    user_dict_id_fetcher,
)
from zerver.lib.message import (
    MessageDict,
    extract_message_dict,
    stringify_message_dict,
)
from zerver.models import Message, Stream, UserProfile


def get_column_values_from_single_table_using_id_lookup(*, columns, table, id_field, ids):
    if len(ids) == 0:
        return []
    column_list = ", ".join(columns)

    for id in ids:
        assert type(id) == int

    id_list = ", ".join(str(id) for id in ids)

    cursor = connection.cursor()
    sql = f"SELECT {column_list} FROM {table} WHERE {id_field} in ({id_list})"
    cursor.execute(sql)
    desc = cursor.description
    rows = [dict(zip((col[0] for col in desc), row)) for row in cursor.fetchall()]
    cursor.close()
    return rows


def direct_db_fetch(
    cache_key_function,
    query_function,
    object_ids,
    *,
    extractor,
    setter,
    id_fetcher,
    cache_transformer,
):
    return {id_fetcher(row): cache_transformer(row) for row in query_function(list(object_ids))}


def fetch(use_cache, *args, **kwargs):
    f = generic_bulk_cached_fetch if use_cache else direct_db_fetch
    return f(*args, **kwargs)


def messages_for_ids(message_ids, *, use_cache):
    # This is cribbed from real code, but it excludes some steps
    # such as getting user-specific message flags.
    cache_transformer = MessageDict.build_dict_from_raw_db_row
    id_fetcher = lambda row: row["id"]

    message_dicts = fetch(
        use_cache,
        to_dict_cache_key_id,
        MessageDict.get_raw_db_rows,
        message_ids,
        id_fetcher=id_fetcher,
        cache_transformer=cache_transformer,
        extractor=extract_message_dict,
        setter=stringify_message_dict,
    )
    return message_dicts


def bulk_fetch_single_user_display_recipients(uids, *, use_cache, optimize):
    if optimize:
        query_function = lambda ids: get_column_values_from_single_table_using_id_lookup(
            columns=display_recipient_fields,
            table="zerver_userprofile",
            id_field="id",
            ids=ids,
        )
    else:
        query_function = lambda ids: list(
            UserProfile.objects.filter(id__in=ids).values(*display_recipient_fields)
        )

    return fetch(
        use_cache,
        cache_key_function=single_user_display_recipient_cache_key,
        query_function=query_function,
        object_ids=uids,
        id_fetcher=user_dict_id_fetcher,
        extractor=lambda obj: obj,
        setter=lambda obj: obj,
        cache_transformer=lambda obj: obj,
    )


def bulk_fetch_stream_names(stream_ids, *, use_cache, optimize):
    # This is modified from the original version to deal just in stream ids
    # and not recipient ids.

    def get_tiny_stream_rows(ids):
        if optimize:
            return get_column_values_from_single_table_using_id_lookup(
                columns=["id", "name"],
                table="zerver_stream",
                id_field="id",
                ids=ids,
            )
        else:
            return Stream.objects.filter(id__in=ids).values("id", "name")

    def get_stream_id(row):
        return row["id"]

    def get_name(row):
        return row["name"]

    stream_display_recipients = fetch(
        use_cache,
        cache_key_function=display_recipient_cache_key,
        query_function=get_tiny_stream_rows,
        object_ids=stream_ids,
        id_fetcher=get_stream_id,
        cache_transformer=get_name,
        setter=lambda obj: obj,
        extractor=lambda obj: obj,
    )

    return stream_display_recipients


def run(f):
    print()
    print(f"===== Running {f.__name__}")
    f()


@run
def benchmark_stream_fetching():
    def run(num_ids, *, use_cache, optimize=False):
        stream_ids = Stream.objects.all()[:num_ids].values_list("id", flat=True)
        assert len(stream_ids) == num_ids

        label = "memcache" if use_cache else "optimize" if optimize else "database"
        # warm up cache
        if use_cache:
            bulk_fetch_stream_names(stream_ids, use_cache=True, optimize=False)

        f = lambda: bulk_fetch_stream_names(stream_ids, use_cache=use_cache, optimize=optimize)
        number = 200
        cost = min(timeit.repeat(f, number=number, repeat=5))
        print(label, 1000 * cost / (num_ids * number), "(milliseconds per row)")

    for n in [1, 5, 10, 15]:
        print(f"Testing with {n} stream ids")
        run(n, use_cache=False)
        run(n, use_cache=False, optimize=True)
        run(n, use_cache=True)
        print()


@run
def benchmark_user_fetching():
    def run(num_ids, *, use_cache, optimize=False):
        user_ids = UserProfile.objects.all()[:num_ids].values_list("id", flat=True)
        assert len(user_ids) == num_ids

        label = "memcache" if use_cache else "optimize" if optimize else "database"
        # warm up cache
        if use_cache:
            for user_id in user_ids:
                cache_delete(single_user_display_recipient_cache_key(user_id))
            bulk_fetch_single_user_display_recipients(user_ids, use_cache=True, optimize=False)

        f = lambda: bulk_fetch_single_user_display_recipients(
            user_ids, use_cache=use_cache, optimize=optimize
        )
        number = 200
        cost = min(timeit.repeat(f, number=number, repeat=5))
        print(label, 1000 * cost / (num_ids * number), "(milliseconds per row)")

    for n in [1, 5, 10, 15, 20, 30, 50]:
        print(f"Testing with {n} user ids")
        run(n, use_cache=False)
        run(n, use_cache=False, optimize=True)
        run(n, use_cache=True)
        print()


@run
def benchmark_message_fetching():
    def run(num_ids, *, use_cache):
        print(f"Testing with {num_ids} message ids")
        message_ids = Message.objects.all()[:num_ids].values_list("id", flat=True)
        assert len(message_ids) == num_ids
        label = "memcache" if use_cache else "database"
        # warm up cache
        if use_cache:
            messages_for_ids(message_ids, use_cache=True)

        f = lambda: messages_for_ids(message_ids, use_cache=use_cache)
        number = 10
        cost = min(timeit.repeat(f, number=number, repeat=3))
        print(label, 1000 * cost / (num_ids * number), "(milliseconds per row)")

    run(20, use_cache=False)
    run(20, use_cache=True)
