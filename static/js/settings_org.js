var settings_org = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
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
        $("#id_realm_restricted_to_domain").prop("disabled", true);
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


exports.toggle_name_change_display = function () {
    if (!meta.loaded) {
        return;
    }

    if ($('#full_name').attr('disabled')) {
        $('#full_name').prop('disabled', false);
    } else {
        $('#full_name').attr('disabled', 'disabled');
    }
    $(".change_name_tooltip").toggle();
};

exports.toggle_email_change_display = function () {
    if (!meta.loaded) {
        return;
    }

    $("#change_email").toggle();
    $(".change_email_tooltip").toggle();
};

exports.toggle_allow_message_editing_pencil = function () {
    if (!meta.loaded) {
        return;
    }

    $(".on_hover_topic_edit").toggle();
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
        name: "admin-realm-dropdown-stream-list",
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

    $("#id_realm_notifications_stream .dropdown-search").click(function (e) {
        e.stopPropagation();
    });

    $("#id_realm_notifications_stream .dropdown-toggle").click(function () {
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
        exports.populate_notifications_stream_dropdown(stream_data.get_streams_for_settings_page());
    }
    exports.render_notifications_stream_ui(page_params.realm_notifications_stream_id);

    // Populate realm domains
    exports.populate_realm_domains(page_params.realm_domains);

    // Populate authentication methods table
    exports.populate_auth_methods(page_params.realm_authentication_methods);

    // create property_types object
    var property_types = {
        profile: {
            name: {
                type: 'text',
                msg: i18n.t("Name changed!"),
            },
            description: {
                type: 'text',
                msg: i18n.t("Description changed!"),
            },
        },

        settings: {
            default_language: {
                type: 'text',
                msg: i18n.t("Default language changed!"),
            },
            allow_edit_history: {
                type: 'bool',
                checked_msg: i18n.t("Users can view message edit history!"),
                unchecked_msg: i18n.t("Users can no longer view message edit history!"),
            },
            mandatory_topics: {
                type: 'bool',
                checked_msg: i18n.t("Topics are required in messages to streams!"),
                unchecked_msg: i18n.t("Topics are not required in messages to streams!"),
            },
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
        },

        permissions: {
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
            invite_by_admins_only: {
                type: 'bool',
                checked_msg: i18n.t("New users must be invited by an admin!"),
                unchecked_msg: i18n.t("Any user may now invite new users!"),
            },
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
            create_stream_by_admins_only: {
                type: 'bool',
                checked_msg: i18n.t("Only administrators may now create new streams!"),
                unchecked_msg: i18n.t("Any user may now create new streams!"),
            },
            add_emoji_by_admins_only: {
                type: 'bool',
                checked_msg: i18n.t("Only administrators may now add new emoji!"),
                unchecked_msg: i18n.t("Any user may now add new emoji!"),
            },
            waiting_period_threshold: {
                type: 'integer',
                msg: i18n.t("Waiting period threshold changed!"),
            },
        },
    };

    function populate_data_for_request(data, category) {
        _.each(property_types[category], function (v, k) {
            var field = property_types[category][k];
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

            if (setting_type === 'text') {
                ui_report.success(field_info.msg,
                                  property_type_status_element(key));
                return;
            }
        });
    }

    $("#id_realm_invite_required").change(function () {
        if (this.checked) {
            $("#id_realm_invite_by_admins_only").prop("disabled", false);
            $("#id_realm_invite_by_admins_only_label").parent().removeClass("control-label-disabled");
        } else {
            $("#id_realm_invite_by_admins_only").attr("disabled", true);
            $("#id_realm_invite_by_admins_only_label").parent().addClass("control-label-disabled");
        }
    });

    $("#id_realm_allow_message_editing").change(function () {
        if (this.checked) {
            $("#id_realm_message_content_edit_limit_minutes").prop("disabled", false);
            $("#id_realm_message_content_edit_limit_minutes_label").parent().removeClass("control-label-disabled");
        } else {
            $("#id_realm_message_content_edit_limit_minutes").attr("disabled", true);
            $("#id_realm_message_content_edit_limit_minutes_label").parent().addClass("control-label-disabled");
        }
    });

    $(".organization").on("submit", "form.org-settings-form", function (e) {
        e.preventDefault();
        e.stopPropagation();

        _.each(property_types.settings, function (v, k) {
            property_type_status_element(k).hide();
        });

        var message_editing_status = $("#admin-realm-message-editing-status").expectOne();
        // grab the first alert available and use it for the status.
        var $alerts = $(".settings-section.show .alert").hide();
        // grab the first alert available and use it for the status.
        var status = $("#admin-realm-notifications-stream-status");

        var new_message_content_edit_limit_minutes = $("#id_realm_message_content_edit_limit_minutes").val();
        var new_allow_message_editing = $("#id_realm_allow_message_editing").prop("checked");

        // If allow_message_editing is unchecked, message_content_edit_limit_minutes
        // is irrelevant.  Hence if allow_message_editing is unchecked, and
        // message_content_edit_limit_minutes is poorly formed, we set the latter to
        // a default value to prevent the server from returning an error.
        if (!new_allow_message_editing) {
            if ((parseInt(new_message_content_edit_limit_minutes, 10).toString() !==
                 new_message_content_edit_limit_minutes) ||
                new_message_content_edit_limit_minutes < 0) {
            // Realm.DEFAULT_MESSAGE_CONTENT_EDIT_LIMIT_SECONDS / 60
            new_message_content_edit_limit_minutes = 10;
            }
        }

        var url = "/json/realm";
        var data = {};
        data = populate_data_for_request({
            allow_message_editing: JSON.stringify(new_allow_message_editing),
            message_content_edit_limit_seconds:
                JSON.stringify(parseInt(new_message_content_edit_limit_minutes, 10) * 60),
        }, 'settings');

        channel.patch({
            url: url,
            data: data,

            success: function (response_data) {
                $alerts.hide();
                if (response_data.allow_message_editing !== undefined) {
                    // We expect message_content_edit_limit_seconds was sent in the
                    // response as well
                    var data_message_content_edit_limit_minutes =
                        Math.ceil(response_data.message_content_edit_limit_seconds / 60);
                    if (response_data.allow_message_editing) {
                        if (response_data.message_content_edit_limit_seconds > 0) {
                            ui_report.success(
                                i18n.t("Users can now edit topics for all their messages, and the content of messages which are less than __num_minutes__ minutes old.",
                                       {num_minutes : data_message_content_edit_limit_minutes}),
                                message_editing_status);
                        } else {
                            ui_report.success(i18n.t("Users can now edit the content and topics of all their past messages!"), message_editing_status);
                        }
                    } else {
                        ui_report.success(i18n.t("Users can no longer edit their past messages!"), message_editing_status);
                    }
                    // message_content_edit_limit_seconds could have been changed earlier
                    // in this function, so update the field just in case
                    $("#id_realm_message_content_edit_limit_minutes").val(data_message_content_edit_limit_minutes);
                }

                process_response_data(response_data, 'settings');
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
                $alerts.hide();
                ui_report.error(i18n.t("Failed"), xhr, status);
            },
        });
    });

    $(".organization").on("submit", "form.org-permissions-form", function (e) {
        var $alerts = $(".settings-section.show .alert").hide();
        // grab the first alert available and use it for the status.
        var status = $("#admin-realm-restricted-to-domain-status");

        var waiting_period_threshold_status = $("#admin-realm-waiting-period-threshold-status").expectOne();
        status.hide();

        e.preventDefault();
        e.stopPropagation();

        var new_message_retention_days = $("#id_realm_message_retention_days").val();

        if (parseInt(new_message_retention_days, 10).toString() !==
            new_message_retention_days && new_message_retention_days !== "") {
                new_message_retention_days = "";
        }

        // take the existing object and apply the rest of the properties.
        var data = populate_data_for_request({
            message_retention_days: new_message_retention_days !== "" ? JSON.stringify(parseInt(new_message_retention_days, 10)) : null,
        }, 'permissions');


        channel.patch({
            url: "/json/realm",
            data: data,
            success: function (response_data) {
                $alerts.hide();
                if (response_data.waiting_period_threshold !== undefined) {
                    if (response_data.waiting_period_threshold >= 0) {
                        ui_report.success(i18n.t("Waiting period threshold changed!"), waiting_period_threshold_status);
                    }
                }

                process_response_data(response_data, 'permissions');

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
                $alerts.hide();
                ui_report.error(i18n.t("Failed"), xhr, status);
            },
        });
    });

    $(".organization").on("submit", "form.org-profile-form", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var $alerts = $(".settings-section.show .alert");
        // grab the first alert available and use it for the status.
        var status = $("#admin-realm-name-status");

        var data = populate_data_for_request({}, 'profile');

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

    $(".organization").on("submit", "form.org-authentications-form", function (e) {
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
        var realm_domains_info = $("#realm_domains_modal").find(".realm_domains_info");

        channel.del({
            url: url,
            success: function () {
                realm_domains_info.removeClass("text-error");
                realm_domains_info.addClass("text-success");
                realm_domains_info.text(i18n.t("Deleted successfully!"));
            },
            error: function (xhr) {
                realm_domains_info.removeClass("text-success");
                realm_domains_info.addClass("text-error");
                realm_domains_info.text(JSON.parse(xhr.responseText).msg);
            },
        });
    });

    $("#submit-add-realm-domain").click(function () {
        var realm_domains_info = $("#realm_domains_modal").find(".realm_domains_info");
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
                $("#id_realm_restricted_to_domain").prop("disabled", false);
                realm_domains_info.removeClass("text-error");
                realm_domains_info.addClass("text-success");
                realm_domains_info.text(i18n.t("Added successfully!"));
            },
            error: function (xhr) {
                realm_domains_info.removeClass("text-success");
                realm_domains_info.addClass("text-error");
                realm_domains_info.text(JSON.parse(xhr.responseText).msg);
            },
        });
    });

    $("#realm_domains_table").on("change", ".allow-subdomains", function (e) {
        e.stopPropagation();
        var realm_domains_info = $("#realm_domains_modal").find(".realm_domains_info");
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
                realm_domains_info.removeClass("text-error");
                realm_domains_info.addClass("text-success");
                if (allow_subdomains) {
                    realm_domains_info.text(i18n.t("Update successful: Subdomains allowed for __domain__",
                                             {domain: domain}));
                } else {
                    realm_domains_info.text(i18n.t("Update successful: Subdomains no longer allowed for __domain__",
                                             {domain: domain}));
                }
            },
            error: function (xhr) {
                realm_domains_info.removeClass("text-success");
                realm_domains_info.addClass("text-error");
                realm_domains_info.text(JSON.parse(xhr.responseText).msg);
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

}
exports.set_up = function () {
    i18n.ensure_i18n(_set_up);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_org;
}
