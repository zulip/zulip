from enum import Enum
from typing import Any, Dict, List, Optional, Text, Type

from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext as _

class AbstractEnum(Enum):
    '''An enumeration whose members are used strictly for their names.'''

    def __new__(cls: Type['AbstractEnum']) -> 'AbstractEnum':
        obj = object.__new__(cls)
        obj._value_ = len(cls.__members__) + 1
        return obj

    # Override all the `Enum` methods that use `_value_`.

    def __repr__(self) -> str:
        return str(self)

    def value(self) -> None:
        assert False

    def __reduce_ex__(self, proto: int) -> None:
        assert False

class ErrorCode(AbstractEnum):
    BAD_REQUEST = ()  # Generic name, from the name of HTTP 400.
    REQUEST_VARIABLE_MISSING = ()
    REQUEST_VARIABLE_INVALID = ()
    BAD_IMAGE = ()
    REALM_UPLOAD_QUOTA = ()
    BAD_NARROW = ()
    STREAM_DOES_NOT_EXIST = ()
    UNAUTHORIZED_PRINCIPAL = ()
    BAD_EVENT_QUEUE_ID = ()
    CSRF_FAILED = ()
    INVITATION_FAILED = ()
    INVALID_ZULIP_SERVER = ()

class JsonableError(Exception):
    '''A standardized error format we can turn into a nice JSON HTTP response.

    This class can be invoked in several ways.

     * Easiest, but completely machine-unreadable:

         raise JsonableError(_("No such widget: {}").format(widget_name))

       The message may be passed through to clients and shown to a user,
       so translation is required.  Because the text will vary depending
       on the user's language, it's not possible for code to distinguish
       this error from others in a non-buggy way.

     * Partially machine-readable, with an error code:

         raise JsonableError(_("No such widget: {}").format(widget_name),
                             ErrorCode.NO_SUCH_WIDGET)

       Now the error's `code` attribute can be used, both in server
       and client code, to identify this type of error.  The data
       (here, the widget name) is still embedded inside a translated
       string, and can't be accessed by code.

     * Fully machine-readable, with an error code and structured data:

         class NoSuchWidgetError(JsonableError):
             code = ErrorCode.NO_SUCH_WIDGET
             data_fields = ['widget_name']

             def __init__(self, widget_name: str) -> None:
                 self.widget_name = widget_name  # type: str

             @staticmethod
             def msg_format() -> str:
                 return _("No such widget: {widget_name}")

         raise NoSuchWidgetError(widget_name)

       Now both server and client code see a `widget_name` attribute.

    Subclasses may also override `http_status_code`.
    '''

    # Override this in subclasses, or just pass a `code` argument
    # to the JsonableError constructor.
    code = ErrorCode.BAD_REQUEST  # type: ErrorCode

    # Override this in subclasses if providing structured data.
    data_fields = []  # type: List[str]

    # Optionally override this in subclasses to return a different HTTP status,
    # like 403 or 404.
    http_status_code = 400  # type: int

    def __init__(self, msg: Text, code: Optional[ErrorCode]=None) -> None:
        if code is not None:
            self.code = code

        # `_msg` is an implementation detail of `JsonableError` itself.
        self._msg = msg  # type: Text

    @staticmethod
    def msg_format() -> Text:
        '''Override in subclasses.  Gets the items in `data_fields` as format args.

        This should return (a translation of) a string literal.
        The reason it's not simply a class attribute is to allow
        translation to work.
        '''
        # Secretly this gets one more format arg not in `data_fields`: `_msg`.
        # That's for the sake of the `JsonableError` base logic itself, for
        # the simplest form of use where we just get a plain message string
        # at construction time.
        return '{_msg}'

    #
    # Infrastructure -- not intended to be overridden in subclasses.
    #

    @property
    def msg(self) -> Text:
        format_data = dict(((f, getattr(self, f)) for f in self.data_fields),
                           _msg=getattr(self, '_msg', None))
        return self.msg_format().format(**format_data)

    @property
    def data(self) -> Dict[str, Any]:
        return dict(((f, getattr(self, f)) for f in self.data_fields),
                    code=self.code.name)

    def to_json(self) -> Dict[str, Any]:
        d = {'result': 'error', 'msg': self.msg}
        d.update(self.data)
        return d

    def __str__(self) -> str:
        return self.msg

class StreamDoesNotExistError(JsonableError):
    code = ErrorCode.STREAM_DOES_NOT_EXIST
    data_fields = ['stream']

    def __init__(self, stream: str) -> None:
        self.stream = stream

    @staticmethod
    def msg_format() -> str:
        return _("Stream '{stream}' does not exist")

class RateLimited(PermissionDenied):
    def __init__(self, msg: str="") -> None:
        super().__init__(msg)
