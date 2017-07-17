var tutorial = (function () {

var exports = {};
var event_handlers = {};

// We'll temporarily set stream colors for the streams we use in the demo
// tutorial messages.
var real_default_color;
var tutorial_default_color = '#76ce90';

function disable_event_handlers() {
    $('body').css({overflow: 'hidden'}); // prevents scrolling the feed
    _.each(["keydown", "keyup", "keypress", "scroll"], function (event_name) {
        var existing_events = $._data(document, "events")[event_name];
        if (existing_events === undefined) {
            existing_events = [];
        }
        event_handlers[event_name] = existing_events;
        $._data(document, "events")[event_name] = [];
    });
}

function enable_event_handlers() {
    $('body').css({overflow: 'auto'}); // enables scrolling the feed
    _.each(["keydown", "keyup", "keypress", "scroll"], function (event_name) {
        $._data(document, "events")[event_name] = event_handlers[event_name];
    });
}

function set_tutorial_status(status, callback) {
    return channel.post({
        url:      '/json/tutorial_status',
        data:     {status: JSON.stringify(status)},
        success:  callback,
    });
}

function finale() {
    $(".screen").css({opacity: 0.0, width: 0, height: 0});

    // Restore your actual stream colors
    set_tutorial_status("finished");
    stream_color.default_color = real_default_color;
    $('#first_run_message').show();
    enable_event_handlers();

    var sender_bot = "welcome-bot@zulip.com";
    narrow.by('pm-with', sender_bot, {select_first_unread: true, trigger: 'sidebar'});
    compose_actions.cancel();
}

exports.start = function () {
    if (overlays.is_active()) {
        ui_util.change_tab_to('#home');
    }
    narrow.deactivate();

    // Set temporarly colors for the streams used in the tutorial.
    real_default_color = stream_color.default_color;
    stream_color.default_color = tutorial_default_color;
    disable_event_handlers();
    set_tutorial_status("started");
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
