import stripe.error as error
import stripe.util as util
import stripe.api_requestor as api_requestor
from stripe.api_resources.list_object import SubscriptionListObject

from typing import Optional, Any, Dict, List, Union

api_key: Optional[str]

class Customer:
    default_source: Card
    created: int
    id: str
    source: str
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
    amount_due: int
    total: int

    @staticmethod
    def upcoming(customer: str=..., subscription: str=...,
                 subscription_items: List[Dict[str, Union[str, int]]]=...) -> Invoice:
        ...

class Subscription:
    created: int
    status: str
    canceled_at: int
    cancel_at_period_end: bool
    proration_date: int
    quantity: int

    @staticmethod
    def create(customer: str=..., billing: str=..., items: List[Dict[str, Any]]=...,
               prorate: bool=..., tax_percent: float=...) -> Subscription:
        ...

class Card:
    id: str
    last4: str

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
