
from typing import Union, List, Dict, Optional
import logging
import ujson

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import require_realm_admin, human_users_only
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.actions import (try_add_realm_custom_profile_field,
                                do_remove_realm_custom_profile_field,
                                try_update_realm_custom_profile_field,
                                do_update_user_custom_profile_data)
from zerver.lib.response import json_success, json_error
from zerver.lib.types import ProfileFieldData
from zerver.lib.validator import (check_dict, check_list, check_int,
                                  validate_field_data, check_capped_string)

from zerver.models import (custom_profile_fields_for_realm, UserProfile,
                           CustomProfileField, custom_profile_fields_for_realm)

def list_realm_custom_profile_fields(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    fields = custom_profile_fields_for_realm(user_profile.realm_id)
    return json_success({'custom_fields': [f.as_dict() for f in fields]})

hint_validator = check_capped_string(CustomProfileField.HINT_MAX_LENGTH)

@require_realm_admin
@has_request_variables
def create_realm_custom_profile_field(request: HttpRequest,
                                      user_profile: UserProfile, name: str=REQ(),
                                      hint: str=REQ(default=''),
                                      field_data: ProfileFieldData=REQ(default={},
                                                                       converter=ujson.loads),
                                      field_type: int=REQ(validator=check_int)) -> HttpResponse:
    if not name.strip():
        return json_error(_("Name cannot be blank."))

    error = hint_validator('hint', hint)
    if error:
        return json_error(error)

    field_types = [i[0] for i in CustomProfileField.FIELD_TYPE_CHOICES]
    if field_type not in field_types:
        return json_error(_("Invalid field type."))

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
                                      field_id: int, name: str=REQ(),
                                      hint: str=REQ(default=''),
                                      field_data: ProfileFieldData=REQ(default={},
                                                                       converter=ujson.loads),
                                      ) -> HttpResponse:
    if not name.strip():
        return json_error(_("Name cannot be blank."))

    error = hint_validator('hint', hint)
    if error:
        return json_error(error, data={'field': 'hint'})

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

@human_users_only
@has_request_variables
def update_user_custom_profile_data(
        request: HttpRequest,
        user_profile: UserProfile,
        data: List[Dict[str, Union[int, str]]]=REQ(validator=check_list(
            check_dict([('id', check_int)])))) -> HttpResponse:
    for item in data:
        field_id = item['id']
        try:
            field = CustomProfileField.objects.get(id=field_id)
        except CustomProfileField.DoesNotExist:
            return json_error(_('Field id {id} not found.').format(id=field_id))

        validators = CustomProfileField.FIELD_VALIDATORS
        extended_validators = CustomProfileField.EXTENDED_FIELD_VALIDATORS
        field_type = field.field_type
        value = item['value']
        if field_type in validators:
            validator = validators[field_type]
            var_name = 'value[{}]'.format(field_id)
            result = validator(var_name, value)
        else:
            # Check extended validators.
            extended_validator = extended_validators[field_type]
            field_data = field.field_data
            var_name = 'value[{}]'.format(field_id)
            result = extended_validator(var_name, field_data, value)

        if result is not None:
            return json_error(result)

    do_update_user_custom_profile_data(user_profile, data)
    # We need to call this explicitly otherwise constraints are not check
    return json_success()
