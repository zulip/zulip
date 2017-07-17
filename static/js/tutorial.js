var tutorial = (function () {

var exports = {};

function set_tutorial_status(status, callback) {
    return channel.post({
        url:      '/json/tutorial_status',
        data:     {status: JSON.stringify(status)},
        success:  callback,
    });
}

function finale() {
    set_tutorial_status("finished");

    var sender_bot = "welcome-bot@zulip.com";
    narrow.by('pm-with', sender_bot, {select_first_unread: true, trigger: 'sidebar'});
    compose_actions.cancel();
}

exports.start = function () {
    finale();
};

exports.initialize = function () {
    if (page_params.needs_tutorial) {
        exports.start();
    }
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = tutorial;
}
