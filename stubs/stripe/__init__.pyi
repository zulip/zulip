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
    subscriptions: SubscriptionListObject
    coupon: str
    account_balance: int
    email: str
    description: str
    discount: Discount
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
    status: str
    total: int

    @staticmethod
    def upcoming(customer: str=..., subscription: str=...,
                 subscription_items: List[Dict[str, Union[str, int]]]=...) -> Invoice:
        ...

    @staticmethod
    def list(customer: str=..., limit: Optional[int]=...) -> List[Invoice]:
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

    @staticmethod
    def list(customer: Optional[str]) -> List[Charge]:
        ...
