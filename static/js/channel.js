var channel = (function () {

var exports = {};
var pending_requests = [];

function add_pending_request(jqXHR) {
    pending_requests.push(jqXHR);
    if (pending_requests.length > 50) {
        blueslip.warn('The length of pending_requests is over 50. Most likely ' +
                      'they are not being correctly removed.');
    }
}

function remove_pending_request(jqXHR) {
    var pending_request_index = _.indexOf(pending_requests, jqXHR);
    if (pending_request_index !== -1) {
        pending_requests.splice(pending_request_index, 1);
    }
}

function call(args, idempotent) {
    // Wrap the error handlers to reload the page if we get a CSRF error
    // (What probably happened is that the user logged out in another tab).
    var orig_error = args.error;
    if (orig_error === undefined) {
        orig_error = function () {};
    }
    args.error = function wrapped_error(xhr, error_type, xhn) {
        remove_pending_request(xhr);

        if (xhr.status === 403) {
            try {
                if (JSON.parse(xhr.responseText).code === 'CSRF_FAILED') {
                    reload.initiate({immediate: true,
                                     save_pointer: true,
                                     save_narrow: true,
                                     save_compose: true});
                }
            } catch (ex) {
                blueslip.error('Unexpected 403 response from server',
                               {xhr: xhr.responseText,
                                args: args},
                               ex.stack);
            }
        }
        return orig_error(xhr, error_type, xhn);
    };
    var orig_success = args.success;
    if (orig_success === undefined) {
        orig_success = function () {};
    }
    args.success = function wrapped_success(data, textStatus, jqXHR) {
        remove_pending_request(jqXHR);

        if (!data && idempotent) {
            // If idempotent, retry
            blueslip.log("Retrying idempotent" + args);
            setTimeout(function () {
                var jqXHR = $.ajax(args);
                add_pending_request(jqXHR);
            }, 0);
            return;
        }
        return orig_success(data, textStatus, jqXHR);
    };

    var jqXHR = $.ajax(args);
    add_pending_request(jqXHR);
    return jqXHR;
}

exports.get = function (options) {
    var args = _.extend({type: "GET", dataType: "json"}, options);
    return call(args, options.idempotent);
};

exports.post = function (options) {
    var args = _.extend({type: "POST", dataType: "json"}, options);
    return call(args, options.idempotent);
};

exports.put = function (options) {
    var args = _.extend({type: "PUT", dataType: "json"}, options);
    return call(args, options.idempotent);
};

// Not called exports.delete because delete is a reserved word in JS
exports.del = function (options) {
    var args = _.extend({type: "DELETE", dataType: "json"}, options);
    return call(args, options.idempotent);
};

exports.patch = function (options) {
    // Send a PATCH as a POST in order to work around QtWebkit
    // (Linux/Windows desktop app) not supporting PATCH body.
    if (options.processData === false) {
        // If we're submitting a FormData object, we need to add the
        // method this way
        options.data.append("method", "PATCH");
    } else {
        options.data = _.extend({}, options.data, {method: 'PATCH'});
    }
    return exports.post(options, options.idempotent);
};

exports.xhr_error_message = function (message, xhr) {
    if (xhr.status.toString().charAt(0) === "4") {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        message += ": " + JSON.parse(xhr.responseText).msg;
    }
    return message;
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = channel;
}
window.channel = channel;
