import $ from "jquery";

import render_settings_resend_invite_modal from "../templates/confirm_dialog/confirm_resend_invite.hbs";
import render_settings_revoke_invite_modal from "../templates/confirm_dialog/confirm_revoke_invite.hbs";
import render_admin_invites_list from "../templates/settings/admin_invites_list.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import {$t, $t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_config from "./settings_config";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";
import * as util from "./util";

const meta = {
    loaded: false,
};

export function reset() {
    meta.loaded = false;
}

function failed_listing_invites(xhr) {
    loading.destroy_indicator($("#admin_page_invites_loading_indicator"));
    ui_report.error(
        $t_html({defaultMessage: "Error listing invites"}),
        xhr,
        $("#invites-field-status"),
    );
}

function add_invited_as_text(invites) {
    for (const data of invites) {
        data.invited_as_text = settings_config.user_role_map.get(data.invited_as);
    }
}

function sort_invitee(a, b) {
    // multi-invite links don't have an email field,
    // so we set them to empty strings to let them
    // sort to the top
    const str1 = (a.email || "").toUpperCase();
    const str2 = (b.email || "").toUpperCase();

    return util.strcmp(str1, str2);
}

function populate_invites(invites_data) {
    if (!meta.loaded) {
        return;
    }

    add_invited_as_text(invites_data.invites);

    const invites_table = $("#admin_invites_table").expectOne();
    ListWidget.create(invites_table, invites_data.invites, {
        name: "admin_invites_list",
        modifier(item) {
            item.invited_absolute_time = timerender.absolute_time(item.invited * 1000);
            item.expiry_date_absolute_time = timerender.absolute_time(item.expiry_date * 1000);
            item.is_admin = page_params.is_admin;
            item.disable_buttons =
                item.invited_as === settings_config.user_role_values.owner.code &&
                !page_params.is_owner;
            item.referrer_name = people.get_by_user_id(item.invited_by_user_id).full_name;
            return render_admin_invites_list({invite: item});
        },
        filter: {
            element: invites_table.closest(".settings-section").find(".search"),
            predicate(item, value) {
                const referrer = people.get_by_user_id(item.invited_by_user_id);
                const referrer_email = referrer.email;
                const referrer_name = referrer.full_name;
                const referrer_name_matched = referrer_name.toLowerCase().includes(value);
                const referrer_email_matched = referrer_email.toLowerCase().includes(value);
                if (item.is_multiuse) {
                    return referrer_name_matched || referrer_email_matched;
                }
                const invitee_email_matched = item.email.toLowerCase().includes(value);
                return referrer_email_matched || referrer_name_matched || invitee_email_matched;
            },
        },
        parent_container: $("#admin-invites-list").expectOne(),
        init_sort: [sort_invitee],
        sort_fields: {
            invitee: sort_invitee,
        },
        simplebar_container: $("#admin-invites-list .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_invites_loading_indicator"));
}

function do_revoke_invite() {
    const modal_invite_id = $(".dialog_submit_button").attr("data-invite-id");
    const modal_is_multiuse = $(".dialog_submit_button").attr("data-is-multiuse");
    const revoke_button = meta.current_revoke_invite_user_modal_row.find("button.revoke");

    if (modal_invite_id !== meta.invite_id || modal_is_multiuse !== meta.is_multiuse) {
        blueslip.error("Invite revoking canceled due to non-matching fields.");
        ui_report.client_error(
            $t_html({
                defaultMessage: "Resending encountered an error. Please reload and try again.",
            }),
            $("#home-error"),
        );
    }

    revoke_button.prop("disabled", true).text($t({defaultMessage: "Working…"}));
    let url = "/json/invites/" + meta.invite_id;

    if (modal_is_multiuse === "true") {
        url = "/json/invites/multiuse/" + meta.invite_id;
    }
    channel.del({
        url,
        error(xhr) {
            ui_report.generic_row_button_error(xhr, revoke_button);
        },
        success() {
            meta.current_revoke_invite_user_modal_row.remove();
        },
    });
}

function do_resend_invite() {
    const modal_invite_id = $(".dialog_submit_button").attr("data-invite-id");
    const resend_button = meta.current_resend_invite_user_modal_row.find("button.resend");

    if (modal_invite_id !== meta.invite_id) {
        blueslip.error("Invite resending canceled due to non-matching fields.");
        ui_report.client_error(
            $t_html({
                defaultMessage: "Resending encountered an error. Please reload and try again.",
            }),
            $("#home-error"),
        );
    }

    resend_button.prop("disabled", true).text($t({defaultMessage: "Working…"}));
    channel.post({
        url: "/json/invites/" + meta.invite_id + "/resend",
        error(xhr) {
            ui_report.generic_row_button_error(xhr, resend_button);
        },
        success(data) {
            resend_button.text($t({defaultMessage: "Sent!"}));
            resend_button.removeClass("resend btn-warning").addClass("sea-green");
            data.timestamp = timerender.absolute_time(data.timestamp * 1000);
            meta.current_resend_invite_user_modal_row.find(".invited_at").text(data.timestamp);
        },
    });
}

export function set_up(initialize_event_handlers = true) {
    meta.loaded = true;

    // create loading indicators
    loading.make_indicator($("#admin_page_invites_loading_indicator"));

    // Populate invites table
    channel.get({
        url: "/json/invites",
        idempotent: true,
        timeout: 10 * 1000,
        success(data) {
            on_load_success(data, initialize_event_handlers);
        },
        error: failed_listing_invites,
    });
}

export function on_load_success(invites_data, initialize_event_handlers) {
    meta.loaded = true;
    populate_invites(invites_data);
    if (!initialize_event_handlers) {
        return;
    }
    $(".admin_invites_table").on("click", ".revoke", (e) => {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();
        const row = $(e.target).closest(".invite_row");
        const email = row.find(".email").text();
        const referred_by = row.find(".referred_by").text();
        meta.current_revoke_invite_user_modal_row = row;
        meta.invite_id = $(e.currentTarget).attr("data-invite-id");
        meta.is_multiuse = $(e.currentTarget).attr("data-is-multiuse");
        const ctx = {
            is_multiuse: meta.is_multiuse === "true",
            email,
            referred_by,
        };
        const html_body = render_settings_revoke_invite_modal(ctx);

        confirm_dialog.launch({
            html_heading: ctx.is_multiuse
                ? $t_html({defaultMessage: "Revoke invitation link"})
                : $t_html({defaultMessage: "Revoke invitation to {email}"}, {email}),
            html_body,
            on_click: do_revoke_invite,
        });

        $(".dialog_submit_button").attr("data-invite-id", meta.invite_id);
        $(".dialog_submit_button").attr("data-is-multiuse", meta.is_multiuse);
    });

    $(".admin_invites_table").on("click", ".resend", (e) => {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        const row = $(e.target).closest(".invite_row");
        const email = row.find(".email").text();
        meta.current_resend_invite_user_modal_row = row;
        meta.invite_id = $(e.currentTarget).attr("data-invite-id");
        const html_body = render_settings_resend_invite_modal({email});

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Resend invitation"}),
            html_body,
            on_click: do_resend_invite,
        });

        $(".dialog_submit_button").attr("data-invite-id", meta.invite_id);
    });
}
