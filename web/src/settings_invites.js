import $ from "jquery";

import render_settings_resend_invite_modal from "../templates/confirm_dialog/confirm_resend_invite.hbs";
import render_settings_revoke_invite_modal from "../templates/confirm_dialog/confirm_revoke_invite.hbs";
import render_invitation_failed_error from "../templates/invitation_failed_error.hbs";
import render_admin_invites_list from "../templates/settings/admin_invites_list.hbs";
import render_settings_dev_env_email_access from "../templates/settings/dev_env_email_access.hbs";
import render_edit_invite_user_modal from "../templates/settings/edit_invite_user_modal.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import {beforeSend, get_invite_streams} from "./invite";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as stream_data from "./stream_data";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";
import * as util from "./util";

const meta = {
    loaded: false,
    invites: [],
};

export function reset() {
    meta.loaded = false;
    meta.invites = [];
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

    meta.invites = invites_data.invites;
    const $invites_table = $("#admin_invites_table").expectOne();
    ListWidget.create($invites_table, invites_data.invites, {
        name: "admin_invites_list",
        modifier(item) {
            item.invited_absolute_time = timerender.absolute_time(item.invited * 1000);
            if (item.expiry_date !== null) {
                item.expiry_date_absolute_time = timerender.absolute_time(item.expiry_date * 1000);
            }
            item.is_admin = page_params.is_admin;
            item.disable_buttons =
                item.invited_as === settings_config.user_role_values.owner.code &&
                !page_params.is_owner;
            item.referrer_name = people.get_by_user_id(item.invited_by_user_id).full_name;
            return render_admin_invites_list({invite: item});
        },
        filter: {
            $element: $invites_table.closest(".settings-section").find(".search"),
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
        $parent_container: $("#admin-invites-list").expectOne(),
        init_sort: [sort_invitee],
        sort_fields: {
            invitee: sort_invitee,
        },
        $simplebar_container: $("#admin-invites-list .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_invites_loading_indicator"));
}

function do_revoke_invite() {
    const modal_invite_id = $(".dialog_submit_button").attr("data-invite-id");
    const modal_is_multiuse = $(".dialog_submit_button").attr("data-is-multiuse");
    const $revoke_button = meta.$current_revoke_invite_user_modal_row.find("button.revoke");

    if (modal_invite_id !== meta.invite_id || modal_is_multiuse !== meta.is_multiuse) {
        blueslip.error("Invite revoking canceled due to non-matching fields.");
        ui_report.client_error(
            $t_html({
                defaultMessage: "Resending encountered an error. Please reload and try again.",
            }),
            $("#home-error"),
        );
    }

    $revoke_button.prop("disabled", true).text($t({defaultMessage: "Working…"}));
    let url = "/json/invites/" + meta.invite_id;

    if (modal_is_multiuse === "true") {
        url = "/json/invites/multiuse/" + meta.invite_id;
    }
    channel.del({
        url,
        error(xhr) {
            ui_report.generic_row_button_error(xhr, $revoke_button);
        },
        success() {
            meta.$current_revoke_invite_user_modal_row.remove();
        },
    });
}

function do_resend_invite() {
    const modal_invite_id = $(".dialog_submit_button").attr("data-invite-id");
    const $resend_button = meta.$current_resend_invite_user_modal_row.find("button.resend");

    if (modal_invite_id !== meta.invite_id) {
        blueslip.error("Invite resending canceled due to non-matching fields.");
        ui_report.client_error(
            $t_html({
                defaultMessage: "Resending encountered an error. Please reload and try again.",
            }),
            $("#home-error"),
        );
    }

    $resend_button.prop("disabled", true).text($t({defaultMessage: "Working…"}));
    channel.post({
        url: "/json/invites/" + meta.invite_id + "/resend",
        error(xhr) {
            ui_report.generic_row_button_error(xhr, $resend_button);
        },
        success(data) {
            $resend_button.text($t({defaultMessage: "Sent!"}));
            $resend_button.removeClass("resend btn-warning").addClass("sea-green");
            data.timestamp = timerender.absolute_time(data.timestamp * 1000);
            meta.$current_resend_invite_user_modal_row.find(".invited_at").text(data.timestamp);
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
        timeout: 10 * 1000,
        success(data) {
            on_load_success(data, initialize_event_handlers);
        },
        error: failed_listing_invites,
    });
}

function get_invitation_data() {
    const invite_as = Number.parseInt($("#invite_as").val(), 10);
    const stream_ids = [];

    $("#invite-stream-checkboxes input:checked").each(function () {
        const stream_id = Number.parseInt($(this).val(), 10);
        stream_ids.push(stream_id);
    });

    const data = {
        csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').attr("value"),
        invite_as,
        stream_ids: JSON.stringify(stream_ids),
    };
    return data;
}

function submit_invitation_form(invite_id) {
    const $invite_status = $("#dialog_error");
    const data = get_invitation_data(invite_id);

    channel.patch({
        url: "/json/invites/" + invite_id,
        data,
        beforeSend,
        success() {
            ui_report.success(
                $t_html({defaultMessage: "Invite updated successfully."}),
                $invite_status,
            );

            if (page_params.development_environment) {
                const rendered_email_msg = render_settings_dev_env_email_access();
                $("#dev_env_msg").html(rendered_email_msg).addClass("alert-info").show();
            }
        },
        error(xhr) {
            const arr = JSON.parse(xhr.responseText);
            if (arr.errors === undefined) {
                // There was a fatal error, no partial processing occurred.
                ui_report.error("", xhr, $invite_status);
            } else {
                // Some users were not invited.
                // This might happen in the case when an email becomes invalid or deactivated
                // between the time of creation of the invite and its edit.
                const error_list = [];
                let is_invitee_deactivated = false;
                for (const value of arr.errors) {
                    const [email, error_message, deactivated] = value;
                    error_list.push(`${email}: ${error_message}`);
                    if (deactivated) {
                        is_invitee_deactivated = true;
                    }
                }

                const error_response = render_invitation_failed_error({
                    error_message: arr.msg,
                    error_list,
                    is_admin: page_params.is_admin,
                    is_invitee_deactivated,
                    license_limit_reached: arr.license_limit_reached,
                    has_billing_access: page_params.is_owner || page_params.is_billing_admin,
                    daily_limit_reached: arr.daily_limit_reached,
                });
                ui_report.message(error_response, $invite_status, "alert-warning");
            }
        },
        complete() {
            $("#invite-user-modal .dialog_submit_button").text(
                $t({defaultMessage: "Save changes"}),
            );
            $("#invite-user-modal .dialog_submit_button").prop("disabled", false);
            $("#invite-user-modal .dialog_cancel_button").prop("disabled", false);
        },
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
        const $row = $(e.target).closest(".invite_row");
        const email = $row.find(".email").text();
        const referred_by = $row.find(".referred_by").text();
        meta.$current_revoke_invite_user_modal_row = $row;
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

    $(".admin_invites_table").on("click", ".edit", (e) => {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.stopPropagation();
        e.preventDefault();

        const invite_id = Number.parseInt(e.currentTarget.dataset.inviteId, 10);
        const invite = meta.invites.find((invite) => invite.id === invite_id);

        const html_body = render_edit_invite_user_modal({
            development_environment: page_params.development_environment,
            invite_as_options: settings_config.user_role_values,
            is_admin: page_params.is_admin,
            is_owner: page_params.is_owner,
            streams: get_invite_streams(),
            notifications_stream: stream_data.get_notifications_stream(),
            invite,
        });

        function invite_user_modal_post_render() {
            $("#invite-user-modal .dialog_submit_button").prop("disabled", true);

            for (const stream_id of invite.streams) {
                $(`[value=${stream_id}]`).prop("checked", true);
            }

            function enable_invite_submit_button() {
                $("#invite-user-modal .dialog_submit_button").prop("disabled", false);
            }

            $("#invite-user-modal").on("input", "input, select", () => {
                enable_invite_submit_button();
            });

            $("#invite_check_all_button").on("click", () => {
                $("#streams_to_add :checkbox").prop("checked", true);
                enable_invite_submit_button();
            });

            $("#invite_uncheck_all_button").on("click", () => {
                $("#streams_to_add :checkbox").prop("checked", false);
                $("#invite-user-modal .dialog_submit_button").prop("disabled", true);
            });
        }

        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Edit invite to users"}),
            html_body,
            html_submit_button: $t_html({defaultMessage: "Save changes"}),
            id: "invite-user-modal",
            loading_spinner: true,
            on_click: () => submit_invitation_form(invite.id),
            post_render: invite_user_modal_post_render,
        });
    });

    $(".admin_invites_table").on("click", ".resend", (e) => {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        const $row = $(e.target).closest(".invite_row");
        const email = $row.find(".email").text();
        meta.$current_resend_invite_user_modal_row = $row;
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

export function update_invite_users_setting_tip() {
    if (settings_data.user_can_invite_others_to_realm() && !page_params.is_admin) {
        $(".invite-user-settings-tip").hide();
        return;
    }
    const permission_type = settings_config.invite_to_realm_policy_values;
    const current_permission = page_params.realm_invite_to_realm_policy;
    let tip_text;
    switch (current_permission) {
        case permission_type.by_admins_only.code: {
            tip_text = $t({
                defaultMessage:
                    "This organization is configured so that admins can invite users to this organization.",
            });

            break;
        }
        case permission_type.by_moderators_only.code: {
            tip_text = $t({
                defaultMessage:
                    "This organization is configured so that admins and moderators can invite users to this organization.",
            });

            break;
        }
        case permission_type.by_members.code: {
            tip_text = $t({
                defaultMessage:
                    "This organization is configured so that admins, moderators and members can invite users to this organization.",
            });

            break;
        }
        case permission_type.by_full_members.code: {
            tip_text = $t({
                defaultMessage:
                    "This organization is configured so that admins, moderators and full members can invite users to this organization.",
            });

            break;
        }
        default: {
            tip_text = $t({
                defaultMessage:
                    "This organization is configured so that nobody can invite users to this organization.",
            });
        }
    }
    $(".invite-user-settings-tip").show();
    $(".invite-user-settings-tip").text(tip_text);
}
