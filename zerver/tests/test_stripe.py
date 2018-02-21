import mock
import os
from typing import Any
import ujson

import stripe
from stripe.api_resources.list_object import ListObject

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Realm, UserProfile
from zilencer.lib.stripe import StripeError, save_stripe_token, catch_stripe_errors
from zilencer.models import Customer

fixture_data_file = open(os.path.join(os.path.dirname(__file__), '../fixtures/stripe.json'), 'r')
fixture_data = ujson.load(fixture_data_file)

def mock_list_sources(*args: Any, **kwargs: Any) -> ListObject:
    return stripe.util.convert_to_stripe_object(fixture_data["list_sources"])

def mock_create_source(*args: Any, **kwargs: Any) -> ListObject:
    return stripe.util.convert_to_stripe_object(fixture_data["create_source"])

def mock_create_customer(*args: Any, **kwargs: Any) -> ListObject:
    return stripe.util.convert_to_stripe_object(fixture_data["create_customer"])

def mock_retrieve_customer(*args: Any, **kwargs: Any) -> ListObject:
    return stripe.util.convert_to_stripe_object(fixture_data["retrieve_customer"])

class StripeTest(ZulipTestCase):
    def setUp(self) -> None:
        self.token = "token"
        self.user = self.example_user("iago")
        self.realm = self.user.realm

    @mock.patch("zilencer.lib.stripe.STRIPE_PUBLISHABLE_KEY", "stripe_publishable_key")
    @mock.patch("zilencer.lib.stripe.billing_logger.info")
    @mock.patch("stripe.api_resources.list_object.ListObject.create", side_effect=mock_create_source)
    @mock.patch("stripe.api_resources.list_object.ListObject.list", side_effect=mock_list_sources)
    @mock.patch("stripe.Customer.create", side_effect=mock_create_customer)
    @mock.patch("stripe.Customer.retrieve", side_effect=mock_retrieve_customer)
    @mock.patch("stripe.api_resources.card.Card.save")
    @mock.patch("stripe.api_resources.customer.Customer.save")
    def test_save_stripe_token(self, mock_save_customer: mock.Mock, mock_save_card: mock.Mock,
                               mock_retrieve_customer: mock.Mock, mock_create_customer: mock.Mock,
                               mock_list_sources: mock.Mock, mock_create_source: mock.Mock,
                               mock_billing_logger_info: mock.Mock) -> None:
        self.assertFalse(Customer.objects.filter(realm=self.realm))
        number_of_cards = save_stripe_token(self.user, self.token)
        self.assertEqual(number_of_cards, 1)
        description = "{} ({})".format(self.realm.name, self.realm.string_id)
        mock_create_customer.assert_called_once_with(description=description, source=self.token,
                                                     metadata={'string_id': self.realm.string_id})
        mock_list_sources.assert_called_once()
        mock_save_card.assert_called_once()
        mock_billing_logger_info.assert_called()
        customer_object = Customer.objects.get(realm=self.realm)

        # Add another card
        number_of_cards = save_stripe_token(self.user, self.token)
        # Note: customer.sources.list is mocked to return 2 cards all the time.
        self.assertEqual(number_of_cards, 2)
        mock_retrieve_customer.assert_called_once_with(customer_object.stripe_customer_id)
        create_source_metadata = {'added_user_id': self.user.id, 'added_user_email': self.user.email}
        mock_create_source.assert_called_once_with(metadata=create_source_metadata, source='token')
        mock_save_customer.assert_called_once()
        mock_billing_logger_info.assert_called()

    @mock.patch("zilencer.lib.stripe.STRIPE_PUBLISHABLE_KEY", "stripe_publishable_key")
    @mock.patch("zilencer.lib.stripe.billing_logger.error")
    def test_errors(self, mock_billing_logger_error: mock.Mock) -> None:
        @catch_stripe_errors
        def raise_invalid_request_error() -> None:
            raise stripe.error.InvalidRequestError("Request req_oJU621i6H6X4Ez: No such token: x",
                                                   None)
        with self.assertRaisesRegex(StripeError, "Something went wrong. Please try again or "):
            raise_invalid_request_error()
        mock_billing_logger_error.assert_called()

        @catch_stripe_errors
        def raise_card_error() -> None:
            error_message = "The card number is not a valid credit card number."
            json_body = {"error": {"message": error_message}}
            raise stripe.error.CardError(error_message, "number", "invalid_number",
                                         json_body=json_body)
        with self.assertRaisesRegex(StripeError,
                                    "The card number is not a valid credit card number."):
            raise_card_error()
        mock_billing_logger_error.assert_called()

        @catch_stripe_errors
        def raise_exception() -> None:
            raise Exception
        with self.assertRaises(Exception):
            raise_exception()
        mock_billing_logger_error.assert_called()

    @mock.patch("zilencer.views.STRIPE_PUBLISHABLE_KEY", "stripe_publishable_key")
    @mock.patch("zilencer.lib.stripe.STRIPE_PUBLISHABLE_KEY", "stripe_publishable_key")
    def test_billing_page_view_permissions(self) -> None:
        result = self.client_get("/billing/")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login?next=/billing/")

        self.login(self.example_email("hamlet"))
        result = self.client_get("/billing/")
        message = ("You should be an administrator of the organization {} to view this page."
                   .format(self.realm.name))
        self.assert_in_success_response([message], result)
        self.assert_not_in_success_response(["stripe_publishable_key"], result)

        self.login(self.example_email("iago"))
        result = self.client_get("/billing/")
        self.assert_not_in_success_response([message], result)
        self.assert_in_success_response(["stripe_publishable_key"], result)

    def test_billing_page_view_add_card(self) -> None:
        self.login(self.example_email("iago"))

        with mock.patch("zilencer.views.save_stripe_token", side_effect=StripeError("Stripe error")):
            result = self.client_post("/billing/", {"stripeToken": self.token})
            self.assert_in_success_response(["Stripe error"], result)
            self.assert_not_in_success_response(["The card has been saved successfully"], result)

        with mock.patch("zilencer.views.save_stripe_token", return_value=1), \
                mock.patch("zilencer.views.count_stripe_cards", return_value=1):
            result = self.client_post("/billing/", {"stripeToken": self.token})
            self.assert_in_success_response(["The card has been saved successfully"], result)

        # Add another card
        with mock.patch("zilencer.views.save_stripe_token", return_value=2), \
                mock.patch("zilencer.views.count_stripe_cards", return_value=2):
            result = self.client_post("/billing/", {"stripeToken": self.token})
            self.assert_in_success_response(["The card has been saved successfully"], result)
