from functools import wraps

import types

class TornadoAsyncException(Exception): pass

class _DefGen_Return(BaseException):
    def __init__(self, value):
        self.value = value

def returnResponse(value):
    raise _DefGen_Return(value)

def asynchronous(method):
    @wraps(method)
    def wrapper(request, *args, **kwargs):
        try:
            v = method(request, request._tornado_handler, *args, **kwargs)
            if v == None or type(v) == types.GeneratorType:
                raise TornadoAsyncException
        except _DefGen_Return, e:
            request._tornado_handler.finish(e.value.content)
        return v
    if getattr(method, 'csrf_exempt', False):
        wrapper.csrf_exempt = True
    return wrapper
