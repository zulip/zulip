from typing import Any, Dict, List, Union
from unittest import mock

import orjson

from zerver.lib.actions import (
    do_remove_realm_custom_profile_field,
    do_update_user_custom_profile_data_if_changed,
    try_add_realm_custom_profile_field,
    try_reorder_realm_custom_profile_fields,
)
from zerver.lib.external_accounts import DEFAULT_EXTERNAL_ACCOUNTS
from zerver.lib.markdown import markdown_convert
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import queries_captured
from zerver.models import (
    CustomProfileField,
    CustomProfileFieldValue,
    custom_profile_fields_for_realm,
    get_realm,
)


class CustomProfileFieldTestCase(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm("zulip")
        self.original_count = len(custom_profile_fields_for_realm(self.realm.id))

    def custom_field_exists_in_realm(self, field_id: int) -> bool:
        fields = custom_profile_fields_for_realm(self.realm.id)
        field_ids = [field.id for field in fields]
        return (field_id in field_ids)

class CreateCustomProfileFieldTest(CustomProfileFieldTestCase):
    def test_create(self) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        data: Dict[str, Any] = {"name": "Phone", "field_type": "text id"}
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'Argument "field_type" is not valid JSON.')

        data["name"] = ""
        data["field_type"] = 100
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'Label cannot be blank.')

        data["name"] = "*" * 41
        data["field_type"] = 100
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'name is too long (limit: 40 characters)')

        data["name"] = "Phone"
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'Invalid field type.')

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

        data["name"] = "Name "
        data["hint"] = "Some name"
        data["field_type"] = CustomProfileField.SHORT_TEXT
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_success(result)

        field = CustomProfileField.objects.get(name="Name", realm=realm)
        self.assertEqual(field.id, field.order)

        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result,
                               'A field with that label already exists.')

    def test_create_choice_field(self) -> None:
        self.login('iago')
        data: Dict[str, Union[str, int]] = {}
        data["name"] = "Favorite programming language"
        data["field_type"] = CustomProfileField.CHOICE

        data['field_data'] = 'invalid'
        result = self.client_post("/json/realm/profile_fields", info=data)
        error_msg = "Bad value for 'field_data': invalid"
        self.assert_json_error(result, error_msg)

        data["field_data"] = orjson.dumps({
            'python': ['1'],
            'java': ['2'],
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data is not a dict')

        data["field_data"] = orjson.dumps({
            'python': {'text': 'Python'},
            'java': {'text': 'Java'},
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, "order key is missing from field_data")

        data["field_data"] = orjson.dumps({
            'python': {'text': 'Python', 'order': ''},
            'java': {'text': 'Java', 'order': '2'},
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data["order"] cannot be blank.')

        data["field_data"] = orjson.dumps({
            '': {'text': 'Python', 'order': '1'},
            'java': {'text': 'Java', 'order': '2'},
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, "'value' cannot be blank.")

        data["field_data"] = orjson.dumps({
            'python': {'text': 'Python', 'order': 1},
            'java': {'text': 'Java', 'order': '2'},
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data["order"] is not a string')

        data["field_data"] = orjson.dumps({}).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'Field must have at least one choice.')

        data["field_data"] = orjson.dumps({
            'python': {'text': 'Python', 'order': '1'},
            'java': {'text': 'Java', 'order': '2'},
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_success(result)

    def test_create_default_external_account_field(self) -> None:
        self.login('iago')
        realm = get_realm("zulip")
        field_type: int = CustomProfileField.EXTERNAL_ACCOUNT
        field_data: str = orjson.dumps({
            'subtype': 'twitter',
        }).decode()
        invalid_field_name: str = "Not required field name"
        invalid_field_hint: str = "Not required field hint"

        result = self.client_post("/json/realm/profile_fields",
                                  info=dict(
                                      field_type=field_type,
                                      field_data=field_data,
                                      hint=invalid_field_hint,
                                      name=invalid_field_name,
                                  ))
        self.assert_json_success(result)
        # Silently overwrite name and hint with values set in default fields dict
        # for default custom external account fields.
        with self.assertRaises(CustomProfileField.DoesNotExist):
            field = CustomProfileField.objects.get(name=invalid_field_name, realm=realm)
        # The field is created with 'Twitter' name as per values in default fields dict
        field = CustomProfileField.objects.get(name='Twitter')
        self.assertEqual(field.name, DEFAULT_EXTERNAL_ACCOUNTS['twitter']['name'])
        self.assertEqual(field.hint, DEFAULT_EXTERNAL_ACCOUNTS['twitter']['hint'])

        result = self.client_delete(f"/json/realm/profile_fields/{field.id}")
        self.assert_json_success(result)

        # Should also work without name or hint and only external field type and subtype data
        result = self.client_post("/json/realm/profile_fields",
                                  info=dict(field_type=field_type, field_data=field_data))
        self.assert_json_success(result)

        # Default external account field data cannot be updated
        field = CustomProfileField.objects.get(name="Twitter", realm=realm)
        result = self.client_patch(
            f"/json/realm/profile_fields/{field.id}",
            info={'name': 'Twitter username',
                  'field_type': CustomProfileField.EXTERNAL_ACCOUNT},
        )
        self.assert_json_error(result, 'Default custom field cannot be updated.')

        result = self.client_delete(f"/json/realm/profile_fields/{field.id}")
        self.assert_json_success(result)

    def test_create_external_account_field(self) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        data: Dict[str, Union[str, int, Dict[str, str]]] = {}
        data["name"] = "Twitter"
        data["field_type"] = CustomProfileField.EXTERNAL_ACCOUNT

        data['field_data'] = 'invalid'
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, "Bad value for 'field_data': invalid")

        data['field_data'] = orjson.dumps({}).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, "subtype key is missing from field_data")

        data["field_data"] = orjson.dumps({
            'subtype': '',
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data["subtype"] cannot be blank.')

        data["field_data"] = orjson.dumps({
            'subtype': '123',
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'Invalid external account type')

        non_default_external_account = 'linkedin'
        data["field_data"] = orjson.dumps({
            'subtype': non_default_external_account,
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'Invalid external account type')

        data["field_data"] = orjson.dumps({
            'subtype': 'twitter',
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_success(result)

        twitter_field = CustomProfileField.objects.get(name="Twitter", realm=realm)
        self.assertEqual(twitter_field.field_type, CustomProfileField.EXTERNAL_ACCOUNT)
        self.assertEqual(twitter_field.name, "Twitter")
        self.assertEqual(orjson.loads(twitter_field.field_data)['subtype'], 'twitter')

        data['name'] = 'Reddit'
        data["field_data"] = orjson.dumps({
            'subtype': 'custom',
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'Custom external account must define URL pattern')

        data["field_data"] = orjson.dumps({
            'subtype': 'custom',
            'url_pattern': 123,
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data["url_pattern"] is not a string')

        data["field_data"] = orjson.dumps({
            'subtype': 'custom',
            'url_pattern': 'invalid',
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'Malformed URL pattern.')

        data["field_data"] = orjson.dumps({
            'subtype': 'custom',
            'url_pattern': 'https://www.reddit.com/%(username)s/user/%(username)s',
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'Malformed URL pattern.')

        data["field_data"] = orjson.dumps({
            'subtype': 'custom',
            'url_pattern': 'reddit.com/%(username)s',
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data["url_pattern"] is not a URL')

        data["field_data"] = orjson.dumps({
            'subtype': 'custom',
            'url_pattern': 'https://www.reddit.com/user/%(username)s',
        }).decode()
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_success(result)

        custom_field = CustomProfileField.objects.get(name="Reddit", realm=realm)
        self.assertEqual(custom_field.field_type, CustomProfileField.EXTERNAL_ACCOUNT)
        self.assertEqual(custom_field.name, "Reddit")
        field_data = orjson.loads(custom_field.field_data)
        self.assertEqual(field_data['subtype'], 'custom')
        self.assertEqual(field_data['url_pattern'], 'https://www.reddit.com/user/%(username)s')

        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, "A field with that label already exists.")

    def test_create_field_of_type_user(self) -> None:
        self.login('iago')
        data = {"name": "Your mentor",
                "field_type": CustomProfileField.USER,
                }
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_success(result)

    def test_not_realm_admin(self) -> None:
        self.login('hamlet')
        result = self.client_post("/json/realm/profile_fields")
        self.assert_json_error(result, 'Must be an organization administrator')
        result = self.client_delete("/json/realm/profile_fields/1")
        self.assert_json_error(result, 'Must be an organization administrator')

class DeleteCustomProfileFieldTest(CustomProfileFieldTestCase):
    def test_delete(self) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        field = CustomProfileField.objects.get(name="Phone number", realm=realm)
        result = self.client_delete("/json/realm/profile_fields/100")
        self.assert_json_error(result, 'Field id 100 not found.')

        self.assertTrue(self.custom_field_exists_in_realm(field.id))
        result = self.client_delete(
            f"/json/realm/profile_fields/{field.id}")
        self.assert_json_success(result)
        self.assertFalse(self.custom_field_exists_in_realm(field.id))

    def test_delete_field_value(self) -> None:
        iago = self.example_user("iago")
        self.login_user(iago)
        realm = get_realm("zulip")

        invalid_field_id = 1234
        result = self.client_delete("/json/users/me/profile_data", {
            'data': orjson.dumps([invalid_field_id]).decode(),
        })
        self.assert_json_error(result,
                               f'Field id {invalid_field_id} not found.')

        field = CustomProfileField.objects.get(name="Mentor", realm=realm)
        data: List[Dict[str, Union[int, str, List[int]]]] = [
            {'id': field.id, 'value': [self.example_user("aaron").id]},
        ]
        do_update_user_custom_profile_data_if_changed(iago, data)

        iago_value = CustomProfileFieldValue.objects.get(user_profile=iago, field=field)
        converter = field.FIELD_CONVERTERS[field.field_type]
        self.assertEqual([self.example_user("aaron").id], converter(iago_value.value))

        result = self.client_delete("/json/users/me/profile_data", {
            'data': orjson.dumps([field.id]).decode(),
        })
        self.assert_json_success(result)

        # Don't throw an exception here
        result = self.client_delete("/json/users/me/profile_data", {
            'data': orjson.dumps([field.id]).decode(),
        })
        self.assert_json_success(result)

    def test_delete_internals(self) -> None:
        user_profile = self.example_user('iago')
        realm = user_profile.realm
        field = CustomProfileField.objects.get(name="Phone number", realm=realm)
        data: List[Dict[str, Union[int, str, List[int]]]] = [
            {'id': field.id, 'value': '123456'},
        ]
        do_update_user_custom_profile_data_if_changed(user_profile, data)

        self.assertTrue(self.custom_field_exists_in_realm(field.id))
        self.assertEqual(user_profile.customprofilefieldvalue_set.count(), self.original_count)

        do_remove_realm_custom_profile_field(realm, field)

        self.assertFalse(self.custom_field_exists_in_realm(field.id))
        self.assertEqual(user_profile.customprofilefieldvalue_set.count(), self.original_count - 1)

class UpdateCustomProfileFieldTest(CustomProfileFieldTestCase):
    def test_update(self) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        result = self.client_patch(
            "/json/realm/profile_fields/100",
            info={'name': 'Phone Number',
                  'field_type': CustomProfileField.SHORT_TEXT},
        )
        self.assert_json_error(result, 'Field id 100 not found.')

        field = CustomProfileField.objects.get(name="Phone number", realm=realm)
        result = self.client_patch(
            f"/json/realm/profile_fields/{field.id}",
            info={'name': '',
                  'field_type': CustomProfileField.SHORT_TEXT},
        )
        self.assert_json_error(result, 'Label cannot be blank.')

        self.assertEqual(CustomProfileField.objects.count(), self.original_count)
        result = self.client_patch(
            f"/json/realm/profile_fields/{field.id}",
            info={'name': 'New phone number',
                  'field_type': CustomProfileField.SHORT_TEXT})
        self.assert_json_success(result)
        field = CustomProfileField.objects.get(id=field.id, realm=realm)
        self.assertEqual(CustomProfileField.objects.count(), self.original_count)
        self.assertEqual(field.name, 'New phone number')
        self.assertIs(field.hint, '')
        self.assertEqual(field.field_type, CustomProfileField.SHORT_TEXT)

        result = self.client_patch(
            f"/json/realm/profile_fields/{field.id}",
            info={'name': '*' * 41,
                  'field_type': CustomProfileField.SHORT_TEXT})
        msg = "name is too long (limit: 40 characters)"
        self.assert_json_error(result, msg)

        result = self.client_patch(
            f"/json/realm/profile_fields/{field.id}",
            info={'name': 'New phone number',
                  'hint': '*' * 81,
                  'field_type': CustomProfileField.SHORT_TEXT})
        msg = "hint is too long (limit: 80 characters)"
        self.assert_json_error(result, msg)

        result = self.client_patch(
            f"/json/realm/profile_fields/{field.id}",
            info={'name': 'New phone number',
                  'hint': 'New contact number',
                  'field_type': CustomProfileField.SHORT_TEXT})
        self.assert_json_success(result)

        field = CustomProfileField.objects.get(id=field.id, realm=realm)
        self.assertEqual(CustomProfileField.objects.count(), self.original_count)
        self.assertEqual(field.name, 'New phone number')
        self.assertEqual(field.hint, 'New contact number')
        self.assertEqual(field.field_type, CustomProfileField.SHORT_TEXT)

        result = self.client_patch(
            f"/json/realm/profile_fields/{field.id}",
            info={'name': 'Name ',
                  'field_type': CustomProfileField.SHORT_TEXT},
        )
        self.assert_json_success(result)
        field.refresh_from_db()
        self.assertEqual(field.name, 'Name')

        field = CustomProfileField.objects.get(name="Favorite editor", realm=realm)
        result = self.client_patch(
            f"/json/realm/profile_fields/{field.id}",
            info={'name': 'Favorite editor',
                  'field_data': 'invalid'})
        self.assert_json_error(result, "Bad value for 'field_data': invalid")

        field_data = orjson.dumps({
            'vim': 'Vim',
            'emacs': {'order': '2', 'text': 'Emacs'},
        }).decode()
        result = self.client_patch(
            f"/json/realm/profile_fields/{field.id}",
            info={'name': 'Favorite editor',
                  'field_data': field_data})
        self.assert_json_error(result, "field_data is not a dict")

        field_data = orjson.dumps({
            'vim': {'order': '1', 'text': 'Vim'},
            'emacs': {'order': '2', 'text': 'Emacs'},
            'notepad': {'order': '3', 'text': 'Notepad'},
        }).decode()
        result = self.client_patch(
            f"/json/realm/profile_fields/{field.id}",
            info={'name': 'Favorite editor',
                  'field_data': field_data})
        self.assert_json_success(result)

    def test_update_is_aware_of_uniqueness(self) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        field_1 = try_add_realm_custom_profile_field(realm, "Phone",
                                                     CustomProfileField.SHORT_TEXT)

        field_2 = try_add_realm_custom_profile_field(realm, "Phone 1",
                                                     CustomProfileField.SHORT_TEXT)

        self.assertTrue(self.custom_field_exists_in_realm(field_1.id))
        self.assertTrue(self.custom_field_exists_in_realm(field_2.id))
        result = self.client_patch(
            f"/json/realm/profile_fields/{field_2.id}",
            info={'name': 'Phone', 'field_type': CustomProfileField.SHORT_TEXT})
        self.assert_json_error(
            result, 'A field with that label already exists.')

    def assert_error_update_invalid_value(self, field_name: str, new_value: object, error_msg: str) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        field = CustomProfileField.objects.get(name=field_name, realm=realm)

        # Update value of field
        result = self.client_patch("/json/users/me/profile_data",
                                   {'data': orjson.dumps([{"id": field.id, "value": new_value}]).decode()})
        self.assert_json_error(result, error_msg)

    def test_update_invalid_field(self) -> None:
        self.login('iago')
        data = [{'id': 1234, 'value': '12'}]
        result = self.client_patch("/json/users/me/profile_data", {
            'data': orjson.dumps(data).decode(),
        })
        self.assert_json_error(result,
                               "Field id 1234 not found.")

    def test_update_invalid_short_text(self) -> None:
        field_name = "Phone number"
        self.assert_error_update_invalid_value(field_name, 't' * 201,
                                               f"{field_name} is too long (limit: 50 characters)")

    def test_update_invalid_date(self) -> None:
        field_name = "Birthday"
        self.assert_error_update_invalid_value(field_name, "a-b-c",
                                               f"{field_name} is not a date")
        self.assert_error_update_invalid_value(field_name, "1909-3-5",
                                               f"{field_name} is not a date")
        self.assert_error_update_invalid_value(field_name, 123,
                                               f"{field_name} is not a string")

    def test_update_invalid_url(self) -> None:
        field_name = "Favorite website"
        self.assert_error_update_invalid_value(field_name, "not URL",
                                               f"{field_name} is not a URL")

    def test_update_invalid_user_field(self) -> None:
        field_name = "Mentor"
        invalid_user_id = 1000
        self.assert_error_update_invalid_value(field_name, [invalid_user_id],
                                               f"Invalid user ID: {invalid_user_id}")

    def test_update_profile_data_successfully(self) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        fields = [
            ('Phone number', '*short* text data'),
            ('Biography', '~~short~~ **long** text data'),
            ('Favorite food', 'long short text data'),
            ('Favorite editor', 'vim'),
            ('Birthday', '1909-03-05'),
            ('Favorite website', 'https://zulip.com'),
            ('Mentor', [self.example_user("cordelia").id]),
            ('GitHub', 'zulip-mobile'),
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
        result = self.client_patch(
            "/json/users/me/profile_data",
            {"data": orjson.dumps([{"id": f["id"], "value": f["value"]} for f in data]).decode()},
        )
        self.assert_json_success(result)

        iago = self.example_user('iago')
        expected_value = {f['id']: f['value'] for f in data}
        expected_rendered_value: Dict[Union[int, float, str, None], Union[str, None]] = {}
        for f in data:
            if f['field'].is_renderable():
                expected_rendered_value[f['id']] = markdown_convert(f['value'])
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
                                   {'data': orjson.dumps(data).decode()})
        self.assert_json_success(result)
        for field_dict in iago.profile_data:
            if field_dict['id'] == field.id:
                self.assertEqual(field_dict['value'], 'foobar')

    def test_update_invalid_choice_field(self) -> None:
        field_name = "Favorite editor"
        self.assert_error_update_invalid_value(field_name, "foobar",
                                               f"'foobar' is not a valid choice for '{field_name}'.")

    def test_update_choice_field_successfully(self) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        field = CustomProfileField.objects.get(name='Favorite editor', realm=realm)
        data = [{
            'id': field.id,
            'value': 'emacs',
        }]

        result = self.client_patch("/json/users/me/profile_data",
                                   {'data': orjson.dumps(data).decode()})
        self.assert_json_success(result)

    def test_null_value_and_rendered_value(self) -> None:
        self.login('iago')
        realm = get_realm("zulip")

        quote = try_add_realm_custom_profile_field(
            realm=realm,
            name="Quote",
            hint="Saying or phrase which you known for.",
            field_type=CustomProfileField.SHORT_TEXT,
        )

        iago = self.example_user("iago")
        iago_profile_quote = iago.profile_data[-1]
        value = iago_profile_quote["value"]
        rendered_value = iago_profile_quote["rendered_value"]
        self.assertIsNone(value)
        self.assertIsNone(rendered_value)

        update_dict: Dict[str, Union[int, str, List[int]]] = {
            "id": quote.id,
            "value": "***beware*** of jealousy...",
        }
        do_update_user_custom_profile_data_if_changed(iago, [update_dict])

        iago_profile_quote = self.example_user("iago").profile_data[-1]
        value = iago_profile_quote["value"]
        rendered_value = iago_profile_quote["rendered_value"]
        self.assertIsNotNone(value)
        self.assertIsNotNone(rendered_value)
        self.assertEqual("<p><strong><em>beware</em></strong> of jealousy...</p>", rendered_value)

    def test_do_update_value_not_changed(self) -> None:
        iago = self.example_user("iago")
        self.login_user(iago)
        realm = get_realm("zulip")

        # Set field value:
        field = CustomProfileField.objects.get(name="Mentor", realm=realm)
        data: List[Dict[str, Union[int, str, List[int]]]] = [
            {'id': field.id, 'value': [self.example_user("aaron").id]},
        ]
        do_update_user_custom_profile_data_if_changed(iago, data)

        with mock.patch("zerver.lib.actions.notify_user_update_custom_profile_data") as mock_notify:
            # Attempting to "update" the field value, when it wouldn't actually change,
            # if always_notify is disabled, shouldn't trigger notify.
            do_update_user_custom_profile_data_if_changed(iago, data)
            mock_notify.assert_not_called()

class ListCustomProfileFieldTest(CustomProfileFieldTestCase):
    def test_list(self) -> None:
        self.login('iago')
        result = self.client_get("/json/realm/profile_fields")
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        content = result.json()
        self.assertEqual(len(content["custom_fields"]), self.original_count)

    def test_list_order(self) -> None:
        self.login('iago')
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

    def test_get_custom_profile_fields_from_api(self) -> None:
        iago = self.example_user("iago")
        test_bot = self.create_test_bot("foo-bot", iago)
        self.login_user(iago)
        assert(test_bot)

        with queries_captured() as queries:
            response = self.client_get("/json/users", {"client_gravatar": "false", "include_custom_profile_fields": "true"})

        self.assertEqual(len(queries), 4)

        self.assertEqual(response.status_code, 200)
        raw_users_data = response.json()["members"]

        iago_raw_data = None
        test_bot_raw_data = None

        for user_dict in raw_users_data:
            if user_dict["user_id"] == iago.id:
                iago_raw_data = user_dict
                continue
            if user_dict["user_id"] == test_bot.id:
                test_bot_raw_data = user_dict
                continue

        if (not iago_raw_data) or (not test_bot_raw_data):
            raise AssertionError("Could not find required data from the response.")

        expected_keys_for_iago = {
            "delivery_email",
            "email", "user_id", "avatar_url", "avatar_version", "is_admin", "is_guest", "is_bot", "is_owner",
            "full_name", "timezone", "is_active", "date_joined", "profile_data"}
        self.assertEqual(set(iago_raw_data.keys()), expected_keys_for_iago)
        self.assertNotEqual(iago_raw_data["profile_data"], {})

        expected_keys_for_test_bot = {
            "delivery_email",
            "email", "user_id", "avatar_url", "avatar_version", "is_admin", "is_guest", "is_bot", "is_owner",
            "full_name", "timezone", "is_active", "date_joined", "bot_type", "bot_owner_id"}
        self.assertEqual(set(test_bot_raw_data.keys()), expected_keys_for_test_bot)
        self.assertEqual(test_bot_raw_data["bot_type"], 1)
        self.assertEqual(test_bot_raw_data["bot_owner_id"], iago_raw_data["user_id"])

        response = self.client_get("/json/users", {"client_gravatar": "false"})
        self.assertEqual(response.status_code, 200)
        raw_users_data = response.json()["members"]
        for user_dict in raw_users_data:
            with self.assertRaises(KeyError):
                user_dict["profile_data"]

    def test_get_custom_profile_fields_from_api_for_single_user(self) -> None:
        self.login('iago')
        expected_keys = {
            "result", "msg", "max_message_id", "user_id", "avatar_url",
            "full_name", "email", "is_bot", "is_admin", "is_owner", "profile_data",
            "avatar_version", "timezone", "delivery_email", "is_active", "is_guest",
            "date_joined"}

        url = "/json/users/me"
        response = self.client_get(url)
        self.assertEqual(response.status_code, 200)
        raw_user_data = response.json()
        self.assertEqual(set(raw_user_data.keys()), expected_keys)


class ReorderCustomProfileFieldTest(CustomProfileFieldTestCase):
    def test_reorder(self) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        order = list(
            CustomProfileField.objects.filter(realm=realm)
            .order_by('-order')
            .values_list('order', flat=True)
        )
        result = self.client_patch("/json/realm/profile_fields",
                                   info={'order': orjson.dumps(order).decode()})
        self.assert_json_success(result)
        fields = CustomProfileField.objects.filter(realm=realm).order_by('order')
        for field in fields:
            self.assertEqual(field.id, order[field.order])

    def test_reorder_duplicates(self) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        order = list(
            CustomProfileField.objects.filter(realm=realm)
            .order_by('-order')
            .values_list('order', flat=True)
        )
        order.append(4)
        result = self.client_patch("/json/realm/profile_fields",
                                   info={'order': orjson.dumps(order).decode()})
        self.assert_json_success(result)
        fields = CustomProfileField.objects.filter(realm=realm).order_by('order')
        for field in fields:
            self.assertEqual(field.id, order[field.order])

    def test_reorder_unauthorized(self) -> None:
        self.login('hamlet')
        realm = get_realm('zulip')
        order = list(
            CustomProfileField.objects.filter(realm=realm)
            .order_by('-order')
            .values_list('order', flat=True)
        )
        result = self.client_patch("/json/realm/profile_fields",
                                   info={'order': orjson.dumps(order).decode()})
        self.assert_json_error(result, "Must be an organization administrator")

    def test_reorder_invalid(self) -> None:
        self.login('iago')
        order = [100, 200, 300]
        result = self.client_patch("/json/realm/profile_fields",
                                   info={'order': orjson.dumps(order).decode()})
        self.assert_json_error(
            result, 'Invalid order mapping.')
        order = [1, 2]
        result = self.client_patch("/json/realm/profile_fields",
                                   info={'order': orjson.dumps(order).decode()})
        self.assert_json_error(
            result, 'Invalid order mapping.')
