var admin = (function () {

var meta = {};
var exports = {};
var all_streams = [];

exports.show_or_hide_menu_item = function () {
    var item = $('.admin-menu-item').expectOne();
    if (page_params.is_admin) {
        item.show();
    } else {
        item.hide();
    }
};

function get_user_info(email) {
    var self = {};
    self.user_row = $("tr[id='user_" + email + "']");
    self.form_row = $("tr[id='user_form_" + email + "']");

    return self;
}

function get_email_for_user_row(row) {
    var email = row.find('.email').text();
    return email;
}

exports.update_user_full_name = function (email, new_full_name) {
    var user_info = get_user_info(email);

    var user_row = user_info.user_row;
    var form_row = user_info.form_row;

    // Update the full name in the table
    user_row.find(".user_name").text(new_full_name);
    form_row.find("input[name='full_name']").val(new_full_name);

    // Hide name change form
    form_row.hide();
    user_row.show();
};

function failed_listing_users(xhr) {
    loading.destroy_indicator($('#subs_page_loading_indicator'));
    ui.report_error(i18n.t("Error listing users or bots"), xhr, $("#administration-status"));
}

function failed_listing_streams(xhr) {
    ui.report_error(i18n.t("Error listing streams"), xhr, $("#administration-status"));
}

function failed_changing_name(xhr) {
    ui.report_error(i18n.t("Error changing name"), xhr, $("#administration-status"));
}

function populate_users(realm_people_data) {
    var users_table = $("#admin_users_table");
    var deactivated_users_table = $("#admin_deactivated_users_table");
    var bots_table = $("#admin_bots_table");
    // Clear table rows, but not the table headers
    users_table.find("tr.user_row").remove();
    deactivated_users_table.find("tr.user_row").remove();
    bots_table.find("tr.user_row").remove();

    var active_users = [];
    var deactivated_users = [];
    var bots = [];
    _.each(realm_people_data.members, function (user) {
        user.is_active_human = user.is_active && !user.is_bot;
        if (user.is_bot) {
            bots.push(user);
        } else if (user.is_active) {
            active_users.push(user);
        } else {
            deactivated_users.push(user);
        }
    });

    active_users = _.sortBy(active_users, 'full_name');
    deactivated_users = _.sortBy(deactivated_users, 'full_name');
    bots = _.sortBy(bots, 'full_name');

    _.each(bots, function (user) {
        bots_table.append(templates.render("admin_user_list", {user: user}));
    });
    _.each(active_users, function (user) {
        users_table.append(templates.render("admin_user_list", {user: user}));
    });
    _.each(deactivated_users, function (user) {
        deactivated_users_table.append(templates.render("admin_user_list", {user: user}));
    });
    loading.destroy_indicator($('#admin_page_users_loading_indicator'));
    loading.destroy_indicator($('#admin_page_bots_loading_indicator'));
    loading.destroy_indicator($('#admin_page_deactivated_users_loading_indicator'));
}

function populate_streams(streams_data) {
    var streams_table = $("#admin_streams_table").expectOne();
    all_streams = streams_data;
    streams_table.find("tr.stream_row").remove();
    _.each(streams_data.streams, function (stream) {
        streams_table.append(templates.render("admin_streams_list", {stream: stream}));
    });
    loading.destroy_indicator($('#admin_page_streams_loading_indicator'));
}

function populate_default_streams(streams_data) {
    var default_streams_table = $("#admin_default_streams_table").expectOne();
    _.each(streams_data, function (stream) {
        default_streams_table.append(templates.render("admin_default_streams_list", {stream: stream}));
    });
    loading.destroy_indicator($('#admin_page_default_streams_loading_indicator'));
}

function get_non_default_streams_names(streams_data) {
    var non_default_streams_names = [];
    var default_streams_names = [];

    _.each(page_params.realm_default_streams, function (default_stream) {
        default_streams_names.push(default_stream.name);
    });

    _.each(streams_data.streams, function (stream) {
        if (default_streams_names.indexOf(stream.name) < 0) {
            non_default_streams_names.push(stream.name);
        }
    });
    return non_default_streams_names;
}

exports.update_default_streams_table = function () {
    if ($('#administration').hasClass('active')) {
        $("#admin_default_streams_table").expectOne().find("tr.default_stream_row").remove();
        populate_default_streams(page_params.realm_default_streams);
    }
};

function make_stream_default(stream_name) {
    var data = {
        stream_name: stream_name
    };

    channel.post({
        url: '/json/default_streams',
        data: data,
        error: function (xhr) {
            if (xhr.status.toString().charAt(0) === "4") {
                $(".active_stream_row button").closest("td").html(
                    $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg));
            } else {
                $(".active_stream_row button").text("Failed!");
            }
        }
    });
}

function stringify_list_with_conjunction(lst, conjunction) {
    if (lst.length === 0) {
        return '';
    } else if (lst.length === 1) {
        return lst.toString();
    } else if (lst.length === 2) {
        return lst.join(" " + conjunction + " ");
    }
    return lst.slice(0, lst.length-1).join(", ") + ", " + conjunction + " " + lst[lst.length-1].toString();
}

exports.populate_emoji = function (emoji_data) {
    var emoji_table = $('#admin_emoji_table').expectOne();
    emoji_table.find('tr.emoji_row').remove();
    _.each(emoji_data, function (data, name) {
        emoji_table.append(templates.render('admin_emoji_list', {
            emoji: {
                name: name, source_url: data.source_url,
                display_url: data.display_url,
                author: data.author
            }
        }));
    });
    loading.destroy_indicator($('#admin_page_emoji_loading_indicator'));
};

exports.populate_filters = function (filters_data) {
    var filters_table = $("#admin_filters_table").expectOne();
    filters_table.find("tr.filter_row").remove();
    _.each(filters_data, function (filter) {
        filters_table.append(
            templates.render(
                "admin_filter_list", {
                    filter: {
                        pattern: filter[0],
                        url_format_string: filter[1],
                        id: filter[2]
                    }
                }
            )
        );
    });
    loading.destroy_indicator($('#admin_page_filters_loading_indicator'));
};

exports.reset_realm_default_language = function () {
    $("#id_realm_default_language").val(page_params.realm_default_language);
};

exports.populate_auth_methods = function (auth_methods) {
    var auth_methods_table = $("#admin_auth_methods_table").expectOne();
    auth_methods_table.find('tr.method_row').remove();
    _.each(_.keys(auth_methods).sort(), function (key) {
        auth_methods_table.append(templates.render('admin_auth_methods_list', {
            method: {
                method: key,
                enabled: auth_methods[key]
            }
        }));
    });
    loading.destroy_indicator($('#admin_page_auth_methods_loading_indicator'));
};

function _setup_page() {
    var domains_string = stringify_list_with_conjunction(page_params.domains, "or");
    var atdomains = page_params.domains.slice();
    var i;
    for (i = 0; i < atdomains.length; i += 1) {
        atdomains[i] = '@' + atdomains[i];
    }
    var atdomains_string = stringify_list_with_conjunction(atdomains, "or");
    var options = {
        realm_name: page_params.realm_name,
        domains_string: domains_string,
        atdomains_string: atdomains_string,
        realm_restricted_to_domain: page_params.realm_restricted_to_domain,
        realm_invite_required: page_params.realm_invite_required,
        realm_invite_by_admins_only: page_params.realm_invite_by_admins_only,
        realm_authentication_methods: page_params.realm_authentication_methods,
        realm_create_stream_by_admins_only: page_params.realm_create_stream_by_admins_only,
        realm_add_emoji_by_admins_only: page_params.realm_add_emoji_by_admins_only,
        realm_allow_message_editing: page_params.realm_allow_message_editing,
        realm_message_content_edit_limit_minutes:
            Math.ceil(page_params.realm_message_content_edit_limit_seconds / 60),
        language_list: page_params.language_list,
        realm_default_language: page_params.realm_default_language,
        realm_waiting_period_threshold: page_params.realm_waiting_period_threshold
    };
    var admin_tab = templates.render('admin_tab', options);
    $("#administration").html(admin_tab);
    $("#administration-status").expectOne().hide();
    $("#admin-realm-name-status").expectOne().hide();
    $("#admin-realm-restricted-to-domain-status").expectOne().hide();
    $("#admin-realm-invite-required-status").expectOne().hide();
    $("#admin-realm-invite-by-admins-only-status").expectOne().hide();
    $("#admin-realm-authentication-methods-status").expectOne().hide();
    $("#admin-realm-create-stream-by-admins-only-status").expectOne().hide();
    $("#admin-realm-add-emoji-by-admins-only-status").expectOne().hide();
    $("#admin-realm-message-editing-status").expectOne().hide();
    $("#admin-realm-default-language-status").expectOne().hide();
    $('#admin-realm-waiting_period_threshold_status').expectOne().hide();
    $("#admin-emoji-status").expectOne().hide();
    $('#admin-filter-status').expectOne().hide();
    $('#admin-filter-pattern-status').expectOne().hide();
    $('#admin-filter-format-status').expectOne().hide();

    $("#id_realm_default_language").val(page_params.realm_default_language);

    // create loading indicators
    loading.make_indicator($('#admin_page_users_loading_indicator'));
    loading.make_indicator($('#admin_page_bots_loading_indicator'));
    loading.make_indicator($('#admin_page_streams_loading_indicator'));
    loading.make_indicator($('#admin_page_deactivated_users_loading_indicator'));
    loading.make_indicator($('#admin_page_emoji_loading_indicator'));
    loading.make_indicator($('#admin_page_auth_methods_loading_indicator'));
    loading.make_indicator($('#admin_page_filters_loading_indicator'));

    // Populate users and bots tables
    channel.get({
        url:      '/json/users',
        idempotent: true,
        timeout:  10*1000,
        success: populate_users,
        error: failed_listing_users
    });

    // Populate streams table
    channel.get({
        url:      '/json/streams?include_public=true&include_subscribed=true&include_default=true',
        timeout:  10*1000,
        idempotent: true,
        success: populate_streams,
        error: failed_listing_streams
    });

    // Populate authentication methods table
    exports.populate_auth_methods(page_params.realm_authentication_methods);

    // Populate emoji table
    exports.populate_emoji(page_params.realm_emoji);
    exports.update_default_streams_table();

    // Populate filters table
    exports.populate_filters(page_params.realm_filters);

    // Setup click handlers
    $(".admin_user_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var row = $(e.target).closest(".user_row");

        var user_name = row.find('.user_name').text();
        var email = get_email_for_user_row(row);

        $("#deactivation_user_modal .email").text(email);
        $("#deactivation_user_modal .user_name").text(user_name);
        $("#deactivation_user_modal").modal("show");

        meta.current_deactivate_user_modal_row = row;
    });

    $(".admin_stream_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        $(".active_stream_row").removeClass("active_stream_row");
        var row = $(e.target).closest(".stream_row");
        row.addClass("active_stream_row");

        var stream_name = row.find('.stream_name').text();

        $("#deactivation_stream_modal .stream_name").text(stream_name);
        $("#deactivation_stream_modal").modal("show");
    });

    $(".admin_default_stream_table").on("click", ".remove-default-stream", function (e) {
        e.preventDefault();
        e.stopPropagation();

        $(".active_default_stream_row").removeClass("active_default_stream_row");
        var row = $(e.target).closest(".default_stream_row");
        row.addClass("active_default_stream_row");
        var stream_name = row.find('.default_stream_name').text();

        channel.del({
            url: '/json/default_streams'+ '?' + $.param({stream_name: stream_name}),
            error: function (xhr) {
                if (xhr.status.toString().charAt(0) === "4") {
                    $(".active_default_stream_row button").closest("td").html(
                    $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg));
                } else {
                    $(".active_default_stream_row button").text("Failed!");
                }
            },
            success: function () {
                var row = $(".active_default_stream_row");
                row.remove();
            }
        });
    });

    $('.create_default_stream').keypress(function (e) {
        if (e.which === 13) {
            e.preventDefault();
            e.stopPropagation();
        }
    });

    $('.create_default_stream').typeahead({
        items: 5,
        fixed: true,
        source: function () {
            return get_non_default_streams_names(all_streams);
        },
        highlight: true,
        updater: function (stream_name) {
            make_stream_default(stream_name);
        }
    });

    $("#do_deactivate_user_button").expectOne().click(function () {
        var email = meta.current_deactivate_user_modal_row.find(".email").text();

        if ($("#deactivation_user_modal .email").html() !== email) {
            blueslip.error("User deactivation canceled due to non-matching fields.");
            ui.report_message("Deactivation encountered an error. Please reload and try again.",
               $("#home-error"), 'alert-error');
        }
        $("#deactivation_user_modal").modal("hide");
        meta.current_deactivate_user_modal_row.find("button").eq(0).prop("disabled", true).text("Working…");
        channel.del({
            url: '/json/users/' + email,
            error: function (xhr) {
                if (xhr.status.toString().charAt(0) === "4") {
                    meta.current_deactivate_user_modal_row.find("button").closest("td").html(
                        $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg)
                    );
                } else {
                     meta.current_deactivate_user_modal_row.find("button").text("Failed!");
                }
            },
            success: function () {
                var button = meta.current_deactivate_user_modal_row.find("button.deactivate");
                button.prop("disabled", false);
                button.addClass("btn-warning reactivate").removeClass("btn-danger deactivate");
                button.text(i18n.t("Reactivate"));
                meta.current_deactivate_user_modal_row.addClass("deactivated_user");
                meta.current_deactivate_user_modal_row.find(".user-admin-settings").hide();
            }
        });
    });

    $(".admin_bot_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var row = $(e.target).closest(".user_row");

        var email = get_email_for_user_row(row);

        channel.del({
            url: '/json/bots/' + email,
            error: function (xhr) {
                if (xhr.status.toString().charAt(0) === "4") {
                    row.find("button").closest("td").html(
                        $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg)
                    );
                } else {
                    row.find("button").text("Failed!");
                }
            },
            success: function () {
                var button = row.find("button.deactivate");
                button.addClass("btn-warning");
                button.removeClass("btn-danger");
                button.addClass("reactivate");
                button.removeClass("deactivate");
                button.text(i18n.t("Reactivate"));
                row.addClass("deactivated_user");
            }
        });
    });

    $(".admin_user_table, .admin_bot_table").on("click", ".reactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        // Go up the tree until we find the user row, then grab the email element
        var row = $(e.target).closest(".user_row");
        var email = get_email_for_user_row(row);

        channel.post({
            url: '/json/users/' + email + "/reactivate",
            error: function (xhr) {
                var button = row.find("button");
                if (xhr.status.toString().charAt(0) === "4") {
                    button.closest("td").html(
                        $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg)
                    );
                } else {
                     button.text(i18n.t("Failed!"));
                }
            },
            success: function () {
                row.find(".user-admin-settings").show();
                var button = row.find("button.reactivate");
                button.addClass("btn-danger");
                button.removeClass("btn-warning");
                button.addClass("deactivate");
                button.removeClass("reactivate");
                button.text(i18n.t("Deactivate"));
                row.removeClass("deactivated_user");
            }
        });
    });

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

    $(".administration").on("submit", "form.admin-realm-form", function (e) {
        var name_status = $("#admin-realm-name-status").expectOne();
        var restricted_to_domain_status = $("#admin-realm-restricted-to-domain-status").expectOne();
        var invite_required_status = $("#admin-realm-invite-required-status").expectOne();
        var invite_by_admins_only_status = $("#admin-realm-invite-by-admins-only-status").expectOne();
        var authentication_methods_status = $("#admin-realm-authentication-methods-status").expectOne();
        var create_stream_by_admins_only_status = $("#admin-realm-create-stream-by-admins-only-status").expectOne();
        var add_emoji_by_admins_only_status = $("#admin-realm-add-emoji-by-admins-only-status").expectOne();
        var message_editing_status = $("#admin-realm-message-editing-status").expectOne();
        var default_language_status = $("#admin-realm-default-language-status").expectOne();
        var waiting_period_threshold_status = $("#admin-realm-waiting_period_threshold_status").expectOne();
        name_status.hide();
        restricted_to_domain_status.hide();
        invite_required_status.hide();
        invite_by_admins_only_status.hide();
        authentication_methods_status.hide();
        create_stream_by_admins_only_status.hide();
        add_emoji_by_admins_only_status.hide();
        message_editing_status.hide();
        default_language_status.hide();
        waiting_period_threshold_status.hide();

        e.preventDefault();
        e.stopPropagation();

        var new_name = $("#id_realm_name").val();
        var new_restricted = $("#id_realm_restricted_to_domain").prop("checked");
        var new_invite = $("#id_realm_invite_required").prop("checked");
        var new_invite_by_admins_only = $("#id_realm_invite_by_admins_only").prop("checked");
        var new_create_stream_by_admins_only = $("#id_realm_create_stream_by_admins_only").prop("checked");
        var new_add_emoji_by_admins_only = $("#id_realm_add_emoji_by_admins_only").prop("checked");
        var new_allow_message_editing = $("#id_realm_allow_message_editing").prop("checked");
        var new_message_content_edit_limit_minutes = $("#id_realm_message_content_edit_limit_minutes").val();
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

        var url = "/json/realm";
        var data = {
            name: JSON.stringify(new_name),
            restricted_to_domain: JSON.stringify(new_restricted),
            invite_required: JSON.stringify(new_invite),
            invite_by_admins_only: JSON.stringify(new_invite_by_admins_only),
            authentication_methods: JSON.stringify(new_auth_methods),
            create_stream_by_admins_only: JSON.stringify(new_create_stream_by_admins_only),
            add_emoji_by_admins_only: JSON.stringify(new_add_emoji_by_admins_only),
            allow_message_editing: JSON.stringify(new_allow_message_editing),
            message_content_edit_limit_seconds:
                JSON.stringify(parseInt(new_message_content_edit_limit_minutes, 10) * 60),
            default_language: JSON.stringify(new_default_language),
            waiting_period_threshold: JSON.stringify(parseInt(new_waiting_period_threshold, 10))
        };

        channel.patch({
            url: url,
            data: data,
            success: function (response_data) {
                if (response_data.name !== undefined) {
                    ui.report_success(i18n.t("Name changed!"), name_status);
                }
                if (response_data.restricted_to_domain !== undefined) {
                    if (response_data.restricted_to_domain) {
                        ui.report_success(i18n.t("New users must have e-mails ending in __atdomains_string__!", {atdomains_string: atdomains_string}), restricted_to_domain_status);
                    } else {
                        ui.report_success(i18n.t("New users may have arbitrary e-mails!"), restricted_to_domain_status);
                    }
                }
                if (response_data.invite_required !== undefined) {
                    if (response_data.invite_required) {
                        ui.report_success(i18n.t("New users must be invited by e-mail!"), invite_required_status);
                    } else {
                        ui.report_success(i18n.t("New users may sign up online!"), invite_required_status);
                    }
                }
                if (response_data.invite_by_admins_only !== undefined) {
                    if (response_data.invite_by_admins_only) {
                        ui.report_success(i18n.t("New users must be invited by an admin!"), invite_by_admins_only_status);
                    } else {
                        ui.report_success(i18n.t("Any user may now invite new users!"), invite_by_admins_only_status);
                    }
                }
                if (response_data.create_stream_by_admins_only !== undefined) {
                    if (response_data.create_stream_by_admins_only) {
                        ui.report_success(i18n.t("Only Admins may now create new streams!"), create_stream_by_admins_only_status);
                    } else {
                        ui.report_success(i18n.t("Any user may now create new streams!"), create_stream_by_admins_only_status);
                    }
                }
                if (response_data.add_emoji_by_admins_only !== undefined) {
                    if (response_data.add_emoji_by_admins_only) {
                        ui.report_success(i18n.t("Only Admins may now add new emoji!"), add_emoji_by_admins_only_status);
                    } else {
                        ui.report_success(i18n.t("Any user may now add new emoji!"), add_emoji_by_admins_only_status);
                    }
                }
                if (response_data.authentication_methods !== undefined) {
                    if (response_data.authentication_methods) {
                        ui.report_success(i18n.t("Authentication methods saved!"), authentication_methods_status);
                    }
                }
                if (response_data.allow_message_editing !== undefined) {
                    // We expect message_content_edit_limit_seconds was sent in the
                    // response as well
                    var data_message_content_edit_limit_minutes =
                        Math.ceil(response_data.message_content_edit_limit_seconds / 60);
                    if (response_data.allow_message_editing) {
                        if (response_data.message_content_edit_limit_seconds > 0) {
                            ui.report_success(i18n.t("Users can now edit topics for all their messages,"
                                                      +" and the content of messages which are less than __num_minutes__ minutes old.",
                                                     {num_minutes :
                                                       data_message_content_edit_limit_minutes}),
                                              message_editing_status);
                        } else {
                            ui.report_success(i18n.t("Users can now edit the content and topics of all their past messages!"), message_editing_status);
                        }
                    } else {
                        ui.report_success(i18n.t("Users can no longer edit their past messages!"), message_editing_status);
                    }
                    // message_content_edit_limit_seconds could have been changed earlier
                    // in this function, so update the field just in case
                    $("#id_realm_message_content_edit_limit_minutes").val(data_message_content_edit_limit_minutes);
                }
                if (response_data.default_language !== undefined) {
                    if (response_data.default_language) {
                        ui.report_success(i18n.t("Default language changed!"), default_language_status);
                    }
                }
                if (response_data.waiting_period_threshold !== undefined) {
                    if (response_data.waiting_period_threshold > 0) {
                        ui.report_success(i18n.t("waiting period threshold changed!"), waiting_period_threshold_status);
                    }
                }
            },
            error: function (xhr) {
                var reason = $.parseJSON(xhr.responseText).reason;
                if (reason === "no authentication") {
                    ui.report_error(i18n.t("Failed!"), xhr, authentication_methods_status);
                } else {
                    ui.report_error(i18n.t("Failed!"), xhr, name_status);
                }
            }
        });
    });

    $(".admin_user_table").on("click", ".make-admin", function (e) {
        e.preventDefault();
        e.stopPropagation();

        // Go up the tree until we find the user row, then grab the email element
        var row = $(e.target).closest(".user_row");
        var email = get_email_for_user_row(row);

        var url = "/json/users/" + email;
        var data = {
            is_admin: JSON.stringify(true)
        };

        channel.patch({
            url: url,
            data: data,
            success: function () {
                var button = row.find("button.make-admin");
                button.addClass("btn-danger");
                button.removeClass("btn-warning");
                button.addClass("remove-admin");
                button.removeClass("make-admin");
                button.text(i18n.t("Remove admin"));
            },
            error: function (xhr) {
                var status = row.find(".admin-user-status");
                ui.report_error(i18n.t("Failed!"), xhr, status);
            }
        });
    });

    $(".admin_user_table").on("click", ".remove-admin", function (e) {
        e.preventDefault();
        e.stopPropagation();

        // Go up the tree until we find the user row, then grab the email element
        var row = $(e.target).closest(".user_row");
        var email = get_email_for_user_row(row);

        var url = "/json/users/" + email;
        var data = {
            is_admin: JSON.stringify(false)
        };

        channel.patch({
            url: url,
            data: data,
            success: function () {
                var button = row.find("button.remove-admin");
                button.addClass("btn-warning");
                button.removeClass("btn-danger");
                button.addClass("make-admin");
                button.removeClass("remove-admin");
                button.text(i18n.t("Make admin"));
            },
            error: function (xhr) {
                var status = row.find(".admin-user-status");
                ui.report_error(i18n.t("Failed!"), xhr, status);
            }
        });
    });

    $(".admin_user_table, .admin_bot_table").on("click", ".open-user-form", function (e) {
        var email = $(e.currentTarget).data("email");
        var user_info = get_user_info(email);
        var user_row = user_info.user_row;
        var form_row = user_info.form_row;
        var reset_button = form_row.find(".reset_edit_user");
        var submit_button = form_row.find(".submit_name_changes");
        var full_name = form_row.find("input[name='full_name']");
        var admin_status = $('#administration-status').expectOne();

        // Show user form.
        user_row.hide();
        form_row.show();

        reset_button.on("click", function () {
            form_row.hide();
            user_row.show();
        });

        submit_button.on("click", function (e) {
            e.preventDefault();
            e.stopPropagation();

            var url = "/json/users/" + email;
            var data = {
                full_name: JSON.stringify(full_name.val())
            };

            channel.patch({
                url: url,
                data: data,
                success: function () {
                    ui.report_success(i18n.t('Name successfully updated!'), admin_status);
                },
                error: failed_changing_name
            });
        });
    });

    $("#do_deactivate_stream_button").click(function () {
        if ($("#deactivation_stream_modal .stream_name").text() !== $(".active_stream_row").find('.stream_name').text()) {
            blueslip.error("Stream deactivation canceled due to non-matching fields.");
            ui.report_message("Deactivation encountered an error. Please reload and try again.",
               $("#home-error"), 'alert-error');
        }
        $("#deactivation_stream_modal").modal("hide");
        $(".active_stream_row button").prop("disabled", true).text("Working…");
        channel.del({
            url: '/json/streams/' + encodeURIComponent($(".active_stream_row").find('.stream_name').text()),
            error: function (xhr) {
                if (xhr.status.toString().charAt(0) === "4") {
                    $(".active_stream_row button").closest("td").html(
                        $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg)
                    );
                } else {
                     $(".active_stream_row button").text("Failed!");
                }
            },
            success: function () {
                var row = $(".active_stream_row");
                row.remove();
            }
        });
    });

    $('.admin_emoji_table').on('click', '.delete', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var btn = $(this);

        channel.del({
            url: '/json/realm/emoji/' + encodeURIComponent(btn.attr('data-emoji-name')),
            error: function (xhr) {
                if (xhr.status.toString().charAt(0) === "4") {
                    btn.closest("td").html(
                        $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg)
                    );
                } else {
                     btn.text("Failed!");
                }
            },
            success: function () {
                var row = btn.parents('tr');
                row.remove();
            }
        });
    });

    $(".administration").on("submit", "form.admin-emoji-form", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var emoji_status = $('#admin-emoji-status');
        var emoji = {};
        _.each($(this).serializeArray(), function (obj) {
            emoji[obj.name] = obj.value;
        });

        channel.put({
            url: "/json/realm/emoji",
            data: $(this).serialize(),
            success: function () {
                $('#admin-emoji-status').hide();
                ui.report_success(i18n.t("Custom emoji added!"), emoji_status);
                $("form.admin-emoji-form input[type='text']").val("");
            },
            error: function (xhr) {
                $('#admin-emoji-status').hide();
                var errors = JSON.parse(xhr.responseText).msg;
                xhr.responseText = JSON.stringify({msg: errors});
                ui.report_error(i18n.t("Failed!"), xhr, emoji_status);
            }
        });
    });

    $('.admin_filters_table').on('click', '.delete', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var btn = $(this);

        channel.del({
            url: '/json/realm/filters/' + encodeURIComponent(btn.attr('data-filter-id')),
            error: function (xhr) {
                if (xhr.status.toString().charAt(0) === "4") {
                    btn.closest("td").html(
                        $("<p>").addClass("text-error").text($.parseJSON(xhr.responseText).msg)
                    );
                } else {
                     btn.text("Failed!");
                }
            },
            success: function () {
                var row = btn.parents('tr');
                row.remove();
            }
        });
    });

    $(".administration").on("submit", "form.admin-filter-form", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var filter_status = $('#admin-filter-status');
        var pattern_status = $('#admin-filter-pattern-status');
        var format_status = $('#admin-filter-format-status');
        filter_status.hide();
        pattern_status.hide();
        format_status.hide();
        var filter = {};
        _.each($(this).serializeArray(), function (obj) {
            filter[obj.name] = obj.value;
        });

        channel.post({
            url: "/json/realm/filters",
            data: $(this).serialize(),
            success: function (data) {
                filter.id = data.id;
                ui.report_success(i18n.t("Custom filter added!"), filter_status);
            },
            error: function (xhr) {
                var errors = $.parseJSON(xhr.responseText).errors;
                if (errors.pattern !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.pattern});
                    ui.report_error(i18n.t("Failed"), xhr, pattern_status);
                }
                if (errors.url_format_string !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.url_format_string});
                    ui.report_error(i18n.t("Failed"), xhr, format_status);
                }
                if (errors.__all__ !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.__all__});
                    ui.report_error(i18n.t("Failed"), xhr, filter_status);
                }
            }
        });
    });

}

exports.setup_page = function () {
    i18n.ensure_i18n(_setup_page);
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = admin;
}
