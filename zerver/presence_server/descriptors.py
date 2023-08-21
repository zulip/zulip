descriptors_by_handler_id = {}


def get_descriptor_by_handler_id(handler_id):
    return descriptors_by_handler_id.get(handler_id)


def set_descriptor_by_handler_id(handler_id, client_descriptor):
    descriptors_by_handler_id[handler_id] = client_descriptor


def clear_descriptor_by_handler_id(handler_id):
    del descriptors_by_handler_id[handler_id]
