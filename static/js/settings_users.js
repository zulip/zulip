var settings_users = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
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

function populate_users(realm_people_data) {
    var active_users = [];
    var deactivated_users = [];
    var bots = [];
    _.each(realm_people_data.members, function (user) {
        user.is_active_human = user.is_active && !user.is_bot;
        if (user.is_bot) {
            // Convert bot type id to string for viewing to the users.
            user.bot_type = settings_bots.type_id_to_string(user.bot_type);
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

    var update_scrollbar = function ($sel) {
        return function () {
            ui.update_scrollbar($sel);
        };
    };

    var $bots_table = $("#admin_bots_table");
    list_render($bots_table, bots, {
        name: "admin_bot_list",
        modifier: function (item) {
            return templates.render("admin_user_list", { user: item, can_modify: page_params.is_admin });
        },
        filter: {
            element: $bots_table.closest(".settings-section").find(".search"),
            callback: function (item, value) {
                return (
                    item.full_name.toLowerCase().indexOf(value) >= 0 ||
                    item.email.toLowerCase().indexOf(value) >= 0
                );
            },
            onupdate: update_scrollbar($bots_table),
        },
    }).init();

    var $users_table = $("#admin_users_table");
    list_render($users_table, active_users, {
        name: "users_table_list",
        modifier: function (item) {
            var activity_rendered;
            var today = new XDate();
            if (people.is_current_user(item.email)) {
                activity_rendered = timerender.render_date(today, undefined, today);
            } else if (presence.presence_info[item.user_id]) {
                // XDate takes number of milliseconds since UTC epoch.
                var last_active = presence.presence_info[item.user_id].last_active * 1000;

                if (!isNaN(last_active)) {
                    var last_active_date = new XDate(last_active);
                    activity_rendered = timerender.render_date(last_active_date, undefined, today);
                } else {
                    activity_rendered = $("<span></span>").text(i18n.t("Never"));
                }
            } else {
                activity_rendered = $("<span></span>").text(i18n.t("Unknown"));
            }

            var $row = $(templates.render("admin_user_list", {user: item, can_modify: page_params.is_admin}));

            $row.find(".last_active").append(activity_rendered);

            return $row;
        },
        filter: {
            element: $users_table.closest(".settings-section").find(".search"),
            callback: function (item, value) {
                return (
                    item.full_name.toLowerCase().indexOf(value) >= 0 ||
                    item.email.toLowerCase().indexOf(value) >= 0
                );
            },
            onupdate: update_scrollbar($users_table),
        },
    }).init();

    var $deactivated_users_table = $("#admin_deactivated_users_table");
    list_render($deactivated_users_table, deactivated_users, {
        name: "deactivated_users_table_list",
        modifier: function (item) {
            return templates.render("admin_user_list", { user: item, can_modify: page_params.is_admin });
        },
        filter: {
            element: $deactivated_users_table.closest(".settings-section").find(".search"),
            callback: function (item, value) {
                return (
                    item.full_name.toLowerCase().indexOf(value) >= 0 ||
                    item.email.toLowerCase().indexOf(value) >= 0
                );
            },
            onupdate: update_scrollbar($deactivated_users_table),
        },
    }).init();

    [$bots_table, $users_table, $deactivated_users_table].forEach(function ($o) {
        ui.set_up_scrollbar($o.closest(".progressive-table-wrapper"));
    });

    loading.destroy_indicator($('#admin_page_users_loading_indicator'));
    loading.destroy_indicator($('#admin_page_bots_loading_indicator'));
    loading.destroy_indicator($('#admin_page_deactivated_users_loading_indicator'));
    $("#admin_deactivated_users_table").show();
    $("#admin_users_table").show();
    $("#admin_bots_table").show();
}

exports.set_up = function () {
    loading.make_indicator($('#admin_page_users_loading_indicator'), {text: 'Loading...'});
    loading.make_indicator($('#admin_page_bots_loading_indicator'), {text: 'Loading...'});
    loading.make_indicator($('#admin_page_deactivated_users_loading_indicator'), {text: 'Loading...'});
    $("#admin_deactivated_users_table").hide();
    $("#admin_users_table").hide();
    $("#admin_bots_table").hide();

    // Populate users and bots tables
    channel.get({
        url:      '/json/users',
        idempotent: true,
        timeout:  10*1000,
        success: exports.on_load_success,
        error: failed_listing_users,
    });
};

exports.on_load_success = function (realm_people_data) {
    meta.loaded = true;

    populate_users(realm_people_data);

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

    $("#do_deactivate_user_button").expectOne().click(function () {
        var email = meta.current_deactivate_user_modal_row.find(".email").text();

        if ($("#deactivation_user_modal .email").html() !== email) {
            blueslip.error("User deactivation canceled due to non-matching fields.");
            ui_report.message(i18n.t("Deactivation encountered an error. Please reload and try again."),
               $("#home-error"), 'alert-error');
        }
        $("#deactivation_user_modal").modal("hide");
        meta.current_deactivate_user_modal_row.find("button").eq(0).prop("disabled", true).text(i18n.t("Working…"));
        channel.del({
            url: '/json/users/' + encodeURIComponent(email),
            error: function (xhr) {
                var status = $("#organization-status").expectOne();
                ui_report.error(i18n.t("Failed"), xhr, status);
                var button = meta.current_deactivate_user_modal_row.find("button.deactivate");
                button.text(i18n.t("Deactivate"));
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
                ui_report.generic_row_button_error(xhr, $(e.target));
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
                ui_report.generic_row_button_error(xhr, $(e.target));
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
                var status = $("#organization-status").expectOne();
                ui_report.error(i18n.t("Failed"), xhr, status);
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
                var status = $("#organization-status").expectOne();
                ui_report.error(i18n.t("Failed"), xhr, status);
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
        var url;
        var data;
        if (!person) {
            return;
        } else if (person.is_bot) {
            // Dynamically add the owner select control in order to
            // avoid performance issues in case of large number of users.
            owner_select.val(bot_data.get(user_id).owner || "");
            form_row.find(".edit_bot_owner_container").append(owner_select);
        }

        // Show user form and set the full name value in input field.
        full_name.val(person.full_name);
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

            if (person.is_bot) {
                url = "/json/bots/" + encodeURIComponent(person.email);
                data = {
                    full_name: full_name.val(),
                };
                if (owner_select.val() !== undefined && owner_select.val() !== "") {
                    data.bot_owner = owner_select.val();
                }
            } else {
                url = "/json/users/" + encodeURIComponent(person.email);
                data = {
                    full_name: JSON.stringify(full_name.val()),
                };
            }

            channel.patch({
                url: url,
                data: data,
                success: function () {
                    ui_report.success(i18n.t('Updated successfully!'), admin_status);
                },
                error: function (xhr) {
                    ui_report.error(i18n.t('Failed'), xhr, admin_status);
                },
            });
        });
    });

};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_users;
}
