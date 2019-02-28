var settings_org = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

var org_profile = {
    name: {
        type: 'text',
    },
    description: {
        type: 'text',
    },
};

var org_settings = {
    msg_editing: {
        allow_edit_history: {
            type: 'bool',
        },
        allow_community_topic_editing: {
            type: 'bool',
        },
    },
    other_settings: {
        inline_image_preview: {
            type: 'bool',
        },
        inline_url_embed_preview: {
            type: 'bool',
        },
        mandatory_topics: {
            type: 'bool',
        },
        video_chat_provider: {
            type: 'text',
        },
        google_hangouts_domain: {
            type: 'text',
        },
        zoom_user_id: {
            type: 'text',
        },
        zoom_api_key: {
            type: 'text',
        },
        zoom_api_secret: {
            type: 'text',
        },
        message_content_allowed_in_email_notifications: {
            type: 'bool',
        },
    },
    user_defaults: {
        default_language: {
            type: 'text',
        },
        default_twenty_four_hour_time: {
            type: 'bool',
        },
    },
    notifications: {
        send_welcome_emails: {
            type: 'bool',
        },
    },
};

var org_permissions = {
    user_identity: {
        name_changes_disabled: {
            type: 'bool',
        },
        email_changes_disabled: {
            type: 'bool',
        },
    },
    other_permissions: {
        bot_creation_policy: {
            type: 'integer',
        },
        email_address_visibility: {
            type: 'integer',
        },
    },
};

exports.maybe_disable_widgets = function () {
    if (page_params.is_admin) {
        return;
    }

    $(".organization-box [data-name='organization-profile']")
        .find("input, textarea, button, select").attr("disabled", true);

    $(".organization-box [data-name='organization-settings']")
        .find("input, textarea, button, select").attr("disabled", true);

    $(".organization-box [data-name='organization-settings']")
        .find(".control-label-disabled").addClass('enabled');

    $(".organization-box [data-name='organization-permissions']")
        .find("input, textarea, button, select").attr("disabled", true);

    $(".organization-box [data-name='organization-permissions']")
        .find(".control-label-disabled").addClass('enabled');

    $(".organization-box [data-name='auth-methods']")
        .find("input, button, select, checked").attr("disabled", true);
};

exports.email_address_visibility_values = {
    everyone: {
        code: 1,
        description: i18n.t("Members, admins, and guests"),
    },
    //// Backend support for this configuration is not available yet.
    // admins_and_members: {
    //     code: 2,
    //     description: i18n.t("Members and admins"),
    // },
    admins_only: {
        code: 3,
        description: i18n.t("Admins only"),
    },
};

function get_subsection_property_types(subsection) {
    if (_.has(org_settings, subsection)) {
        return org_settings[subsection];
    } else if (_.has(org_permissions, subsection)) {
        return org_permissions[subsection];
    } else if (subsection === 'org_profile') {
        return org_profile;
    }
    return;
}

exports.get_realm_time_limits_in_minutes = function (property) {
    var val = (page_params[property] / 60).toFixed(1);
    if (parseFloat(val, 10) === parseInt(val, 10)) {
        val = parseInt(val, 10);
    }
    return val.toString();
};

function get_property_value(property_name) {
    var value;

    if (property_name === 'realm_message_content_edit_limit_minutes') {
        return exports.get_realm_time_limits_in_minutes('realm_message_content_edit_limit_seconds');
    }

    if (property_name === 'realm_message_content_delete_limit_minutes') {
        return exports.get_realm_time_limits_in_minutes('realm_message_content_delete_limit_seconds');
    }

    if (property_name === 'realm_create_stream_permission') {
        if (page_params.realm_create_stream_by_admins_only) {
            return "by_admins_only";
        }
        if (page_params.realm_waiting_period_threshold === 0) {
            return "by_anyone";
        }
        if (page_params.realm_waiting_period_threshold === 3) {
            return "by_admin_user_with_three_days_old";
        }
        return "by_admin_user_with_custom_time";
    }

    if (property_name === 'realm_add_emoji_by_admins_only') {
        if (page_params.realm_add_emoji_by_admins_only) {
            return "by_admins_only";
        }
        return "by_anyone";
    }

    if (property_name === 'realm_msg_edit_limit_setting') {
        if (!page_params.realm_allow_message_editing) {
            return "never";
        }
        value = _.findKey(exports.msg_edit_limit_dropdown_values, function (elem) {
            return elem.seconds === page_params.realm_message_content_edit_limit_seconds;
        });
        if (value === undefined) {
            return "custom_limit";
        }
        return value;
    }

    if (property_name === 'realm_msg_delete_limit_setting') {
        if (!page_params.realm_allow_message_deleting) {
            return "never";
        }
        value = _.findKey(exports.msg_delete_limit_dropdown_values, function (elem) {
            return elem.seconds === page_params.realm_message_content_delete_limit_seconds;
        });
        if (value === undefined) {
            return "custom_limit";
        }
        return value;
    }

    if (property_name === 'realm_org_join_restrictions') {
        if (page_params.realm_emails_restricted_to_domains) {
            return "only_selected_domain";
        }
        if (page_params.realm_disallow_disposable_email_addresses) {
            return "no_disposable_email";
        }
        return "no_restriction";
    }

    if (property_name === 'realm_user_invite_restriction') {
        if (!page_params.realm_invite_required) {
            return "no_invite_required";
        }
        if (page_params.realm_invite_by_admins_only) {
            return "by_admins_only";
        }
        return "by_anyone";
    }

    return page_params[property_name];
}

exports.extract_property_name = function (elem) {
    return elem.attr('id').split('-').join('_').replace("id_", "");
};

function set_create_stream_permission_dropdown() {
    var value = get_property_value("realm_create_stream_permission");
    $("#id_realm_create_stream_permission").val(value);
    if (value === "by_admin_user_with_custom_time") {
        $("#id_realm_waiting_period_threshold").parent().show();
    } else {
        $("#id_realm_waiting_period_threshold").parent().hide();
    }
}

function set_add_emoji_permission_dropdown() {
    $("#id_realm_add_emoji_by_admins_only").val(get_property_value("realm_add_emoji_by_admins_only"));
}

function set_video_chat_provider_dropdown() {
    var chat_provider = page_params.realm_video_chat_provider;
    $("#id_realm_video_chat_provider").val(chat_provider);
    if (chat_provider === "Google Hangouts") {
        $("#google_hangouts_domain").show();
        $(".zoom_credentials").hide();
        $("#id_realm_google_hangouts_domain").val(page_params.realm_google_hangouts_domain);
    } else if (chat_provider === "Zoom") {
        $("#google_hangouts_domain").hide();
        $(".zoom_credentials").show();
        $("#id_realm_zoom_user_id").val(page_params.realm_zoom_user_id);
        $("#id_realm_zoom_api_key").val(page_params.realm_zoom_api_key);
        $("#id_realm_zoom_api_secret").val(page_params.realm_zoom_api_secret);
    } else {
        $("#google_hangouts_domain").hide();
        $(".zoom_credentials").hide();
    }
}

var time_limit_dropdown_values = {
    any_time: {
        text: i18n.t("Any time"),
        seconds: 0,
    },
    never: {
        text: i18n.t("Never"),
    },
    upto_two_min: {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("2 minutes")}),
        seconds: 2 * 60,
    },
    upto_ten_min: {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("10 minutes")}),
        seconds: 10 * 60,
    },
    upto_one_hour: {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("1 hour")}),
        seconds: 60 * 60,
    },
    upto_one_day: {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("1 day")}),
        seconds: 24 * 60 * 60,
    },
    upto_one_week: {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("1 week")}),
        seconds: 7 * 24 * 60 * 60,
    },
    custom_limit: {
        text: i18n.t("Up to N minutes after posting"),
    },
};
exports.msg_edit_limit_dropdown_values = time_limit_dropdown_values;
exports.msg_delete_limit_dropdown_values = time_limit_dropdown_values;

function set_msg_edit_limit_dropdown() {
    var value = get_property_value("realm_msg_edit_limit_setting");
    $("#id_realm_msg_edit_limit_setting").val(value);
    if (value === "custom_limit") {
        $("#id_realm_message_content_edit_limit_minutes").parent().show();
    } else {
        $("#id_realm_message_content_edit_limit_minutes").parent().hide();
    }
    settings_ui.disable_sub_setting_onchange(value !== "never",
                                             "id_realm_allow_community_topic_editing", true);
}

function set_msg_delete_limit_dropdown() {
    var value = get_property_value("realm_msg_delete_limit_setting");
    $("#id_realm_msg_delete_limit_setting").val(value);
    if (value === "custom_limit") {
        $("#id_realm_message_content_delete_limit_minutes").parent().show();
    } else {
        $("#id_realm_message_content_delete_limit_minutes").parent().hide();
    }
}

function set_user_invite_restriction_dropdown() {
    $("#id_realm_user_invite_restriction").val(get_property_value("realm_user_invite_restriction"));
}

function set_org_join_restrictions_dropdown() {
    var value = get_property_value("realm_org_join_restrictions");
    $("#id_realm_org_join_restrictions").val(value);
    var node = $("#allowed_domains_label").parent();
    if (value === 'only_selected_domain') {
        node.show();
    } else {
        node.hide();
    }
}

function set_message_content_in_email_notifications_visiblity() {
    if (page_params.realm_message_content_allowed_in_email_notifications) {
        $('#message_content_in_email_notifications_label').parent().show();
    } else {
        $('#message_content_in_email_notifications_label').parent().hide();
    }
}

exports.populate_realm_domains = function (realm_domains) {
    if (!meta.loaded) {
        return;
    }

    var domains_list = _.map(realm_domains, function (realm_domain) {
        return realm_domain.allow_subdomains ? "*." + realm_domain.domain : realm_domain.domain;
    });
    var domains = domains_list.join(', ');
    if (domains.length === 0) {
        domains = i18n.t("None");
    }
    $("#allowed_domains_label").text(i18n.t("Allowed domains: __domains__", {domains: domains}));

    var realm_domains_table_body = $("#realm_domains_table tbody").expectOne();
    realm_domains_table_body.find("tr").remove();
    _.each(realm_domains, function (realm_domain) {
        realm_domains_table_body.append(templates.render("admin-realm-domains-list", {realm_domain: realm_domain}));
    });
};

exports.populate_auth_methods = function (auth_methods) {
    if (!meta.loaded) {
        return;
    }

    var auth_methods_table = $("#admin_auth_methods_table").expectOne();
    auth_methods_table.find('tr.method_row').remove();
    _.each(_.keys(auth_methods).sort(), function (key) {
        auth_methods_table.append(templates.render('admin_auth_methods_list', {
            method: {
                method: key,
                enabled: auth_methods[key],
            },
        }));
    });
    loading.destroy_indicator($('#admin_page_auth_methods_loading_indicator'));
    if (!page_params.is_admin) {
        $(".organization-box [data-name='auth-methods']")
            .find("input, button, select, checked").attr("disabled", true);
        var tip_box = $("<div class='tip'></div>")
            .text(i18n.t("Only organization administrators can edit these settings."));
        // Don't prepend a tip to custom emoji settings page. We handle it separately.
        $(".organization-box").find(".settings-section:not(.can-edit)")
            .not("#emoji-settings")
            .not("#user-groups-admin")
            .prepend(tip_box);
    }
};


exports.render_notifications_stream_ui = function (stream_id, elem) {

    var name = stream_data.maybe_get_stream_name(stream_id);

    if (!name) {
        elem.text(i18n.t("Disabled"));
        elem.addClass("text-warning");
        elem.closest('.input-group').find('.notification-disable').hide();
        return;
    }

    // Happy path
    elem.text('#' + name);
    elem.removeClass('text-warning');
    elem.closest('.input-group').find('.notification-disable').show();
};

exports.populate_notifications_stream_dropdown = function (stream_list) {
    var dropdown_list_body = $("#id_realm_notifications_stream .dropdown-list-body").expectOne();
    var search_input = $("#id_realm_notifications_stream .dropdown-search > input[type=text]");

    list_render.create(dropdown_list_body, stream_list, {
        name: "admin-realm-notifications-stream-dropdown-list",
        modifier: function (item) {
            return templates.render("admin-realm-dropdown-stream-list", { stream: item });
        },
        filter: {
            element: search_input,
            callback: function (item, value) {
                return item.name.toLowerCase().indexOf(value) >= 0;
            },
            onupdate: function () {
                ui.reset_scrollbar(dropdown_list_body);
            },
        },
    }).init();

    ui.set_up_scrollbar(dropdown_list_body);

    $("#id_realm_notifications_stream .dropdown-search").click(function (e) {
        e.stopPropagation();
    });

    $("#id_realm_notifications_stream .dropdown-toggle").click(function () {
        search_input.val("").trigger("input");
    });
};

exports.populate_signup_notifications_stream_dropdown = function (stream_list) {
    var dropdown_list_body = $("#id_realm_signup_notifications_stream .dropdown-list-body").expectOne();
    var search_input = $("#id_realm_signup_notifications_stream .dropdown-search > input[type=text]");

    list_render.create(dropdown_list_body, stream_list, {
        name: "admin-realm-signup-notifications-stream-dropdown-list",
        modifier: function (item) {
            return templates.render("admin-realm-dropdown-stream-list", { stream: item });
        },
        filter: {
            element: search_input,
            callback: function (item, value) {
                return item.name.toLowerCase().indexOf(value) >= 0;
            },
        },
    }).init();

    $("#id_realm_signup_notifications_stream .dropdown-search").click(function (e) {
        e.stopPropagation();
    });

    $("#id_realm_signup_notifications_stream .dropdown-toggle").click(function () {
        search_input.val("").trigger("input");
    });
};

function update_dependent_subsettings(property_name) {
    if (property_name === 'realm_create_stream_permission' || property_name === 'realm_waiting_period_threshold') {
        set_create_stream_permission_dropdown();
    } else if (property_name === 'realm_video_chat_provider' ||
               property_name === 'realm_google_hangouts_domain' ||
               property_name.startsWith('realm_zoom')) {
        set_video_chat_provider_dropdown();
    } else if (property_name === 'realm_msg_edit_limit_setting' ||
               property_name === 'realm_message_content_edit_limit_minutes') {
        set_msg_edit_limit_dropdown();
    } else if (property_name === 'realm_msg_delete_limit_setting' ||
        property_name === 'realm_message_content_delete_limit_minutes') {
        set_msg_delete_limit_dropdown();
    } else if (property_name === 'realm_org_join_restrictions') {
        set_org_join_restrictions_dropdown();
    } else if (property_name === 'realm_user_invite_restriction') {
        set_user_invite_restriction_dropdown();
    } else if (property_name === 'realm_message_content_allowed_in_email_notifications') {
        set_message_content_in_email_notifications_visiblity();
    }
}

function discard_property_element_changes(elem) {
    elem = $(elem);
    var property_name = exports.extract_property_name(elem);
    var property_value = get_property_value(property_name);

    if (typeof property_value === 'boolean') {
        elem.prop('checked', property_value);
    } else if (typeof property_value === 'string' || typeof property_value === 'number') {
        elem.val(property_value);
    } else {
        blueslip.error('Element refers to unknown property ' + property_name);
    }

    update_dependent_subsettings(property_name);
}

exports.sync_realm_settings = function (property) {
    if (!overlays.settings_open()) {
        return;
    }

    if (property === 'message_content_edit_limit_seconds') {
        property = 'message_content_edit_limit_minutes';
    } else if (property === 'create_stream_by_admins_only') {
        property = 'create_stream_permission';
    } else if (property === 'allow_message_editing') {
        property = 'msg_edit_limit_setting';
    } else if (property === 'emails_restricted_to_domains' || property === 'disallow_disposable_email_addresses') {
        property = 'org_join_restrictions';
    } else if (property === 'message_content_delete_limit_seconds') {
        property = 'message_content_delete_limit_minutes';
    } else if (property === 'allow_message_deleting') {
        property = 'msg_delete_limit_setting';
    } else if (property === 'invite_required' || property === 'invite_by_admins_only') {
        property = 'user_invite_restriction';
    }
    var element =  $('#id_realm_' + property);
    if (element.length) {
        discard_property_element_changes(element);
    }
};

exports.change_save_button_state = function ($element, state) {
    var show_hide_element = function (state) {
        if (state === 'show') {
            $element.removeClass('hide').addClass('.show').fadeIn(300);
        } else {
            $element.fadeOut(300);
        }
    };
    var $saveBtn = $element.find('.save-button');
    var $textEl = $saveBtn.find('.icon-button-text');
    if (state !== "saving") {
        $saveBtn.removeClass('saving');
    }
    if (state === "unsaved") {
        $textEl.text(i18n.t("Save changes"));
        $saveBtn.attr("data-status", "unsaved");
        show_hide_element('show');
    } else if (state === "saved") {
        $textEl.text(i18n.t("Save changes"));
        $saveBtn.attr("data-status", "");
        show_hide_element('hide');
    } else if (state === "discarded") {
        $element.removeClass('saving');
        show_hide_element('hide');
    } else if (state === "saving") {
        $saveBtn.addClass('saving');
        $textEl.text(i18n.t("Saving"));
        $saveBtn.attr("data-status", "saving");
        show_hide_element('show');
    } else if (state === "failed") {
        show_hide_element('show');
        $textEl.text(i18n.t("Save changes"));
        $saveBtn.attr("data-status", "failed");
    } else if (state === 'succeeded') {
        show_hide_element('hide');
        $textEl.text(i18n.t("Saved"));
        $saveBtn.attr("data-status", "saved");
    }
};

exports.set_up = function () {
    exports.build_page();
    exports.maybe_disable_widgets();
};

exports.build_page = function () {
    meta.loaded = true;

    loading.make_indicator($('#admin_page_auth_methods_loading_indicator'));

    // Populate notifications stream modal
    if (page_params.is_admin) {
        var streams = stream_data.get_streams_for_settings_page();
        exports.populate_notifications_stream_dropdown(streams);
        exports.populate_signup_notifications_stream_dropdown(streams);
    }
    exports.render_notifications_stream_ui(page_params.realm_notifications_stream_id,
                                           $('#realm_notifications_stream_name'));
    exports.render_notifications_stream_ui(page_params.realm_signup_notifications_stream_id,
                                           $('#realm_signup_notifications_stream_name'));

    // Populate realm domains
    exports.populate_realm_domains(page_params.realm_domains);

    // Populate authentication methods table
    exports.populate_auth_methods(page_params.realm_authentication_methods);

    function populate_data_for_request(data, changing_property_types) {
        _.each(changing_property_types, function (v, k) {
            var field = changing_property_types[k];
            if (field.type === 'bool') {
                data[k] = JSON.stringify($('#id_realm_' + k).prop('checked'));
                return;
            }
            if (field.type === 'text') {
                data[k] = JSON.stringify($('#id_realm_' + k).val().trim());
                return;
            }
            if (field.type === 'integer') {
                data[k] = JSON.stringify(parseInt($("#id_realm_" + k).val().trim(), 10));
            }
        });
        return data;
    }

    set_create_stream_permission_dropdown();
    set_add_emoji_permission_dropdown();
    set_video_chat_provider_dropdown();
    set_msg_edit_limit_dropdown();
    set_msg_delete_limit_dropdown();
    set_org_join_restrictions_dropdown();
    set_user_invite_restriction_dropdown();
    set_message_content_in_email_notifications_visiblity();

    function check_property_changed(elem) {
        elem = $(elem);
        var property_name = exports.extract_property_name(elem);
        var changed_val;
        var current_val = get_property_value(property_name);

        if (typeof current_val === 'boolean') {
            changed_val = elem.prop('checked');
        } else if (typeof current_val === 'string') {
            changed_val = elem.val().trim();
        } else if (typeof current_val === 'number') {
            current_val = current_val.toString();
            changed_val = elem.val().trim();
        } else {
            blueslip.error('Element refers to unknown property ' + property_name);
        }

        return current_val !== changed_val;
    }

    function get_subsection_property_elements(element) {
        var subsection = $(element).closest('.org-subsection-parent');
        return subsection.find("input[id^='id_realm_'], select[id^='id_realm_'], textarea[id^='id_realm_']");
    }

    $('.admin-realm-form').on('change input', 'input, select, textarea', function (e) {
        e.preventDefault();
        e.stopPropagation();

        var subsection = $(e.target).closest('.org-subsection-parent');
        subsection.find('.subsection-failed-status p').hide();
        subsection.find('.save-button').show();
        var properties_elements = get_subsection_property_elements(subsection);
        var show_change_process_button = false;
        _.each(properties_elements, function (elem) {
            if (check_property_changed(elem)) {
                show_change_process_button = true;
            }
        });

        var save_btn_controls = subsection.find('.subsection-header .save-button-controls');
        var button_state = show_change_process_button ? "unsaved" : "saved";
        exports.change_save_button_state(save_btn_controls, button_state);
    });

    $('.organization').on('click', '.subsection-header .subsection-changes-discard .button', function (e) {
        e.preventDefault();
        e.stopPropagation();
        _.each(get_subsection_property_elements(e.target), discard_property_element_changes);
        var save_btn_controls = $(e.target).closest('.save-button-controls');
        exports.change_save_button_state(save_btn_controls, "discarded");
    });

    exports.save_organization_settings = function (data, save_button, success_continuation) {
        var subsection_parent = save_button.closest('.org-subsection-parent');
        var save_btn_container = subsection_parent.find('.save-button-controls');
        var failed_alert_elem = subsection_parent.find('.subsection-failed-status p');
        exports.change_save_button_state(save_btn_container, "saving");
        channel.patch({
            url: "/json/realm",
            data: data,
            success: function (response_data) {
                failed_alert_elem.hide();
                setTimeout(function () {
                    exports.change_save_button_state(save_btn_container, "succeeded");
                }, 500);
                if (success_continuation !== undefined) {
                    success_continuation(response_data);
                }
            },
            error: function (xhr) {
                exports.change_save_button_state(save_btn_container, "failed");
                save_button.hide();
                ui_report.error(i18n.t("Save failed"), xhr, failed_alert_elem);
            },
        });
    };

    function parse_time_limit(elem) {
        return Math.floor(parseFloat(elem.val(), 10).toFixed(1) * 60);
    }
    exports.parse_time_limit = parse_time_limit;

    function get_complete_data_for_subsection(subsection) {
        var opts = {};
        if (subsection === 'msg_editing') {
            var edit_limit_setting_value = $("#id_realm_msg_edit_limit_setting").val();
            opts.data = {};
            if (edit_limit_setting_value === 'never') {
                opts.data.allow_message_editing = false;
            } else if (edit_limit_setting_value === 'custom_limit') {
                opts.data.message_content_edit_limit_seconds = parse_time_limit($('#id_realm_message_content_edit_limit_minutes'));
                // Disable editing if the parsed time limit is 0 seconds
                opts.data.allow_message_editing = !!opts.data.message_content_edit_limit_seconds;
            } else {
                opts.data.allow_message_editing = true;
                opts.data.message_content_edit_limit_seconds =
                    exports.msg_edit_limit_dropdown_values[edit_limit_setting_value].seconds;
            }
            var delete_limit_setting_value = $("#id_realm_msg_delete_limit_setting").val();
            if (delete_limit_setting_value === 'never') {
                opts.data.allow_message_deleting = false;
            } else if (delete_limit_setting_value === 'custom_limit') {
                opts.data.message_content_delete_limit_seconds = parse_time_limit($('#id_realm_message_content_delete_limit_minutes'));
                // Disable deleting if the parsed time limit is 0 seconds
                opts.data.allow_message_deleting = !!opts.data.message_content_delete_limit_seconds;
            } else {
                opts.data.allow_message_deleting = true;
                opts.data.message_content_delete_limit_seconds =
                    exports.msg_delete_limit_dropdown_values[delete_limit_setting_value].seconds;
            }
        } else if (subsection === 'other_permissions') {
            var create_stream_permission = $("#id_realm_create_stream_permission").val();
            var add_emoji_permission = $("#id_realm_add_emoji_by_admins_only").val();
            var new_message_retention_days = $("#id_realm_message_retention_days").val();

            if (parseInt(new_message_retention_days, 10).toString() !== new_message_retention_days
                && new_message_retention_days !== "") {
                new_message_retention_days = "";
            }

            var data = {
                message_retention_days: new_message_retention_days !== "" ?
                    JSON.stringify(parseInt(new_message_retention_days, 10)) : null,
            };

            if (add_emoji_permission === "by_admins_only") {
                data.add_emoji_by_admins_only = true;
            } else if (add_emoji_permission === "by_anyone") {
                data.add_emoji_by_admins_only = false;
            }

            if (create_stream_permission === "by_admins_only") {
                data.create_stream_by_admins_only = true;
            } else if (create_stream_permission === "by_admin_user_with_three_days_old") {
                data.create_stream_by_admins_only = false;
                data.waiting_period_threshold = 3;
            } else if (create_stream_permission === "by_admin_user_with_custom_time") {
                data.create_stream_by_admins_only = false;
                data.waiting_period_threshold = $("#id_realm_waiting_period_threshold").val();
            } else if (create_stream_permission === "by_anyone") {
                data.create_stream_by_admins_only = false;
                data.waiting_period_threshold = 0;
            }
            opts.data = data;
        } else if (subsection === 'org_join') {
            opts.data = {};

            var org_join_restrictions = $('#id_realm_org_join_restrictions').val();
            if (org_join_restrictions === "only_selected_domain") {
                opts.data.emails_restricted_to_domains = true;
                opts.data.disallow_disposable_email_addresses = false;
            } else if (org_join_restrictions === "no_disposable_email") {
                opts.data.emails_restricted_to_domains = false;
                opts.data.disallow_disposable_email_addresses = true;
            } else if (org_join_restrictions === "no_restriction") {
                opts.data.disallow_disposable_email_addresses = false;
                opts.data.emails_restricted_to_domains = false;
            }

            var user_invite_restriction = $('#id_realm_user_invite_restriction').val();
            if (user_invite_restriction === 'no_invite_required') {
                opts.data.invite_required = false;
                opts.data.invite_by_admins_only = false;
            } else if (user_invite_restriction === 'by_admins_only') {
                opts.data.invite_required = true;
                opts.data.invite_by_admins_only = true;
            } else {
                opts.data.invite_required = true;
                opts.data.invite_by_admins_only = false;
            }
        }

        return opts;
    }

    $(".organization").on("click", ".subsection-header .subsection-changes-save .button", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var save_button = $(e.currentTarget);
        var subsection_id = save_button.attr('id').replace("org-submit-", "");
        var subsection = subsection_id.split('-').join('_');

        var data = populate_data_for_request({}, get_subsection_property_types(subsection));
        var opts = get_complete_data_for_subsection(subsection);
        data = _.extend(data, opts.data);
        var success_continuation = opts.success_continuation;

        exports.save_organization_settings(data, save_button, success_continuation);
    });

    $(".org-subsection-parent").on("keydown", "input", function (e) {
        e.stopPropagation();
        if (e.keyCode === 13) {
            e.preventDefault();
            $(e.target).closest('.org-subsection-parent').find('.subsection-changes-save button').click();
        }
    });

    $("#id_realm_msg_edit_limit_setting").change(function (e) {
        var msg_edit_limit_dropdown_value = e.target.value;
        var node = $("#id_realm_message_content_edit_limit_minutes").parent();
        if (msg_edit_limit_dropdown_value === 'custom_limit') {
            node.show();
        } else {
            node.hide();
        }
    });

    $("#id_realm_msg_delete_limit_setting").change(function (e) {
        var msg_delete_limit_dropdown_value = e.target.value;
        var node = $("#id_realm_message_content_delete_limit_minutes").parent();
        if (msg_delete_limit_dropdown_value === 'custom_limit') {
            node.show();
        } else {
            node.hide();
        }
    });

    $("#id_realm_create_stream_permission").change(function () {
        var create_stream_permission = this.value;
        var node = $("#id_realm_waiting_period_threshold").parent();
        if (create_stream_permission === 'by_admin_user_with_custom_time') {
            node.show();
        } else {
            node.hide();
        }
    });

    $("#id_realm_video_chat_provider").change(function (e) {
        var video_chat_provider = e.target.value;
        if (video_chat_provider === "Google Hangouts") {
            $("#google_hangouts_domain").show();
            $(".zoom_credentials").hide();
        } else if (video_chat_provider === "Zoom") {
            $("#google_hangouts_domain").hide();
            $(".zoom_credentials").show();
        } else {
            $("#google_hangouts_domain").hide();
            $(".zoom_credentials").hide();
        }
    });

    $("#id_realm_org_join_restrictions").change(function (e) {
        var org_join_restrictions = e.target.value;
        var node = $("#allowed_domains_label").parent();
        if (org_join_restrictions === 'only_selected_domain') {
            node.show();
            if (_.isEmpty(page_params.realm_domains)) {
                overlays.open_modal('realm_domains_modal');
            }
        } else {
            node.hide();
        }
    });

    $("#id_realm_org_join_restrictions").click(function (e) {
        // This prevents the disappearance of modal when there are
        // no allowed domains otherwise it gets closed due to
        // the click event handler attached to `#settings_overlay_container`
        e.stopPropagation();
    });


    $('#admin_auth_methods_table').change(function () {
        var new_auth_methods = {};
        _.each($("#admin_auth_methods_table").find('tr.method_row'), function (method_row) {
            new_auth_methods[$(method_row).data('method')] = $(method_row).find('input').prop('checked');
        });

        settings_ui.do_settings_change(channel.patch, '/json/realm',
                                       {authentication_methods: JSON.stringify(new_auth_methods)},
                                       $('#admin-realm-authentication-methods-status').expectOne()
        );
    });

    function fade_status_element(elem) {
        setTimeout(function () {
            elem.fadeOut(500);
        }, 1000);
    }

    $("#realm_domains_table").on("click", ".delete_realm_domain", function () {
        var domain = $(this).parents("tr").find(".domain").text();
        var url = "/json/realm/domains/" + domain;
        var realm_domains_info = $(".realm_domains_info");

        channel.del({
            url: url,
            success: function () {
                ui_report.success(i18n.t("Deleted successfully!"), realm_domains_info);
                fade_status_element(realm_domains_info);
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed"), xhr, realm_domains_info);
                fade_status_element(realm_domains_info);
            },
        });
    });

    $("#submit-add-realm-domain").click(function () {
        var realm_domains_info = $(".realm_domains_info");
        var widget = $("#add-realm-domain-widget");
        var domain = widget.find(".new-realm-domain").val();
        var allow_subdomains = widget.find(".new-realm-domain-allow-subdomains").prop("checked");
        var data = {
            domain: JSON.stringify(domain),
            allow_subdomains: JSON.stringify(allow_subdomains),
        };

        channel.post({
            url: "/json/realm/domains",
            data: data,
            success: function () {
                $("#add-realm-domain-widget .new-realm-domain").val("");
                $("#add-realm-domain-widget .new-realm-domain-allow-subdomains").prop("checked", false);
                ui_report.success(i18n.t("Added successfully!"), realm_domains_info);
                fade_status_element(realm_domains_info);
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed"), xhr, realm_domains_info);
                fade_status_element(realm_domains_info);
            },
        });
    });

    $("#realm_domains_table").on("change", ".allow-subdomains", function (e) {
        e.stopPropagation();
        var realm_domains_info = $(".realm_domains_info");
        var domain = $(this).parents("tr").find(".domain").text();
        var allow_subdomains = $(this).prop('checked');
        var url = '/json/realm/domains/' + domain;
        var data = {
            allow_subdomains: JSON.stringify(allow_subdomains),
        };

        channel.patch({
            url: url,
            data: data,
            success: function () {
                if (allow_subdomains) {
                    ui_report.success(i18n.t("Update successful: Subdomains allowed for __domain__",
                                             {domain: domain}), realm_domains_info);
                } else {
                    ui_report.success(i18n.t("Update successful: Subdomains no longer allowed for __domain__",
                                             {domain: domain}), realm_domains_info);
                }
                fade_status_element(realm_domains_info);
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed"), xhr, realm_domains_info);
                fade_status_element(realm_domains_info);
            },
        });
    });

    var notifications_stream_status = $("#admin-realm-notifications-stream-status").expectOne();
    function update_notifications_stream(new_notifications_stream_id) {
        exports.render_notifications_stream_ui(new_notifications_stream_id,
                                               $('#realm_notifications_stream_name'));
        notifications_stream_status.hide();

        var url = "/json/realm";
        var data = {
            notifications_stream_id: JSON.stringify(parseInt(new_notifications_stream_id, 10)),
        };

        channel.patch({
            url: url,
            data: data,

            success: function (response_data) {
                if (response_data.notifications_stream_id !== undefined) {
                    if (response_data.notifications_stream_id < 0) {
                        ui_report.success(i18n.t("Notifications stream disabled!"), notifications_stream_status);
                    } else {
                        ui_report.success(i18n.t("Notifications stream changed!"), notifications_stream_status);
                    }
                }
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed to change notifications stream!"), xhr, notifications_stream_status);
            },
        });
    }

    var dropdown_menu = $("#id_realm_notifications_stream .dropdown-menu");
    $("#id_realm_notifications_stream .dropdown-list-body").on("click keypress", ".stream_name", function (e) {
        if (e.type === "keypress") {
            if (e.which === 13) {
                dropdown_menu.dropdown("toggle");
            } else {
                return;
            }
        }

        update_notifications_stream($(this).attr("data-stream-id"));
    });

    $(".notifications-stream-disable").click(function () {
        update_notifications_stream(-1);
    });

    var signup_notifications_stream_status = $("#admin-realm-signup-notifications-stream-status").expectOne();
    function update_signup_notifications_stream(new_signup_notifications_stream_id) {
        exports.render_notifications_stream_ui(new_signup_notifications_stream_id,
                                               $('#realm_signup_notifications_stream_name'));
        signup_notifications_stream_status.hide();
        var stringified_id = JSON.stringify(parseInt(new_signup_notifications_stream_id, 10));
        var url = "/json/realm";
        var data = {
            signup_notifications_stream_id: stringified_id,
        };

        channel.patch({
            url: url,
            data: data,

            success: function (response_data) {
                if (response_data.signup_notifications_stream_id !== undefined) {
                    if (response_data.signup_notifications_stream_id < 0) {
                        ui_report.success(i18n.t("Signup notifications stream disabled!"), signup_notifications_stream_status);
                    } else {
                        ui_report.success(i18n.t("Signup notifications stream changed!"), signup_notifications_stream_status);
                    }
                }
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed to change signup notifications stream!"), xhr, signup_notifications_stream_status);
            },
        });
    }

    dropdown_menu = $("#id_realm_signup_notifications_stream .dropdown-menu");
    $("#id_realm_signup_notifications_stream .dropdown-list-body").on("click keypress", ".stream_name", function (e) {
        if (e.type === "keypress") {
            if (e.which === 13) {
                dropdown_menu.dropdown("toggle");
            } else {
                return;
            }
        }

        update_signup_notifications_stream($(this).attr("data-stream-id"));
    });

    $(".signup-notifications-stream-disable").click(function () {
        update_signup_notifications_stream(-1);
    });

    function upload_realm_icon(file_input) {
        var form_data = new FormData();

        form_data.append('csrfmiddlewaretoken', csrf_token);
        jQuery.each(file_input[0].files, function (i, file) {
            form_data.append('file-' + i, file);
        });

        var error_field = $("#realm_icon_file_input_error");
        error_field.hide();
        var spinner = $("#upload_icon_spinner").expectOne();
        loading.make_indicator(spinner, {text: i18n.t("Uploading icon.")});
        $("#upload_icon_button_text").expectOne().hide();

        channel.post({
            url: '/json/realm/icon',
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success: function () {
                loading.destroy_indicator($("#upload_icon_spinner"));
                $("#upload_icon_button_text").expectOne().show();
            },
            error: function (xhr) {
                loading.destroy_indicator($("#upload_icon_spinner"));
                $("#upload_icon_button_text").expectOne().show();
                ui_report.error("", xhr, error_field);
            },
        });

    }
    realm_icon.build_realm_icon_widget(upload_realm_icon);

    function upload_realm_logo(file_input, night) {
        var form_data = new FormData();
        var spinner;
        var error_field;
        var button_text;

        form_data.append('csrfmiddlewaretoken', csrf_token);
        jQuery.each(file_input[0].files, function (i, file) {
            form_data.append('file-' + i, file);
        });
        if (night) {
            error_field = $("#realm_night_logo_file_input_error");
            spinner = $("#upload_night_logo_spinner");
            button_text = $("#upload_night_logo_button_text");
        } else {
            error_field = $("#realm_logo_file_input_error");
            spinner = $("#upload_logo_spinner");
            button_text = $("#upload_logo_button_text");
        }
        spinner.expectOne();
        error_field.hide();
        button_text.expectOne().hide();
        loading.make_indicator(spinner, {text: i18n.t("Uploading logo.")});
        form_data.append('night', JSON.stringify(night));
        channel.post({
            url: '/json/realm/logo',
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success: function () {
                loading.destroy_indicator(spinner);
                button_text.expectOne().show();
            },
            error: function (xhr) {
                loading.destroy_indicator(spinner);
                button_text.expectOne().show();
                ui_report.error("", xhr, error_field);
            },
        });

    }
    realm_logo.build_realm_night_logo_widget(upload_realm_logo);
    realm_logo.build_realm_logo_widget(upload_realm_logo);

    $('#deactivate_realm_button').on('click', function (e) {
        if (!overlays.is_modal_open()) {
            e.preventDefault();
            e.stopPropagation();
            overlays.open_modal('deactivate-realm-modal');
        }
    });

    $('#do_deactivate_realm_button').on('click', function () {
        if (overlays.is_modal_open()) {
            overlays.close_modal('deactivate-realm-modal');
        }
        channel.post({
            url: '/json/realm/deactivate',
            error: function (xhr) {
                ui_report.error(
                    i18n.t("Failed"), xhr, $('#admin-realm-deactivation-status').expectOne()
                );
            },
        });
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_org;
}
window.settings_org = settings_org;
