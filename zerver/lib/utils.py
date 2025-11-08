import hashlib
import logging
import re
import secrets
from collections.abc import Callable
from typing import TypeVar

from django.db import models

T = TypeVar("T")


def generate_api_key() -> str:
    api_key = ""
    while len(api_key) < 32:
        # One iteration suffices 99.4992% of the time.
        api_key += secrets.token_urlsafe(3 * 9).replace("_", "").replace("-", "")
    return api_key[:32]


def has_api_key_format(key: str) -> bool:
    return bool(re.fullmatch(r"([A-Za-z0-9]){32}", key))


def assert_is_not_none(value: T | None) -> T:
    assert value is not None
    return value


def process_list_in_batches(
    lst: list[T], chunk_size: int, process_batch: Callable[[list[T]], None]
) -> None:
    offset = 0
    total_message_length = len(lst)
    while True:
        items = lst[offset : offset + chunk_size]
        if not items:
            break
        process_batch(items)
        offset = min(offset + chunk_size, total_message_length)
        logging.info("Processed messages up to %s / %s", offset, total_message_length)


def optional_bytes_to_mib(value: int | None) -> int | None:
    if value is None:
        return None
    else:
        return value >> 20


def get_fk_field_name(model: type[models.Model], related_model: type[models.Model]) -> str | None:
    """
    Get the name of the foreign key field in model, pointing the related_model table.
    Returns None if there is no such field.

    Example usage:

    get_fk_field_name(UserProfile, Realm) returns "realm"
    """

    fields = model._meta.get_fields()
    foreign_key_fields_to_related_model = [
        field
        for field in fields
        if hasattr(field, "related_model") and field.related_model == related_model
    ]

    if len(foreign_key_fields_to_related_model) == 0:
        return None

    assert len(foreign_key_fields_to_related_model) == 1

    return foreign_key_fields_to_related_model[0].name


def sha256_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
