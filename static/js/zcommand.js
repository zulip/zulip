"use strict";

const marked = require("../third/marked/lib/marked");

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
    const command = opts.command;
    const on_success = opts.on_success;
    const data = {
        command,
    };

    channel.post({
        url: "/json/zcommand",
        data,
        success(data) {
            if (on_success) {
                on_success(data);
            }
        },
        error() {
            exports.tell_user("server did not respond");
        },
    });
};

exports.tell_user = function (msg) {
    // This is a bit hacky, but we don't have a super easy API now
    // for just telling users stuff.
    $("#compose-send-status")
        .removeClass(common.status_classes)
        .addClass("alert-error")
        .stop(true)
        .fadeTo(0, 1);
    $("#compose-error-msg").text(msg);
};

exports.enter_day_mode = function () {
    exports.send({
        command: "/day",
        on_success(data) {
            night_mode.disable();
            feedback_widget.show({
                populate(container) {
                    const rendered_msg = marked(data.msg).trim();
                    container.html(rendered_msg);
                },
                on_undo() {
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
        on_success(data) {
            night_mode.enable();
            feedback_widget.show({
                populate(container) {
                    const rendered_msg = marked(data.msg).trim();
                    container.html(rendered_msg);
                },
                on_undo() {
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

exports.enter_fluid_mode = function () {
    exports.send({
        command: "/fluid-width",
        on_success(data) {
            scroll_bar.set_layout_width();
            feedback_widget.show({
                populate(container) {
                    const rendered_msg = marked(data.msg).trim();
                    container.html(rendered_msg);
                },
                on_undo() {
                    exports.send({
                        command: "/fixed-width",
                    });
                },
                title_text: i18n.t("Fluid width mode"),
                undo_button_text: i18n.t("Fixed width"),
            });
        },
    });
};

exports.enter_fixed_mode = function () {
    exports.send({
        command: "/fixed-width",
        on_success(data) {
            scroll_bar.set_layout_width();
            feedback_widget.show({
                populate(container) {
                    const rendered_msg = marked(data.msg).trim();
                    container.html(rendered_msg);
                },
                on_undo() {
                    exports.send({
                        command: "/fluid-width",
                    });
                },
                title_text: i18n.t("Fixed width mode"),
                undo_button_text: i18n.t("Fluid width"),
            });
        },
    });
};

exports.process = function (message_content) {
    const content = message_content.trim();

    if (content === "/ping") {
        const start_time = new Date();

        exports.send({
            command: content,
            on_success() {
                const end_time = new Date();
                let diff = end_time - start_time;
                diff = Math.round(diff);
                const msg = "ping time: " + diff + "ms";
                exports.tell_user(msg);
            },
        });
        return true;
    }

    const day_commands = ["/day", "/light"];
    if (day_commands.includes(content)) {
        exports.enter_day_mode();
        return true;
    }

    const night_commands = ["/night", "/dark"];
    if (night_commands.includes(content)) {
        exports.enter_night_mode();
        return true;
    }

    if (content === "/fluid-width") {
        exports.enter_fluid_mode();
        return true;
    }

    if (content === "/fixed-width") {
        exports.enter_fixed_mode();
        return true;
    }

    if (content === "/settings") {
        hashchange.go_to_location("settings/your-account");
        return true;
    }

    // It is incredibly important here to return false
    // if we don't see an actual zcommand, so that compose.js
    // knows this is a normal message.
    return false;
};

window.zcommand = exports;
