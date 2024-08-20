import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";
import {z} from "zod";

import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";

import * as blueslip from "./blueslip";
import * as compose_banner from "./compose_banner";
import type {DropdownWidget} from "./dropdown_widget";
import {$t} from "./i18n";
import {
    LEGACY_FONT_SIZE_PX,
    LEGACY_LINE_HEIGHT_PERCENT,
    NON_COMPACT_MODE_FONT_SIZE_PX,
    NON_COMPACT_MODE_LINE_HEIGHT_PERCENT,
} from "./information_density";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as scroll_util from "./scroll_util";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import type {CustomProfileField} from "./state_data";
import {realm} from "./state_data";
import * as stream_data from "./stream_data";
import type {StreamSubscription} from "./sub_store";
import type {HTMLSelectOneElement} from "./types";
import type {UserGroup} from "./user_groups";
import * as util from "./util";

const MAX_CUSTOM_TIME_LIMIT_SETTING_VALUE = 2147483647;

type SettingOptionValue = {
    order?: number;
    code: number;
    description: string;
};

type SettingOptionValueWithKey = SettingOptionValue & {key: string};

export function get_sorted_options_list(
    option_values_object: Record<string, SettingOptionValue>,
): SettingOptionValueWithKey[] {
    const options_list: SettingOptionValueWithKey[] = Object.entries(option_values_object).map(
        ([key, value]) => ({...value, key}),
    );
    let comparator: (x: SettingOptionValueWithKey, y: SettingOptionValueWithKey) => number;

    if (options_list[0] !== undefined && !options_list[0].order) {
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
    } else {
        comparator = (x, y) => {
            assert(x.order !== undefined);
            assert(y.order !== undefined);
            return x.order - y.order;
        };
    }
    options_list.sort(comparator);
    return options_list;
}

type MessageTimeLimitSetting =
    | "realm_message_content_edit_limit_seconds"
    | "realm_move_messages_between_streams_limit_seconds"
    | "realm_move_messages_within_stream_limit_seconds"
    | "realm_message_content_delete_limit_seconds";

export function get_realm_time_limits_in_minutes(property: MessageTimeLimitSetting): string {
    const setting_value = realm[property];
    if (setting_value === null) {
        // This represents "Anytime" case.
        return "";
    }
    let val = (setting_value / 60).toFixed(1);
    if (Number.parseFloat(val) === Number.parseInt(val, 10)) {
        val = (setting_value / 60).toFixed(0);
    }
    return val;
}

type RealmSetting = typeof realm;
type RealmSettingProperties = keyof RealmSetting | "realm_org_join_restrictions";

type RealmUserSettingDefaultType = typeof realm_user_settings_defaults;
type RealmUserSettingDefaultProperties =
    | keyof RealmUserSettingDefaultType
    | "email_notification_batching_period_edit_minutes";

type StreamSettingProperties = keyof StreamSubscription | "stream_privacy" | "is_default_stream";

type valueof<T> = T[keyof T];

export function get_realm_settings_property_value(
    property_name: RealmSettingProperties,
): valueof<RealmSetting> {
    if (property_name === "realm_org_join_restrictions") {
        if (realm.realm_emails_restricted_to_domains) {
            return "only_selected_domain";
        }
        if (realm.realm_disallow_disposable_email_addresses) {
            return "no_disposable_email";
        }
        return "no_restriction";
    }

    if (property_name === "realm_authentication_methods") {
        return JSON.stringify(realm_authentication_methods_to_boolean_dict());
    }
    return realm[property_name];
}

export function get_stream_settings_property_value(
    property_name: StreamSettingProperties,
    sub: StreamSubscription,
): valueof<StreamSubscription> {
    if (property_name === "stream_privacy") {
        return stream_data.get_stream_privacy_policy(sub.stream_id);
    }
    if (property_name === "is_default_stream") {
        return stream_data.is_default_stream_id(sub.stream_id);
    }
    return sub[property_name];
}

export function get_group_property_value(
    property_name: keyof UserGroup,
    group: UserGroup,
): valueof<UserGroup> {
    return group[property_name];
}

export function get_custom_profile_property_value(
    property_name: keyof CustomProfileField,
    custom_profile_field: CustomProfileField,
): valueof<CustomProfileField> {
    const value = custom_profile_field[property_name];
    if (property_name === "display_in_profile_summary" && value === undefined) {
        return false;
    }
    return value;
}

export function get_realm_default_setting_property_value(
    property_name: RealmUserSettingDefaultProperties,
): valueof<RealmUserSettingDefaultType> {
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

export function realm_authentication_methods_to_boolean_dict(): Record<string, boolean> {
    return Object.fromEntries(
        Object.entries(realm.realm_authentication_methods)
            .sort()
            .map(([auth_method_name, auth_method_info]) => [
                auth_method_name,
                auth_method_info.enabled,
            ]),
    );
}

export function extract_property_name($elem: JQuery, for_realm_default_settings?: boolean): string {
    const elem_id = $elem.attr("id");
    assert(elem_id !== undefined);
    if (for_realm_default_settings) {
        // ID for realm_user_default_settings elements are of the form
        // "realm_{settings_name}}" because both user and realm default
        // settings use the same template and each element should have
        // unique id.
        return /^realm_(.*)$/.exec(elem_id.replaceAll("-", "_"))![1]!;
    }

    if (elem_id.startsWith("id_authmethod")) {
        // Authentication Method component IDs include authentication method name
        // for uniqueness, anchored to "id_authmethod" prefix, e.g. "id_authmethodapple_<property_name>".
        // We need to strip that whole construct down to extract the actual property name.
        // The [\da-z]+ part of the regexp covers the auth method name itself.
        // We assume it's not an empty string and can contain only digits and lowercase ASCII letters,
        // this is ensured by a respective allowlist-based filter in populate_auth_methods().
        return /^id_authmethod[\da-z]+_(.*)$/.exec(elem_id)![1]!;
    }

    if (elem_id.startsWith("id-custom-profile-field")) {
        return /^id_custom_profile_field_(.*)$/.exec(elem_id.replaceAll("-", "_"))![1]!;
    }

    return /^id_(.*)$/.exec(elem_id.replaceAll("-", "_"))![1]!;
}

export function get_subsection_property_elements($subsection: JQuery): HTMLElement[] {
    return [...$subsection.find(".prop-element")];
}

type simple_dropdown_realm_settings = Pick<
    typeof realm,
    | "realm_create_private_stream_policy"
    | "realm_invite_to_stream_policy"
    | "realm_user_group_edit_policy"
    | "realm_add_custom_emoji_policy"
    | "realm_invite_to_realm_policy"
    | "realm_wildcard_mention_policy"
    | "realm_move_messages_between_streams_policy"
    | "realm_edit_topic_policy"
    | "realm_org_type"
>;

export function set_property_dropdown_value(
    property_name: keyof simple_dropdown_realm_settings,
): void {
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const property_value = get_realm_settings_property_value(
        property_name,
    ) as valueof<simple_dropdown_realm_settings>;
    $(`#id_${CSS.escape(property_name)}`).val(property_value);
}

export function change_element_block_display_property(
    elem_id: string,
    show_element: boolean,
): void {
    const $elem = $(`#${CSS.escape(elem_id)}`);
    if (show_element) {
        $elem.parent().show();
    } else {
        $elem.parent().hide();
    }
}

export function is_video_chat_provider_jitsi_meet(): boolean {
    const video_chat_provider_id = Number.parseInt(
        $<HTMLSelectOneElement>("select:not([multiple])#id_realm_video_chat_provider").val()!,
        10,
    );
    const jitsi_meet_id = realm.realm_available_video_chat_providers.jitsi_meet.id;
    return video_chat_provider_id === jitsi_meet_id;
}

function get_jitsi_server_url_setting_value(
    $input_elem: JQuery<HTMLSelectElement>,
    for_api_data = true,
): string | null {
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

    const $custom_input_elem = $<HTMLInputElement>("input#id_realm_jitsi_server_url_custom_input");
    if (!for_api_data) {
        return $custom_input_elem.val()!;
    }
    return JSON.stringify($custom_input_elem.val());
}

export function update_custom_value_input(property_name: MessageTimeLimitSetting): void {
    const $dropdown_elem = $(`#id_${CSS.escape(property_name)}`);
    const custom_input_elem_id = $dropdown_elem
        .parent()
        .find(".time-limit-custom-input")
        .attr("id")!;

    const show_custom_limit_input = $dropdown_elem.val() === "custom_period";
    change_element_block_display_property(custom_input_elem_id, show_custom_limit_input);
    if (show_custom_limit_input) {
        $(`#${CSS.escape(custom_input_elem_id)}`).val(
            get_realm_time_limits_in_minutes(property_name),
        );
    }
}

export function get_time_limit_dropdown_setting_value(
    property_name: MessageTimeLimitSetting,
): string {
    const value = realm[property_name];
    if (value === null) {
        return "any_time";
    }

    const valid_limit_values = settings_config.time_limit_dropdown_values.map((x) => x.value);
    if (valid_limit_values.includes(value)) {
        return value.toString();
    }

    return "custom_period";
}

export function set_time_limit_setting(property_name: MessageTimeLimitSetting): void {
    const dropdown_elem_val = get_time_limit_dropdown_setting_value(property_name);
    $(`#id_${CSS.escape(property_name)}`).val(dropdown_elem_val);

    const $custom_input = $(`#id_${CSS.escape(property_name)}`)
        .parent()
        .find(".time-limit-custom-input");
    $custom_input.val(get_realm_time_limits_in_minutes(property_name));

    change_element_block_display_property(
        $custom_input.attr("id")!,
        dropdown_elem_val === "custom_period",
    );
}

function check_valid_number_input(input_value: string, keep_number_as_float = false): number {
    // This check is important to make sure that inputs like "24a" are
    // considered invalid and this function returns NaN for such inputs.
    // Number.parseInt and Number.parseFloat will convert strings like
    // "24a" to 24.
    if (Number.isNaN(Number(input_value))) {
        return Number.NaN;
    }

    if (keep_number_as_float) {
        return Number.parseFloat(Number.parseFloat(input_value).toFixed(1));
    }

    return Number.parseInt(input_value, 10);
}

function get_message_retention_setting_value(
    $input_elem: JQuery<HTMLSelectElement>,
    for_api_data = true,
): string | number | null {
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

    const custom_input_val = $input_elem
        .parent()
        .find<HTMLInputElement>(".message-retention-setting-custom-input")
        .val()!;
    if (custom_input_val.length === 0) {
        return settings_config.retain_message_forever;
    }
    return check_valid_number_input(custom_input_val);
}

export const select_field_data_schema = z.record(z.object({text: z.string(), order: z.string()}));
export type SelectFieldData = z.output<typeof select_field_data_schema>;

function read_select_field_data_from_form(
    $profile_field_form: JQuery,
    old_field_data: unknown,
): SelectFieldData {
    const field_data: SelectFieldData = {};
    let field_order = 1;

    const old_option_value_map = new Map<string, string>();
    if (old_field_data !== undefined) {
        for (const [value, choice] of Object.entries(
            select_field_data_schema.parse(old_field_data),
        )) {
            assert(typeof choice !== "string");
            old_option_value_map.set(choice.text, value);
        }
    }
    $profile_field_form.find("div.choice-row").each(function (this: HTMLElement) {
        const text = util.the($(this).find("input")).value;
        if (text) {
            let value = old_option_value_map.get(text);
            if (value !== undefined) {
                // Resetting the data-value in the form is
                // important if the user removed an option string
                // and then added it back again before saving
                // changes.
                $(this).attr("data-value", value);
            } else {
                value = $(this).attr("data-value")!;
            }
            field_data[value] = {text, order: field_order.toString()};
            field_order += 1;
        }
    });

    return field_data;
}

export const external_account_field_schema = z.object({
    subtype: z.string(),
    url_pattern: z.optional(z.string()),
});

export type ExternalAccountFieldData = z.output<typeof external_account_field_schema>;

function read_external_account_field_data($profile_field_form: JQuery): ExternalAccountFieldData {
    const field_data: ExternalAccountFieldData = {
        subtype: $profile_field_form
            .find<HTMLSelectOneElement>("select:not([multiple])[name=external_acc_field_type]")
            .val()!,
    };
    if (field_data.subtype === "custom") {
        field_data.url_pattern = $profile_field_form
            .find<HTMLInputElement>("input[name=url_pattern]")
            .val()!;
    }
    return field_data;
}

export type FieldData = SelectFieldData | ExternalAccountFieldData;

export function read_field_data_from_form(
    field_type_id: number,
    $profile_field_form: JQuery,
    old_field_data: unknown,
): FieldData | undefined {
    const field_types = realm.custom_profile_field_types;

    // Only the following field types support associated field data.
    if (field_type_id === field_types.SELECT.id) {
        return read_select_field_data_from_form($profile_field_form, old_field_data);
    } else if (field_type_id === field_types.EXTERNAL_ACCOUNT.id) {
        return read_external_account_field_data($profile_field_form);
    }
    return undefined;
}

function get_field_data_input_value($input_elem: JQuery): string | undefined {
    const $profile_field_form = $input_elem.closest(".profile-field-form");
    const profile_field_id = Number.parseInt(
        $($profile_field_form).attr("data-profile-field-id")!,
        10,
    );
    const field = realm.custom_profile_fields.find((field) => field.id === profile_field_id)!;

    const proposed_value = read_field_data_from_form(
        field.type,
        $profile_field_form,
        JSON.parse(field.field_data),
    );
    return JSON.stringify(proposed_value);
}

export let new_group_can_manage_group_widget: DropdownWidget | null = null;
export let new_group_can_mention_group_widget: DropdownWidget | null = null;

const dropdown_widget_map = new Map<string, DropdownWidget | null>([
    ["realm_new_stream_announcements_stream_id", null],
    ["realm_signup_announcements_stream_id", null],
    ["realm_zulip_update_announcements_stream_id", null],
    ["realm_default_code_block_language", null],
    ["realm_create_multiuse_invite_group", null],
    ["can_remove_subscribers_group", null],
    ["realm_can_access_all_users_group", null],
    ["can_manage_group", null],
    ["can_mention_group", null],
    ["realm_can_create_public_channel_group", null],
    ["realm_can_create_private_channel_group", null],
    ["realm_can_create_web_public_channel_group", null],
    ["realm_can_delete_any_message_group", null],
    ["realm_direct_message_initiator_group", null],
    ["realm_direct_message_permission_group", null],
]);

export function get_widget_for_dropdown_list_settings(
    property_name: string,
): DropdownWidget | null {
    const dropdown_widget = dropdown_widget_map.get(property_name);

    if (dropdown_widget === undefined) {
        blueslip.error("No dropdown list widget for property", {property_name});
        return null;
    }

    return dropdown_widget;
}

export function set_dropdown_setting_widget(property_name: string, widget: DropdownWidget): void {
    if (dropdown_widget_map.get(property_name) === undefined) {
        blueslip.error("No dropdown list widget for property", {property_name});
        return;
    }

    dropdown_widget_map.set(property_name, widget);
}

export function set_new_group_can_mention_group_widget(widget: DropdownWidget): void {
    new_group_can_mention_group_widget = widget;
}

export function set_new_group_can_manage_group_widget(widget: DropdownWidget): void {
    new_group_can_manage_group_widget = widget;
}

export function set_dropdown_list_widget_setting_value(
    property_name: string,
    value: number | string,
): void {
    const widget = get_widget_for_dropdown_list_settings(property_name);
    assert(widget !== null);
    widget.render(value);
}

export function get_dropdown_list_widget_setting_value($input_elem: JQuery): number | string {
    const widget_name = extract_property_name($input_elem);
    const setting_widget = get_widget_for_dropdown_list_settings(widget_name);
    assert(setting_widget !== null);

    const setting_value = setting_widget.value();
    assert(setting_value !== undefined);

    return setting_value;
}

export function change_save_button_state($element: JQuery, state: string): void {
    function show_hide_element(
        $element: JQuery,
        show: boolean,
        fadeout_delay: number,
        fadeout_callback: (this: HTMLElement) => void,
    ): void {
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
        let hide_delay = 0;
        if ($saveBtn.attr("data-status") === "saved") {
            // Keep saved button displayed a little longer.
            hide_delay = 500;
        }
        show_hide_element($element, false, hide_delay, () => {
            enable_or_disable_save_button($element.closest(".settings-subsection-parent"));
        });
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

    assert(button_text !== undefined);
    $textEl.text(button_text);
    assert(data_status !== undefined);
    $saveBtn.attr("data-status", data_status);
    if (state === "unsaved") {
        // Do not scroll if the currently focused element is a textarea or an input
        // of type text, to not interrupt the user's typing flow. Scrolling will happen
        // anyway when the field loses focus (via the change event) if necessary.
        if (
            !document.activeElement ||
            !$(document.activeElement).is('textarea, input[type="text"]')
        ) {
            // Ensure the save button is visible when the state is "unsaved",
            // so the user does not miss saving their changes.
            scroll_util.scroll_element_into_container(
                $element.parent(".subsection-header"),
                $("#settings_content"),
            );
        }
        enable_or_disable_save_button($element.closest(".settings-subsection-parent"));
    }
    assert(is_show !== undefined);
    show_hide_element($element, is_show, 800, () => {
        // There is no need for a callback here since we have already
        // called the function to enable or disable save button.
    });
}

function get_input_type($input_elem: JQuery, input_type?: string): string {
    if (input_type !== undefined && ["boolean", "string", "number"].includes(input_type)) {
        return input_type;
    }
    input_type = $input_elem.attr("data-setting-widget-type");
    assert(input_type !== undefined);
    return input_type;
}

export function get_input_element_value(
    input_elem: HTMLElement,
    input_type?: string,
): boolean | number | string | null | undefined {
    const $input_elem = $(input_elem);
    input_type = get_input_type($input_elem, input_type);
    let input_value;
    switch (input_type) {
        case "boolean":
            assert(input_elem instanceof HTMLInputElement);
            return input_elem.checked;
        case "string":
            assert(
                input_elem instanceof HTMLInputElement ||
                    input_elem instanceof HTMLSelectElement ||
                    input_elem instanceof HTMLTextAreaElement,
            );
            input_value = $(input_elem).val()!;
            assert(typeof input_value === "string");
            return input_value.trim();
        case "number":
            assert(
                input_elem instanceof HTMLInputElement || input_elem instanceof HTMLSelectElement,
            );
            input_value = $(input_elem).val()!;
            assert(typeof input_value === "string");
            return Number.parseInt(input_value.trim(), 10);
        case "radio-group": {
            const selected_val = $input_elem.find<HTMLInputElement>("input:checked").val()!;
            if ($input_elem.data("setting-choice-type") === "number") {
                return Number.parseInt(selected_val, 10);
            }
            return selected_val.trim();
        }
        case "time-limit":
            assert(input_elem instanceof HTMLSelectElement);
            return get_time_limit_setting_value($(input_elem));
        case "jitsi-server-url-setting":
            assert(input_elem instanceof HTMLSelectElement);
            return get_jitsi_server_url_setting_value($(input_elem));
        case "message-retention-setting":
            assert(input_elem instanceof HTMLSelectElement);
            return get_message_retention_setting_value($(input_elem));
        case "dropdown-list-widget":
            return get_dropdown_list_widget_setting_value($input_elem);
        case "field-data-setting":
            return get_field_data_input_value($input_elem);
        case "language-setting":
            return $input_elem.find(".language_selection_button span").attr("data-language-code");
        case "auth-methods":
            return JSON.stringify(get_auth_method_list_data());
        default:
            return undefined;
    }
}

export function set_input_element_value(
    $input_elem: JQuery,
    value: number | string | boolean,
): void {
    const input_type = get_input_type($input_elem, typeof value);
    if (input_type) {
        if (input_type === "boolean") {
            assert(typeof value === "boolean");
            $input_elem.prop("checked", value);
            return;
        } else if (input_type === "string" || input_type === "number") {
            assert(typeof value !== "boolean");
            $input_elem.val(value);
            return;
        }
    }
    blueslip.error("Failed to set value of property", {
        property: extract_property_name($input_elem),
    });
    return;
}

export function get_auth_method_list_data(): Record<string, boolean> {
    const new_auth_methods: Record<string, boolean> = {};
    const $auth_method_rows = $("#id_realm_authentication_methods").find("div.method_row");

    for (const method_row of $auth_method_rows) {
        const method = $(method_row).attr("data-method");
        assert(method !== undefined);
        new_auth_methods[method] = util.the($(method_row).find<HTMLInputElement>("input")).checked;
    }

    return new_auth_methods;
}

export function parse_time_limit($elem: JQuery<HTMLInputElement>): number {
    const time_limit_in_minutes = check_valid_number_input($elem.val()!, true);
    return Math.floor(time_limit_in_minutes * 60);
}

function get_time_limit_setting_value(
    $input_elem: JQuery<HTMLSelectElement>,
    for_api_data = true,
): string | number | null {
    const select_elem_val = $input_elem.val()!;

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
        assert(typeof select_elem_val === "string");
        return Number.parseInt(select_elem_val, 10);
    }

    const $custom_input_elem = $input_elem
        .parent()
        .find<HTMLInputElement>("input.time-limit-custom-input");
    if ($custom_input_elem.val() === "") {
        // This handles the case where the initial setting value is "Any time" and then
        // dropdown is changed to "Custom" where the input box is empty initially and
        // thus we do not show the save-discard widget until something is typed in the
        // input box.
        return null;
    }

    if ($input_elem.attr("id") === "id_realm_waiting_period_threshold") {
        // For realm waiting period threshold setting, the custom input element contains
        // number of days.
        return check_valid_number_input($custom_input_elem.val()!);
    }

    return parse_time_limit($custom_input_elem);
}

export function check_realm_settings_property_changed(elem: HTMLElement): boolean {
    const $elem = $(elem);

    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const property_name = extract_property_name($elem) as RealmSettingProperties;
    const current_val = get_realm_settings_property_value(property_name);
    let proposed_val;
    switch (property_name) {
        case "realm_authentication_methods":
            proposed_val = get_input_element_value(elem, "auth-methods");
            break;
        case "realm_new_stream_announcements_stream_id":
        case "realm_signup_announcements_stream_id":
        case "realm_zulip_update_announcements_stream_id":
        case "realm_default_code_block_language":
        case "realm_create_multiuse_invite_group":
        case "realm_can_access_all_users_group":
        case "realm_can_create_public_channel_group":
        case "realm_can_create_private_channel_group":
        case "realm_can_create_web_public_channel_group":
        case "realm_can_delete_any_message_group":
        case "realm_direct_message_initiator_group":
        case "realm_direct_message_permission_group":
            proposed_val = get_dropdown_list_widget_setting_value($elem);
            break;
        case "realm_message_content_edit_limit_seconds":
        case "realm_message_content_delete_limit_seconds":
        case "realm_move_messages_between_streams_limit_seconds":
        case "realm_move_messages_within_stream_limit_seconds":
        case "realm_waiting_period_threshold":
            assert(elem instanceof HTMLSelectElement);
            proposed_val = get_time_limit_setting_value($(elem), false);
            break;
        case "realm_message_retention_days":
            assert(elem instanceof HTMLSelectElement);
            proposed_val = get_message_retention_setting_value($(elem), false);
            break;
        case "realm_jitsi_server_url":
            assert(elem instanceof HTMLSelectElement);
            proposed_val = get_jitsi_server_url_setting_value($(elem), false);
            break;
        case "realm_default_language":
            proposed_val = $(
                "#org-notifications .language_selection_widget .language_selection_button span",
            ).attr("data-language-code");
            break;
        default:
            if (current_val !== undefined) {
                proposed_val = get_input_element_value(elem, typeof current_val);
            } else {
                blueslip.error("Element refers to unknown property", {property_name});
            }
    }
    return current_val !== proposed_val;
}

export function check_stream_settings_property_changed(
    elem: HTMLElement,
    sub: StreamSubscription,
): boolean {
    const $elem = $(elem);
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const property_name = extract_property_name($elem) as StreamSettingProperties;
    const current_val = get_stream_settings_property_value(property_name, sub);
    let proposed_val;
    switch (property_name) {
        case "can_remove_subscribers_group":
            proposed_val = get_dropdown_list_widget_setting_value($elem);
            break;
        case "message_retention_days":
            assert(elem instanceof HTMLSelectElement);
            proposed_val = get_message_retention_setting_value($(elem), false);
            break;
        case "stream_privacy":
            proposed_val = get_input_element_value(elem, "radio-group");
            break;
        default:
            if (current_val !== undefined) {
                proposed_val = get_input_element_value(elem, typeof current_val);
            } else {
                blueslip.error("Element refers to unknown property", {property_name});
            }
    }
    return current_val !== proposed_val;
}

export function check_group_property_changed(elem: HTMLElement, group: UserGroup): boolean {
    const $elem = $(elem);
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const property_name = extract_property_name($elem) as keyof UserGroup;
    const current_val = get_group_property_value(property_name, group);
    let proposed_val;
    switch (property_name) {
        case "can_manage_group":
        case "can_mention_group":
            proposed_val = get_dropdown_list_widget_setting_value($elem);
            break;
        default:
            if (current_val !== undefined) {
                proposed_val = get_input_element_value(elem, typeof current_val);
            } else {
                blueslip.error("Element refers to unknown property", {property_name});
            }
    }
    return current_val !== proposed_val;
}

export function check_custom_profile_property_changed(
    elem: HTMLElement,
    custom_profile_field: CustomProfileField,
): boolean {
    const $elem = $(elem);
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const property_name = extract_property_name($elem) as keyof CustomProfileField;
    const current_val = get_custom_profile_property_value(property_name, custom_profile_field);
    let proposed_val;
    if (property_name === "field_data") {
        proposed_val = get_input_element_value(elem, "field-data-setting");
    } else if (current_val !== undefined) {
        proposed_val = get_input_element_value(elem, typeof current_val);
    } else {
        blueslip.error("Element refers to unknown property", {property_name});
    }
    return current_val !== proposed_val;
}

export function check_realm_default_settings_property_changed(elem: HTMLElement): boolean {
    const $elem = $(elem);
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const property_name = extract_property_name($elem, true) as RealmUserSettingDefaultProperties;
    const current_val = get_realm_default_setting_property_value(property_name);
    let proposed_val;
    switch (property_name) {
        case "emojiset":
        case "user_list_style":
            proposed_val = get_input_element_value(elem, "radio-group");
            break;
        case "email_notifications_batching_period_seconds":
            assert(elem instanceof HTMLSelectElement);
            proposed_val = get_time_limit_setting_value($(elem), false);
            break;
        default:
            if (current_val !== undefined) {
                proposed_val = get_input_element_value(elem, typeof current_val);
            } else {
                blueslip.error("Element refers to unknown property", {property_name});
            }
    }
    return current_val !== proposed_val;
}

function get_request_data_for_org_join_restrictions(selected_val: string): {
    disallow_disposable_email_addresses: boolean;
    emails_restricted_to_domains: boolean;
} {
    switch (selected_val) {
        case "only_selected_domain": {
            return {
                emails_restricted_to_domains: true,
                disallow_disposable_email_addresses: false,
            };
        }
        case "no_disposable_email": {
            return {
                emails_restricted_to_domains: false,
                disallow_disposable_email_addresses: true,
            };
        }
        default: {
            return {
                disallow_disposable_email_addresses: false,
                emails_restricted_to_domains: false,
            };
        }
    }
}

export function populate_data_for_realm_settings_request(
    $subsection_elem: JQuery,
): Record<string, string | boolean | number> {
    let data: Record<string, string | boolean | number> = {};
    const properties_elements = get_subsection_property_elements($subsection_elem);
    for (const input_elem of properties_elements) {
        const $input_elem = $(input_elem);
        if (check_realm_settings_property_changed(input_elem)) {
            const input_value = get_input_element_value(input_elem);
            if (input_value !== undefined && input_value !== null) {
                let property_name: string;
                if ($input_elem.attr("id")!.startsWith("id_authmethod")) {
                    // Authentication Method component IDs include authentication method name
                    // for uniqueness, anchored to "id_authmethod" prefix, e.g. "id_authmethodapple_<property_name>".
                    // We need to strip that whole construct down to extract the actual property name.
                    // The [\da-z]+ part of the regexp covers the auth method name itself.
                    // We assume it's not an empty string and can contain only digits and lowercase ASCII letters,
                    // this is ensured by a respective allowlist-based filter in populate_auth_methods().
                    const match_array = /^id_authmethod[\da-z]+_(.*)$/.exec(
                        $input_elem.attr("id")!,
                    );
                    assert(match_array !== null);
                    property_name = match_array[1]!;
                } else {
                    const match_array = /^id_realm_(.*)$/.exec($input_elem.attr("id")!);
                    assert(match_array !== null);
                    property_name = match_array[1]!;
                }

                if (property_name === "org_join_restrictions") {
                    data = {
                        ...data,
                        ...get_request_data_for_org_join_restrictions(input_value.toString()),
                    };
                    continue;
                }

                const realm_group_settings_using_new_api_format = new Set([
                    "can_create_private_channel_group",
                    "can_create_public_channel_group",
                    "can_create_web_public_channel_group",
                    "can_delete_any_message_group",
                    "direct_message_initiator_group",
                    "direct_message_permission_group",
                ]);
                if (realm_group_settings_using_new_api_format.has(property_name)) {
                    const old_value = get_realm_settings_property_value(
                        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
                        ("realm_" + property_name) as RealmSettingProperties,
                    );
                    data[property_name] = JSON.stringify({
                        new: input_value,
                        old: old_value,
                    });
                    continue;
                }

                data[property_name] = input_value;
            }
        }
    }
    return data;
}

export function populate_data_for_stream_settings_request(
    $subsection_elem: JQuery,
    sub: StreamSubscription,
): Record<string, string | boolean | number> {
    let data: Record<string, string | boolean | number> = {};
    const properties_elements = get_subsection_property_elements($subsection_elem);
    for (const input_elem of properties_elements) {
        const $input_elem = $(input_elem);
        if (check_stream_settings_property_changed(input_elem, sub)) {
            const input_value = get_input_element_value(input_elem);
            if (input_value !== undefined && input_value !== null) {
                const property_name = extract_property_name($input_elem);
                if (property_name === "stream_privacy") {
                    data = {
                        ...data,
                        ...settings_data.get_request_data_for_stream_privacy(
                            input_value.toString(),
                        ),
                    };
                    continue;
                }
                data[property_name] = input_value;
            }
        }
    }
    return data;
}

export function populate_data_for_group_request(
    $subsection_elem: JQuery,
    group: UserGroup,
): Record<string, string | boolean | number> {
    const data: Record<string, string | boolean | number> = {};
    const properties_elements = get_subsection_property_elements($subsection_elem);
    for (const input_elem of properties_elements) {
        const $input_elem = $(input_elem);
        if (check_group_property_changed(input_elem, group)) {
            const input_value = get_input_element_value(input_elem);
            if (input_value !== undefined && input_value !== null) {
                // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
                const property_name = extract_property_name($input_elem) as keyof UserGroup;
                const old_value = get_group_property_value(property_name, group);
                data[property_name] = JSON.stringify({
                    new: input_value,
                    old: old_value,
                });
            }
        }
    }
    return data;
}

export function populate_data_for_custom_profile_field_request(
    $subsection_elem: JQuery,
    custom_profile_field: CustomProfileField,
): Record<string, string | boolean | number> {
    const data: Record<string, string | boolean | number> = {};
    const properties_elements = get_subsection_property_elements($subsection_elem);
    for (const input_elem of properties_elements) {
        const $input_elem = $(input_elem);
        if (check_custom_profile_property_changed(input_elem, custom_profile_field)) {
            const input_value = get_input_element_value(input_elem);
            if (input_value !== undefined && input_value !== null) {
                const property_name = extract_property_name($input_elem);
                data[property_name] = input_value;
            }
        }
    }
    return data;
}

export function populate_data_for_default_realm_settings_request(
    $subsection_elem: JQuery,
): Record<string, string | boolean | number> {
    const data: Record<string, string | boolean | number> = {};
    const properties_elements = get_subsection_property_elements($subsection_elem);
    for (const input_elem of properties_elements) {
        const $input_elem = $(input_elem);
        if (check_realm_default_settings_property_changed(input_elem)) {
            const input_value = get_input_element_value(input_elem);
            if (input_value !== undefined && input_value !== null) {
                const property_name: string = extract_property_name($input_elem, true);
                data[property_name] = input_value;

                if (property_name === "dense_mode") {
                    data.web_font_size_px = input_value
                        ? LEGACY_FONT_SIZE_PX
                        : NON_COMPACT_MODE_FONT_SIZE_PX;
                    data.web_line_height_percent = input_value
                        ? LEGACY_LINE_HEIGHT_PERCENT
                        : NON_COMPACT_MODE_LINE_HEIGHT_PERCENT;
                }
            }
        }
    }

    return data;
}

function switching_to_private(properties_elements: HTMLElement[]): boolean {
    for (const elem of properties_elements) {
        const $elem = $(elem);
        const property_name = extract_property_name($elem);
        if (property_name !== "stream_privacy") {
            continue;
        }
        const proposed_val = get_input_element_value(elem, "radio-group");
        return proposed_val === "invite-only-public-history" || proposed_val === "invite-only";
    }
    return false;
}

export function save_discard_realm_settings_widget_status_handler($subsection: JQuery): void {
    $subsection.find(".subsection-failed-status p").hide();
    $subsection.find(".save-button").show();
    const properties_elements = get_subsection_property_elements($subsection);
    const show_change_process_button = properties_elements.some((elem) =>
        check_realm_settings_property_changed(elem),
    );

    const $save_btn_controls = $subsection.find(".subsection-header .save-button-controls");
    const button_state = show_change_process_button ? "unsaved" : "discarded";
    change_save_button_state($save_btn_controls, button_state);
}

export function save_discard_stream_settings_widget_status_handler(
    $subsection: JQuery,
    sub: StreamSubscription,
): void {
    $subsection.find(".subsection-failed-status p").hide();
    $subsection.find(".save-button").show();
    const properties_elements = get_subsection_property_elements($subsection);
    const show_change_process_button = properties_elements.some((elem) =>
        check_stream_settings_property_changed(elem, sub),
    );

    const $save_btn_controls = $subsection.find(".subsection-header .save-button-controls");
    const button_state = show_change_process_button ? "unsaved" : "discarded";
    change_save_button_state($save_btn_controls, button_state);

    // If the stream isn't currently private but being changed to private,
    // and the user changing this setting isn't subscribed, we show a
    // warning that they won't be able to access the stream after
    // making it private unless they subscribe.
    if (
        button_state === "unsaved" &&
        !sub.invite_only &&
        !sub.subscribed &&
        switching_to_private(properties_elements)
    ) {
        if ($("#stream_permission_settings .stream_privacy_warning").length > 0) {
            return;
        }
        const context = {
            banner_type: compose_banner.WARNING,
            banner_text: $t({
                defaultMessage:
                    "Only subscribers can access or join private channels, so you will lose access to this channel if you convert it to a private channel while not subscribed to it.",
            }),
            button_text: $t({defaultMessage: "Subscribe"}),
            classname: "stream_privacy_warning",
            stream_id: sub.stream_id,
        };
        $("#stream_permission_settings .stream-permissions-warning-banner").append(
            $(render_compose_banner(context)),
        );
    } else {
        $("#stream_permission_settings .stream-permissions-warning-banner").empty();
    }
}

export function save_discard_group_widget_status_handler(
    $subsection: JQuery,
    group: UserGroup,
): void {
    $subsection.find(".subsection-failed-status p").hide();
    $subsection.find(".save-button").show();
    const properties_elements = get_subsection_property_elements($subsection);
    const show_change_process_button = properties_elements.some((elem) =>
        check_group_property_changed(elem, group),
    );
    const $save_btn_controls = $subsection.find(".subsection-header .save-button-controls");
    const button_state = show_change_process_button ? "unsaved" : "discarded";
    change_save_button_state($save_btn_controls, button_state);
}

export function save_discard_default_realm_settings_widget_status_handler(
    $subsection: JQuery,
): void {
    $subsection.find(".subsection-failed-status p").hide();
    $subsection.find(".save-button").show();
    const properties_elements = get_subsection_property_elements($subsection);
    const show_change_process_button = properties_elements.some((elem) =>
        check_realm_default_settings_property_changed(elem),
    );

    const $save_btn_controls = $subsection.find(".subsection-header .save-button-controls");
    const button_state = show_change_process_button ? "unsaved" : "discarded";
    change_save_button_state($save_btn_controls, button_state);
}

function check_maximum_valid_value(
    $custom_input_elem: JQuery<HTMLInputElement>,
    property_name: string,
): boolean {
    let setting_value = Number.parseInt($custom_input_elem.val()!, 10);
    if (
        property_name === "realm_message_content_edit_limit_seconds" ||
        property_name === "realm_message_content_delete_limit_seconds" ||
        property_name === "email_notifications_batching_period_seconds"
    ) {
        setting_value = parse_time_limit($custom_input_elem);
    }
    return setting_value <= MAX_CUSTOM_TIME_LIMIT_SETTING_VALUE;
}

function should_disable_save_button_for_jitsi_server_url_setting(): boolean {
    if (!is_video_chat_provider_jitsi_meet()) {
        return false;
    }

    const $dropdown_elem = $<HTMLSelectOneElement>(
        "select:not([multiple])#id_realm_jitsi_server_url",
    );
    const $custom_input_elem = $<HTMLInputElement>("input#id_realm_jitsi_server_url_custom_input");

    return (
        $dropdown_elem.val()!.toString() === "custom" &&
        !util.is_valid_url($custom_input_elem.val()!, true)
    );
}

function should_disable_save_button_for_time_limit_settings(
    time_limit_settings: HTMLElement[],
): boolean {
    let disable_save_btn = false;
    for (const setting_elem of time_limit_settings) {
        const $dropdown_elem = $(setting_elem).find<HTMLSelectOneElement>("select:not([multiple])");
        const $custom_input_elem = $(setting_elem).find<HTMLInputElement>(
            "input.time-limit-custom-input",
        );
        const custom_input_elem_val = check_valid_number_input($custom_input_elem.val()!);

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

function enable_or_disable_save_button($subsection_elem: JQuery): void {
    const time_limit_settings = [...$subsection_elem.find(".time-limit-setting")];

    let disable_save_btn = false;
    if (time_limit_settings.length) {
        disable_save_btn = should_disable_save_button_for_time_limit_settings(time_limit_settings);
    } else if ($subsection_elem.attr("id") === "org-other-settings") {
        disable_save_btn = should_disable_save_button_for_jitsi_server_url_setting();
        const $button_wrapper = $subsection_elem.find<tippy.PopperElement>(
            ".subsection-changes-save",
        );
        const tippy_instance = util.the($button_wrapper)._tippy;
        if (disable_save_btn) {
            // avoid duplication of tippy
            if (!tippy_instance) {
                const opts: Partial<tippy.Props> = {placement: "top"};
                initialize_disable_btn_hint_popover(
                    $button_wrapper,
                    $t({defaultMessage: "Cannot save invalid Jitsi server URL."}),
                    opts,
                );
            }
        } else {
            if (tippy_instance) {
                tippy_instance.destroy();
            }
        }
    }

    $subsection_elem.find(".subsection-changes-save button").prop("disabled", disable_save_btn);
}

export function initialize_disable_btn_hint_popover(
    $btn_wrapper: JQuery,
    hint_text: string | undefined,
    opts: Partial<tippy.Props>,
): void {
    const tippy_opts: Partial<tippy.Props> = {
        animation: false,
        hideOnClick: false,
        placement: "bottom",
        ...opts,
    };

    // If hint_text is undefined, we use the HTML content of a
    // <template> whose id is given by data-tooltip-template-id
    if (hint_text !== undefined) {
        tippy_opts.content = hint_text;
    }
    tippy.default(util.the($btn_wrapper), tippy_opts);
}
