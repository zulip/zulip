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
            on_success(data);
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

function update_setting(command) {
    exports.send({
        command: command,
        on_success: function (data) {
            exports.tell_user(data.msg);
        },
    });
}

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

    var mode_commands = ['/day', '/night', '/light', '/dark'];
    if (mode_commands.indexOf(content) >= 0) {
        update_setting(content);
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
