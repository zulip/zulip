from django.test import TestCase
from unittest.mock import patch

from zerver.models import Realm, CustomProfileField
from zerver.lib.custom_profile_fields import try_add_realm_custom_profile_field

class TestTryAddRealmCustomProfileField(TestCase):
    def setUp(self):
        # Set up a Realm instance to be used in all tests.
        self.realm = Realm.objects.create(name="Test Realm", string_id="testrealm")
        self.field_type = CustomProfileField.PERSONAL

    @patch('zerver.lib.custom_profile_fields.notify_realm_custom_profile_fields')
    def test_add_field_with_valid_name_and_hint(self, mock_notify):
        """
        Test adding a field with valid name and hint.
        Ensures that the function correctly handles valid inputs and that the
        notification function is triggered.
        """
        result = try_add_realm_custom_profile_field(
            realm=self.realm,
            field_type=self.field_type,
            name="Test Name",
            hint="Test Hint",
            required=True
        )

        self.assertIsInstance(result, CustomProfileField)
        self.assertEqual(result.name, "Test Name")
        self.assertEqual(result.hint, "Test Hint")
        self.assertTrue(result.required)
        mock_notify.assert_called_once_with(self.realm)

    @patch('zerver.lib.custom_profile_fields.notify_realm_custom_profile_fields')
    def test_add_field_with_empty_name(self, mock_notify):
        """
        Test adding a field with an empty name.
        Verifies that the function can handle an empty string for the name parameter
        and that the field is created with an empty name.
        """
        result = try_add_realm_custom_profile_field(
            realm=self.realm,
            field_type=self.field_type,
            name="",
            hint="Test Hint",
            required=False
        )

        self.assertIsInstance(result, CustomProfileField)
        self.assertEqual(result.name, "")
        self.assertEqual(result.hint, "Test Hint")
        self.assertFalse(result.required)
        mock_notify.assert_called_once_with(self.realm)

    @patch('zerver.lib.custom_profile_fields.notify_realm_custom_profile_fields')
    def test_add_field_with_none_name_and_hint(self, mock_notify):
        """
        Test the behavior when both name and hint are None.
        Checks if the function defaults to an empty string for name and None for hint correctly.
        """
        result = try_add_realm_custom_profile_field(
            realm=self.realm,
            field_type=self.field_type,
            name=None,
            hint=None,
            required=None
        )

        self.assertIsInstance(result, CustomProfileField)
        self.assertEqual(result.name, "")
        self.assertIsNone(result.hint)
        self.assertFalse(result.required)
        mock_notify.assert_called_once_with(self.realm)

    @patch('zerver.lib.custom_profile_fields.notify_realm_custom_profile_fields')
    def test_add_field_with_invalid_required_value(self, mock_notify):
        """
        Test the addition of a field with `required=None`.
        This tests the `required` parameter defaults to False if None is passed.
        """
        result = try_add_realm_custom_profile_field(
            realm=self.realm,
            field_type=self.field_type,
            name="cliff",
            hint="cc",
            required=None
        )

        self.assertIsInstance(result, CustomProfileField)
        self.assertEqual(result.name, "cliff")
        self.assertEqual(result.hint, "cc")
        self.assertFalse(result.required)
        mock_notify.assert_called_once_with(self.realm)

    @patch('zerver.lib.custom_profile_fields.notify_realm_custom_profile_fields')
    def test_add_field_without_displaying_in_profile_summary(self, mock_notify):
        """
        Test adding a field with `display_in_profile_summary=False`.
        Verifies that the field is created correctly without displaying in the profile summary.
        """
        result = try_add_realm_custom_profile_field(
            realm=self.realm,
            field_type=self.field_type,
            name="ethan",
            hint="ewoj",
            display_in_profile_summary=False,
            required=True
        )

        self.assertIsInstance(result, CustomProfileField)
        self.assertEqual(result.name, "ethan")
        self.assertEqual(result.hint, "ewoj")
        self.assertFalse(result.display_in_profile_summary)
        self.assertTrue(result.required)
        mock_notify.assert_called_once_with(self.realm)
