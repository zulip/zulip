import {parseISO} from "date-fns";
import $ from "jquery";

import timezones from "../generated/timezones.json";
import render_settings_overlay from "../templates/settings_overlay.hbs";
import render_settings_tab from "../templates/settings_tab.hbs";

import * as browser_history from "./browser_history.ts";
import * as common from "./common.ts";
import * as flatpickr from "./flatpickr.ts";
import {$t} from "./i18n.ts";
import * as information_density from "./information_density.ts";
import * as overlays from "./overlays.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as settings_bots from "./settings_bots.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as settings_panel_menu from "./settings_panel_menu.ts";
import * as settings_preferences from "./settings_preferences.ts";
import * as settings_sections from "./settings_sections.ts";
import * as settings_toggle from "./settings_toggle.ts";
import {current_user, realm} from "./state_data.ts";
import * as timerender from "./timerender.ts";
import {user_settings} from "./user_settings.ts";

function get_parsed_date_of_joining(): string {
    const user_date_joined = people.get_by_user_id(current_user.user_id).date_joined;
    return timerender.get_localized_date_or_time_for_format(
        parseISO(user_date_joined),
        "dayofyear_year",
    );
}

function user_can_change_password(): boolean {
    if (settings_data.user_email_not_configured()) {
        return false;
    }
    return realm.realm_email_auth_enabled;
}

export function update_lock_icon_in_sidebar(): void {
    if (current_user.is_owner) {
        $(".org-settings-list .locked").hide();
        return;
    }
    if (current_user.is_admin) {
        $(".org-settings-list .locked").hide();
        $(".org-settings-list li[data-section='auth-methods'] .locked").show();
        return;
    }

    $(".org-settings-list .locked").show();

    if (settings_bots.can_create_incoming_webhooks()) {
        $(".org-settings-list li[data-section='bot-list-admin'] .locked").hide();
    }

    if (settings_data.user_can_add_custom_emoji()) {
        $(".org-settings-list li[data-section='emoji-settings'] .locked").hide();
    }
}

export function build_page(): void {
    const settings_label = {
        // settings_notification
        allow_private_data_export: $t({
            defaultMessage: "Let administrators export my private data",
        }),
        presence_enabled: $t({
            defaultMessage: "Display my availability to other users",
        }),
        presence_enabled_parens_text: $t({defaultMessage: "invisible mode off"}),
        send_stream_typing_notifications: $t({
            defaultMessage: "Let recipients see when I'm typing messages in channels",
        }),
        send_private_typing_notifications: $t({
            defaultMessage: "Let recipients see when I'm typing direct messages",
        }),
        send_read_receipts: $t({
            defaultMessage: "Let others see when I've read messages",
        }),

        ...settings_config.notification_settings_labels,
        ...settings_config.preferences_settings_labels,
    };

    const rendered_settings_tab = render_settings_tab({
        full_name: people.my_full_name(),
        profile_picture: people.small_avatar_url_for_person(
            people.get_by_user_id(people.my_current_user_id()),
        ),
        date_joined_text: get_parsed_date_of_joining(),
        current_user,
        page_params,
        realm,
        enable_sound_select:
            user_settings.enable_sounds || user_settings.enable_stream_audible_notifications,
        zuliprc: "zuliprc",
        botserverrc: "botserverrc",
        timezones: timezones.timezones,
        can_create_new_bots: settings_bots.can_create_incoming_webhooks(),
        settings_label,
        demote_inactive_streams_values: settings_config.demote_inactive_streams_values,
        web_mark_read_on_scroll_policy_values:
            settings_config.web_mark_read_on_scroll_policy_values,
        web_channel_default_view_values: settings_config.web_channel_default_view_values,
        user_list_style_values: settings_config.user_list_style_values,
        web_animate_image_previews_values: settings_config.web_animate_image_previews_values,
        resolved_topic_notice_auto_read_policy_values:
            settings_config.resolved_topic_notice_auto_read_policy_values,
        web_stream_unreads_count_display_policy_values:
            settings_config.web_stream_unreads_count_display_policy_values,
        color_scheme_values: settings_config.color_scheme_values,
        web_home_view_values: settings_config.web_home_view_values,
        twenty_four_hour_time_values: settings_config.twenty_four_hour_time_values,
        general_settings: settings_config.all_notifications(user_settings).general_settings,
        notification_settings: settings_config.all_notifications(user_settings).settings,
        custom_stream_specific_notification_settings:
            settings_config.get_custom_stream_specific_notifications_table_row_data(),
        email_notifications_batching_period_values:
            settings_config.email_notifications_batching_period_values,
        realm_name_in_email_notifications_policy_values:
            settings_config.realm_name_in_email_notifications_policy_values,
        desktop_icon_count_display_values: settings_config.desktop_icon_count_display_values,
        disabled_notification_settings:
            settings_config.all_notifications(user_settings).disabled_notification_settings,
        information_density_settings: settings_config.get_information_density_preferences(),
        settings_render_only: settings_config.get_settings_render_only(),
        user_can_change_name: settings_data.user_can_change_name(),
        user_can_change_avatar: settings_data.user_can_change_avatar(),
        user_can_change_email: settings_data.user_can_change_email(),
        user_role_text: people.get_user_type(current_user.user_id),
        default_language_name: settings_preferences.user_default_language_name,
        default_language: user_settings.default_language,
        realm_push_notifications_enabled: realm.realm_push_notifications_enabled,
        settings_object: user_settings,
        send_read_receipts_tooltip: $t({
            defaultMessage: "Read receipts are currently disabled in this organization.",
        }),
        user_is_only_organization_owner: people.is_current_user_only_owner(),
        email_address_visibility_values: settings_config.email_address_visibility_values,
        owner_is_only_user_in_organization: people.get_active_human_count() === 1,
        user_can_change_password: user_can_change_password(),
        user_has_email_set: !settings_data.user_email_not_configured(),
        automatically_follow_topics_policy_values:
            settings_config.automatically_follow_or_unmute_topics_policy_values,
        automatically_unmute_topics_in_muted_streams_policy_values:
            settings_config.automatically_follow_or_unmute_topics_policy_values,
        web_line_height_percent_display_value:
            information_density.get_string_display_value_for_line_height(
                user_settings.web_line_height_percent,
            ),
        max_user_name_length: people.MAX_USER_NAME_LENGTH,
    });

    $(".settings-box").html(rendered_settings_tab);
    settings_bots.update_bot_settings_tip($("#personal-bot-settings-tip"));
    common.adjust_mac_kbd_tags("#user_enter_sends_label kbd");
}

export function open_settings_overlay(): void {
    overlays.open_overlay({
        name: "settings",
        $overlay: $("#settings_overlay_container"),
        on_close() {
            browser_history.exit_overlay();
            flatpickr.close_all();
            settings_panel_menu.mobile_deactivate_section();
        },
    });
}

export function launch(section: string): void {
    settings_sections.reset_sections();

    open_settings_overlay();
    if (section !== "") {
        settings_panel_menu.normal_settings.set_current_tab(section);
    }
    settings_toggle.goto("settings");
}

export function initialize(): void {
    const rendered_settings_overlay = render_settings_overlay({
        is_owner: current_user.is_owner,
        is_admin: current_user.is_admin,
        is_guest: current_user.is_guest,
        show_uploaded_files_section: realm.max_file_upload_size_mib > 0,
        show_emoji_settings_lock: !settings_data.user_can_add_custom_emoji(),
        can_create_new_bots: settings_bots.can_create_incoming_webhooks(),
        can_edit_user_panel:
            current_user.is_admin ||
            settings_data.user_can_create_multiuse_invite() ||
            settings_data.user_can_invite_users_by_email(),
    });
    $("#settings_overlay_container").append($(rendered_settings_overlay));
}
