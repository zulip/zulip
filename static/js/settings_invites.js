const util = require("./util");
const render_admin_invites_list = require("../templates/admin_invites_list.hbs");
const render_settings_revoke_invite_modal = require("../templates/settings/revoke_invite_modal.hbs");

const meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

function failed_listing_invites(xhr) {
    loading.destroy_indicator($('#admin_page_invites_loading_indicator'));
    ui_report.error(i18n.t("Error listing invites"), xhr, $("#invites-field-status"));
}

exports.invited_as_values = new Map([
    [1, i18n.t("Member")],
    [2, i18n.t("Organization administrator")],
    [3, i18n.t("Guest")],
]);

function add_invited_as_text(invites) {
    for (const data of invites) {
        data.invited_as_text = exports.invited_as_values.get(data.invited_as);
    }
}

function sort_invitee(a, b) {
    // multi-invite links don't have an email field,
    // so we set them to empty strings to let them
    // sort to the top
    const str1 = (a.email || '').toUpperCase();
    const str2 = (b.email || '').toUpperCase();

    return util.strcmp(str1, str2);
}

function populate_invites(invites_data) {
    if (!meta.loaded) {
        return;
    }

    add_invited_as_text(invites_data.invites);

    const invites_table = $("#admin_invites_table").expectOne();

    list_render.create(invites_table, invites_data.invites, {
        name: 'admin_invites_list',
        modifier: function (item) {
            item.invited_absolute_time = timerender.absolute_time(item.invited * 1000);
            item.is_admin = page_params.is_admin;
            return render_admin_invites_list({ invite: item });
        },
        filter: {
            element: invites_table.closest(".settings-section").find(".search"),
            predicate: function (item, value) {
                const referrer_email_matched = item.ref.toLowerCase().includes(value);
                if (item.is_multiuse) {
                    return referrer_email_matched;
                }
                const invitee_email_matched = item.email.toLowerCase().includes(value);
                return referrer_email_matched || invitee_email_matched;
            },
        },
        parent_container: $("#admin-invites-list").expectOne(),
        init_sort: [sort_invitee],
        sort_fields: {
            invitee: sort_invitee,
        },
    });

    loading.destroy_indicator($('#admin_page_invites_loading_indicator'));
}

function do_revoke_invite() {
    const modal_invite_id = $("#revoke_invite_modal #do_revoke_invite_button").attr("data-invite-id");
    const modal_is_multiuse = $("#revoke_invite_modal #do_revoke_invite_button").attr("data-is-multiuse");
    const revoke_button = meta.current_revoke_invite_user_modal_row.find("button.revoke");

    if (modal_invite_id !== meta.invite_id || modal_is_multiuse !== meta.is_multiuse) {
        blueslip.error("Invite revoking canceled due to non-matching fields.");
        ui_report.message(i18n.t("Resending encountered an error. Please reload and try again."),
                          $("#home-error"), 'alert-error');
    }
    $("#revoke_invite_modal").modal("hide");
    revoke_button.prop("disabled", true).text(i18n.t("Working…"));
    let url = '/json/invites/' + meta.invite_id;

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
        const row = $(e.target).closest(".invite_row");
        const email = row.find('.email').text();
        const referred_by = row.find('.referred_by').text();
        meta.current_revoke_invite_user_modal_row = row;
        meta.invite_id = $(e.currentTarget).attr("data-invite-id");
        meta.is_multiuse = $(e.currentTarget).attr("data-is-multiuse");
        const ctx = {is_multiuse: meta.is_multiuse === "true", email: email, referred_by: referred_by};
        const rendered_revoke_modal = render_settings_revoke_invite_modal(ctx);
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

        const row = $(e.target).closest(".invite_row");
        const email = row.find('.email').text();
        meta.current_resend_invite_user_modal_row = row;
        meta.invite_id = $(e.currentTarget).attr("data-invite-id");

        $("#resend_invite_modal .email").text(email);
        $("#resend_invite_modal #do_resend_invite_button").attr("data-invite-id", meta.invite_id);
        $("#resend_invite_modal").modal("show");
    });

    $("#do_resend_invite_button").click(function () {
        const modal_invite_id = $("#resend_invite_modal #do_resend_invite_button").attr("data-invite-id");
        const resend_button = meta.current_resend_invite_user_modal_row.find("button.resend");

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

window.settings_invites = exports;
