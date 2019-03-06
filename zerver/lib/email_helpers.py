from zerver.models import UserProfile

import email.message as message
from typing import Optional

def format_to(to_user: UserProfile) -> str:
    # Change to formataddr((to_user.full_name, to_user.email)) once
    # https://github.com/zulip/zulip/issues/4676 is resolved
    return to_user.delivery_email

def get_message_part_by_type(message: message.Message, content_type: str) -> Optional[str]:
    charsets = message.get_charsets()

    for idx, part in enumerate(message.walk()):
        if part.get_content_type() == content_type:
            content = part.get_payload(decode=True)
            assert isinstance(content, bytes)
            if charsets[idx]:
                return content.decode(charsets[idx], errors="ignore")
    return None
