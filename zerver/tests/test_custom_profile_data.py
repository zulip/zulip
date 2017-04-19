# -*- coding: utf-8 -*-
from __future__ import absolute_import

from typing import Union, List, Dict, Text, Any
from mock import patch

from zerver.lib.actions import get_realm, try_add_realm_custom_profile_field, \
    do_update_user_custom_profile_data, do_remove_realm_custom_profile_field
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import CustomProfileField, get_user_profile_by_email, \
    custom_profile_fields_for_realm
import ujson


class CustomProfileFieldTest(ZulipTestCase):

    def test_list(self):
        # type: () -> None
        self.login(u"iago@zulip.com")
        realm = get_realm('zulip')
        try_add_realm_custom_profile_field(realm, u"Phone",
                                           CustomProfileField.SHORT_TEXT)
        result = self.client_get("/json/realm/profile_fields")
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        content = result.json()
        self.assertEqual(len(content["custom_fields"]), 1)

    def test_create(self):
        # type: () -> None
        self.login(u"iago@zulip.com")
        data = {"name": u"Phone", "field_type": "text id"}  # type: Dict[str, Any]
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, u'argument "field_type" is not valid json.')

        data["name"] = ""
        data["field_type"] = 100
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, u'Name cannot be blank.')

        data["name"] = "Phone"
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, u'Invalid field type.')

        data["name"] = "Phone"
        data["field_type"] = CustomProfileField.SHORT_TEXT
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_success(result)

        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result,
                               u'A field with that name already exists.')

    def test_not_realm_admin(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/realm/profile_fields")
        self.assert_json_error(result, u'Must be a realm administrator')
        result = self.client_delete("/json/realm/profile_fields/1")
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_delete(self):
        # type: () -> None
        self.login("iago@zulip.com")
        realm = get_realm('zulip')
        field = try_add_realm_custom_profile_field(
            realm,
            "Phone",
            CustomProfileField.SHORT_TEXT
        )
        result = self.client_delete("/json/realm/profile_fields/100")
        self.assert_json_error(result, 'Field id 100 not found.')

        self.assertEqual(CustomProfileField.objects.count(), 1)
        result = self.client_delete(
            "/json/realm/profile_fields/{}".format(field.id))
        self.assert_json_success(result)
        self.assertEqual(CustomProfileField.objects.count(), 0)

    def test_update(self):
        # type: () -> None
        self.login("iago@zulip.com")
        realm = get_realm('zulip')
        result = self.client_patch(
            "/json/realm/profile_fields/100",
            info={'name': '',
                  'field_type': CustomProfileField.SHORT_TEXT}
        )
        self.assert_json_error(result, u'Name cannot be blank.')

        result = self.client_patch(
            "/json/realm/profile_fields/100",
            info={'name': 'Phone Number',
                  'field_type': CustomProfileField.SHORT_TEXT}
        )
        self.assert_json_error(result, u'Field id 100 not found.')

        field = try_add_realm_custom_profile_field(
            realm,
            u"Phone",
            CustomProfileField.SHORT_TEXT
        )

        self.assertEqual(CustomProfileField.objects.count(), 1)
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'Phone Number',
                  'field_type': CustomProfileField.SHORT_TEXT})
        self.assert_json_success(result)
        self.assertEqual(CustomProfileField.objects.count(), 1)
        field = CustomProfileField.objects.first()
        self.assertEqual(field.name, 'Phone Number')
        self.assertEqual(field.field_type, CustomProfileField.SHORT_TEXT)

    def test_update_is_aware_of_uniqueness(self):
        # type: () -> None
        self.login(u"iago@zulip.com")
        realm = get_realm('zulip')
        try_add_realm_custom_profile_field(realm, u"Phone",
                                           CustomProfileField.SHORT_TEXT)

        field = try_add_realm_custom_profile_field(
            realm,
            u"Phone 1",
            CustomProfileField.SHORT_TEXT
        )

        self.assertEqual(CustomProfileField.objects.count(), 2)
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'Phone', 'field_type': CustomProfileField.SHORT_TEXT})
        self.assert_json_error(
            result, u'A field with that name already exists.')

class CustomProfileDataTest(ZulipTestCase):

    def test_update_invalid(self):
        # type: () -> None
        self.login(u"iago@zulip.com")
        data = [{'id': 1234, 'value': '12'}]
        result = self.client_patch("/json/users/me/profile_data", {
            'data': ujson.dumps(data)
        })
        self.assert_json_error(result,
                               u"Field id 1234 not found.")

    def test_update_invalid_value(self):
        # type: () -> None
        self.login(u"iago@zulip.com")
        realm = get_realm('zulip')
        age_field = try_add_realm_custom_profile_field(
            realm,
            u"age",
            CustomProfileField.INTEGER
        )

        data = [{'id': age_field.id, 'value': 'text'}]
        result = self.client_patch("/json/users/me/profile_data", {
            'data': ujson.dumps(data)
        })
        self.assert_json_error(
            result,
            u"value[{}] is not an integer".format(age_field.id))

    def test_update_invalid_double(self):
        # type: () -> None
        self.login(u"iago@zulip.com")
        realm = get_realm('zulip')
        field = try_add_realm_custom_profile_field(
            realm,
            u"distance",
            CustomProfileField.FLOAT
        )

        data = [{'id': field.id, 'value': 'text'}]
        result = self.client_patch("/json/users/me/profile_data", {
            'data': ujson.dumps(data)
        })
        self.assert_json_error(
            result,
            u"value[{}] is not a float".format(field.id))

    def test_update_invalid_short_text(self):
        # type: () -> None
        self.login(u"iago@zulip.com")
        realm = get_realm('zulip')
        field = try_add_realm_custom_profile_field(
            realm,
            u"description",
            CustomProfileField.SHORT_TEXT
        )

        data = [{'id': field.id, 'value': 't' * 201}]
        result = self.client_patch("/json/users/me/profile_data", {
            'data': ujson.dumps(data)
        })
        self.assert_json_error(
            result,
            u"value[{}] is longer than 200.".format(field.id))

    def test_update_profile_data(self):
        # type: () -> None
        self.login(u"iago@zulip.com")
        realm = get_realm('zulip')
        fields = [
            (CustomProfileField.SHORT_TEXT, 'name 1', 'short text data'),
            (CustomProfileField.LONG_TEXT, 'name 2', 'long text data'),
            (CustomProfileField.INTEGER, 'name 3', 1),
            (CustomProfileField.FLOAT, 'name 4', 2.0),
        ]

        data = []
        for i, field_value in enumerate(fields):
            field_type, name, value = field_value
            field = try_add_realm_custom_profile_field(realm, name, field_type)
            data.append({
                'id': field.id,
                'value': value,
            })

        result = self.client_patch("/json/users/me/profile_data",
                                   {'data': ujson.dumps(data)})
        self.assert_json_success(result)

        iago = get_user_profile_by_email('iago@zulip.com')
        expected_value = {f['id']: f['value'] for f in data}

        for field in iago.profile_data:
            self.assertEqual(field['value'], expected_value[field['id']])
            for k in ['id', 'type', 'name']:
                self.assertIn(k, field)

            self.assertEqual(len(iago.profile_data), 4)

        # Update value of field
        field = CustomProfileField.objects.get(name='name 1', realm=realm)
        data = [{
            'id': field.id,
            'value': 'foobar',
        }]

        result = self.client_patch("/json/users/me/profile_data",
                                   {'data': ujson.dumps(data)})
        self.assert_json_success(result)
        for f in iago.profile_data:
            if f['id'] == field.id:
                self.assertEqual(f['value'], 'foobar')

    def test_delete(self):
        # type: () -> None
        user_profile = get_user_profile_by_email('iago@zulip.com')
        realm = user_profile.realm
        field = try_add_realm_custom_profile_field(
            realm,
            u"Phone",
            CustomProfileField.SHORT_TEXT
        )
        data = [{'id': field.id, 'value': u'123456'}]  # type: List[Dict[str, Union[int, Text]]]
        do_update_user_custom_profile_data(user_profile, data)

        self.assertEqual(len(custom_profile_fields_for_realm(realm.id)), 1)
        self.assertEqual(user_profile.customprofilefieldvalue_set.count(), 1)

        do_remove_realm_custom_profile_field(realm, field)

        self.assertEqual(len(custom_profile_fields_for_realm(realm.id)), 0)
        self.assertEqual(user_profile.customprofilefieldvalue_set.count(), 0)
