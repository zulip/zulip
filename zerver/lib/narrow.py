from zerver.lib.request import JsonableError

def check_supported_events_narrow_filter(narrow):
    for element in narrow:
        operator = element[0]
        if operator not in ["stream", "topic", "sender", "is"]:
            raise JsonableError("Operator %s not supported." % (operator,))

def build_narrow_filter(narrow):
    check_supported_events_narrow_filter(narrow)
    def narrow_filter(event):
        message = event["message"]
        flags = event["flags"]
        for element in narrow:
            operator = element[0]
            operand = element[1]
            if operator == "stream":
                if message["type"] != "stream":
                    return False
                if operand.lower() != message["display_recipient"].lower():
                    return False
            elif operator == "topic":
                if message["type"] != "stream":
                    return False
                if operand.lower() != message["subject"].lower():
                    return False
            elif operator == "sender":
                if operand.lower() != message["sender_email"].lower():
                    return False
            elif operator == "is" and operand == "private":
                if message["type"] != "private":
                    return False
            elif operator == "is" and operand in ["starred"]:
                if operand not in flags:
                    return False
            elif operator == "is" and operand in ["alerted", "mentioned"]:
                if "mentioned" not in flags:
                    return False

        return True
    return narrow_filter
