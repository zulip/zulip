var settings_invites = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

function failed_listing_invites(xhr) {
    loading.destroy_indicator($('#admin_page_invites_loading_indicator'));
    ui_report.error(i18n.t("Error listing invites"), xhr, $("#invites-field-status"));
}

exports.invited_as_values = {
    member: {
        value: 1,
        description: i18n.t("Member"),
    },
    admin_user: {
        value: 2,
        description: i18n.t("Organization administrator"),
    },
    guest_user: {
        value: 3,
        description: i18n.t("Guest"),
    },
};

function add_invited_as_text(invites) {
    invites.forEach(function (data) {
        var invited_as_type = _.findKey(exports.invited_as_values, function (elem) {
            return elem.value === data.invited_as;
        });
        data.invited_as_text = exports.invited_as_values[invited_as_type].description;
    });
}


function populate_invites(invites_data) {
    if (!meta.loaded) {
        return;
    }

    add_invited_as_text(invites_data.invites);

    var invites_table = $("#admin_invites_table").expectOne();

    var admin_invites_list = list_render.get("admin_invites_list");

    if (admin_invites_list) {
        admin_invites_list.data(invites_data.invites);
        admin_invites_list.set_container(invites_table);
        admin_invites_list.render();
    } else {
        list_render.create(invites_table, invites_data.invites, {
            name: "admin_invites_list",
            modifier: function (item) {
                item.invited_absolute_time = timerender.absolute_time(item.invited * 1000);
                return templates.render("admin_invites_list", { invite: item });
            },
            filter: {
                element: invites_table.closest(".settings-section").find(".search"),
                callback: function (item, value) {
                    var referrer_email_matched = item.ref.toLowerCase().indexOf(value) >= 0;
                    if (item.is_multiuse) {
                        return referrer_email_matched;
                    }
                    var invitee_email_matched = item.email.toLowerCase().indexOf(value) >= 0;
                    return referrer_email_matched || invitee_email_matched;
                },
            },
        }).init();
    }

    loading.destroy_indicator($('#admin_page_invites_loading_indicator'));
}

function do_revoke_invite() {
    var modal_invite_id = $("#revoke_invite_modal #do_revoke_invite_button").attr("data-invite-id");
    var modal_is_multiuse = $("#revoke_invite_modal #do_revoke_invite_button").attr("data-is-multiuse");
    var revoke_button = meta.current_revoke_invite_user_modal_row.find("button.revoke");

    if (modal_invite_id !== meta.invite_id || modal_is_multiuse !== meta.is_multiuse) {
        blueslip.error("Invite revoking canceled due to non-matching fields.");
        ui_report.message(i18n.t("Resending encountered an error. Please reload and try again."),
                          $("#home-error"), 'alert-error');
    }
    $("#revoke_invite_modal").modal("hide");
    revoke_button.prop("disabled", true).text(i18n.t("Working…"));
    var url = '/json/invites/' + meta.invite_id;

    if (modal_is_multiuse === "true") {
        url = '/json/invites/multiuse/' + meta.invite_id;
    }
    channel.del({
        url: url,
        error: function (xhr) {
            ui_report.generic_row_button_error(xhr, revoke_button);
        },
        success: function () {
            meta.current_revoke_invite_user_modal_row.remove();
        },
    });
}

exports.set_up = function (initialize_event_handlers) {
    meta.loaded = true;
    if (typeof initialize_event_handlers === 'undefined') {
        initialize_event_handlers = true;
    }

    // create loading indicators
    loading.make_indicator($('#admin_page_invites_loading_indicator'));

    // Populate invites table
    channel.get({
        url: '/json/invites',
        idempotent: true,
        timeout: 10 * 1000,
        success: function (data) {
            exports.on_load_success(data, initialize_event_handlers);
        },
        error: failed_listing_invites,
    });
};

exports.on_load_success = function (invites_data, initialize_event_handlers) {
    meta.loaded = true;
    populate_invites(invites_data);
    if (!initialize_event_handlers) {
        return;
    }
    $(".admin_invites_table").on("click", ".revoke", function (e) {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();
        var row = $(e.target).closest(".invite_row");
        var email = row.find('.email').text();
        var referred_by = row.find('.referred_by').text();
        meta.current_revoke_invite_user_modal_row = row;
        meta.invite_id = $(e.currentTarget).attr("data-invite-id");
        meta.is_multiuse = $(e.currentTarget).attr("data-is-multiuse");
        var ctx = {is_multiuse: meta.is_multiuse === "true", email: email, referred_by: referred_by};
        var rendered_revoke_modal = templates.render("revoke-invite-modal", ctx);
        $("#revoke_invite_modal_holder").html(rendered_revoke_modal);
        $("#revoke_invite_modal #do_revoke_invite_button").attr("data-invite-id", meta.invite_id);
        $("#revoke_invite_modal #do_revoke_invite_button").attr("data-is-multiuse", meta.is_multiuse);
        $("#revoke_invite_modal").modal("show");
        $("#do_revoke_invite_button").unbind("click");
        $("#do_revoke_invite_button").click(do_revoke_invite);
    });

    $(".admin_invites_table").on("click", ".resend", function (e) {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        var row = $(e.target).closest(".invite_row");
        var email = row.find('.email').text();
        meta.current_resend_invite_user_modal_row = row;
        meta.invite_id = $(e.currentTarget).attr("data-invite-id");

        $("#resend_invite_modal .email").text(email);
        $("#resend_invite_modal #do_resend_invite_button").attr("data-invite-id", meta.invite_id);
        $("#resend_invite_modal").modal("show");
    });

    $("#do_resend_invite_button").click(function () {
        var modal_invite_id = $("#resend_invite_modal #do_resend_invite_button").attr("data-invite-id");
        var resend_button = meta.current_resend_invite_user_modal_row.find("button.resend");

        if (modal_invite_id !== meta.invite_id) {
            blueslip.error("Invite resending canceled due to non-matching fields.");
            ui_report.message(i18n.t("Resending encountered an error. Please reload and try again."),
                              $("#home-error"), 'alert-error');
        }
        $("#resend_invite_modal").modal("hide");
        resend_button.prop("disabled", true).text(i18n.t("Working…"));
        channel.post({
            url: '/json/invites/' + meta.invite_id + "/resend",
            error: function (xhr) {
                ui_report.generic_row_button_error(xhr, resend_button);
            },
            success: function (data) {
                resend_button.text(i18n.t("Sent!"));
                resend_button.removeClass('resend btn-warning').addClass('sea-green');
                data.timestamp = timerender.absolute_time(data.timestamp * 1000);
                meta.current_resend_invite_user_modal_row.find(".invited_at").text(data.timestamp);
            },
        });
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_invites;
}
window.settings_invites = settings_invites;
