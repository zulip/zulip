import $ from "jquery";
import assert from "minimalistic-assert";

import render_add_new_bot_form from "../templates/settings/add_new_bot_form.hbs";
import render_bot_settings_tip from "../templates/settings/bot_settings_tip.hbs";

import * as avatar from "./avatar.ts";
import * as bot_data from "./bot_data.ts";
import * as channel from "./channel.ts";
import {csrf_token} from "./csrf.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import {page_params} from "./page_params.ts";
import {current_user, realm} from "./state_data.ts";
import type {HTMLSelectOneElement} from "./types.ts";
import * as ui_report from "./ui_report.ts";
import type {UploadWidget} from "./upload_widget.ts";

const OUTGOING_WEBHOOK_BOT_TYPE = "3";
export const OUTGOING_WEBHOOK_BOT_TYPE_INT = 3;
const EMBEDDED_BOT_TYPE = "4";

function is_local_part(value: string): boolean {
    // Adapted from Django's EmailValidator
    return /^[\w!#$%&'*+/=?^`{|}~-]+(\.[\w!#$%&'*+/=?^`{|}~-]+)*$/i.test(value);
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

export function can_create_new_bots(): boolean {
    if (current_user.is_admin) {
        return true;
    }

    if (current_user.is_guest) {
        return false;
    }

    return realm.realm_bot_creation_policy !== bot_creation_policy_values.admins_only.code;
}

export function update_bot_settings_tip($tip_container: JQuery, for_org_settings: boolean): void {
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

function update_add_bot_button(): void {
    if (can_create_new_bots()) {
        $("#bot-settings .add-a-new-bot").show();
        $("#admin-bot-list .add-new-bots").show();
        $("#admin-bot-list .manage-your-bots").hide();
        $(".org-settings-list li[data-section='bots'] .locked").hide();
    } else {
        $("#bot-settings .add-a-new-bot").hide();
        $("#admin-bot-list .add-new-bots").hide();
        $(".org-settings-list li[data-section='bots'] .locked").show();

        if (bot_data.get_all_bots_for_current_user().length > 0) {
            $("#admin-bot-list .manage-your-bots").show();
        }
    }
}

export function update_bot_permissions_ui(): void {
    update_bot_settings_tip($("#admin-bot-settings-tip"), true);
    update_bot_settings_tip($("#personal-bot-settings-tip"), false);
    update_add_bot_button();
    $("#id_realm_bot_creation_policy").val(realm.realm_bot_creation_policy);
}

export function add_a_new_bot(): void {
    const html_body = render_add_new_bot_form({
        bot_types: page_params.bot_types,
        realm_embedded_bots: realm.realm_embedded_bots,
        realm_bot_domain: realm.realm_bot_domain,
    });

    let create_avatar_widget: UploadWidget;

    function create_a_new_bot(): void {
        const bot_type = $<HTMLSelectOneElement>("select:not([multiple])#create_bot_type").val()!;
        const full_name = $<HTMLInputElement>("input#create_bot_name").val()!;
        const short_name =
            $<HTMLInputElement>("input#create_bot_short_name").val() ??
            $("#create_bot_short_name").text();
        const payload_url = $("#create_payload_url").val();
        const interface_type = $<HTMLSelectOneElement>(
            "select:not([multiple])#create_interface_type",
        ).val()!;
        const service_name = $<HTMLSelectOneElement>(
            "select:not([multiple])#select_service_name",
        ).val()!;
        const formData = new FormData();
        assert(csrf_token !== undefined);
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
            const config_data: Record<string, string> = {};
            $<HTMLInputElement>(
                `#config_inputbox [name*='${CSS.escape(service_name)}'] input`,
            ).each(function () {
                const key = $(this).attr("name")!;
                const value = $(this).val()!;
                config_data[key] = value;
            });
            formData.append("config_data", JSON.stringify(config_data));
        }
        const files = $<HTMLInputElement>("input#bot_avatar_file_input")[0]!.files;
        assert(files !== null);
        for (const [i, file] of [...files].entries()) {
            formData.append("file-" + i, file);
        }

        void channel.post({
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

    function set_up_form_fields(): void {
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
            const selected_bot = $<HTMLSelectOneElement>(
                "select:not([multiple])#select_service_name",
            ).val()!;
            $(`[name*='${CSS.escape(selected_bot)}']`).show();
        });
    }

    function validate_input(): boolean {
        const bot_short_name = $<HTMLInputElement>("input#create_bot_short_name").val()!;

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

export function set_up(): void {
    $("#bot-settings .add-a-new-bot").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        add_a_new_bot();
    });
}
