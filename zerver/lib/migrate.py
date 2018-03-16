from typing import Any, Callable, Dict, List, Tuple, Text
from django.db.models.query import QuerySet
import re
import time

def create_index_if_not_exist(index_name: Text, table_name: Text, column_string: Text,
                              where_clause: Text) -> Text:
    #
    # FUTURE TODO: When we no longer need to support postgres 9.3 for Trusty,
    #              we can use "IF NOT EXISTS", which is part of postgres 9.5
    #              (and which already is supported on Xenial systems).
    stmt = '''
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_class
                where relname = '%s'
                ) THEN
                    CREATE INDEX
                    %s
                    ON %s (%s)
                    %s;
            END IF;
        END$$;
        ''' % (index_name, index_name, table_name, column_string, where_clause)
    return stmt

def act_on_message_ranges(db: Any,
                          orm: Dict[str, Any],
                          tasks: List[Tuple[Callable[[QuerySet], QuerySet], Callable[[QuerySet], None]]],
                          batch_size: int=5000,
                          sleep: float=0.5) -> None:
    # tasks should be an array of (filterer, action) tuples
    # where filterer is a function that returns a filtered QuerySet
    # and action is a function that acts on a QuerySet

    all_objects = orm['zerver.Message'].objects

    try:
        min_id = all_objects.all().order_by('id')[0].id
    except IndexError:
        print('There is no work to do')
        return

    max_id = all_objects.all().order_by('-id')[0].id
    print("max_id = %d" % (max_id,))
    overhead = int((max_id + 1 - min_id) / batch_size * sleep / 60)
    print("Expect this to take at least %d minutes, just due to sleeps alone." % (overhead,))

    while min_id <= max_id:
        lower = min_id
        upper = min_id + batch_size - 1
        if upper > max_id:
            upper = max_id

        print('%s about to update range %s to %s' % (time.asctime(), lower, upper))

        db.start_transaction()
        for filterer, action in tasks:
            objects = all_objects.filter(id__range=(lower, upper))
            targets = filterer(objects)
            action(targets)
        db.commit_transaction()

        min_id = upper + 1
        time.sleep(sleep)
