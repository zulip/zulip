var admin = (function () {

var meta = {
    loaded: false,
};
var exports = {};
var all_streams = [];

exports.show_or_hide_menu_item = function () {
    var item = $('.admin-menu-item').expectOne();
    if (page_params.is_admin) {
        item.show();
    } else {
        item.hide();
        $(".organization-box [data-name='organization-settings']")
            .find("input, button, select").attr("disabled", true);
    }
};

function get_user_info(user_id) {
    var self = {};
    self.user_row = $("tr.user_row[data-user-id='" + user_id + "']");
    self.form_row = $("tr.user-name-form[data-user-id='" + user_id + "']");

    return self;
}

function get_email_for_user_row(row) {
    var email = row.find('.email').text();
    return email;
}

function update_view_on_deactivate(row) {
    var button = row.find("button.deactivate");
    row.find('button.open-user-form').hide();
    button.addClass("btn-warning");
    button.removeClass("btn-danger");
    button.addClass("reactivate");
    button.removeClass("deactivate");
    button.text(i18n.t("Reactivate"));
    row.addClass("deactivated_user");
}

function update_view_on_reactivate(row) {
    row.find(".user-admin-settings").show();
    var button = row.find("button.reactivate");
    row.find("button.open-user-form").show();
    button.addClass("btn-danger");
    button.removeClass("btn-warning");
    button.addClass("deactivate");
    button.removeClass("reactivate");
    button.text(i18n.t("Deactivate"));
    row.removeClass("deactivated_user");
}

exports.update_user_data = function (user_id, new_data) {
    if (!meta.loaded) {
        return;
    }

    var user_info = get_user_info(user_id);
    var user_row = user_info.user_row;
    var form_row = user_info.form_row;

    if (new_data.full_name !== undefined) {
        // Update the full name in the table
        user_row.find(".user_name").text(new_data.full_name);
        form_row.find("input[name='full_name']").val(new_data.full_name);
    }

    if (new_data.owner !== undefined) {
        // Update the bot owner in the table
        user_row.find(".owner").text(new_data.owner);
    }

    if (new_data.is_active !== undefined) {
        if (new_data.is_active === false) {
            // Deactivate the bot in the table
            update_view_on_deactivate(user_row);
        } else {
            // Reactivate the bot in the table
            update_view_on_reactivate(user_row);
        }
    }

    // Remove the bot owner select control.
    form_row.find(".edit_bot_owner_container select").remove();

    // Hide name change form
    form_row.hide();
    user_row.show();
};

function failed_listing_users(xhr) {
    loading.destroy_indicator($('#subs_page_loading_indicator'));
    ui_report.error(i18n.t("Error listing users or bots"), xhr, $("#organization-status"));
}

function failed_listing_streams(xhr) {
    ui_report.error(i18n.t("Error listing streams"), xhr, $("#organization-status"));
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

    var bots_table_html = "";
    _.each(bots, function (user) {
        var bot_html = templates.render("admin_user_list", {user: user});
        bots_table_html = bots_table_html.concat(bot_html);
    });
    bots_table.append(bots_table_html);

    _.each(active_users, function (user) {
        var activity_rendered;
        var row = $(templates.render("admin_user_list", {user: user}));
        if (people.is_current_user(user.email)) {
            activity_rendered = timerender.render_date(new XDate());
        } else {
            var last_active_date = presence.last_active_date(user.user_id);
            if (last_active_date) {
                activity_rendered = timerender.render_date(last_active_date);
            } else {
                activity_rendered = $("<span></span>").text(i18n.t("Unknown"));
            }
        }
        row.find(".last_active").append(activity_rendered);
        users_table.append(row);
    });

    var deactivated_table_html = "";
    _.each(deactivated_users, function (user) {
        var user_html = templates.render("admin_user_list", {user: user});
        deactivated_table_html = deactivated_table_html.concat(user_html);
    });
    deactivated_users_table.append(deactivated_table_html);
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

exports.build_default_stream_table = function (streams_data) {
    var self = {};

    self.row_dict = new Dict();

    function set_up_remove_click_hander(row, stream_name) {
        row.on("click", ".remove-default-stream", function (e) {
            e.preventDefault();
            e.stopPropagation();

            channel.del({
                url: '/json/default_streams'+ '?' + $.param({stream_name: stream_name}),
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
                    row.remove();
                },
            });
        });
    }

    (function () {
        var table = $("#admin_default_streams_table").expectOne();
        _.each(streams_data, function (stream) {
            var row = $(templates.render("admin_default_streams_list", {stream: stream}));
            set_up_remove_click_hander(row, stream.name);
            self.row_dict.set(stream.stream_id, row);
            table.append(row);
        });
        loading.destroy_indicator($('#admin_page_default_streams_loading_indicator'));
    }());

    self.remove = function (stream_id) {
        if (self.row_dict.has(stream_id)) {
            var row = self.row_dict.get(stream_id);
            row.remove();
        }
    };

    return self;
};
var default_stream_table;

exports.remove_default_stream = function (stream_id) {
    if (default_stream_table) {
        default_stream_table.remove(stream_id);
    }
};

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
    if (/#*organization/.test(window.location.hash) ||
        /#*settings/.test(window.location.hash)) {
        $("#admin_default_streams_table").expectOne().find("tr.default_stream_row").remove();
        default_stream_table = exports.build_default_stream_table(
            page_params.realm_default_streams);
    }
};

function make_stream_default(stream_name) {
    var data = {
        stream_name: stream_name,
    };

    channel.post({
        url: '/json/default_streams',
        data: data,
        error: function (xhr) {
            if (xhr.status.toString().charAt(0) === "4") {
                $(".active_stream_row button").closest("td").html(
                    $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg));
            } else {
                $(".active_stream_row button").text(i18n.t("Failed!"));
            }
        },
    });
}

exports.populate_filters = function (filters_data) {
    if (!meta.loaded) {
        return;
    }

    var filters_table = $("#admin_filters_table").expectOne();
    filters_table.find("tr.filter_row").remove();
    _.each(filters_data, function (filter) {
        filters_table.append(
            templates.render(
                "admin_filter_list", {
                    filter: {
                        pattern: filter[0],
                        url_format_string: filter[1],
                        id: filter[2],
                    },
                }
            )
        );
    });
    loading.destroy_indicator($('#admin_page_filters_loading_indicator'));
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

    exports.show_or_hide_menu_item();

    $("#id_realm_default_language").val(page_params.realm_default_language);

    // create loading indicators
    loading.make_indicator($('#admin_page_users_loading_indicator'));
    loading.make_indicator($('#admin_page_bots_loading_indicator'));
    loading.make_indicator($('#admin_page_streams_loading_indicator'));
    loading.make_indicator($('#admin_page_deactivated_users_loading_indicator'));
    loading.make_indicator($('#admin_page_filters_loading_indicator'));

    // Populate users and bots tables
    channel.get({
        url:      '/json/users',
        idempotent: true,
        timeout:  10*1000,
        success: populate_users,
        error: failed_listing_users,
    });

    // Populate streams table
    channel.get({
        url:      '/json/streams?include_public=true&include_subscribed=true&include_default=true',
        timeout:  10*1000,
        idempotent: true,
        success: populate_streams,
        error: failed_listing_streams,
    });

    // We set this flag before we're fully loaded so that the populate
    // methods don't short-circuit.
    meta.loaded = true;

    settings_org.set_up();
    settings_emoji.set_up();

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
        },
    });

    $("#do_deactivate_user_button").expectOne().click(function () {
        var email = meta.current_deactivate_user_modal_row.find(".email").text();

        if ($("#deactivation_user_modal .email").html() !== email) {
            blueslip.error("User deactivation canceled due to non-matching fields.");
            ui_report.message("Deactivation encountered an error. Please reload and try again.",
               $("#home-error"), 'alert-error');
        }
        $("#deactivation_user_modal").modal("hide");
        meta.current_deactivate_user_modal_row.find("button").eq(0).prop("disabled", true).text(i18n.t("Working…"));
        channel.del({
            url: '/json/users/' + encodeURIComponent(email),
            error: function (xhr) {
                if (xhr.status.toString().charAt(0) === "4") {
                    meta.current_deactivate_user_modal_row.find("button").closest("td").html(
                        $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg)
                    );
                } else {
                    meta.current_deactivate_user_modal_row.find("button").text(i18n.t("Failed!"));
                }
            },
            success: function () {
                var button = meta.current_deactivate_user_modal_row.find("button.deactivate");
                button.prop("disabled", false);
                button.addClass("btn-warning reactivate").removeClass("btn-danger deactivate");
                button.text(i18n.t("Reactivate"));
                meta.current_deactivate_user_modal_row.addClass("deactivated_user");
                meta.current_deactivate_user_modal_row.find('button.open-user-form').hide();
                meta.current_deactivate_user_modal_row.find(".user-admin-settings").hide();
            },
        });
    });

    $(".admin_bot_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var row = $(e.target).closest(".user_row");

        var email = get_email_for_user_row(row);

        channel.del({
            url: '/json/bots/' + encodeURIComponent(email),
            error: function (xhr) {
                if (xhr.status.toString().charAt(0) === "4") {
                    row.find("button").closest("td").html(
                        $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg)
                    );
                } else {
                    row.find("button").text(i18n.t("Failed!"));
                }
            },
            success: function () {
                update_view_on_deactivate(row);
            },
        });
    });

    $(".admin_user_table, .admin_bot_table").on("click", ".reactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        // Go up the tree until we find the user row, then grab the email element
        var row = $(e.target).closest(".user_row");
        var email = get_email_for_user_row(row);

        channel.post({
            url: '/json/users/' + encodeURIComponent(email) + "/reactivate",
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
                update_view_on_reactivate(row);
            },
        });
    });

    $(".admin_user_table").on("click", ".make-admin", function (e) {
        e.preventDefault();
        e.stopPropagation();

        // Go up the tree until we find the user row, then grab the email element
        var row = $(e.target).closest(".user_row");
        var email = get_email_for_user_row(row);

        var url = "/json/users/" + encodeURIComponent(email);
        var data = {
            is_admin: JSON.stringify(true),
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
                ui_report.error(i18n.t("Failed!"), xhr, status);
            },
        });
    });

    $(".admin_user_table").on("click", ".remove-admin", function (e) {
        e.preventDefault();
        e.stopPropagation();

        // Go up the tree until we find the user row, then grab the email element
        var row = $(e.target).closest(".user_row");
        var email = get_email_for_user_row(row);

        var url = "/json/users/" + encodeURIComponent(email);
        var data = {
            is_admin: JSON.stringify(false),
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
                ui_report.error(i18n.t("Failed!"), xhr, status);
            },
        });
    });

    $(".admin_user_table, .admin_bot_table").on("click", ".open-user-form", function (e) {
        var users_list = people.get_realm_persons().filter(function (person)  {
            return !person.is_bot;
        });
        var user_id = $(e.currentTarget).attr("data-user-id");
        var user_info = get_user_info(user_id);
        var user_row = user_info.user_row;
        var form_row = user_info.form_row;
        var reset_button = form_row.find(".reset_edit_user");
        var submit_button = form_row.find(".submit_name_changes");
        var full_name = form_row.find("input[name='full_name']");
        var owner_select = $(templates.render("bot_owner_select", {users_list: users_list}));
        var admin_status = $('#organization-status').expectOne();
        var person = people.get_person_from_user_id(user_id);
        if (!person) {
            return;
        } else if (person.is_bot) {
            // Dynamically add the owner select control in order to
            // avoid performance issues in case of large number of users.
            owner_select.val(bot_data.get(person.email).owner || "");
            form_row.find(".edit_bot_owner_container").append(owner_select);
        }

        // Show user form.
        user_row.hide();
        form_row.show();

        reset_button.on("click", function () {
            owner_select.remove();
            form_row.hide();
            user_row.show();
        });

        submit_button.on("click", function (e) {
            e.preventDefault();
            e.stopPropagation();

            var url = "/json/bots/" + encodeURIComponent(person.email);
            var data = {
                full_name: full_name.val(),
            };

            if (owner_select.val() !== undefined && owner_select.val() !== "") {
                data.bot_owner = owner_select.val();
            }

            channel.patch({
                url: url,
                data: data,
                success: function () {
                    ui_report.success(i18n.t('Updated successfully!'), admin_status);
                },
                error: function () {
                    ui_report.error(i18n.t('Update failed!'), admin_status);
                },
            });
        });
    });

    $("#do_deactivate_stream_button").click(function () {
        if ($("#deactivation_stream_modal .stream_name").text() !== $(".active_stream_row").find('.stream_name').text()) {
            blueslip.error("Stream deactivation canceled due to non-matching fields.");
            ui_report.message("Deactivation encountered an error. Please reload and try again.",
               $("#home-error"), 'alert-error');
        }
        $("#deactivation_stream_modal").modal("hide");
        $(".active_stream_row button").prop("disabled", true).text(i18n.t("Working…"));
        var stream_name = $(".active_stream_row").find('.stream_name').text();
        var stream_id = stream_data.get_sub(stream_name).stream_id;
        channel.del({
            url: '/json/streams/' + stream_id,
            error: function (xhr) {
                if (xhr.status.toString().charAt(0) === "4") {
                    $(".active_stream_row button").closest("td").html(
                        $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg)
                    );
                } else {
                    $(".active_stream_row button").text(i18n.t("Failed!"));
                }
            },
            success: function () {
                var row = $(".active_stream_row");
                row.remove();
            },
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
                    btn.text(i18n.t("Failed!"));
                }
            },
            success: function () {
                var row = btn.parents('tr');
                row.remove();
            },
        });
    });

    $(".organization").on("submit", "form.admin-filter-form", function (e) {
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
                ui_report.success(i18n.t("Custom filter added!"), filter_status);
            },
            error: function (xhr) {
                var errors = $.parseJSON(xhr.responseText).errors;
                if (errors.pattern !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.pattern});
                    ui_report.error(i18n.t("Failed"), xhr, pattern_status);
                }
                if (errors.url_format_string !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.url_format_string});
                    ui_report.error(i18n.t("Failed"), xhr, format_status);
                }
                if (errors.__all__ !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.__all__});
                    ui_report.error(i18n.t("Failed"), xhr, filter_status);
                }
            },
        });
    });


}

exports.launch_page = function (tab) {
    var $active_tab = $("#settings_overlay_container li[data-section='" + tab + "']");

    if ($active_tab.hasClass("admin")) {
        $(".sidebar .ind-tab[data-tab-key='organization']").click();
    }

    $("#settings_overlay_container").addClass("show");
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
