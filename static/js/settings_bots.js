import ClipboardJS from "clipboard";
import $ from "jquery";

import render_settings_deactivation_bot_modal from "../templates/confirm_dialog/confirm_deactivate_bot.hbs";
import render_add_new_bot_form from "../templates/settings/add_new_bot_form.hbs";
import render_bot_avatar_row from "../templates/settings/bot_avatar_row.hbs";
import render_edit_bot_form from "../templates/settings/edit_bot_form.hbs";
import render_settings_edit_embedded_bot_service from "../templates/settings/edit_embedded_bot_service.hbs";
import render_settings_edit_outgoing_webhook_service from "../templates/settings/edit_outgoing_webhook_service.hbs";

import * as avatar from "./avatar";
import * as blueslip from "./blueslip";
import * as bot_data from "./bot_data";
import * as channel from "./channel";
import {csrf_token} from "./csrf";
import * as dialog_widget from "./dialog_widget";
import {DropdownListWidget} from "./dropdown_list_widget";
import {$t, $t_html} from "./i18n";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_config from "./settings_config";
import * as settings_users from "./settings_users";
import * as ui_report from "./ui_report";
import * as user_profile from "./user_profile";

const OUTGOING_WEBHOOK_BOT_TYPE = "3";
const EMBEDDED_BOT_TYPE = "4";

export function hide_errors() {
    $("#bot_table_error").hide();
    $(".bot_error").hide();
}

const focus_tab = {
    active_bots_tab() {
        $("#bots_lists_navbar .active").removeClass("active");
        $("#bots_lists_navbar .active-bots-tab").addClass("active");
        $("#active_bots_list").show();
        $("#inactive_bots_list").hide();
        hide_errors();
    },
    inactive_bots_tab() {
        $("#bots_lists_navbar .active").removeClass("active");
        $("#bots_lists_navbar .inactive-bots-tab").addClass("active");
        $("#active_bots_list").hide();
        $("#inactive_bots_list").show();
        hide_errors();
    },
};

export function get_bot_info_div(bot_id) {
    const sel = `.bot_info[data-user-id="${CSS.escape(bot_id)}"]`;
    return $(sel).expectOne();
}

export function bot_error(bot_id, xhr) {
    const $bot_info = get_bot_info_div(bot_id);
    const $bot_error_div = $bot_info.find(".bot_error");
    $bot_error_div.text(JSON.parse(xhr.responseText).msg);
    $bot_error_div.show();
    const $bot_box = $bot_info.closest(".bot-information-box");
    $bot_box.scrollTop($bot_box[0].scrollHeight - $bot_box[0].clientHeight);
}

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

export function type_id_to_string(type_id) {
    return page_params.bot_types.find((bot_type) => bot_type.type_id === type_id).name;
}

export function render_bots() {
    $("#active_bots_list").empty();
    $("#inactive_bots_list").empty();

    const all_bots_for_current_user = bot_data.get_all_bots_for_current_user();
    let user_owns_an_active_bot = false;

    for (const elem of all_bots_for_current_user) {
        add_bot_row({
            name: elem.full_name,
            email: elem.email,
            user_id: elem.user_id,
            type: type_id_to_string(elem.bot_type),
            avatar_url: elem.avatar_url,
            api_key: elem.api_key,
            is_active: elem.is_active,
            zuliprc: "zuliprc", // Most browsers do not allow filename starting with `.`
        });
        user_owns_an_active_bot = user_owns_an_active_bot || elem.is_active;
    }
}

export function generate_zuliprc_uri(bot_id) {
    const bot = bot_data.get(bot_id);
    const data = generate_zuliprc_content(bot);
    return encode_zuliprc_as_uri(data);
}

export function encode_zuliprc_as_uri(zuliprc) {
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
        page_params.realm_uri +
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
        page_params.realm_uri +
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
    if (page_params.is_admin) {
        return true;
    }

    if (page_params.is_guest) {
        return false;
    }

    return page_params.realm_bot_creation_policy !== bot_creation_policy_values.admins_only.code;
}

export function update_bot_settings_tip() {
    const permission_type = bot_creation_policy_values;
    const current_permission = page_params.realm_bot_creation_policy;
    let tip_text;
    if (current_permission === permission_type.admins_only.code) {
        tip_text = $t({
            defaultMessage: "Only organization administrators can add bots to this organization.",
        });
    } else if (current_permission === permission_type.restricted.code) {
        tip_text = $t({defaultMessage: "Only organization administrators can add generic bots."});
    } else {
        tip_text = $t({defaultMessage: "Anyone in this organization can add bots."});
    }
    $(".bot-settings-tip").text(tip_text);
}

function update_add_bot_button() {
    if (can_create_new_bots()) {
        $("#bot-settings .add-a-new-bot").show();
        $("#admin-bot-list .add-a-new-bot").show();
    } else {
        $("#bot-settings .add-a-new-bot").hide();
        $("#admin-bot-list .add-a-new-bot").hide();
    }
}

export function update_bot_permissions_ui() {
    update_bot_settings_tip();
    hide_errors();
    update_add_bot_button();
    $("#id_realm_bot_creation_policy").val(page_params.realm_bot_creation_policy);
}

export function add_a_new_bot() {
    const html_body = render_add_new_bot_form({
        bot_types: page_params.bot_types,
        realm_embedded_bots: page_params.realm_embedded_bots,
        realm_bot_domain: page_params.realm_bot_domain,
    });

    let create_avatar_widget;

    function create_a_new_bot() {
        const bot_type = $("#create_bot_type :selected").val();
        const full_name = $("#create_bot_name").val();
        const short_name = $("#create_bot_short_name").val() || $("#create_bot_short_name").text();
        const payload_url = $("#create_payload_url").val();
        const interface_type = $("#create_interface_type").val();
        const service_name = $("#select_service_name :selected").val();
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
                hide_errors();
                create_avatar_widget.clear();
                dialog_widget.close_modal();
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
            const bot_type = $("#create_bot_type :selected").val();
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
            const selected_bot = $("#select_service_name :selected").val();
            $(`[name*='${CSS.escape(selected_bot)}']`).show();
        });
    }

    function validate_input(e) {
        e.preventDefault();
        e.stopPropagation();

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

export function confirm_bot_deactivation(bot_id, handle_confirm, loading_spinner) {
    const bot = people.get_by_user_id(bot_id);
    const html_body = render_settings_deactivation_bot_modal();

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Deactivate {name}?"}, {name: bot.full_name}),
        help_link: "/help/deactivate-or-reactivate-a-bot",
        html_body,
        html_submit_button: $t_html({defaultMessage: "Deactivate"}),
        on_click: handle_confirm,
        loading_spinner,
    });
}

export function show_edit_bot_info_modal(user_id, from_user_info_popover) {
    const bot = people.get_by_user_id(user_id);

    if (!bot) {
        return;
    }

    const html_body = render_edit_bot_form({
        user_id,
        email: bot.email,
        full_name: bot.full_name,
        user_role_values: settings_config.user_role_values,
        disable_role_dropdown: !page_params.is_admin || (bot.is_owner && !page_params.is_owner),
    });

    let owner_widget;
    let avatar_widget;

    const bot_type = bot.bot_type.toString();
    const service = bot_data.get_services(bot.user_id)[0];

    function submit_bot_details() {
        const role = Number.parseInt($("#bot-role-select").val().trim(), 10);
        const $full_name = $("#dialog_widget_modal").find("input[name='full_name']");
        const url = "/json/bots/" + encodeURIComponent(bot.user_id);

        const formData = new FormData();
        formData.append("csrfmiddlewaretoken", csrf_token);
        formData.append("full_name", $full_name.val());
        formData.append("role", JSON.stringify(role));

        if (owner_widget === undefined) {
            blueslip.error("get_bot_owner_widget not called");
        }
        const human_user_id = owner_widget.value();
        if (human_user_id) {
            formData.append("bot_owner_id", human_user_id);
        }

        if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
            const service_payload_url = $("#edit_service_base_url").val();
            const service_interface = $("#edit_service_interface :selected").val();
            formData.append("service_payload_url", JSON.stringify(service_payload_url));
            formData.append("service_interface", service_interface);
        } else if (bot_type === EMBEDDED_BOT_TYPE && service !== undefined) {
            const config_data = {};
            $("#config_edit_inputbox input").each(function () {
                config_data[$(this).attr("name")] = $(this).val();
            });
            formData.append("config_data", JSON.stringify(config_data));
        }

        const $file_input = $("#bot-edit-form").find(".edit_bot_avatar_file_input");
        for (const [i, file] of Array.prototype.entries.call($file_input[0].files)) {
            formData.append("file-" + i, file);
        }

        channel.patch({
            url,
            data: formData,
            processData: false,
            contentType: false,
            success() {
                avatar_widget.clear();
                dialog_widget.close_modal();
            },
            error(xhr) {
                ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
                dialog_widget.hide_dialog_spinner();
            },
        });
    }

    function edit_bot_post_render() {
        const owner_id = bot_data.get(user_id).owner_id;

        const user_ids = people.get_active_human_ids();
        const users_list = user_ids.map((user_id) => ({
            name: people.get_full_name(user_id),
            value: user_id.toString(),
        }));

        const opts = {
            widget_name: "edit_bot_owner",
            data: users_list,
            default_text: $t({defaultMessage: "No owner"}),
            value: owner_id,
        };
        // Note: Rendering this is quite expensive in
        // organizations with 10Ks of users.
        owner_widget = new DropdownListWidget(opts);
        owner_widget.setup();

        $("#bot-role-select").val(bot.role);
        if (!page_params.is_owner) {
            $("#bot-role-select")
                .find(`option[value="${CSS.escape(settings_config.user_role_values.owner.code)}"]`)
                .hide();
        }

        avatar_widget = avatar.build_bot_edit_widget($("#bot-edit-form"));

        if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
            $("#service_data").append(
                render_settings_edit_outgoing_webhook_service({
                    service,
                }),
            );
            $("#edit_service_interface").val(service.interface);
        }
        if (bot_type === EMBEDDED_BOT_TYPE) {
            $("#service_data").append(
                render_settings_edit_embedded_bot_service({
                    service,
                }),
            );
        }

        $("#bot-edit-form").on("click", ".deactivate_bot_button", (e) => {
            e.preventDefault();
            e.stopPropagation();
            const bot_id = $("#bot-edit-form").data("user-id");
            function handle_confirm() {
                const url = "/json/bots/" + encodeURIComponent(bot_id);
                dialog_widget.submit_api_request(channel.del, url);
            }
            const open_deactivate_modal_callback = () =>
                confirm_bot_deactivation(bot_id, handle_confirm, true);
            dialog_widget.close_modal(open_deactivate_modal_callback);
        });
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Manage bot"}),
        html_body,
        id: "edit_bot_modal",
        on_click: submit_bot_details,
        post_render: edit_bot_post_render,
        loading_spinner: from_user_info_popover,
    });
}

export function set_up() {
    $("#download_botserverrc").on("click", function () {
        const OUTGOING_WEBHOOK_BOT_TYPE_INT = 3;
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

    // This needs to come before render_bots() in case the user
    // has no active bots
    focus_tab.active_bots_tab();
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
        confirm_bot_deactivation(bot_id, handle_confirm, true);
    });

    $("#inactive_bots_list").on("click", "button.reactivate_bot", (e) => {
        const user_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        e.stopPropagation();
        e.preventDefault();

        function handle_confirm() {
            channel.post({
                url: "/json/users/" + encodeURIComponent(user_id) + "/reactivate",
                success() {
                    dialog_widget.close_modal();
                },
                error(xhr) {
                    ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
                    dialog_widget.hide_dialog_spinner();
                },
            });
        }

        settings_users.confirm_reactivation(user_id, handle_confirm, true);
    });

    $("#active_bots_list").on("click", "button.regenerate_bot_api_key", (e) => {
        const bot_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        channel.post({
            url: "/json/bots/" + encodeURIComponent(bot_id) + "/api_key/regenerate",
            success(data) {
                const $row = $(e.currentTarget).closest("li");
                $row.find(".api_key").find(".value").text(data.api_key);
                $row.find("api_key_error").hide();
            },
            error(xhr) {
                const $row = $(e.currentTarget).closest("li");
                $row.find(".api_key_error").text(JSON.parse(xhr.responseText).msg).show();
            },
        });
    });

    $("#active_bots_list").on("click", "button.open_edit_bot_form", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const $li = $(e.currentTarget).closest("li");
        const bot_id = Number.parseInt($li.find(".bot_info").attr("data-user-id"), 10);
        show_edit_bot_info_modal(bot_id, false);
    });

    $("#active_bots_list").on("click", "a.download_bot_zuliprc", function () {
        const $bot_info = $(this).closest(".bot-information-box").find(".bot_info");
        const bot_id = Number.parseInt($bot_info.attr("data-user-id"), 10);
        $(this).attr("href", generate_zuliprc_uri(bot_id));
    });

    $("#active_bots_list").on("click", "button.open_bots_subscribed_streams", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const bot_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        const bot = people.get_by_user_id(bot_id);
        user_profile.show_user_profile(bot, "user-profile-streams-tab");
    });

    new ClipboardJS("#copy_zuliprc", {
        text(trigger) {
            const $bot_info = $(trigger).closest(".bot-information-box").find(".bot_info");
            const bot_id = Number.parseInt($bot_info.attr("data-user-id"), 10);
            const bot = bot_data.get(bot_id);
            const data = generate_zuliprc_content(bot);
            return data;
        },
    });

    $("#bots_lists_navbar .active-bots-tab").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        focus_tab.active_bots_tab();
    });

    $("#bots_lists_navbar .inactive-bots-tab").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        focus_tab.inactive_bots_tab();
    });

    $("#bot-settings .add-a-new-bot").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        add_a_new_bot();
    });
}
