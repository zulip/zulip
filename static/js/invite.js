"use strict";

const autosize = require("autosize");

const render_invitation_failed_error = require("../templates/invitation_failed_error.hbs");
const render_invite_subscription = require("../templates/invite_subscription.hbs");
const render_settings_dev_env_email_access = require("../templates/settings/dev_env_email_access.hbs");

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
    $("#submit-invitation").button("loading");
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
            ui_report.success(i18n.t("User(s) invited successfully."), invite_status);
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
                arr.errors.forEach((value) => {
                    const [email, error_message, deactivated] = value;
                    error_list.push(`${email}: ${error_message}`);
                    if (deactivated) {
                        is_invitee_deactivated = true;
                    }
                    invitee_emails_errored.push(email);
                });

                const error_response = render_invitation_failed_error({
                    error_message: arr.msg,
                    error_list,
                    is_admin: page_params.is_admin,
                    is_invitee_deactivated,
                });
                ui_report.message(error_response, invite_status, "alert-warning");
                invitee_emails_group.addClass("warning");

                if (arr.sent_invitations) {
                    invitee_emails.val(invitee_emails_errored.join("\n"));
                }
            }
        },
        complete() {
            $("#submit-invitation").text(i18n.t("Invite"));
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
            ui_report.success(
                i18n.t('Invitation link: <a href="__link__">__link__</a>', {
                    link: data.invite_link,
                }),
                invite_status,
            );
        },
        error(xhr) {
            ui_report.error("", xhr, invite_status);
        },
        complete() {
            $("#submit-invitation").text(i18n.t("Generate invite link"));
            $("#submit-invitation").prop("disabled", false);
        },
    });
}

exports.get_invite_streams = function () {
    const streams = stream_data.get_invite_stream_data();

    function compare_streams(a, b) {
        return a.name.localeCompare(b.name);
    }
    streams.sort(compare_streams);
    return streams;
};

function update_subscription_checkboxes() {
    const data = {
        streams: exports.get_invite_streams(),
        notifications_stream: stream_data.get_notifications_stream(),
    };
    const html = render_invite_subscription(data);
    $("#streams_to_add").html(html);
}

function prepare_form_to_be_shown() {
    update_subscription_checkboxes();
    reset_error_messages();
}

exports.launch = function () {
    $("#submit-invitation").button();
    prepare_form_to_be_shown();

    overlays.open_overlay({
        name: "invite",
        overlay: $("#invite-user"),
        on_close() {
            hashchange.exit_overlay();
        },
    });

    autosize($("#invitee_emails").trigger("focus"));

    // Ctrl + Enter key to submit form
    $("#invite-user").on("keydown", (e) => {
        if (e.key === "Enter" && e.ctrlKey) {
            submit_invitation_form();
        }
    });
};

exports.initialize = function () {
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
        $("#submit-invitation").text(i18n.t("Generate invite link"));
        $("#submit-invitation").data("loading-text", i18n.t("Generating link..."));
        reset_error_messages();
    });

    $("#invite-user").on("change", "#generate_multiuse_invite_radio", () => {
        $("#invitee_emails").prop("disabled", false);
        $("#submit-invitation").text(i18n.t("Invite"));
        $("#submit-invitation").data("loading-text", i18n.t("Inviting..."));
        $("#multiuse_radio_section").hide();
        $("#invite-method-choice").show();
        reset_error_messages();
    });
};

window.invite = exports;
