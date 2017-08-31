var tutorial = (function () {

var exports = {};

function set_tutorial_status(status, callback) {
    return channel.post({
        url:      '/json/tutorial_status',
        data:     {status: JSON.stringify(status)},
        success:  callback,
    });
}

exports.initialize = function () {
    if (page_params.needs_tutorial) {
        set_tutorial_status("started");
        narrow.by('is', 'private', {select_first_unread: true, trigger: 'sidebar'});
    }
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = tutorial;
}
