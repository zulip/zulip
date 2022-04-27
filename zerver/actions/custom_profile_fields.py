from typing import Dict, List, Optional, Union

import orjson
from django.db import transaction
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.external_accounts import DEFAULT_EXTERNAL_ACCOUNTS
from zerver.lib.streams import render_stream_description
from zerver.lib.types import ProfileDataElementValue, ProfileFieldData
from zerver.models import (
    CustomProfileField,
    CustomProfileFieldValue,
    Realm,
    UserProfile,
    active_user_ids,
    custom_profile_fields_for_realm,
)
from zerver.tornado.django_api import send_event


def notify_realm_custom_profile_fields(realm: Realm) -> None:
    fields = custom_profile_fields_for_realm(realm.id)
    event = dict(type="custom_profile_fields", fields=[f.as_dict() for f in fields])
    send_event(realm, event, active_user_ids(realm.id))


def try_add_realm_default_custom_profile_field(
    realm: Realm, field_subtype: str
) -> CustomProfileField:
    field_data = DEFAULT_EXTERNAL_ACCOUNTS[field_subtype]
    custom_profile_field = CustomProfileField(
        realm=realm,
        name=field_data["name"],
        field_type=CustomProfileField.EXTERNAL_ACCOUNT,
        hint=field_data["hint"],
        field_data=orjson.dumps(dict(subtype=field_subtype)).decode(),
    )
    custom_profile_field.save()
    custom_profile_field.order = custom_profile_field.id
    custom_profile_field.save(update_fields=["order"])
    notify_realm_custom_profile_fields(realm)
    return custom_profile_field


def try_add_realm_custom_profile_field(
    realm: Realm,
    name: str,
    field_type: int,
    hint: str = "",
    field_data: Optional[ProfileFieldData] = None,
) -> CustomProfileField:
    custom_profile_field = CustomProfileField(realm=realm, name=name, field_type=field_type)
    custom_profile_field.hint = hint
    if (
        custom_profile_field.field_type == CustomProfileField.SELECT
        or custom_profile_field.field_type == CustomProfileField.EXTERNAL_ACCOUNT
    ):
        custom_profile_field.field_data = orjson.dumps(field_data or {}).decode()

    custom_profile_field.save()
    custom_profile_field.order = custom_profile_field.id
    custom_profile_field.save(update_fields=["order"])
    notify_realm_custom_profile_fields(realm)
    return custom_profile_field


def do_remove_realm_custom_profile_field(realm: Realm, field: CustomProfileField) -> None:
    """
    Deleting a field will also delete the user profile data
    associated with it in CustomProfileFieldValue model.
    """
    field.delete()
    notify_realm_custom_profile_fields(realm)


def do_remove_realm_custom_profile_fields(realm: Realm) -> None:
    CustomProfileField.objects.filter(realm=realm).delete()


def try_update_realm_custom_profile_field(
    realm: Realm,
    field: CustomProfileField,
    name: str,
    hint: str = "",
    field_data: Optional[ProfileFieldData] = None,
) -> None:
    field.name = name
    field.hint = hint
    if (
        field.field_type == CustomProfileField.SELECT
        or field.field_type == CustomProfileField.EXTERNAL_ACCOUNT
    ):
        field.field_data = orjson.dumps(field_data or {}).decode()
    field.save()
    notify_realm_custom_profile_fields(realm)


def try_reorder_realm_custom_profile_fields(realm: Realm, order: List[int]) -> None:
    order_mapping = {_[1]: _[0] for _ in enumerate(order)}
    custom_profile_fields = CustomProfileField.objects.filter(realm=realm)
    for custom_profile_field in custom_profile_fields:
        if custom_profile_field.id not in order_mapping:
            raise JsonableError(_("Invalid order mapping."))
    for custom_profile_field in custom_profile_fields:
        custom_profile_field.order = order_mapping[custom_profile_field.id]
        custom_profile_field.save(update_fields=["order"])
    notify_realm_custom_profile_fields(realm)


def notify_user_update_custom_profile_data(
    user_profile: UserProfile, field: Dict[str, Union[int, str, List[int], None]]
) -> None:
    data = dict(id=field["id"], value=field["value"])

    if field["rendered_value"]:
        data["rendered_value"] = field["rendered_value"]
    payload = dict(user_id=user_profile.id, custom_profile_field=data)
    event = dict(type="realm_user", op="update", person=payload)
    send_event(user_profile.realm, event, active_user_ids(user_profile.realm.id))


def do_update_user_custom_profile_data_if_changed(
    user_profile: UserProfile,
    data: List[Dict[str, Union[int, ProfileDataElementValue]]],
) -> None:
    with transaction.atomic():
        for custom_profile_field in data:
            field_value, created = CustomProfileFieldValue.objects.get_or_create(
                user_profile=user_profile, field_id=custom_profile_field["id"]
            )

            # field_value.value is a TextField() so we need to have field["value"]
            # in string form to correctly make comparisons and assignments.
            if isinstance(custom_profile_field["value"], str):
                custom_profile_field_value_string = custom_profile_field["value"]
            else:
                custom_profile_field_value_string = orjson.dumps(
                    custom_profile_field["value"]
                ).decode()

            if not created and field_value.value == custom_profile_field_value_string:
                # If the field value isn't actually being changed to a different one,
                # we have nothing to do here for this field.
                continue

            field_value.value = custom_profile_field_value_string
            if field_value.field.is_renderable():
                field_value.rendered_value = render_stream_description(
                    custom_profile_field_value_string
                )
                field_value.save(update_fields=["value", "rendered_value"])
            else:
                field_value.save(update_fields=["value"])
            notify_user_update_custom_profile_data(
                user_profile,
                {
                    "id": field_value.field_id,
                    "value": field_value.value,
                    "rendered_value": field_value.rendered_value,
                    "type": field_value.field.field_type,
                },
            )


def check_remove_custom_profile_field_value(user_profile: UserProfile, field_id: int) -> None:
    try:
        custom_profile_field = CustomProfileField.objects.get(realm=user_profile.realm, id=field_id)
        field_value = CustomProfileFieldValue.objects.get(
            field=custom_profile_field, user_profile=user_profile
        )
        field_value.delete()
        notify_user_update_custom_profile_data(
            user_profile,
            {
                "id": field_id,
                "value": None,
                "rendered_value": None,
                "type": custom_profile_field.field_type,
            },
        )
    except CustomProfileField.DoesNotExist:
        raise JsonableError(_("Field id {id} not found.").format(id=field_id))
    except CustomProfileFieldValue.DoesNotExist:
        pass
