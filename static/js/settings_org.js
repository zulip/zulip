"use strict";

const pygments_data = require("../generated/pygments_data.json");
const render_settings_admin_auth_methods_list = require("../templates/settings/admin_auth_methods_list.hbs");
const render_settings_admin_realm_domains_list = require("../templates/settings/admin_realm_domains_list.hbs");

const settings_config = require("./settings_config");

const meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.maybe_disable_widgets = function () {
    if (page_params.is_owner) {
        return;
    }

    $(".organization-box [data-name='auth-methods']")
        .find("input, button, select, checked")
        .prop("disabled", true);

    if (page_params.is_admin) {
        $("#deactivate_realm_button").prop("disabled", true);
        $("#org-message-retention").find("input, select").prop("disabled", true);
        return;
    }

    $(".organization-box [data-name='organization-profile']")
        .find("input, textarea, button, select")
        .prop("disabled", true);

    $(".organization-box [data-name='organization-settings']")
        .find("input, textarea, button, select")
        .prop("disabled", true);

    $(".organization-box [data-name='organization-settings']")
        .find(".control-label-disabled")
        .addClass("enabled");

    $(".organization-box [data-name='organization-permissions']")
        .find("input, textarea, button, select")
        .prop("disabled", true);

    $(".organization-box [data-name='organization-permissions']")
        .find(".control-label-disabled")
        .addClass("enabled");
};

exports.get_sorted_options_list = function (option_values_object) {
    const options_list = Object.keys(option_values_object).map((key) => ({
        ...option_values_object[key],
        key,
    }));
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
        settings_config.create_stream_policy_values,
    );
    options.invite_to_stream_policy_values = exports.get_sorted_options_list(
        settings_config.invite_to_stream_policy_values,
    );
    options.user_group_edit_policy_values = exports.get_sorted_options_list(
        settings_config.user_group_edit_policy_values,
    );
    options.private_message_policy_values = exports.get_sorted_options_list(
        settings_config.private_message_policy_values,
    );
    return options;
};

exports.get_realm_time_limits_in_minutes = function (property) {
    let val = (page_params[property] / 60).toFixed(1);
    if (parseFloat(val, 10) === parseInt(val, 10)) {
        val = parseInt(val, 10);
    }
    return val.toString();
};

function get_property_value(property_name) {
    if (property_name === "realm_message_content_edit_limit_minutes") {
        return exports.get_realm_time_limits_in_minutes("realm_message_content_edit_limit_seconds");
    }

    if (property_name === "realm_message_content_delete_limit_minutes") {
        return exports.get_realm_time_limits_in_minutes(
            "realm_message_content_delete_limit_seconds",
        );
    }

    if (property_name === "realm_waiting_period_setting") {
        if (page_params.realm_waiting_period_threshold === 0) {
            return "none";
        }
        if (page_params.realm_waiting_period_threshold === 3) {
            return "three_days";
        }
        return "custom_days";
    }

    if (property_name === "realm_add_emoji_by_admins_only") {
        if (page_params.realm_add_emoji_by_admins_only) {
            return "by_admins_only";
        }
        return "by_anyone";
    }

    if (property_name === "realm_msg_edit_limit_setting") {
        if (!page_params.realm_allow_message_editing) {
            return "never";
        }
        for (const [value, elem] of settings_config.msg_edit_limit_dropdown_values) {
            if (elem.seconds === page_params.realm_message_content_edit_limit_seconds) {
                return value;
            }
        }
        return "custom_limit";
    }

    if (property_name === "realm_message_retention_setting") {
        if (page_params.realm_message_retention_days === settings_config.retain_message_forever) {
            return "retain_forever";
        }
        return "retain_for_period";
    }

    if (property_name === "realm_msg_delete_limit_setting") {
        if (!page_params.realm_allow_message_deleting) {
            return "never";
        }
        for (const [value, elem] of settings_config.msg_delete_limit_dropdown_values) {
            if (elem.seconds === page_params.realm_message_content_delete_limit_seconds) {
                return value;
            }
        }
        return "custom_limit";
    }

    if (property_name === "realm_org_join_restrictions") {
        if (page_params.realm_emails_restricted_to_domains) {
            return "only_selected_domain";
        }
        if (page_params.realm_disallow_disposable_email_addresses) {
            return "no_disposable_email";
        }
        return "no_restriction";
    }

    if (property_name === "realm_user_invite_restriction") {
        if (!page_params.realm_invite_required) {
            if (page_params.realm_invite_by_admins_only) {
                return "no_invite_required_by_admins_only";
            }
            return "no_invite_required";
        }
        if (page_params.realm_invite_by_admins_only) {
            return "by_admins_only";
        }
        return "by_anyone";
    }

    if (property_name === "realm_default_twenty_four_hour_time") {
        return JSON.stringify(page_params[property_name]);
    }

    return page_params[property_name];
}

exports.extract_property_name = function (elem) {
    return elem.attr("id").split("-").join("_").replace("id_", "");
};

function get_subsection_property_elements(element) {
    const subsection = $(element).closest(".org-subsection-parent");
    return Array.from(subsection.find(".prop-element"));
}

const simple_dropdown_properties = [
    "realm_create_stream_policy",
    "realm_invite_to_stream_policy",
    "realm_user_group_edit_policy",
    "realm_private_message_policy",
    "realm_add_emoji_by_admins_only",
    "realm_user_invite_restriction",
];

function set_property_dropdown_value(property_name) {
    $("#id_" + property_name).val(get_property_value(property_name));
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
    change_element_block_display_property(
        "id_realm_waiting_period_threshold",
        value === "custom_days",
    );
}

function set_video_chat_provider_dropdown() {
    const chat_provider_id = page_params.realm_video_chat_provider;
    $("#id_realm_video_chat_provider").val(chat_provider_id);
}

function set_msg_edit_limit_dropdown() {
    const value = get_property_value("realm_msg_edit_limit_setting");
    $("#id_realm_msg_edit_limit_setting").val(value);
    change_element_block_display_property(
        "id_realm_message_content_edit_limit_minutes",
        value === "custom_limit",
    );
    settings_ui.disable_sub_setting_onchange(
        value !== "never",
        "id_realm_allow_community_topic_editing",
        true,
    );
}

function set_msg_delete_limit_dropdown() {
    const value = get_property_value("realm_msg_delete_limit_setting");
    $("#id_realm_msg_delete_limit_setting").val(value);
    change_element_block_display_property(
        "id_realm_message_content_delete_limit_minutes",
        value === "custom_limit",
    );
}

function set_message_retention_setting_dropdown() {
    const value = get_property_value("realm_message_retention_setting");
    $("#id_realm_message_retention_setting").val(value);
    change_element_block_display_property(
        "id_realm_message_retention_days",
        value === "retain_for_period",
    );
    if (
        get_property_value("realm_message_retention_days") ===
        settings_config.retain_message_forever
    ) {
        $("#id_realm_message_retention_days").val("");
    }
}

function set_org_join_restrictions_dropdown() {
    const value = get_property_value("realm_org_join_restrictions");
    $("#id_realm_org_join_restrictions").val(value);
    change_element_block_display_property(
        "allowed_domains_label",
        value === "only_selected_domain",
    );
}

function set_message_content_in_email_notifications_visiblity() {
    change_element_block_display_property(
        "message_content_in_email_notifications_label",
        page_params.realm_message_content_allowed_in_email_notifications,
    );
}

function set_digest_emails_weekday_visibility() {
    change_element_block_display_property(
        "id_realm_digest_weekday",
        page_params.realm_digest_emails_enabled,
    );
}

exports.populate_realm_domains = function (realm_domains) {
    if (!meta.loaded) {
        return;
    }

    const domains_list = realm_domains.map((realm_domain) =>
        realm_domain.allow_subdomains ? "*." + realm_domain.domain : realm_domain.domain,
    );
    let domains = domains_list.join(", ");
    if (domains.length === 0) {
        domains = i18n.t("None");
    }
    $("#allowed_domains_label").text(i18n.t("Allowed domains: __domains__", {domains}));

    const realm_domains_table_body = $("#realm_domains_table tbody").expectOne();
    realm_domains_table_body.find("tr").remove();

    for (const realm_domain of realm_domains) {
        realm_domains_table_body.append(
            render_settings_admin_realm_domains_list({
                realm_domain,
            }),
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
            is_owner: page_params.is_owner,
        });
    }
    auth_methods_table.html(rendered_auth_method_rows);
};

function update_dependent_subsettings(property_name) {
    if (simple_dropdown_properties.includes(property_name)) {
        set_property_dropdown_value(property_name);
    } else if (property_name === "realm_waiting_period_threshold") {
        set_realm_waiting_period_dropdown();
    } else if (
        property_name === "realm_video_chat_provider" ||
        property_name.startsWith("realm_zoom")
    ) {
        set_video_chat_provider_dropdown();
    } else if (
        property_name === "realm_msg_edit_limit_setting" ||
        property_name === "realm_message_content_edit_limit_minutes"
    ) {
        set_msg_edit_limit_dropdown();
    } else if (property_name === "realm_message_retention_days") {
        set_message_retention_setting_dropdown();
    } else if (
        property_name === "realm_msg_delete_limit_setting" ||
        property_name === "realm_message_content_delete_limit_minutes"
    ) {
        set_msg_delete_limit_dropdown();
    } else if (property_name === "realm_org_join_restrictions") {
        set_org_join_restrictions_dropdown();
    } else if (property_name === "realm_message_content_allowed_in_email_notifications") {
        set_message_content_in_email_notifications_visiblity();
    } else if (property_name === "realm_digest_emails_enabled") {
        settings_notifications.set_enable_digest_emails_visibility();
        set_digest_emails_weekday_visibility();
    }
}

function discard_property_element_changes(elem) {
    elem = $(elem);
    const property_name = exports.extract_property_name(elem);
    const property_value = get_property_value(property_name);

    if (property_name === "realm_authentication_methods") {
        exports.populate_auth_methods(property_value);
    } else if (property_name === "realm_notifications_stream_id") {
        exports.notifications_stream_widget.render(property_value);
    } else if (property_name === "realm_signup_notifications_stream_id") {
        exports.signup_notifications_stream_widget.render(property_value);
    } else if (property_name === "realm_default_code_block_language") {
        exports.default_code_language_widget.render(property_value);
    } else if (property_value !== undefined) {
        exports.set_input_element_value(elem, property_value);
    } else {
        blueslip.error("Element refers to unknown property " + property_name);
    }

    update_dependent_subsettings(property_name);
}

exports.sync_realm_settings = function (property) {
    if (!overlays.settings_open()) {
        return;
    }

    const value = page_params[`realm_${property}`];
    if (property === "notifications_stream_id") {
        exports.notifications_stream_widget.render(value);
    } else if (property === "signup_notifications_stream_id") {
        exports.signup_notifications_stream_widget.render(value);
    } else if (property === "default_code_block_language") {
        exports.default_code_language_widget.render(value);
    }

    if (property === "message_content_edit_limit_seconds") {
        property = "message_content_edit_limit_minutes";
    } else if (property === "allow_message_editing") {
        property = "msg_edit_limit_setting";
    } else if (
        property === "emails_restricted_to_domains" ||
        property === "disallow_disposable_email_addresses"
    ) {
        property = "org_join_restrictions";
    } else if (property === "message_content_delete_limit_seconds") {
        property = "message_content_delete_limit_minutes";
    } else if (property === "allow_message_deleting") {
        property = "msg_delete_limit_setting";
    } else if (property === "invite_required" || property === "invite_by_admins_only") {
        property = "user_invite_restriction";
    }
    const element = $("#id_realm_" + property);
    if (element.length) {
        discard_property_element_changes(element);
    }
};

exports.change_save_button_state = function ($element, state) {
    function show_hide_element($element, show, fadeout_delay) {
        if (show) {
            $element.removeClass("hide").addClass(".show").fadeIn(300);
            return;
        }
        setTimeout(() => {
            $element.fadeOut(300);
        }, fadeout_delay);
    }

    const $saveBtn = $element.find(".save-button");
    const $textEl = $saveBtn.find(".save-discard-widget-button-text");

    if (state !== "saving") {
        $saveBtn.removeClass("saving");
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

        $element.find(".discard-button").show();
    } else if (state === "saved") {
        button_text = i18n.t("Save changes");
        data_status = "";
        is_show = false;
    } else if (state === "saving") {
        button_text = i18n.t("Saving");
        data_status = "saving";
        is_show = true;

        $element.find(".discard-button").hide();
        $saveBtn.addClass("saving");
    } else if (state === "failed") {
        button_text = i18n.t("Save changes");
        data_status = "failed";
        is_show = true;
    } else if (state === "succeeded") {
        button_text = i18n.t("Saved");
        data_status = "saved";
        is_show = false;
    }

    $textEl.text(button_text);
    $saveBtn.attr("data-status", data_status);
    show_hide_element($element, is_show, 800);
};

function get_input_type(input_elem, input_type) {
    if (["boolean", "string", "number"].includes(input_type)) {
        return input_type;
    }
    return input_elem.data("setting-widget-type");
}

exports.get_input_element_value = function (input_elem, input_type) {
    input_elem = $(input_elem);
    input_type = get_input_type(input_elem, input_type);
    if (input_type) {
        if (input_type === "boolean") {
            return input_elem.prop("checked");
        }
        if (input_type === "string") {
            return input_elem.val().trim();
        }
        if (input_type === "number") {
            return parseInt(input_elem.val().trim(), 10);
        }
    }
    return;
};

exports.set_input_element_value = function (input_elem, value) {
    const input_type = get_input_type(input_elem, typeof value);
    if (input_type) {
        if (input_type === "boolean") {
            return input_elem.prop("checked", value);
        }
        if (input_type === "string" || input_type === "number") {
            return input_elem.val(value);
        }
    }
    blueslip.error(`Failed to set value of property ${exports.extract_property_name(input_elem)}`);
};

exports.set_up = function () {
    exports.build_page();
    exports.maybe_disable_widgets();
};

function get_auth_method_table_data() {
    const new_auth_methods = {};
    const auth_method_rows = $("#id_realm_authentication_methods").find("tr.method_row");

    for (const method_row of auth_method_rows) {
        new_auth_methods[$(method_row).data("method")] = $(method_row)
            .find("input")
            .prop("checked");
    }

    return new_auth_methods;
}

function check_property_changed(elem) {
    elem = $(elem);
    const property_name = exports.extract_property_name(elem);
    let current_val = get_property_value(property_name);
    let changed_val;

    if (property_name === "realm_authentication_methods") {
        current_val = sort_object_by_key(current_val);
        current_val = JSON.stringify(current_val);
        changed_val = get_auth_method_table_data();
        changed_val = JSON.stringify(changed_val);
    } else if (property_name === "realm_notifications_stream_id") {
        changed_val = parseInt(exports.notifications_stream_widget.value(), 10);
    } else if (property_name === "realm_signup_notifications_stream_id") {
        changed_val = parseInt(exports.signup_notifications_stream_widget.value(), 10);
    } else if (property_name === "realm_default_code_block_language") {
        changed_val = exports.default_code_language_widget.value();
    } else if (current_val !== undefined) {
        changed_val = exports.get_input_element_value(elem, typeof current_val);
    } else {
        blueslip.error("Element refers to unknown property " + property_name);
    }
    return current_val !== changed_val;
}

exports.save_discard_widget_status_handler = (subsection) => {
    subsection.find(".subsection-failed-status p").hide();
    subsection.find(".save-button").show();
    const properties_elements = get_subsection_property_elements(subsection);
    const show_change_process_button = properties_elements.some(check_property_changed);

    const save_btn_controls = subsection.find(".subsection-header .save-button-controls");
    const button_state = show_change_process_button ? "unsaved" : "discarded";
    exports.change_save_button_state(save_btn_controls, button_state);
};

exports.default_code_language_widget = null;
exports.notifications_stream_widget = null;
exports.signup_notifications_stream_widget = null;

exports.init_dropdown_widgets = () => {
    const streams = stream_data.get_streams_for_settings_page();
    const notification_stream_options = {
        data: streams.map((x) => {
            const item = {
                name: x.name,
                value: x.stream_id.toString(),
            };
            return item;
        }),
        on_update: () => {
            exports.save_discard_widget_status_handler($("#org-notifications"));
        },
        default_text: i18n.t("Disabled"),
        render_text: (x) => `#${x}`,
        null_value: -1,
    };
    exports.notifications_stream_widget = dropdown_list_widget(
        Object.assign(
            {
                widget_name: "realm_notifications_stream_id",
                value: page_params.realm_notifications_stream_id,
            },
            notification_stream_options,
        ),
    );
    exports.signup_notifications_stream_widget = dropdown_list_widget(
        Object.assign(
            {
                widget_name: "realm_signup_notifications_stream_id",
                value: page_params.realm_signup_notifications_stream_id,
            },
            notification_stream_options,
        ),
    );
    exports.default_code_language_widget = dropdown_list_widget({
        widget_name: "realm_default_code_block_language",
        data: Object.keys(pygments_data.langs).map((x) => ({
            name: x,
            value: x,
        })),
        value: page_params.realm_default_code_block_language,
        on_update: () => {
            exports.save_discard_widget_status_handler($("#org-other-settings"));
        },
        default_text: i18n.t("No language set"),
    });
};

exports.build_page = function () {
    meta.loaded = true;

    loading.make_indicator($("#admin_page_auth_methods_loading_indicator"));

    // Initialize all the dropdown list widgets.
    exports.init_dropdown_widgets();
    // Populate realm domains
    exports.populate_realm_domains(page_params.realm_domains);

    // Populate authentication methods table
    exports.populate_auth_methods(page_params.realm_authentication_methods);

    simple_dropdown_properties.forEach(set_property_dropdown_value);

    set_realm_waiting_period_dropdown();
    set_video_chat_provider_dropdown();
    set_msg_edit_limit_dropdown();
    set_msg_delete_limit_dropdown();
    set_message_retention_setting_dropdown();
    set_org_join_restrictions_dropdown();
    set_message_content_in_email_notifications_visiblity();
    set_digest_emails_weekday_visibility();

    $(".admin-realm-form").on("change input", "input, select, textarea", (e) => {
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

        const subsection = $(e.target).closest(".org-subsection-parent");
        exports.save_discard_widget_status_handler(subsection);
    });

    $(".organization").on(
        "click",
        ".subsection-header .subsection-changes-discard .button",
        (e) => {
            e.preventDefault();
            e.stopPropagation();
            get_subsection_property_elements(e.target).forEach(discard_property_element_changes);
            const save_btn_controls = $(e.target).closest(".save-button-controls");
            exports.change_save_button_state(save_btn_controls, "discarded");
        },
    );

    exports.save_organization_settings = function (data, save_button) {
        const subsection_parent = save_button.closest(".org-subsection-parent");
        const save_btn_container = subsection_parent.find(".save-button-controls");
        const failed_alert_elem = subsection_parent.find(".subsection-failed-status p");
        exports.change_save_button_state(save_btn_container, "saving");
        channel.patch({
            url: "/json/realm",
            data,
            success() {
                failed_alert_elem.hide();
                exports.change_save_button_state(save_btn_container, "succeeded");
            },
            error(xhr) {
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

        if (subsection === "msg_editing") {
            const edit_limit_setting_value = $("#id_realm_msg_edit_limit_setting").val();
            if (edit_limit_setting_value === "never") {
                data.allow_message_editing = false;
            } else if (edit_limit_setting_value === "custom_limit") {
                data.message_content_edit_limit_seconds = exports.parse_time_limit(
                    $("#id_realm_message_content_edit_limit_minutes"),
                );
                // Disable editing if the parsed time limit is 0 seconds
                data.allow_message_editing = !!data.message_content_edit_limit_seconds;
            } else {
                data.allow_message_editing = true;
                data.message_content_edit_limit_seconds = settings_config.msg_edit_limit_dropdown_values.get(
                    edit_limit_setting_value,
                ).seconds;
            }
            const delete_limit_setting_value = $("#id_realm_msg_delete_limit_setting").val();
            if (delete_limit_setting_value === "never") {
                data.allow_message_deleting = false;
            } else if (delete_limit_setting_value === "custom_limit") {
                data.message_content_delete_limit_seconds = exports.parse_time_limit(
                    $("#id_realm_message_content_delete_limit_minutes"),
                );
                // Disable deleting if the parsed time limit is 0 seconds
                data.allow_message_deleting = !!data.message_content_delete_limit_seconds;
            } else {
                data.allow_message_deleting = true;
                data.message_content_delete_limit_seconds = settings_config.msg_delete_limit_dropdown_values.get(
                    delete_limit_setting_value,
                ).seconds;
            }
        } else if (subsection === "notifications") {
            data.notifications_stream_id = JSON.stringify(
                parseInt(exports.notifications_stream_widget.value(), 10),
            );
            data.signup_notifications_stream_id = JSON.stringify(
                parseInt(exports.signup_notifications_stream_widget.value(), 10),
            );
        } else if (subsection === "message_retention") {
            const message_retention_setting_value = $("#id_realm_message_retention_setting").val();
            if (message_retention_setting_value === "retain_forever") {
                data.message_retention_days = JSON.stringify("forever");
            } else {
                data.message_retention_days = JSON.stringify(
                    exports.get_input_element_value($("#id_realm_message_retention_days")),
                );
            }
        } else if (subsection === "other_settings") {
            const code_block_language_value = exports.default_code_language_widget.value();
            data.default_code_block_language = JSON.stringify(code_block_language_value);
        } else if (subsection === "other_permissions") {
            const add_emoji_permission = $("#id_realm_add_emoji_by_admins_only").val();

            if (add_emoji_permission === "by_admins_only") {
                data.add_emoji_by_admins_only = true;
            } else if (add_emoji_permission === "by_anyone") {
                data.add_emoji_by_admins_only = false;
            }
        } else if (subsection === "org_join") {
            const org_join_restrictions = $("#id_realm_org_join_restrictions").val();
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

            const user_invite_restriction = $("#id_realm_user_invite_restriction").val();
            if (user_invite_restriction === "no_invite_required") {
                data.invite_required = false;
                data.invite_by_admins_only = false;
            } else if (user_invite_restriction === "no_invite_required_by_admins_only") {
                data.invite_required = false;
                data.invite_by_admins_only = true;
            } else if (user_invite_restriction === "by_admins_only") {
                data.invite_required = true;
                data.invite_by_admins_only = true;
            } else {
                data.invite_required = true;
                data.invite_by_admins_only = false;
            }

            const waiting_period_threshold = $("#id_realm_waiting_period_setting").val();
            if (waiting_period_threshold === "none") {
                data.waiting_period_threshold = 0;
            } else if (waiting_period_threshold === "three_days") {
                data.waiting_period_threshold = 3;
            } else if (waiting_period_threshold === "custom_days") {
                data.waiting_period_threshold = $("#id_realm_waiting_period_threshold").val();
            }
        } else if (subsection === "auth_settings") {
            data = {};
            data.authentication_methods = JSON.stringify(get_auth_method_table_data());
        } else if (subsection === "user_defaults") {
            const realm_default_twenty_four_hour_time = $(
                "#id_realm_default_twenty_four_hour_time",
            ).val();
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
                const input_value = exports.get_input_element_value(input_elem);
                if (input_value !== undefined) {
                    const property_name = input_elem.attr("id").replace("id_realm_", "");
                    data[property_name] = JSON.stringify(input_value);
                }
            }
        }

        return data;
    }

    $(".organization").on("click", ".subsection-header .subsection-changes-save .button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const save_button = $(e.currentTarget);
        const subsection_id = save_button.attr("id").replace("org-submit-", "");
        const subsection = subsection_id.split("-").join("_");
        const subsection_elem = save_button.closest(".org-subsection-parent");

        const data = {
            ...populate_data_for_request(subsection_elem),
            ...get_complete_data_for_subsection(subsection),
        };
        exports.save_organization_settings(data, save_button);
    });

    $(".org-subsection-parent").on("keydown", "input", (e) => {
        e.stopPropagation();
        if (e.keyCode === 13) {
            e.preventDefault();
            $(e.target)
                .closest(".org-subsection-parent")
                .find(".subsection-changes-save button")
                .trigger("click");
        }
    });

    $("#id_realm_msg_edit_limit_setting").on("change", (e) => {
        const msg_edit_limit_dropdown_value = e.target.value;
        change_element_block_display_property(
            "id_realm_message_content_edit_limit_minutes",
            msg_edit_limit_dropdown_value === "custom_limit",
        );
    });

    $("#id_realm_msg_delete_limit_setting").on("change", (e) => {
        const msg_delete_limit_dropdown_value = e.target.value;
        change_element_block_display_property(
            "id_realm_message_content_delete_limit_minutes",
            msg_delete_limit_dropdown_value === "custom_limit",
        );
    });

    $("#id_realm_message_retention_setting").on("change", (e) => {
        const message_retention_setting_dropdown_value = e.target.value;
        change_element_block_display_property(
            "id_realm_message_retention_days",
            message_retention_setting_dropdown_value === "retain_for_period",
        );
    });

    $("#id_realm_waiting_period_setting").on("change", function () {
        const waiting_period_threshold = this.value;
        change_element_block_display_property(
            "id_realm_waiting_period_threshold",
            waiting_period_threshold === "custom_days",
        );
    });

    $("#id_realm_org_join_restrictions").on("change", (e) => {
        const org_join_restrictions = e.target.value;
        const node = $("#allowed_domains_label").parent();
        if (org_join_restrictions === "only_selected_domain") {
            node.show();
            if (page_params.realm_domains.length === 0) {
                overlays.open_modal("#realm_domains_modal");
            }
        } else {
            node.hide();
        }
    });

    $("#id_realm_org_join_restrictions").on("click", (e) => {
        // This prevents the disappearance of modal when there are
        // no allowed domains otherwise it gets closed due to
        // the click event handler attached to `#settings_overlay_container`
        e.stopPropagation();
    });

    function fade_status_element(elem) {
        setTimeout(() => {
            elem.fadeOut(500);
        }, 1000);
    }

    $("#realm_domains_table").on("click", ".delete_realm_domain", function () {
        const domain = $(this).parents("tr").find(".domain").text();
        const url = "/json/realm/domains/" + domain;
        const realm_domains_info = $(".realm_domains_info");

        channel.del({
            url,
            success() {
                ui_report.success(i18n.t("Deleted successfully!"), realm_domains_info);
                fade_status_element(realm_domains_info);
            },
            error(xhr) {
                ui_report.error(i18n.t("Failed"), xhr, realm_domains_info);
                fade_status_element(realm_domains_info);
            },
        });
    });

    $("#submit-add-realm-domain").on("click", () => {
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
            data,
            success() {
                $("#add-realm-domain-widget .new-realm-domain").val("");
                $("#add-realm-domain-widget .new-realm-domain-allow-subdomains").prop(
                    "checked",
                    false,
                );
                ui_report.success(i18n.t("Added successfully!"), realm_domains_info);
                fade_status_element(realm_domains_info);
            },
            error(xhr) {
                ui_report.error(i18n.t("Failed"), xhr, realm_domains_info);
                fade_status_element(realm_domains_info);
            },
        });
    });

    $("#realm_domains_table").on("change", ".allow-subdomains", function (e) {
        e.stopPropagation();
        const realm_domains_info = $(".realm_domains_info");
        const domain = $(this).parents("tr").find(".domain").text();
        const allow_subdomains = $(this).prop("checked");
        const url = "/json/realm/domains/" + domain;
        const data = {
            allow_subdomains: JSON.stringify(allow_subdomains),
        };

        channel.patch({
            url,
            data,
            success() {
                if (allow_subdomains) {
                    ui_report.success(
                        i18n.t("Update successful: Subdomains allowed for __domain__", {
                            domain,
                        }),
                        realm_domains_info,
                    );
                } else {
                    ui_report.success(
                        i18n.t("Update successful: Subdomains no longer allowed for __domain__", {
                            domain,
                        }),
                        realm_domains_info,
                    );
                }
                fade_status_element(realm_domains_info);
            },
            error(xhr) {
                ui_report.error(i18n.t("Failed"), xhr, realm_domains_info);
                fade_status_element(realm_domains_info);
            },
        });
    });

    function realm_icon_logo_upload_complete(spinner, upload_text, delete_button) {
        spinner.css({visibility: "hidden"});
        upload_text.show();
        delete_button.show();
    }

    function realm_icon_logo_upload_start(spinner, upload_text, delete_button) {
        spinner.css({visibility: "visible"});
        upload_text.hide();
        delete_button.hide();
    }

    function upload_realm_logo_or_icon(file_input, night, icon) {
        const form_data = new FormData();
        let widget;
        let url;

        form_data.append("csrfmiddlewaretoken", csrf_token);
        for (const [i, file] of Array.prototype.entries.call(file_input[0].files)) {
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
        const spinner = $(`${widget} .upload-spinner-background`).expectOne();
        const upload_text = $(`${widget}  .image-upload-text`).expectOne();
        const delete_button = $(`${widget}  .image-delete-button`).expectOne();
        const error_field = $(`${widget}  .image_file_input_error`).expectOne();
        realm_icon_logo_upload_start(spinner, upload_text, delete_button);
        error_field.hide();
        channel.post({
            url,
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success() {
                realm_icon_logo_upload_complete(spinner, upload_text, delete_button);
            },
            error(xhr) {
                realm_icon_logo_upload_complete(spinner, upload_text, delete_button);
                ui_report.error("", xhr, error_field);
            },
        });
    }

    realm_icon.build_realm_icon_widget(upload_realm_logo_or_icon, null, true);
    if (page_params.zulip_plan_is_not_limited) {
        realm_logo.build_realm_logo_widget(upload_realm_logo_or_icon, false);
        realm_logo.build_realm_logo_widget(upload_realm_logo_or_icon, true);
    }

    $("#deactivate_realm_button").on("click", (e) => {
        if (!overlays.is_modal_open()) {
            e.preventDefault();
            e.stopPropagation();
            overlays.open_modal("#deactivate-realm-modal");
        }
    });

    $("#do_deactivate_realm_button").on("click", () => {
        if (overlays.is_modal_open()) {
            overlays.close_modal("#deactivate-realm-modal");
        }
        channel.post({
            url: "/json/realm/deactivate",
            error(xhr) {
                ui_report.error(
                    i18n.t("Failed"),
                    xhr,
                    $("#admin-realm-deactivation-status").expectOne(),
                );
            },
        });
    });
};

window.settings_org = exports;
