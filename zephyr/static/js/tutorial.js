var tutorial = (function () {

var exports = {};
var is_running = false;

function set_tutorial_status(status, callback) {
    return $.ajax({
        type:     'POST',
        url:      '/json/tutorial_status',
        data:     {status: status},
        success:  callback
    });
}

exports.is_running = function() {
    return is_running;
};

exports.start = function () {
    is_running = true;
    set_tutorial_status("started");
};

exports.initialize = function () {
    if (page_params.needs_tutorial) {
        exports.start();
    }
};

return exports;
}());
