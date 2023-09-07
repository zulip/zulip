import $ from "jquery";

import pygments_data from "../generated/pygments_data.json";
import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";
import render_settings_deactivate_realm_modal from "../templates/confirm_dialog/confirm_deactivate_realm.hbs";
import render_settings_admin_auth_methods_list from "../templates/settings/admin_auth_methods_list.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as compose_banner from "./compose_banner";
import {csrf_token} from "./csrf";
import * as dialog_widget from "./dialog_widget";
import * as dropdown_widget from "./dropdown_widget";
import {$t, $t_html, get_language_name} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as loading from "./loading";
import * as notifications from "./notifications";
import {page_params} from "./page_params";
import * as realm_icon from "./realm_icon";
import * as realm_logo from "./realm_logo";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as settings_notifications from "./settings_notifications";
import * as settings_realm_domains from "./settings_realm_domains";
import * as settings_realm_user_settings_defaults from "./settings_realm_user_settings_defaults";
import * as settings_ui from "./settings_ui";
import * as stream_data from "./stream_data";
import * as stream_edit from "./stream_edit";
import * as stream_settings_data from "./stream_settings_data";
import * as ui_report from "./ui_report";
import * as user_groups from "./user_groups";

const meta = {
    loaded: false,
};

export function reset() {
    meta.loaded = false;
}

const MAX_CUSTOM_TIME_LIMIT_SETTING_VALUE = 2147483647;
const DISABLED_STATE_ID = -1;

export function maybe_disable_widgets() {
    if (page_params.is_owner) {
        return;
    }

    $(".organization-box [data-name='auth-methods']")
        .find("input, button, select, checked")
        .prop("disabled", true);

    if (page_params.is_admin) {
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

export function get_sorted_options_list(option_values_object) {
    const options_list = Object.keys(option_values_object).map((key) => ({
        ...option_values_object[key],
        key,
    }));
    let comparator = (x, y) => x.order - y.order;
    if (!options_list[0].order) {
        comparator = (x, y) => {
            const key_x = x.key.toUpperCase();
            const key_y = y.key.toUpperCase();
            if (key_x < key_y) {
                return -1;
            }
            if (key_x > key_y) {
                return 1;
            }
            return 0;
        };
    }
    options_list.sort(comparator);
    return options_list;
}

export function get_organization_settings_options() {
    const options = {};
    options.common_policy_values = get_sorted_options_list(settings_config.common_policy_values);
    options.private_message_policy_values = get_sorted_options_list(
        settings_config.private_message_policy_values,
    );
    options.wildcard_mention_policy_values = get_sorted_options_list(
        settings_config.wildcard_mention_policy_values,
    );
    options.common_message_policy_values = get_sorted_options_list(
        settings_config.common_message_policy_values,
    );
    options.invite_to_realm_policy_values = get_sorted_options_list(
        settings_config.email_invite_to_realm_policy_values,
    );
    options.edit_topic_policy_values = get_sorted_options_list(
        settings_config.edit_topic_policy_values,
    );
    options.move_messages_between_streams_policy_values = get_sorted_options_list(
        settings_config.move_messages_between_streams_policy_values,
    );
    return options;
}

export function get_org_type_dropdown_options() {
    const current_org_type = page_params.realm_org_type;
    if (current_org_type !== 0) {
        return settings_config.defined_org_type_values;
    }
    return settings_config.all_org_type_values;
}

export function get_realm_time_limits_in_minutes(property) {
    if (page_params[property] === null) {
        // This represents "Anytime" case.
        return null;
    }
    let val = (page_params[property] / 60).toFixed(1);
    if (Number.parseFloat(val, 10) === Number.parseInt(val, 10)) {
        val = Number.parseInt(val, 10);
    }
    return val.toString();
}

function get_property_value(property_name, for_realm_default_settings, sub) {
    if (for_realm_default_settings) {
        // realm_user_default_settings are stored in a separate object.
        if (property_name === "twenty_four_hour_time") {
            return JSON.stringify(realm_user_settings_defaults.twenty_four_hour_time);
        }
        if (
            property_name === "email_notifications_batching_period_seconds" ||
            property_name === "email_notification_batching_period_edit_minutes"
        ) {
            return realm_user_settings_defaults.email_notifications_batching_period_seconds;
        }
        return realm_user_settings_defaults[property_name];
    }

    if (sub) {
        if (property_name === "stream_privacy") {
            return stream_data.get_stream_privacy_policy(sub.stream_id);
        }
        if (property_name === "is_default_stream") {
            return stream_data.is_default_stream_id(sub.stream_id);
        }

        return sub[property_name];
    }

    if (property_name === "realm_org_join_restrictions") {
        if (page_params.realm_emails_restricted_to_domains) {
            return "only_selected_domain";
        }
        if (page_params.realm_disallow_disposable_email_addresses) {
            return "no_disposable_email";
        }
        return "no_restriction";
    }

    return page_params[property_name];
}

export function extract_property_name($elem, for_realm_default_settings) {
    if (for_realm_default_settings) {
        // ID for realm_user_default_settings elements are of the form
        // "realm_{settings_name}}" because both user and realm default
        // settings use the same template and each element should have
        // unique id.
        return /^realm_(.*)$/.exec($elem.attr("id").replaceAll("-", "_"))[1];
    }

    if ($elem.attr("id").startsWith("id_authmethod")) {
        // Authentication Method component IDs include authentication method name
        // for uniqueness, anchored to "id_authmethod" prefix, e.g. "id_authmethodapple_<property_name>".
        // We need to strip that whole construct down to extract the actual property name.
        // The [\da-z]+ part of the regexp covers the auth method name itself.
        // We assume it's not an empty string and can contain only digits and lowercase ASCII letters,
        // this is ensured by a respective allowlist-based filter in populate_auth_methods().
        return /^id_authmethod[\da-z]+_(.*)$/.exec($elem.attr("id"))[1];
    }

    return /^id_(.*)$/.exec($elem.attr("id").replaceAll("-", "_"))[1];
}

export function get_subsection_property_elements(subsection) {
    return [...$(subsection).find(".prop-element")];
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

function set_property_dropdown_value(property_name) {
    $(`#id_${CSS.escape(property_name)}`).val(get_property_value(property_name));
}

export function change_element_block_display_property(elem_id, show_element) {
    const $elem = $(`#${CSS.escape(elem_id)}`);
    if (show_element) {
        $elem.parent().show();
    } else {
        $elem.parent().hide();
    }
}

function set_realm_waiting_period_setting() {
    const setting_value = page_params.realm_waiting_period_threshold;
    const valid_limit_values = settings_config.waiting_period_threshold_dropdown_values.map(
        (x) => x.code,
    );

    if (valid_limit_values.includes(setting_value)) {
        $("#id_realm_waiting_period_threshold").val(setting_value);
    } else {
        $("#id_realm_waiting_period_threshold").val("custom_period");
    }

    $("#id_realm_waiting_period_threshold_custom_input").val(setting_value);
    change_element_block_display_property(
        "id_realm_waiting_period_threshold_custom_input",
        $("#id_realm_waiting_period_threshold").val() === "custom_period",
    );
}

function set_video_chat_provider_dropdown() {
    const chat_provider_id = page_params.realm_video_chat_provider;
    $("#id_realm_video_chat_provider").val(chat_provider_id);
}

function set_giphy_rating_dropdown() {
    const rating_id = page_params.realm_giphy_rating;
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

function update_custom_value_input(property_name) {
    const $dropdown_elem = $(`#id_${CSS.escape(property_name)}`);
    const custom_input_elem_id = $dropdown_elem
        .parent()
        .find(".time-limit-custom-input")
        .attr("id");

    const show_custom_limit_input = $dropdown_elem.val() === "custom_period";
    change_element_block_display_property(custom_input_elem_id, show_custom_limit_input);
    if (show_custom_limit_input) {
        $(`#${CSS.escape(custom_input_elem_id)}`).val(
            get_realm_time_limits_in_minutes(property_name),
        );
    }
}

function get_time_limit_dropdown_setting_value(property_name) {
    if (page_params[property_name] === null) {
        return "any_time";
    }

    const valid_limit_values = settings_config.time_limit_dropdown_values.map((x) => x.value);
    if (valid_limit_values.includes(page_params[property_name])) {
        return page_params[property_name].toString();
    }

    return "custom_period";
}

function set_time_limit_setting(property_name) {
    const dropdown_elem_val = get_time_limit_dropdown_setting_value(property_name);
    $(`#id_${CSS.escape(property_name)}`).val(dropdown_elem_val);

    const $custom_input = $(`#id_${CSS.escape(property_name)}`)
        .parent()
        .find(".time-limit-custom-input");
    $custom_input.val(get_realm_time_limits_in_minutes(property_name));

    change_element_block_display_property(
        $custom_input.attr("id"),
        dropdown_elem_val === "custom_period",
    );
}

function set_msg_edit_limit_dropdown() {
    set_time_limit_setting("realm_message_content_edit_limit_seconds");
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
    set_time_limit_setting(property_name);

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
    const limit_setting_dropdown_value = get_time_limit_dropdown_setting_value(
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
    set_time_limit_setting("realm_message_content_delete_limit_seconds");
}

function get_message_retention_setting_value($input_elem, for_api_data = true) {
    const select_elem_val = $input_elem.val();
    if (select_elem_val === "unlimited") {
        if (!for_api_data) {
            return settings_config.retain_message_forever;
        }
        return JSON.stringify("unlimited");
    }

    if (select_elem_val === "realm_default") {
        if (!for_api_data) {
            return null;
        }
        return JSON.stringify("realm_default");
    }

    const $custom_input = $input_elem.parent().find(".message-retention-setting-custom-input");
    if ($custom_input.val().length === 0) {
        return settings_config.retain_message_forever;
    }
    return Number.parseInt(Number($custom_input.val()), 10);
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
    const setting_value = get_property_value(property_name, false, sub);
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

    change_element_block_display_property(
        $custom_input_elem.attr("id"),
        dropdown_val === "custom_period",
    );
}

function set_org_join_restrictions_dropdown() {
    const value = get_property_value("realm_org_join_restrictions");
    $("#id_realm_org_join_restrictions").val(value);
    change_element_block_display_property(
        "allowed_domains_label",
        value === "only_selected_domain",
    );
}

function set_message_content_in_email_notifications_visibility() {
    change_element_block_display_property(
        "message_content_in_email_notifications_label",
        page_params.realm_message_content_allowed_in_email_notifications,
    );
}

function set_digest_emails_weekday_visibility() {
    change_element_block_display_property(
        "id_realm_digest_weekday",
        page_params.realm_digest_emails_enabled,
    );
}

function set_create_web_public_stream_dropdown_visibility() {
    change_element_block_display_property(
        "id_realm_create_web_public_stream_policy",
        page_params.server_web_public_streams_enabled &&
            page_params.zulip_plan_is_not_limited &&
            page_params.realm_enable_spectator_access,
    );
}

export function populate_realm_domains_label(realm_domains) {
    if (!meta.loaded) {
        return;
    }

    const domains_list = realm_domains.map((realm_domain) =>
        realm_domain.allow_subdomains ? "*." + realm_domain.domain : realm_domain.domain,
    );
    let domains = domains_list.join(", ");
    if (domains.length === 0) {
        domains = $t({defaultMessage: "None"});
    }
    $("#allowed_domains_label").text($t({defaultMessage: "Allowed domains: {domains}"}, {domains}));
}

function sort_object_by_key(obj) {
    const keys = Object.keys(obj).sort();
    const new_obj = {};

    for (const key of keys) {
        new_obj[key] = obj[key];
    }

    return new_obj;
}

function can_configure_auth_methods() {
    if (settings_data.user_email_not_configured()) {
        return false;
    }
    if (page_params.is_owner) {
        return true;
    }
    return false;
}

export function populate_auth_methods(auth_methods) {
    if (!meta.loaded) {
        return;
    }
    const $auth_methods_list = $("#id_realm_authentication_methods").expectOne();
    auth_methods = sort_object_by_key(auth_methods);
    let rendered_auth_method_rows = "";
    for (const [auth_method, value] of Object.entries(auth_methods)) {
        rendered_auth_method_rows += render_settings_admin_auth_methods_list({
            method: auth_method,
            enabled: value,
            disable_configure_auth_method: !can_configure_auth_methods(),
            // The negated character class regexp serves as an allowlist - the replace() will
            // remove *all* symbols *but* digits (\d) and lowecase letters (a-z),
            // so that we can make assumptions on this string elsewhere in the code.
            // As a result, the only two "incoming" assumptions on the auth method name are:
            // 1) It contains at least one allowed symbol
            // 2) No two auth method names are identical after this allowlist filtering
            prefix: "id_authmethod" + auth_method.toLowerCase().replaceAll(/[^\da-z]/g, "") + "_",
        });
    }
    $auth_methods_list.html(rendered_auth_method_rows);
}

function update_dependent_subsettings(property_name) {
    if (simple_dropdown_properties.includes(property_name)) {
        set_property_dropdown_value(property_name);
        return;
    }

    switch (property_name) {
        case "realm_video_chat_provider":
            set_video_chat_provider_dropdown();
            break;
        case "realm_allow_message_editing":
            update_message_edit_sub_settings(page_params.realm_allow_message_editing);
            break;
        case "realm_delete_own_message_policy":
            set_delete_own_message_policy_dropdown(page_params.realm_delete_own_message_policy);
            break;
        case "realm_org_join_restrictions":
            set_org_join_restrictions_dropdown();
            break;
        case "realm_message_content_allowed_in_email_notifications":
            set_message_content_in_email_notifications_visibility();
            break;
        case "realm_digest_emails_enabled":
            settings_notifications.set_enable_digest_emails_visibility(
                settings_notifications.user_settings_panel,
            );
            settings_notifications.set_enable_digest_emails_visibility(
                settings_realm_user_settings_defaults.realm_default_settings_panel,
            );
            set_digest_emails_weekday_visibility();
            break;
        case "realm_enable_spectator_access":
            set_create_web_public_stream_dropdown_visibility();
            break;
    }
}

export let default_code_language_widget = null;
export let notifications_stream_widget = null;
export let signup_notifications_stream_widget = null;
export let create_multiuse_invite_group_widget = null;

export function get_widget_for_dropdown_list_settings(property_name) {
    switch (property_name) {
        case "realm_notifications_stream_id":
            return notifications_stream_widget;
        case "realm_signup_notifications_stream_id":
            return signup_notifications_stream_widget;
        case "realm_default_code_block_language":
            return default_code_language_widget;
        case "realm_create_multiuse_invite_group":
            return create_multiuse_invite_group_widget;
        case "can_remove_subscribers_group":
            return stream_edit.can_remove_subscribers_group_widget;
        default:
            blueslip.error("No dropdown list widget for property", {property_name});
            return null;
    }
}

export function set_dropdown_list_widget_setting_value(property_name, value) {
    const widget = get_widget_for_dropdown_list_settings(property_name);
    widget.render(value);
}

export function get_dropdown_list_widget_setting_value($input_elem) {
    const widget_name = extract_property_name($input_elem);
    const setting_widget = get_widget_for_dropdown_list_settings(widget_name);

    const setting_value_type = $input_elem.attr("data-setting-value-type");
    if (setting_value_type === "number") {
        return Number.parseInt(setting_widget.value(), 10);
    }

    return setting_widget.value();
}

export function discard_property_element_changes(elem, for_realm_default_settings, sub) {
    const $elem = $(elem);
    const property_name = extract_property_name($elem, for_realm_default_settings);
    const property_value = get_property_value(property_name, for_realm_default_settings, sub);

    switch (property_name) {
        case "notification_sound":
            notifications.update_notification_sound_source(
                $("#realm-default-notification-sound-audio"),
                {
                    notification_sound: property_value,
                },
            );
            set_input_element_value($elem, property_value);
            break;
        case "realm_authentication_methods":
            populate_auth_methods(property_value);
            break;
        case "realm_notifications_stream_id":
        case "realm_signup_notifications_stream_id":
        case "realm_default_code_block_language":
        case "can_remove_subscribers_group":
        case "realm_create_multiuse_invite_group":
            set_dropdown_list_widget_setting_value(property_name, property_value);
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
        case "stream_privacy":
            // Because this widget has a radio button structure, it
            // needs custom reset code.
            $elem.find(`input[value='${CSS.escape(property_value)}']`).prop("checked", true);
            break;
        case "email_notifications_batching_period_seconds":
        case "email_notification_batching_period_edit_minutes":
            settings_notifications.set_notification_batching_ui(
                $("#realm-user-default-settings"),
                realm_user_settings_defaults.email_notifications_batching_period_seconds,
            );
            break;
        case "realm_org_type":
            set_input_element_value($elem, property_value);
            // Remove 'unspecified' option (value=0) from realm_org_type
            // dropdown menu options whenever page_params.realm_org_type
            // returns another value.
            if (property_value !== 0) {
                $("#id_realm_org_type option[value=0]").remove();
            }
            break;
        case "realm_message_content_edit_limit_seconds":
        case "realm_message_content_delete_limit_seconds":
            set_time_limit_setting(property_name);
            break;
        case "realm_move_messages_within_stream_limit_seconds":
        case "realm_move_messages_between_streams_limit_seconds":
            set_msg_move_limit_setting(property_name);
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
                set_input_element_value($elem, property_value);
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

export function change_save_button_state($element, state) {
    function show_hide_element($element, show, fadeout_delay, fadeout_callback) {
        if (show) {
            $element.removeClass("hide").addClass(".show").fadeIn(300);
            return;
        }
        setTimeout(() => {
            $element.fadeOut(300, fadeout_callback);
        }, fadeout_delay);
    }

    const $saveBtn = $element.find(".save-button");
    const $textEl = $saveBtn.find(".save-discard-widget-button-text");

    if (state !== "saving") {
        $saveBtn.removeClass("saving");
    }

    if (state === "discarded") {
        show_hide_element($element, false, 0, () =>
            enable_or_disable_save_button($element.closest(".settings-subsection-parent")),
        );
        return;
    }

    let button_text;
    let data_status;
    let is_show;
    switch (state) {
        case "unsaved":
            button_text = $t({defaultMessage: "Save changes"});
            data_status = "unsaved";
            is_show = true;

            $element.find(".discard-button").show();
            break;
        case "saved":
            button_text = $t({defaultMessage: "Save changes"});
            data_status = "";
            is_show = false;
            break;
        case "saving":
            button_text = $t({defaultMessage: "Saving"});
            data_status = "saving";
            is_show = true;

            $element.find(".discard-button").hide();
            $saveBtn.addClass("saving");
            break;
        case "failed":
            button_text = $t({defaultMessage: "Save changes"});
            data_status = "failed";
            is_show = true;
            break;
        case "succeeded":
            button_text = $t({defaultMessage: "Saved"});
            data_status = "saved";
            is_show = false;
            break;
    }

    $textEl.text(button_text);
    $saveBtn.attr("data-status", data_status);
    if (state === "unsaved") {
        enable_or_disable_save_button($element.closest(".settings-subsection-parent"));
    }
    show_hide_element($element, is_show, 800);
}

export function save_organization_settings(data, $save_button, patch_url) {
    const $subsection_parent = $save_button.closest(".settings-subsection-parent");
    const $save_btn_container = $subsection_parent.find(".save-button-controls");
    const $failed_alert_elem = $subsection_parent.find(".subsection-failed-status p");
    change_save_button_state($save_btn_container, "saving");
    channel.patch({
        url: patch_url,
        data,
        success() {
            $failed_alert_elem.hide();
            change_save_button_state($save_btn_container, "succeeded");
        },
        error(xhr) {
            change_save_button_state($save_btn_container, "failed");
            $save_button.hide();
            ui_report.error($t_html({defaultMessage: "Save failed"}), xhr, $failed_alert_elem);
        },
    });
}

function get_input_type($input_elem, input_type) {
    if (["boolean", "string", "number"].includes(input_type)) {
        return input_type;
    }
    return $input_elem.data("setting-widget-type");
}

export function get_input_element_value(input_elem, input_type) {
    const $input_elem = $(input_elem);
    input_type = get_input_type($input_elem, input_type);
    switch (input_type) {
        case "boolean":
            return $input_elem.prop("checked");
        case "string":
            return $input_elem.val().trim();
        case "number":
            return Number.parseInt($input_elem.val().trim(), 10);
        case "radio-group": {
            const selected_val = $input_elem.find("input:checked").val();
            if ($input_elem.data("setting-choice-type") === "number") {
                return Number.parseInt(selected_val, 10);
            }
            return selected_val.trim();
        }
        case "time-limit":
            return get_time_limit_setting_value($input_elem);
        case "message-retention-setting":
            return get_message_retention_setting_value($input_elem);
        case "dropdown-list-widget":
            return get_dropdown_list_widget_setting_value($input_elem);
        default:
            return undefined;
    }
}

export function set_input_element_value($input_elem, value) {
    const input_type = get_input_type($input_elem, typeof value);
    if (input_type) {
        if (input_type === "boolean") {
            return $input_elem.prop("checked", value);
        } else if (input_type === "string" || input_type === "number") {
            return $input_elem.val(value);
        }
    }
    blueslip.error("Failed to set value of property", {
        property: extract_property_name($input_elem),
    });
    return undefined;
}

export function set_up() {
    build_page();
    maybe_disable_widgets();
}

function get_auth_method_list_data() {
    const new_auth_methods = {};
    const $auth_method_rows = $("#id_realm_authentication_methods").find("div.method_row");

    for (const method_row of $auth_method_rows) {
        new_auth_methods[$(method_row).data("method")] = $(method_row)
            .find("input")
            .prop("checked");
    }

    return new_auth_methods;
}

export function parse_time_limit($elem) {
    return Math.floor(Number.parseFloat(Number($elem.val()), 10).toFixed(1) * 60);
}

function get_time_limit_setting_value($input_elem, for_api_data = true) {
    const select_elem_val = $input_elem.val();

    if (select_elem_val === "any_time") {
        // "unlimited" is sent to API when a user wants to set the setting to
        // "Any time" and the message_content_edit_limit_seconds field is "null"
        // for that case.
        if (!for_api_data) {
            return null;
        }
        return JSON.stringify("unlimited");
    }

    if (select_elem_val !== "custom_period") {
        return Number.parseInt(select_elem_val, 10);
    }

    const $custom_input_elem = $input_elem.parent().find(".time-limit-custom-input");
    if ($custom_input_elem.val().length === 0) {
        // This handles the case where the initial setting value is "Any time" and then
        // dropdown is changed to "Custom" where the input box is empty initially and
        // thus we do not show the save-discard widget until something is typed in the
        // input box.
        return null;
    }

    if ($input_elem.attr("id") === "id_realm_waiting_period_threshold") {
        // For realm waiting period threshold setting, the custom input element contains
        // number of days.
        return Number.parseInt(Number($custom_input_elem.val()), 10);
    }

    return parse_time_limit($custom_input_elem);
}

export function check_property_changed(elem, for_realm_default_settings, sub) {
    const $elem = $(elem);
    const property_name = extract_property_name($elem, for_realm_default_settings);
    let current_val = get_property_value(property_name, for_realm_default_settings, sub);
    let proposed_val;

    switch (property_name) {
        case "realm_authentication_methods":
            current_val = sort_object_by_key(current_val);
            current_val = JSON.stringify(current_val);
            proposed_val = get_auth_method_list_data();
            proposed_val = JSON.stringify(proposed_val);
            break;
        case "realm_notifications_stream_id":
        case "realm_signup_notifications_stream_id":
        case "realm_default_code_block_language":
        case "can_remove_subscribers_group":
        case "realm_create_multiuse_invite_group":
            proposed_val = get_dropdown_list_widget_setting_value($elem);
            break;
        case "email_notifications_batching_period_seconds":
            proposed_val = get_time_limit_setting_value($elem, false);
            break;
        case "realm_message_content_edit_limit_seconds":
        case "realm_message_content_delete_limit_seconds":
        case "realm_move_messages_between_streams_limit_seconds":
        case "realm_move_messages_within_stream_limit_seconds":
        case "realm_waiting_period_threshold":
            proposed_val = get_time_limit_setting_value($elem, false);
            break;
        case "realm_message_retention_days":
        case "message_retention_days":
            proposed_val = get_message_retention_setting_value($elem, false);
            break;
        case "realm_default_language":
            proposed_val = $(
                "#org-notifications .language_selection_widget .language_selection_button span",
            ).attr("data-language-code");
            break;
        case "emojiset":
        case "user_list_style":
        case "stream_privacy":
            proposed_val = get_input_element_value($elem, "radio-group");
            break;
        default:
            if (current_val !== undefined) {
                proposed_val = get_input_element_value($elem, typeof current_val);
            } else {
                blueslip.error("Element refers to unknown property", {property_name});
            }
    }
    return current_val !== proposed_val;
}

function switching_to_private(properties_elements, for_realm_default_settings) {
    for (const elem of properties_elements) {
        const $elem = $(elem);
        const property_name = extract_property_name($elem, for_realm_default_settings);
        if (property_name !== "stream_privacy") {
            continue;
        }
        const proposed_val = get_input_element_value($elem, "radio-group");
        return proposed_val === "invite-only-public-history" || proposed_val === "invite-only";
    }
    return false;
}

export function save_discard_widget_status_handler($subsection, for_realm_default_settings, sub) {
    $subsection.find(".subsection-failed-status p").hide();
    $subsection.find(".save-button").show();
    const properties_elements = get_subsection_property_elements($subsection);
    const show_change_process_button = properties_elements.some((elem) =>
        check_property_changed(elem, for_realm_default_settings, sub),
    );

    const $save_btn_controls = $subsection.find(".subsection-header .save-button-controls");
    const button_state = show_change_process_button ? "unsaved" : "discarded";
    change_save_button_state($save_btn_controls, button_state);

    // If this widget is for a stream, and the stream isn't currently private
    // but being changed to private, and the user changing this setting isn't
    // subscribed, we show a warning that they won't be able to access the
    // stream after making it private unless they subscribe.
    if (!sub) {
        return;
    }
    if (
        button_state === "unsaved" &&
        !sub.invite_only &&
        !sub.subscribed &&
        switching_to_private(properties_elements, for_realm_default_settings)
    ) {
        if ($("#stream_permission_settings .stream_privacy_warning").length > 0) {
            return;
        }
        const context = {
            banner_type: compose_banner.WARNING,
            banner_text: $t({
                defaultMessage:
                    "Only subscribers can access or join private streams, so you will lose access to this stream if you convert it to a private stream while not subscribed to it.",
            }),
            button_text: $t({defaultMessage: "Subscribe"}),
            classname: "stream_privacy_warning",
            stream_id: sub.stream_id,
        };
        $("#stream_permission_settings .stream-permissions-warning-banner").append(
            render_compose_banner(context),
        );
    } else {
        $("#stream_permission_settings .stream-permissions-warning-banner").empty();
    }
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

    notifications_stream_widget = new dropdown_widget.DropdownWidget({
        widget_name: "realm_notifications_stream_id",
        get_options: notification_stream_options,
        $events_container: $("#settings_overlay_container #organization-settings"),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            notifications_stream_widget.render();
            save_discard_widget_status_handler($("#org-notifications"));
        },
        tippy_props: {
            placement: "bottom-start",
        },
        default_id: page_params.realm_notifications_stream_id,
        unique_id_type: dropdown_widget.DATA_TYPES.NUMBER,
        show_disabled_if_current_value_not_in_options: true,
    });
    notifications_stream_widget.setup();

    signup_notifications_stream_widget = new dropdown_widget.DropdownWidget({
        widget_name: "realm_signup_notifications_stream_id",
        get_options: notification_stream_options,
        $events_container: $("#settings_overlay_container #organization-settings"),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            signup_notifications_stream_widget.render();
            save_discard_widget_status_handler($("#org-notifications"));
        },
        tippy_props: {
            placement: "bottom-start",
        },
        default_id: page_params.realm_signup_notifications_stream_id,
        unique_id_type: dropdown_widget.DATA_TYPES.NUMBER,
        show_disabled_if_current_value_not_in_options: true,
    });
    signup_notifications_stream_widget.setup();

    default_code_language_widget = new dropdown_widget.DropdownWidget({
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
        default_id: page_params.realm_default_code_block_language,
        unique_id_type: dropdown_widget.DATA_TYPES.STRING,
        tippy_props: {
            placement: "bottom-start",
        },
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            default_code_language_widget.render();
            save_discard_widget_status_handler($("#org-other-settings"));
        },
    });
    default_code_language_widget.setup();

    create_multiuse_invite_group_widget = new dropdown_widget.DropdownWidget({
        widget_name: "realm_create_multiuse_invite_group",
        get_options: () =>
            user_groups.get_realm_user_groups_for_dropdown_list_widget(
                "create_multiuse_invite_group",
            ),
        $events_container: $("#settings_overlay_container #organization-permissions"),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            create_multiuse_invite_group_widget.render();
            save_discard_widget_status_handler($("#org-join-settings"));
        },
        tippy_props: {
            placement: "bottom-start",
        },
        default_id: page_params.realm_create_multiuse_invite_group,
        unique_id_type: dropdown_widget.DATA_TYPES.NUMBER,
        on_mount_callback(dropdown) {
            $(dropdown.popper).css("min-width", "300px");
        },
    });
    create_multiuse_invite_group_widget.setup();
}

function check_maximum_valid_value($custom_input_elem, property_name) {
    let setting_value = Number.parseInt($custom_input_elem.val(), 10);
    if (
        property_name === "realm_message_content_edit_limit_seconds" ||
        property_name === "realm_message_content_delete_limit_seconds" ||
        property_name === "email_notifications_batching_period_seconds"
    ) {
        setting_value = parse_time_limit($custom_input_elem);
    }
    return setting_value <= MAX_CUSTOM_TIME_LIMIT_SETTING_VALUE;
}

function enable_or_disable_save_button($subsection_elem) {
    const time_limit_settings = [...$subsection_elem.find(".time-limit-setting")];
    let disable_save_btn = false;
    for (const setting_elem of time_limit_settings) {
        const $dropdown_elem = $(setting_elem).find("select");
        const $custom_input_elem = $(setting_elem).find(".time-limit-custom-input");
        const custom_input_elem_val = Number.parseInt(Number($custom_input_elem.val()), 10);

        const for_realm_default_settings =
            $dropdown_elem.closest(".settings-section.show").attr("id") ===
            "realm-user-default-settings";
        const property_name = extract_property_name($dropdown_elem, for_realm_default_settings);

        disable_save_btn =
            $dropdown_elem.val() === "custom_period" &&
            (custom_input_elem_val <= 0 ||
                Number.isNaN(custom_input_elem_val) ||
                !check_maximum_valid_value($custom_input_elem, property_name));

        if (
            $custom_input_elem.val() === "0" &&
            property_name === "realm_waiting_period_threshold"
        ) {
            // 0 is a valid value for realm_waiting_period_threshold setting. We specifically
            // check for $custom_input_elem.val() to be "0" and not custom_input_elem_val
            // because it is 0 even when custom input box is empty.
            disable_save_btn = false;
        }

        if (disable_save_btn) {
            break;
        }
    }
    $subsection_elem.find(".subsection-changes-save button").prop("disabled", disable_save_btn);
}

export function populate_data_for_request(subsection, for_realm_default_settings, sub) {
    let data = {};
    const properties_elements = get_subsection_property_elements(subsection);

    for (const input_elem of properties_elements) {
        const $input_elem = $(input_elem);
        if (check_property_changed($input_elem, for_realm_default_settings, sub)) {
            const input_value = get_input_element_value($input_elem);
            if (input_value !== undefined) {
                let property_name;
                if (for_realm_default_settings || sub) {
                    property_name = extract_property_name($input_elem, for_realm_default_settings);
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
                        ...stream_edit.get_request_data_for_stream_privacy(input_value),
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
            change_element_block_display_property(
                "realm_email_notification_batching_period_edit_minutes",
                show_elem,
            );
        }

        const $subsection = $(e.target).closest(".settings-subsection-parent");
        save_discard_widget_status_handler($subsection, for_realm_default_settings);
        return undefined;
    });

    $container.on("click", ".subsection-header .subsection-changes-discard button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const $subsection = $(e.target).closest(".settings-subsection-parent");
        for (const elem of get_subsection_property_elements($subsection)) {
            discard_property_element_changes(elem, for_realm_default_settings);
        }
        const $save_btn_controls = $(e.target).closest(".save-button-controls");
        change_save_button_state($save_btn_controls, "discarded");
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
                data.authentication_methods = JSON.stringify(get_auth_method_list_data());
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
    populate_realm_domains_label(page_params.realm_domains);

    // Populate authentication methods table
    populate_auth_methods(page_params.realm_authentication_methods);

    for (const property_name of simple_dropdown_properties) {
        set_property_dropdown_value(property_name);
    }

    set_realm_waiting_period_setting();
    set_video_chat_provider_dropdown();
    set_giphy_rating_dropdown();
    set_msg_edit_limit_dropdown();
    set_msg_move_limit_setting("realm_move_messages_within_stream_limit_seconds");
    set_msg_move_limit_setting("realm_move_messages_between_streams_limit_seconds");
    set_msg_delete_limit_dropdown();
    set_delete_own_message_policy_dropdown(page_params.realm_delete_own_message_policy);
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
        update_custom_value_input("realm_message_content_edit_limit_seconds");
    });

    $("#id_realm_move_messages_between_streams_limit_seconds").on("change", () => {
        update_custom_value_input("realm_move_messages_between_streams_limit_seconds");
    });

    $("#id_realm_move_messages_within_stream_limit_seconds").on("change", () => {
        update_custom_value_input("realm_move_messages_within_stream_limit_seconds");
    });

    $("#id_realm_message_content_delete_limit_seconds").on("change", () => {
        update_custom_value_input("realm_message_content_delete_limit_seconds");
    });

    $("#id_realm_message_retention_days").on("change", (e) => {
        const message_retention_setting_dropdown_value = e.target.value;
        change_element_block_display_property(
            "id_realm_message_retention_custom_input",
            message_retention_setting_dropdown_value === "custom_period",
        );
    });

    $("#id_realm_waiting_period_threshold").on("change", function () {
        const waiting_period_threshold = this.value;
        change_element_block_display_property(
            "id_realm_waiting_period_threshold_custom_input",
            waiting_period_threshold === "custom_period",
        );
    });

    $("#id_realm_digest_emails_enabled").on("change", (e) => {
        const digest_emails_enabled = $(e.target).is(":checked");
        change_element_block_display_property(
            "id_realm_digest_weekday",
            digest_emails_enabled === true,
        );
    });

    $("#id_realm_org_join_restrictions").on("change", (e) => {
        const org_join_restrictions = e.target.value;
        const $node = $("#allowed_domains_label").parent();
        if (org_join_restrictions === "only_selected_domain") {
            $node.show();
            if (page_params.realm_domains.length === 0) {
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
        const property_name = extract_property_name($policy_dropdown_elem);
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
    if (page_params.zulip_plan_is_not_limited) {
        realm_logo.build_realm_logo_widget(upload_realm_logo_or_icon, false);
        realm_logo.build_realm_logo_widget(upload_realm_logo_or_icon, true);
    }

    $("#organization-profile .deactivate_realm_button").on("click", deactivate_organization);
}
