import {add} from "date-fns";
import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_settings_deactivate_realm_modal from "../templates/confirm_dialog/confirm_deactivate_realm.hbs";
import render_settings_admin_auth_methods_list from "../templates/settings/admin_auth_methods_list.hbs";

import * as audible_notifications from "./audible_notifications.ts";
import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import {csrf_token} from "./csrf.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import * as group_permission_settings from "./group_permission_settings.ts";
import {
    type RealmGroupSettingNameSupportingAnonymousGroups,
    realm_group_setting_name_supporting_anonymous_groups_schema,
} from "./group_permission_settings.ts";
import {$t, $t_html, get_language_name} from "./i18n.ts";
import * as information_density from "./information_density.ts";
import * as keydown_util from "./keydown_util.ts";
import * as loading from "./loading.ts";
import * as pygments_data from "./pygments_data.ts";
import * as realm_icon from "./realm_icon.ts";
import * as realm_logo from "./realm_logo.ts";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults.ts";
import {
    type MessageMoveTimeLimitSetting,
    type SettingOptionValueWithKey,
    realm_setting_property_schema,
    realm_user_settings_default_properties_schema,
    simple_dropdown_realm_settings_schema,
    stream_settings_property_schema,
} from "./settings_components.ts";
import * as settings_components from "./settings_components.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_notifications from "./settings_notifications.ts";
import * as settings_realm_domains from "./settings_realm_domains.ts";
import * as settings_ui from "./settings_ui.ts";
import {current_user, realm, realm_schema} from "./state_data.ts";
import type {Realm} from "./state_data.ts";
import * as stream_settings_data from "./stream_settings_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as timerender from "./timerender.ts";
import {group_setting_value_schema} from "./types.ts";
import type {HTMLSelectOneElement} from "./types.ts";
import * as ui_report from "./ui_report.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";
import * as util from "./util.ts";

const meta = {
    loaded: false,
};

export function reset(): void {
    meta.loaded = false;
}

const DISABLED_STATE_ID = -1;

export function maybe_disable_widgets(): void {
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

    $(".organization-box [data-name='organization-profile']")
        .find("input[type='checkbox']:disabled")
        .closest(".input-group")
        .addClass("control-label-disabled");

    $(".organization-box [data-name='organization-settings']")
        .find("input, textarea, button, select")
        .prop("disabled", true);

    $(".organization-box [data-name='organization-settings']")
        .find(".dropdown_list_reset_button")
        .hide();

    $(".organization-box [data-name='organization-settings']")
        .find("input[type='checkbox']:disabled")
        .closest(".input-group")
        .addClass("control-label-disabled");

    $(".organization-box [data-name='organization-permissions']")
        .find("input, textarea, button, select")
        .prop("disabled", true);

    $(".organization-box [data-name='organization-permissions']")
        .find("input[type='checkbox']:disabled")
        .closest(".input-group")
        .addClass("control-label-disabled");
}

export function enable_or_disable_group_permission_settings(): void {
    if (current_user.is_owner) {
        const $permission_pill_container_elements = $("#organization-permissions").find(
            ".pill-container",
        );
        $permission_pill_container_elements.find(".input").prop("contenteditable", true);
        $permission_pill_container_elements
            .closest(".input-group")
            .removeClass("group_setting_disabled");
        settings_components.enable_opening_typeahead_on_clicking_label(
            $("#organization-permissions"),
        );
        return;
    }

    if (current_user.is_admin) {
        const $permission_pill_container_elements = $("#organization-permissions").find(
            ".pill-container",
        );
        $permission_pill_container_elements.find(".input").prop("contenteditable", true);
        $permission_pill_container_elements
            .closest(".input-group")
            .removeClass("group_setting_disabled");
        settings_components.enable_opening_typeahead_on_clicking_label(
            $("#organization-permissions"),
        );

        // Admins are not allowed to update organization joining and group
        // related settings.
        const owner_editable_settings = [
            "realm_create_multiuse_invite_group",
            "realm_can_create_groups",
            "realm_can_manage_all_groups",
            "realm_can_manage_billing_group",
        ];
        for (const setting_name of owner_editable_settings) {
            const $permission_pill_container = $(`#id_${CSS.escape(setting_name)}`);
            settings_components.disable_group_permission_setting($permission_pill_container);
        }
        return;
    }

    const $permission_pill_container_elements = $("#organization-permissions").find(
        ".pill-container",
    );
    settings_components.disable_group_permission_setting($permission_pill_container_elements);
}

type OrganizationSettingsOptions = {
    common_policy_values: SettingOptionValueWithKey[];
};

export function get_organization_settings_options(): OrganizationSettingsOptions {
    return {
        common_policy_values: settings_components.get_sorted_options_list(
            settings_config.common_policy_values,
        ),
    };
}

type DefinedOrgTypeValues = typeof settings_config.defined_org_type_values;
type AllOrgTypeValues = typeof settings_config.all_org_type_values;

export function get_org_type_dropdown_options(): DefinedOrgTypeValues | AllOrgTypeValues {
    const current_org_type = realm.realm_org_type;
    if (current_org_type !== 0) {
        return settings_config.defined_org_type_values;
    }
    return settings_config.all_org_type_values;
}

const simple_dropdown_properties = z.keyof(simple_dropdown_realm_settings_schema).def.values;

function set_realm_waiting_period_setting(): void {
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

function update_jitsi_server_url_custom_input(dropdown_val: string): void {
    const custom_input = "id_realm_jitsi_server_url_custom_input";
    settings_components.change_element_block_display_property(
        custom_input,
        dropdown_val === "custom",
    );

    if (dropdown_val !== "custom") {
        return;
    }

    const $custom_input_elem = $(`#${CSS.escape(custom_input)}`);
    $custom_input_elem.val(realm.realm_jitsi_server_url ?? "");
}

function set_jitsi_server_url_dropdown(): void {
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

function set_video_chat_provider_dropdown(): void {
    const chat_provider_id = realm.realm_video_chat_provider;
    $("#id_realm_video_chat_provider").val(chat_provider_id);

    set_jitsi_server_url_dropdown();
}

function set_giphy_rating_dropdown(): void {
    const rating_id = realm.realm_giphy_rating;
    $("#id_realm_giphy_rating").val(rating_id);
}

function update_message_edit_sub_settings(is_checked: boolean): void {
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

function set_msg_edit_limit_dropdown(): void {
    settings_components.set_time_limit_setting("realm_message_content_edit_limit_seconds");
}

function set_msg_move_limit_setting(property_name: MessageMoveTimeLimitSetting): void {
    settings_components.set_time_limit_setting(property_name);
}

function set_msg_delete_limit_dropdown(): void {
    settings_components.set_time_limit_setting("realm_message_content_delete_limit_seconds");
}

function get_dropdown_value_for_message_retention_setting(setting_value: number | null): string {
    if (setting_value === settings_config.retain_message_forever) {
        return "unlimited";
    }

    if (setting_value === null) {
        return "realm_default";
    }

    return "custom_period";
}

export function set_message_retention_setting_dropdown(sub: StreamSubscription | undefined): void {
    let property_name: "message_retention_days" | "realm_message_retention_days";
    let setting_value: number | null;
    if (sub !== undefined) {
        property_name = "message_retention_days";
        setting_value = sub.message_retention_days;
    } else {
        property_name = "realm_message_retention_days";
        setting_value = realm.realm_message_retention_days;
    }
    const dropdown_val = get_dropdown_value_for_message_retention_setting(setting_value);

    const $dropdown_elem = $(`#id_${CSS.escape(property_name)}`);
    $dropdown_elem.val(dropdown_val);

    const $custom_input_elem = $dropdown_elem
        .parent()
        .find(".message-retention-setting-custom-input")
        .val("");
    if (dropdown_val === "custom_period") {
        assert(setting_value !== null);
        $custom_input_elem.val(setting_value);
    }

    settings_components.change_element_block_display_property(
        $custom_input_elem.attr("id")!,
        dropdown_val === "custom_period",
    );
}

function set_org_join_restrictions_dropdown(): void {
    const value = settings_components.get_realm_settings_property_value(
        "realm_org_join_restrictions",
    );
    assert(typeof value === "string");
    $("#id_realm_org_join_restrictions").val(value);
    settings_components.change_element_block_display_property(
        "allowed_domains_label",
        value === "only_selected_domain",
    );
}

function set_message_content_in_email_notifications_visibility(): void {
    settings_components.change_element_block_display_property(
        "message_content_in_email_notifications_label",
        realm.realm_message_content_allowed_in_email_notifications,
    );
}

function set_digest_emails_weekday_visibility(): void {
    settings_components.change_element_block_display_property(
        "id_realm_digest_weekday",
        realm.realm_digest_emails_enabled,
    );
}

function set_create_web_public_stream_dropdown_visibility(): void {
    settings_components.change_element_block_display_property(
        "id_realm_can_create_web_public_channel_group",
        realm.server_web_public_streams_enabled &&
            realm.zulip_plan_is_not_limited &&
            realm.realm_enable_spectator_access,
    );
}

function disable_create_user_groups_if_on_limited_plan(): void {
    if (!realm.zulip_plan_is_not_limited) {
        settings_components.disable_group_permission_setting(
            $("#id_realm_can_create_groups").closest(".input-group"),
        );
    }
}

export function check_disable_direct_message_initiator_group_widget(): void {
    const direct_message_permission_group_widget = settings_components.get_group_setting_widget(
        "realm_direct_message_permission_group",
    );
    if (direct_message_permission_group_widget === null) {
        // direct_message_permission_group_widget can be null if
        // the settings overlay is not opened yet.
        return;
    }
    assert(direct_message_permission_group_widget !== null);
    const direct_message_permission_value = settings_components.get_group_setting_widget_value(
        direct_message_permission_group_widget,
    );
    if (user_groups.is_setting_group_empty(direct_message_permission_value)) {
        settings_components.disable_group_permission_setting(
            $("#id_realm_direct_message_initiator_group"),
        );
    } else if (current_user.is_admin) {
        $("#id_realm_direct_message_initiator_group").find(".input").prop("contenteditable", true);
        $("#id_realm_direct_message_initiator_group")
            .closest(".input-group")
            .removeClass("group_setting_disabled");
        settings_components.enable_opening_typeahead_on_clicking_label(
            $("#id_realm_direct_message_initiator_group").closest(".input-group"),
        );
    }
}

export function populate_realm_domains_label(
    realm_domains: {domain: string; allow_subdomains: boolean}[],
): void {
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

export function populate_auth_methods(auth_method_to_bool_map: Record<string, boolean>): void {
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
            !realm.realm_authentication_methods[auth_method]!.available && !value;

        const render_args = {
            method: auth_method,
            enabled: value,
            disable_configure_auth_method: !current_user.is_owner || cant_be_enabled,
            // The negated character class regexp serves as an allowlist - the replace() will
            // remove *all* symbols *but* digits (\d) and lowercase letters (a-z),
            // so that we can make assumptions on this string elsewhere in the code.
            // As a result, the only two "incoming" assumptions on the auth method name are:
            // 1) It contains at least one allowed symbol
            // 2) No two auth method names are identical after this allowlist filtering
            prefix: "id_authmethod" + auth_method.toLowerCase().replaceAll(/[^\da-z]/g, "") + "_",
            ...(cant_be_enabled && {
                unavailable_reason:
                    realm.realm_authentication_methods[auth_method]!.unavailable_reason,
            }),
        };

        rendered_auth_method_rows += render_settings_admin_auth_methods_list(render_args);
    }
    $auth_methods_list.html(rendered_auth_method_rows);
}

function update_dependent_subsettings(property_name: string): void {
    const parsed_property_name = z
        .keyof(simple_dropdown_realm_settings_schema)
        .safeParse(property_name);
    if (parsed_property_name.success) {
        settings_components.set_property_dropdown_value(parsed_property_name.data);
        return;
    }

    switch (property_name) {
        case "realm_allow_message_editing":
            update_message_edit_sub_settings(realm.realm_allow_message_editing);
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
        case "realm_direct_message_permission_group":
            check_disable_direct_message_initiator_group_widget();
            break;
    }
}

export function discard_realm_property_element_changes(elem: HTMLElement): void {
    const $elem = $(elem);
    const property_name = settings_components.extract_property_name($elem);
    const property_value = settings_components.get_realm_settings_property_value(
        realm_setting_property_schema.parse(property_name),
    );

    switch (property_name) {
        case "realm_authentication_methods":
            populate_auth_methods(
                settings_components.realm_authentication_methods_to_boolean_dict(),
            );
            break;
        case "realm_new_stream_announcements_stream_id":
        case "realm_signup_announcements_stream_id":
        case "realm_zulip_update_announcements_stream_id":
        case "realm_default_code_block_language":
        case "realm_can_access_all_users_group":
        case "realm_can_create_web_public_channel_group":
            assert(typeof property_value === "string" || typeof property_value === "number");
            settings_components.set_dropdown_list_widget_setting_value(
                property_name,
                property_value,
            );
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
        case "realm_can_set_delete_message_policy_group":
        case "realm_can_set_topics_policy_group":
        case "realm_can_summarize_topics_group":
        case "realm_create_multiuse_invite_group":
        case "realm_direct_message_initiator_group":
        case "realm_direct_message_permission_group": {
            const pill_widget = settings_components.get_group_setting_widget(property_name);
            assert(pill_widget !== null);
            settings_components.set_group_setting_widget_value(
                pill_widget,
                group_setting_value_schema.parse(property_value),
            );
            break;
        }
        case "realm_default_language":
            assert(typeof property_value === "string");
            $("#org-notifications .language_selection_widget").attr(
                "data-language-code",
                property_value,
            );
            $("#org-notifications .language_selection_widget .language_selection_button").text(
                // We know this is defined, since we got the `property_value` from a dropdown
                // of valid language options.
                get_language_name(property_value)!,
            );
            break;
        case "realm_org_type":
            assert(typeof property_value === "number");
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
            set_message_retention_setting_dropdown(undefined);
            break;
        case "realm_waiting_period_threshold":
            set_realm_waiting_period_setting();
            break;
        default:
            if (property_value !== undefined) {
                const validated_property_value = z
                    .union([z.string(), z.number(), z.boolean()])
                    .parse(property_value);
                settings_components.set_input_element_value($elem, validated_property_value);
            } else {
                blueslip.error("Element refers to unknown property", {property_name});
            }
    }
    update_dependent_subsettings(property_name);
}

export function discard_stream_property_element_changes(
    elem: HTMLElement,
    sub: StreamSubscription,
): void {
    const $elem = $(elem);
    const property_name = settings_components.extract_property_name($elem);
    const property_value = settings_components.get_stream_settings_property_value(
        stream_settings_property_schema.parse(property_name),
        sub,
    );

    if (Object.keys(realm.server_supported_permission_settings.stream).includes(property_name)) {
        const pill_widget = settings_components.get_group_setting_widget(property_name);
        assert(pill_widget !== null);
        settings_components.set_group_setting_widget_value(
            pill_widget,
            group_setting_value_schema.parse(property_value),
        );
        update_dependent_subsettings(property_name);
        return;
    }

    switch (property_name) {
        case "stream_privacy": {
            assert(typeof property_value === "string");
            $elem.find(`input[value='${CSS.escape(property_value)}']`).prop("checked", true);

            // Hide stream privacy warning banner
            const $stream_permissions_warning_banner = $(
                "#stream_settings .stream-permissions-warning-banner",
            );
            if (!$stream_permissions_warning_banner.is(":empty")) {
                $stream_permissions_warning_banner.empty();
            }
            break;
        }
        case "message_retention_days":
            set_message_retention_setting_dropdown(sub);
            break;
        case "folder_id":
            settings_components.set_channel_folder_dropdown_value(sub);
            break;
        default:
            if (property_value !== undefined) {
                const validated_property_value = z
                    .union([z.string(), z.number(), z.boolean()])
                    .parse(property_value);
                settings_components.set_input_element_value($elem, validated_property_value);
            } else {
                blueslip.error("Element refers to unknown property", {property_name});
            }
    }
    update_dependent_subsettings(property_name);
}

export function discard_group_property_element_changes($elem: JQuery, group: UserGroup): void {
    const property_name = settings_components.extract_property_name($elem);
    const property_value = settings_components.get_group_property_value(
        z.keyof(user_groups.user_group_schema).parse(property_name),
        group,
    );

    const group_widget_settings = [...settings_components.group_setting_widget_map.keys()];
    if (group_widget_settings.includes(property_name)) {
        const pill_widget = settings_components.get_group_setting_widget(property_name);
        assert(pill_widget !== null);
        settings_components.set_group_setting_widget_value(
            pill_widget,
            group_setting_value_schema.parse(property_value),
        );
    } else {
        blueslip.error("Element refers to unknown property", {property_name});
    }
    update_dependent_subsettings(property_name);
}

export function discard_realm_default_property_element_changes(elem: HTMLElement): void {
    const $elem = $(elem);
    const property_name = realm_user_settings_default_properties_schema.parse(
        settings_components.extract_property_name($elem, true),
    );
    const property_value =
        settings_components.get_realm_default_setting_property_value(property_name);
    switch (property_name) {
        case "notification_sound":
            assert(typeof property_value === "string");
            audible_notifications.update_notification_sound_source(
                $("audio#realm-default-notification-sound-audio"),
                {
                    notification_sound: property_value,
                },
            );
            settings_components.set_input_element_value($elem, property_value);
            break;
        case "color_scheme":
        case "emojiset":
        case "user_list_style":
            // Because this widget has a radio button structure, it
            // needs custom reset code.
            assert(typeof property_value === "number" || typeof property_value === "string");
            $elem
                .find(`input[value='${CSS.escape(property_value.toString())}']`)
                .prop("checked", true);
            break;
        case "web_font_size_px":
        case "web_line_height_percent": {
            const setting_value = z.number().parse(property_value);
            $elem.val(setting_value);
            if (property_name === "web_font_size_px") {
                $elem.closest(".button-group").find(".display-value").text(setting_value);
            } else {
                $elem
                    .closest(".button-group")
                    .find(".display-value")
                    .text(
                        information_density.get_string_display_value_for_line_height(setting_value),
                    );
            }
            information_density.enable_or_disable_control_buttons(
                $elem.closest(".settings-subsection-parent"),
            );
            break;
        }
        case "email_notifications_batching_period_seconds":
        case "email_notification_batching_period_edit_minutes":
            settings_notifications.set_notification_batching_ui(
                $("#realm-user-default-settings"),
                realm_user_settings_defaults.email_notifications_batching_period_seconds,
            );
            break;
        default:
            if (property_value !== undefined) {
                const validated_property_value = z
                    .union([z.string(), z.number(), z.boolean()])
                    .parse(property_value);
                settings_components.set_input_element_value($elem, validated_property_value);
            } else {
                blueslip.error("Element refers to unknown property", {property_name});
            }
    }
    update_dependent_subsettings(property_name);
}

function discard_realm_settings_subsection_changes($subsection: JQuery): void {
    for (const elem of settings_components.get_subsection_property_elements($subsection)) {
        discard_realm_property_element_changes(elem);
    }
    const $save_button_controls = $subsection.find(".save-button-controls");
    settings_components.change_save_button_state($save_button_controls, "discarded");
}

export function discard_stream_settings_subsection_changes(
    $subsection: JQuery,
    sub: StreamSubscription,
): void {
    for (const elem of settings_components.get_subsection_property_elements($subsection)) {
        discard_stream_property_element_changes(elem, sub);
    }
    const $save_button_controls = $subsection.find(".save-button-controls");
    settings_components.change_save_button_state($save_button_controls, "discarded");
}

export function discard_group_settings_subsection_changes(
    $subsection: JQuery,
    group: UserGroup,
): void {
    for (const elem of settings_components.get_subsection_property_elements($subsection)) {
        discard_group_property_element_changes($(elem), group);
    }
    const $save_button_controls = $subsection.find(".save-button-controls");
    settings_components.change_save_button_state($save_button_controls, "discarded");
}

export function discard_realm_default_settings_subsection_changes($subsection: JQuery): void {
    for (const elem of settings_components.get_subsection_property_elements($subsection)) {
        discard_realm_default_property_element_changes(elem);
    }
    const $save_button_controls = $subsection.find(".save-button-controls");
    settings_components.change_save_button_state($save_button_controls, "discarded");
}

export function deactivate_organization(e: JQuery.Event): void {
    e.preventDefault();
    e.stopPropagation();

    function do_deactivate_realm(): void {
        const raw_delete_in = $<HTMLSelectOneElement>(
            "select:not([multiple])#delete-realm-data-in",
        ).val()!;
        let delete_in_days: number | null;

        // See settings_config.realm_deletion_in_values for why we do this conversion.
        if (raw_delete_in === "null") {
            delete_in_days = null;
        } else if (raw_delete_in === "custom") {
            const deletes_in_minutes = util.get_custom_time_in_minutes(
                custom_deletion_time_unit,
                custom_deletion_time_input,
            );
            delete_in_days = deletes_in_minutes / (60 * 24);
        } else {
            const deletes_in_minutes = Number.parseFloat(raw_delete_in);
            delete_in_days = deletes_in_minutes / (60 * 24);
        }
        const data = {
            deletion_delay_days: JSON.stringify(delete_in_days),
        };

        channel.post({
            url: "/json/realm/deactivate",
            data,
            error(xhr) {
                ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
            },
        });
    }

    let custom_deletion_time_input = realm.server_min_deactivated_realm_deletion_days ?? 0;
    let custom_deletion_time_unit = settings_config.custom_time_unit_values.days.name;

    function delete_data_in_text(): string {
        const $delete_in = $<HTMLSelectOneElement>("select:not([multiple])#delete-realm-data-in");
        const delete_data_value = $delete_in.val()!;

        if (delete_data_value === "null") {
            return $t({defaultMessage: "Data will not be automatically deleted"});
        }

        let time_in_minutes: number;
        if (delete_data_value === "custom") {
            if (!util.validate_custom_time_input(custom_deletion_time_input)) {
                return $t({defaultMessage: "Invalid custom time"});
            }
            time_in_minutes = util.get_custom_time_in_minutes(
                custom_deletion_time_unit,
                custom_deletion_time_input,
            );
            if (!is_valid_time_period(time_in_minutes)) {
                return $t({defaultMessage: "Invalid custom time"});
            }
        } else {
            // These options were already filtered for is_valid_time_period.
            time_in_minutes = Number.parseFloat(delete_data_value);
        }

        if (time_in_minutes === 0) {
            return $t({defaultMessage: "Data will be deleted immediately"});
        }

        // The below is a duplicate of timerender.get_full_datetime, with a different base string.
        const valid_to = add(new Date(), {minutes: time_in_minutes});
        const date = timerender.get_localized_date_or_time_for_format(valid_to, "dayofyear_year");
        return $t({defaultMessage: "Data will be deleted after {date}"}, {date});
    }

    const minimum_allowed_days = realm.server_min_deactivated_realm_deletion_days ?? 0;
    const maximum_allowed_days = realm.server_max_deactivated_realm_deletion_days;

    function is_valid_time_period(time_period: string | number): boolean {
        if (time_period === "custom") {
            return true;
        }
        if (time_period === "null") {
            if (maximum_allowed_days === null) {
                return true;
            }
            return false;
        }
        if (typeof time_period === "number") {
            if (maximum_allowed_days === null) {
                if (time_period >= minimum_allowed_days * 24 * 60) {
                    return true;
                }
            } else {
                if (
                    time_period >= minimum_allowed_days * 24 * 60 &&
                    time_period <= maximum_allowed_days * 24 * 60
                ) {
                    return true;
                }
            }
        }
        return false;
    }

    function get_custom_deletion_input_text(): string {
        if (maximum_allowed_days === null) {
            if (minimum_allowed_days === 0) {
                // If there's no limit at all, avoid showing 0+. It's
                // not a marginal string for translators, since we use
                // that string elsewhere.
                return $t({defaultMessage: "Custom time"});
            }
            return $t({defaultMessage: `Custom time ({min}+ days)`}, {min: minimum_allowed_days});
        }
        return $t(
            {defaultMessage: `Custom time ({min}-{max} days)`},
            {min: minimum_allowed_days, max: maximum_allowed_days},
        );
    }

    function toggle_deactivate_submit_button(): void {
        const $delete_in = $<HTMLSelectOneElement>("select:not([multiple])#delete-realm-data-in");
        const valid_custom_time =
            util.validate_custom_time_input(custom_deletion_time_input) &&
            is_valid_time_period(
                util.get_custom_time_in_minutes(
                    custom_deletion_time_unit,
                    custom_deletion_time_input,
                ),
            );
        $("#deactivate-realm-user-modal .dialog_submit_button").prop(
            "disabled",
            $delete_in.val() === "custom" && !valid_custom_time,
        );
    }

    function deactivate_realm_modal_post_render(): void {
        settings_components.set_custom_time_inputs_visibility(
            $("#delete-realm-data-in"),
            custom_deletion_time_unit,
            custom_deletion_time_input,
        );
        settings_components.set_time_input_formatted_text(
            $("#delete-realm-data-in"),
            delete_data_in_text(),
        );

        $("#delete-realm-data-in").on("change", () => {
            // If the user navigates away and back to the custom
            // time input, we show a better value than "NaN" if
            // the previous value was invalid.
            if (!util.validate_custom_time_input(custom_deletion_time_input)) {
                custom_deletion_time_input = 0;
            }
            settings_components.set_custom_time_inputs_visibility(
                $("#delete-realm-data-in"),
                custom_deletion_time_unit,
                custom_deletion_time_input,
            );
            settings_components.set_time_input_formatted_text(
                $("#delete-realm-data-in"),
                delete_data_in_text(),
            );
            toggle_deactivate_submit_button();
        });

        $("#custom-deletion-time-input").on("keydown", (e) => {
            if (e.key === "Enter") {
                // Prevent submitting the realm deactivation form via Enter.
                e.preventDefault();
                return;
            }
        });

        $("#custom-realm-deletion-time").on(
            "input",
            ".custom-time-input-value, .custom-time-input-unit",
            () => {
                custom_deletion_time_input = util.check_time_input(
                    $<HTMLInputElement>("input#custom-deletion-time-input").val()!,
                );
                custom_deletion_time_unit = $<HTMLSelectOneElement>(
                    "select:not([multiple])#custom-deletion-time-unit",
                ).val()!;
                settings_components.set_time_input_formatted_text(
                    $("#delete-realm-data-in"),
                    delete_data_in_text(),
                );
                toggle_deactivate_submit_button();
            },
        );
    }

    const all_delete_options = Object.values(settings_config.realm_deletion_in_values);
    const valid_delete_options = all_delete_options.filter((option) =>
        is_valid_time_period(option.value),
    );
    const time_unit_choices = [
        settings_config.custom_time_unit_values.days,
        settings_config.custom_time_unit_values.weeks,
    ];

    const html_body = render_settings_deactivate_realm_modal({
        delete_in_options: valid_delete_options,
        custom_deletion_input_label: get_custom_deletion_input_text(),
        time_choices: time_unit_choices,
    });

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Deactivate organization"}),
        help_link: "/help/deactivate-your-organization",
        html_body,
        id: "deactivate-realm-user-modal",
        on_click: do_deactivate_realm,
        close_on_submit: false,
        focus_submit_on_open: true,
        html_submit_button: $t_html({defaultMessage: "Confirm"}),
        post_render: deactivate_realm_modal_post_render,
    });
}

export function sync_realm_settings(property: string): void {
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
    if ($element.length > 0) {
        const $subsection = $element.closest(".settings-subsection-parent");
        if ($subsection.find(".save-button-controls").hasClass("hide")) {
            discard_realm_property_element_changes(util.the($element));
        } else {
            discard_realm_settings_subsection_changes($subsection);
        }
    }
}

export function save_organization_settings(
    data: Record<string, string | number | boolean>,
    $save_button: JQuery,
    patch_url: string,
): void {
    const $subsection_parent = $save_button.closest(".settings-subsection-parent");
    const $save_button_container = $subsection_parent.find(".save-button-controls");
    const $failed_alert_elem = $subsection_parent.find(".subsection-failed-status p");
    settings_components.change_save_button_state($save_button_container, "saving");
    channel.patch({
        url: patch_url,
        data,
        success() {
            $failed_alert_elem.hide();
            settings_components.change_save_button_state($save_button_container, "succeeded");
        },
        error(xhr) {
            settings_components.change_save_button_state($save_button_container, "failed");
            $save_button.hide();
            ui_report.error($t_html({defaultMessage: "Save failed"}), xhr, $failed_alert_elem);
        },
    });
}

export function set_up(): void {
    build_page();
    maybe_disable_widgets();
}

function set_up_dropdown_widget(
    setting_name: keyof Realm,
    setting_options: () => dropdown_widget.Option[],
    setting_type: string,
): void {
    const $save_discard_widget_container = $(`#id_${CSS.escape(setting_name)}`).closest(
        ".settings-subsection-parent",
    );
    const $events_container = $(`#id_${CSS.escape(setting_name)}`).closest(".settings-section");

    let text_if_current_value_not_in_options;
    if (setting_type === "channel") {
        text_if_current_value_not_in_options = $t({defaultMessage: "Cannot view channel"});
    }

    let unique_id_type: dropdown_widget.DataType = "number";
    if (setting_type === "language") {
        unique_id_type = "string";
    }

    const setting_dropdown_widget = new dropdown_widget.DropdownWidget({
        widget_name: setting_name,
        get_options: setting_options,
        $events_container,
        item_click_callback(event, dropdown, this_widget) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            this_widget.render();
            settings_components.save_discard_realm_settings_widget_status_handler(
                $save_discard_widget_container,
            );
        },
        default_id: z.union([z.string(), z.number()]).parse(realm[setting_name]),
        unique_id_type,
        ...(text_if_current_value_not_in_options && {text_if_current_value_not_in_options}),
        on_mount_callback(dropdown) {
            if (setting_type === "group") {
                $(dropdown.popper).css("min-width", "300px");
                $(dropdown.popper).find(".simplebar-content").css("width", "max-content");
                $(dropdown.popper).find(".simplebar-content").css("min-width", "100%");
            }
        },
    });
    settings_components.set_dropdown_setting_widget(setting_name, setting_dropdown_widget);
    setting_dropdown_widget.setup();
}

export function set_up_dropdown_widget_for_realm_group_settings(): void {
    const realm_group_permission_settings = Object.entries(
        realm.server_supported_permission_settings.realm,
    );

    for (const [setting_name, setting_config] of realm_group_permission_settings) {
        if (!setting_config.require_system_group) {
            // For settings that do not require system groups,
            // we use pills UI.
            continue;
        }
        const get_setting_options = (): dropdown_widget.Option[] =>
            group_permission_settings.get_realm_user_groups_for_dropdown_list_widget(
                setting_name,
                "realm",
            );
        set_up_dropdown_widget(
            z.keyof(realm_schema).parse("realm_" + setting_name),
            get_setting_options,
            "group",
        );
    }
}

export let init_dropdown_widgets = (): void => {
    const notification_stream_options = (): dropdown_widget.Option[] => {
        const streams = stream_settings_data.get_streams_for_settings_page();
        const options: dropdown_widget.Option[] = streams.map((stream) => ({
            name: stream.name,
            unique_id: stream.stream_id,
            stream,
        }));

        const disabled_option = {
            is_setting_disabled: true,
            show_disabled_icon: true,
            show_disabled_option_name: false,
            unique_id: DISABLED_STATE_ID,
            name: $t({defaultMessage: "Disabled"}),
        };

        options.unshift(disabled_option);
        return options;
    };

    set_up_dropdown_widget(
        "realm_new_stream_announcements_stream_id",
        notification_stream_options,
        "channel",
    );
    set_up_dropdown_widget(
        "realm_signup_announcements_stream_id",
        notification_stream_options,
        "channel",
    );
    set_up_dropdown_widget(
        "realm_zulip_update_announcements_stream_id",
        notification_stream_options,
        "channel",
    );

    set_up_dropdown_widget(
        "realm_default_code_block_language",
        combined_code_language_options,
        "language",
    );

    set_up_dropdown_widget_for_realm_group_settings();
};

export const combined_code_language_options = (): dropdown_widget.Option[] => {
    // Default language options from pygments_data
    const default_options = Object.keys(pygments_data.langs).map((x) => ({
        name: x,
        unique_id: x,
    }));

    // Custom playground language options from realm_playgrounds.
    const playground_options = (realm.realm_playgrounds ?? []).map((playground) => ({
        name: playground.pygments_language,
        unique_id: playground.pygments_language,
    }));

    const disabled_option = {
        is_setting_disabled: true,
        show_disabled_icon: true,
        show_disabled_option_name: false,
        unique_id: "",
        name: $t({defaultMessage: "No language set"}),
    };

    return [disabled_option, ...playground_options, ...default_options];
};

export function rewire_init_dropdown_widgets(value: typeof init_dropdown_widgets): void {
    init_dropdown_widgets = value;
}

export function register_save_discard_widget_handlers(
    $container: JQuery,
    patch_url: string,
    for_realm_default_settings: boolean,
): void {
    $container.on("change input", "input, select, textarea", function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();

        // This event handler detects whether after these input
        // changes, any fields have different values from the current
        // official values stored in the database and page_params.  If
        // they do, we transition to the "unsaved" state showing the
        // save/discard widget; otherwise, we hide that widget (the
        // "discarded" state).

        if ($(this).hasClass("no-input-change-detection")) {
            // This is to prevent input changes detection in elements
            // within a subsection whose changes should not affect the
            // visibility of the discard button
            return false;
        }

        if ($(this).hasClass("setting_email_notifications_batching_period_seconds")) {
            const show_elem = $(this).val() === "custom_period";
            settings_components.change_element_block_display_property(
                "realm_email_notification_batching_period_edit_minutes",
                show_elem,
            );
        }

        const $subsection = $(this).closest(".settings-subsection-parent");
        if (for_realm_default_settings) {
            settings_components.save_discard_default_realm_settings_widget_status_handler(
                $subsection,
            );
        } else {
            settings_components.save_discard_realm_settings_widget_status_handler($subsection);
        }

        return undefined;
    });

    $container.on(
        "click",
        ".subsection-header .subsection-changes-discard button",
        function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();
            const $subsection = $(this).closest(".settings-subsection-parent");
            if (for_realm_default_settings) {
                discard_realm_default_settings_subsection_changes($subsection);
            } else {
                discard_realm_settings_subsection_changes($subsection);
            }
        },
    );

    $container.on(
        "click",
        ".subsection-header .subsection-changes-save .save-button[data-status='unsaved']",
        function (this: HTMLElement, e: JQuery.ClickEvent) {
            e.preventDefault();
            e.stopPropagation();
            const $save_button = $(this);
            const $subsection_elem = $save_button.closest(".settings-subsection-parent");
            let data: Record<string, string | number | boolean>;
            if (!for_realm_default_settings) {
                data =
                    settings_components.populate_data_for_realm_settings_request($subsection_elem);
            } else {
                data =
                    settings_components.populate_data_for_default_realm_settings_request(
                        $subsection_elem,
                    );
            }
            save_organization_settings(data, $save_button, patch_url);
        },
    );

    $container.on(
        "click",
        ".subsection-header .subsection-changes-save button",
        (e: JQuery.ClickEvent) => {
            // Prevents the default form submission action when clicking a button (e.g., "Saving...").
            e.preventDefault();
        },
    );
}

// Exported for tests
export let initialize_group_setting_widgets = (): void => {
    const realm_group_permission_settings = Object.entries(
        realm.server_supported_permission_settings.realm,
    );
    for (const [setting_name, setting_config] of realm_group_permission_settings) {
        if (setting_config.require_system_group) {
            continue;
        }

        const opts: {
            $pill_container: JQuery;
            setting_name: RealmGroupSettingNameSupportingAnonymousGroups;
            pill_update_callback?: () => void;
        } = {
            $pill_container: $(`#id_realm_${CSS.escape(setting_name)}`),
            setting_name:
                realm_group_setting_name_supporting_anonymous_groups_schema.parse(setting_name),
        };
        if (setting_name === "direct_message_permission_group") {
            opts.pill_update_callback = check_disable_direct_message_initiator_group_widget;
        }
        settings_components.create_realm_group_setting_widget(opts);
    }

    enable_or_disable_group_permission_settings();
    check_disable_direct_message_initiator_group_widget();
};

export function rewire_initialize_group_setting_widgets(
    value: typeof initialize_group_setting_widgets,
): void {
    initialize_group_setting_widgets = value;
}

export function build_page(): void {
    meta.loaded = true;

    loading.make_indicator($("#admin_page_auth_methods_loading_indicator"));

    // Initialize all the dropdown list widgets.
    init_dropdown_widgets();
    // Populate realm domains
    populate_realm_domains_label(realm.realm_domains);

    initialize_group_setting_widgets();

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
    set_message_retention_setting_dropdown(undefined);
    set_org_join_restrictions_dropdown();
    set_message_content_in_email_notifications_visibility();
    set_digest_emails_weekday_visibility();
    set_create_web_public_stream_dropdown_visibility();
    disable_create_user_groups_if_on_limited_plan();

    register_save_discard_widget_handlers($(".admin-realm-form"), "/json/realm", false);

    $(".org-permissions-form").on(
        "input change",
        ".time-limit-custom-input",
        function (this: HTMLInputElement, e) {
            e.preventDefault();
            e.stopPropagation();
            settings_components.update_custom_time_limit_minute_text($(this));
        },
    );

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

    $<HTMLSelectOneElement>("select:not([multiple])#id_realm_jitsi_server_url").on(
        "change",
        function () {
            const dropdown_val = this.value;
            update_jitsi_server_url_custom_input(dropdown_val);
        },
    );

    $<HTMLSelectOneElement>("select:not([multiple])#id_realm_message_retention_days").on(
        "change",
        function () {
            const message_retention_setting_dropdown_value = this.value;
            settings_components.change_element_block_display_property(
                "id_realm_message_retention_custom_input",
                message_retention_setting_dropdown_value === "custom_period",
            );
        },
    );

    $<HTMLSelectOneElement>("select:not([multiple])#id_realm_waiting_period_threshold").on(
        "change",
        function () {
            const waiting_period_threshold = this.value;
            settings_components.change_element_block_display_property(
                "id_realm_waiting_period_threshold_custom_input",
                waiting_period_threshold === "custom_period",
            );
        },
    );

    $("#id_realm_digest_emails_enabled").on("change", function () {
        const digest_emails_enabled = $(this).is(":checked");
        settings_components.change_element_block_display_property(
            "id_realm_digest_weekday",
            digest_emails_enabled,
        );
    });

    $<HTMLSelectOneElement>("select:not([multiple])#id_realm_org_join_restrictions").on(
        "change",
        function () {
            const org_join_restrictions = this.value;
            const $node = $("#allowed_domains_label").parent();
            if (org_join_restrictions === "only_selected_domain") {
                $node.show();
                if (realm.realm_domains.length === 0) {
                    settings_realm_domains.show_realm_domains_modal();
                }
            } else {
                $node.hide();
            }
        },
    );

    $<HTMLInputElement>("input#id_realm_allow_message_editing").on("change", function () {
        update_message_edit_sub_settings(this.checked);
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

    function realm_icon_logo_upload_complete(
        $spinner: JQuery,
        $upload_text: JQuery,
        $delete_button: JQuery,
    ): void {
        $spinner.css({visibility: "hidden"});
        $upload_text.show();
        $delete_button.show();
    }

    function realm_icon_logo_upload_start(
        $spinner: JQuery,
        $upload_text: JQuery,
        $delete_button: JQuery,
    ): void {
        $spinner.css({visibility: "visible"});
        $upload_text.hide();
        $delete_button.hide();
    }

    function upload_realm_logo_or_icon(
        $file_input: JQuery<HTMLInputElement>,
        night: boolean | null,
        icon: boolean,
    ): void {
        const form_data = new FormData();
        let widget;
        let url;

        assert(csrf_token !== undefined);
        form_data.append("csrfmiddlewaretoken", csrf_token);
        const files = util.the($file_input).files;
        assert(files !== null);
        for (const [i, file] of [...files].entries()) {
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

    realm_icon.build_realm_icon_widget(upload_realm_logo_or_icon);
    if (realm.zulip_plan_is_not_limited) {
        realm_logo.build_realm_logo_widget(upload_realm_logo_or_icon, false);
        realm_logo.build_realm_logo_widget(upload_realm_logo_or_icon, true);
    }

    $("#id_org_profile_preview").on("click", () => {
        window.open("/login/?preview=true", "_blank", "noopener,noreferrer");
    });

    $("#organization-profile .deactivate_realm_button").on("click", deactivate_organization);
}
