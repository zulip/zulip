import ClipboardJS from "clipboard";
import $ from "jquery";

import render_add_new_bot_form from "../templates/settings/add_new_bot_form.hbs";
import render_bot_avatar_row from "../templates/settings/bot_avatar_row.hbs";
import render_bot_settings_tip from "../templates/settings/bot_settings_tip.hbs";

import * as avatar from "./avatar";
import * as bot_data from "./bot_data";
import * as channel from "./channel";
import * as components from "./components";
import {show_copied_confirmation} from "./copied_tooltip";
import {csrf_token} from "./csrf";
import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import * as integration_url_modal from "./integration_url_modal";
import * as list_widget from "./list_widget";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_data from "./settings_data";
import {current_user, realm} from "./state_data";
import * as ui_report from "./ui_report";
import * as user_deactivation_ui from "./user_deactivation_ui";
import * as user_profile from "./user_profile";

const INCOMING_WEBHOOK_BOT_TYPE = 2;
const OUTGOING_WEBHOOK_BOT_TYPE = "3";
const OUTGOING_WEBHOOK_BOT_TYPE_INT = 3;
const EMBEDDED_BOT_TYPE = "4";

function add_bot_row(info) {
    const $row = $(render_bot_avatar_row(info));
    if (info.is_active) {
        $("#active_bots_list").append($row);
    } else {
        $("#inactive_bots_list").append($row);
    }
}

function is_local_part(value) {
    // Adapted from Django's EmailValidator
    return /^[\w!#$%&'*+/=?^`{|}~-]+(\.[\w!#$%&'*+/=?^`{|}~-]+)*$/i.test(value);
}

export function render_bots() {
    $("#active_bots_list").empty();
    $("#inactive_bots_list").empty();

    const all_bots_for_current_user = bot_data.get_all_bots_for_current_user();
    let user_owns_an_active_outgoing_webhook_bot = false;

    for (const elem of all_bots_for_current_user) {
        add_bot_row({
            name: elem.full_name,
            email: elem.email,
            user_id: elem.user_id,
            type: settings_data.bot_type_id_to_string(elem.bot_type),
            avatar_url: elem.avatar_url,
            api_key: elem.api_key,
            is_active: elem.is_active,
            is_incoming_webhook_bot: elem.bot_type === INCOMING_WEBHOOK_BOT_TYPE,
            zuliprc: "zuliprc", // Most browsers do not allow filename starting with `.`
        });
        user_owns_an_active_outgoing_webhook_bot =
            user_owns_an_active_outgoing_webhook_bot ||
            (elem.is_active && elem.bot_type === OUTGOING_WEBHOOK_BOT_TYPE_INT);
    }

    if (user_owns_an_active_outgoing_webhook_bot) {
        $("#active_bots_list_container .config-download-text").show();
    } else {
        $("#active_bots_list_container .config-download-text").hide();
    }

    list_widget.render_empty_list_message_if_needed($("#active_bots_list"));
    list_widget.render_empty_list_message_if_needed($("#inactive_bots_list"));
}

export function generate_zuliprc_url(bot_id) {
    const bot = bot_data.get(bot_id);
    const data = generate_zuliprc_content(bot);
    return encode_zuliprc_as_url(data);
}

export function encode_zuliprc_as_url(zuliprc) {
    return "data:application/octet-stream;charset=utf-8," + encodeURIComponent(zuliprc);
}

export function generate_zuliprc_content(bot) {
    let token;
    // For outgoing webhooks, include the token in the zuliprc.
    // It's needed for authenticating to the Botserver.
    if (bot.bot_type === 3) {
        token = bot_data.get_services(bot.user_id)[0].token;
    }
    return (
        "[api]" +
        "\nemail=" +
        bot.email +
        "\nkey=" +
        bot.api_key +
        "\nsite=" +
        realm.realm_uri +
        (token === undefined ? "" : "\ntoken=" + token) +
        // Some tools would not work in files without a trailing new line.
        "\n"
    );
}

export function generate_botserverrc_content(email, api_key, token) {
    return (
        "[]" +
        "\nemail=" +
        email +
        "\nkey=" +
        api_key +
        "\nsite=" +
        realm.realm_uri +
        "\ntoken=" +
        token +
        "\n"
    );
}

export const bot_creation_policy_values = {
    admins_only: {
        code: 3,
        description: $t({defaultMessage: "Admins"}),
    },
    everyone: {
        code: 1,
        description: $t({defaultMessage: "Admins, moderators and members"}),
    },
    restricted: {
        code: 2,
        description: $t({
            defaultMessage: "Admins, moderators and members, but only admins can add generic bots",
        }),
    },
};

export function can_create_new_bots() {
    if (current_user.is_admin) {
        return true;
    }

    if (current_user.is_guest) {
        return false;
    }

    return realm.realm_bot_creation_policy !== bot_creation_policy_values.admins_only.code;
}

export function update_bot_settings_tip($tip_container, for_org_settings) {
    if (
        !current_user.is_admin &&
        realm.realm_bot_creation_policy === bot_creation_policy_values.everyone.code
    ) {
        $tip_container.hide();
        return;
    }

    if (current_user.is_admin && !for_org_settings) {
        $tip_container.hide();
        return;
    }

    const rendered_tip = render_bot_settings_tip({
        realm_bot_creation_policy: realm.realm_bot_creation_policy,
        permission_type: bot_creation_policy_values,
    });
    $tip_container.show();
    $tip_container.html(rendered_tip);
}

function update_add_bot_button() {
    if (can_create_new_bots()) {
        $("#bot-settings .add-a-new-bot").show();
        $("#admin-bot-list .add-new-bots").show();
        $("#admin-bot-list .manage-your-bots").hide();
        $(".org-settings-list li[data-section='bot-list-admin'] .locked").hide();
    } else {
        $("#bot-settings .add-a-new-bot").hide();
        $("#admin-bot-list .add-new-bots").hide();
        $(".org-settings-list li[data-section='bot-list-admin'] .locked").show();

        if (bot_data.get_all_bots_for_current_user().length > 0) {
            $("#admin-bot-list .manage-your-bots").show();
        }
    }
}

export function update_bot_permissions_ui() {
    update_bot_settings_tip($("#admin-bot-settings-tip"), true);
    update_bot_settings_tip($("#personal-bot-settings-tip"), false);
    update_add_bot_button();
    $("#id_realm_bot_creation_policy").val(realm.realm_bot_creation_policy);
}

export function add_a_new_bot() {
    const html_body = render_add_new_bot_form({
        bot_types: page_params.bot_types,
        realm_embedded_bots: realm.realm_embedded_bots,
        realm_bot_domain: realm.realm_bot_domain,
    });

    let create_avatar_widget;

    function create_a_new_bot() {
        const bot_type = $("#create_bot_type").val();
        const full_name = $("#create_bot_name").val();
        const short_name = $("#create_bot_short_name").val() || $("#create_bot_short_name").text();
        const payload_url = $("#create_payload_url").val();
        const interface_type = $("#create_interface_type").val();
        const service_name = $("#select_service_name").val();
        const formData = new FormData();

        formData.append("csrfmiddlewaretoken", csrf_token);
        formData.append("bot_type", bot_type);
        formData.append("full_name", full_name);
        formData.append("short_name", short_name);

        // If the selected bot_type is Outgoing webhook
        if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
            formData.append("payload_url", JSON.stringify(payload_url));
            formData.append("interface_type", interface_type);
        } else if (bot_type === EMBEDDED_BOT_TYPE) {
            formData.append("service_name", service_name);
            const config_data = {};
            $(`#config_inputbox [name*='${CSS.escape(service_name)}'] input`).each(function () {
                config_data[$(this).attr("name")] = $(this).val();
            });
            formData.append("config_data", JSON.stringify(config_data));
        }
        for (const [i, file] of Array.prototype.entries.call(
            $("#bot_avatar_file_input")[0].files,
        )) {
            formData.append("file-" + i, file);
        }

        channel.post({
            url: "/json/bots",
            data: formData,
            cache: false,
            processData: false,
            contentType: false,
            success() {
                create_avatar_widget.clear();
                dialog_widget.close();
            },
            error(xhr) {
                ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
                dialog_widget.hide_dialog_spinner();
            },
        });
    }

    function set_up_form_fields() {
        $("#payload_url_inputbox").hide();
        $("#create_payload_url").val("");
        $("#service_name_list").hide();
        $("#config_inputbox").hide();
        const selected_embedded_bot = "converter";
        $("#select_service_name").val(selected_embedded_bot); // TODO: Use 'select a bot'.
        $("#config_inputbox").children().hide();
        $(`[name*='${CSS.escape(selected_embedded_bot)}']`).show();

        create_avatar_widget = avatar.build_bot_create_widget();

        $("#create_bot_type").on("change", () => {
            const bot_type = $("#create_bot_type").val();
            // For "generic bot" or "incoming webhook" both these fields need not be displayed.
            $("#service_name_list").hide();
            $("#select_service_name").removeClass("required");
            $("#config_inputbox").hide();

            $("#payload_url_inputbox").hide();
            $("#create_payload_url").removeClass("required");
            if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
                $("#payload_url_inputbox").show();
                $("#create_payload_url").addClass("required");
            } else if (bot_type === EMBEDDED_BOT_TYPE) {
                $("#service_name_list").show();
                $("#select_service_name").addClass("required");
                $("#select_service_name").trigger("change");
                $("#config_inputbox").show();
            }
        });

        $("#select_service_name").on("change", () => {
            $("#config_inputbox").children().hide();
            const selected_bot = $("#select_service_name").val();
            $(`[name*='${CSS.escape(selected_bot)}']`).show();
        });
    }

    function validate_input() {
        const bot_short_name = $("#create_bot_short_name").val();

        if (is_local_part(bot_short_name)) {
            return true;
        }
        ui_report.error(
            $t_html({
                defaultMessage: "Please only use characters that are valid in an email address",
            }),
            undefined,
            $("#dialog_error"),
        );
        return false;
    }

    dialog_widget.launch({
        form_id: "create_bot_form",
        help_link: "/help/add-a-bot-or-integration",
        html_body,
        html_heading: $t_html({defaultMessage: "Add a new bot"}),
        html_submit_button: $t_html({defaultMessage: "Add"}),
        loading_spinner: true,
        on_click: create_a_new_bot,
        on_shown: () => $("#create_bot_type").trigger("focus"),
        post_render: set_up_form_fields,
        validate_input,
    });
}

export function set_up() {
    $("#download_botserverrc").on("click", function () {
        let content = "";

        for (const bot of bot_data.get_all_bots_for_current_user()) {
            if (bot.is_active && bot.bot_type === OUTGOING_WEBHOOK_BOT_TYPE_INT) {
                const bot_token = bot_data.get_services(bot.user_id)[0].token;
                content += generate_botserverrc_content(bot.email, bot.api_key, bot_token);
            }
        }

        $(this).attr(
            "href",
            "data:application/octet-stream;charset=utf-8," + encodeURIComponent(content),
        );
    });

    const toggler = components.toggle({
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "Active bots"}), key: "active-bots"},
            {label: $t({defaultMessage: "Inactive bots"}), key: "inactive-bots"},
        ],
        callback(_name, key) {
            $(".bots_section").hide();
            $(`[data-bot-settings-section="${CSS.escape(key)}"]`).show();
        },
    });

    toggler.get().prependTo($("#bot-settings .tab-container"));
    toggler.goto("active-bots");

    render_bots();

    $("#active_bots_list").on("click", "button.deactivate_bot", (e) => {
        const bot_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);

        function handle_confirm() {
            const url = "/json/bots/" + encodeURIComponent(bot_id);
            const opts = {
                success_continuation() {
                    const $row = $(e.currentTarget).closest("li");
                    $row.hide("slow", () => {
                        $row.remove();
                    });
                },
            };
            dialog_widget.submit_api_request(channel.del, url, {}, opts);
        }
        user_deactivation_ui.confirm_bot_deactivation(bot_id, handle_confirm, true);
    });

    $("#inactive_bots_list").on("click", "button.reactivate_bot", (e) => {
        const user_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        e.stopPropagation();
        e.preventDefault();

        function handle_confirm() {
            channel.post({
                url: "/json/users/" + encodeURIComponent(user_id) + "/reactivate",
                success() {
                    dialog_widget.close();
                },
                error(xhr) {
                    ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
                    dialog_widget.hide_dialog_spinner();
                },
            });
        }

        user_deactivation_ui.confirm_reactivation(user_id, handle_confirm, true);
    });

    $("#active_bots_list").on("click", "button.bot-card-regenerate-bot-api-key", (e) => {
        const bot_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        channel.post({
            url: "/json/bots/" + encodeURIComponent(bot_id) + "/api_key/regenerate",
            success(data) {
                const $row = $(e.currentTarget).closest("li");
                $row.find(".bot-card-api-key").find(".value").text(data.api_key);
                $row.find(".bot-card-api-key-error").hide();
            },
            error(xhr) {
                if (xhr.responseJSON?.msg) {
                    const $row = $(e.currentTarget).closest("li");
                    $row.find(".bot-card-api-key-error").text(xhr.responseJSON.msg).show();
                }
            },
        });
    });

    $("#active_bots_list").on("click", "button.open_edit_bot_form", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const $li = $(e.currentTarget).closest("li");
        const bot_id = Number.parseInt($li.find(".bot-card-info").attr("data-user-id"), 10);
        const bot = people.get_by_user_id(bot_id);
        user_profile.show_user_profile(bot, "manage-profile-tab");
    });

    $("#active_bots_list").on("click", "a.download_bot_zuliprc", function () {
        const $bot_info = $(this).closest(".bot-information-box").find(".bot-card-info");
        const bot_id = Number.parseInt($bot_info.attr("data-user-id"), 10);
        $(this).attr("href", generate_zuliprc_url(bot_id));
    });

    $("#active_bots_list").on("click", "button.open_bots_subscribed_streams", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const bot_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        const bot = people.get_by_user_id(bot_id);
        user_profile.show_user_profile(bot, "user-profile-streams-tab");
    });

    $("#active_bots_list").on("click", "button.open-generate-integration-url-modal", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const api_key = $(e.currentTarget).attr("data-api-key");
        integration_url_modal.show_generate_integration_url_modal(api_key);
    });

    const clipboard = new ClipboardJS("#copy_zuliprc", {
        text(trigger) {
            const $bot_info = $(trigger).closest(".bot-information-box").find(".bot-card-info");
            const bot_id = Number.parseInt($bot_info.attr("data-user-id"), 10);
            const bot = bot_data.get(bot_id);
            const data = generate_zuliprc_content(bot);
            return data;
        },
    });

    // Show a tippy tooltip when the bot zuliprc is copied
    clipboard.on("success", (e) => {
        show_copied_confirmation(e.trigger);
    });

    $("#bot-settings .add-a-new-bot").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        add_a_new_bot();
    });
}
