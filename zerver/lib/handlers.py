import logging
from zerver.middleware import async_request_restart
from typing import Any

current_handler_id = 0
handlers = {} # type: Dict[int, Any] # TODO: Should be AsyncDjangoHandler but we don't important runtornado.py.

def get_handler_by_id(handler_id):
    # type: (int) -> Any # TODO: should be AsyncDjangoHandler, see above
    return handlers[handler_id]

def allocate_handler_id(handler):
    # type: (Any) -> int # TODO: should be AsyncDjangoHandler, see above
    global current_handler_id
    handlers[current_handler_id] = handler
    handler.handler_id = current_handler_id
    current_handler_id += 1
    return handler.handler_id

def clear_handler_by_id(handler_id):
    # type: (int) -> None
    del handlers[handler_id]

def handler_stats_string():
    # type: () -> str
    return "%s handlers, latest ID %s" % (len(handlers), current_handler_id)

def finish_handler(handler_id, event_queue_id, contents, apply_markdown):
    # type: (int, str, List[Dict[str, Any]], bool) -> None
    err_msg = "Got error finishing handler for queue %s" % (event_queue_id,)
    try:
        # We call async_request_restart here in case we are
        # being finished without any events (because another
        # get_events request has supplanted this request)
        handler = get_handler_by_id(handler_id)
        request = handler._request
        async_request_restart(request)
        request._log_data['extra'] = "[%s/1]" % (event_queue_id,)
        handler.zulip_finish(dict(result='success', msg='',
                                  events=contents,
                                  queue_id=event_queue_id),
                             request, apply_markdown=apply_markdown)
    except IOError as e:
        if str(e) != 'Stream is closed':
            logging.exception(err_msg)
    except AssertionError as e:
        if str(e) != 'Request closed':
            logging.exception(err_msg)
    except Exception:
        logging.exception(err_msg)
