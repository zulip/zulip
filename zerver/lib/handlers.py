import logging
from zerver.middleware import async_request_restart

current_handler_id = 0
handlers = {}

def get_handler_by_id(handler_id):
    return handlers[handler_id]

def allocate_handler_id(handler):
    global current_handler_id
    handlers[current_handler_id] = handler
    handler.handler_id = current_handler_id
    current_handler_id += 1
    return handler.handler_id

def finish_handler(handler_id, event_queue_id, contents, apply_markdown):
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
        if e.message != 'Stream is closed':
            logging.exception(err_msg)
    except AssertionError as e:
        if e.message != 'Request closed':
            logging.exception(err_msg)
    except Exception:
        logging.exception(err_msg)
