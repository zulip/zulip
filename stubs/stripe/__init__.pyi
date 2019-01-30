# NOTE: When editing stubs, we recommend using `tools/run-mypy --no-daemon`,
# because the mypy daemon's caching system has some bugs around editing stubs
#
# See https://zulip.readthedocs.io/en/latest/testing/mypy.html#mypy-stubs-for-third-party-modules
# for notes on how we manage mypy stubs.

import stripe.error as error
import stripe.util as util
import stripe.api_requestor as api_requestor
from stripe.api_resources.list_object import SubscriptionListObject

from typing import Optional, Any, Dict, List, Union

api_key: Optional[str]

class Customer:
    default_source: Union[Card, Source]
    created: int
    id: str
    source: str
    sources: List[Union[Card, Source]]
    subscriptions: SubscriptionListObject
    coupon: str
    account_balance: int
    email: str
    description: str
    discount: Optional[Discount]
    metadata: Dict[str, str]

    @staticmethod
    def retrieve(customer_id: str=..., expand: Optional[List[str]]=...) -> Customer:
        ...

    @staticmethod
    def create(description: str=..., email: str=..., metadata: Dict[str, Any]=...,
               source: Optional[str]=..., coupon: Optional[str]=...) -> Customer:
        ...

    @staticmethod
    def save(customer: Customer) -> Customer:
        ...

    @staticmethod
    def delete_discount(customer: Customer) -> None:
        ...

    @staticmethod
    def list(limit: Optional[int]=...) -> List[Customer]:
        ...


class Invoice:
    auto_advance: bool
    amount_due: int
    billing: str
    billing_reason: str
    default_source: Source
    due_date: int
    finalized_at: int
    lines: List[InvoiceLineItem]
    status: str
    total: int

    @staticmethod
    def upcoming(customer: str=..., subscription: str=...,
                 subscription_items: List[Dict[str, Union[str, int]]]=...) -> Invoice:
        ...

    @staticmethod
    def list(customer: str=..., limit: Optional[int]=...) -> List[Invoice]:
        ...

    @staticmethod
    def create(auto_advance: bool=..., billing: str=..., customer: str=...,
               days_until_due: Optional[int]=..., statement_descriptor: str=...) -> Invoice:
        ...

    @staticmethod
    def finalize_invoice(invoice: Invoice) -> Invoice:
        ...

    def get(self, key: str) -> Any:
        ...

class Subscription:
    created: int
    status: str
    canceled_at: int
    cancel_at_period_end: bool
    days_until_due: Optional[int]
    proration_date: int
    quantity: int

    @staticmethod
    def create(customer: str=..., billing: str=..., days_until_due: Optional[int]=...,
               items: List[Dict[str, Any]]=...,
               prorate: bool=..., tax_percent: float=...) -> Subscription:
        ...

    @staticmethod
    def save(subscription: Subscription, idempotency_key: str=...) -> Subscription:
        ...

    @staticmethod
    def delete(subscription: Subscription) -> Subscription:
        ...

    @staticmethod
    def retrieve(subscription_id: str) -> Subscription:
        ...

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
    def create(currency: str=..., interval: str=..., product: str=..., amount: int=...,
               billing_scheme: str=..., nickname: str=..., usage_type: str=...) -> Plan:
        ...

class Product:
    id: str

    @staticmethod
    def create(name: str=..., type: str=..., statement_descriptor: str=..., unit_label: str=...) -> Product:
        ...

class Discount:
    coupon: Coupon

class Coupon:
    id: str
    percent_off: int

    @staticmethod
    def create(duration: str=..., name: str=..., percent_off: int=...) -> Coupon:
        ...

class Token:
    id: str
    @staticmethod
    def create(card: Dict[str, Any]) -> Token:
        ...

class Charge:
    amount: int
    description: str
    failure_code: str
    receipt_email: str
    source: Source
    statement_descriptor: str

    @staticmethod
    def list(customer: Optional[str]) -> List[Charge]:
        ...

    @staticmethod
    def create(amount: int=..., currency: str=..., customer: str=..., description: str=...,
               receipt_email: str=..., statement_descriptor: str=...) -> Charge:
        ...

class InvoiceItem:
    @staticmethod
    def create(amount: int=..., currency: str=..., customer: str=..., description: str=...,
               discountable: bool=..., period: Dict[str, int]=..., quantity: int=...,
               unit_amount: int=..., idempotency_key: Optional[str]=...) -> InvoiceItem:
        ...

    @staticmethod
    def list(customer: Optional[str]) -> List[InvoiceItem]:
        ...

class InvoiceLineItem:
    amount: int

    def get(self, key: str) -> Any:
        ...
