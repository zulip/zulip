import $ from "jquery";
import * as tippy from "tippy.js";

import render_admin_tab from "../templates/settings/admin_tab.hbs";
import render_settings_organization_settings_tip from "../templates/settings/organization_settings_tip.hbs";

import * as bot_data from "./bot_data.ts";
import * as demo_organizations_ui from "./demo_organizations_ui.ts";
import {$t, language_list} from "./i18n.ts";
import * as information_density from "./information_density.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults.ts";
import * as settings from "./settings.ts";
import * as settings_bots from "./settings_bots.ts";
import * as settings_components from "./settings_components.ts";
import type {AllNotifications} from "./settings_config.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as settings_invites from "./settings_invites.ts";
import * as settings_org from "./settings_org.ts";
import * as settings_panel_menu from "./settings_panel_menu.ts";
import * as settings_sections from "./settings_sections.ts";
import * as settings_toggle from "./settings_toggle.ts";
import * as settings_users from "./settings_users.ts";
import {current_user, realm} from "./state_data.ts";
import {the} from "./util.ts";
import * as util from "./util.ts";

const admin_settings_label = {
    // Organization profile
    realm_want_advertise_in_communities_directory: $t({
        defaultMessage: "Advertise organization in the Zulip communities directory",
    }),
    // Organization settings
    realm_new_stream_announcements_stream: $t({defaultMessage: "New channel announcements"}),
    realm_signup_announcements_stream: $t({defaultMessage: "New user announcements"}),
    realm_zulip_update_announcements_stream: $t({defaultMessage: "Zulip update announcements"}),
    realm_moderation_request_channel: $t({defaultMessage: "Moderation requests"}),
    realm_inline_image_preview: $t({
        defaultMessage: "Show previews of uploaded and linked images and videos",
    }),
    realm_inline_url_embed_preview: $t({defaultMessage: "Show previews of linked websites"}),
    realm_send_welcome_emails: $t({defaultMessage: "Send emails introducing Zulip to new users"}),
    realm_require_e2ee_push_notifications: $t({
        defaultMessage: "Require end-to-end encryption for push notification content",
    }),
    realm_message_content_allowed_in_email_notifications: $t({
        defaultMessage: "Allow message content in message notification emails",
    }),
    realm_enable_spectator_access: $t({
        defaultMessage: "Allow creating web-public channels (visible to anyone on the Internet)",
    }),
    realm_send_channel_events_messages: $t({
        defaultMessage: "Send automated messages for channel events",
    }),
    realm_digest_emails_enabled: $t({
        defaultMessage: "Send weekly digest emails to inactive users",
    }),
    realm_default_code_block_language: $t({defaultMessage: "Default language for code blocks"}),
    realm_enable_welcome_message_custom_text: $t({
        defaultMessage: "Send a custom Welcome Bot message to new users",
    }),

    // Organization permissions
    realm_require_unique_names: $t({defaultMessage: "Require unique names"}),
    realm_name_changes_disabled: $t({defaultMessage: "Prevent users from changing their name"}),
    realm_email_changes_disabled: $t({
        defaultMessage: "Prevent users from changing their email address",
    }),
    realm_avatar_changes_disabled: $t({defaultMessage: "Prevent users from changing their avatar"}),
    realm_invite_required: $t({
        defaultMessage: "Invitations are required for joining this organization",
    }),
    realm_default_language: $t({
        defaultMessage: "Language for automated messages and invitation emails",
    }),
    realm_allow_message_editing: $t({defaultMessage: "Allow message editing"}),
    realm_enable_read_receipts: $t({defaultMessage: "Enable read receipts"}),
    realm_enable_read_receipts_parens_text: $t({
        defaultMessage: "Users can always disable their personal read receipts.",
    }),
    realm_enable_guest_user_indicator: $t({
        defaultMessage: "Display “(guest)” after names of guest users",
    }),
    realm_enable_guest_user_dm_warning: $t({
        defaultMessage: "Warn when composing a DM to a guest",
    }),
};

function insert_tip_box(): void {
    if (current_user.is_admin) {
        return;
    }
    const tip_box_html = render_settings_organization_settings_tip({
        is_admin: current_user.is_admin,
    });
    $(".organization-box")
        .find(".settings-section, .user-settings-section")
        .not("#emoji-settings")
        .not("#organization-auth-settings")
        .not("#admin-bot-list")
        .not("#admin-invites-list")
        .not("#admin-user-list")
        .not("#admin-active-users-list")
        .not("#admin-deactivated-users-list")
        .prepend($(tip_box_html));
}

function get_realm_level_notification_settings(): {
    general_settings: AllNotifications["general_settings"];
    notification_settings: AllNotifications["settings"];
    disabled_notification_settings: AllNotifications["disabled_notification_settings"];
} {
    const all_notifications_settings = settings_config.all_notifications(
        realm_user_settings_defaults,
    );

    // We remove enable_marketing_emails and enable_login_emails
    // setting from all_notification_settings, since there are no
    // realm-level defaults for these setting.
    all_notifications_settings.settings.other_email_settings = ["enable_digest_emails"];

    return {
        general_settings: all_notifications_settings.general_settings,
        notification_settings: all_notifications_settings.settings,
        disabled_notification_settings: all_notifications_settings.disabled_notification_settings,
    };
}

export function build_page(): void {
    let realm_night_logo_url = realm.realm_night_logo_url;
    if (realm.realm_logo_source !== "D" && realm.realm_night_logo_source === "D") {
        // If no dark theme logo is specified but a light theme one is,
        // use the light theme one.  See also similar code in realm_logo.js.
        realm_night_logo_url = realm.realm_logo_url;
    }

    let giphy_help_link = "/help/animated-gifs-from-giphy";
    if (realm.giphy_api_key === "") {
        giphy_help_link =
            "https://zulip.readthedocs.io/en/latest/production/giphy-gif-integration.html";
    }

    const options = {
        custom_profile_field_types: realm.custom_profile_field_types,
        full_name: current_user.full_name,
        profile_picture: people.small_avatar_url_for_person(current_user),
        realm_name: realm.realm_name,
        realm_org_type: realm.realm_org_type,
        realm_available_video_chat_providers: realm.realm_available_video_chat_providers,
        server_jitsi_server_url: realm.server_jitsi_server_url,
        giphy_rating_options: realm.giphy_rating_options,
        giphy_api_key_empty: realm.giphy_api_key === "",
        realm_description: realm.realm_description,
        realm_inline_image_preview: realm.realm_inline_image_preview,
        server_inline_image_preview: realm.server_inline_image_preview,
        realm_inline_url_embed_preview: realm.realm_inline_url_embed_preview,
        server_inline_url_embed_preview: realm.server_inline_url_embed_preview,
        realm_authentication_methods: realm.realm_authentication_methods,
        realm_name_changes_disabled: realm.realm_name_changes_disabled,
        realm_require_unique_names: realm.realm_require_unique_names,
        realm_email_changes_disabled: realm.realm_email_changes_disabled,
        realm_avatar_changes_disabled: realm.realm_avatar_changes_disabled,
        can_add_emojis: settings_data.user_can_add_custom_emoji(),
        can_create_new_bots: settings_bots.can_create_incoming_webhooks(),
        realm_message_content_edit_limit_minutes:
            settings_components.get_realm_time_limits_in_minutes(
                "realm_message_content_edit_limit_seconds",
            ),
        realm_move_messages_between_streams_limit_minutes:
            settings_components.get_realm_time_limits_in_minutes(
                "realm_move_messages_between_streams_limit_seconds",
            ),
        realm_move_messages_within_stream_limit_minutes:
            settings_components.get_realm_time_limits_in_minutes(
                "realm_move_messages_within_stream_limit_seconds",
            ),
        realm_message_content_delete_limit_minutes:
            settings_components.get_realm_time_limits_in_minutes(
                "realm_message_content_delete_limit_seconds",
            ),
        realm_message_retention_days: realm.realm_message_retention_days,
        realm_message_edit_history_visibility_policy:
            realm.realm_message_edit_history_visibility_policy,
        realm_allow_message_editing: realm.realm_allow_message_editing,
        language_list,
        realm_default_language_code: realm.realm_default_language,
        realm_waiting_period_threshold: realm.realm_waiting_period_threshold,
        realm_moderation_request_channel_id: realm.realm_moderation_request_channel_id,
        realm_new_stream_announcements_stream_id: realm.realm_new_stream_announcements_stream_id,
        realm_signup_announcements_stream_id: realm.realm_signup_announcements_stream_id,
        realm_zulip_update_announcements_stream_id:
            realm.realm_zulip_update_announcements_stream_id,
        is_admin: current_user.is_admin,
        is_guest: current_user.is_guest,
        is_owner: current_user.is_owner,
        user_can_change_logo: settings_data.user_can_change_logo(),
        realm_icon_source: realm.realm_icon_source,
        realm_icon_url: realm.realm_icon_url,
        realm_logo_source: realm.realm_logo_source,
        realm_logo_url: realm.realm_logo_url,
        realm_night_logo_source: realm.realm_night_logo_source,
        realm_night_logo_url,
        realm_topics_policy: realm.realm_topics_policy,
        realm_topics_policy_values: settings_config.get_realm_topics_policy_values(),
        empty_string_topic_display_name: util.get_final_topic_display_name(""),
        realm_send_welcome_emails: realm.realm_send_welcome_emails,
        realm_enable_welcome_message_custom_text:
            realm.realm_welcome_message_custom_text.length > 0,
        realm_welcome_message_custom_text: realm.realm_welcome_message_custom_text,
        realm_require_e2ee_push_notifications: realm.realm_require_e2ee_push_notifications,
        realm_message_content_allowed_in_email_notifications:
            realm.realm_message_content_allowed_in_email_notifications,
        realm_enable_spectator_access: realm.realm_enable_spectator_access,
        settings_send_digest_emails: realm.settings_send_digest_emails,
        realm_send_channel_events_messages: realm.realm_send_channel_events_messages,
        realm_digest_emails_enabled: realm.realm_digest_emails_enabled,
        realm_digest_weekday: realm.realm_digest_weekday,
        development: page_params.development_environment,
        zulip_plan_is_not_limited: realm.zulip_plan_is_not_limited,
        upgrade_text_for_wide_organization_logo: realm.upgrade_text_for_wide_organization_logo,
        realm_default_external_accounts: realm.realm_default_external_accounts,
        admin_settings_label,
        msg_edit_limit_dropdown_values: settings_config.msg_edit_limit_dropdown_values,
        msg_delete_limit_dropdown_values: settings_config.msg_delete_limit_dropdown_values,
        msg_move_limit_dropdown_values: settings_config.msg_move_limit_dropdown_values,
        email_address_visibility_values: settings_config.email_address_visibility_values,
        waiting_period_threshold_dropdown_values:
            settings_config.waiting_period_threshold_dropdown_values,
        message_edit_history_visibility_policy_values:
            settings_config.message_edit_history_visibility_policy_values,
        can_create_multiuse_invite: settings_data.user_can_create_multiuse_invite(),
        can_invite_users_by_email: settings_data.user_can_invite_users_by_email(),
        realm_invite_required: realm.realm_invite_required,
        policy_values: settings_config.common_policy_values,
        ...settings_org.get_organization_settings_options(),
        demote_inactive_streams_values: settings_config.demote_inactive_streams_values,
        web_mark_read_on_scroll_policy_values:
            settings_config.web_mark_read_on_scroll_policy_values,
        web_channel_default_view_values: settings_config.web_channel_default_view_values,
        user_list_style_values: settings_config.user_list_style_values,
        web_stream_unreads_count_display_policy_values:
            settings_config.web_stream_unreads_count_display_policy_values,
        web_animate_image_previews_values: settings_config.web_animate_image_previews_values,
        resolved_topic_notice_auto_read_policy_values:
            settings_config.resolved_topic_notice_auto_read_policy_values,
        color_scheme_values: settings_config.color_scheme_values,
        web_home_view_values: settings_config.web_home_view_values,
        settings_object: realm_user_settings_defaults,
        information_density_settings: settings_config.get_information_density_preferences(),
        settings_render_only: settings_config.get_settings_render_only(),
        settings_label: settings_config.realm_user_settings_defaults_labels,
        desktop_icon_count_display_values: settings_config.desktop_icon_count_display_values,
        enable_sound_select:
            realm_user_settings_defaults.enable_sounds ||
            realm_user_settings_defaults.enable_stream_audible_notifications,
        email_notifications_batching_period_values:
            settings_config.email_notifications_batching_period_values,
        realm_name_in_email_notifications_policy_values:
            settings_config.realm_name_in_email_notifications_policy_values,
        twenty_four_hour_time_values: settings_config.twenty_four_hour_time_values,
        disable_enable_spectator_access_setting:
            !realm.server_web_public_streams_enabled || !realm.zulip_plan_is_not_limited,
        realm_push_notifications_enabled: realm.realm_push_notifications_enabled,
        realm_org_type_values: settings_org.get_org_type_dropdown_options(),
        realm_want_advertise_in_communities_directory:
            realm.realm_want_advertise_in_communities_directory,
        disable_want_advertise_in_communities_directory: !realm.realm_push_notifications_enabled,
        is_business_type_org:
            realm.realm_org_type === settings_config.all_org_type_values.business.code,
        realm_enable_read_receipts: realm.realm_enable_read_receipts,
        allow_sorting_deactivated_users_list_by_email:
            settings_users.allow_sorting_deactivated_users_list_by_email(),
        has_bots: bot_data.get_all_bots_for_current_user().length > 0,
        user_has_email_set: !settings_data.user_email_not_configured(),
        automatically_follow_topics_policy_values:
            settings_config.automatically_follow_or_unmute_topics_policy_values,
        automatically_unmute_topics_in_muted_streams_policy_values:
            settings_config.automatically_follow_or_unmute_topics_policy_values,
        realm_enable_guest_user_indicator: realm.realm_enable_guest_user_indicator,
        realm_enable_guest_user_dm_warning: realm.realm_enable_guest_user_dm_warning,
        active_user_list_dropdown_widget_name: settings_users.active_user_list_dropdown_widget_name,
        deactivated_user_list_dropdown_widget_name:
            settings_users.deactivated_user_list_dropdown_widget_name,
        giphy_help_link,
        ...get_realm_level_notification_settings(),
        all_bots_list_dropdown_widget_name: settings_bots.all_bots_list_dropdown_widget_name,
        your_bots_list_dropdown_widget_name: settings_bots.your_bots_list_dropdown_widget_name,
        group_setting_labels: settings_config.all_group_setting_labels.realm,
        server_can_summarize_topics: realm.server_can_summarize_topics,
        is_plan_self_hosted:
            realm.realm_plan_type === settings_config.realm_plan_types.self_hosted.code,
        has_billing_access: settings_data.user_has_billing_access(),
        web_line_height_percent_display_value:
            information_density.get_string_display_value_for_line_height(
                realm_user_settings_defaults.web_line_height_percent,
            ),
    };

    const rendered_admin_tab = render_admin_tab(options);
    $("#settings_content .organization-box").html(rendered_admin_tab);
    $("#settings_content .alert").removeClass("show");

    settings_bots.update_bot_settings_tip($("#admin-bot-settings-tip"));
    settings_invites.update_invite_user_panel();
    insert_tip_box();

    if (realm.demo_organization_scheduled_deletion_date && current_user.is_admin) {
        demo_organizations_ui.insert_demo_organization_warning();
        demo_organizations_ui.handle_demo_organization_conversion();
    }

    $("#id_realm_digest_weekday").val(realm.realm_digest_weekday);

    const is_plan_plus = realm.realm_plan_type === settings_config.realm_plan_types.plus.code;
    const is_plan_self_hosted =
        realm.realm_plan_type === settings_config.realm_plan_types.self_hosted.code;
    if (current_user.is_admin && !(is_plan_plus || is_plan_self_hosted)) {
        $("#realm_can_access_all_users_group_widget").prop("disabled", true);

        const opts: {content?: string} = {};
        if (settings_data.user_has_billing_access()) {
            opts.content = $t({
                defaultMessage: "This feature is available on Zulip Cloud Plus. Upgrade to access.",
            });
        } else {
            opts.content = $t({
                defaultMessage: "This feature is available on Zulip Cloud Plus.",
            });
        }

        tippy.default(the($("#realm_can_access_all_users_group_widget_container")), opts);
    }
}

export function launch(section: string, settings_tab: string | undefined): void {
    settings_sections.reset_sections();

    settings.open_settings_overlay();
    if (section !== "") {
        settings_panel_menu.org_settings.set_current_tab(section);
    }
    if (section === "users") {
        settings_panel_menu.org_settings.set_user_settings_tab(settings_tab);
    }
    if (section === "bots") {
        settings_panel_menu.org_settings.set_bot_settings_tab(settings_tab);
    }
    settings_toggle.goto("organization");
}
