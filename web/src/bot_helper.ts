import ClipboardJS from "clipboard";
import $ from "jquery";
import assert from "minimalistic-assert";
import {z} from "zod";

import * as bot_data from "./bot_data.ts";
import * as channel from "./channel.ts";
import { show_copied_confirmation } from "./copied_tooltip.ts";
import { realm } from "./state_data.ts";

export function generate_zuliprc_url(bot_id: number): string {
    const bot = bot_data.get(bot_id);
    assert(bot !== undefined);
    const data = generate_zuliprc_content(bot);
    return encode_zuliprc_as_url(data);
}

export function encode_zuliprc_as_url(zuliprc: string): string {
    return "data:application/octet-stream;charset=utf-8," + encodeURIComponent(zuliprc);
}

export function generate_zuliprc_content(bot: {
    bot_type?: number;
    user_id: number;
    email: string;
    api_key: string;
}): string {
    let token;
    // For outgoing webhooks, include the token in the zuliprc.
    // It's needed for authenticating to the Botserver.
    if (bot.bot_type === 3) {
        const services = bot_data.get_services(bot.user_id);
        assert(services !== undefined);
        const service = services[0];
        assert(service && "token" in service);
        token = service.token;
    }
    return (
        "[api]" +
        "\nemail=" +
        bot.email +
        "\nkey=" +
        bot.api_key +
        "\nsite=" +
        realm.realm_url +
        (token === undefined ? "" : "\ntoken=" + token) +
        // Some tools would not work in files without a trailing new line.
        "\n"
    );
}

export function generate_botserverrc_content(
    email: string,
    api_key: string,
    token: string,
): string {
    return (
        "[]" +
        "\nemail=" +
        email +
        "\nkey=" +
        api_key +
        "\nsite=" +
        realm.realm_url +
        "\ntoken=" +
        token +
        "\n"
    );
}

export function initialize_bot_click_handlers(): void {
    $("body").on("click", "button.bot-modal-regenerate-bot-api-key", (e) => {
        e.preventDefault();
        const bot_id = Number.parseInt($(e.currentTarget).attr("data-user-id") ?? "", 10);
        assert(!Number.isNaN(bot_id));

        void channel.post({
            url: `/json/bots/${encodeURIComponent(bot_id)}/api_key/regenerate`,
            success(data) {
                const parsedData = z
                    .object({
                        result: z.string(),
                        msg: z.string().optional(),
                        api_key: z.string(),
                    })
                    .parse(data);

                const $row = $("#bot-edit-form");
                $row.find(".bot-modal-info .api-key").val(parsedData.api_key);
                $row.find(".bot-modal-info #copy_api_key").attr("data-api-key", parsedData.api_key);
                $row.find(".bot-modal-api-key-error").hide();
            },
            error(xhr) {
                const parsedErrorData = z
                    .object({
                        result: z.literal("error"),
                        msg: z.string(),
                        code: z.string(),
                    })
                    .parse(xhr.responseJSON);

                if (parsedErrorData) {
                    const $row = $(e.currentTarget).closest("li");
                    $row.find(".bot-modal-api-key-error").text(parsedErrorData.msg).show();
                }
            },
        });
    });

    $("body").on("click", "a.download-bot-zuliprc", function () {
        const $bot_info = $(this).closest("#bot-edit-form");
        const bot_id = Number.parseInt($bot_info.attr("data-user-id") ?? "", 10);
        assert(!Number.isNaN(bot_id));
        $(this).attr("href", generate_zuliprc_url(bot_id));
    });
}

export function initialize_clipboard_handlers(): void {
    new ClipboardJS("#copy_api_key", {
        text(trigger) {
            const data = $(trigger).attr("data-api-key") ?? "";
            return data;
        },
    }).on("success", (e) => {
        assert(e.trigger instanceof HTMLElement);
        show_copied_confirmation(e.trigger, {
            show_check_icon: true,
        });
    });

    new ClipboardJS("#copy_zuliprc", {
        text(trigger) {
            const $bot_info = $(trigger).closest("#bot-edit-form");
            const bot_id = Number.parseInt($bot_info.attr("data-user-id") ?? "", 10);
            assert(!Number.isNaN(bot_id));
            const bot = bot_data.get(bot_id);
            if (bot) {
                const data = generate_zuliprc_content(bot);
                return data;
            }
            return "";
        },
    }).on("success", (e) => {
        assert(e.trigger instanceof HTMLElement);
        show_copied_confirmation(e.trigger, {
            show_check_icon: true,
        });
    });
}
