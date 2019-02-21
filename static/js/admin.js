var admin = (function () {

var exports = {};

var admin_settings_label = {
    // Organization settings
    realm_allow_community_topic_editing: i18n.t("Users can edit the topic of any message"),
    realm_allow_edit_history: i18n.t("Enable message edit history"),
    realm_mandatory_topics: i18n.t("Require topics in stream messages"),
    realm_inline_image_preview: i18n.t("Show previews of uploaded and linked images"),
    realm_inline_url_embed_preview: i18n.t("Show previews of linked websites"),
    realm_default_twenty_four_hour_time: i18n.t("24-hour time (17:00 instead of 5:00 PM)"),
    realm_send_welcome_emails: i18n.t("Send emails introducing Zulip to new users"),
    realm_message_content_allowed_in_email_notifications:
        i18n.t("Allow message content in missed message emails"),

    // Organization permissions
    realm_name_changes_disabled: i18n.t("Prevent users from changing their name"),
    realm_email_changes_disabled: i18n.t("Prevent users from changing their email address"),
};

exports.build_page = function () {
    var options = {
        custom_profile_field_types: page_params.custom_profile_field_types,
        realm_name: page_params.realm_name,
        realm_available_video_chat_providers: page_params.realm_available_video_chat_providers,
        realm_description: page_params.realm_description,
        realm_inline_image_preview: page_params.realm_inline_image_preview,
        server_inline_image_preview: page_params.server_inline_image_preview,
        realm_inline_url_embed_preview: page_params.realm_inline_url_embed_preview,
        server_inline_url_embed_preview: page_params.server_inline_url_embed_preview,
        realm_authentication_methods: page_params.realm_authentication_methods,
        realm_create_stream_by_admins_only: page_params.realm_create_stream_by_admins_only,
        realm_name_changes_disabled: page_params.realm_name_changes_disabled,
        realm_email_changes_disabled: page_params.realm_email_changes_disabled,
        realm_add_emoji_by_admins_only: page_params.realm_add_emoji_by_admins_only,
        can_add_emojis: settings_emoji.can_add_emoji(),
        realm_allow_community_topic_editing: page_params.realm_allow_community_topic_editing,
        realm_message_content_edit_limit_minutes:
            settings_org.get_realm_time_limits_in_minutes('realm_message_content_edit_limit_seconds'),
        realm_message_content_delete_limit_minutes:
            settings_org.get_realm_time_limits_in_minutes('realm_message_content_delete_limit_seconds'),
        realm_message_retention_days: page_params.realm_message_retention_days,
        realm_allow_edit_history: page_params.realm_allow_edit_history,
        language_list: page_params.language_list,
        realm_default_language: page_params.realm_default_language,
        realm_waiting_period_threshold: page_params.realm_waiting_period_threshold,
        realm_notifications_stream_id: page_params.realm_notifications_stream_id,
        realm_signup_notifications_stream_id: page_params.realm_signup_notifications_stream_id,
        is_admin: page_params.is_admin,
        is_guest: page_params.is_guest,
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
        realm_default_twenty_four_hour_time: page_params.realm_default_twenty_four_hour_time,
        development: page_params.development_environment,
    };

    options.admin_settings_label = admin_settings_label;
    options.msg_edit_limit_dropdown_values = settings_org.msg_edit_limit_dropdown_values;
    options.msg_delete_limit_dropdown_values = settings_org.msg_delete_limit_dropdown_values;
    options.bot_creation_policy_values = settings_bots.bot_creation_policy_values;
    options.email_address_visibility_values = settings_org.email_address_visibility_values;

    if (options.realm_logo_source !== 'D' && options.realm_night_logo_source === 'D') {
        // If no night mode logo is specified but a day mode one is,
        // use the day mode one.  See also similar code in realm_logo.js.
        options.realm_night_logo_url = options.realm_logo_url;
    }

    var rendered_admin_tab = templates.render('admin_tab', options);
    $("#settings_content .organization-box").html(rendered_admin_tab);
    $("#settings_content .alert").removeClass("show");

    settings_bots.update_bot_settings_tip();
    $("#id_realm_bot_creation_policy").val(page_params.realm_bot_creation_policy);
    $("#id_realm_email_address_visibility").val(page_params.realm_email_address_visibility);

    $("#id_realm_default_language").val(page_params.realm_default_language);
};


exports.launch = function (section) {
    settings.build_page();
    exports.build_page();
    settings_sections.reset_sections();

    overlays.open_settings();
    settings_panel_menu.org_settings.activate_section(section);
    settings_toggle.highlight_toggle('organization');
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = admin;
}
window.admin = admin;
