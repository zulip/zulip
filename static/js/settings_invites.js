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
    ui_report.error(i18n.t("Error listing invites"), xhr, $("#organization-status"));
}

function populate_invites(invites_data) {
    if (!meta.loaded) {
        return;
    }
    var invites_table = $("#admin_invites_table").expectOne();

    var admin_invites_list = list_render.get("admin_invites_list");

    if (admin_invites_list) {
        admin_invites_list.data(invites_data.invites);
        admin_invites_list.set_container(invites_table);
        admin_invites_list.render();
    } else {
        list_render(invites_table, invites_data.invites, {
            name: "admin_invites_list",
            modifier: function (item) {
                item.invited = timerender.absolute_time(item.invited * 1000);
                return templates.render("admin_invites_list", { invite: item });
            },
            filter: {
                element: invites_table.closest(".settings-section").find(".search"),
                callback: function (item, value) {
                    return item.email.toLowerCase().indexOf(value) >= 0;
                },
            },
        }).init();
    }

    loading.destroy_indicator($('#admin_page_invites_loading_indicator'));
}


exports.set_up = function () {
    meta.loaded = true;

    // create loading indicators
    loading.make_indicator($('#admin_page_invites_loading_indicator'));

    // Populate invites table
    channel.get({
        url: '/json/invites',
        idempotent: true,
        timeout:  10*1000,
        success: exports.on_load_success,
        error: failed_listing_invites,
    });
};

exports.on_load_success = function (invites_data) {
    meta.loaded = true;
    populate_invites(invites_data);

    $(".admin_invites_table").on("click", ".revoke", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var row = $(e.target).closest(".invite_row");
        var email = row.find('.email').text();
        meta.current_revoke_invite_user_modal_row = row;
        meta.invite_id = $(e.currentTarget).attr("data-invite-id");

        $("#revoke_invite_modal .email").text(email);
        $("#revoke_invite_modal #do_revoke_invite_button").attr("data-invite-id", meta.invite_id);
        $("#revoke_invite_modal").modal("show");
    });

    $(".admin_invites_table").on("click", ".resend", function (e) {
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

    $("#do_revoke_invite_button").click(function () {
        var modal_invite_id = $("#revoke_invite_modal #do_revoke_invite_button").attr("data-invite-id");
        var revoke_button = meta.current_revoke_invite_user_modal_row.find("button.revoke");

        if (modal_invite_id !== meta.invite_id) {
            blueslip.error("Invite revoking canceled due to non-matching fields.");
            ui_report.message(i18n.t("Resending encountered an error. Please reload and try again."),
               $("#home-error"), 'alert-error');
        }
        $("#revoke_invite_modal").modal("hide");
        revoke_button.prop("disabled", true).text(i18n.t("Working…"));
        channel.del({
            url: '/json/invites/' + meta.invite_id,
            error: function (xhr) {
                ui_report.generic_row_button_error(xhr, revoke_button);
            },
            success: function () {
                meta.current_revoke_invite_user_modal_row.remove();
            },
        });
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
