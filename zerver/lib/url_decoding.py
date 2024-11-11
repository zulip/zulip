from urllib.parse import urlsplit

from django.conf import settings


def is_valid_near_link_recipient_encoding(recipient_encoding: str) -> bool:
    try:
        recipient_id, recipient_name = recipient_encoding.split("-", maxsplit=1)
    except ValueError:
        # Failed to decode the recipient encoding. Refer to
        # `encode_stream()` in url_encoding.py to see how we
        # encode recipient data for near links.
        return False

    recipient_name_is_encoded = all(char not in recipient_name for char in [" ", "%"])
    recipient_id_is_digits = all(id.isdigit() for id in recipient_id.split(","))

    return recipient_id_is_digits and recipient_name_is_encoded


def check_near_link_base(url: str) -> bool:
    """
    Performs basic checks to see whether or not the near link is
    from the same Zulip server and has a valid base structure.

    That is, they start with three main parts: a category
    (`narrow`), a section (`channel` or `dm`), and recipient
    encoding (e.g., `10-Denmark`, `11,12,20-group`).

    To match for a specific type of near link, use a function
    like `is_same_server_message_link`, which checks for
    additional parts the link might have.
    """
    split_result = urlsplit(url)
    fragment_parts = split_result.fragment.split("/")
    if split_result.hostname not in {None, settings.EXTERNAL_HOST_WITHOUT_PORT}:
        return False

    if len(fragment_parts) < 3:
        return False

    category = fragment_parts[0]
    section = fragment_parts[1]

    return (
        category == "narrow"
        and section in {"channel", "stream", "dm"}
        and is_valid_near_link_recipient_encoding(fragment_parts[2])
    )


def is_same_server_message_link(url: str) -> bool:
    """
    A message link is a type of near link that always ends with
    `/near/<message_id>`, where <message_id> is a sequence of
    digits. The URL fragment of a message link has at least 5
    parts. e.g. '#narrow/dm/9,15-dm/near/43'
    """
    if not check_near_link_base(url):
        return False
    fragment_parts = urlsplit(url).fragment.split("/")

    if len(fragment_parts) < 5:
        return False

    ends_with_near_message_id = fragment_parts[-2] == "near" and fragment_parts[-1].isdigit()

    return ends_with_near_message_id
