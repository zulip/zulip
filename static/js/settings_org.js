const settings_config = require("./settings_config");
const render_settings_admin_auth_methods_list = require('../templates/settings/admin_auth_methods_list.hbs');
const render_settings_admin_realm_domains_list = require("../templates/settings/admin_realm_domains_list.hbs");
const render_settings_admin_realm_dropdown_stream_list = require("../templates/settings/admin_realm_dropdown_stream_list.hbs");
const render_settings_organization_settings_tip = require("../templates/settings/organization_settings_tip.hbs");

const meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
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

exports.private_message_policy_values = {
    by_anyone: {
        order: 1,
        code: 1,
        description: i18n.t("Admins, members, and guests"),
    },
    disabled: {
        order: 2,
        code: 2,
        description: i18n.t("Private messages disabled"),
    },
};

exports.get_sorted_options_list = function (option_values_object) {
    const options_list = Object.keys(option_values_object).map((key) => {
        return _.extend(option_values_object[key], {key: key});
    });
    let comparator = (x, y) => x.order - y.order;
    if (!options_list[0].order) {
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
    }
    options_list.sort(comparator);
    return options_list;
};

exports.get_organization_settings_options = () => {
    const options = {};
    options.create_stream_policy_values = exports.get_sorted_options_list(
        settings_config.create_stream_policy_values);
    options.invite_to_stream_policy_values = exports.get_sorted_options_list(
        settings_config.invite_to_stream_policy_values);
    options.user_group_edit_policy_values = exports.get_sorted_options_list(
        settings_config.user_group_edit_policy_values);
    options.private_message_policy_values = exports.get_sorted_options_list(
        exports.private_message_policy_values);
    return options;
};

exports.show_email = function () {
    // TODO: Extend this when we add support for admins_and_members above.
    if (page_params.realm_email_address_visibility ===
        settings_config.email_address_visibility_values.everyone.code) {
        return true;
    }
    if (page_params.realm_email_address_visibility ===
        settings_config.email_address_visibility_values.admins_only.code) {
        return page_params.is_admin;
    }
};

exports.get_realm_time_limits_in_minutes = function (property) {
    let val = (page_params[property] / 60).toFixed(1);
    if (parseFloat(val, 10) === parseInt(val, 10)) {
        val = parseInt(val, 10);
    }
    return val.toString();
};

function get_property_value(property_name) {
    let value;

    if (property_name === 'realm_message_content_edit_limit_minutes') {
        return exports.get_realm_time_limits_in_minutes('realm_message_content_edit_limit_seconds');
    }

    if (property_name === 'realm_message_content_delete_limit_minutes') {
        return exports.get_realm_time_limits_in_minutes('realm_message_content_delete_limit_seconds');
    }

    if (property_name === 'realm_waiting_period_setting') {
        if (page_params.realm_waiting_period_threshold === 0) {
            return "none";
        }
        if (page_params.realm_waiting_period_threshold === 3) {
            return "three_days";
        }
        return "custom_days";
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

    if (property_name === 'realm_default_twenty_four_hour_time') {
        return JSON.stringify(page_params[property_name]);
    }

    if (property_name === 'realm_notifications_stream') {
        return page_params.realm_notifications_stream_id;
    }

    if (property_name === 'realm_signup_notifications_stream') {
        return page_params.realm_signup_notifications_stream_id;
    }

    return page_params[property_name];
}

exports.extract_property_name = function (elem) {
    return elem.attr('id').split('-').join('_').replace("id_", "");
};

function get_subsection_property_elements(element) {
    const subsection = $(element).closest('.org-subsection-parent');
    return Array.from(subsection.find('.prop-element'));
}

const simple_dropdown_properties = ['realm_create_stream_policy',
                                    'realm_invite_to_stream_policy',
                                    'realm_user_group_edit_policy',
                                    'realm_private_message_policy',
                                    'realm_add_emoji_by_admins_only',
                                    'realm_user_invite_restriction'];

function set_property_dropdown_value(property_name) {
    $('#id_' + property_name).val(get_property_value(property_name));
}

function change_element_block_display_property(elem_id, show_element) {
    const elem = $("#" + elem_id);
    if (show_element) {
        elem.parent().show();
    } else {
        elem.parent().hide();
    }
}

function set_realm_waiting_period_dropdown() {
    const value = get_property_value("realm_waiting_period_setting");
    $("#id_realm_waiting_period_setting").val(value);
    change_element_block_display_property('id_realm_waiting_period_threshold',
                                          value === "custom_days");
}

function set_video_chat_provider_dropdown() {
    const chat_provider_id = page_params.realm_video_chat_provider;
    const available_providers = page_params.realm_available_video_chat_providers;

    $("#id_realm_video_chat_provider").val(chat_provider_id);
    if (chat_provider_id === available_providers.google_hangouts.id) {
        $("#google_hangouts_domain").show();
        $(".zoom_credentials").hide();
        $("#id_realm_google_hangouts_domain").val(page_params.realm_google_hangouts_domain);
    } else if (chat_provider_id === available_providers.zoom.id) {
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

const time_limit_dropdown_values = {
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
    const value = get_property_value("realm_msg_edit_limit_setting");
    $("#id_realm_msg_edit_limit_setting").val(value);
    change_element_block_display_property('id_realm_message_content_edit_limit_minutes',
                                          value === "custom_limit");
    settings_ui.disable_sub_setting_onchange(value !== "never",
                                             "id_realm_allow_community_topic_editing", true);
}

function set_msg_delete_limit_dropdown() {
    const value = get_property_value("realm_msg_delete_limit_setting");
    $("#id_realm_msg_delete_limit_setting").val(value);
    change_element_block_display_property('id_realm_message_content_delete_limit_minutes',
                                          value === "custom_limit");
}

function set_org_join_restrictions_dropdown() {
    const value = get_property_value("realm_org_join_restrictions");
    $("#id_realm_org_join_restrictions").val(value);
    change_element_block_display_property('allowed_domains_label',
                                          value === 'only_selected_domain');
}

function set_message_content_in_email_notifications_visiblity() {
    change_element_block_display_property(
        'message_content_in_email_notifications_label',
        page_params.realm_message_content_allowed_in_email_notifications);
}

function set_digest_emails_weekday_visibility() {
    change_element_block_display_property('id_realm_digest_weekday',
                                          page_params.realm_digest_emails_enabled);
}

exports.populate_realm_domains = function (realm_domains) {
    if (!meta.loaded) {
        return;
    }

    const domains_list = realm_domains.map(
        realm_domain => realm_domain.allow_subdomains ? "*." + realm_domain.domain : realm_domain.domain
    );
    let domains = domains_list.join(', ');
    if (domains.length === 0) {
        domains = i18n.t("None");
    }
    $("#allowed_domains_label").text(i18n.t("Allowed domains: __domains__", {domains: domains}));

    const realm_domains_table_body = $("#realm_domains_table tbody").expectOne();
    realm_domains_table_body.find("tr").remove();

    for (const realm_domain of realm_domains) {
        realm_domains_table_body.append(
            render_settings_admin_realm_domains_list({
                realm_domain: realm_domain,
            })
        );
    }
};
function sort_object_by_key(obj) {
    const keys = Object.keys(obj).sort();
    const new_obj = {};

    for (const key of keys) {
        new_obj[key] = obj[key];
    }

    return new_obj;
}
exports.populate_auth_methods = function (auth_methods) {
    if (!meta.loaded) {
        return;
    }
    const auth_methods_table = $("#id_realm_authentication_methods").expectOne();
    auth_methods = sort_object_by_key(auth_methods);
    let rendered_auth_method_rows = "";
    for (const [auth_method, value] of Object.entries(auth_methods)) {
        rendered_auth_method_rows += render_settings_admin_auth_methods_list({
            method: auth_method,
            enabled: value,
            is_admin: page_params.is_admin,
        });
    }
    auth_methods_table.html(rendered_auth_method_rows);
};

function insert_tip_box() {
    if (page_params.is_admin) {
        return;
    }
    const tip_box = render_settings_organization_settings_tip({is_admin: page_params.is_admin});
    $(".organization-box").find(".settings-section:not(.can-edit)")
        .not("#emoji-settings")
        .not("#user-groups-admin")
        .prepend(tip_box);
}

exports.render_notifications_stream_ui = function (stream_id, notification_type) {
    const name = stream_data.maybe_get_stream_name(stream_id);

    $(`#id_realm_${notification_type}_stream`).data("stream-id", stream_id);

    const elem = $(`#realm_${notification_type}_stream_name`);

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
    const dropdown_list_body = $("#id_realm_notifications_stream .dropdown-list-body").expectOne();
    const search_input = $("#id_realm_notifications_stream .dropdown-search > input[type=text]");

    list_render.create(dropdown_list_body, stream_list, {
        name: "admin-realm-notifications-stream-dropdown-list",
        modifier: function (item) {
            return render_settings_admin_realm_dropdown_stream_list({ stream: item });
        },
        filter: {
            element: search_input,
            predicate: function (item, value) {
                return item.name.toLowerCase().includes(value);
            },
            onupdate: function () {
                ui.reset_scrollbar(dropdown_list_body);
            },
        },
    }).init();

    $("#id_realm_notifications_stream .dropdown-search").click(function (e) {
        e.stopPropagation();
    });

    $("#id_realm_notifications_stream .dropdown-toggle").click(function () {
        search_input.val("").trigger("input");
    });
};

exports.populate_signup_notifications_stream_dropdown = function (stream_list) {
    const dropdown_list_body = $("#id_realm_signup_notifications_stream .dropdown-list-body").expectOne();
    const search_input = $("#id_realm_signup_notifications_stream .dropdown-search > input[type=text]");

    list_render.create(dropdown_list_body, stream_list, {
        name: "admin-realm-signup-notifications-stream-dropdown-list",
        modifier: function (item) {
            return render_settings_admin_realm_dropdown_stream_list({ stream: item });
        },
        filter: {
            element: search_input,
            predicate: function (item, value) {
                return item.name.toLowerCase().includes(value);
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
    if (simple_dropdown_properties.includes(property_name)) {
        set_property_dropdown_value(property_name);
    } else if (property_name === 'realm_waiting_period_threshold') {
        set_realm_waiting_period_dropdown();
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
    } else if (property_name === 'realm_message_content_allowed_in_email_notifications') {
        set_message_content_in_email_notifications_visiblity();
    } else if (property_name === 'realm_digest_emails_enabled') {
        settings_notifications.set_enable_digest_emails_visibility();
        set_digest_emails_weekday_visibility();
    }
}

function discard_property_element_changes(elem) {
    elem = $(elem);
    const property_name = exports.extract_property_name(elem);
    const property_value = get_property_value(property_name);

    if (property_name === 'realm_authentication_methods') {
        exports.populate_auth_methods(property_value);
    } else if (property_name === 'realm_notifications_stream') {
        exports.render_notifications_stream_ui(property_value, "notifications");
    } else if (property_name === 'realm_signup_notifications_stream') {
        exports.render_notifications_stream_ui(property_value, "signup_notifications");
    } else if (typeof property_value === 'boolean') {
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
    const element =  $('#id_realm_' + property);
    if (element.length) {
        discard_property_element_changes(element);
    }
};


exports.change_save_button_state = function ($element, state) {
    function show_hide_element($element, show, fadeout_delay) {
        if (show) {
            $element.removeClass('hide').addClass('.show').fadeIn(300);
            return;
        }
        setTimeout(function () {
            $element.fadeOut(300);
        }, fadeout_delay);
    }

    const $saveBtn = $element.find('.save-button');
    const $textEl = $saveBtn.find('.icon-button-text');

    if (state !== "saving") {
        $saveBtn.removeClass('saving');
    }

    if (state === "discarded") {
        show_hide_element($element, false, 0);
        return;
    }

    let button_text;
    let data_status;
    let is_show;
    if (state === "unsaved") {
        button_text = i18n.t("Save changes");
        data_status = "unsaved";
        is_show = true;

        $element.find('.discard-button').show();
    } else if (state === "saved") {
        button_text = i18n.t("Save changes");
        data_status = "";
        is_show = false;
    } else if (state === "saving") {
        button_text = i18n.t("Saving");
        data_status = "saving";
        is_show = true;

        $element.find('.discard-button').hide();
        $saveBtn.addClass('saving');
    } else if (state === "failed") {
        button_text = i18n.t("Save changes");
        data_status = "failed";
        is_show = true;
    } else if (state === 'succeeded') {
        button_text = i18n.t("Saved");
        data_status = "saved";
        is_show = false;
    }

    $textEl.text(button_text);
    $saveBtn.attr("data-status", data_status);
    show_hide_element($element, is_show, 800);
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
        const streams = stream_data.get_streams_for_settings_page();
        exports.populate_notifications_stream_dropdown(streams);
        exports.populate_signup_notifications_stream_dropdown(streams);
    }
    exports.render_notifications_stream_ui(page_params.realm_notifications_stream_id, 'notifications');
    exports.render_notifications_stream_ui(page_params.realm_signup_notifications_stream_id, 'signup_notifications');

    // Populate realm domains
    exports.populate_realm_domains(page_params.realm_domains);

    // Populate authentication methods table
    exports.populate_auth_methods(page_params.realm_authentication_methods);
    insert_tip_box();

    simple_dropdown_properties.forEach(set_property_dropdown_value);

    set_realm_waiting_period_dropdown();
    set_video_chat_provider_dropdown();
    set_msg_edit_limit_dropdown();
    set_msg_delete_limit_dropdown();
    set_org_join_restrictions_dropdown();
    set_message_content_in_email_notifications_visiblity();
    set_digest_emails_weekday_visibility();

    function get_auth_method_table_data() {
        const new_auth_methods = {};
        const auth_method_rows = $("#id_realm_authentication_methods").find('tr.method_row');

        for (const method_row of auth_method_rows) {
            new_auth_methods[$(method_row).data('method')] = $(method_row).find('input').prop('checked');
        }

        return new_auth_methods;
    }

    function check_property_changed(elem) {
        elem = $(elem);
        const property_name = exports.extract_property_name(elem);
        let changed_val;
        let current_val = get_property_value(property_name);

        if (property_name === 'realm_authentication_methods') {
            current_val = sort_object_by_key(current_val);
            current_val = JSON.stringify(current_val);
            changed_val = get_auth_method_table_data();
            changed_val = JSON.stringify(changed_val);
        } else if (property_name === 'realm_notifications_stream') {
            changed_val = parseInt($("#id_realm_notifications_stream").data('stream-id'), 10);
        } else if (property_name === 'realm_signup_notifications_stream') {
            changed_val = parseInt($("#id_realm_signup_notifications_stream").data('stream-id'), 10);
        } else if (typeof current_val === 'boolean') {
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

    function save_discard_widget_status_handler(subsection) {
        subsection.find('.subsection-failed-status p').hide();
        subsection.find('.save-button').show();
        const properties_elements = get_subsection_property_elements(subsection);
        const show_change_process_button = properties_elements.some(check_property_changed);

        const save_btn_controls = subsection.find('.subsection-header .save-button-controls');
        const button_state = show_change_process_button ? "unsaved" : "discarded";
        exports.change_save_button_state(save_btn_controls, button_state);
    }

    $('.admin-realm-form').on('change input', 'input, select, textarea', function (e) {
        e.preventDefault();
        e.stopPropagation();

        // This event handler detects whether after these input
        // changes, any fields have different values from the current
        // official values stored in the database and page_params.  If
        // they do, we transition to the "unsaved" state showing the
        // save/discard widget; otherwise, we hide that widget (the
        // "discarded" state).

        if ($(e.target).hasClass("no-input-change-detection")) {
            // This is to prevent input changes detection in elements
            // within a subsection whose changes should not affect the
            // visibility of the discard button
            return false;
        }

        const subsection = $(e.target).closest('.org-subsection-parent');
        save_discard_widget_status_handler(subsection);
    });

    $('.organization').on('click', '.subsection-header .subsection-changes-discard .button', function (e) {
        e.preventDefault();
        e.stopPropagation();
        get_subsection_property_elements(e.target).forEach(discard_property_element_changes);
        const save_btn_controls = $(e.target).closest('.save-button-controls');
        exports.change_save_button_state(save_btn_controls, "discarded");
    });

    exports.save_organization_settings = function (data, save_button) {
        const subsection_parent = save_button.closest('.org-subsection-parent');
        const save_btn_container = subsection_parent.find('.save-button-controls');
        const failed_alert_elem = subsection_parent.find('.subsection-failed-status p');
        exports.change_save_button_state(save_btn_container, "saving");
        channel.patch({
            url: "/json/realm",
            data: data,
            success: function () {
                failed_alert_elem.hide();
                exports.change_save_button_state(save_btn_container, "succeeded");
            },
            error: function (xhr) {
                exports.change_save_button_state(save_btn_container, "failed");
                save_button.hide();
                ui_report.error(i18n.t("Save failed"), xhr, failed_alert_elem);
            },
        });
    };

    exports.parse_time_limit = function parse_time_limit(elem) {
        return Math.floor(parseFloat(elem.val(), 10).toFixed(1) * 60);
    };

    function get_complete_data_for_subsection(subsection) {
        let data = {};
        if (subsection === 'msg_editing') {
            const edit_limit_setting_value = $("#id_realm_msg_edit_limit_setting").val();
            if (edit_limit_setting_value === 'never') {
                data.allow_message_editing = false;
            } else if (edit_limit_setting_value === 'custom_limit') {
                data.message_content_edit_limit_seconds = exports.parse_time_limit($('#id_realm_message_content_edit_limit_minutes'));
                // Disable editing if the parsed time limit is 0 seconds
                data.allow_message_editing = !!data.message_content_edit_limit_seconds;
            } else {
                data.allow_message_editing = true;
                data.message_content_edit_limit_seconds =
                    exports.msg_edit_limit_dropdown_values[edit_limit_setting_value].seconds;
            }
            const delete_limit_setting_value = $("#id_realm_msg_delete_limit_setting").val();
            if (delete_limit_setting_value === 'never') {
                data.allow_message_deleting = false;
            } else if (delete_limit_setting_value === 'custom_limit') {
                data.message_content_delete_limit_seconds = exports.parse_time_limit($('#id_realm_message_content_delete_limit_minutes'));
                // Disable deleting if the parsed time limit is 0 seconds
                data.allow_message_deleting = !!data.message_content_delete_limit_seconds;
            } else {
                data.allow_message_deleting = true;
                data.message_content_delete_limit_seconds =
                    exports.msg_delete_limit_dropdown_values[delete_limit_setting_value].seconds;
            }
        } else if (subsection === 'notifications') {
            data.notifications_stream_id = JSON.stringify(
                parseInt($('#id_realm_notifications_stream').data('stream-id'), 10));
            data.signup_notifications_stream_id = JSON.stringify(
                parseInt($('#id_realm_signup_notifications_stream').data('stream-id'), 10));
        } else if (subsection === 'other_settings') {
            let new_message_retention_days = $("#id_realm_message_retention_days").val();

            if (parseInt(new_message_retention_days, 10).toString() !== new_message_retention_days
                && new_message_retention_days !== "") {
                new_message_retention_days = "";
            }

            data.message_retention_days = new_message_retention_days !== "" ?
                JSON.stringify(parseInt(new_message_retention_days, 10)) : null;
        } else if (subsection === 'other_permissions') {
            const waiting_period_threshold = $("#id_realm_waiting_period_setting").val();
            const add_emoji_permission = $("#id_realm_add_emoji_by_admins_only").val();

            if (add_emoji_permission === "by_admins_only") {
                data.add_emoji_by_admins_only = true;
            } else if (add_emoji_permission === "by_anyone") {
                data.add_emoji_by_admins_only = false;
            }

            if (waiting_period_threshold === "none") {
                data.waiting_period_threshold = 0;
            } else if (waiting_period_threshold === "three_days") {
                data.waiting_period_threshold = 3;
            } else if (waiting_period_threshold === "custom_days") {
                data.waiting_period_threshold = $("#id_realm_waiting_period_threshold").val();
            }
        } else if (subsection === 'org_join') {
            const org_join_restrictions = $('#id_realm_org_join_restrictions').val();
            if (org_join_restrictions === "only_selected_domain") {
                data.emails_restricted_to_domains = true;
                data.disallow_disposable_email_addresses = false;
            } else if (org_join_restrictions === "no_disposable_email") {
                data.emails_restricted_to_domains = false;
                data.disallow_disposable_email_addresses = true;
            } else if (org_join_restrictions === "no_restriction") {
                data.disallow_disposable_email_addresses = false;
                data.emails_restricted_to_domains = false;
            }

            const user_invite_restriction = $('#id_realm_user_invite_restriction').val();
            if (user_invite_restriction === 'no_invite_required') {
                data.invite_required = false;
                data.invite_by_admins_only = false;
            } else if (user_invite_restriction === 'by_admins_only') {
                data.invite_required = true;
                data.invite_by_admins_only = true;
            } else {
                data.invite_required = true;
                data.invite_by_admins_only = false;
            }
        } else if (subsection === 'auth_settings') {
            data = {};
            data.authentication_methods = JSON.stringify(get_auth_method_table_data());
        } else if (subsection === 'user_defaults') {
            const realm_default_twenty_four_hour_time = $('#id_realm_default_twenty_four_hour_time').val();
            data.default_twenty_four_hour_time = realm_default_twenty_four_hour_time;
        }
        return data;
    }

    function populate_data_for_request(subsection) {
        const data = {};
        const properties_elements = get_subsection_property_elements(subsection);

        for (let input_elem of properties_elements) {
            input_elem = $(input_elem);
            if (check_property_changed(input_elem)) {
                const input_type = input_elem.data("setting-widget-type");
                if (input_type) {
                    const property_name = input_elem.attr('id').replace("id_realm_", "");
                    if (input_type === 'bool') {
                        data[property_name] = JSON.stringify(input_elem.prop('checked'));
                        continue;
                    }
                    if (input_type === 'text') {
                        data[property_name] = JSON.stringify(input_elem.val().trim());
                        continue;
                    }
                    if (input_type === 'integer') {
                        data[property_name] = JSON.stringify(parseInt(input_elem.val().trim(), 10));
                    }
                }
            }
        }

        return data;
    }

    $(".organization").on("click", ".subsection-header .subsection-changes-save .button", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const save_button = $(e.currentTarget);
        const subsection_id = save_button.attr('id').replace("org-submit-", "");
        const subsection = subsection_id.split('-').join('_');
        const subsection_elem = save_button.closest('.org-subsection-parent');

        let data = populate_data_for_request(subsection_elem);
        data = _.extend(data, get_complete_data_for_subsection(subsection));
        exports.save_organization_settings(data, save_button);
    });

    $(".org-subsection-parent").on("keydown", "input", function (e) {
        e.stopPropagation();
        if (e.keyCode === 13) {
            e.preventDefault();
            $(e.target).closest('.org-subsection-parent').find('.subsection-changes-save button').click();
        }
    });

    $("#id_realm_msg_edit_limit_setting").change(function (e) {
        const msg_edit_limit_dropdown_value = e.target.value;
        change_element_block_display_property('id_realm_message_content_edit_limit_minutes',
                                              msg_edit_limit_dropdown_value === 'custom_limit');
    });

    $("#id_realm_msg_delete_limit_setting").change(function (e) {
        const msg_delete_limit_dropdown_value = e.target.value;
        change_element_block_display_property('id_realm_message_content_delete_limit_minutes',
                                              msg_delete_limit_dropdown_value === 'custom_limit');
    });

    $("#id_realm_waiting_period_setting").change(function () {
        const waiting_period_threshold = this.value;
        change_element_block_display_property('id_realm_waiting_period_threshold',
                                              waiting_period_threshold === 'custom_days');
    });

    $("#id_realm_video_chat_provider").change(function (e) {
        const available_providers = page_params.realm_available_video_chat_providers;
        const video_chat_provider_id = parseInt(e.target.value, 10);

        if (video_chat_provider_id === available_providers.google_hangouts.id) {
            $("#google_hangouts_domain").show();
            $(".zoom_credentials").hide();
        } else if (video_chat_provider_id === available_providers.zoom.id) {
            $("#google_hangouts_domain").hide();
            $(".zoom_credentials").show();
        } else {
            $("#google_hangouts_domain").hide();
            $(".zoom_credentials").hide();
        }
    });

    $("#id_realm_org_join_restrictions").change(function (e) {
        const org_join_restrictions = e.target.value;
        const node = $("#allowed_domains_label").parent();
        if (org_join_restrictions === 'only_selected_domain') {
            node.show();
            if (page_params.realm_domains.length === 0) {
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

    function fade_status_element(elem) {
        setTimeout(function () {
            elem.fadeOut(500);
        }, 1000);
    }

    $("#realm_domains_table").on("click", ".delete_realm_domain", function () {
        const domain = $(this).parents("tr").find(".domain").text();
        const url = "/json/realm/domains/" + domain;
        const realm_domains_info = $(".realm_domains_info");

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
        const realm_domains_info = $(".realm_domains_info");
        const widget = $("#add-realm-domain-widget");
        const domain = widget.find(".new-realm-domain").val();
        const allow_subdomains = widget.find(".new-realm-domain-allow-subdomains").prop("checked");
        const data = {
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
        const realm_domains_info = $(".realm_domains_info");
        const domain = $(this).parents("tr").find(".domain").text();
        const allow_subdomains = $(this).prop('checked');
        const url = '/json/realm/domains/' + domain;
        const data = {
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

    function notification_stream_update(stream_id, notification_type) {
        exports.render_notifications_stream_ui(stream_id, notification_type);
        save_discard_widget_status_handler($('#org-notifications'));
    }

    $(".notifications-stream-setting .dropdown-list-body").on("click keypress", ".stream_name", function (e) {
        const notifications_stream_setting_elem = $(this).closest(".notifications-stream-setting");
        if (e.type === "keypress") {
            if (e.which === 13) {
                notifications_stream_setting_elem.find(".dropdown-menu").dropdown("toggle");
            } else {
                return;
            }
        }
        const stream_id = parseInt($(this).attr('data-stream-id'), 10);
        notification_stream_update(stream_id, notifications_stream_setting_elem.data("notifications-type"));
    });

    $(".notification-disable").click(function (e) {
        notification_stream_update(-1, e.target.id.replace("_stream_disable", ""));
    });

    function upload_realm_icon(file_input) {
        const form_data = new FormData();

        form_data.append('csrfmiddlewaretoken', csrf_token);
        for (const [i, file] of Array.prototype.entries.call(file_input[0].files)) {
            form_data.append('file-' + i, file);
        }

        const error_field = $("#realm_icon_file_input_error");
        error_field.hide();
        const spinner = $("#upload_icon_spinner").expectOne();
        loading.make_indicator(spinner, {text: i18n.t("Uploading profile picture.")});
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
        const form_data = new FormData();
        let spinner;
        let error_field;
        let button_text;

        form_data.append('csrfmiddlewaretoken', csrf_token);
        for (const [i, file] of Array.prototype.entries.call(file_input[0].files)) {
            form_data.append('file-' + i, file);
        }
        if (night) {
            error_field = $("#night-logo-section .realm-logo-file-input-error");
            spinner = $("#night-logo-section .upload-logo-spinner");
            button_text = $("#night-logo-section .upload-logo-button-text");
        } else {
            error_field = $("#day-logo-section .realm-logo-file-input-error");
            spinner = $("#day-logo-section .upload-logo-spinner");
            button_text = $("#day-logo-section .upload-logo-button-text");
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

    if (page_params.plan_includes_wide_organization_logo) {
        realm_logo.build_realm_logo_widget(upload_realm_logo, false);
        realm_logo.build_realm_logo_widget(upload_realm_logo, true);
    }


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

window.settings_org = exports;
