from typing import Dict, List

from django.db import connection
from psycopg2.sql import SQL

from zerver.models import Recipient


class StreamRecipientMap:
    '''
    This class maps stream_id -> recipient_id and vice versa.
    It is useful for bulk operations.  Call the populate_* methods
    to initialize the data structures.  You should try to avoid
    excessive queries by finding ids up front, but you can call
    this repeatedly, and it will only look up new ids.

    You should ONLY use this class for READ operations.

    Note that this class uses raw SQL, because we want to highly
    optimize page loads.
    '''

    def __init__(self) -> None:
        self.recip_to_stream: Dict[int, int] = {}
        self.stream_to_recip: Dict[int, int] = {}

    def populate_with(self, *, stream_id: int, recipient_id: int) -> None:
        # We use * to enforce using named arguments when calling this function,
        # to avoid confusion about the ordering of the two integers.
        self.recip_to_stream[recipient_id] = stream_id
        self.stream_to_recip[stream_id] = recipient_id

    def populate_for_recipient_ids(self, recipient_ids: List[int]) -> None:
        recipient_ids = sorted(
            recip_id for recip_id in recipient_ids
            if recip_id not in self.recip_to_stream
        )

        if not recipient_ids:
            return

        # see comment at the top of the class
        query = SQL('''
            SELECT
                zerver_recipient.id as recipient_id,
                zerver_recipient.type_id as stream_id
            FROM
                zerver_recipient
            WHERE
                zerver_recipient.type = %(STREAM)s
            AND
                zerver_recipient.id in %(recipient_ids)s
        ''')

        cursor = connection.cursor()
        cursor.execute(query, {
            "STREAM": Recipient.STREAM,
            "recipient_ids": tuple(recipient_ids),
        })
        rows = cursor.fetchall()
        cursor.close()
        for recip_id, stream_id in rows:
            self.recip_to_stream[recip_id] = stream_id
            self.stream_to_recip[stream_id] = recip_id

    def recipient_id_for(self, stream_id: int) -> int:
        return self.stream_to_recip[stream_id]

    def stream_id_for(self, recip_id: int) -> int:
        return self.recip_to_stream[recip_id]

    def recipient_to_stream_id_dict(self) -> Dict[int, int]:
        return self.recip_to_stream
