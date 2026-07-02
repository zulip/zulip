import ClipboardJS from "clipboard";
import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_bot_api_key_details from "../templates/settings/bot_api_key_details.hbs";

import * as banners from "./banners.ts";
import * as bot_data from "./bot_data.ts";
import type {Bot} from "./bot_data.ts";
import * as buttons from "./buttons.ts";
import * as channel from "./channel.ts";
import * as clipboard_handler from "./clipboard_handler.ts";
import {show_copied_confirmation} from "./copied_tooltip.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import {realm} from "./state_data.ts";

export function validate_bot_short_name(value: string): boolean {
    // Adapted from Django's EmailValidator
    return /^[\w!#$%&'*+/=?^`{|}~-]+(\.[\w!#$%&'*+/=?^`{|}~-]+)*$/i.test(value);
}

export function generate_zuliprc_url(bot_id: number, api_key: string): string {
    const bot = bot_data.get(bot_id);
    assert(bot !== undefined);
    const data = generate_zuliprc_content({...bot, api_key});
    return encode_zuliprc_as_url(data);
}

export function encode_zuliprc_as_url(zuliprc: string): string {
    return "data:application/octet-stream;charset=utf-8," + encodeURIComponent(zuliprc);
}

export function get_outgoing_webhook_token(bot_user_id: number): string {
    const services = bot_data.get_services(bot_user_id);
    assert(services !== undefined);
    const service = services[0];
    assert(service && "token" in service);
    return service.token;
}

export function generate_bot_config_file_content(
    heading: string,
    email: string,
    api_key: string,
    token?: string,
): string {
    const body = `
${heading}
email=${email}
key=${api_key}
site=${realm.realm_url}
${token !== undefined ? `token=${token}` : ""}
`.trim();

    // Some tools would not work in files without a trailing new line.
    return `${body}\n`;
}

export function generate_zuliprc_content(bot: {
    bot_type?: number;
    user_id: number;
    email: string;
    api_key: string;
}): string {
    let token: string | undefined;
    // For outgoing webhooks, include the token in the zuliprc.
    // It's needed for authenticating to the Botserver.
    if (bot.bot_type === 3) {
        token = get_outgoing_webhook_token(bot.user_id);
    }
    return generate_bot_config_file_content("[api]", bot.email, bot.api_key, token);
}

export async function fetch_bot_api_key(
    bot_id: number,
    $error_element: JQuery,
    $trigger?: JQuery,
): Promise<string | null> {
    try {
        if ($trigger !== undefined) {
            buttons.show_button_loading_indicator($trigger);
            $trigger.prop("disabled", true);
        }
        const raw_data = await channel.get({
            url: `/json/bots/${bot_id}/api_key`,
            error(xhr) {
                const error_message = channel.xhr_error_message(
                    $t_html({defaultMessage: "Failed"}),
                    xhr,
                );
                banners.open(
                    {
                        intent: "danger",
                        label: error_message,
                        buttons: [],
                        close_button: false,
                    },
                    $error_element,
                );
            },
        });

        const data = z
            .object({
                api_key: z.string(),
                msg: z.string(),
                result: z.string(),
            })
            .parse(raw_data);

        return data.api_key;
    } catch {
        return null;
    } finally {
        if ($trigger !== undefined) {
            buttons.hide_button_loading_indicator($trigger);
            $trigger.prop("disabled", false);
        }
    }
}

function initialize_api_key_clipboard_handlers(): void {
    new ClipboardJS("#copy-api-key-button", {
        text(trigger) {
            const data = $(trigger).closest(".bot-api-key-container").attr("data-api-key") ?? "";
            return data;
        },
    }).on("success", (e) => {
        assert(e.trigger instanceof HTMLElement);
        show_copied_confirmation(e.trigger, {
            show_check_icon: true,
        });
    });
}

async function copy_zuliprc_content(bot: Bot, api_key: string): Promise<void> {
    const zuliprc_content = generate_zuliprc_content({...bot, api_key});

    return new Promise((resolve) => {
        function handle_copy_event(e: ClipboardEvent): void {
            e.clipboardData?.setData("text/plain", zuliprc_content);
            e.preventDefault();
            resolve();
        }
        clipboard_handler.execute_copy(handle_copy_event, zuliprc_content);
    });
}

export async function show_api_key_modal(bot_id: number): Promise<void> {
    const api_key = await fetch_bot_api_key(
        bot_id,
        $("#bot-edit-form-error"),
        $("#bot-edit-form .show-api-key"),
    );

    if (!api_key) {
        $("#bot-edit-form").closest(".simplebar-content-wrapper").animate({scrollTop: 0}, "fast");
        return;
    }

    const bot = bot_data.get(bot_id)!;
    const modal_content_html = render_bot_api_key_details({
        bot_id,
        api_key,
    });
    dialog_widget.launch({
        modal_title_html: $t_html(
            {defaultMessage: "API key for {bot_name}"},
            {bot_name: bot.full_name},
        ),
        modal_content_html,
        id: "api-key-modal",
        single_footer_button: true,
        modal_submit_button_text: $t_html({defaultMessage: "Close"}),
        on_click() {
            return;
        },
        post_render: initialize_api_key_clipboard_handlers,
    });
}

// Focus goes to Cancel, not Confirm: Cancel takes the exact spot the
// regenerate icon was in, so a double-click (or a second Enter) backs out
// instead of rotating the key.
function show_api_key_regenerate_confirmation($container: JQuery): void {
    $container.find(".bot-modal-regenerate-bot-api-key").addClass("hide");
    $container.find(".copy-api-key").addClass("hide");
    $container.find(".bot-api-key-regenerate-warning").removeClass("hide");
    $container.find(".bot-modal-confirm-regenerate-bot-api-key").removeClass("hide");
    $container
        .find(".bot-modal-cancel-regenerate-bot-api-key")
        .removeClass("hide")
        .trigger("focus");
}

function hide_api_key_regenerate_confirmation($container: JQuery): void {
    $container.find(".bot-modal-cancel-regenerate-bot-api-key").addClass("hide");
    $container.find(".bot-modal-confirm-regenerate-bot-api-key").addClass("hide");
    $container.find(".bot-api-key-regenerate-warning").addClass("hide");
    $container.find(".copy-api-key").removeClass("hide");
    $container.find(".bot-modal-regenerate-bot-api-key").removeClass("hide").trigger("focus");
}

export function initialize_bot_click_handlers(): void {
    $("body").on("click", "button.bot-modal-regenerate-bot-api-key", (e) => {
        e.preventDefault();
        show_api_key_regenerate_confirmation($(e.currentTarget).closest(".bot-api-key-container"));
    });

    $("body").on("click", "button.bot-modal-cancel-regenerate-bot-api-key", (e) => {
        e.preventDefault();
        hide_api_key_regenerate_confirmation($(e.currentTarget).closest(".bot-api-key-container"));
    });

    $("body").on(
        "click",
        "button.bot-modal-confirm-regenerate-bot-api-key",
        function (this: HTMLElement, e) {
            e.preventDefault();
            const $button = $(this);
            const $container = $button.closest(".bot-api-key-container");
            const bot_id = Number.parseInt($container.attr("data-user-id")!, 10);

            $container.find(".bot-modal-cancel-regenerate-bot-api-key").addClass("hide");
            $button.prop("disabled", true);
            buttons.show_button_loading_indicator($button);
            void channel.post({
                url: `/json/bots/${encodeURIComponent(bot_id)}/api_key/regenerate`,
                success(data) {
                    const parsed_data = z.object({api_key: z.string()}).parse(data);
                    $container.find(".api-key").val(parsed_data.api_key);
                    $container.attr("data-api-key", parsed_data.api_key);
                    $container.find(".bot-modal-api-key-error").hide();
                },
                error(xhr) {
                    const parsed = z.object({msg: z.string()}).safeParse(xhr.responseJSON);
                    const message =
                        parsed.success && parsed.data.msg !== ""
                            ? parsed.data.msg
                            : $t({defaultMessage: "Failed to generate new API key"});
                    $container.find(".bot-modal-api-key-error").text(message).show();
                },
                complete() {
                    buttons.hide_button_loading_indicator($button);
                    hide_api_key_regenerate_confirmation($container);
                },
            });
        },
    );

    $("body").on("click", "button.download-bot-zuliprc", function () {
        void (async () => {
            const $bot_info = $(this).closest("#bot-edit-form");
            const bot_id = Number.parseInt($bot_info.attr("data-user-id")!, 10);
            const bot_email = $bot_info.attr("data-email");
            const api_key = await fetch_bot_api_key(bot_id, $("#bot-edit-form-error"), $(this));
            if (!api_key) {
                $("#bot-edit-form")
                    .closest(".simplebar-content-wrapper")
                    .animate({scrollTop: 0}, "fast");
                return;
            }

            // Select the <a> element by matching data-email.
            const $zuliprc_link = $(`.hidden-zuliprc-download[data-email="${bot_email}"]`);
            $zuliprc_link.attr("href", generate_zuliprc_url(bot_id, api_key));
            $zuliprc_link[0]?.click();
        })();
    });

    $("body").on("click", "#copy-zuliprc-config", function (this: HTMLElement) {
        void (async () => {
            const $bot_info = $(this).closest("#bot-edit-form");
            const bot_id = Number.parseInt($bot_info.attr("data-user-id")!, 10);
            const bot = bot_data.get(bot_id)!;
            const api_key = await fetch_bot_api_key(bot_id, $("#bot-edit-form-error"), $(this));
            if (!api_key) {
                $("#bot-edit-form")
                    .closest(".simplebar-content-wrapper")
                    .animate({scrollTop: 0}, "fast");
                return;
            }

            await copy_zuliprc_content(bot, api_key);
            show_copied_confirmation(this, {
                show_check_icon: true,
            });
        })();
    });
}
