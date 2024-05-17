# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from typing import Any, Dict, List, Tuple

from django.db import connection
from psycopg2.sql import SQL, Literal
from typing_extensions import override

from zerver.worker.base import LoopQueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("user_activity")
class UserActivityWorker(LoopQueueProcessingWorker):
    """The UserActivity queue is perhaps our highest-traffic queue, and
    requires some care to ensure it performs adequately.

    We use a LoopQueueProcessingWorker as a performance optimization
    for managing the queue.  The structure of UserActivity records is
    such that they are easily deduplicated before being sent to the
    database; we take advantage of that to make this queue highly
    effective at dealing with a backlog containing many similar
    events.  Such a backlog happen in a few ways:

    * In abuse/DoS situations, if a client is sending huge numbers of
      similar requests to the server.
    * If the queue ends up with several minutes of backlog e.g. due to
      downtime of the queue processor, many clients will have several
      common events from doing an action multiple times.

    """

    client_id_map: Dict[str, int] = {}

    @override
    def start(self) -> None:
        # For our unit tests to make sense, we need to clear this on startup.
        self.client_id_map = {}
        super().start()

    @override
    def consume_batch(self, user_activity_events: List[Dict[str, Any]]) -> None:
        uncommitted_events: Dict[Tuple[int, int, str], Tuple[int, float]] = {}

        # First, we drain the queue of all user_activity events and
        # deduplicate them for insertion into the database.
        for event in user_activity_events:
            user_profile_id = event["user_profile_id"]
            client_id = event["client_id"]

            key_tuple = (user_profile_id, client_id, event["query"])
            if key_tuple not in uncommitted_events:
                uncommitted_events[key_tuple] = (1, event["time"])
            else:
                count, event_time = uncommitted_events[key_tuple]
                uncommitted_events[key_tuple] = (count + 1, max(event_time, event["time"]))

        rows = []
        for key_tuple, value_tuple in uncommitted_events.items():
            user_profile_id, client_id, query = key_tuple
            count, event_time = value_tuple
            rows.append(
                SQL("({},{},{},{},to_timestamp({}))").format(
                    Literal(user_profile_id),
                    Literal(client_id),
                    Literal(query),
                    Literal(count),
                    Literal(event_time),
                )
            )

        # Perform a single bulk UPSERT for all of the rows
        sql_query = SQL(
            """
            INSERT INTO zerver_useractivity(user_profile_id, client_id, query, count, last_visit)
            VALUES {rows}
            ON CONFLICT (user_profile_id, client_id, query) DO UPDATE SET
                count = zerver_useractivity.count + excluded.count,
                last_visit = greatest(zerver_useractivity.last_visit, excluded.last_visit)
            """
        ).format(rows=SQL(", ").join(rows))
        with connection.cursor() as cursor:
            cursor.execute(sql_query)
