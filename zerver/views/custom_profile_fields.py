from typing import Dict, List, Union

import orjson
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import human_users_only, require_realm_admin
from zerver.lib.actions import (
    check_remove_custom_profile_field_value,
    do_remove_realm_custom_profile_field,
    do_update_user_custom_profile_data_if_changed,
    try_add_realm_custom_profile_field,
    try_add_realm_default_custom_profile_field,
    try_reorder_realm_custom_profile_fields,
    try_update_realm_custom_profile_field,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.external_accounts import validate_external_account_field_data
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.types import ProfileFieldData
from zerver.lib.users import validate_user_custom_profile_data
from zerver.lib.validator import (
    check_capped_string,
    check_dict_only,
    check_int,
    check_list,
    check_string,
    check_union,
    validate_choice_field_data,
)
from zerver.models import CustomProfileField, UserProfile, custom_profile_fields_for_realm


def list_realm_custom_profile_fields(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    fields = custom_profile_fields_for_realm(user_profile.realm_id)
    return json_success({'custom_fields': [f.as_dict() for f in fields]})

hint_validator = check_capped_string(CustomProfileField.HINT_MAX_LENGTH)
name_validator = check_capped_string(CustomProfileField.NAME_MAX_LENGTH)

def validate_field_name_and_hint(name: str, hint: str) -> None:
    if not name.strip():
        raise JsonableError(_("Label cannot be blank."))

    try:
        hint_validator('hint', hint)
        name_validator('name', name)
    except ValidationError as error:
        raise JsonableError(error.message)

def validate_custom_field_data(field_type: int,
                               field_data: ProfileFieldData) -> None:
    try:
        if field_type == CustomProfileField.CHOICE:
            # Choice type field must have at least have one choice
            if len(field_data) < 1:
                raise JsonableError(_("Field must have at least one choice."))
            validate_choice_field_data(field_data)
        elif field_type == CustomProfileField.EXTERNAL_ACCOUNT:
            validate_external_account_field_data(field_data)
    except ValidationError as error:
        raise JsonableError(error.message)

def is_default_external_field(field_type: int, field_data: ProfileFieldData) -> bool:
    if field_type != CustomProfileField.EXTERNAL_ACCOUNT:
        return False
    if field_data['subtype'] == 'custom':
        return False
    return True

def validate_custom_profile_field(name: str, hint: str, field_type: int,
                                  field_data: ProfileFieldData) -> None:
    # Validate field data
    validate_custom_field_data(field_type, field_data)

    if not is_default_external_field(field_type, field_data):
        # If field is default external field then we will fetch all data
        # from our default field dictionary, so no need to validate name or hint
        # Validate field name, hint if not default external account field
        validate_field_name_and_hint(name, hint)

    field_types = [i[0] for i in CustomProfileField.FIELD_TYPE_CHOICES]
    if field_type not in field_types:
        raise JsonableError(_("Invalid field type."))

@require_realm_admin
@has_request_variables
def create_realm_custom_profile_field(request: HttpRequest,
                                      user_profile: UserProfile,
                                      name: str=REQ(default='', converter=lambda x: x.strip()),
                                      hint: str=REQ(default=''),
                                      field_data: ProfileFieldData=REQ(default={},
                                                                       converter=orjson.loads),
                                      field_type: int=REQ(validator=check_int)) -> HttpResponse:
    validate_custom_profile_field(name, hint, field_type, field_data)
    try:
        if is_default_external_field(field_type, field_data):
            field_subtype = field_data['subtype']
            assert isinstance(field_subtype, str)
            field = try_add_realm_default_custom_profile_field(
                realm=user_profile.realm,
                field_subtype=field_subtype,
            )
            return json_success({'id': field.id})
        else:
            field = try_add_realm_custom_profile_field(
                realm=user_profile.realm,
                name=name,
                field_data=field_data,
                field_type=field_type,
                hint=hint,
            )
            return json_success({'id': field.id})
    except IntegrityError:
        return json_error(_("A field with that label already exists."))

@require_realm_admin
def delete_realm_custom_profile_field(request: HttpRequest, user_profile: UserProfile,
                                      field_id: int) -> HttpResponse:
    try:
        field = CustomProfileField.objects.get(id=field_id)
    except CustomProfileField.DoesNotExist:
        return json_error(_('Field id {id} not found.').format(id=field_id))

    do_remove_realm_custom_profile_field(realm=user_profile.realm,
                                         field=field)
    return json_success()

@require_realm_admin
@has_request_variables
def update_realm_custom_profile_field(request: HttpRequest, user_profile: UserProfile,
                                      field_id: int,
                                      name: str=REQ(default='', converter=lambda x: x.strip()),
                                      hint: str=REQ(default=''),
                                      field_data: ProfileFieldData=REQ(default={},
                                                                       converter=orjson.loads),
                                      ) -> HttpResponse:
    realm = user_profile.realm
    try:
        field = CustomProfileField.objects.get(realm=realm, id=field_id)
    except CustomProfileField.DoesNotExist:
        return json_error(_('Field id {id} not found.').format(id=field_id))

    if field.field_type == CustomProfileField.EXTERNAL_ACCOUNT:
        if is_default_external_field(field.field_type, orjson.loads(field.field_data)):
            return json_error(_("Default custom field cannot be updated."))

    validate_custom_profile_field(name, hint, field.field_type, field_data)
    try:
        try_update_realm_custom_profile_field(realm, field, name, hint=hint,
                                              field_data=field_data)
    except IntegrityError:
        return json_error(_('A field with that label already exists.'))
    return json_success()

@require_realm_admin
@has_request_variables
def reorder_realm_custom_profile_fields(request: HttpRequest, user_profile: UserProfile,
                                        order: List[int]=REQ(validator=check_list(
                                            check_int))) -> HttpResponse:
    try_reorder_realm_custom_profile_fields(user_profile.realm, order)
    return json_success()

@human_users_only
@has_request_variables
def remove_user_custom_profile_data(request: HttpRequest, user_profile: UserProfile,
                                    data: List[int]=REQ(validator=check_list(
                                                        check_int))) -> HttpResponse:
    for field_id in data:
        check_remove_custom_profile_field_value(user_profile, field_id)
    return json_success()

@human_users_only
@has_request_variables
def update_user_custom_profile_data(
    request: HttpRequest,
    user_profile: UserProfile,
    data: List[Dict[str, Union[int, str, List[int]]]] = REQ(
        validator=check_list(
            check_dict_only([
                ('id', check_int),
                ('value', check_union([check_int, check_string, check_list(check_int)])),
            ]),
        )
    ),
) -> HttpResponse:

    validate_user_custom_profile_data(user_profile.realm.id, data)
    do_update_user_custom_profile_data_if_changed(user_profile, data)
    # We need to call this explicitly otherwise constraints are not check
    return json_success()
