from __future__ import absolute_import
from __future__ import print_function

from typing import (
    Optional,
    Sequence,
    Text,
)

from django.utils.translation import ugettext as _
from zerver.lib.request import JsonableError

class Addressee(object):
    # This is really just a holder for vars that tended to be passed
    # around in a non-type-safe way before this class was introduced.
    #
    # It also avoids some nonsense where you have to think about whether
    # topic should be None or '' for a PM, or you have to make an array
    # of one stream.
    #
    # Eventually we can use this to cache Stream and UserProfile objects
    # in memory.
    #
    # This should be treated as an immutable class.
    def __init__(self, msg_type, emails=None, stream_name=None, topic=None):
        # type: (str, Optional[Sequence[Text]], Optional[Text], Text) -> None
        assert(msg_type in ['stream', 'private'])
        self._msg_type = msg_type
        self._emails = emails
        self._stream_name = stream_name
        self._topic = topic

    def msg_type(self):
        # type: () -> str
        return self._msg_type

    def is_stream(self):
        # type: () -> bool
        return self._msg_type == 'stream'

    def is_private(self):
        # type: () -> bool
        return self._msg_type == 'private'

    def emails(self):
        # type: () -> Sequence[Text]
        assert(self.is_private())
        return self._emails

    def stream_name(self):
        # type: () -> Text
        assert(self.is_stream())
        return self._stream_name

    def topic(self):
        # type: () -> Text
        assert(self._msg_type == 'stream')
        return self._topic

    @staticmethod
    def legacy_build(message_type_name, message_to, subject_name):
        # type: (Text, Sequence[Text], Text) -> Addressee

        # For legacy reason message_to used to be either a list of
        # emails or a list of streams.  We haven't fixed all of our
        # callers yet.
        if message_type_name == 'stream':
            if len(message_to) > 1:
                raise JsonableError(_("Cannot send to multiple streams"))

            if message_to:
                stream_name = message_to[0]
            else:
                # This is a hack to deal with the fact that we still support
                # default streams (and the None will be converted later in the
                # callpath).
                stream_name = None

            return Addressee.for_stream(stream_name, subject_name)
        elif message_type_name == 'private':
            return Addressee.for_private(emails=message_to)
        else:
            raise JsonableError(_("Invalid message type"))

    @staticmethod
    def for_stream(stream_name, topic):
        # type: (Text, Text) -> Addressee
        return Addressee(
            msg_type='stream',
            stream_name=stream_name,
            topic=topic,
        )

    @staticmethod
    def for_private(emails):
        # type: (Sequence[Text]) -> Addressee
        return Addressee(
            msg_type='private',
            emails=emails,
        )

    @staticmethod
    def for_email(email):
        # type: (Text) -> Addressee
        return Addressee(
            msg_type='private',
            emails=[email],
        )
