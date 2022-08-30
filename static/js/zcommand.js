import * as channel from "./channel";
import * as compose_banner from "./compose_banner";
import * as dark_theme from "./dark_theme";
import * as feedback_widget from "./feedback_widget";
import {$t} from "./i18n";
import * as markdown from "./markdown";
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
            tell_user("server did not respond");
        },
    });
}

export function tell_user(msg) {
    // This is a bit hacky, but we don't have a super easy API now
    // for just telling users stuff.
    compose_banner.show_error_message(msg, compose_banner.CLASSNAMES.generic_compose_error);
}

export function switch_to_light_theme() {
    send({
        command: "/day",
        on_success(data) {
            dark_theme.disable();
            feedback_widget.show({
                populate($container) {
                    const rendered_msg = markdown.parse_non_message(data.msg);
                    $container.html(rendered_msg);
                },
                on_undo() {
                    send({
                        command: "/night",
                    });
                },
                title_text: $t({defaultMessage: "Light theme"}),
                undo_button_text: $t({defaultMessage: "Dark theme"}),
            });
        },
    });
}

export function switch_to_dark_theme() {
    send({
        command: "/night",
        on_success(data) {
            dark_theme.enable();
            feedback_widget.show({
                populate($container) {
                    const rendered_msg = markdown.parse_non_message(data.msg);
                    $container.html(rendered_msg);
                },
                on_undo() {
                    send({
                        command: "/day",
                    });
                },
                title_text: $t({defaultMessage: "Dark theme"}),
                undo_button_text: $t({defaultMessage: "Light theme"}),
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
                populate($container) {
                    const rendered_msg = markdown.parse_non_message(data.msg);
                    $container.html(rendered_msg);
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
                populate($container) {
                    const rendered_msg = markdown.parse_non_message(data.msg);
                    $container.html(rendered_msg);
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
        switch_to_light_theme();
        return true;
    }

    const night_commands = ["/night", "/dark"];
    if (night_commands.includes(content)) {
        switch_to_dark_theme();
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

    // It is incredibly important here to return false
    // if we don't see an actual zcommand, so that compose.js
    // knows this is a normal message.
    return false;
}
