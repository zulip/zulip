# See https://zulip.readthedocs.io/en/latest/testing/mypy.html#mypy-stubs-for-third-party-modules
# for notes on how we manage mypy stubs.

from typing import Any, Dict, List, Optional, Union

import stripe.api_requestor as api_requestor
import stripe.error as error
import stripe.util as util
from stripe.api_resources.list_object import SubscriptionListObject
from stripe.checkout import Session
from typing_extensions import Literal

api_key: Optional[str]

class InvoiceSettings:
    custom_field: List[str]
    default_payment_method: Optional[PaymentMethod]
    footer: str

class Customer:
    default_source: Union[Card, Source]
    created: int
    id: str
    source: str
    sources: List[Union[Card, Source]]
    subscriptions: SubscriptionListObject
    coupon: str
    balance: int
    email: str
    description: str
    discount: Optional[Discount]
    metadata: Dict[str, str]
    invoice_settings: InvoiceSettings
    @staticmethod
    def retrieve(customer_id: str = ..., expand: Optional[List[str]] = ...) -> Customer: ...
    @staticmethod
    def create(
        description: str = ...,
        email: str = ...,
        metadata: Dict[str, Any] = ...,
        payment_method: Optional[str] = ...,
        coupon: Optional[str] = ...,
    ) -> Customer: ...
    @staticmethod
    def modify(customer_id: str, invoice_settings: Dict[str, Any]) -> Customer:
        pass
    @staticmethod
    def save(customer: Customer) -> Customer: ...
    @staticmethod
    def delete_discount(customer: Customer) -> None: ...
    @staticmethod
    def list(limit: Optional[int] = ...) -> List[Customer]: ...
    @staticmethod
    def create_balance_transaction(
        customer_id: str, amount: int, currency: str, description: str
    ) -> None: ...
    def refresh(self, customer: Customer) -> Customer: ...

class Invoice:
    id: str
    auto_advance: bool
    amount_due: int
    collection_method: str
    billing_reason: str
    default_source: Source
    due_date: int
    lines: List[InvoiceLineItem]
    status: str
    status_transitions: Any
    total: int
    @staticmethod
    def upcoming(
        customer: str = ...,
        subscription: str = ...,
        subscription_items: List[Dict[str, Union[str, int]]] = ...,
    ) -> Invoice: ...
    @staticmethod
    def list(
        collection_method: str = ...,
        customer: str = ...,
        status: str = ...,
        limit: Optional[int] = ...,
        starting_after: Optional[Invoice] = ...,
    ) -> List[Invoice]: ...
    @staticmethod
    def create(
        auto_advance: bool = ...,
        collection_method: str = ...,
        customer: str = ...,
        days_until_due: Optional[int] = ...,
        statement_descriptor: str = ...,
    ) -> Invoice: ...
    @staticmethod
    def finalize_invoice(invoice: Invoice) -> Invoice: ...
    @staticmethod
    def pay(invoice: Invoice, paid_out_of_band: bool = False) -> Invoice: ...
    @staticmethod
    def void_invoice(id: str) -> None: ...
    def get(self, key: str) -> Any: ...
    def refresh(self, invoice: Invoice) -> Invoice: ...

class Subscription:
    created: int
    status: str
    canceled_at: int
    cancel_at_period_end: bool
    days_until_due: Optional[int]
    proration_date: int
    quantity: int
    @staticmethod
    def create(
        customer: str = ...,
        collection_method: str = ...,
        days_until_due: Optional[int] = ...,
        items: List[Dict[str, Any]] = ...,
        prorate: bool = ...,
        tax_percent: float = ...,
    ) -> Subscription: ...
    @staticmethod
    def save(subscription: Subscription, idempotency_key: str = ...) -> Subscription: ...
    @staticmethod
    def delete(subscription: Subscription) -> Subscription: ...
    @staticmethod
    def retrieve(subscription_id: str) -> Subscription: ...

class Source:
    id: str
    object: str
    type: str

class Card:
    id: str
    brand: str
    last4: str
    object: str

class Plan:
    id: str
    @staticmethod
    def create(
        currency: str = ...,
        interval: str = ...,
        product: str = ...,
        amount: int = ...,
        billing_scheme: str = ...,
        nickname: str = ...,
        usage_type: str = ...,
    ) -> Plan: ...

class Product:
    id: str
    @staticmethod
    def create(
        name: str = ..., type: str = ..., statement_descriptor: str = ..., unit_label: str = ...
    ) -> Product: ...

class Discount:
    coupon: Coupon

class Coupon:
    id: str
    percent_off: int
    @staticmethod
    def create(duration: str = ..., name: str = ..., percent_off: int = ...) -> Coupon: ...

class Token:
    id: str
    @staticmethod
    def create(card: Dict[str, Any]) -> Token: ...

class Charge:
    amount: int
    description: str
    failure_code: str
    receipt_email: str
    source: Source
    statement_descriptor: str
    payment_method_details: PaymentMethod
    @staticmethod
    def list(customer: Optional[str]) -> List[Charge]: ...
    @staticmethod
    def create(
        amount: int = ...,
        currency: str = ...,
        customer: str = ...,
        description: str = ...,
        receipt_email: str = ...,
        statement_descriptor: str = ...,
    ) -> Charge: ...

class InvoiceItem:
    @staticmethod
    def create(
        amount: int = ...,
        currency: str = ...,
        customer: str = ...,
        description: str = ...,
        discountable: bool = ...,
        period: Dict[str, int] = ...,
        quantity: int = ...,
        unit_amount: int = ...,
        idempotency_key: Optional[str] = ...,
    ) -> InvoiceItem: ...
    @staticmethod
    def list(customer: Optional[str]) -> List[InvoiceItem]: ...

class InvoiceLineItem:
    amount: int
    def get(self, key: str) -> Any: ...

class SetupIntent:
    id: str

    customer: str
    metadata: Dict[str, Any]
    payment_method: str
    payment_method_types: List[str]
    usage: str
    @staticmethod
    def create(
        confirm: bool = ...,
        usage: str = ...,
        customer: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payment_method: Optional[str] = None,
        payment_method_types: List[str] = ...,
    ) -> SetupIntent: ...
    @staticmethod
    def list(limit: int = ...) -> List[SetupIntent]: ...
    @staticmethod
    def retrieve(setup_intent_id: str, expand: Optional[List[str]] = ...) -> SetupIntent: ...

PaymentIntentStatuses = Literal[
    "requires_payment_method",
    "requires_confirmation",
    "requires_action",
    "processing",
    "requires_capture",
    "canceled",
    "succeeded",
]

class LastPaymentError:
    def get(self, key: Literal["code", "message", "type", "param"]) -> Optional[str]: ...

class PaymentIntent:
    id: str
    amount: int
    charges: List[Charge]
    customer: str
    metadata: Dict[str, str]
    status: PaymentIntentStatuses
    last_payment_error: LastPaymentError
    @staticmethod
    def create(
        amount: int,
        currency: str,
        confirm: bool = ...,
        customer: Optional[str] = None,
        description: Optional[str] = None,
        payment_method: Optional[str] = None,
        off_session: Optional[bool] = None,
        receipt_email: Optional[str] = None,
        statement_descriptor: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentMethod: ...
    @staticmethod
    def confirm(
        payment_intent_id: str,
        payment_method: Optional[str] = None,
        off_session: Optional[bool] = None,
    ) -> PaymentIntent: ...
    @staticmethod
    def list(limit: int = ...) -> List[PaymentIntent]: ...
    @staticmethod
    def retrieve(payment_intent_id: str) -> PaymentIntent: ...

PaymentMethodTypes = Literal[
    "acss_debit",
    "afterpay_clearpay",
    "alipay",
    "au_becs_debit",
    "bacs_debit",
    "bancontact",
    "boleto",
    "card",
    "eps",
    "fpx",
    "giropay",
    "grabpay",
    "ideal",
    "oxxo",
    "p24",
    "sepa_debit",
    "sofort",
    "wechat_pay",
]

class PaymentMethod:
    id: str
    status: str
    card: Card
    type: PaymentMethodTypes
    @staticmethod
    def create(
        type: PaymentMethodTypes, card: Optional[Dict[str, Any]] = None
    ) -> PaymentMethod: ...
    @staticmethod
    def detach(payment_method_id: str) -> PaymentMethod: ...
    @staticmethod
    def list(customer: Customer, type: str, limit: int = ...) -> List[PaymentMethod]: ...

EventTypes = Literal[
    "checkout.session.completed", "payment_intent.succeeded", "payment_intent.payment_failed"
]

class EventData:
    object: Union[Session, PaymentIntent]

class Event:
    id: str
    api_version: str
    type: EventTypes
    data: EventData
    @staticmethod
    def construct_from(values: Dict[Any, Any], key: Optional[str]) -> Event: ...
    @staticmethod
    def list(limit: int = ..., ending_before: Optional[Event] = None) -> List[Event]: ...
    def to_dict_recursive(self) -> Dict[str, Any]: ...

class Webhook:
    @staticmethod
    def construct_event(payload: bytes, request_signature: str, webhook_secret: str) -> Event: ...
