import $ from "jquery";

import render_digress_zcommand_message from "../templates/digress_zcommand_message.hbs";
import marked from "../third/marked/lib/marked";

import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as common from "./common";
import * as compose_state from "./compose_state";
import * as feedback_widget from "./feedback_widget";
import {$t} from "./i18n";
import * as narrow from "./narrow";
import * as night_mode from "./night_mode";
import * as scroll_bar from "./scroll_bar";

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

export function send(opts) {
    const command = opts.command;
    const command_data = opts.command_data;
    const on_success = opts.on_success;
    const data = {
        command,
        command_data: JSON.stringify(command_data),
    };

    channel.post({
        url: "/json/zcommand",
        data,
        success(data) {
            if (on_success) {
                on_success(data);
            }
        },
        error(xhr) {
            if (xhr.responseText) {
                tell_user(JSON.parse(xhr.responseText).msg);
            } else {
                tell_user("server did not respond");
            }
        },
    });
}

export function tell_user(msg) {
    // This is a bit hacky, but we don't have a super easy API now
    // for just telling users stuff.
    $("#compose-send-status")
        .removeClass(common.status_classes)
        .addClass("alert-error")
        .stop(true)
        .fadeTo(0, 1);
    $("#compose-error-msg").text(msg);
}

export function enter_day_mode() {
    send({
        command: "/day",
        on_success(data) {
            night_mode.disable();
            feedback_widget.show({
                populate(container) {
                    const rendered_msg = marked(data.msg).trim();
                    container.html(rendered_msg);
                },
                on_undo() {
                    send({
                        command: "/night",
                    });
                },
                title_text: $t({defaultMessage: "Day mode"}),
                undo_button_text: $t({defaultMessage: "Night"}),
            });
        },
    });
}

export function enter_night_mode() {
    send({
        command: "/night",
        on_success(data) {
            night_mode.enable();
            feedback_widget.show({
                populate(container) {
                    const rendered_msg = marked(data.msg).trim();
                    container.html(rendered_msg);
                },
                on_undo() {
                    send({
                        command: "/day",
                    });
                },
                title_text: $t({defaultMessage: "Night mode"}),
                undo_button_text: $t({defaultMessage: "Day"}),
            });
        },
    });
}

export function enter_fluid_mode() {
    send({
        command: "/fluid-width",
        on_success(data) {
            scroll_bar.set_layout_width();
            feedback_widget.show({
                populate(container) {
                    const rendered_msg = marked(data.msg).trim();
                    container.html(rendered_msg);
                },
                on_undo() {
                    send({
                        command: "/fixed-width",
                    });
                },
                title_text: $t({defaultMessage: "Fluid width mode"}),
                undo_button_text: $t({defaultMessage: "Fixed width"}),
            });
        },
    });
}

export function enter_fixed_mode() {
    send({
        command: "/fixed-width",
        on_success(data) {
            scroll_bar.set_layout_width();
            feedback_widget.show({
                populate(container) {
                    const rendered_msg = marked(data.msg).trim();
                    container.html(rendered_msg);
                },
                on_undo() {
                    send({
                        command: "/fluid-width",
                    });
                },
                title_text: $t({defaultMessage: "Fixed width mode"}),
                undo_button_text: $t({defaultMessage: "Fluid width"}),
            });
        },
    });
}

export function digress(command_data) {
    send({
        command: "/digress",
        command_data,
        on_success() {
            let operators = [
                {operator: "stream", operand: command_data.new_stream},
                {operator: "topic", operand: command_data.new_topic},
            ];
            narrow.activate(operators);
            feedback_widget.show({
                populate(container) {
                    const rendered_message = render_digress_zcommand_message({
                        stream_name: command_data.new_stream,
                        topic: command_data.new_topic,
                    });
                    container.html(rendered_message);
                },
                on_undo() {
                    operators = [
                        {operator: "stream", operand: command_data.old_stream},
                        {operator: "topic", operand: command_data.old_topic},
                    ];
                    narrow.activate(operators);
                },
                title_text: $t({defaultMessage: "Digress"}),
                undo_button_text: $t({defaultMessage: "Go back"}),
            });
        },
    });
}

export function process(message_content) {
    const content = message_content.trim();

    if (content === "/ping") {
        const start_time = new Date();

        send({
            command: content,
            on_success() {
                const end_time = new Date();
                let diff = end_time - start_time;
                diff = Math.round(diff);
                const msg = "ping time: " + diff + "ms";
                tell_user(msg);
            },
        });
        return true;
    }

    const day_commands = ["/day", "/light"];
    if (day_commands.includes(content)) {
        enter_day_mode();
        return true;
    }

    const night_commands = ["/night", "/dark"];
    if (night_commands.includes(content)) {
        enter_night_mode();
        return true;
    }

    if (content === "/fluid-width") {
        enter_fluid_mode();
        return true;
    }

    if (content === "/fixed-width") {
        enter_fixed_mode();
        return true;
    }

    if (content === "/settings") {
        browser_history.go_to_location("settings/your-account");
        return true;
    }

    if (content.indexOf("/digress") === 0) {
        if (compose_state.get_message_type() !== "stream") {
            // digress can be used only in streams
            return true;
        }

        let param = content.slice(8);
        param = param.trim();

        // A valid param will now be of the form #**stream name>topic name**
        const new_stream_name_start = param.indexOf("#**") + 3;
        const new_topic_start = param.indexOf(">") + 1;
        const new_topic_end = param.lastIndexOf("**");

        if (
            new_stream_name_start === 3 &&
            new_topic_start > new_stream_name_start &&
            new_topic_end > new_topic_start &&
            param.endsWith("**")
        ) {
            const new_stream_name = param.slice(new_stream_name_start, new_topic_start - 1);
            const new_topic = param.slice(new_topic_start, new_topic_end);

            const old_stream_name = compose_state.stream_name();
            const old_topic = compose_state.topic();

            digress({
                old_stream: old_stream_name,
                old_topic,
                new_stream: new_stream_name,
                new_topic,
            });
            return true;
        }
    }

    // It is incredibly important here to return false
    // if we don't see an actual zcommand, so that compose.js
    // knows this is a normal message.
    return false;
}
