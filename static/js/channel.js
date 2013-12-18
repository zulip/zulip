var channel = (function () {

var exports = {};

function call(args) {
    return $.ajax(args);
}

exports.get = function (options) {
    var args = _.extend({type: "GET", dataType: "json"}, options);
    return call(args);
};

exports.post = function (options) {
    var args = _.extend({type: "POST", dataType: "json"}, options);
    return call(args);
};

exports.put = function (options) {
    var args = _.extend({type: "PUT", dataType: "json"}, options);
    return call(args);
};

// Not called exports.delete because delete is a reserved word in JS
exports.del = function (options) {
    var args = _.extend({type: "DELETE", dataType: "json"}, options);
    return call(args);
};

exports.patch = function (options) {
    // Send a PATCH as a POST in order to work around QtWebkit
    // (Linux/Windows desktop app) not supporting PATCH body.
    options.method = "PATCH";
    if (options.processData === false) {
        // If we're submitting a FormData object, we need to add the
        // method this way
        options.data.append("method", "PATCH");
    }
    return exports.post(options);
};

return exports;

}());
