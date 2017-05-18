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
    $("#realm_restricted_to_domains_label").text(i18n.t("New users restricted to the following domains: __domains__", {domains: domains}));

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
        $('#full_name').removeAttr('disabled');
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

exports.update_realm_description = function (description) {
    if (!meta.loaded) {
        return;
    }

    $('#id_realm_description').val(description);
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
    }
};

exports.set_up = function () {
    meta.loaded = true;

    loading.make_indicator($('#admin_page_auth_methods_loading_indicator'));

    // Populate realm domains
    exports.populate_realm_domains(page_params.realm_domains);

    // Populate authentication methods table
    exports.populate_auth_methods(page_params.realm_authentication_methods);

    $("#id_realm_invite_required").change(function () {
        if (this.checked) {
            $("#id_realm_invite_by_admins_only").removeAttr("disabled");
            $("#id_realm_invite_by_admins_only_label").parent().removeClass("control-label-disabled");
        } else {
            $("#id_realm_invite_by_admins_only").attr("disabled", true);
            $("#id_realm_invite_by_admins_only_label").parent().addClass("control-label-disabled");
        }
    });

    $("#id_realm_allow_message_editing").change(function () {
        if (this.checked) {
            $("#id_realm_message_content_edit_limit_minutes").removeAttr("disabled");
            $("#id_realm_message_content_edit_limit_minutes_label").parent().removeClass("control-label-disabled");
        } else {
            $("#id_realm_message_content_edit_limit_minutes").attr("disabled", true);
            $("#id_realm_message_content_edit_limit_minutes_label").parent().addClass("control-label-disabled");
        }
    });

    $(".organization").on("submit", "form.admin-realm-form", function (e) {
        // TODO: We actually have three forms named admin-realm-form.  We really
        //       should break out three separate forms.

        var name_status = $("#admin-realm-name-status").expectOne();
        var description_status = $("#admin-realm-description-status").expectOne();
        var restricted_to_domain_status = $("#admin-realm-restricted-to-domain-status").expectOne();
        var invite_required_status = $("#admin-realm-invite-required-status").expectOne();
        var invite_by_admins_only_status = $("#admin-realm-invite-by-admins-only-status").expectOne();
        var inline_image_preview_status = $("#admin-realm-inline-image-preview-status").expectOne();
        var inline_url_embed_preview_status = $("#admin-realm-inline-url-embed-preview-status").expectOne();
        var authentication_methods_status = $("#admin-realm-authentication-methods-status").expectOne();
        var create_stream_by_admins_only_status = $("#admin-realm-create-stream-by-admins-only-status").expectOne();
        var name_changes_disabled_status = $("#admin-realm-name-changes-disabled-status").expectOne();
        var email_changes_disabled_status = $("#admin-realm-email-changes-disabled-status").expectOne();
        var add_emoji_by_admins_only_status = $("#admin-realm-add-emoji-by-admins-only-status").expectOne();
        var message_editing_status = $("#admin-realm-message-editing-status").expectOne();
        var default_language_status = $("#admin-realm-default-language-status").expectOne();
        var waiting_period_threshold_status = $("#admin-realm-waiting_period_threshold_status").expectOne();
        name_status.hide();
        description_status.hide();
        restricted_to_domain_status.hide();
        invite_required_status.hide();
        invite_by_admins_only_status.hide();
        inline_image_preview_status.hide();
        inline_url_embed_preview_status.hide();
        authentication_methods_status.hide();
        create_stream_by_admins_only_status.hide();
        name_changes_disabled_status.hide();
        email_changes_disabled_status.hide();
        add_emoji_by_admins_only_status.hide();
        message_editing_status.hide();
        default_language_status.hide();
        waiting_period_threshold_status.hide();

        e.preventDefault();
        e.stopPropagation();

        var new_name = $("#id_realm_name").val();
        var new_description = $("#id_realm_description").val().trim();
        var new_restricted = $("#id_realm_restricted_to_domain").prop("checked");
        var new_invite = $("#id_realm_invite_required").prop("checked");
        var new_invite_by_admins_only = $("#id_realm_invite_by_admins_only").prop("checked");
        var new_inline_image_preview = $("#id_realm_inline_image_preview").prop("checked");
        var new_inline_url_embed_preview = $("#id_realm_inline_url_embed_preview").prop("checked");
        var new_create_stream_by_admins_only = $("#id_realm_create_stream_by_admins_only").prop("checked");
        var new_name_changes_disabled = $("#id_realm_name_changes_disabled").prop("checked");
        var new_email_changes_disabled = $("#id_realm_email_changes_disabled").prop("checked");
        var new_add_emoji_by_admins_only = $("#id_realm_add_emoji_by_admins_only").prop("checked");
        var new_allow_message_editing = $("#id_realm_allow_message_editing").prop("checked");
        var new_message_content_edit_limit_minutes = $("#id_realm_message_content_edit_limit_minutes").val();
        var new_message_retention_days = $("#id_realm_message_retention_days").val();
        var new_default_language = $("#id_realm_default_language").val();
        var new_waiting_period_threshold = $("#id_realm_waiting_period_threshold").val();
        var new_auth_methods = {};
        _.each($("#admin_auth_methods_table").find('tr.method_row'), function (method_row) {
            new_auth_methods[$(method_row).data('method')] = $(method_row).find('input').prop('checked');
        });
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
        if (parseInt(new_message_retention_days, 10).toString() !==
            new_message_retention_days && new_message_retention_days !== "") {
                new_message_retention_days = "";
        }

        var url = "/json/realm";
        var data = {
            name: JSON.stringify(new_name),
            description: JSON.stringify(new_description),
            restricted_to_domain: JSON.stringify(new_restricted),
            invite_required: JSON.stringify(new_invite),
            invite_by_admins_only: JSON.stringify(new_invite_by_admins_only),
            inline_image_preview: JSON.stringify(new_inline_image_preview),
            inline_url_embed_preview: JSON.stringify(new_inline_url_embed_preview),
            authentication_methods: JSON.stringify(new_auth_methods),
            create_stream_by_admins_only: JSON.stringify(new_create_stream_by_admins_only),
            name_changes_disabled: JSON.stringify(new_name_changes_disabled),
            email_changes_disabled: JSON.stringify(new_email_changes_disabled),
            add_emoji_by_admins_only: JSON.stringify(new_add_emoji_by_admins_only),
            allow_message_editing: JSON.stringify(new_allow_message_editing),
            message_content_edit_limit_seconds:
                JSON.stringify(parseInt(new_message_content_edit_limit_minutes, 10) * 60),
            message_retention_days: new_message_retention_days !== "" ? JSON.stringify(parseInt(new_message_retention_days, 10)) : null,
            default_language: JSON.stringify(new_default_language),
            waiting_period_threshold: JSON.stringify(parseInt(new_waiting_period_threshold, 10)),
        };

        channel.patch({
            url: url,
            data: data,
            success: function (response_data) {
                if (response_data.name !== undefined) {
                    ui_report.success(i18n.t("Name changed!"), name_status);
                }
                if (response_data.description !== undefined) {
                    ui_report.success(i18n.t("Description changed!"), description_status);
                }
                if (response_data.restricted_to_domain !== undefined) {
                    if (response_data.restricted_to_domain) {
                        ui_report.success(i18n.t("New user e-mails now restricted to certain domains!"), restricted_to_domain_status);
                    } else {
                        ui_report.success(i18n.t("New users may have arbitrary e-mails!"), restricted_to_domain_status);
                    }
                }
                if (response_data.invite_required !== undefined) {
                    if (response_data.invite_required) {
                        ui_report.success(i18n.t("New users must be invited by e-mail!"), invite_required_status);
                    } else {
                        ui_report.success(i18n.t("New users may sign up online!"), invite_required_status);
                    }
                }
                if (response_data.invite_by_admins_only !== undefined) {
                    if (response_data.invite_by_admins_only) {
                        ui_report.success(i18n.t("New users must be invited by an admin!"), invite_by_admins_only_status);
                    } else {
                        ui_report.success(i18n.t("Any user may now invite new users!"), invite_by_admins_only_status);
                    }
                }
                if (response_data.inline_image_preview !== undefined) {
                    if (response_data.inline_image_preview) {
                        ui_report.success(i18n.t("Previews of uploaded and linked images will be shown!"), inline_image_preview_status);
                    } else {
                        ui_report.success(i18n.t("Previews of uploaded and linked images will not be shown!"), inline_image_preview_status);
                    }
                }
                if (response_data.inline_url_embed_preview !== undefined) {
                    if (response_data.inline_url_embed_preview) {
                        ui_report.success(i18n.t("Previews for linked websites will be shown!"), inline_url_embed_preview_status);
                    } else {
                        ui_report.success(i18n.t("Previews for linked websites will not be shown!"), inline_url_embed_preview_status);
                    }
                }
                if (response_data.create_stream_by_admins_only !== undefined) {
                    if (response_data.create_stream_by_admins_only) {
                        ui_report.success(i18n.t("Only administrators may now create new streams!"), create_stream_by_admins_only_status);
                    } else {
                        ui_report.success(i18n.t("Any user may now create new streams!"), create_stream_by_admins_only_status);
                    }
                }
                if (response_data.name_changes_disabled !== undefined) {
                    if (response_data.name_changes_disabled) {
                        ui_report.success(i18n.t("Users cannot change their name!"), name_changes_disabled_status);
                    } else {
                        ui_report.success(i18n.t("Users may now change their name!"), name_changes_disabled_status);
                    }
                }
                if (response_data.email_changes_disabled !== undefined) {
                    if (response_data.email_changes_disabled) {
                        ui_report.success(i18n.t("Users cannot change their email!"), email_changes_disabled_status);
                    } else {
                        ui_report.success(i18n.t("Users may now change their email!"), email_changes_disabled_status);
                    }
                }
                if (response_data.add_emoji_by_admins_only !== undefined) {
                    if (response_data.add_emoji_by_admins_only) {
                        ui_report.success(i18n.t("Only administrators may now add new emoji!"), add_emoji_by_admins_only_status);
                    } else {
                        ui_report.success(i18n.t("Any user may now add new emoji!"), add_emoji_by_admins_only_status);
                    }
                }
                if (response_data.authentication_methods !== undefined) {
                    if (response_data.authentication_methods) {
                        ui_report.success(i18n.t("Authentication methods saved!"), authentication_methods_status);
                    }
                }
                if (response_data.allow_message_editing !== undefined) {
                    // We expect message_content_edit_limit_seconds was sent in the
                    // response as well
                    var data_message_content_edit_limit_minutes =
                        Math.ceil(response_data.message_content_edit_limit_seconds / 60);
                    if (response_data.allow_message_editing) {
                        if (response_data.message_content_edit_limit_seconds > 0) {
                            ui_report.success(i18n.t("Users can now edit topics for all their messages,"
                                                      +" and the content of messages which are less than __num_minutes__ minutes old.",
                                                     {num_minutes :
                                                       data_message_content_edit_limit_minutes}),
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
                if (response_data.default_language !== undefined) {
                    if (response_data.default_language) {
                        ui_report.success(i18n.t("Default language changed!"), default_language_status);
                    }
                }
                if (response_data.waiting_period_threshold !== undefined) {
                    if (response_data.waiting_period_threshold > 0) {
                        ui_report.success(i18n.t("Waiting period threshold changed!"), waiting_period_threshold_status);
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
                    ui_report.success(i18n.t("No changes to save!"), name_status);
                }
            },
            error: function (xhr) {
                var reason = $.parseJSON(xhr.responseText).reason;
                if (reason === "no authentication") {
                    ui_report.error(i18n.t("Failed"), xhr, authentication_methods_status);
                } else {
                    ui_report.error(i18n.t("Failed"), xhr, name_status);
                }
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

    function upload_realm_icon(file_input) {
        var form_data = new FormData();

        form_data.append('csrfmiddlewaretoken', csrf_token);
        jQuery.each(file_input[0].files, function (i, file) {
            form_data.append('file-'+i, file);
        });

        var spinner = $("#upload_icon_spinner").expectOne();
        loading.make_indicator(spinner, {text: i18n.t("Uploading icon.")});

        channel.put({
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

};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_org;
}
