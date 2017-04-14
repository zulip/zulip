var compose_state = (function () {

var exports = {};

var message_type = false; // 'stream', 'private', or false-y

exports.set_message_type = function (msg_type) {
    message_type = msg_type;
};

exports.get_message_type = function () {
    return message_type;
};

exports.composing = function () {
    // For legacy reasons, this is the same as get_message_type.
    // Most callers use this in a boolean context, but there are
    // some stragglers that inspect the string value.
    //
    // TODO: Fix callers who care about stream/private to use
    //       get_message_type(), and then convert this to return
    //       `!!message_type` or something like that.
    return message_type;
};

function get_or_set(fieldname, keep_leading_whitespace) {
    // We can't hoist the assignment of 'elem' out of this lambda,
    // because the DOM element might not exist yet when get_or_set
    // is called.
    return function (newval) {
        var elem = $('#'+fieldname);
        var oldval = elem.val();
        if (newval !== undefined) {
            elem.val(newval);
        }
        return keep_leading_whitespace ? util.rtrim(oldval) : $.trim(oldval);
    };
}

// TODO: Break out setters and getter into their own functions.
exports.stream_name     = get_or_set('stream');
exports.subject         = get_or_set('subject');
// We can't trim leading whitespace in `new_message_content` because
// of the indented syntax for multi-line code blocks.
exports.message_content = get_or_set('new_message_content', true);
exports.recipient       = get_or_set('private_message_recipient');

exports.has_message_content = function () {
    return exports.message_content() !== "";
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = compose_state;
}
