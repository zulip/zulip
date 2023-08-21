"""
This replaces sharding.py in the bigger tornado server.

We may eventually shard presence servers, but that will
be a lot easier once other details are worked out.

Sharding isn't rocket science, so we can always add that
later.
"""


def get_server_url():
    return "http://127.0.0.1:8888"


def notify_queue_name():
    return "presence_server_notifications"
