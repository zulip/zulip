import $ from "jquery";

import render_admin_tab from "../templates/settings/admin_tab.hbs";
import render_settings_organization_settings_tip from "../templates/settings/organization_settings_tip.hbs";

import {$t, language_list} from "./i18n";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as settings from "./settings";
import * as settings_bots from "./settings_bots";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as settings_emoji from "./settings_emoji";
import * as settings_org from "./settings_org";
import * as settings_panel_menu from "./settings_panel_menu";
import * as settings_sections from "./settings_sections";
import * as settings_toggle from "./settings_toggle";

const admin_settings_label = {
    // Organization settings
    realm_allow_edit_history: $t({defaultMessage: "Enable message edit history"}),
    realm_mandatory_topics: $t({defaultMessage: "Require topics in stream messages"}),
    realm_notifications_stream: $t({defaultMessage: "New stream notifications:"}),
    realm_signup_notifications_stream: $t({defaultMessage: "New user notifications:"}),
    realm_inline_image_preview: $t({defaultMessage: "Show previews of uploaded and linked images"}),
    realm_inline_url_embed_preview: $t({defaultMessage: "Show previews of linked websites"}),
    realm_default_twenty_four_hour_time: $t({defaultMessage: "Time format"}),
    realm_send_welcome_emails: $t({defaultMessage: "Send emails introducing Zulip to new users"}),
    realm_message_content_allowed_in_email_notifications: $t({
        defaultMessage: "Allow message content in message notification emails",
    }),
    realm_digest_emails_enabled: $t({
        defaultMessage: "Send weekly digest emails to inactive users",
    }),
    realm_default_code_block_language: $t({defaultMessage: "Default language for code blocks:"}),

    // Organization permissions
    realm_name_changes_disabled: $t({defaultMessage: "Prevent users from changing their name"}),
    realm_email_changes_disabled: $t({
        defaultMessage: "Prevent users from changing their email address",
    }),
    realm_avatar_changes_disabled: $t({defaultMessage: "Prevent users from changing their avatar"}),
    realm_invite_required: $t({
        defaultMessage: "Invitations are required for joining this organization",
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
        .prepend(tip_box);
}

export function build_page() {
    const options = {
        custom_profile_field_types: page_params.custom_profile_field_types,
        realm_name: page_params.realm_name,
        realm_available_video_chat_providers: page_params.realm_available_video_chat_providers,
        giphy_rating_options: page_params.giphy_rating_options,
        giphy_api_key_empty: page_params.giphy_api_key === "",
        realm_description: page_params.realm_description,
        realm_inline_image_preview: page_params.realm_inline_image_preview,
        server_inline_image_preview: page_params.server_inline_image_preview,
        realm_inline_url_embed_preview: page_params.realm_inline_url_embed_preview,
        server_inline_url_embed_preview: page_params.server_inline_url_embed_preview,
        realm_default_twenty_four_hour_time_values: settings_config.twenty_four_hour_time_values,
        realm_authentication_methods: page_params.realm_authentication_methods,
        realm_user_group_edit_policy: page_params.realm_user_group_edit_policy,
        realm_name_changes_disabled: page_params.realm_name_changes_disabled,
        realm_email_changes_disabled: page_params.realm_email_changes_disabled,
        realm_avatar_changes_disabled: page_params.realm_avatar_changes_disabled,
        realm_add_emoji_by_admins_only: page_params.realm_add_emoji_by_admins_only,
        can_add_emojis: settings_emoji.can_add_emoji(),
        realm_message_content_edit_limit_minutes: settings_org.get_realm_time_limits_in_minutes(
            "realm_message_content_edit_limit_seconds",
        ),
        realm_message_content_delete_limit_minutes: settings_org.get_realm_time_limits_in_minutes(
            "realm_message_content_delete_limit_seconds",
        ),
        realm_message_retention_days: page_params.realm_message_retention_days,
        realm_allow_edit_history: page_params.realm_allow_edit_history,
        language_list,
        realm_default_language: page_params.realm_default_language,
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
        settings_send_digest_emails: page_params.settings_send_digest_emails,
        realm_digest_emails_enabled: page_params.realm_digest_emails_enabled,
        realm_digest_weekday: page_params.realm_digest_weekday,
        show_email: settings_data.show_email(),
        development: page_params.development_environment,
        zulip_plan_is_not_limited: page_params.zulip_plan_is_not_limited,
        upgrade_text_for_wide_organization_logo:
            page_params.upgrade_text_for_wide_organization_logo,
        realm_default_external_accounts: page_params.realm_default_external_accounts,
        admin_settings_label,
        msg_edit_limit_dropdown_values: settings_config.msg_edit_limit_dropdown_values,
        msg_delete_limit_dropdown_values: settings_config.msg_delete_limit_dropdown_values,
        bot_creation_policy_values: settings_bots.bot_creation_policy_values,
        email_address_visibility_values: settings_config.email_address_visibility_values,
        can_invite_others_to_realm: settings_data.user_can_invite_others_to_realm(),
        realm_invite_required: page_params.realm_invite_required,
        can_edit_user_groups: settings_data.user_can_edit_user_groups(),
        policy_values: settings_config.common_policy_values,
        ...settings_org.get_organization_settings_options(),
    };

    if (options.realm_logo_source !== "D" && options.realm_night_logo_source === "D") {
        // If no night mode logo is specified but a day mode one is,
        // use the day mode one.  See also similar code in realm_logo.js.
        options.realm_night_logo_url = options.realm_logo_url;
    }

    options.giphy_help_link = "/help/animated-gifs-from-giphy";
    if (options.giphy_api_key_empty) {
        options.giphy_help_link =
            "https://zulip.readthedocs.io/en/latest/production/giphy-gif-integration.html";
    }

    const rendered_admin_tab = render_admin_tab(options);
    $("#settings_content .organization-box").html(rendered_admin_tab);
    $("#settings_content .alert").removeClass("show");

    settings_bots.update_bot_settings_tip();
    insert_tip_box();

    $("#id_realm_bot_creation_policy").val(page_params.realm_bot_creation_policy);
    $("#id_realm_email_address_visibility").val(page_params.realm_email_address_visibility);

    $("#id_realm_default_language").val(page_params.realm_default_language);
    $("#id_realm_digest_weekday").val(options.realm_digest_weekday);

    // default_twenty_four_hour time is a boolean in the API but a
    // dropdown, so we need to convert the value to a string for
    // storage in the browser's DOM.
    $("#id_realm_default_twenty_four_hour_time").val(
        JSON.stringify(page_params.realm_default_twenty_four_hour_time),
    );
}

export function launch(section) {
    settings.build_page();
    build_page();
    settings_sections.reset_sections();

    overlays.open_settings();
    settings_panel_menu.org_settings.activate_section_or_default(section);
    settings_toggle.highlight_toggle("organization");
}
