current_handler_id = 0
handlers = {}

def get_handler_by_id(handler_id):
    return handlers[handler_id]

def allocate_handler_id(handler):
    global current_handler_id
    handlers[current_handler_id] = handler
    ret = current_handler_id
    current_handler_id += 1
    return ret
