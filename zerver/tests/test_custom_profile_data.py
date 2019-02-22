# -*- coding: utf-8 -*-

from typing import Union, List, Dict, Any

from zerver.lib.actions import get_realm, try_add_realm_custom_profile_field, \
    do_update_user_custom_profile_data, do_remove_realm_custom_profile_field, \
    try_reorder_realm_custom_profile_fields
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.bugdown import convert as bugdown_convert
from zerver.models import CustomProfileField, \
    custom_profile_fields_for_realm, CustomProfileFieldValue
import ujson

class CustomProfileFieldTest(ZulipTestCase):
    def setUp(self) -> None:
        self.realm = get_realm("zulip")
        self.original_count = len(custom_profile_fields_for_realm(self.realm.id))

    def custom_field_exists_in_realm(self, field_id: int) -> bool:
        fields = custom_profile_fields_for_realm(self.realm.id)
        field_ids = [field.id for field in fields]
        return (field_id in field_ids)

    def test_list(self) -> None:
        self.login(self.example_email("iago"))
        result = self.client_get("/json/realm/profile_fields")
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        content = result.json()
        self.assertEqual(len(content["custom_fields"]), self.original_count)

    def test_list_order(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        order = (
            CustomProfileField.objects.filter(realm=realm)
            .order_by('-order')
            .values_list('order', flat=True)
        )
        try_reorder_realm_custom_profile_fields(realm, order)
        result = self.client_get("/json/realm/profile_fields")
        content = result.json()
        self.assertListEqual(content["custom_fields"],
                             sorted(content["custom_fields"], key=lambda x: -x["id"]))

    def test_create(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        data = {"name": u"Phone", "field_type": "text id"}  # type: Dict[str, Any]
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, u'Argument "field_type" is not valid JSON.')

        data["name"] = ""
        data["field_type"] = 100
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, u'Name cannot be blank.')

        data["name"] = "*" * 41
        data["field_type"] = 100
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'name is too long (limit: 40 characters)')

        data["name"] = "Phone"
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, u'Invalid field type.')

        data["name"] = "Phone"
        data["hint"] = "*" * 81
        data["field_type"] = CustomProfileField.SHORT_TEXT
        result = self.client_post("/json/realm/profile_fields", info=data)
        msg = "hint is too long (limit: 80 characters)"
        self.assert_json_error(result, msg)

        data["name"] = "Phone"
        data["hint"] = "Contact number"
        data["field_type"] = CustomProfileField.SHORT_TEXT
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_success(result)

        field = CustomProfileField.objects.get(name="Phone", realm=realm)
        self.assertEqual(field.id, field.order)

        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result,
                               u'A field with that name already exists.')

    def test_create_choice_field(self) -> None:
        self.login(self.example_email("iago"))
        data = {}  # type: Dict[str, Union[str, int]]
        data["name"] = "Favorite programming language"
        data["field_type"] = CustomProfileField.CHOICE

        data['field_data'] = 'invalid'
        result = self.client_post("/json/realm/profile_fields", info=data)
        error_msg = "Bad value for 'field_data': invalid"
        self.assert_json_error(result, error_msg)

        data["field_data"] = ujson.dumps({
            'python': ['1'],
            'java': ['2'],
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data is not a dict')

        data["field_data"] = ujson.dumps({
            'python': {'text': 'Python'},
            'java': {'text': 'Java'},
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, "order key is missing from field_data")

        data["field_data"] = ujson.dumps({
            'python': {'text': 'Python', 'order': ''},
            'java': {'text': 'Java', 'order': '2'},
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data["order"] cannot be blank.')

        data["field_data"] = ujson.dumps({
            '': {'text': 'Python', 'order': '1'},
            'java': {'text': 'Java', 'order': '2'},
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, "'value' cannot be blank.")

        data["field_data"] = ujson.dumps({
            'python': {'text': 'Python', 'order': 1},
            'java': {'text': 'Java', 'order': '2'},
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data["order"] is not a string')

        data["field_data"] = ujson.dumps({})
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'Field must have at least one choice.')

        data["field_data"] = ujson.dumps({
            'python': {'text': 'Python', 'order': '1'},
            'java': {'text': 'Java', 'order': '2'},
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_success(result)

    def test_not_realm_admin(self) -> None:
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/realm/profile_fields")
        self.assert_json_error(result, u'Must be an organization administrator')
        result = self.client_delete("/json/realm/profile_fields/1")
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_delete(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        field = CustomProfileField.objects.get(name="Phone number", realm=realm)
        result = self.client_delete("/json/realm/profile_fields/100")
        self.assert_json_error(result, 'Field id 100 not found.')

        self.assertTrue(self.custom_field_exists_in_realm(field.id))
        result = self.client_delete(
            "/json/realm/profile_fields/{}".format(field.id))
        self.assert_json_success(result)
        self.assertFalse(self.custom_field_exists_in_realm(field.id))

    def test_update(self) -> None:
        self.login(self.example_email("iago"))
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

        field = CustomProfileField.objects.get(name="Phone number", realm=realm)

        self.assertEqual(CustomProfileField.objects.count(), self.original_count)
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'New phone number',
                  'field_type': CustomProfileField.SHORT_TEXT})
        self.assert_json_success(result)
        field = CustomProfileField.objects.get(id=field.id, realm=realm)
        self.assertEqual(CustomProfileField.objects.count(), self.original_count)
        self.assertEqual(field.name, 'New phone number')
        self.assertIs(field.hint, '')
        self.assertEqual(field.field_type, CustomProfileField.SHORT_TEXT)

        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': '*' * 41,
                  'field_type': CustomProfileField.SHORT_TEXT})
        msg = "name is too long (limit: 40 characters)"
        self.assert_json_error(result, msg)

        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'New phone number',
                  'hint': '*' * 81,
                  'field_type': CustomProfileField.SHORT_TEXT})
        msg = "hint is too long (limit: 80 characters)"
        self.assert_json_error(result, msg)

        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'New phone number',
                  'hint': 'New contact number',
                  'field_type': CustomProfileField.SHORT_TEXT})
        self.assert_json_success(result)

        field = CustomProfileField.objects.get(id=field.id, realm=realm)
        self.assertEqual(CustomProfileField.objects.count(), self.original_count)
        self.assertEqual(field.name, 'New phone number')
        self.assertEqual(field.hint, 'New contact number')
        self.assertEqual(field.field_type, CustomProfileField.SHORT_TEXT)

        field = CustomProfileField.objects.get(name="Favorite editor", realm=realm)
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'Favorite editor',
                  'field_data': 'invalid'})
        self.assert_json_error(result, "Bad value for 'field_data': invalid")

        field_data = ujson.dumps({
            'vim': 'Vim',
            'emacs': {'order': '2', 'text': 'Emacs'},
        })
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'Favorite editor',
                  'field_data': field_data})
        self.assert_json_error(result, "field_data is not a dict")

        field_data = ujson.dumps({
            'vim': {'order': '1', 'text': 'Vim'},
            'emacs': {'order': '2', 'text': 'Emacs'},
            'notepad': {'order': '3', 'text': 'Notepad'},
        })
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'Favorite editor',
                  'field_data': field_data})
        self.assert_json_success(result)

    def test_update_is_aware_of_uniqueness(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        field_1 = try_add_realm_custom_profile_field(realm, u"Phone",
                                                     CustomProfileField.SHORT_TEXT)

        field_2 = try_add_realm_custom_profile_field(realm, u"Phone 1",
                                                     CustomProfileField.SHORT_TEXT)

        self.assertTrue(self.custom_field_exists_in_realm(field_1.id))
        self.assertTrue(self.custom_field_exists_in_realm(field_2.id))
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field_2.id),
            info={'name': 'Phone', 'field_type': CustomProfileField.SHORT_TEXT})
        self.assert_json_error(
            result, u'A field with that name already exists.')

    def assert_error_update_invalid_value(self, field_name: str, new_value: object, error_msg: str) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        field = CustomProfileField.objects.get(name=field_name, realm=realm)

        # Update value of field
        result = self.client_patch("/json/users/me/profile_data",
                                   {'data': ujson.dumps([{"id": field.id, "value": new_value}])})
        self.assert_json_error(result, error_msg)

    def test_reorder(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        order = (
            CustomProfileField.objects.filter(realm=realm)
            .order_by('-order')
            .values_list('order', flat=True)
        )
        result = self.client_patch("/json/realm/profile_fields",
                                   info={'order': ujson.dumps(order)})
        self.assert_json_success(result)
        fields = CustomProfileField.objects.filter(realm=realm).order_by('order')
        for field in fields:
            self.assertEqual(field.id, order[field.order])

    def test_reorder_duplicates(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        order = (
            CustomProfileField.objects.filter(realm=realm)
            .order_by('-order')
            .values_list('order', flat=True)
        )
        order = list(order)
        order.append(4)
        result = self.client_patch("/json/realm/profile_fields",
                                   info={'order': ujson.dumps(order)})
        self.assert_json_success(result)
        fields = CustomProfileField.objects.filter(realm=realm).order_by('order')
        for field in fields:
            self.assertEqual(field.id, order[field.order])

    def test_reorder_unauthorized(self) -> None:
        self.login(self.example_email("hamlet"))
        realm = get_realm('zulip')
        order = (
            CustomProfileField.objects.filter(realm=realm)
            .order_by('-order')
            .values_list('order', flat=True)
        )
        result = self.client_patch("/json/realm/profile_fields",
                                   info={'order': ujson.dumps(order)})
        self.assert_json_error(result, "Must be an organization administrator")

    def test_reorder_invalid(self) -> None:
        self.login(self.example_email("iago"))
        order = [100, 200, 300]
        result = self.client_patch("/json/realm/profile_fields",
                                   info={'order': ujson.dumps(order)})
        self.assert_json_error(
            result, u'Invalid order mapping.')
        order = [1, 2]
        result = self.client_patch("/json/realm/profile_fields",
                                   info={'order': ujson.dumps(order)})
        self.assert_json_error(
            result, u'Invalid order mapping.')

    def test_update_invalid_field(self) -> None:
        self.login(self.example_email("iago"))
        data = [{'id': 1234, 'value': '12'}]
        result = self.client_patch("/json/users/me/profile_data", {
            'data': ujson.dumps(data)
        })
        self.assert_json_error(result,
                               u"Field id 1234 not found.")

    def test_delete_field_value(self) -> None:
        iago = self.example_user("iago")
        self.login(iago.email)
        realm = get_realm("zulip")

        invalid_field_id = 1234
        result = self.client_delete("/json/users/me/profile_data", {
            'data': ujson.dumps([invalid_field_id])
        })
        self.assert_json_error(result,
                               u'Field id %d not found.' % (invalid_field_id))

        field = CustomProfileField.objects.get(name="Mentor", realm=realm)
        data = [{'id': field.id,
                 'value': [self.example_user("aaron").id]}]  # type: List[Dict[str, Union[int, str, List[int]]]]
        do_update_user_custom_profile_data(iago, data)

        iago_value = CustomProfileFieldValue.objects.get(user_profile=iago, field=field)
        converter = field.FIELD_CONVERTERS[field.field_type]
        self.assertEqual([self.example_user("aaron").id], converter(iago_value.value))

        result = self.client_delete("/json/users/me/profile_data", {
            'data': ujson.dumps([field.id])
        })
        self.assert_json_success(result)

        # Don't throw an exception here
        result = self.client_delete("/json/users/me/profile_data", {
            'data': ujson.dumps([field.id])
        })
        self.assert_json_success(result)

    def test_update_invalid_short_text(self) -> None:
        field_name = "Phone number"
        self.assert_error_update_invalid_value(field_name, 't' * 201,
                                               u"{} is too long (limit: 50 characters)".format(field_name))

    def test_update_invalid_date(self) -> None:
        field_name = "Birthday"
        self.assert_error_update_invalid_value(field_name, u"a-b-c",
                                               u"{} is not a date".format(field_name))
        self.assert_error_update_invalid_value(field_name, 123,
                                               u"{} is not a string".format(field_name))

    def test_update_invalid_url(self) -> None:
        field_name = "GitHub profile"
        self.assert_error_update_invalid_value(field_name, u"not URL",
                                               u"{} is not a URL".format(field_name))

    def test_update_invalid_user_field(self) -> None:
        field_name = "Mentor"
        invalid_user_id = 1000
        self.assert_error_update_invalid_value(field_name, [invalid_user_id],
                                               u"Invalid user ID: %d"
                                               % (invalid_user_id))

    def test_create_field_of_type_user(self) -> None:
        self.login(self.example_email("iago"))
        data = {"name": "Your mentor",
                "field_type": CustomProfileField.USER,
                }
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_success(result)

    def test_update_profile_data_successfully(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        fields = [
            ('Phone number', '*short* text data'),
            ('Biography', '~~short~~ **long** text data'),
            ('Favorite food', 'long short text data'),
            ('Favorite editor', 'vim'),
            ('Birthday', '1909-3-5'),
            ('GitHub profile', 'https://github.com/ABC'),
            ('Mentor', [self.example_user("cordelia").id]),
        ]

        data = []
        for i, field_value in enumerate(fields):
            name, value = field_value
            field = CustomProfileField.objects.get(name=name, realm=realm)
            data.append({
                'id': field.id,
                'value': value,
                'field': field,
            })

        # Update value of field
        result = self.client_patch("/json/users/me/profile_data",
                                   {'data': ujson.dumps(data)})
        self.assert_json_success(result)

        iago = self.example_user('iago')
        expected_value = {f['id']: f['value'] for f in data}
        expected_rendered_value = {}  # type: Dict[Union[int, float, str, None], Union[str, None]]
        for f in data:
            if f['field'].is_renderable():
                expected_rendered_value[f['id']] = bugdown_convert(f['value'])
            else:
                expected_rendered_value[f['id']] = None

        for field_dict in iago.profile_data:
            self.assertEqual(field_dict['value'], expected_value[field_dict['id']])
            self.assertEqual(field_dict['rendered_value'], expected_rendered_value[field_dict['id']])
            for k in ['id', 'type', 'name', 'field_data']:
                self.assertIn(k, field_dict)

        # Update value of one field.
        field = CustomProfileField.objects.get(name='Biography', realm=realm)
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

    def test_update_invalid_choice_field(self) -> None:
        field_name = "Favorite editor"
        self.assert_error_update_invalid_value(field_name, "foobar",
                                               "'foobar' is not a valid choice for '{}'.".format(field_name))

    def test_update_choice_field_successfully(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        field = CustomProfileField.objects.get(name='Favorite editor', realm=realm)
        data = [{
            'id': field.id,
            'value': 'emacs',
        }]

        result = self.client_patch("/json/users/me/profile_data",
                                   {'data': ujson.dumps(data)})
        self.assert_json_success(result)

    def test_delete_internals(self) -> None:
        user_profile = self.example_user('iago')
        realm = user_profile.realm
        field = CustomProfileField.objects.get(name="Phone number", realm=realm)
        data = [{'id': field.id, 'value': u'123456'}]  # type: List[Dict[str, Union[int, str, List[int]]]]
        do_update_user_custom_profile_data(user_profile, data)

        self.assertTrue(self.custom_field_exists_in_realm(field.id))
        self.assertEqual(user_profile.customprofilefieldvalue_set.count(), self.original_count)

        do_remove_realm_custom_profile_field(realm, field)

        self.assertFalse(self.custom_field_exists_in_realm(field.id))
        self.assertEqual(user_profile.customprofilefieldvalue_set.count(), self.original_count - 1)

    def test_null_value_and_rendered_value(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm("zulip")

        quote = try_add_realm_custom_profile_field(
            realm=realm,
            name="Quote",
            hint="Saying or phrase which you known for.",
            field_type=CustomProfileField.SHORT_TEXT
        )

        iago = self.example_user("iago")
        iago_profile_quote = iago.profile_data[-1]
        value = iago_profile_quote["value"]
        rendered_value = iago_profile_quote["rendered_value"]
        self.assertIsNone(value)
        self.assertIsNone(rendered_value)

        update_dict = {
            "id": quote.id,
            "value": "***beware*** of jealousy..."
        }
        do_update_user_custom_profile_data(iago, [update_dict])

        iago_profile_quote = self.example_user("iago").profile_data[-1]
        value = iago_profile_quote["value"]
        rendered_value = iago_profile_quote["rendered_value"]
        self.assertIsNotNone(value)
        self.assertIsNotNone(rendered_value)
        self.assertEqual("<p><strong><em>beware</em></strong> of jealousy...</p>", rendered_value)
