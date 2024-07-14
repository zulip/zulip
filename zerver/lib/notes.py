import weakref
from abc import ABC, abstractmethod
from collections.abc import MutableMapping
from typing import Any, ClassVar, Generic, TypeVar

from typing_extensions import override

_KeyT = TypeVar("_KeyT")
_DataT = TypeVar("_DataT")


class BaseNotes(Generic[_KeyT, _DataT], ABC):
    """This class defines a generic type-safe mechanism for associating
    additional data with an object (without modifying the original
    object via subclassing or monkey-patching).

    It was originally designed to avoid monkey-patching the Django
    HttpRequest object, to which we want to associate computed state
    (e.g. parsed state computed from the User-Agent) so that it's
    available in code paths that receive the HttpRequest object.

    The implementation uses a WeakKeyDictionary, so that the notes
    object will be garbage-collected when the original object no
    longer has other references (avoiding memory leaks).

    We still need to be careful to avoid any of the attributes of
    _DataT having points to the original object, as that can create a
    cyclic reference cycle that the Python garbage collect may not
    handle correctly.
    """

    __notes_map: ClassVar[MutableMapping[Any, Any]]

    @override
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "__notes_map"):
            cls.__notes_map = weakref.WeakKeyDictionary()

    @classmethod
    def get_notes(cls, key: _KeyT) -> _DataT:
        try:
            return cls.__notes_map[key]
        except KeyError:
            cls.__notes_map[key] = cls.init_notes()
            return cls.__notes_map[key]

    @classmethod
    def set_notes(cls, key: _KeyT, notes: _DataT) -> None:
        cls.__notes_map[key] = notes

    @classmethod
    @abstractmethod
    def init_notes(cls) -> _DataT: ...
