var zcommand = (function () {

var exports = {};

/*

What in the heck is a zcommand?

    A zcommand is basically a specific type of slash
    command where the client does almost no work and
    the server just does something pretty simple like
    flip a setting.

    The first zcommand we wrote is for "/ping", and
    the server just responds with a 200 for that.

    Not all slash commands use zcommand under the hood.
    For more exotic things like /poll see submessage.js
    and widgetize.js

*/

exports.send = function (opts) {
    var command = opts.command;
    var on_success = opts.on_success;
    var data = {
        command: command,
    };

    channel.post({
        url: '/json/zcommand',
        data: data,
        success: function (data) {
            if (on_success) {
                on_success(data);
            }
        },
        error: function () {
            exports.tell_user('server did not respond');
        },
    });
};

exports.tell_user = function (msg) {
    // This is a bit hacky, but we don't have a super easy API now
    // for just telling users stuff.
    $('#compose-send-status').removeClass(common.status_classes)
        .addClass('alert-error')
        .stop(true).fadeTo(0, 1);
    $('#compose-error-msg').text(msg);
};

exports.enter_day_mode = function () {
    exports.send({
        command: "/day",
        on_success: function (data) {
            night_mode.disable();
            feedback_widget.show({
                populate: function (container) {
                    container.text(data.msg);
                },
                on_undo: function () {
                    exports.send({
                        command: "/night",
                    });
                },
                title_text: i18n.t("Day mode"),
                undo_button_text: i18n.t("Night"),
            });
        },
    });
};

exports.enter_night_mode = function () {
    exports.send({
        command: "/night",
        on_success: function (data) {
            night_mode.enable();
            feedback_widget.show({
                populate: function (container) {
                    container.text(data.msg);
                },
                on_undo: function () {
                    exports.send({
                        command: "/day",
                    });
                },
                title_text: i18n.t("Night mode"),
                undo_button_text: i18n.t("Day"),
            });
        },
    });
};

exports.process = function (message_content) {

    var content = message_content.trim();

    if (content === '/ping') {
        var start_time = new Date();

        exports.send({
            command: content,
            on_success: function () {
                var end_time = new Date();
                var diff = end_time - start_time;
                diff = Math.round(diff);
                var msg = "ping time: " + diff + "ms";
                exports.tell_user(msg);
            },
        });
        return true;
    }

    var day_commands = ['/day', '/light'];
    if (day_commands.indexOf(content) >= 0) {
        exports.enter_day_mode();
        return true;
    }

    var night_commands = ['/night', '/dark'];
    if (night_commands.indexOf(content) >= 0) {
        exports.enter_night_mode();
        return true;
    }

    if (content === '/settings') {
        hashchange.go_to_location('settings/your-account');
        return true;
    }

    // It is incredibly important here to return false
    // if we don't see an actual zcommand, so that compose.js
    // knows this is a normal message.
    return false;
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = zcommand;
}

window.zcommand = zcommand;
