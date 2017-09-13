from __future__ import absolute_import
from __future__ import print_function

from typing import (Dict, List)

from django.db import connection
from zerver.models import Recipient

class StreamRecipientMap(object):
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
    def __init__(self):
        # type: () -> None
        self.recip_to_stream = dict()  # type: Dict[int, int]
        self.stream_to_recip = dict()  # type: Dict[int, int]

    def populate_for_stream_ids(self, stream_ids):
        # type: (List[int]) -> None
        stream_ids = sorted([
            stream_id for stream_id in stream_ids
            if stream_id not in self.stream_to_recip
        ])

        if not stream_ids:
            return

        # see comment at the top of the class
        id_list = ', '.join(str(stream_id) for stream_id in stream_ids)
        query = '''
            SELECT
                zerver_recipient.id as recipient_id,
                zerver_stream.id as stream_id
            FROM
                zerver_stream
            INNER JOIN zerver_recipient ON
                zerver_stream.id = zerver_recipient.type_id
            WHERE
                zerver_recipient.type = %d
            AND
                zerver_stream.id in (%s)
            ''' % (Recipient.STREAM, id_list)
        self._process_query(query)

    def populate_for_recipient_ids(self, recipient_ids):
        # type: (List[int]) -> None
        recipient_ids = sorted([
            recip_id for recip_id in recipient_ids
            if recip_id not in self.recip_to_stream
        ])

        if not recipient_ids:
            return

        # see comment at the top of the class
        id_list = ', '.join(str(recip_id) for recip_id in recipient_ids)
        query = '''
            SELECT
                zerver_recipient.id as recipient_id,
                zerver_stream.id as stream_id
            FROM
                zerver_recipient
            INNER JOIN zerver_stream ON
                zerver_stream.id = zerver_recipient.type_id
            WHERE
                zerver_recipient.type = %d
            AND
                zerver_recipient.id in (%s)
            ''' % (Recipient.STREAM, id_list)

        self._process_query(query)

    def _process_query(self, query):
        # type: (str) -> None
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        for recip_id, stream_id in rows:
            self.recip_to_stream[recip_id] = stream_id
            self.stream_to_recip[stream_id] = recip_id

    def recipient_id_for(self, stream_id):
        # type: (int) -> int
        return self.stream_to_recip[stream_id]

    def stream_id_for(self, recip_id):
        # type: (int) -> int
        return self.recip_to_stream[recip_id]

    def recipient_to_stream_id_dict(self):
        # type: () -> Dict[int, int]
        return self.recip_to_stream
