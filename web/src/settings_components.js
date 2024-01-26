import $ from "jquery";

import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";

import * as blueslip from "./blueslip";
import * as compose_banner from "./compose_banner";
import {$t} from "./i18n";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as settings_config from "./settings_config";
import {realm} from "./state_data";
import * as stream_data from "./stream_data";
import * as util from "./util";

const MAX_CUSTOM_TIME_LIMIT_SETTING_VALUE = 2147483647;

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

export function get_realm_time_limits_in_minutes(property) {
    if (realm[property] === null) {
        // This represents "Anytime" case.
        return null;
    }
    let val = (realm[property] / 60).toFixed(1);
    if (Number.parseFloat(val, 10) === Number.parseInt(val, 10)) {
        val = Number.parseInt(val, 10);
    }
    return val.toString();
}

export function get_property_value(property_name, for_realm_default_settings, sub, group) {
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

    if (group) {
        return group[property_name];
    }

    if (property_name === "realm_org_join_restrictions") {
        if (realm.realm_emails_restricted_to_domains) {
            return "only_selected_domain";
        }
        if (realm.realm_disallow_disposable_email_addresses) {
            return "no_disposable_email";
        }
        return "no_restriction";
    }

    return realm[property_name];
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

export function set_property_dropdown_value(property_name) {
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

export function is_video_chat_provider_jitsi_meet() {
    const video_chat_provider_id = Number.parseInt($("#id_realm_video_chat_provider").val(), 10);
    const jitsi_meet_id = realm.realm_available_video_chat_providers.jitsi_meet.id;
    return video_chat_provider_id === jitsi_meet_id;
}

function get_jitsi_server_url_setting_value($input_elem, for_api_data = true) {
    // If the video chat provider dropdown is not set to Jitsi, we return
    // `realm_jitsi_server_url` to indicate that the property remains unchanged.
    // This ensures the appropriate state of the save button and prevents the
    // addition of the `jitsi_server_url` in the API data.
    if (!is_video_chat_provider_jitsi_meet()) {
        return realm.realm_jitsi_server_url;
    }

    const select_elem_val = $input_elem.val();
    if (select_elem_val === "server_default") {
        if (!for_api_data) {
            return null;
        }
        return JSON.stringify("default");
    }

    const $custom_input_elem = $("#id_realm_jitsi_server_url_custom_input");
    if (!for_api_data) {
        return $custom_input_elem.val();
    }
    return JSON.stringify($custom_input_elem.val());
}

export function update_custom_value_input(property_name) {
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

export function get_time_limit_dropdown_setting_value(property_name) {
    if (realm[property_name] === null) {
        return "any_time";
    }

    const valid_limit_values = settings_config.time_limit_dropdown_values.map((x) => x.value);
    if (valid_limit_values.includes(realm[property_name])) {
        return realm[property_name].toString();
    }

    return "custom_period";
}

export function set_time_limit_setting(property_name) {
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

export function sort_object_by_key(obj) {
    const keys = Object.keys(obj).sort();
    const new_obj = {};

    for (const key of keys) {
        new_obj[key] = obj[key];
    }

    return new_obj;
}

export let default_code_language_widget = null;
export let new_stream_announcements_stream_widget = null;
export let signup_announcements_stream_widget = null;
export let zulip_update_announcements_stream_widget = null;
export let create_multiuse_invite_group_widget = null;
export let can_remove_subscribers_group_widget = null;
export let can_access_all_users_group_widget = null;
export let can_mention_group_widget = null;
export let new_group_can_mention_group_widget = null;

export function get_widget_for_dropdown_list_settings(property_name) {
    switch (property_name) {
        case "realm_new_stream_announcements_stream_id":
            return new_stream_announcements_stream_widget;
        case "realm_signup_announcements_stream_id":
            return signup_announcements_stream_widget;
        case "realm_zulip_update_announcements_stream_id":
            return zulip_update_announcements_stream_widget;
        case "realm_default_code_block_language":
            return default_code_language_widget;
        case "realm_create_multiuse_invite_group":
            return create_multiuse_invite_group_widget;
        case "can_remove_subscribers_group":
            return can_remove_subscribers_group_widget;
        case "realm_can_access_all_users_group":
            return can_access_all_users_group_widget;
        case "can_mention_group":
            return can_mention_group_widget;
        default:
            blueslip.error("No dropdown list widget for property", {property_name});
            return null;
    }
}

export function set_default_code_language_widget(widget) {
    default_code_language_widget = widget;
}

export function set_new_stream_announcements_stream_widget(widget) {
    new_stream_announcements_stream_widget = widget;
}

export function set_signup_announcements_stream_widget(widget) {
    signup_announcements_stream_widget = widget;
}

export function set_zulip_update_announcements_stream_widget(widget) {
    zulip_update_announcements_stream_widget = widget;
}

export function set_create_multiuse_invite_group_widget(widget) {
    create_multiuse_invite_group_widget = widget;
}

export function set_can_remove_subscribers_group_widget(widget) {
    can_remove_subscribers_group_widget = widget;
}

export function set_can_access_all_users_group_widget(widget) {
    can_access_all_users_group_widget = widget;
}

export function set_can_mention_group_widget(widget) {
    can_mention_group_widget = widget;
}

export function set_new_group_can_mention_group_widget(widget) {
    new_group_can_mention_group_widget = widget;
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
        case "jitsi-server-url-setting":
            return get_jitsi_server_url_setting_value($input_elem);
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

export function get_auth_method_list_data() {
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

export function check_property_changed(elem, for_realm_default_settings, sub, group) {
    const $elem = $(elem);
    const property_name = extract_property_name($elem, for_realm_default_settings);
    let current_val = get_property_value(property_name, for_realm_default_settings, sub, group);
    let proposed_val;

    switch (property_name) {
        case "realm_authentication_methods":
            current_val = sort_object_by_key(current_val);
            current_val = JSON.stringify(current_val);
            proposed_val = get_auth_method_list_data();
            proposed_val = JSON.stringify(proposed_val);
            break;
        case "realm_new_stream_announcements_stream_id":
        case "realm_signup_announcements_stream_id":
        case "realm_zulip_update_announcements_stream_id":
        case "realm_default_code_block_language":
        case "can_remove_subscribers_group":
        case "realm_create_multiuse_invite_group":
        case "can_mention_group":
        case "realm_can_access_all_users_group":
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
        case "realm_jitsi_server_url":
            proposed_val = get_jitsi_server_url_setting_value($elem, false);
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

export function save_discard_widget_status_handler(
    $subsection,
    for_realm_default_settings,
    sub,
    group,
) {
    $subsection.find(".subsection-failed-status p").hide();
    $subsection.find(".save-button").show();
    const properties_elements = get_subsection_property_elements($subsection);
    const show_change_process_button = properties_elements.some((elem) =>
        check_property_changed(elem, for_realm_default_settings, sub, group),
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

function should_disable_save_button_for_jitsi_server_url_setting() {
    if (!is_video_chat_provider_jitsi_meet()) {
        return false;
    }

    const $dropdown_elem = $("#id_realm_jitsi_server_url");
    const $custom_input_elem = $("#id_realm_jitsi_server_url_custom_input");

    return $dropdown_elem.val() === "custom" && !util.is_valid_url($custom_input_elem.val(), true);
}

function should_disable_save_button_for_time_limit_settings(time_limit_settings) {
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

    return disable_save_btn;
}

function enable_or_disable_save_button($subsection_elem) {
    const time_limit_settings = [...$subsection_elem.find(".time-limit-setting")];

    let disable_save_btn = false;
    if (time_limit_settings.length) {
        disable_save_btn = should_disable_save_button_for_time_limit_settings(time_limit_settings);
    } else if ($subsection_elem.attr("id") === "org-other-settings") {
        disable_save_btn = should_disable_save_button_for_jitsi_server_url_setting();
    }

    $subsection_elem.find(".subsection-changes-save button").prop("disabled", disable_save_btn);
}
