import $ from "jquery";

import render_settings_deactivate_realm_modal from "../templates/confirm_dialog/confirm_deactivate_realm.hbs";
import render_settings_admin_auth_methods_list from "../templates/settings/admin_auth_methods_list.hbs";

import * as audible_notifications from "./audible_notifications";
import * as blueslip from "./blueslip";
import * as channel from "./channel";
import {csrf_token} from "./csrf";
import * as dialog_widget from "./dialog_widget";
import * as dropdown_widget from "./dropdown_widget";
import {$t, $t_html, get_language_name} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as loading from "./loading";
import * as pygments_data from "./pygments_data";
import * as realm_icon from "./realm_icon";
import * as realm_logo from "./realm_logo";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as settings_components from "./settings_components";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as settings_notifications from "./settings_notifications";
import * as settings_realm_domains from "./settings_realm_domains";
import * as settings_ui from "./settings_ui";
import {current_user, realm} from "./state_data";
import * as stream_settings_data from "./stream_settings_data";
import * as ui_report from "./ui_report";
import * as user_groups from "./user_groups";
import * as util from "./util";

const meta = {
    loaded: false,
};

export function reset() {
    meta.loaded = false;
}

const DISABLED_STATE_ID = -1;

export function maybe_disable_widgets() {
    if (current_user.is_owner) {
        return;
    }

    $(".organization-box [data-name='auth-methods']")
        .find("input, button, select, checked")
        .prop("disabled", true);

    if (current_user.is_admin) {
        $(".deactivate_realm_button").prop("disabled", true);
        $("#deactivate_realm_button_container").addClass("disabled_setting_tooltip");
        $("#org-message-retention").find("input, select").prop("disabled", true);
        $("#org-join-settings").find("input, select, button").prop("disabled", true);
        $("#id_realm_invite_required_label").parent().addClass("control-label-disabled");
        return;
    }

    $(".organization-box [data-name='organization-profile']")
        .find("input, textarea, button, select")
        .prop("disabled", true);

    $(".organization-box [data-name='organization-profile']").find(".image_upload_button").hide();

    $(".organization-box [data-name='organization-settings']")
        .find("input, textarea, button, select")
        .prop("disabled", true);

    $(".organization-box [data-name='organization-settings']")
        .find(".dropdown_list_reset_button")
        .hide();

    $(".organization-box [data-name='organization-settings']")
        .find(".control-label-disabled")
        .addClass("enabled");

    $(".organization-box [data-name='organization-permissions']")
        .find("input, textarea, button, select")
        .prop("disabled", true);

    $(".organization-box [data-name='organization-permissions']")
        .find(".control-label-disabled")
        .addClass("enabled");
}

export function get_organization_settings_options() {
    const options = {};
    options.common_policy_values = settings_components.get_sorted_options_list(
        settings_config.common_policy_values,
    );
    options.private_message_policy_values = settings_components.get_sorted_options_list(
        settings_config.private_message_policy_values,
    );
    options.wildcard_mention_policy_values = settings_components.get_sorted_options_list(
        settings_config.wildcard_mention_policy_values,
    );
    options.common_message_policy_values = settings_components.get_sorted_options_list(
        settings_config.common_message_policy_values,
    );
    options.invite_to_realm_policy_values = settings_components.get_sorted_options_list(
        settings_config.email_invite_to_realm_policy_values,
    );
    options.edit_topic_policy_values = settings_components.get_sorted_options_list(
        settings_config.edit_topic_policy_values,
    );
    options.move_messages_between_streams_policy_values =
        settings_components.get_sorted_options_list(
            settings_config.move_messages_between_streams_policy_values,
        );
    return options;
}

export function get_org_type_dropdown_options() {
    const current_org_type = realm.realm_org_type;
    if (current_org_type !== 0) {
        return settings_config.defined_org_type_values;
    }
    return settings_config.all_org_type_values;
}

const simple_dropdown_properties = [
    "realm_create_private_stream_policy",
    "realm_create_public_stream_policy",
    "realm_create_web_public_stream_policy",
    "realm_invite_to_stream_policy",
    "realm_user_group_edit_policy",
    "realm_private_message_policy",
    "realm_add_custom_emoji_policy",
    "realm_invite_to_realm_policy",
    "realm_wildcard_mention_policy",
    "realm_move_messages_between_streams_policy",
    "realm_edit_topic_policy",
    "realm_org_type",
];

function set_realm_waiting_period_setting() {
    const setting_value = realm.realm_waiting_period_threshold;
    const valid_limit_values = settings_config.waiting_period_threshold_dropdown_values.map(
        (x) => x.code,
    );

    if (valid_limit_values.includes(setting_value)) {
        $("#id_realm_waiting_period_threshold").val(setting_value);
    } else {
        $("#id_realm_waiting_period_threshold").val("custom_period");
    }

    $("#id_realm_waiting_period_threshold_custom_input").val(setting_value);
    settings_components.change_element_block_display_property(
        "id_realm_waiting_period_threshold_custom_input",
        $("#id_realm_waiting_period_threshold").val() === "custom_period",
    );
}

function update_jitsi_server_url_custom_input(dropdown_val) {
    const custom_input = "id_realm_jitsi_server_url_custom_input";
    settings_components.change_element_block_display_property(
        custom_input,
        dropdown_val === "custom",
    );

    if (dropdown_val !== "custom") {
        return;
    }

    const $custom_input_elem = $(`#${CSS.escape(custom_input)}`);
    $custom_input_elem.val(realm.realm_jitsi_server_url);
}

function set_jitsi_server_url_dropdown() {
    if (!settings_components.is_video_chat_provider_jitsi_meet()) {
        $("#realm_jitsi_server_url_setting").hide();
        return;
    }

    $("#realm_jitsi_server_url_setting").show();

    let dropdown_val = "server_default";
    if (realm.realm_jitsi_server_url) {
        dropdown_val = "custom";
    }

    $("#id_realm_jitsi_server_url").val(dropdown_val);
    update_jitsi_server_url_custom_input(dropdown_val);
}

function set_video_chat_provider_dropdown() {
    const chat_provider_id = realm.realm_video_chat_provider;
    $("#id_realm_video_chat_provider").val(chat_provider_id);

    set_jitsi_server_url_dropdown();
}

function set_giphy_rating_dropdown() {
    const rating_id = realm.realm_giphy_rating;
    $("#id_realm_giphy_rating").val(rating_id);
}

function update_message_edit_sub_settings(is_checked) {
    settings_ui.disable_sub_setting_onchange(
        is_checked,
        "id_realm_message_content_edit_limit_seconds",
        true,
    );
    settings_ui.disable_sub_setting_onchange(
        is_checked,
        "id_realm_message_content_edit_limit_minutes",
        true,
    );
}

function set_msg_edit_limit_dropdown() {
    settings_components.set_time_limit_setting("realm_message_content_edit_limit_seconds");
}

function message_move_limit_setting_enabled(related_setting_name) {
    const setting_value = Number.parseInt($(`#id_${CSS.escape(related_setting_name)}`).val(), 10);

    let settings_options;
    if (related_setting_name === "realm_edit_topic_policy") {
        settings_options = settings_config.edit_topic_policy_values;
    } else {
        settings_options = settings_config.move_messages_between_streams_policy_values;
    }

    if (setting_value === settings_options.by_admins_only.code) {
        return false;
    }

    if (setting_value === settings_options.by_moderators_only.code) {
        return false;
    }

    if (setting_value === settings_options.nobody.code) {
        return false;
    }

    return true;
}

function enable_or_disable_related_message_move_time_limit_setting(setting_name, disable_setting) {
    const $setting_elem = $(`#id_${CSS.escape(setting_name)}`);
    const $custom_input_elem = $setting_elem.parent().find(".time-limit-custom-input");

    settings_ui.disable_sub_setting_onchange(disable_setting, $setting_elem.attr("id"), true);
    settings_ui.disable_sub_setting_onchange(disable_setting, $custom_input_elem.attr("id"), true);
}

function set_msg_move_limit_setting(property_name) {
    settings_components.set_time_limit_setting(property_name);

    let disable_setting;
    if (property_name === "realm_move_messages_within_stream_limit_seconds") {
        disable_setting = message_move_limit_setting_enabled("realm_edit_topic_policy");
    } else {
        disable_setting = message_move_limit_setting_enabled(
            "realm_move_messages_between_streams_policy",
        );
    }
    enable_or_disable_related_message_move_time_limit_setting(property_name, disable_setting);
}

function message_delete_limit_setting_enabled(setting_value) {
    // This function is used to check whether the time-limit setting
    // should be enabled. The setting is disabled when delete_own_message_policy
    // is set to 'admins only' as admins can delete messages irrespective of
    // time limit.
    if (setting_value === settings_config.common_message_policy_values.by_admins_only.code) {
        return false;
    }
    return true;
}

function set_delete_own_message_policy_dropdown(setting_value) {
    $("#id_realm_delete_own_message_policy").val(setting_value);
    settings_ui.disable_sub_setting_onchange(
        message_delete_limit_setting_enabled(setting_value),
        "id_realm_message_content_delete_limit_seconds",
        true,
    );
    const limit_setting_dropdown_value = settings_components.get_time_limit_dropdown_setting_value(
        "realm_message_content_delete_limit_seconds",
    );
    if (limit_setting_dropdown_value === "custom_period") {
        settings_ui.disable_sub_setting_onchange(
            message_delete_limit_setting_enabled(setting_value),
            "id_realm_message_content_delete_limit_minutes",
            true,
        );
    }
}

function set_msg_delete_limit_dropdown() {
    settings_components.set_time_limit_setting("realm_message_content_delete_limit_seconds");
}

function get_dropdown_value_for_message_retention_setting(setting_value) {
    if (setting_value === settings_config.retain_message_forever) {
        return "unlimited";
    }

    if (setting_value === null) {
        return "realm_default";
    }

    return "custom_period";
}

export function set_message_retention_setting_dropdown(sub) {
    let property_name = "realm_message_retention_days";
    if (sub !== undefined) {
        property_name = "message_retention_days";
    }
    const setting_value = settings_components.get_property_value(property_name, false, sub);
    const dropdown_val = get_dropdown_value_for_message_retention_setting(setting_value);

    const $dropdown_elem = $(`#id_${CSS.escape(property_name)}`);
    $dropdown_elem.val(dropdown_val);

    const $custom_input_elem = $dropdown_elem
        .parent()
        .find(".message-retention-setting-custom-input")
        .val("");
    if (dropdown_val === "custom_period") {
        $custom_input_elem.val(setting_value);
    }

    settings_components.change_element_block_display_property(
        $custom_input_elem.attr("id"),
        dropdown_val === "custom_period",
    );
}

function set_org_join_restrictions_dropdown() {
    const value = settings_components.get_property_value("realm_org_join_restrictions");
    $("#id_realm_org_join_restrictions").val(value);
    settings_components.change_element_block_display_property(
        "allowed_domains_label",
        value === "only_selected_domain",
    );
}

function set_message_content_in_email_notifications_visibility() {
    settings_components.change_element_block_display_property(
        "message_content_in_email_notifications_label",
        realm.realm_message_content_allowed_in_email_notifications,
    );
}

function set_digest_emails_weekday_visibility() {
    settings_components.change_element_block_display_property(
        "id_realm_digest_weekday",
        realm.realm_digest_emails_enabled,
    );
}

function set_create_web_public_stream_dropdown_visibility() {
    settings_components.change_element_block_display_property(
        "id_realm_create_web_public_stream_policy",
        realm.server_web_public_streams_enabled &&
            realm.zulip_plan_is_not_limited &&
            realm.realm_enable_spectator_access,
    );
}

export function populate_realm_domains_label(realm_domains) {
    if (!meta.loaded) {
        return;
    }

    const domains_list = realm_domains.map((realm_domain) =>
        realm_domain.allow_subdomains ? "*." + realm_domain.domain : realm_domain.domain,
    );
    let domains = util.format_array_as_list(domains_list, "long", "conjunction");
    if (domains.length === 0) {
        domains = $t({defaultMessage: "None"});
    }
    $("#allowed_domains_label").text($t({defaultMessage: "Allowed domains: {domains}"}, {domains}));
}

function can_configure_auth_methods() {
    if (settings_data.user_email_not_configured()) {
        return false;
    }
    if (current_user.is_owner) {
        return true;
    }
    return false;
}

export function populate_auth_methods(auth_method_to_bool_map) {
    if (!meta.loaded) {
        return;
    }
    const $auth_methods_list = $("#id_realm_authentication_methods").expectOne();
    let rendered_auth_method_rows = "";
    for (const [auth_method, value] of Object.entries(auth_method_to_bool_map)) {
        // Certain authentication methods are not available to be enabled without
        // purchasing a plan, so we need to disable them in this UI.
        // The restriction only applies to **enabling** the auth method, so this
        // logic is dependent on the current value.
        // The reason for that is that if for any reason, the auth method is already
        // enabled (for example, because it was manually enabled for the organization
        // by request, as an exception) - the organization should be able to disable it
        // if they don't want it anymore.
        const cant_be_enabled =
            !realm.realm_authentication_methods[auth_method].available && !value;

        const render_args = {
            method: auth_method,
            enabled: value,
            disable_configure_auth_method: !can_configure_auth_methods() || cant_be_enabled,
            // The negated character class regexp serves as an allowlist - the replace() will
            // remove *all* symbols *but* digits (\d) and lowecase letters (a-z),
            // so that we can make assumptions on this string elsewhere in the code.
            // As a result, the only two "incoming" assumptions on the auth method name are:
            // 1) It contains at least one allowed symbol
            // 2) No two auth method names are identical after this allowlist filtering
            prefix: "id_authmethod" + auth_method.toLowerCase().replaceAll(/[^\da-z]/g, "") + "_",
        };

        if (cant_be_enabled) {
            render_args.unavailable_reason =
                realm.realm_authentication_methods[auth_method].unavailable_reason;
        }

        rendered_auth_method_rows += render_settings_admin_auth_methods_list(render_args);
    }
    $auth_methods_list.html(rendered_auth_method_rows);
}

function update_dependent_subsettings(property_name) {
    if (simple_dropdown_properties.includes(property_name)) {
        settings_components.set_property_dropdown_value(property_name);
        return;
    }

    switch (property_name) {
        case "realm_allow_message_editing":
            update_message_edit_sub_settings(realm.realm_allow_message_editing);
            break;
        case "realm_delete_own_message_policy":
            set_delete_own_message_policy_dropdown(realm.realm_delete_own_message_policy);
            break;
        case "realm_org_join_restrictions":
            set_org_join_restrictions_dropdown();
            break;
        case "realm_message_content_allowed_in_email_notifications":
            set_message_content_in_email_notifications_visibility();
            break;
        case "realm_digest_emails_enabled":
            settings_notifications.set_enable_digest_emails_visibility(
                $("#user-notification-settings"),
                false,
            );
            settings_notifications.set_enable_digest_emails_visibility(
                $("#realm-user-default-settings"),
                true,
            );
            set_digest_emails_weekday_visibility();
            break;
        case "realm_enable_spectator_access":
            set_create_web_public_stream_dropdown_visibility();
            break;
    }
}

export function discard_property_element_changes(elem, for_realm_default_settings, sub, group) {
    const $elem = $(elem);
    const property_name = settings_components.extract_property_name(
        $elem,
        for_realm_default_settings,
    );
    const property_value = settings_components.get_property_value(
        property_name,
        for_realm_default_settings,
        sub,
        group,
    );

    switch (property_name) {
        case "notification_sound":
            audible_notifications.update_notification_sound_source(
                $("audio#realm-default-notification-sound-audio"),
                {
                    notification_sound: property_value,
                },
            );
            settings_components.set_input_element_value($elem, property_value);
            break;
        case "realm_authentication_methods":
            populate_auth_methods(
                settings_components.realm_authentication_methods_to_boolean_dict(),
            );
            break;
        case "realm_new_stream_announcements_stream_id":
        case "realm_signup_announcements_stream_id":
        case "realm_zulip_update_announcements_stream_id":
        case "realm_default_code_block_language":
        case "can_remove_subscribers_group":
        case "realm_create_multiuse_invite_group":
        case "realm_can_access_all_users_group":
        case "can_mention_group":
            settings_components.set_dropdown_list_widget_setting_value(
                property_name,
                property_value,
            );
            break;
        case "realm_default_language":
            $("#org-notifications .language_selection_widget .language_selection_button span").attr(
                "data-language-code",
                property_value,
            );
            $("#org-notifications .language_selection_widget .language_selection_button span").text(
                get_language_name(property_value),
            );
            break;
        case "emojiset":
        case "user_list_style":
            // Because this widget has a radio button structure, it
            // needs custom reset code.
            $elem.find(`input[value='${CSS.escape(property_value)}']`).prop("checked", true);
            break;
        case "stream_privacy": {
            $elem.find(`input[value='${CSS.escape(property_value)}']`).prop("checked", true);

            // Hide stream privacy warning banner
            const $stream_permissions_warning_banner = $(
                "#stream_permission_settings .stream-permissions-warning-banner",
            );
            if (!$stream_permissions_warning_banner.is(":empty")) {
                $stream_permissions_warning_banner.empty();
            }
            break;
        }
        case "email_notifications_batching_period_seconds":
        case "email_notification_batching_period_edit_minutes":
            settings_notifications.set_notification_batching_ui(
                $("#realm-user-default-settings"),
                realm_user_settings_defaults.email_notifications_batching_period_seconds,
            );
            break;
        case "realm_org_type":
            settings_components.set_input_element_value($elem, property_value);
            // Remove 'unspecified' option (value=0) from realm_org_type
            // dropdown menu options whenever realm.realm_org_type
            // returns another value.
            if (property_value !== 0) {
                $("#id_realm_org_type option[value=0]").remove();
            }
            break;
        case "realm_message_content_edit_limit_seconds":
        case "realm_message_content_delete_limit_seconds":
            settings_components.set_time_limit_setting(property_name);
            break;
        case "realm_move_messages_within_stream_limit_seconds":
        case "realm_move_messages_between_streams_limit_seconds":
            set_msg_move_limit_setting(property_name);
            break;
        case "realm_video_chat_provider":
            set_video_chat_provider_dropdown();
            break;
        case "realm_jitsi_server_url":
            set_jitsi_server_url_dropdown();
            break;
        case "realm_message_retention_days":
        case "message_retention_days":
            set_message_retention_setting_dropdown(sub);
            break;
        case "realm_waiting_period_threshold":
            set_realm_waiting_period_setting();
            break;
        default:
            if (property_value !== undefined) {
                settings_components.set_input_element_value($elem, property_value);
            } else {
                blueslip.error("Element refers to unknown property", {property_name});
            }
    }

    update_dependent_subsettings(property_name);
}

export function deactivate_organization(e) {
    e.preventDefault();
    e.stopPropagation();

    function do_deactivate_realm() {
        channel.post({
            url: "/json/realm/deactivate",
            error(xhr) {
                ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
            },
        });
    }

    const html_body = render_settings_deactivate_realm_modal();

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Deactivate organization"}),
        help_link: "/help/deactivate-your-organization",
        html_body,
        on_click: do_deactivate_realm,
        close_on_submit: false,
        focus_submit_on_open: true,
        html_submit_button: $t_html({defaultMessage: "Confirm"}),
    });
}

export function sync_realm_settings(property) {
    if (!meta.loaded) {
        return;
    }

    switch (property) {
        case "emails_restricted_to_domains":
        case "disallow_disposable_email_addresses":
            property = "org_join_restrictions";
            break;
    }
    const $element = $(`#id_realm_${CSS.escape(property)}`);
    if ($element.length) {
        discard_property_element_changes($element);
    }
}

export function save_organization_settings(data, $save_button, patch_url) {
    const $subsection_parent = $save_button.closest(".settings-subsection-parent");
    const $save_btn_container = $subsection_parent.find(".save-button-controls");
    const $failed_alert_elem = $subsection_parent.find(".subsection-failed-status p");
    settings_components.change_save_button_state($save_btn_container, "saving");
    channel.patch({
        url: patch_url,
        data,
        success() {
            $failed_alert_elem.hide();
            settings_components.change_save_button_state($save_btn_container, "succeeded");
        },
        error(xhr) {
            settings_components.change_save_button_state($save_btn_container, "failed");
            $save_button.hide();
            ui_report.error($t_html({defaultMessage: "Save failed"}), xhr, $failed_alert_elem);
        },
    });
}

export function set_up() {
    build_page();
    maybe_disable_widgets();
}

export function init_dropdown_widgets() {
    const notification_stream_options = () => {
        const streams = stream_settings_data.get_streams_for_settings_page();
        const options = streams.map((stream) => ({
            name: stream.name,
            unique_id: stream.stream_id,
            stream,
        }));

        const disabled_option = {
            is_setting_disabled: true,
            unique_id: DISABLED_STATE_ID,
            name: $t({defaultMessage: "Disabled"}),
        };

        options.unshift(disabled_option);
        return options;
    };

    const new_stream_announcements_stream_widget = new dropdown_widget.DropdownWidget({
        widget_name: "realm_new_stream_announcements_stream_id",
        get_options: notification_stream_options,
        $events_container: $("#settings_overlay_container #organization-settings"),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            settings_components.new_stream_announcements_stream_widget.render();
            settings_components.save_discard_widget_status_handler($("#org-notifications"));
        },
        tippy_props: {
            placement: "bottom-start",
        },
        default_id: realm.realm_new_stream_announcements_stream_id,
        unique_id_type: dropdown_widget.DataTypes.NUMBER,
        text_if_current_value_not_in_options: $t({defaultMessage: "Cannot view channel"}),
    });
    settings_components.set_new_stream_announcements_stream_widget(
        new_stream_announcements_stream_widget,
    );
    new_stream_announcements_stream_widget.setup();

    const signup_announcements_stream_widget = new dropdown_widget.DropdownWidget({
        widget_name: "realm_signup_announcements_stream_id",
        get_options: notification_stream_options,
        $events_container: $("#settings_overlay_container #organization-settings"),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            settings_components.signup_announcements_stream_widget.render();
            settings_components.save_discard_widget_status_handler($("#org-notifications"));
        },
        tippy_props: {
            placement: "bottom-start",
        },
        default_id: realm.realm_signup_announcements_stream_id,
        unique_id_type: dropdown_widget.DataTypes.NUMBER,
        text_if_current_value_not_in_options: $t({defaultMessage: "Cannot view channel"}),
    });
    settings_components.set_signup_announcements_stream_widget(signup_announcements_stream_widget);
    signup_announcements_stream_widget.setup();

    const zulip_update_announcements_stream_widget = new dropdown_widget.DropdownWidget({
        widget_name: "realm_zulip_update_announcements_stream_id",
        get_options: notification_stream_options,
        $events_container: $("#settings_overlay_container #organization-settings"),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            settings_components.zulip_update_announcements_stream_widget.render();
            settings_components.save_discard_widget_status_handler($("#org-notifications"));
        },
        tippy_props: {
            placement: "bottom-start",
        },
        default_id: realm.realm_zulip_update_announcements_stream_id,
        unique_id_type: dropdown_widget.DataTypes.NUMBER,
        text_if_current_value_not_in_options: $t({defaultMessage: "Cannot view channel"}),
    });
    settings_components.set_zulip_update_announcements_stream_widget(
        zulip_update_announcements_stream_widget,
    );
    zulip_update_announcements_stream_widget.setup();

    const default_code_language_widget = new dropdown_widget.DropdownWidget({
        widget_name: "realm_default_code_block_language",
        get_options() {
            const options = Object.keys(pygments_data.langs).map((x) => ({
                name: x,
                unique_id: x,
            }));

            const disabled_option = {
                is_setting_disabled: true,
                unique_id: "",
                name: $t({defaultMessage: "No language set"}),
            };

            options.unshift(disabled_option);
            return options;
        },
        $events_container: $("#settings_overlay_container #organization-settings"),
        default_id: realm.realm_default_code_block_language,
        unique_id_type: dropdown_widget.DataTypes.STRING,
        tippy_props: {
            placement: "bottom-start",
        },
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            settings_components.default_code_language_widget.render();
            settings_components.save_discard_widget_status_handler($("#org-other-settings"));
        },
    });
    settings_components.set_default_code_language_widget(default_code_language_widget);
    default_code_language_widget.setup();

    const create_multiuse_invite_group_widget = new dropdown_widget.DropdownWidget({
        widget_name: "realm_create_multiuse_invite_group",
        get_options: () =>
            user_groups.get_realm_user_groups_for_dropdown_list_widget(
                "create_multiuse_invite_group",
                "realm",
            ),
        $events_container: $("#settings_overlay_container #organization-permissions"),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            settings_components.create_multiuse_invite_group_widget.render();
            settings_components.save_discard_widget_status_handler($("#org-join-settings"));
        },
        tippy_props: {
            placement: "bottom-start",
        },
        default_id: realm.realm_create_multiuse_invite_group,
        unique_id_type: dropdown_widget.DataTypes.NUMBER,
        on_mount_callback(dropdown) {
            $(dropdown.popper).css("min-width", "300px");
        },
    });
    settings_components.set_create_multiuse_invite_group_widget(
        create_multiuse_invite_group_widget,
    );
    create_multiuse_invite_group_widget.setup();

    const can_access_all_users_group_widget = new dropdown_widget.DropdownWidget({
        widget_name: "realm_can_access_all_users_group",
        get_options: () =>
            user_groups.get_realm_user_groups_for_dropdown_list_widget(
                "can_access_all_users_group",
                "realm",
            ),
        $events_container: $("#settings_overlay_container #organization-permissions"),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            settings_components.can_access_all_users_group_widget.render();
            settings_components.save_discard_widget_status_handler($("#org-guest-settings"));
        },
        tippy_props: {
            placement: "bottom-start",
        },
        default_id: realm.realm_can_access_all_users_group,
        unique_id_type: dropdown_widget.DataTypes.NUMBER,
        on_mount_callback(dropdown) {
            $(dropdown.popper).css("min-width", "300px");
        },
    });
    settings_components.set_can_access_all_users_group_widget(can_access_all_users_group_widget);
    can_access_all_users_group_widget.setup();
}

export function populate_data_for_request(
    subsection,
    for_realm_default_settings,
    sub,
    group,
    custom_profile_field = undefined,
) {
    let data = {};
    const properties_elements = settings_components.get_subsection_property_elements(subsection);

    for (const input_elem of properties_elements) {
        const $input_elem = $(input_elem);
        if (
            settings_components.check_property_changed(
                input_elem,
                for_realm_default_settings,
                sub,
                group,
                custom_profile_field,
            )
        ) {
            const input_value = settings_components.get_input_element_value(input_elem);
            if (input_value !== undefined) {
                let property_name;
                if (for_realm_default_settings || sub || group || custom_profile_field) {
                    property_name = settings_components.extract_property_name(
                        $input_elem,
                        for_realm_default_settings,
                    );
                } else if ($input_elem.attr("id").startsWith("id_authmethod")) {
                    // Authentication Method component IDs include authentication method name
                    // for uniqueness, anchored to "id_authmethod" prefix, e.g. "id_authmethodapple_<property_name>".
                    // We need to strip that whole construct down to extract the actual property name.
                    // The [\da-z]+ part of the regexp covers the auth method name itself.
                    // We assume it's not an empty string and can contain only digits and lowercase ASCII letters,
                    // this is ensured by a respective allowlist-based filter in populate_auth_methods().
                    [, property_name] = /^id_authmethod[\da-z]+_(.*)$/.exec($input_elem.attr("id"));
                } else {
                    [, property_name] = /^id_realm_(.*)$/.exec($input_elem.attr("id"));
                }

                if (property_name === "stream_privacy") {
                    data = {
                        ...data,
                        ...settings_data.get_request_data_for_stream_privacy(input_value),
                    };
                    continue;
                }
                data[property_name] = input_value;
            }
        }
    }

    return data;
}

export function register_save_discard_widget_handlers(
    $container,
    patch_url,
    for_realm_default_settings,
) {
    $container.on("change input", "input, select, textarea", (e) => {
        e.preventDefault();
        e.stopPropagation();

        // This event handler detects whether after these input
        // changes, any fields have different values from the current
        // official values stored in the database and page_params.  If
        // they do, we transition to the "unsaved" state showing the
        // save/discard widget; otherwise, we hide that widget (the
        // "discarded" state).

        if ($(e.target).hasClass("no-input-change-detection")) {
            // This is to prevent input changes detection in elements
            // within a subsection whose changes should not affect the
            // visibility of the discard button
            return false;
        }

        if ($(e.target).hasClass("setting_email_notifications_batching_period_seconds")) {
            const show_elem = $(e.target).val() === "custom_period";
            settings_components.change_element_block_display_property(
                "realm_email_notification_batching_period_edit_minutes",
                show_elem,
            );
        }

        const $subsection = $(e.target).closest(".settings-subsection-parent");
        settings_components.save_discard_widget_status_handler(
            $subsection,
            for_realm_default_settings,
        );
        return undefined;
    });

    $container.on("click", ".subsection-header .subsection-changes-discard button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const $subsection = $(e.target).closest(".settings-subsection-parent");
        for (const elem of settings_components.get_subsection_property_elements($subsection)) {
            discard_property_element_changes(elem, for_realm_default_settings);
        }
        const $save_btn_controls = $(e.target).closest(".save-button-controls");
        settings_components.change_save_button_state($save_btn_controls, "discarded");
    });

    function get_complete_data_for_subsection(subsection) {
        let data = {};

        switch (subsection) {
            case "notifications":
                data.default_language = $(
                    "#org-notifications .language_selection_widget .language_selection_button span",
                ).attr("data-language-code");
                break;
            case "join_settings": {
                const org_join_restrictions = $("#id_realm_org_join_restrictions").val();
                switch (org_join_restrictions) {
                    case "only_selected_domain":
                        data.emails_restricted_to_domains = true;
                        data.disallow_disposable_email_addresses = false;
                        break;
                    case "no_disposable_email":
                        data.emails_restricted_to_domains = false;
                        data.disallow_disposable_email_addresses = true;
                        break;
                    case "no_restriction":
                        data.disallow_disposable_email_addresses = false;
                        data.emails_restricted_to_domains = false;
                        break;
                }
                break;
            }
            case "auth_settings":
                data = {};
                data.authentication_methods = JSON.stringify(
                    settings_components.get_auth_method_list_data(),
                );
                break;
        }
        return data;
    }

    $container.on("click", ".subsection-header .subsection-changes-save button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const $save_button = $(e.currentTarget);
        const $subsection_elem = $save_button.closest(".settings-subsection-parent");
        let extra_data = {};

        if (!for_realm_default_settings) {
            // The organization settings system has some coupled
            // fields that must be submitted together, which is
            // managed by the get_complete_data_for_subsection function.
            const [, subsection_id] = /^org-(.*)$/.exec($subsection_elem.attr("id"));
            const subsection = subsection_id.replaceAll("-", "_");
            extra_data = get_complete_data_for_subsection(subsection);
        }

        const data = {
            ...populate_data_for_request($subsection_elem, for_realm_default_settings),
            ...extra_data,
        };
        save_organization_settings(data, $save_button, patch_url);
    });
}

export function build_page() {
    meta.loaded = true;

    loading.make_indicator($("#admin_page_auth_methods_loading_indicator"));

    // Initialize all the dropdown list widgets.
    init_dropdown_widgets();
    // Populate realm domains
    populate_realm_domains_label(realm.realm_domains);

    // Populate authentication methods table

    populate_auth_methods(settings_components.realm_authentication_methods_to_boolean_dict());

    for (const property_name of simple_dropdown_properties) {
        settings_components.set_property_dropdown_value(property_name);
    }

    set_realm_waiting_period_setting();
    set_video_chat_provider_dropdown();
    set_giphy_rating_dropdown();
    set_msg_edit_limit_dropdown();
    set_msg_move_limit_setting("realm_move_messages_within_stream_limit_seconds");
    set_msg_move_limit_setting("realm_move_messages_between_streams_limit_seconds");
    set_msg_delete_limit_dropdown();
    set_delete_own_message_policy_dropdown(realm.realm_delete_own_message_policy);
    set_message_retention_setting_dropdown();
    set_org_join_restrictions_dropdown();
    set_message_content_in_email_notifications_visibility();
    set_digest_emails_weekday_visibility();
    set_create_web_public_stream_dropdown_visibility();

    register_save_discard_widget_handlers($(".admin-realm-form"), "/json/realm", false);

    $(".settings-subsection-parent").on("keydown", "input", (e) => {
        e.stopPropagation();
        if (keydown_util.is_enter_event(e)) {
            e.preventDefault();
            $(e.target)
                .closest(".settings-subsection-parent")
                .find(".subsection-changes-save button")
                .trigger("click");
        }
    });

    $("#id_realm_message_content_edit_limit_seconds").on("change", () => {
        settings_components.update_custom_value_input("realm_message_content_edit_limit_seconds");
    });

    $("#id_realm_move_messages_between_streams_limit_seconds").on("change", () => {
        settings_components.update_custom_value_input(
            "realm_move_messages_between_streams_limit_seconds",
        );
    });

    $("#id_realm_move_messages_within_stream_limit_seconds").on("change", () => {
        settings_components.update_custom_value_input(
            "realm_move_messages_within_stream_limit_seconds",
        );
    });

    $("#id_realm_message_content_delete_limit_seconds").on("change", () => {
        settings_components.update_custom_value_input("realm_message_content_delete_limit_seconds");
    });

    $("#id_realm_video_chat_provider").on("change", () => {
        set_jitsi_server_url_dropdown();
    });

    $("#id_realm_jitsi_server_url").on("change", (e) => {
        const dropdown_val = e.target.value;
        update_jitsi_server_url_custom_input(dropdown_val);
    });

    $("#id_realm_message_retention_days").on("change", (e) => {
        const message_retention_setting_dropdown_value = e.target.value;
        settings_components.change_element_block_display_property(
            "id_realm_message_retention_custom_input",
            message_retention_setting_dropdown_value === "custom_period",
        );
    });

    $("#id_realm_waiting_period_threshold").on("change", function () {
        const waiting_period_threshold = this.value;
        settings_components.change_element_block_display_property(
            "id_realm_waiting_period_threshold_custom_input",
            waiting_period_threshold === "custom_period",
        );
    });

    $("#id_realm_digest_emails_enabled").on("change", (e) => {
        const digest_emails_enabled = $(e.target).is(":checked");
        settings_components.change_element_block_display_property(
            "id_realm_digest_weekday",
            digest_emails_enabled === true,
        );
    });

    $("#id_realm_org_join_restrictions").on("change", (e) => {
        const org_join_restrictions = e.target.value;
        const $node = $("#allowed_domains_label").parent();
        if (org_join_restrictions === "only_selected_domain") {
            $node.show();
            if (realm.realm_domains.length === 0) {
                settings_realm_domains.show_realm_domains_modal();
            }
        } else {
            $node.hide();
        }
    });

    $("#id_realm_allow_message_editing").on("change", (e) => {
        const is_checked = $(e.target).prop("checked");
        update_message_edit_sub_settings(is_checked);
    });

    $("#org-moving-msgs").on("change", ".move-message-policy-setting", (e) => {
        const $policy_dropdown_elem = $(e.target);
        const property_name = settings_components.extract_property_name($policy_dropdown_elem);
        const disable_time_limit_setting = message_move_limit_setting_enabled(property_name);

        let time_limit_setting_name;
        if (property_name === "realm_edit_topic_policy") {
            time_limit_setting_name = "realm_move_messages_within_stream_limit_seconds";
        } else {
            time_limit_setting_name = "realm_move_messages_between_streams_limit_seconds";
        }

        enable_or_disable_related_message_move_time_limit_setting(
            time_limit_setting_name,
            disable_time_limit_setting,
        );
    });

    $("#id_realm_delete_own_message_policy").on("change", (e) => {
        const setting_value = Number.parseInt($(e.target).val(), 10);
        set_delete_own_message_policy_dropdown(setting_value);
    });

    $("#id_realm_org_join_restrictions").on("click", (e) => {
        // This prevents the disappearance of modal when there are
        // no allowed domains otherwise it gets closed due to
        // the click event handler attached to `#settings_overlay_container`
        e.stopPropagation();
    });

    $("#show_realm_domains_modal").on("click", (e) => {
        e.stopPropagation();
        settings_realm_domains.show_realm_domains_modal();
    });

    function realm_icon_logo_upload_complete($spinner, $upload_text, $delete_button) {
        $spinner.css({visibility: "hidden"});
        $upload_text.show();
        $delete_button.show();
    }

    function realm_icon_logo_upload_start($spinner, $upload_text, $delete_button) {
        $spinner.css({visibility: "visible"});
        $upload_text.hide();
        $delete_button.hide();
    }

    function upload_realm_logo_or_icon($file_input, night, icon) {
        const form_data = new FormData();
        let widget;
        let url;

        form_data.append("csrfmiddlewaretoken", csrf_token);
        for (const [i, file] of Array.prototype.entries.call($file_input[0].files)) {
            form_data.append("file-" + i, file);
        }
        if (icon) {
            url = "/json/realm/icon";
            widget = "#realm-icon-upload-widget";
        } else {
            if (night) {
                widget = "#realm-night-logo-upload-widget";
            } else {
                widget = "#realm-day-logo-upload-widget";
            }
            url = "/json/realm/logo";
            form_data.append("night", JSON.stringify(night));
        }
        const $spinner = $(`${widget} .upload-spinner-background`).expectOne();
        const $upload_text = $(`${widget}  .image-upload-text`).expectOne();
        const $delete_button = $(`${widget}  .image-delete-button`).expectOne();
        const $error_field = $(`${widget}  .image_file_input_error`).expectOne();
        realm_icon_logo_upload_start($spinner, $upload_text, $delete_button);
        $error_field.hide();
        channel.post({
            url,
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success() {
                realm_icon_logo_upload_complete($spinner, $upload_text, $delete_button);
            },
            error(xhr) {
                realm_icon_logo_upload_complete($spinner, $upload_text, $delete_button);
                ui_report.error("", xhr, $error_field);
            },
        });
    }

    realm_icon.build_realm_icon_widget(upload_realm_logo_or_icon, null, true);
    if (realm.zulip_plan_is_not_limited) {
        realm_logo.build_realm_logo_widget(upload_realm_logo_or_icon, false);
        realm_logo.build_realm_logo_widget(upload_realm_logo_or_icon, true);
    }

    $("#organization-profile .deactivate_realm_button").on("click", deactivate_organization);
}
