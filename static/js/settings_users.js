var render_admin_user_list = require("../templates/admin_user_list.hbs");
var render_bot_owner_select = require("../templates/bot_owner_select.hbs");
var render_user_info_form_modal = require('../templates/user_info_form_modal.hbs');

var settings_users = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

function compare_a_b(a, b) {
    if (a > b) {
        return 1;
    } else if (a === b) {
        return 0;
    }
    return -1;
}

function get_user_info_row(user_id) {
    return $("tr.user_row[data-user-id='" + user_id + "']");
}

function update_view_on_deactivate(row) {
    var button = row.find("button.deactivate");
    var user_role = row.find(".user_role");
    button.prop("disabled", false);
    row.find('button.open-user-form').hide();
    row.find('i.deactivated-user-icon').show();
    button.addClass("btn-warning reactivate");
    button.removeClass("deactivate btn-danger");
    button.text(i18n.t("Reactivate"));
    row.addClass("deactivated_user");

    if (user_role) {
        var user_id = row.data('user-id');
        user_role.text("%state (%role)".replace("%state", i18n.t("Deactivated")).
            replace("%role", people.get_user_type(user_id)));
    }
}

function update_view_on_reactivate(row) {
    var button = row.find("button.reactivate");
    var user_role = row.find(".user_role");
    row.find("button.open-user-form").show();
    row.find('i.deactivated-user-icon').hide();
    button.addClass("btn-danger deactivate");
    button.removeClass("btn-warning reactivate");
    button.text(i18n.t("Deactivate"));
    row.removeClass("deactivated_user");

    if (user_role) {
        var user_id = row.data('user-id');
        user_role.text(people.get_user_type(user_id));
    }
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
            // Deactivate the user/bot in the table
            update_view_on_deactivate(user_row);
        } else {
            // Reactivate the user/bot in the table
            update_view_on_reactivate(user_row);
        }
    }

    if (new_data.is_admin !== undefined || new_data.is_guest !== undefined) {
        user_row.find(".user_role").text(people.get_user_type(user_id));
    }
};

function failed_listing_users(xhr) {
    loading.destroy_indicator($('#subs_page_loading_indicator'));
    var status = get_status_field();
    ui_report.error(i18n.t("Error listing users or bots"), xhr, status);
}

var LAST_ACTIVE_NEVER = -1;
var LAST_ACTIVE_UNKNOWN = -2;

function get_last_active(user) {
    var presence_info = presence.presence_info[user.user_id];
    if (!presence_info) {
        return LAST_ACTIVE_UNKNOWN;
    }
    if (!isNaN(presence_info.last_active)) {
        return presence_info.last_active;
    }
    return LAST_ACTIVE_NEVER;
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
            user.last_active = get_last_active(user);
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
    var bot_list = list_render.create($bots_table, bots, {
        name: "admin_bot_list",
        modifier: function (item) {
            return render_admin_user_list({
                can_modify: page_params.is_admin,
                // It's always safe to show the fake email addresses for bot users
                show_email: true,
                user: item,
            });
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
        parent_container: $("#admin-bot-list").expectOne(),
    }).init();

    bot_list.sort("alphabetic", "full_name");

    bot_list.add_sort_function("bot_owner", function (a, b) {
        if (!a.bot_owner) { return 1; }
        if (!b.bot_owner) { return -1; }

        return compare_a_b(a.bot_owner, b.bot_owner);
    });

    function get_rendered_last_activity(item) {
        var today = new XDate();
        if (item.last_active === LAST_ACTIVE_UNKNOWN) {
            return $("<span></span>").text(i18n.t("Unknown"));
        }
        if (item.last_active === LAST_ACTIVE_NEVER) {
            return $("<span></span>").text(i18n.t("Never"));
        }
        return timerender.render_date(
            new XDate(item.last_active * 1000), undefined, today);
    }

    var $users_table = $("#admin_users_table");
    var users_list = list_render.create($users_table, active_users, {
        name: "users_table_list",
        modifier: function (item) {
            var $row = $(render_admin_user_list({
                can_modify: page_params.is_admin,
                is_current_user: people.is_my_user_id(item.user_id),
                show_email: settings_org.show_email(),
                user: item,
            }));
            $row.find(".last_active").append(get_rendered_last_activity(item));
            return $row;
        },
        filter: {
            element: $users_table.closest(".settings-section").find(".search"),
            callback: function (item, value) {
                var email = item.email;
                if (page_params.is_admin) {
                    email = item.delivery_email;
                }

                return (
                    item.full_name.toLowerCase().indexOf(value) >= 0 ||
                    email.toLowerCase().indexOf(value) >= 0
                );
            },
            onupdate: reset_scrollbar($users_table),
        },
        parent_container: $("#admin-user-list").expectOne(),
    }).init();

    users_list.sort("alphabetic", "full_name");

    function sort_role(a, b) {
        function role(user) {
            if (user.is_admin) { return 0; }
            if (user.is_guest) { return 2; }
            return 1; // member
        }
        return compare_a_b(role(a), role(b));
    }
    users_list.add_sort_function("role", sort_role);

    users_list.add_sort_function("last_active", function (a, b) {
        return compare_a_b(b.last_active, a.last_active);
    });

    var $deactivated_users_table = $("#admin_deactivated_users_table");
    var deactivated_users_list = list_render.create($deactivated_users_table, deactivated_users, {
        name: "deactivated_users_table_list",
        modifier: function (item) {
            return render_admin_user_list({
                user: item,
                show_email: settings_org.show_email(),
                can_modify: page_params.is_admin,
            });
        },
        filter: {
            element: $deactivated_users_table.closest(".settings-section").find(".search"),
            callback: function (item, value) {
                var email = item.email;
                if (page_params.is_admin) {
                    email = item.delivery_email;
                }

                return (
                    item.full_name.toLowerCase().indexOf(value) >= 0 ||
                    email.toLowerCase().indexOf(value) >= 0
                );
            },
            onupdate: reset_scrollbar($deactivated_users_table),
        },
        parent_container: $("#admin-deactivated-users-list").expectOne(),
    }).init();

    deactivated_users_list.sort("alphabetic", "full_name");
    deactivated_users_list.add_sort_function("role", sort_role);

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

function open_user_info_form_modal(person) {
    var html = render_user_info_form_modal({
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
        var owner_select = $(render_bot_owner_select({users_list: users_list}));
        owner_select.val(bot_data.get(person.user_id).owner || "");
        modal_container.find(".edit_bot_owner_container").append(owner_select);
    }

    return user_info_form_modal;
}

exports.on_load_success = function (realm_people_data) {
    meta.loaded = true;

    populate_users(realm_people_data);

    var modal_elem = $("#deactivation_user_modal").expectOne();

    $(".admin_user_table").on("click", ".deactivate", function (e) {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        var row = $(e.target).closest(".user_row");
        var user_id = row.data('user-id');
        var user = people.get_person_from_user_id(user_id);
        modal_elem.find(".email").text(user.email);
        modal_elem.find(".user_name").text(user.full_name);
        modal_elem.modal("show");
        modal_elem.data('user-id', user_id);
    });

    modal_elem.find('.do_deactivate_button').click(function () {
        var user_id = modal_elem.data('user-id');
        var row = get_user_info_row(user_id);
        var email = row.attr("data-email");

        if ($("#deactivation_user_modal .email").html() !== email) {
            blueslip.error("User deactivation canceled due to non-matching fields.");
            ui_report.message(i18n.t("Deactivation encountered an error. Please reload and try again."),
                              $("#home-error"), 'alert-error');
        }
        modal_elem.modal("hide");
        var row_deactivate_button = row.find("button.deactivate");
        row_deactivate_button.prop("disabled", true).text(i18n.t("Working…"));
        var opts = {
            success_continuation: function () {
                update_view_on_deactivate(row);
            },
            error_continuation: function () {
                row_deactivate_button.text(i18n.t("Deactivate"));
            },
        };
        var status = get_status_field();
        var url = '/json/users/' + encodeURIComponent(user_id);
        settings_ui.do_settings_change(channel.del, url, {}, status, opts);

    });

    $(".admin_bot_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var button_elem = $(e.target);
        var row = button_elem.closest(".user_row");
        var bot_id = row.attr("data-user-id");
        var url = '/json/bots/' + encodeURIComponent(bot_id);

        var opts = {
            success_continuation: function () {
                update_view_on_deactivate(row);
            },
            error_continuation: function (xhr) {
                ui_report.generic_row_button_error(xhr, button_elem);
            },
        };
        var status = get_status_field();
        settings_ui.do_settings_change(channel.del, url, {}, status, opts);

    });

    $(".admin_user_table, .admin_bot_table").on("click", ".reactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();
        // Go up the tree until we find the user row, then grab the email element
        var button_elem = $(e.target);
        var row = button_elem.closest(".user_row");
        var user_id = row.attr("data-user-id");
        var url = '/json/users/' + encodeURIComponent(user_id) + "/reactivate";
        var data = {};
        var status = get_status_field();

        var opts = {
            success_continuation: function () {
                update_view_on_reactivate(row);
            },
            error_continuation: function (xhr) {
                ui_report.generic_row_button_error(xhr, button_elem);
            },
        };

        settings_ui.do_settings_change(channel.post, url, data, status, opts);
    });

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
        var fields_user_pills = settings_account.initialize_custom_user_type_fields(element,
                                                                                    user_id,
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
