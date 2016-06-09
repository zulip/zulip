import six
from six import text_type, binary_type
from typing import Any, Mapping, Union, TypeVar

NonBinaryStr = TypeVar('NonBinaryStr', str, text_type)
# This is used to represent text or native strings

def force_text(s):
    # type: (Union[text_type, binary_type]) -> text_type
    if isinstance(s, text_type):
        return s
    elif isinstance(s, binary_type):
        return s.decode('utf-8')
    else:
        raise ValueError("force_text expects a string type")

def force_bytes(s):
    # type: (Union[text_type, binary_type]) -> binary_type
    if isinstance(s, binary_type):
        return s
    elif isinstance(s, text_type):
        return s.encode('utf-8')
    else:
        raise ValueError("force_bytes expects a string type")

def force_str(s):
    # type: (Union[text_type, binary_type]) -> str
    if isinstance(s, str):
        return s
    elif isinstance(s, text_type):
        return s.encode('utf-8')
    elif isinstance(s, binary_type):
        return s.decode('utf-8')
    else:
        raise ValueError("force_str expects a string type")

def dict_with_str_keys(dct):
    # type: (Mapping[NonBinaryStr, Any]) -> Dict[str, Any]
    """applies force_str on the keys of a dict (non-recursively)"""
    return {force_str(key): value for key, value in six.iteritems(dct)}
