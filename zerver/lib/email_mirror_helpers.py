import re

from django.conf import settings
from django.utils.text import slugify

from zerver.models import Stream

from typing import Tuple

class ZulipEmailForwardError(Exception):
    pass

def get_email_gateway_message_string_from_address(address: str) -> str:
    pattern_parts = [re.escape(part) for part in settings.EMAIL_GATEWAY_PATTERN.split('%s')]
    if settings.EMAIL_GATEWAY_EXTRA_PATTERN_HACK:
        # Accept mails delivered to any Zulip server
        pattern_parts[-1] = settings.EMAIL_GATEWAY_EXTRA_PATTERN_HACK
    match_email_re = re.compile("(.*?)".join(pattern_parts))
    match = match_email_re.match(address)

    if not match:
        raise ZulipEmailForwardError('Address not recognized by gateway.')
    msg_string = match.group(1)

    return msg_string

def encode_email_address(stream: Stream) -> str:
    return encode_email_address_helper(stream.name, stream.email_token)

def encode_email_address_helper(name: str, email_token: str) -> str:
    # Some deployments may not use the email gateway
    if settings.EMAIL_GATEWAY_PATTERN == '':
        return ''

    # Given the fact that we have almost no restrictions on stream names and
    # that what characters are allowed in e-mail addresses is complicated and
    # dependent on context in the address, we opt for a simple scheme:
    # 1. Replace all substrings of non-alphanumeric characters with a single hyphen.
    # 2. Use Django's slugify to convert the resulting name to ascii.
    # 3. If the resulting name is shorter than the name we got in step 1,
    # it means some letters can't be reasonably turned to ascii and have to be dropped,
    # which would mangle the name, so we just skip the name part of the address.
    name = re.sub(r"\W+", '-', name)
    slug_name = slugify(name)
    encoded_name = slug_name if len(slug_name) == len(name) else ''

    # If encoded_name ends up empty, we just skip this part of the address:
    if encoded_name:
        encoded_token = "%s+%s" % (encoded_name, email_token)
    else:
        encoded_token = email_token

    return settings.EMAIL_GATEWAY_PATTERN % (encoded_token,)

def decode_email_address(email: str) -> Tuple[str, bool]:
    # Perform the reverse of encode_email_address. Returns a tuple of
    # (email_token, show_sender)
    msg_string = get_email_gateway_message_string_from_address(email)

    if msg_string.endswith(('+show-sender', '.show-sender')):
        show_sender = True
        msg_string = msg_string[:-12]  # strip "+show-sender"
    else:
        show_sender = False

    # Workaround for Google Groups and other programs that don't accept emails
    # that have + signs in them (see Trac #2102)
    splitting_char = '.' if '.' in msg_string else '+'

    parts = msg_string.split(splitting_char)
    # msg_string may have one or two parts:
    # [stream_name, email_token] or just [email_token]
    if len(parts) == 1:
        token = parts[0]
    else:
        token = parts[1]

    return token, show_sender
