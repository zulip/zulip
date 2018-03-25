var settings_org = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.set_create_stream_permission_dropdwon = function () {
    var menu = "id_realm_create_stream_permission";
    $("#id_realm_waiting_period_threshold").parent().hide();
    if (page_params.realm_create_stream_by_admins_only) {
        $("#" + menu + " option[value=by_admins_only]").attr("selected", "selected");
    } else if (page_params.realm_waiting_period_threshold === 0) {
        $("#" + menu + " option[value=by_anyone]").attr("selected", "selected");
    } else if (page_params.realm_waiting_period_threshold === 3) {
        $("#" + menu + " option[value=by_admin_user_with_three_days_old]").attr("selected", "selected");
    } else {
        $("#" + menu + " option[value=by_admin_user_with_custom_time]").attr("selected", "selected");
        $("#id_realm_waiting_period_threshold").parent().show();
    }
};

exports.set_add_emoji_permission_dropdown = function () {
    var menu = "id_realm_add_emoji_by_admins_only";
    if (page_params.realm_add_emoji_by_admins_only) {
        $("#" + menu + " option[value=by_admins_only]").attr("selected", "selected");
    } else {
        $("#" + menu + " option[value=by_anyone]").attr("selected", "selected");
    }
};

exports.populate_realm_domains = function (realm_domains) {
    if (!meta.loaded) {
        return;
    }

    var domains_list = _.map(realm_domains, function (realm_domain) {
        return (realm_domain.allow_subdomains ? "*." + realm_domain.domain : realm_domain.domain);
    });
    var domains = domains_list.join(', ');

    $("#id_realm_restricted_to_domain").prop("checked", page_params.realm_restricted_to_domain);
    if (domains.length === 0) {
        domains = i18n.t("None");
        $("#id_realm_restricted_to_domain").attr("data-toggle", "modal");
        $("#id_realm_restricted_to_domain").attr("href", "#realm_domains_modal");
    }
    if (domains !== "None") {
        $("#id_realm_restricted_to_domain").attr("data-toggle", "none");
    }
    $("#realm_restricted_to_domains_label").text(i18n.t("Restrict new users to the following email domains: __domains__", {domains: domains}));

    var realm_domains_table_body = $("#realm_domains_table tbody").expectOne();
    realm_domains_table_body.find("tr").remove();
    _.each(realm_domains, function (realm_domain) {
        realm_domains_table_body.append(templates.render("admin-realm-domains-list", {realm_domain: realm_domain}));
    });
};

exports.reset_realm_default_language = function () {
    if (!meta.loaded) {
        return;
    }

    $("#id_realm_default_language").val(page_params.realm_default_language);
};

exports.update_realm_description = function () {
    if (!meta.loaded) {
        return;
    }

    $('#id_realm_description').val(page_params.realm_description);
};

exports.update_message_retention_days = function () {
    if (!meta.loaded) {
        return;
    }

    $("#id_realm_message_retention_days").val(page_params.message_retention_days);
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


exports.render_notifications_stream_ui = function (stream_id) {
    var elem = $('#realm_notifications_stream_name');

    var name = stream_data.maybe_get_stream_name(stream_id);

    if (!name) {
        elem.text(i18n.t("Disabled"));
        elem.addClass("text-warning");
        return;
    }

    // Happy path
    elem.text('#' + name);
    elem.removeClass('text-warning');
};

exports.populate_notifications_stream_dropdown = function (stream_list) {
    var dropdown_list_body = $("#id_realm_notifications_stream .dropdown-list-body").expectOne();
    var search_input = $("#id_realm_notifications_stream .dropdown-search > input[type=text]");

    list_render(dropdown_list_body, stream_list, {
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
                ui.update_scrollbar(dropdown_list_body);
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

exports.render_signup_notifications_stream_ui = function (stream_id) {
    var elem = $('#realm_signup_notifications_stream_name');

    var name = stream_data.maybe_get_stream_name(stream_id);

    if (!name || !page_params.new_user_bot_configured) {
        elem.text(i18n.t("Disabled"));
        elem.addClass("text-warning");
        return;
    }

    // Happy path
    elem.text('#' + name);
    elem.removeClass('text-warning');
};

exports.populate_signup_notifications_stream_dropdown = function (stream_list) {
    var dropdown_list_body = $("#id_realm_signup_notifications_stream .dropdown-list-body").expectOne();
    var search_input = $("#id_realm_signup_notifications_stream .dropdown-search > input[type=text]");

    list_render(dropdown_list_body, stream_list, {
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

function property_type_status_element(element) {
    return $("#admin-realm-" + element.split('_').join('-') + "-status").expectOne();
}

function _set_up() {
    meta.loaded = true;

    loading.make_indicator($('#admin_page_auth_methods_loading_indicator'));

    // Populate notifications stream modal
    if (page_params.is_admin) {
        var streams = stream_data.get_streams_for_settings_page();
        exports.populate_notifications_stream_dropdown(streams);
        exports.populate_signup_notifications_stream_dropdown(streams);
    }
    exports.render_notifications_stream_ui(page_params.realm_notifications_stream_id);
    exports.render_signup_notifications_stream_ui(page_params.realm_signup_notifications_stream_id);

    // Populate realm domains
    exports.populate_realm_domains(page_params.realm_domains);

    // Populate authentication methods table
    exports.populate_auth_methods(page_params.realm_authentication_methods);

    var org_profile = {
        name: {
            type: 'text',
            msg: i18n.t("Name changed!"),
        },
        description: {
            type: 'text',
            msg: i18n.t("Description changed!"),
        },
    };

    var org_settings = {
        msg_editing: {
            allow_message_deleting: {
                type: 'bool',
                checked_msg: i18n.t("Users can delete their messages!"),
                unchecked_msg: i18n.t("Users can no longer delete their messages!"),
            },
            allow_edit_history: {
                type: 'bool',
                checked_msg: i18n.t("Users can view message edit history!"),
                unchecked_msg: i18n.t("Users can no longer view message edit history!"),
            },
        },
        msg_feed: {
            inline_image_preview: {
                type: 'bool',
                checked_msg: i18n.t("Previews of uploaded and linked images will be shown!"),
                unchecked_msg: i18n.t("Previews of uploaded and linked images will not be shown!"),
            },
            inline_url_embed_preview: {
                type: 'bool',
                checked_msg: i18n.t("Previews for linked websites will be shown!"),
                unchecked_msg: i18n.t("Previews for linked websites will not be shown!"),
            },
            mandatory_topics: {
                type: 'bool',
                checked_msg: i18n.t("Topics are required in messages to streams!"),
                unchecked_msg: i18n.t("Topics are not required in messages to streams!"),
            },
        },
        language_notify: {
            default_language: {
                type: 'text',
                msg: i18n.t("Default language changed!"),
            },
            send_welcome_emails: {
                type: 'bool',
                checked_msg: i18n.t("Send emails to new users explaining how to use Zulip!"),
                unchecked_msg: i18n.t("Don't send emails to new users explaining how to use Zulip!"),
            },
        },
    };

    var org_permissions = {
        org_join: {
            restricted_to_domain: {
                type: 'bool',
                checked_msg: i18n.t("New user e-mails now restricted to certain domains!"),
                unchecked_msg: i18n.t("New users may have arbitrary e-mails!"),
            },
            invite_required: {
                type: 'bool',
                checked_msg: i18n.t("New users must be invited by e-mail!"),
                unchecked_msg: i18n.t("New users may sign up online!"),
            },
            disallow_disposable_email_addresses: {
                type: 'bool',
                checked_msg: i18n.t("Users cannot sign up using disposable email addresses!"),
                unchecked_msg: i18n.t("Users can sign up using disposable email addresses!"),
            },
            invite_by_admins_only: {
                type: 'bool',
                checked_msg: i18n.t("New users must be invited by an admin!"),
                unchecked_msg: i18n.t("Any user may now invite new users!"),
            },
        },
        user_identity: {
            name_changes_disabled: {
                type: 'bool',
                checked_msg: i18n.t("Users cannot change their name!"),
                unchecked_msg: i18n.t("Users may now change their name!"),
            },
            email_changes_disabled: {
                type: 'bool',
                checked_msg: i18n.t("Users cannot change their email!"),
                unchecked_msg: i18n.t("Users may now change their email!"),
            },
        },
        other_permissions: {
            add_emoji_by_admins_only: {
                type: 'bool',
                checked_msg: i18n.t("Only administrators may now add new emoji!"),
                unchecked_msg: i18n.t("Any user may now add new emoji!"),
            },
            bot_creation_policy: {
                type: 'integer',
                msg: i18n.t("Permissions changed"),
            },
        },
    };

    function get_property_types(settings) {
        var setting_property = {};
        _.each(_.values(settings), function (t) {
            setting_property = _.extend(setting_property, t);
        });
        return setting_property;
    }

    // create property_types object
    var property_types = {
        profile: org_profile,
        settings: get_property_types(org_settings),
        permissions: get_property_types(org_permissions),
    };

    function populate_data_for_request(data, changing_property_types) {
        _.each(changing_property_types, function (v, k) {
            var field = changing_property_types[k];
            if (field.type === 'bool') {
                data[k] = JSON.stringify($('#id_realm_'+k).prop('checked'));
                return;
            }
            if (field.type === 'text') {
                data[k] = JSON.stringify($('#id_realm_'+k).val().trim());
                return;
            }
            if (field.type === 'integer') {
                data[k] = JSON.stringify(parseInt($("#id_realm_"+k).val().trim(), 10));
            }
        });
        return data;
    }

    function process_response_data(response_data, category) {
        if (!_.has(property_types, category)) {
            blueslip.error('Unknown category ' + category);
            return;
        }

        _.each(response_data, function (value, key) {
            if (value === undefined || !_.has(property_types[category], key)) {
                return;
            }

            var msg;
            var field_info = property_types[category][key];
            var setting_type = field_info.type;

            if (setting_type === 'bool') {
                if (value) {
                    msg = field_info.checked_msg;
                } else {
                    msg = field_info.unchecked_msg;
                }
                ui_report.success(msg,
                                  property_type_status_element(key));
                return;
            }

            if (setting_type === 'text' || setting_type === 'integer') {
                ui_report.success(field_info.msg,
                                  property_type_status_element(key));
                return;
            }
        });
    }

    exports.set_create_stream_permission_dropdwon();
    exports.set_add_emoji_permission_dropdown();

    $("#id_realm_restricted_to_domain").change(function () {
        if (this.checked) {
            $("#id_realm_disallow_disposable_email_addresses").attr("disabled", true);
            $("#id_realm_disallow_disposable_email_addresses_label").parent().addClass("control-label-disabled");
        } else {
            $("#id_realm_disallow_disposable_email_addresses").prop("disabled", false);
            $("#id_realm_disallow_disposable_email_addresses_label").parent().removeClass("control-label-disabled");
        }
    });

    $("#id_realm_invite_required").change(function () {
        settings_ui.disable_sub_setting_onchange(this.checked, "id_realm_invite_by_admins_only", true);
    });

    $("#id_realm_allow_message_editing").change(function () {
        settings_ui.disable_sub_setting_onchange(this.checked, "id_realm_message_content_edit_limit_minutes", true);
    });

    function property_value_element_refers(property_name) {
        if (property_name === 'realm_message_content_edit_limit_minutes') {
            return Math.ceil(page_params.realm_message_content_edit_limit_seconds / 60).toString();
        } else if (property_name === 'realm_create_stream_permission') {
            if (page_params.create_stream_by_admins_only) {
                return "by_admins_only";
            }
            if (page_params.realm_waiting_period_threshold === 0) {
                return "by_anyone";
            }
            if (page_params.realm_waiting_period_threshold === 3) {
                return "by_admin_user_with_three_days_old";
            }
            return "by_admin_user_with_custom_time";
        } else if (property_name === 'realm_add_emoji_by_admins_only') {
            if (page_params.realm_add_emoji_by_admins_only) {
                return "by_admins_only";
            }
            return "by_anyone";
        }
        return;
    }

    exports.extract_property_name = function (elem) {
        return elem.attr('id').split('-').join('_').replace("id_", "");
    };

    function check_property_changed(elem) {
        elem = $(elem);
        var property_name = exports.extract_property_name(elem);
        var changed_val;
        // Check whether the id refers to a property whose name we can't
        // extract from element's id.
        var current_val = property_value_element_refers(property_name);
        if (current_val === undefined) {
            current_val = page_params[property_name];
        }

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
        return subsection.find("input[id^='id_realm_'], select[id^='id_realm_']");
    }

    $('.admin-realm-form').on('change input', 'input, select', function (e) {
        e.preventDefault();
        e.stopPropagation();

        var subsection = $(this).closest('.org-subsection-parent');
        var properties_elements = get_subsection_property_elements(subsection);
        var show_change_process_button = false;
        _.each(properties_elements , function (elem) {
            if (check_property_changed(elem)) {
                show_change_process_button = true;
            }
        });

        var change_process_button = subsection.find('.subsection-header .button');
        change_process_button.first().text(i18n.t("Save"));
        if (show_change_process_button) {
            change_process_button.removeClass('hide').addClass('show');
        } else {
            change_process_button.removeClass('show').addClass('hide');
        }
    });

    function discard_subsection_changes(target) {
        _.each(get_subsection_property_elements(target), function (elem) {
            elem = $(elem);
            var property_name = exports.extract_property_name(elem);
            // Check whether the id refers to a property whose name we can't
            // extract from element's id.
            var property_value = property_value_element_refers(property_name);
            if (property_value === undefined) {
                property_value = page_params[property_name];
            }

            if (typeof property_value === 'boolean') {
                elem.prop('checked', property_value);
            } else if (typeof property_value === 'string' || typeof property_value === 'number') {
                elem.val(property_value);
            } else {
                blueslip.error('Element refers to unknown property ' + property_name);
            }
            // Triggering a change event to handle fading and showing of
            // dependent sub-settings correctly
            elem.change();
        });
    }

    $('.organization').on('click', '.subsection-header .subsection-changes-discard button', function (e) {
        e.preventDefault();
        e.stopPropagation();
        discard_subsection_changes(e.target);
        var subsection = $(e.target).closest('.org-subsection-parent');
        var change_process_buttons = subsection.find('.subsection-header .button');
        change_process_buttons.removeClass('show').addClass('hide');
    });

    exports.save_organization_settings = function (data, save_button, success_continuation) {
        var subsection_parent = save_button.closest('.org-subsection-parent');
        var discard_button = subsection_parent.find('.subsection-changes-discard button');
        var failed_alert_elem = subsection_parent.prevAll('.admin-realm-failed-change-status:first').expectOne();
        save_button.text(i18n.t("Saving"));
        save_button.attr("data-status", "saving");
        channel.patch({
            url: "/json/realm",
            data: data,
            success: function (response_data) {
                discard_button.removeClass('show').addClass('hide');
                failed_alert_elem.hide();
                save_button.attr("data-status", "saved");
                save_button.text(i18n.t("Saved"));
                save_button.removeClass('hide').addClass('show').stop(true).fadeTo(0, 1);
                if (success_continuation !== undefined) {
                    success_continuation(response_data);
                }
            },
            error: function (xhr) {
                save_button.attr("data-status", "failed");
                save_button.text(i18n.t("Save"));
                ui_report.error(i18n.t("Failed"), xhr, failed_alert_elem);
            },
        });
    };

    function get_complete_data_for_subsection(subsection) {
        var opts = {};
        if (subsection === 'msg_editing') {
            var compose_textarea_edit_limit_minutes = $("#id_realm_message_content_edit_limit_minutes").val();
            var new_allow_message_editing = $("#id_realm_allow_message_editing").prop("checked");
            // If allow_message_editing is unchecked, message_content_edit_limit_minutes
            // is irrelevant.  Hence if allow_message_editing is unchecked, and
            // message_content_edit_limit_minutes is poorly formed, we set the latter to
            // a default value to prevent the server from returning an error.
            if (!new_allow_message_editing) {
                if ((parseInt(compose_textarea_edit_limit_minutes, 10).toString() !==
                     compose_textarea_edit_limit_minutes) ||
                        compose_textarea_edit_limit_minutes < 0) {
                    // Realm.DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS / 60
                    compose_textarea_edit_limit_minutes = 10;
                }
            }

            opts.data = {
                allow_message_editing: JSON.stringify(new_allow_message_editing),
                message_content_edit_limit_seconds:
                    JSON.stringify(parseInt(compose_textarea_edit_limit_minutes, 10) * 60),
            };

            opts.success_continuation = function (response_data) {
                if (response_data.allow_message_editing !== undefined) {
                   // We expect message_content_edit_limit_seconds was sent in the
                   // response as well
                   var data_message_content_edit_limit_minutes =
                   Math.ceil(response_data.message_content_edit_limit_seconds / 60);
                   // message_content_edit_limit_seconds could have been changed earlier
                   // in this function, so update the field just in case
                   $("#id_realm_message_content_edit_limit_minutes").val(data_message_content_edit_limit_minutes);
                }
            };
        } else if (subsection === 'other_permissions') {
            var create_stream_permission = $("#id_realm_create_stream_permission").val();
            var add_emoji_permission = $("#id_realm_add_emoji_by_admins_only").val();
            var new_message_retention_days = $("#id_realm_message_retention_days").val();

            if (parseInt(new_message_retention_days, 10).toString() !==
                new_message_retention_days && new_message_retention_days !== "") {
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
        }

        return opts;
    }

    function get_subsection_property_types(subsection) {
        if (_.has(org_settings, subsection)) {
            return org_settings[subsection];
        } else if (_.has(org_permissions, subsection)) {
            return org_permissions[subsection];
        }
    }

    $(".organization").on("click", ".subsection-header .subsection-changes-save button", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var save_button = $(e.target);
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

    $("#id_realm_create_stream_permission").change(function () {
        var create_stream_permission = this.value;
        var node = $("#id_realm_waiting_period_threshold").parent();
        if (create_stream_permission === 'by_admin_user_with_custom_time') {
            node.show();
        } else {
            node.hide();
        }
    });

    $(".organization form.org-profile-form").off('submit').on('submit', function (e) {
        e.preventDefault();
        e.stopPropagation();

        var $alerts = $(".settings-section.show .alert");
        // grab the first alert available and use it for the status.
        var status = $("#admin-realm-name-status");

        var data = populate_data_for_request({}, org_profile);

        channel.patch({
            url: "/json/realm",
            data: data,

            success: function (response_data) {
                $alerts.hide();
                process_response_data(response_data, 'profile');
                // Check if no changes made
                var no_changes_made = true;
                for (var key in response_data) {
                    if (['msg', 'result'].indexOf(key) < 0) {
                        no_changes_made = false;
                    }
                }

                if (no_changes_made) {
                    ui_report.success(i18n.t("No changes to save!"), status);
                }
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed"), xhr, status);
            },
        });
    });

    $(".organization form.org-authentications-form").off('submit').on('submit', function (e) {
        var authentication_methods_status = $("#admin-realm-authentication-methods-status").expectOne();

        var new_auth_methods = {};
        _.each($("#admin_auth_methods_table").find('tr.method_row'), function (method_row) {
            new_auth_methods[$(method_row).data('method')] = $(method_row).find('input').prop('checked');
        });

        authentication_methods_status.hide();

        e.preventDefault();
        e.stopPropagation();

        var url = "/json/realm";
        var data = {
            authentication_methods: JSON.stringify(new_auth_methods),
        };

        channel.patch({
            url: url,
            data: data,
            success: function (response_data) {
                if (response_data.authentication_methods !== undefined) {
                    if (response_data.authentication_methods) {
                        ui_report.success(i18n.t("Authentication methods saved!"), authentication_methods_status);
                    }
                }
                // Check if no changes made
                var no_changes_made = true;
                for (var key in response_data) {
                    if (['msg', 'result'].indexOf(key) < 0) {
                        no_changes_made = false;
                    }
                }
                if (no_changes_made) {
                    ui_report.success(i18n.t("No changes to save!"), authentication_methods_status);
                }
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed"), xhr, authentication_methods_status);
            },
        });
    });

    $("#realm_domains_table").on("click", ".delete_realm_domain", function () {
        var domain = $(this).parents("tr").find(".domain").text();
        var url = "/json/realm/domains/" + domain;
        var realm_domains_info = $(".realm_domains_info");

        channel.del({
            url: url,
            success: function () {
                ui_report.success(i18n.t("Deleted successfully!"), realm_domains_info);
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed"), xhr, realm_domains_info);
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
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed"), xhr, realm_domains_info);
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
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Failed"), xhr, realm_domains_info);
            },
        });
    });

    var notifications_stream_status = $("#admin-realm-notifications-stream-status").expectOne();
    function update_notifications_stream(new_notifications_stream_id) {
        exports.render_notifications_stream_ui(new_notifications_stream_id);
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
        exports.render_signup_notifications_stream_ui(new_signup_notifications_stream_id);
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
            form_data.append('file-'+i, file);
        });

        var spinner = $("#upload_icon_spinner").expectOne();
        loading.make_indicator(spinner, {text: i18n.t("Uploading icon.")});

        channel.post({
            url: '/json/realm/icon',
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success: function () {
                loading.destroy_indicator($("#upload_icon_spinner"));
            },
        });

    }
    realm_icon.build_realm_icon_widget(upload_realm_icon);

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
            url:'/json/realm/deactivate',
            error: function (xhr) {
                ui_report.error(
                    i18n.t("Failed"), xhr, $('#admin-realm-deactivation-status').expectOne()
                );
            },
        });
    });

}
exports.set_up = function () {
    i18n.ensure_i18n(_set_up);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_org;
}
