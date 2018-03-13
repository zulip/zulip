from typing import TypeVar, Callable
from django.http import HttpResponse

ViewFuncT = TypeVar('ViewFuncT', bound=Callable[..., HttpResponse])
