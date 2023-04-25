import $ from "jquery";

import render_admin_tab from "../templates/settings/admin_tab.hbs";
import render_settings_organization_settings_tip from "../templates/settings/organization_settings_tip.hbs";

import * as bot_data from "./bot_data";
import {$t, get_language_name, language_list} from "./i18n";
import {page_params} from "./page_params";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as settings from "./settings";
import * as settings_bots from "./settings_bots";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as settings_invites from "./settings_invites";
import * as settings_org from "./settings_org";
import * as settings_panel_menu from "./settings_panel_menu";
import * as settings_sections from "./settings_sections";
import * as settings_toggle from "./settings_toggle";
import * as settings_users from "./settings_users";

const admin_settings_label = {
    // Organization profile
    realm_want_advertise_in_communities_directory: $t({
        defaultMessage: "Advertise organization in the Zulip communities directory",
    }),
    // Organization settings
    realm_allow_edit_history: $t({defaultMessage: "Enable message edit history"}),
    realm_mandatory_topics: $t({defaultMessage: "Require topics in stream messages"}),
    realm_notifications_stream: $t({defaultMessage: "New stream announcements"}),
    realm_signup_notifications_stream: $t({defaultMessage: "New user announcements"}),
    realm_inline_image_preview: $t({defaultMessage: "Show previews of uploaded and linked images"}),
    realm_inline_url_embed_preview: $t({defaultMessage: "Show previews of linked websites"}),
    realm_send_welcome_emails: $t({defaultMessage: "Send emails introducing Zulip to new users"}),
    realm_message_content_allowed_in_email_notifications: $t({
        defaultMessage: "Allow message content in message notification emails",
    }),
    realm_enable_spectator_access: $t({
        defaultMessage: "Allow creating web-public streams (visible to anyone on the Internet)",
    }),
    realm_digest_emails_enabled: $t({
        defaultMessage: "Send weekly digest emails to inactive users",
    }),
    realm_default_code_block_language: $t({defaultMessage: "Default language for code blocks"}),

    // Organization permissions
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
};

function insert_tip_box() {
    if (page_params.is_admin) {
        return;
    }
    const tip_box = render_settings_organization_settings_tip({is_admin: page_params.is_admin});
    $(".organization-box")
        .find(".settings-section")
        .not("#emoji-settings")
        .not("#user-groups-admin")
        .not("#organization-auth-settings")
        .not("#admin-bot-list")
        .not("#admin-invites-list")
        .prepend(tip_box);
}

function get_realm_level_notification_settings(options) {
    const all_notifications_settings = settings_config.all_notifications(
        realm_user_settings_defaults,
    );

    // We remove enable_marketing_emails and enable_login_emails
    // setting from all_notification_settings, since there are no
    // realm-level defaults for these setting.
    all_notifications_settings.settings.other_email_settings = ["enable_digest_emails"];

    options.general_settings = all_notifications_settings.general_settings;
    options.notification_settings = all_notifications_settings.settings;
    options.show_push_notifications_tooltip =
        all_notifications_settings.show_push_notifications_tooltip;
}

export function build_page() {
    const options = {
        custom_profile_field_types: page_params.custom_profile_field_types,
        full_name: page_params.full_name,
        realm_name: page_params.realm_name,
        realm_org_type: page_params.realm_org_type,
        realm_available_video_chat_providers: page_params.realm_available_video_chat_providers,
        giphy_rating_options: page_params.giphy_rating_options,
        giphy_api_key_empty: page_params.giphy_api_key === "",
        realm_description: page_params.realm_description,
        realm_inline_image_preview: page_params.realm_inline_image_preview,
        server_inline_image_preview: page_params.server_inline_image_preview,
        realm_inline_url_embed_preview: page_params.realm_inline_url_embed_preview,
        server_inline_url_embed_preview: page_params.server_inline_url_embed_preview,
        realm_authentication_methods: page_params.realm_authentication_methods,
        realm_user_group_edit_policy: page_params.realm_user_group_edit_policy,
        realm_name_changes_disabled: page_params.realm_name_changes_disabled,
        realm_email_changes_disabled: page_params.realm_email_changes_disabled,
        realm_avatar_changes_disabled: page_params.realm_avatar_changes_disabled,
        realm_add_custom_emoji_policy: page_params.realm_add_custom_emoji_policy,
        can_add_emojis: settings_data.user_can_add_custom_emoji(),
        can_create_new_bots: settings_bots.can_create_new_bots(),
        realm_message_content_edit_limit_minutes: settings_org.get_realm_time_limits_in_minutes(
            "realm_message_content_edit_limit_seconds",
        ),
        realm_message_content_delete_limit_minutes: settings_org.get_realm_time_limits_in_minutes(
            "realm_message_content_delete_limit_seconds",
        ),
        realm_message_retention_days: page_params.realm_message_retention_days,
        realm_allow_edit_history: page_params.realm_allow_edit_history,
        realm_allow_message_editing: page_params.realm_allow_message_editing,
        language_list,
        realm_default_language_name: get_language_name(page_params.realm_default_language),
        realm_default_language_code: page_params.realm_default_language,
        realm_waiting_period_threshold: page_params.realm_waiting_period_threshold,
        realm_notifications_stream_id: page_params.realm_notifications_stream_id,
        realm_signup_notifications_stream_id: page_params.realm_signup_notifications_stream_id,
        is_admin: page_params.is_admin,
        is_guest: page_params.is_guest,
        is_owner: page_params.is_owner,
        user_can_change_logo: settings_data.user_can_change_logo(),
        realm_icon_source: page_params.realm_icon_source,
        realm_icon_url: page_params.realm_icon_url,
        realm_logo_source: page_params.realm_logo_source,
        realm_logo_url: page_params.realm_logo_url,
        realm_night_logo_source: page_params.realm_night_logo_source,
        realm_night_logo_url: page_params.realm_night_logo_url,
        realm_mandatory_topics: page_params.realm_mandatory_topics,
        realm_send_welcome_emails: page_params.realm_send_welcome_emails,
        realm_message_content_allowed_in_email_notifications:
            page_params.realm_message_content_allowed_in_email_notifications,
        realm_enable_spectator_access: page_params.realm_enable_spectator_access,
        settings_send_digest_emails: page_params.settings_send_digest_emails,
        realm_digest_emails_enabled: page_params.realm_digest_emails_enabled,
        realm_digest_weekday: page_params.realm_digest_weekday,
        development: page_params.development_environment,
        zulip_plan_is_not_limited: page_params.zulip_plan_is_not_limited,
        upgrade_text_for_wide_organization_logo:
            page_params.upgrade_text_for_wide_organization_logo,
        realm_default_external_accounts: page_params.realm_default_external_accounts,
        admin_settings_label,
        msg_edit_limit_dropdown_values: settings_config.msg_edit_limit_dropdown_values,
        msg_delete_limit_dropdown_values: settings_config.msg_delete_limit_dropdown_values,
        msg_move_limit_dropdown_values: settings_config.msg_move_limit_dropdown_values,
        bot_creation_policy_values: settings_bots.bot_creation_policy_values,
        email_address_visibility_values: settings_config.email_address_visibility_values,
        waiting_period_threshold_dropdown_values:
            settings_config.waiting_period_threshold_dropdown_values,
        can_create_multiuse_invite: settings_data.user_can_create_multiuse_invite(),
        can_invite_users_by_email: settings_data.user_can_invite_users_by_email(),
        realm_invite_required: page_params.realm_invite_required,
        can_edit_user_groups: settings_data.user_can_edit_user_groups(),
        policy_values: settings_config.common_policy_values,
        realm_delete_own_message_policy: page_params.realm_delete_own_message_policy,
        DELETE_OWN_MESSAGE_POLICY_ADMINS_ONLY:
            settings_config.common_message_policy_values.by_admins_only.code,
        ...settings_org.get_organization_settings_options(),
        demote_inactive_streams_values: settings_config.demote_inactive_streams_values,
        web_mark_read_on_scroll_policy_values:
            settings_config.web_mark_read_on_scroll_policy_values,
        user_list_style_values: settings_config.user_list_style_values,
        web_stream_unreads_count_display_policy_values:
            settings_config.web_stream_unreads_count_display_policy_values,
        color_scheme_values: settings_config.color_scheme_values,
        default_view_values: settings_config.default_view_values,
        settings_object: realm_user_settings_defaults,
        display_settings: settings_config.get_all_display_settings(),
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
        create_web_public_stream_policy_values:
            settings_config.create_web_public_stream_policy_values,
        disable_enable_spectator_access_setting:
            !page_params.server_web_public_streams_enabled ||
            !page_params.zulip_plan_is_not_limited,
        realm_push_notifications_enabled: page_params.realm_push_notifications_enabled,
        realm_org_type_values: settings_org.get_org_type_dropdown_options(),
        realm_want_advertise_in_communities_directory:
            page_params.realm_want_advertise_in_communities_directory,
        disable_want_advertise_in_communities_directory:
            !page_params.realm_push_notifications_enabled,
        is_business_type_org:
            page_params.realm_org_type === settings_config.all_org_type_values.business.code,
        realm_enable_read_receipts: page_params.realm_enable_read_receipts,
        allow_sorting_deactivated_users_list_by_email:
            settings_users.allow_sorting_deactivated_users_list_by_email(),
        has_bots: bot_data.get_all_bots_for_current_user().length > 0,
        user_has_email_set: !settings_data.user_email_not_configured(),
    };

    if (options.realm_logo_source !== "D" && options.realm_night_logo_source === "D") {
        // If no dark theme logo is specified but a light theme one is,
        // use the light theme one.  See also similar code in realm_logo.js.
        options.realm_night_logo_url = options.realm_logo_url;
    }

    options.giphy_help_link = "/help/animated-gifs-from-giphy";
    if (options.giphy_api_key_empty) {
        options.giphy_help_link =
            "https://zulip.readthedocs.io/en/latest/production/giphy-gif-integration.html";
    }

    get_realm_level_notification_settings(options);

    const rendered_admin_tab = render_admin_tab(options);
    $("#settings_content .organization-box").html(rendered_admin_tab);
    $("#settings_content .alert").removeClass("show");

    settings_bots.update_bot_settings_tip($("#admin-bot-settings-tip"), true);
    settings_invites.update_invite_user_panel();
    insert_tip_box();

    $("#id_realm_bot_creation_policy").val(page_params.realm_bot_creation_policy);

    $("#id_realm_digest_weekday").val(options.realm_digest_weekday);
}

export function launch(section) {
    settings_sections.reset_sections();

    settings.open_settings_overlay();
    settings_panel_menu.org_settings.activate_section_or_default(section);
    settings_toggle.highlight_toggle("organization");
}
