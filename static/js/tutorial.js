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
    $(".screen").css({opacity: 0.0, width: 0, height: 0});

    set_tutorial_status("finished");
    $('#first_run_message').show();

    var sender_bot = "welcome-bot@zulip.com";
    narrow.by('pm-with', sender_bot, {select_first_unread: true, trigger: 'sidebar'});
    compose_actions.cancel();
}

exports.start = function () {
    if (overlays.is_active()) {
        ui_util.change_tab_to('#home');
    }
    narrow.deactivate();

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
