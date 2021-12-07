import autosize from "autosize";
import ClipboardJS from "clipboard";
import $ from "jquery";

import copy_invite_link from "../templates/copy_invite_link.hbs";
import render_invitation_failed_error from "../templates/invitation_failed_error.hbs";
import render_invite_subscription from "../templates/invite_subscription.hbs";
import render_invite_user from "../templates/invite_user.hbs";
import render_settings_dev_env_email_access from "../templates/settings/dev_env_email_access.hbs";

import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as common from "./common";
import {$t, $t_html} from "./i18n";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
import * as stream_data from "./stream_data";
import * as ui from "./ui";
import * as ui_report from "./ui_report";
import * as util from "./util";

function reset_error_messages() {
    $("#invite_status").hide().text("").removeClass(common.status_classes);
    $("#multiuse_invite_status").hide().text("").removeClass(common.status_classes);

    $("#invitee_emails").closest(".control-group").removeClass("warning error");

    if (page_params.development_environment) {
        $("#dev_env_msg").hide().text("").removeClass(common.status_classes);
    }
}

function get_common_invitation_data() {
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

function beforeSend() {
    reset_error_messages();
    // TODO: You could alternatively parse the textarea here, and return errors to
    // the user if they don't match certain constraints (i.e. not real email addresses,
    // aren't in the right domain, etc.)
    //
    // OR, you could just let the server do it. Probably my temptation.
    const loading_text = $("#submit-invitation").data("loading-text");
    $("#submit-invitation").text(loading_text);
    $("#submit-invitation").prop("disabled", true);
    return true;
}

function submit_invitation_form() {
    const invite_status = $("#invite_status");
    const invitee_emails = $("#invitee_emails");
    const invitee_emails_group = invitee_emails.closest(".control-group");
    const data = get_common_invitation_data();
    data.invitee_emails = $("#invitee_emails").val();

    channel.post({
        url: "/json/invites",
        data,
        beforeSend,
        success() {
            ui_report.success(
                $t_html({defaultMessage: "User(s) invited successfully."}),
                invite_status,
            );
            invitee_emails_group.removeClass("warning");
            invitee_emails.val("");

            if (page_params.development_environment) {
                const rendered_email_msg = render_settings_dev_env_email_access();
                $("#dev_env_msg").html(rendered_email_msg).addClass("alert-info").show();
            }
        },
        error(xhr) {
            const arr = JSON.parse(xhr.responseText);
            if (arr.errors === undefined) {
                // There was a fatal error, no partial processing occurred.
                ui_report.error("", xhr, invite_status);
            } else {
                // Some users were not invited.
                const invitee_emails_errored = [];
                const error_list = [];
                let is_invitee_deactivated = false;
                for (const value of arr.errors) {
                    const [email, error_message, deactivated] = value;
                    error_list.push(`${email}: ${error_message}`);
                    if (deactivated) {
                        is_invitee_deactivated = true;
                    }
                    invitee_emails_errored.push(email);
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
                ui_report.message(error_response, invite_status, "alert-warning");
                invitee_emails_group.addClass("warning");

                if (arr.sent_invitations) {
                    invitee_emails.val(invitee_emails_errored.join("\n"));
                }
            }
        },
        complete() {
            $("#submit-invitation").text($t({defaultMessage: "Invite"}));
            $("#submit-invitation").prop("disabled", false);
            $("#invitee_emails").focus();
            ui.get_scroll_element($("#invite_user_form .modal-body"))[0].scrollTop = 0;
        },
    });
}

function generate_multiuse_invite() {
    const invite_status = $("#multiuse_invite_status");
    const data = get_common_invitation_data();
    channel.post({
        url: "/json/invites/multiuse",
        data,
        beforeSend,
        success(data) {
            const copy_link_html = copy_invite_link(data);
            ui_report.success(copy_link_html, invite_status);
            new ClipboardJS("#copy_generated_invite_link");
        },
        error(xhr) {
            ui_report.error("", xhr, invite_status);
        },
        complete() {
            $("#submit-invitation").text($t({defaultMessage: "Generate invite link"}));
            $("#submit-invitation").prop("disabled", false);
        },
    });
}

export function get_invite_streams() {
    const streams = stream_data.get_invite_stream_data();
    streams.sort((a, b) => util.strcmp(a.name, b.name));
    return streams;
}

function update_subscription_checkboxes() {
    const data = {
        streams: get_invite_streams(),
        notifications_stream: stream_data.get_notifications_stream(),
    };
    const html = render_invite_subscription(data);
    $("#streams_to_add").html(html);
}

function prepare_form_to_be_shown() {
    update_subscription_checkboxes();
    reset_error_messages();
}

export function launch() {
    $("#submit-invitation").button();
    prepare_form_to_be_shown();

    overlays.open_overlay({
        name: "invite",
        overlay: $("#invite-user"),
        on_close() {
            browser_history.exit_overlay();
        },
    });

    autosize($("#invitee_emails").trigger("focus"));

    // Ctrl + Enter key to submit form
    $("#invite-user").on("keydown", (e) => {
        if (e.key === "Enter" && e.ctrlKey) {
            submit_invitation_form();
        }
    });
}

export function initialize() {
    const rendered = render_invite_user({
        is_admin: page_params.is_admin,
        is_owner: page_params.is_owner,
        development_environment: page_params.development_environment,
        invite_as_options: settings_config.user_role_values,
    });

    $(".app").append(rendered);

    $(document).on("click", "#invite_check_all_button", () => {
        $("#streams_to_add :checkbox").prop("checked", true);
    });

    $(document).on("click", "#invite_uncheck_all_button", () => {
        $("#streams_to_add :checkbox").prop("checked", false);
    });

    $("#submit-invitation").on("click", () => {
        const is_generate_invite_link = $("#generate_multiuse_invite_radio").prop("checked");
        if (is_generate_invite_link) {
            generate_multiuse_invite();
        } else {
            submit_invitation_form();
        }
    });

    $("#generate_multiuse_invite_button").on("click", () => {
        $("#generate_multiuse_invite_radio").prop("checked", true);
        $("#multiuse_radio_section").show();
        $("#invite-method-choice").hide();
        $("#invitee_emails").prop("disabled", true);
        $("#submit-invitation").text($t({defaultMessage: "Generate invite link"}));
        $("#submit-invitation").data("loading-text", $t({defaultMessage: "Generating link..."}));
        reset_error_messages();
    });

    $("#invite-user").on("change", "#generate_multiuse_invite_radio", () => {
        $("#invitee_emails").prop("disabled", false);
        $("#submit-invitation").text($t({defaultMessage: "Invite"}));
        $("#submit-invitation").data("loading-text", $t({defaultMessage: "Inviting..."}));
        $("#multiuse_radio_section").hide();
        $("#invite-method-choice").show();
        reset_error_messages();
    });
}
