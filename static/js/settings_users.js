var settings_users = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

function get_user_info_row(user_id) {
    return $("tr.user_row[data-user-id='" + user_id + "']");
}

function update_view_on_deactivate() {
    var row = meta.current_deactivate_bot_modal_row;
    var button = row.find("button.deactivate");
    row.find('button.open-user-form').hide();
    button.addClass("btn-warning");
    button.removeClass("btn-danger");
    button.addClass("reactivate");
    button.removeClass("deactivate");
    button.text(i18n.t("Reactivate"));
    row.addClass("deactivated_user");
}
function update_view_on_deactivate_reactivate_failure(xhr) {
    ui_report.generic_row_button_error(xhr, meta.current_bot_element);

}

function get_status_field() {
    var current_tab = settings_panel_menu.org_settings.current_tab();
    switch (current_tab) {
    case 'deactivated-users-admin':
        return $("#deactivated-user-field-status").expectOne();
    case 'user-list-admin':
        return $("#user-field-status").expectOne();
    case 'bot-list-admin':
        return $("#bot-field-status").expectOne();
    default:
        blueslip.fatal("Invalid admin settings page");
    }
}

function update_view_on_reactivate() {
    var row = meta.current_bot_element.closest(".user_row");
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

    var user_row = get_user_info_row(user_id);

    if (new_data.full_name !== undefined) {
        // Update the full name in the table
        user_row.find(".user_name").text(new_data.full_name);
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

    if (new_data.is_admin !== undefined || new_data.is_guest !== undefined) {
        var person_obj = people.get_person_from_user_id(user_id);
        if (person_obj.is_admin) {
            user_row.find(".user_role").text(i18n.t("Administrator"));
        } else if (person_obj.is_guest) {
            user_row.find(".user_role").text(i18n.t("Guest"));
        } else {
            user_row.find(".user_role").text(i18n.t("Member"));
        }
    }
};

function failed_listing_users(xhr) {
    loading.destroy_indicator($('#subs_page_loading_indicator'));
    var status = get_status_field();
    ui_report.error(i18n.t("Error listing users or bots"), xhr, status);
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

    var reset_scrollbar = function ($sel) {
        return function () {
            ui.reset_scrollbar($sel);
        };
    };

    var $bots_table = $("#admin_bots_table");
    list_render.create($bots_table, bots, {
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
            onupdate: reset_scrollbar($bots_table),
        },
    }).init();

    var $users_table = $("#admin_users_table");
    list_render.create($users_table, active_users, {
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
            onupdate: reset_scrollbar($users_table),
        },
    }).init();

    var $deactivated_users_table = $("#admin_deactivated_users_table");
    list_render.create($deactivated_users_table, deactivated_users, {
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
            onupdate: reset_scrollbar($deactivated_users_table),
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
        url: '/json/users',
        idempotent: true,
        timeout: 10 * 1000,
        success: exports.on_load_success,
        error: failed_listing_users,
    });
};

exports.on_load_success = function (realm_people_data) {
    meta.loaded = true;

    populate_users(realm_people_data);

    // Setup click handlers
    $(".admin_user_table").on("click", ".deactivate", function (e) {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        var row = $(e.target).closest(".user_row");

        var user_name = row.find('.user_name').text();
        var email = row.attr("data-email");

        $("#deactivation_user_modal .email").text(email);
        $("#deactivation_user_modal .user_name").text(user_name);
        $("#deactivation_user_modal").modal("show");

        meta.current_deactivate_user_modal_row = row;
    });

    function update_button_on_success() {
        var button = meta.current_deactivate_user_modal_row.find("button.deactivate");
        button.prop("disabled", false);
        button.addClass("btn-warning reactivate").removeClass("btn-danger deactivate");
        button.text(i18n.t("Reactivate"));
        meta.current_deactivate_user_modal_row.addClass("deactivated_user");
        meta.current_deactivate_user_modal_row.find('button.open-user-form').hide();
        meta.current_deactivate_user_modal_row.find(".user-admin-settings").hide();
    }
    function update_button_on_failure() {
        var button = meta.current_deactivate_user_modal_row.find("button.deactivate");
        button.text(i18n.t("Deactivate"));
    }

    $("#do_deactivate_user_button").expectOne().click(function () {
        var email = meta.current_deactivate_user_modal_row.attr("data-email");
        var user_id = meta.current_deactivate_user_modal_row.attr("data-user-id");

        if ($("#deactivation_user_modal .email").html() !== email) {
            blueslip.error("User deactivation canceled due to non-matching fields.");
            ui_report.message(i18n.t("Deactivation encountered an error. Please reload and try again."),
                              $("#home-error"), 'alert-error');
        }
        $("#deactivation_user_modal").modal("hide");
        meta.current_deactivate_user_modal_row.find("button").eq(0).prop("disabled", true).text(i18n.t("Working…"));
        var data = {
        };
        var opts = {
            success_continuation: update_button_on_success,
            error_continuation: update_button_on_failure,
        };
        var status = get_status_field();
        var url = '/json/users/' + encodeURIComponent(user_id);
        settings_ui.do_settings_change(channel.del, url, data, status, opts);

    });

    $(".admin_bot_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var row = $(e.target).closest(".user_row");
        meta.current_deactivate_bot_modal_row = row;
        meta.current_bot_element = $(e.target);
        var bot_id = row.attr("data-user-id");
        var url = '/json/bots/' + encodeURIComponent(bot_id);
        var data = {
        };
        var opts = {
            success_continuation: update_view_on_deactivate,
            error_continuation: update_view_on_deactivate_reactivate_failure,
        };
        var status = get_status_field();
        settings_ui.do_settings_change(channel.del, url, data, status, opts);

    });

    $(".admin_user_table, .admin_bot_table").on("click", ".reactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();
        meta.current_bot_element = $(e.target);
        // Go up the tree until we find the user row, then grab the email element
        var row = $(e.target).closest(".user_row");
        var user_id = row.attr("data-user-id");
        var url = '/json/users/' + encodeURIComponent(user_id) + "/reactivate";
        var data = {};
        var status = get_status_field();

        var opts = {
            success_continuation: update_view_on_reactivate,
            error_continuation: update_view_on_deactivate_reactivate_failure,
        };
        settings_ui.do_settings_change(channel.post, url, data, status, opts);
    });

    function open_user_info_form_modal(person) {
        var html = templates.render('user-info-form-modal', {
            user_id: person.user_id,
            email: person.email,
            full_name: people.get_full_name(person.user_id),
            is_admin: person.is_admin,
            is_guest: person.is_guest,
            is_member: !person.is_admin && !person.is_guest,
            is_bot: person.is_bot,
        });
        var user_info_form_modal = $(html);
        var modal_container = $('#user-info-form-modal-container');
        modal_container.empty().append(user_info_form_modal);
        overlays.open_modal('user-info-form-modal');

        if (person.is_bot) {
            // Dynamically add the owner select control in order to
            // avoid performance issues in case of large number of users.
            var users_list = people.get_active_human_persons();
            var owner_select = $(templates.render("bot_owner_select", {users_list: users_list}));
            owner_select.val(bot_data.get(person.user_id).owner || "");
            modal_container.find(".edit_bot_owner_container").append(owner_select);
        }

        return user_info_form_modal;
    }

    $(".admin_user_table, .admin_bot_table").on("click", ".open-user-form", function (e) {
        var user_id = $(e.currentTarget).attr("data-user-id");
        var person = people.get_person_from_user_id(user_id);

        if (!person) {
            return;
        }

        var user_info_form_modal = open_user_info_form_modal(person);
        var element = "#user-info-form-modal .custom-profile-field-form";
        $(element).html("");
        settings_account.append_custom_profile_fields(element, user_id);
        settings_account.initialize_custom_date_type_fields(element);
        var fields_user_pills = settings_account.intialize_custom_user_type_fields(element, user_id,
                                                                                   true, false);

        var url;
        var data;
        var full_name = user_info_form_modal.find("input[name='full_name']");

        user_info_form_modal.find('.submit_user_info_change').on("click", function (e) {
            e.preventDefault();
            e.stopPropagation();

            var user_role_select_value = user_info_form_modal.find('#user-role-select').val();

            var admin_status = get_status_field();
            if (person.is_bot) {
                url = "/json/bots/" + encodeURIComponent(user_id);
                data = {
                    full_name: full_name.val(),
                };
                var owner_select_value = user_info_form_modal.find('.bot_owner_select').val();
                if (owner_select_value) {
                    data.bot_owner_id = people.get_by_email(owner_select_value).user_id;
                }
            } else {
                var new_profile_data = [];
                $("#user-info-form-modal .custom_user_field_value").each(function () {
                    // Remove duplicate datepicker input element genearted flatpicker library
                    if (!$(this).hasClass("form-control")) {
                        new_profile_data.push({
                            id: parseInt($(this).closest(".custom_user_field").attr("data-field-id"), 10),
                            value: $(this).val(),
                        });
                    }
                });
                // Append user type field values also
                _.each(fields_user_pills, function (field_pills, field_id) {
                    if (field_pills) {
                        var user_ids = user_pill.get_user_ids(field_pills);
                        new_profile_data.push({
                            id: parseInt(field_id, 10),
                            value: user_ids,
                        });
                    }
                });

                url = "/json/users/" + encodeURIComponent(user_id);
                data = {
                    full_name: JSON.stringify(full_name.val()),
                    is_admin: JSON.stringify(user_role_select_value === 'admin'),
                    is_guest: JSON.stringify(user_role_select_value === 'guest'),
                    profile_data: JSON.stringify(new_profile_data),
                };
            }

            settings_ui.do_settings_change(channel.patch, url, data, admin_status);
            overlays.close_modal('user-info-form-modal');
        });
    });

};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_users;
}
window.settings_users = settings_users;
