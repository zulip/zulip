from typing import Any, Dict, Iterator, List, Optional

from stripe import Subscription

class SubscriptionListObject:
    data: List[Subscription]
    def __iter__(self) -> Iterator[Subscription]: ...
