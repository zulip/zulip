from typing import Union, List, Dict
import ujson

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import require_realm_admin, human_users_only
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.actions import (try_add_realm_custom_profile_field,
                                do_remove_realm_custom_profile_field,
                                try_update_realm_custom_profile_field,
                                do_update_user_custom_profile_data,
                                try_reorder_realm_custom_profile_fields,
                                check_remove_custom_profile_field_value)
from zerver.lib.response import json_success, json_error
from zerver.lib.types import ProfileFieldData
from zerver.lib.validator import (check_dict, check_list, check_int,
                                  validate_field_data, check_capped_string)

from zerver.models import (UserProfile,
                           CustomProfileField, custom_profile_fields_for_realm)
from zerver.lib.exceptions import JsonableError
from zerver.lib.users import validate_user_custom_profile_data

def list_realm_custom_profile_fields(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    fields = custom_profile_fields_for_realm(user_profile.realm_id)
    return json_success({'custom_fields': [f.as_dict() for f in fields]})

hint_validator = check_capped_string(CustomProfileField.HINT_MAX_LENGTH)
name_validator = check_capped_string(CustomProfileField.NAME_MAX_LENGTH)

def validate_field_name_and_hint(name: str, hint: str) -> None:
    if not name.strip():
        raise JsonableError(_("Name cannot be blank."))

    error = hint_validator('hint', hint)
    if error:
        raise JsonableError(error)

    error = name_validator('name', name)
    if error:
        raise JsonableError(error)

@require_realm_admin
@has_request_variables
def create_realm_custom_profile_field(request: HttpRequest,
                                      user_profile: UserProfile,
                                      name: str=REQ(),
                                      hint: str=REQ(default=''),
                                      field_data: ProfileFieldData=REQ(default={},
                                                                       converter=ujson.loads),
                                      field_type: int=REQ(validator=check_int)) -> HttpResponse:
    validate_field_name_and_hint(name, hint)
    field_types = [i[0] for i in CustomProfileField.FIELD_TYPE_CHOICES]
    if field_type not in field_types:
        return json_error(_("Invalid field type."))

    # Choice type field must have at least have one choice
    if field_type == CustomProfileField.CHOICE and len(field_data) < 1:
        return json_error(_("Field must have at least one choice."))

    error = validate_field_data(field_data)
    if error:
        return json_error(error)

    try:
        field = try_add_realm_custom_profile_field(
            realm=user_profile.realm,
            name=name,
            field_data=field_data,
            field_type=field_type,
            hint=hint,
        )
        return json_success({'id': field.id})
    except IntegrityError:
        return json_error(_("A field with that name already exists."))

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
                                      name: str=REQ(),
                                      hint: str=REQ(default=''),
                                      field_data: ProfileFieldData=REQ(default={},
                                                                       converter=ujson.loads),
                                      ) -> HttpResponse:
    validate_field_name_and_hint(name, hint)
    error = validate_field_data(field_data)
    if error:
        return json_error(error)

    realm = user_profile.realm
    try:
        field = CustomProfileField.objects.get(realm=realm, id=field_id)
    except CustomProfileField.DoesNotExist:
        return json_error(_('Field id {id} not found.').format(id=field_id))

    try:
        try_update_realm_custom_profile_field(realm, field, name, hint=hint,
                                              field_data=field_data)
    except IntegrityError:
        return json_error(_('A field with that name already exists.'))
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
        data: List[Dict[str, Union[int, str, List[int]]]]=REQ(validator=check_list(
            check_dict([('id', check_int)])))) -> HttpResponse:

    validate_user_custom_profile_data(user_profile.realm.id, data)
    do_update_user_custom_profile_data(user_profile, data)
    # We need to call this explicitly otherwise constraints are not check
    return json_success()
