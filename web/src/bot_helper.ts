import ClipboardJS from "clipboard";
import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as bot_data from "./bot_data.ts";
import * as channel from "./channel.ts";
import {show_copied_confirmation} from "./copied_tooltip.ts";
import {realm} from "./state_data.ts";

export function validate_bot_short_name(value: string): boolean {
    // Adapted from Django's EmailValidator
    return /^[\w!#$%&'*+/=?^`{|}~-]+(\.[\w!#$%&'*+/=?^`{|}~-]+)*$/i.test(value);
}

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

export function initialize_clipboard_handlers(): void {
    new ClipboardJS("#copy-api-key-button", {
        text(trigger) {
            const data = $(trigger).closest("span").attr("data-api-key") ?? "";
            return data;
        },
    }).on("success", (e) => {
        assert(e.trigger instanceof HTMLElement);
        show_copied_confirmation(e.trigger, {
            show_check_icon: true,
        });
    });

    new ClipboardJS("#copy-zuliprc-config", {
        text(trigger) {
            const $bot_info = $(trigger).closest("#bot-edit-form");
            const bot_id = Number.parseInt($bot_info.attr("data-user-id")!, 10);
            const bot = bot_data.get(bot_id);
            assert(bot !== undefined);
            const data = generate_zuliprc_content(bot);
            return data;
        },
    }).on("success", (e) => {
        assert(e.trigger instanceof HTMLElement);
        show_copied_confirmation(e.trigger, {
            show_check_icon: true,
        });
    });
}

export function initialize_bot_click_handlers(): void {
    $("body").on("click", "button.bot-modal-regenerate-bot-api-key", (e) => {
        e.preventDefault();
        const bot_id = Number.parseInt(
            $(e.currentTarget).closest("span").attr("data-user-id")!,
            10,
        );
        const $row = $(e.currentTarget).closest(".input-group");

        void channel.post({
            url: `/json/bots/${encodeURIComponent(bot_id)}/api_key/regenerate`,
            success(data) {
                const parsed_data = z
                    .object({
                        api_key: z.string(),
                    })
                    .parse(data);

                $row.find(".api-key").val(parsed_data.api_key);
                $row.find("span[data-api-key]").attr("data-api-key", parsed_data.api_key);
                $row.find(".bot-modal-api-key-error").hide();
            },
            error(xhr) {
                const parsed = z.object({msg: z.string()}).safeParse(xhr.responseJSON);
                if (parsed.success && parsed.data.msg) {
                    $row.find(".bot-modal-api-key-error").text(parsed.data.msg).show();
                }
            },
        });
    });

    $("body").on("click", "button.download-bot-zuliprc", function () {
        const $bot_info = $(this).closest("#bot-edit-form");
        const bot_id = Number.parseInt($bot_info.attr("data-user-id")!, 10);
        const bot_email = $bot_info.attr("data-email");

        // Select the <a> element by matching data-email.
        const $zuliprc_link = $(`.hidden-zuliprc-download[data-email="${bot_email}"]`);
        $zuliprc_link.attr("href", generate_zuliprc_url(bot_id));
        $zuliprc_link[0]?.click();
    });
}
