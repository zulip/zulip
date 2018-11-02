from typing import Any, Dict, Optional

from zerver.models import Message, Realm

# Filters such as UserMentionPattern need a message, but python-markdown
# provides no way to pass extra params through to a pattern. Thus, a global.
current_message = None  # type: Optional[Message]

current_realm = None  # type: Optional[Realm]

# We avoid doing DB queries in our markdown thread to avoid the overhead of
# opening a new DB connection. These connections tend to live longer than the
# threads themselves, as well.
db_data = None  # type: Optional[Dict[str, Any]]
