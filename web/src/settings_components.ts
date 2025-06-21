import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";
import {z} from "zod";

import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";

import * as blueslip from "./blueslip.ts";
import * as buttons from "./buttons.ts";
import * as channel_folders from "./channel_folders.ts";
import * as compose_banner from "./compose_banner.ts";
import type {DropdownWidget} from "./dropdown_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import * as group_permission_settings from "./group_permission_settings.ts";
import type {AssignedGroupPermission, GroupGroupSettingName} from "./group_permission_settings.ts";
import * as group_setting_pill from "./group_setting_pill.ts";
import {$t} from "./i18n.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import {
    realm_default_settings_schema,
    realm_user_settings_defaults,
} from "./realm_user_settings_defaults.ts";
import * as scroll_util from "./scroll_util.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import type {CustomProfileField, GroupSettingValue} from "./state_data.ts";
import {current_user, realm, realm_schema} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_settings_containers from "./stream_settings_containers.ts";
import {
    type StreamPermissionGroupSetting,
    stream_permission_group_settings_schema,
} from "./stream_types.ts";
import type {StreamSubscription} from "./sub_store.ts";
import {stream_subscription_schema} from "./sub_store.ts";
import type {GroupSettingPillContainer} from "./typeahead_helper.ts";
import {group_setting_value_schema} from "./types.ts";
import type {HTMLSelectOneElement} from "./types.ts";
import * as ui_util from "./ui_util.ts";
import * as user_group_pill from "./user_group_pill.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";
import * as user_pill from "./user_pill.ts";
import * as util from "./util.ts";

const MAX_CUSTOM_TIME_LIMIT_SETTING_VALUE = 2147483647;

type SettingOptionValue = {
    order?: number;
    code: number;
    description: string;
};

export type SettingOptionValueWithKey = SettingOptionValue & {key: string};

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

export type MessageMoveTimeLimitSetting =
    | "realm_move_messages_within_stream_limit_seconds"
    | "realm_move_messages_between_streams_limit_seconds";

export type MessageTimeLimitSetting =
    | MessageMoveTimeLimitSetting
    | "realm_message_content_edit_limit_seconds"
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
export const realm_setting_property_schema = z.union([
    realm_schema.keyof(),
    z.literal("realm_org_join_restrictions"),
]);
type RealmSettingProperty = z.infer<typeof realm_setting_property_schema>;

type RealmUserSettingDefaultType = typeof realm_user_settings_defaults;
export const realm_user_settings_default_properties_schema = z.union([
    realm_default_settings_schema.keyof(),
    z.literal("email_notification_batching_period_edit_minutes"),
]);
type RealmUserSettingDefaultProperties = z.infer<
    typeof realm_user_settings_default_properties_schema
>;

export const stream_settings_property_schema = z.union([
    stream_subscription_schema.keyof(),
    z.enum(["stream_privacy", "is_default_stream"]),
]);
type StreamSettingProperty = z.infer<typeof stream_settings_property_schema>;

type valueof<T> = T[keyof T];

export function get_realm_settings_property_value(
    property_name: RealmSettingProperty,
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
    property_name: StreamSettingProperty,
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

export const simple_dropdown_realm_settings_schema = realm_schema.pick({
    realm_org_type: true,
    realm_message_edit_history_visibility_policy: true,
    realm_topics_policy: true,
});
export type SimpleDropdownRealmSettings = z.infer<typeof simple_dropdown_realm_settings_schema>;

export function set_property_dropdown_value(
    property_name: keyof SimpleDropdownRealmSettings,
): void {
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const property_value = get_realm_settings_property_value(
        property_name,
    ) as valueof<SimpleDropdownRealmSettings>;
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
    return util.check_time_input(custom_input_val);
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

const dropdown_widget_map = new Map<string, DropdownWidget | null>([
    ["realm_new_stream_announcements_stream_id", null],
    ["realm_signup_announcements_stream_id", null],
    ["realm_zulip_update_announcements_stream_id", null],
    ["realm_default_code_block_language", null],
    ["realm_can_access_all_users_group", null],
    ["realm_can_create_web_public_channel_group", null],
    ["folder_id", null],
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

    const $save_button = $element.find(".save-button");
    const $textEl = $save_button.find(".action-button-label");

    if (state === "discarded") {
        if (
            // When the save button is in the "saving" or "saved" state,
            // we don't want the realm sync settings logic to hide the
            // save discard widget before the success callback could show the
            // "saved" state in the button.  Moreover, the visibility of the
            // save discard widget will be handled by either the "succeeded"
            // or the "failed" state after the request is complete.
            $save_button.attr("data-status") === "saved" ||
            $save_button.attr("data-status") === "saving"
        ) {
            return;
        }
        show_hide_element($element, false, 0, () => {
            enable_or_disable_save_button($element.closest(".settings-subsection-parent"));
        });
        return;
    }

    if (state === "succeeded" && $save_button.attr("data-status") === "unsaved") {
        // We don't show the "saved" state if the save button is in the "unsaved"
        // state, as that would indicate that user has made some other changes
        // during the saving process.
        return;
    }

    if (state !== "saving") {
        buttons.hide_button_loading_indicator($save_button);
    }

    let button_text = $t({defaultMessage: "Save changes"});
    let data_status;
    let is_show;
    switch (state) {
        case "unsaved":
            data_status = "unsaved";
            is_show = true;

            $element.find(".discard-button").show();
            break;
        case "saving":
            // We don't change the button text on the saving
            // state to avoid changing the button size while
            // we show the loading indicator.
            data_status = "saving";
            is_show = true;

            $element.find(".discard-button").hide();
            buttons.show_button_loading_indicator($save_button);
            break;
        case "failed":
            data_status = "failed";
            is_show = true;
            break;
        case "succeeded":
            button_text = $t({defaultMessage: "Saved"});
            data_status = "saved";
            is_show = false;
            break;
    }

    requestAnimationFrame(() => {
        // We need to use requestAnimationFrame to ensure that the
        // button text and style are updated in the same frame.
        $textEl.text(button_text);
        if (state === "succeeded") {
            buttons.modify_action_button_style($save_button, {
                attention: "borderless",
                intent: "success",
            });
        } else {
            buttons.modify_action_button_style($save_button, {
                attention: "primary",
                intent: "brand",
            });
        }
    });

    assert(data_status !== undefined);
    $save_button.attr("data-status", data_status);
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

export function get_input_type($input_elem: JQuery, input_type?: string): string {
    if (input_type !== undefined && ["boolean", "string", "number"].includes(input_type)) {
        return input_type;
    }
    input_type = $input_elem.attr("data-setting-widget-type");
    assert(input_type !== undefined);
    return input_type;
}

export let get_input_element_value = (
    input_elem: HTMLElement,
    input_type?: string,
): boolean | number | string | null | undefined | GroupSettingValue => {
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
        case "group-setting-type": {
            const setting_name = extract_property_name($input_elem);
            const pill_widget = get_group_setting_widget(setting_name);
            assert(pill_widget !== null);
            return get_group_setting_widget_value(pill_widget);
        }
        case "info-density-setting":
            assert(input_elem instanceof HTMLInputElement);
            return Number.parseInt($(input_elem).val()!, 10);
        default:
            return undefined;
    }
};

export function rewire_get_input_element_value(value: typeof get_input_element_value): void {
    get_input_element_value = value;
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
    const time_limit_in_minutes = util.check_time_input($elem.val()!, true);
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
        return util.check_time_input($custom_input_elem.val()!);
    }

    return parse_time_limit($custom_input_elem);
}

export function check_realm_settings_property_changed(elem: HTMLElement): boolean {
    const $elem = $(elem);

    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const property_name = extract_property_name($elem) as RealmSettingProperty;
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
        case "realm_can_access_all_users_group":
        case "realm_can_create_web_public_channel_group":
            proposed_val = get_dropdown_list_widget_setting_value($elem);
            break;
        case "realm_can_add_custom_emoji_group":
        case "realm_can_add_subscribers_group":
        case "realm_can_create_bots_group":
        case "realm_can_create_groups":
        case "realm_can_create_public_channel_group":
        case "realm_can_create_private_channel_group":
        case "realm_can_create_write_only_bots_group":
        case "realm_can_delete_any_message_group":
        case "realm_can_delete_own_message_group":
        case "realm_can_invite_users_group":
        case "realm_can_manage_all_groups":
        case "realm_can_manage_billing_group":
        case "realm_can_mention_many_users_group":
        case "realm_can_move_messages_between_channels_group":
        case "realm_can_move_messages_between_topics_group":
        case "realm_can_resolve_topics_group":
        case "realm_can_set_topics_policy_group":
        case "realm_can_summarize_topics_group":
        case "realm_create_multiuse_invite_group":
        case "realm_direct_message_initiator_group":
        case "realm_direct_message_permission_group": {
            const pill_widget = get_group_setting_widget(property_name);
            assert(pill_widget !== null);
            proposed_val = get_group_setting_widget_value(pill_widget);
            break;
        }
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
    return !_.isEqual(current_val, proposed_val);
}

export function check_stream_settings_property_changed(
    elem: HTMLElement,
    sub: StreamSubscription,
): boolean {
    const $elem = $(elem);
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const property_name = extract_property_name($elem) as StreamSettingProperty;
    const current_val = get_stream_settings_property_value(property_name, sub);
    let proposed_val;

    if (Object.keys(realm.server_supported_permission_settings.stream).includes(property_name)) {
        const pill_widget = get_group_setting_widget(property_name);
        assert(pill_widget !== null);
        proposed_val = get_group_setting_widget_value(pill_widget);
        return !_.isEqual(current_val, proposed_val);
    }

    switch (property_name) {
        case "message_retention_days":
            assert(elem instanceof HTMLSelectElement);
            proposed_val = get_message_retention_setting_value($(elem), false);
            break;
        case "stream_privacy":
            proposed_val = get_input_element_value(elem, "radio-group");
            break;
        case "folder_id":
            proposed_val = get_channel_folder_value_from_dropdown_widget($(elem));
            break;
        default:
            if (current_val !== undefined) {
                proposed_val = get_input_element_value(elem, typeof current_val);
            } else {
                blueslip.error("Element refers to unknown property", {property_name});
            }
    }
    return !_.isEqual(current_val, proposed_val);
}

export function get_group_setting_widget_value(
    pill_widget: GroupSettingPillContainer,
): GroupSettingValue {
    const setting_pills = pill_widget.items();
    const direct_subgroups: number[] = [];
    const direct_members: number[] = [];
    for (const pill of setting_pills) {
        if (pill.type === "user_group") {
            direct_subgroups.push(pill.group_id);
        } else {
            assert(pill.user_id !== undefined);
            direct_members.push(pill.user_id);
        }
    }

    if (direct_members.length === 0 && direct_subgroups.length === 0) {
        const nobody_group = user_groups.get_user_group_from_name("role:nobody")!;
        return nobody_group.id;
    }

    if (direct_members.length === 0 && direct_subgroups.length === 1) {
        assert(direct_subgroups[0] !== undefined);
        return direct_subgroups[0];
    }

    return {
        direct_subgroups: direct_subgroups.sort(),
        direct_members: direct_members.sort(),
    };
}

export function check_group_property_changed(elem: HTMLElement, group: UserGroup): boolean {
    const $elem = $(elem);
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const property_name = extract_property_name($elem) as keyof UserGroup;
    const current_val = get_group_property_value(property_name, group);
    let proposed_val;

    if (Object.keys(realm.server_supported_permission_settings.group).includes(property_name)) {
        const pill_widget = get_group_setting_widget(property_name);
        assert(pill_widget !== null);
        proposed_val = get_group_setting_widget_value(pill_widget);
    } else if (current_val !== undefined) {
        proposed_val = get_input_element_value(elem, typeof current_val);
    } else {
        blueslip.error("Element refers to unknown property", {property_name});
    }

    return !_.isEqual(current_val, proposed_val);
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
        case "color_scheme":
        case "emojiset":
        case "user_list_style":
            proposed_val = get_input_element_value(elem, "radio-group");
            break;
        case "email_notifications_batching_period_seconds":
            assert(elem instanceof HTMLSelectElement);
            proposed_val = get_time_limit_setting_value($(elem), false);
            break;
        case "web_font_size_px":
        case "web_line_height_percent":
            assert(elem instanceof HTMLInputElement);
            proposed_val = Number.parseInt($(elem).val()!, 10);
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
                    assert(typeof input_value === "string");
                    data = {
                        ...data,
                        ...get_request_data_for_org_join_restrictions(input_value),
                    };
                    continue;
                }

                const realm_group_settings = new Set([
                    "can_access_all_users_group",
                    "can_add_custom_emoji_group",
                    "can_add_subscribers_group",
                    "can_create_bots_group",
                    "can_create_groups",
                    "can_create_private_channel_group",
                    "can_create_public_channel_group",
                    "can_create_web_public_channel_group",
                    "can_create_write_only_bots_group",
                    "can_manage_all_groups",
                    "can_manage_billing_group",
                    "can_delete_any_message_group",
                    "can_delete_own_message_group",
                    "can_invite_users_group",
                    "can_mention_many_users_group",
                    "can_move_messages_between_channels_group",
                    "can_move_messages_between_topics_group",
                    "can_resolve_topics_group",
                    "can_set_topics_policy_group",
                    "can_summarize_topics_group",
                    "create_multiuse_invite_group",
                    "direct_message_initiator_group",
                    "direct_message_permission_group",
                ]);
                if (realm_group_settings.has(property_name)) {
                    const old_value = get_realm_settings_property_value(
                        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
                        ("realm_" + property_name) as RealmSettingProperty,
                    );
                    data[property_name] = JSON.stringify({
                        new: input_value,
                        old: old_value,
                    });
                    continue;
                }

                assert(typeof input_value !== "object");
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
                    assert(typeof input_value === "string");
                    data = {
                        ...data,
                        ...settings_data.get_request_data_for_stream_privacy(input_value),
                    };
                    continue;
                }

                if (stream_permission_group_settings_schema.safeParse(property_name).success) {
                    const old_value = get_stream_settings_property_value(
                        stream_settings_property_schema.parse(property_name),
                        sub,
                    );
                    data[property_name] = JSON.stringify({
                        new: input_value,
                        old: old_value,
                    });
                    continue;
                }

                if (property_name === "folder_id") {
                    const folder_id = get_channel_folder_value_from_dropdown_widget($input_elem);
                    data[property_name] = JSON.stringify(folder_id);
                    continue;
                }

                assert(typeof input_value !== "object");
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
                assert(typeof input_value !== "object");
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
                assert(typeof input_value !== "object");
                data[property_name] = input_value;
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

    const $save_button_controls = $subsection.find(".subsection-header .save-button-controls");
    const button_state = show_change_process_button ? "unsaved" : "discarded";
    change_save_button_state($save_button_controls, button_state);
}

export function save_discard_stream_settings_widget_status_handler(
    $subsection: JQuery,
    sub: StreamSubscription | undefined,
): void {
    $subsection.find(".subsection-failed-status p").hide();
    $subsection.find(".save-button").show();
    const properties_elements = get_subsection_property_elements($subsection);
    let show_change_process_button = false;
    if (sub !== undefined) {
        show_change_process_button = properties_elements.some((elem) =>
            check_stream_settings_property_changed(elem, sub),
        );
    }

    const $save_button_controls = $subsection.find(".subsection-header .save-button-controls");
    const button_state = show_change_process_button ? "unsaved" : "discarded";
    change_save_button_state($save_button_controls, button_state);

    // If the stream isn't currently private but being changed to private,
    // and the user changing this setting isn't subscribed, we show a
    // warning that they won't be able to access the stream after
    // making it private unless they subscribe.
    if (
        button_state === "unsaved" &&
        sub &&
        !sub.invite_only &&
        !sub.subscribed &&
        switching_to_private(properties_elements)
    ) {
        if ($("#stream_settings .stream_privacy_warning").length > 0) {
            return;
        }
        const context = {
            banner_type: compose_banner.WARNING,
            banner_text: $t({
                defaultMessage:
                    "You will lose access to content in this channel if you make it private. To keep access, subscribe or grant yourself permission to do so under Advanced configurations.",
            }),
            button_text: $t({defaultMessage: "Subscribe"}),
            classname: "stream_privacy_warning",
            stream_id: sub.stream_id,
        };
        $("#stream_settings .stream-permissions-warning-banner").append(
            $(render_compose_banner(context)),
        );
    } else {
        $("#stream_settings .stream-permissions-warning-banner").empty();
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
    const $save_button_controls = $subsection.find(".subsection-header .save-button-controls");
    const button_state = show_change_process_button ? "unsaved" : "discarded";
    change_save_button_state($save_button_controls, button_state);
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

    const $save_button_controls = $subsection.find(".subsection-header .save-button-controls");
    const button_state = show_change_process_button ? "unsaved" : "discarded";
    change_save_button_state($save_button_controls, button_state);
}

function check_maximum_valid_value(
    $custom_input_elem: JQuery<HTMLInputElement>,
    property_name: string,
): boolean {
    let setting_value = Number.parseInt($custom_input_elem.val()!, 10);
    if (
        property_name === "realm_message_content_edit_limit_seconds" ||
        property_name === "realm_message_content_delete_limit_seconds" ||
        property_name === "realm_move_messages_between_streams_limit_seconds" ||
        property_name === "realm_move_messages_within_stream_limit_seconds" ||
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

    return $dropdown_elem.val() === "custom" && !util.is_valid_url($custom_input_elem.val()!, true);
}

function should_disable_save_button_for_time_limit_settings(
    time_limit_settings: HTMLElement[],
): boolean {
    let disable_save_button = false;
    for (const setting_elem of time_limit_settings) {
        const $dropdown_elem = $(setting_elem).find<HTMLSelectOneElement>("select:not([multiple])");
        const $custom_input_elem = $(setting_elem).find<HTMLInputElement>(
            "input.time-limit-custom-input",
        );
        const custom_input_elem_val = util.check_time_input($custom_input_elem.val()!);

        const for_realm_default_settings =
            $dropdown_elem.closest(".settings-section.show").attr("id") ===
            "realm-user-default-settings";
        const property_name = extract_property_name($dropdown_elem, for_realm_default_settings);

        disable_save_button =
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
            disable_save_button = false;
        }

        if (disable_save_button) {
            break;
        }
    }

    return disable_save_button;
}

function should_disable_save_button_for_group_settings(settings: string[]): boolean {
    for (const setting_name of settings) {
        let group_setting_config;
        if (setting_name.startsWith("realm_")) {
            const setting_name_without_prefix = /^realm_(.*)$/.exec(setting_name)![1]!;
            group_setting_config = group_permission_settings.get_group_permission_setting_config(
                setting_name_without_prefix,
                "realm",
            );
        } else if (stream_permission_group_settings_schema.safeParse(setting_name).success) {
            group_setting_config = group_permission_settings.get_group_permission_setting_config(
                setting_name,
                "stream",
            );
        } else {
            group_setting_config = group_permission_settings.get_group_permission_setting_config(
                setting_name,
                "group",
            );
        }
        assert(group_setting_config !== undefined);

        const pill_widget = get_group_setting_widget(setting_name);
        assert(pill_widget !== null);
        if (pill_widget.is_pending()) {
            return true;
        }

        if (group_setting_config.allow_nobody_group) {
            continue;
        }
        const setting_value = get_group_setting_widget_value(pill_widget);
        const nobody_group = user_groups.get_user_group_from_name("role:nobody")!;
        if (setting_value === nobody_group.id) {
            return true;
        }
    }
    return false;
}

function enable_or_disable_save_button($subsection_elem: JQuery): void {
    const $save_button = $subsection_elem.find(".save-button");

    const time_limit_settings = [...$subsection_elem.find(".time-limit-setting")];
    if (
        time_limit_settings.length > 0 &&
        should_disable_save_button_for_time_limit_settings(time_limit_settings)
    ) {
        if (
            $subsection_elem.attr("id") === "org-message-retention" ||
            $subsection_elem.hasClass("advanced-configurations-container")
        ) {
            ui_util.disable_element_and_add_tooltip(
                $save_button,
                $t({
                    defaultMessage: "Cannot save invalid message retention period.",
                }),
            );
            return;
        }
        $save_button.prop("disabled", true);
        return;
    }

    if (
        $subsection_elem.attr("id") === "org-compose-settings" &&
        should_disable_save_button_for_jitsi_server_url_setting()
    ) {
        ui_util.disable_element_and_add_tooltip(
            $save_button,
            $t({defaultMessage: "Cannot save invalid Jitsi server URL."}),
        );
        return;
    }

    const group_settings = [...$subsection_elem.find(".pill-container")].map((elem) =>
        extract_property_name($(elem)),
    );
    if (
        group_settings.length > 0 &&
        should_disable_save_button_for_group_settings(group_settings)
    ) {
        $save_button.prop("disabled", true);
        return;
    }

    ui_util.enable_element_and_remove_tooltip($save_button);
}

export function initialize_disable_button_hint_popover(
    $button_wrapper: JQuery,
    hint_text: string | undefined,
    opts: Partial<tippy.Props> = {},
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
    tippy.default(util.the($button_wrapper), tippy_opts);
}

export function enable_opening_typeahead_on_clicking_label($container: JQuery): void {
    const $group_setting_labels = $container.find(".group-setting-label");
    $group_setting_labels.on("click", (e) => {
        if ($(e.target).is("a.help_link_widget, a.help_link_widget i")) {
            // Clicking on the "?" icon should just open the link and there is
            // no need to open the typeahead or focus the input, so we return.
            return;
        }

        // Click opens the typeahead.
        $(e.currentTarget).siblings(".pill-container").find(".input").expectOne().trigger("click");
        // Focus puts the cursor into the input.
        $(e.currentTarget).siblings(".pill-container").find(".input").expectOne().trigger("focus");
    });
}

export function disable_opening_typeahead_on_clicking_label($container: JQuery): void {
    const $group_setting_labels = $container.find(".group-setting-label");
    $group_setting_labels.off("click");
}

export function disable_group_permission_setting($container: JQuery): void {
    $container.find(".input").prop("contenteditable", false);
    $container.closest(".input-group").addClass("group_setting_disabled");
    disable_opening_typeahead_on_clicking_label($container.closest(".input-group"));
}

export const group_setting_widget_map = new Map<string, GroupSettingPillContainer | null>([
    ["can_add_members_group", null],
    ["can_add_subscribers_group", null],
    ["can_administer_channel_group", null],
    ["can_join_group", null],
    ["can_leave_group", null],
    ["can_manage_group", null],
    ["can_mention_group", null],
    ["can_move_messages_out_of_channel_group", null],
    ["can_move_messages_within_channel_group", null],
    ["can_remove_members_group", null],
    ["can_remove_subscribers_group", null],
    ["can_send_message_group", null],
    ["realm_can_add_custom_emoji_group", null],
    ["realm_can_add_subscribers_group", null],
    ["realm_can_create_bots_group", null],
    ["realm_can_create_groups", null],
    ["realm_can_create_public_channel_group", null],
    ["realm_can_create_private_channel_group", null],
    ["realm_can_create_write_only_bots_group", null],
    ["realm_can_delete_any_message_group", null],
    ["realm_can_delete_own_message_group", null],
    ["realm_can_invite_users_group", null],
    ["realm_can_manage_all_groups", null],
    ["realm_can_manage_billing_group", null],
    ["realm_can_mention_many_users_group", null],
    ["realm_can_move_messages_between_channels_group", null],
    ["realm_can_move_messages_between_topics_group", null],
    ["realm_can_resolve_topics_group", null],
    ["realm_can_set_topics_policy_group", null],
    ["realm_can_summarize_topics_group", null],
    ["realm_create_multiuse_invite_group", null],
    ["realm_direct_message_initiator_group", null],
    ["realm_direct_message_permission_group", null],
]);

export function get_group_setting_widget(setting_name: string): GroupSettingPillContainer | null {
    const pill_widget = group_setting_widget_map.get(setting_name);

    if (pill_widget === undefined) {
        blueslip.error("No dropdown list widget for property", {setting_name});
        return null;
    }

    return pill_widget;
}

export function set_group_setting_widget_value(
    pill_widget: GroupSettingPillContainer,
    property_value: GroupSettingValue,
): void {
    pill_widget.clear(true);

    if (typeof property_value === "number") {
        const user_group = user_groups.get_user_group_from_id(property_value);
        if (user_group.name === "role:nobody") {
            return;
        }
        user_group_pill.append_user_group(user_group, pill_widget, false);
    } else {
        for (const setting_sub_group_id of property_value.direct_subgroups) {
            const user_group = user_groups.get_user_group_from_id(setting_sub_group_id);
            if (user_group.name === "role:nobody") {
                continue;
            }
            user_group_pill.append_user_group(user_group, pill_widget, false);
        }
        for (const setting_user_id of property_value.direct_members) {
            const user = people.get_user_by_id_assert_valid(setting_user_id);
            user_pill.append_user(user, pill_widget, false);
        }
    }
}

export function create_group_setting_widget({
    $pill_container,
    setting_name,
    group,
}: {
    $pill_container: JQuery;
    setting_name: GroupGroupSettingName;
    group?: UserGroup;
}): GroupSettingPillContainer {
    const pill_widget = group_setting_pill.create_pills($pill_container, setting_name, "group");
    const opts: {
        setting_name: string;
        group: UserGroup | undefined;
        setting_type: "group";
    } = {
        setting_name,
        group,
        setting_type: "group",
    };
    group_setting_pill.set_up_pill_typeahead({pill_widget, $pill_container, opts});

    if (group !== undefined) {
        group_setting_widget_map.set(setting_name, pill_widget);
    }

    if (group !== undefined) {
        set_group_setting_widget_value(pill_widget, group[setting_name]);

        pill_widget.onTextInputHook(() => {
            save_discard_group_widget_status_handler($("#group_permission_settings"), group);
        });
        pill_widget.onPillCreate(() => {
            save_discard_group_widget_status_handler($("#group_permission_settings"), group);
        });
        pill_widget.onPillRemove(() => {
            save_discard_group_widget_status_handler($("#group_permission_settings"), group);
        });
    } else {
        const default_group_name = group_permission_settings.get_group_permission_setting_config(
            setting_name,
            "group",
        )!.default_group_name;
        if (default_group_name === "group_creator") {
            set_group_setting_widget_value(pill_widget, {
                direct_members: [current_user.user_id],
                direct_subgroups: [],
            });
        } else {
            const default_group_id = user_groups.get_user_group_from_name(default_group_name)!.id;
            set_group_setting_widget_value(pill_widget, default_group_id);
        }
    }

    return pill_widget;
}

export const realm_group_setting_name_supporting_anonymous_groups_schema =
    group_permission_settings.realm_group_setting_name_schema.exclude([
        "can_access_all_users_group",
        "can_create_web_public_channel_group",
    ]);
export type RealmGroupSettingNameSupportingAnonymousGroups = z.infer<
    typeof realm_group_setting_name_supporting_anonymous_groups_schema
>;

export function create_realm_group_setting_widget({
    $pill_container,
    setting_name,
    pill_update_callback,
}: {
    $pill_container: JQuery;
    setting_name: RealmGroupSettingNameSupportingAnonymousGroups;
    pill_update_callback?: () => void;
}): void {
    const pill_widget = group_setting_pill.create_pills($pill_container, setting_name, "realm");
    const opts: {
        setting_name: string;
        setting_type: "realm";
    } = {
        setting_name,
        setting_type: "realm",
    };
    group_setting_pill.set_up_pill_typeahead({pill_widget, $pill_container, opts});

    group_setting_widget_map.set("realm_" + setting_name, pill_widget);

    set_group_setting_widget_value(
        pill_widget,
        group_setting_value_schema.parse(
            realm[realm_schema.keyof().parse("realm_" + setting_name)],
        ),
    );

    const $save_discard_widget_container = $(`#id_realm_${CSS.escape(setting_name)}`).closest(
        ".settings-subsection-parent",
    );
    pill_widget.onTextInputHook(() => {
        if (pill_update_callback !== undefined) {
            pill_update_callback();
        }
        save_discard_realm_settings_widget_status_handler($save_discard_widget_container);
    });
    pill_widget.onPillCreate(() => {
        if (pill_update_callback !== undefined) {
            pill_update_callback();
        }
        save_discard_realm_settings_widget_status_handler($save_discard_widget_container);
    });
    pill_widget.onPillRemove(() => {
        if (pill_update_callback !== undefined) {
            pill_update_callback();
        }
        save_discard_realm_settings_widget_status_handler($save_discard_widget_container);
    });
}

export function create_stream_group_setting_widget({
    $pill_container,
    setting_name,
    sub,
}: {
    $pill_container: JQuery;
    setting_name: StreamPermissionGroupSetting;
    sub?: StreamSubscription;
}): GroupSettingPillContainer {
    const pill_widget = group_setting_pill.create_pills($pill_container, setting_name, "stream");
    const opts: {
        setting_name: string;
        sub: StreamSubscription | undefined;
        setting_type: "stream";
    } = {
        setting_name,
        sub,
        setting_type: "stream",
    };
    group_setting_pill.set_up_pill_typeahead({pill_widget, $pill_container, opts});

    if (sub !== undefined) {
        group_setting_widget_map.set(setting_name, pill_widget);
    }

    if (sub !== undefined) {
        set_group_setting_widget_value(pill_widget, sub[setting_name]);
        const $edit_container = stream_settings_containers.get_edit_container(sub);
        const $subsection = $edit_container.find(".advanced-configurations-container");

        pill_widget.onTextInputHook(() => {
            save_discard_stream_settings_widget_status_handler($subsection, sub);
        });
        pill_widget.onPillCreate(() => {
            save_discard_stream_settings_widget_status_handler($subsection, sub);
        });
        pill_widget.onPillRemove(() => {
            save_discard_stream_settings_widget_status_handler($subsection, sub);
        });
    } else {
        const default_group_name = group_permission_settings.get_group_permission_setting_config(
            setting_name,
            "stream",
        )!.default_group_name;
        if (default_group_name === "stream_creator_or_nobody") {
            set_group_setting_widget_value(pill_widget, {
                direct_members: [current_user.user_id],
                direct_subgroups: [],
            });
        } else {
            const default_group_id = user_groups.get_user_group_from_name(default_group_name)!.id;
            set_group_setting_widget_value(pill_widget, default_group_id);
        }
    }

    return pill_widget;
}

export function set_time_input_formatted_text(
    $time_select_elem: JQuery,
    formatted_text: string,
): void {
    if ($time_select_elem.val() === "custom") {
        $time_select_elem.parent().find(".time-input-formatted-description").hide();
        $time_select_elem
            .parent()
            .find(".custom-time-input-formatted-description")
            .text(formatted_text);
    } else {
        $time_select_elem.parent().find(".time-input-formatted-description").show();
        $time_select_elem.parent().find(".time-input-formatted-description").text(formatted_text);
    }
}

export function set_custom_time_inputs_visibility(
    $time_select_elem: JQuery,
    time_unit: string,
    time_value: number,
): void {
    if ($time_select_elem.val() === "custom") {
        $time_select_elem.parent().find(".custom-time-input-value").val(time_value);
        $time_select_elem.parent().find(".custom-time-input-unit").val(time_unit);
        $time_select_elem.parent().find(".custom-time-input-container").show();
    } else {
        $time_select_elem.parent().find(".custom-time-input-container").hide();
    }
}

export function get_group_assigned_realm_permissions(group: UserGroup): {
    subsection_key: string;
    subsection_heading: string;
    assigned_permissions: AssignedGroupPermission[];
}[] {
    const group_assigned_realm_permissions = [];
    for (const {
        subsection_heading,
        subsection_key,
        settings,
    } of settings_config.realm_group_permission_settings) {
        const assigned_permission_objects = [];
        for (const setting_name of settings) {
            const setting_value = realm[realm_schema.keyof().parse("realm_" + setting_name)];
            const can_edit = settings_config.owner_editable_realm_group_permission_settings.has(
                setting_name,
            )
                ? current_user.is_owner
                : current_user.is_admin;
            const assigned_permission_object =
                group_permission_settings.get_assigned_permission_object(
                    group_setting_value_schema.parse(setting_value),
                    setting_name,
                    group.id,
                    can_edit,
                    "realm",
                );
            if (assigned_permission_object !== undefined) {
                assigned_permission_objects.push(assigned_permission_object);
            }
        }
        group_assigned_realm_permissions.push({
            subsection_heading,
            subsection_key,
            assigned_permissions: assigned_permission_objects,
        });
    }
    return group_assigned_realm_permissions;
}

export function get_group_assigned_stream_permissions(group: UserGroup): {
    stream: StreamSubscription;
    assigned_permissions: AssignedGroupPermission[];
    id_prefix: string;
}[] {
    const subs = stream_data.get_unsorted_subs();
    const group_assigned_stream_permissions = [];
    for (const sub of subs) {
        const assigned_permission_objects = [];
        const can_edit_settings_with_metadata_access =
            stream_data.can_change_permissions_requiring_metadata_access(sub);
        const can_edit_settings_with_content_access =
            stream_data.can_change_permissions_requiring_content_access(sub);
        for (const setting_name of settings_config.stream_group_permission_settings) {
            const setting_value = sub[stream_subscription_schema.keyof().parse(setting_name)];
            let can_edit_settings = can_edit_settings_with_metadata_access;
            if (
                settings_config.stream_group_permission_settings_requiring_content_access.includes(
                    setting_name,
                )
            ) {
                can_edit_settings = can_edit_settings_with_content_access;
            }
            const assigned_permission_object =
                group_permission_settings.get_assigned_permission_object(
                    group_setting_value_schema.parse(setting_value),
                    setting_name,
                    group.id,
                    can_edit_settings,
                    "stream",
                );
            if (assigned_permission_object !== undefined) {
                assigned_permission_objects.push(assigned_permission_object);
            }
        }

        if (assigned_permission_objects.length > 0) {
            group_assigned_stream_permissions.push({
                stream: sub,
                assigned_permissions: assigned_permission_objects,
                id_prefix: "id_group_permission_" + sub.stream_id.toString() + "_",
            });
        }
    }

    return group_assigned_stream_permissions;
}

export function get_group_assigned_user_group_permissions(group: UserGroup): {
    group_id: number;
    group_name: string;
    assigned_permissions: AssignedGroupPermission[];
    id_prefix: string;
}[] {
    const groups = user_groups.get_realm_user_groups();
    const group_assigned_user_group_permissions = [];
    for (const user_group of groups) {
        const can_edit_settings = settings_data.can_manage_user_group(user_group.id);
        const assigned_permission_objects = [];
        for (const setting_name of settings_config.group_permission_settings) {
            const setting_value =
                user_group[user_groups.user_group_schema.keyof().parse(setting_name)];
            const assigned_permission_object =
                group_permission_settings.get_assigned_permission_object(
                    group_setting_value_schema.parse(setting_value),
                    setting_name,
                    group.id,
                    can_edit_settings,
                    "group",
                );
            if (assigned_permission_object !== undefined) {
                assigned_permission_objects.push(assigned_permission_object);
            }
        }

        if (assigned_permission_objects.length > 0) {
            group_assigned_user_group_permissions.push({
                group_id: user_group.id,
                group_name: user_groups.get_display_group_name(user_group.name),
                id_prefix: "id_group_permission_" + user_group.id.toString() + "_",
                assigned_permissions: assigned_permission_objects,
            });
        }
    }

    return group_assigned_user_group_permissions;
}

export function set_up_folder_dropdown_widget(
    sub?: StreamSubscription,
): DropdownWidget | undefined {
    if (!page_params.development_environment) {
        return undefined;
    }

    const folder_options = (): dropdown_widget.Option[] => {
        const folders = channel_folders.get_channel_folders();
        const options: dropdown_widget.Option[] = folders.map((folder) => ({
            name: folder.name,
            unique_id: folder.id,
        }));

        const disabled_option = {
            is_setting_disabled: true,
            show_disabled_icon: false,
            show_disabled_option_name: true,
            unique_id: settings_config.no_folder_selected,
            name: $t({defaultMessage: "None"}),
        };

        options.unshift(disabled_option);
        return options;
    };

    const default_id = sub?.folder_id ?? settings_config.no_folder_selected;

    let widget_name = "folder_id";
    if (sub === undefined) {
        widget_name = "new_channel_folder_id";
    }

    let $events_container = $("#stream_settings .subscription_settings");
    if (sub === undefined) {
        $events_container = $("#stream_creation_form");
    }

    const folder_widget = new dropdown_widget.DropdownWidget({
        widget_name,
        get_options: folder_options,
        $events_container,
        item_click_callback(event, dropdown, this_widget) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            this_widget.render();
            if (sub !== undefined) {
                const $edit_container = stream_settings_containers.get_edit_container(sub);
                save_discard_stream_settings_widget_status_handler(
                    $edit_container.find(".channel-folder-subsection"),
                    stream_data.get_sub_by_id(sub.stream_id),
                );
            }
        },
        default_id,
        unique_id_type: "number",
    });
    if (sub !== undefined) {
        set_dropdown_setting_widget("folder_id", folder_widget);
    }
    folder_widget.setup();
    return folder_widget;
}

export function set_channel_folder_dropdown_value(sub: StreamSubscription): void {
    if (sub.folder_id === null) {
        set_dropdown_list_widget_setting_value("folder_id", settings_config.no_folder_selected);
        return;
    }
    set_dropdown_list_widget_setting_value("folder_id", sub.folder_id);
}

export function get_channel_folder_value_from_dropdown_widget($elem: JQuery): number | null {
    const value = get_dropdown_list_widget_setting_value($elem);
    assert(typeof value === "number");
    if (value === settings_config.no_folder_selected) {
        return null;
    }
    return value;
}
