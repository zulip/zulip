"""

This code slurps some data off the system queue and then adds the data
to all the relevant client queues.

The bigger tornado server does a lot of post-processing in event_queue.py,
but we more or less just distribute the events into the appropriate
buckets without any extra business logic.
"""

from .clients import get_clients_for_user


def process_notifications(notices):
    for notice in notices:
        event = notice["event"]
        user_ids = notice["users"]

        assert event["type"] == "presence"
        assert "user_id" in event
        assert "presence" in event

        print(f"OUTBOUND! about to send out event to some subset of {len(user_ids)} users")

        for user_id in user_ids:
            for client in get_clients_for_user(user_id):
                if client.accepts_event(event):
                    client.add_event(event)
