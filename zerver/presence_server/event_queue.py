"""
This is basically a queue. Surprised by that?

It's a queue of events to send out to a particular client.
"""
from collections import deque

class EventQueue:
    def __init__(self, id: str) -> None:
        # When extending this list of properties, one must be sure to
        # update to_dict and from_dict.

        self.queue = deque()
        self.next_event_id: int = 0
        # will only be None for migration from old versions
        self.newest_pruned_id: Optional[int] = -1
        self.id: str = id

    def to_dict(self):
        # If you add a new key to this dict, make sure you add appropriate
        # migration code in from_dict or load_event_queues to account for
        # loading event queues that lack that key.
        d = dict(
            id=self.id,
            next_event_id=self.next_event_id,
            queue=list(self.queue),
        )
        if self.newest_pruned_id is not None:
            d["newest_pruned_id"] = self.newest_pruned_id
        return d

    @classmethod
    def from_dict(cls, d) -> "EventQueue":
        ret = cls(d["id"])
        ret.next_event_id = d["next_event_id"]
        ret.newest_pruned_id = d.get("newest_pruned_id", None)
        ret.queue = deque(d["queue"])
        return ret

    def push(self, orig_event):
        # By default, we make a shallow copy of the event dictionary
        # to push into the target event queue; this allows the calling
        # code to send the same "event" object to multiple queues.
        # This behavior is important because the event_queue system is
        # about to mutate the event dictionary, minimally to add the
        # event_id attribute.
        event = dict(orig_event)
        event["id"] = self.next_event_id
        self.next_event_id += 1
        self.queue.append(event)

    def pop(self):
        return self.queue.popleft()

    def empty(self):
        return len(self.queue) == 0

    def prune(self, through_id):
        while len(self.queue) != 0 and self.queue[0]["id"] <= through_id:
            self.newest_pruned_id = self.queue[0]["id"]
            self.pop()

    def contents(self, include_internal_data = False):
        contents = []

        for event in self.queue:
            contents.append(event)

        self.queue = deque(contents)

        return contents
