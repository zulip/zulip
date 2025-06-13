import $ from "jquery";
import * as z from "zod/mini";

import * as channel from "./channel.ts";
import * as compose_banner from "./compose_banner.ts";
import * as feedback_widget from "./feedback_widget.ts";
import {$t} from "./i18n.ts";
import * as markdown from "./markdown.ts";
import * as settings_config from "./settings_config.ts";
import * as theme from "./theme.ts";

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
    and widgetize.ts

*/

const data_schema = z.object({
    msg: z.string(),
});

export function send(opts: {command: string; on_success?: (data: unknown) => void}): void {
    const command = opts.command;
    const on_success = opts.on_success;
    const data = {
        command,
    };

    void channel.post({
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

export function tell_user(msg: string): void {
    // This is a bit hacky, but we don't have a super easy API now
    // for just telling users stuff.
    compose_banner.show_error_message(
        msg,
        compose_banner.CLASSNAMES.generic_compose_error,
        $("#compose_banners"),
    );
}

export function switch_to_light_theme(): void {
    send({
        command: "/light",
        on_success(raw_data) {
            const data = data_schema.parse(raw_data);
            requestAnimationFrame(() => {
                theme.set_theme_and_update(settings_config.color_scheme_values.light.code);
            });
            feedback_widget.show({
                populate($container) {
                    const rendered_msg = markdown.parse_non_message(data.msg);
                    $container.html(rendered_msg);
                },
                on_undo() {
                    send({
                        command: "/dark",
                    });
                },
                title_text: $t({defaultMessage: "Light theme"}),
                undo_button_text: $t({defaultMessage: "Dark theme"}),
            });
        },
    });
}

export function switch_to_dark_theme(): void {
    send({
        command: "/dark",
        on_success(raw_data) {
            const data = data_schema.parse(raw_data);
            requestAnimationFrame(() => {
                theme.set_theme_and_update(settings_config.color_scheme_values.dark.code);
            });
            feedback_widget.show({
                populate($container) {
                    const rendered_msg = markdown.parse_non_message(data.msg);
                    $container.html(rendered_msg);
                },
                on_undo() {
                    send({
                        command: "/light",
                    });
                },
                title_text: $t({defaultMessage: "Dark theme"}),
                undo_button_text: $t({defaultMessage: "Light theme"}),
            });
        },
    });
}

export function process(message_content: string): boolean {
    const content = message_content.trim();

    if (content === "/ping") {
        const start_time = new Date();

        send({
            command: content,
            on_success() {
                const end_time = new Date();
                let diff = end_time.getTime() - start_time.getTime();
                diff = Math.round(diff);
                const msg = "ping time: " + diff + "ms";
                tell_user(msg);
            },
        });
        return true;
    }

    const light_commands = ["/day", "/light"];
    if (light_commands.includes(content)) {
        switch_to_light_theme();
        return true;
    }

    const dark_commands = ["/night", "/dark"];
    if (dark_commands.includes(content)) {
        switch_to_dark_theme();
        return true;
    }

    // It is incredibly important here to return false
    // if we don't see an actual zcommand, so that compose.js
    // knows this is a normal message.
    return false;
}
