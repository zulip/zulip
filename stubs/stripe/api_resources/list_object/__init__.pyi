from stripe import Subscription
from typing import Optional, Any, Dict, List, Iterator

class SubscriptionListObject:
    data: List[Subscription]

    def __iter__(self) -> Iterator[Subscription]:
        ...
