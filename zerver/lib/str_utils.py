"""
String Utilities:

This module helps in converting strings from one type to another.

Currently we have strings of 3 semantic types:

1.  text strings: These strings are used to represent all textual data,
    like people's names, stream names, content of messages, etc.
    These strings can contain non-ASCII characters, so its type should be
    typing.str (which is `str` in python 3 and `unicode` in python 2).

2.  binary strings: These strings are used to represent binary data.
    This should be of type `bytes`

3.  native strings: These strings are for internal use only.  Strings of
    this type are not meant to be stored in database, displayed to end
    users, etc.  Things like exception names, parameter names, attribute
    names, etc should be native strings.  These strings should only
    contain ASCII characters and they should have type `str`.

There are 3 utility functions provided for converting strings from one type
to another - force_text, force_bytes, force_str

Interconversion between text strings and binary strings can be done by
using encode and decode appropriately or by using the utility functions
force_text and force_bytes.

It is recommended to use the utility functions for other string conversions.
"""

from typing import Any, Dict, Mapping, Union, TypeVar

NonBinaryStr = TypeVar('NonBinaryStr', str, str)
# This is used to represent text or native strings

def force_text(s: Union[str, bytes], encoding: str='utf-8') -> str:
    """converts a string to a text string"""
    if isinstance(s, str):
        return s
    elif isinstance(s, bytes):
        return s.decode(encoding)
    else:
        raise TypeError("force_text expects a string type")

def force_str(s: Union[str, bytes], encoding: str='utf-8') -> str:
    """converts a string to a native string"""
    if isinstance(s, str):
        return s
    elif isinstance(s, str):
        return s.encode(encoding)
    elif isinstance(s, bytes):
        return s.decode(encoding)
    else:
        raise TypeError("force_str expects a string type")
