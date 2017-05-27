var admin = (function () {

var exports = {};

exports.show_or_hide_menu_item = function () {
    var item = $('.admin-menu-item').expectOne();
    if (page_params.is_admin) {
        item.find("span").text(i18n.t("Manage organization"));
    } else {
        item.find("span").text(i18n.t("Organization settings"));
        $(".organization-box [data-name='organization-settings']")
            .find("input, textarea, button, select").attr("disabled", true);
        $(".organization-box [data-name='organization-permissions']")
            .find("input, textarea, button, select").attr("disabled", true);
        $(".organization-box [data-name='auth-methods']")
            .find("input, button, select, checked").attr("disabled", true);
        $(".organization-box [data-name='default-streams-list']")
            .find("input:not(.search), button, select").attr("disabled", true);
        $(".organization-box [data-name='filter-settings']")
            .find("input, button, select").attr("disabled", true);
        $(".control-label-disabled").css("color", "#333333");
    }
};

function _setup_page() {
    var options = {
        realm_name: page_params.realm_name,
        realm_description: page_params.realm_description,
        realm_restricted_to_domain: page_params.realm_restricted_to_domain,
        realm_invite_required: page_params.realm_invite_required,
        realm_invite_by_admins_only: page_params.realm_invite_by_admins_only,
        realm_inline_image_preview: page_params.realm_inline_image_preview,
        server_inline_image_preview: page_params.server_inline_image_preview,
        realm_inline_url_embed_preview: page_params.realm_inline_url_embed_preview,
        server_inline_url_embed_preview: page_params.server_inline_url_embed_preview,
        realm_authentication_methods: page_params.realm_authentication_methods,
        realm_create_stream_by_admins_only: page_params.realm_create_stream_by_admins_only,
        realm_name_changes_disabled: page_params.realm_name_changes_disabled,
        realm_email_changes_disabled: page_params.realm_email_changes_disabled,
        realm_add_emoji_by_admins_only: page_params.realm_add_emoji_by_admins_only,
        realm_allow_message_editing: page_params.realm_allow_message_editing,
        realm_message_content_edit_limit_minutes:
            Math.ceil(page_params.realm_message_content_edit_limit_seconds / 60),
        realm_message_retention_days: page_params.realm_message_retention_days,
        language_list: page_params.language_list,
        realm_default_language: page_params.realm_default_language,
        realm_waiting_period_threshold: page_params.realm_waiting_period_threshold,
        is_admin: page_params.is_admin,
        realm_icon_source: page_params.realm_icon_source,
        realm_icon_url: page_params.realm_icon_url,
    };

    var admin_tab = templates.render('admin_tab', options);
    $("#settings_content .organization-box").html(admin_tab);
    $("#settings_content .alert").removeClass("show");

    // Since we just swapped in a whole new page, we need to
    // tell admin_sections nothing is loaded.
    admin_sections.reset_sections();

    var tab = (function () {
        var tab = false;
        var hash_sequence = window.location.hash.split(/\//);
        if (/#*(organization)/.test(hash_sequence[0])) {
            tab = hash_sequence[1];
            return tab || "organization-settings";
        }
        return tab;
    }());

    if (tab) {
        exports.launch_page(tab);
    }

    $("#id_realm_default_language").val(page_params.realm_default_language);

    // Do this after calling the setup_up methods, so that we can
    // disable any dynamically rendered elements.
    exports.show_or_hide_menu_item();
}

exports.launch_page = function (tab) {
    var $active_tab = $("#settings_overlay_container li[data-section='" + tab + "']");

    if ($active_tab.hasClass("admin")) {
        $(".sidebar .ind-tab[data-tab-key='organization']").click();
    }

    overlays.open_settings();
    $active_tab.click();
};

exports.setup_page = function () {
    i18n.ensure_i18n(_setup_page);
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = admin;
}
