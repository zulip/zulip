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
    const invite_as = parseInt($("#invite_as").val(), 10);
    const stream_ids = [];
    $("#invite-stream-checkboxes input:checked").each(function () {
        const stream_id = parseInt($(this).val(), 10);
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

function subscribe_existing_accounts(subscriber_stream_names, subscriber_emails) {
    const invite_status = $("#invite_status");
    const subscriber_user_ids = [];
    subscriber_emails.forEach((email) => {
        const person = people.get_by_email(email);
        subscriber_user_ids.push(person.user_id);
    });

    function success(data) {
        // At this point one of these three things could have happen.
        // 1. All the users were newly subscribed to the selected streams.
        // 2. All the users were already part of selected streams.
        // 3. Some users got newly subscribed, while some others were already subscribed.
        const all_newly_subscribed = !Object.entries(data.already_subscribed).length;
        const all_already_subscribed = !Object.entries(data.subscribed).length;
        if (all_newly_subscribed) {
            ui_report.success(i18n.t("User(s) subscribed successfully."), invite_status);
        } else if (all_already_subscribed) {
            ui_report.success(
                i18n.t("User(s) already subscribed to the selected stream(s)."),
                invite_status,
            );
        } else {
            ui_report.success(
                i18n.t(
                    "Some of those addresses were already subscribed to the selected stream(s). We subscribed everyone else!",
                ),
                invite_status,
            );
        }
    }

    function failure(xhr) {
        // Some fatal error occured.
        ui_report.error("", xhr, invite_status);
    }

    channel.post({
        url: "/json/users/me/subscriptions",
        data: {
            subscriptions: JSON.stringify(subscriber_stream_names),
            principals: JSON.stringify(subscriber_user_ids),
        },
        success,
        error: failure,
    });
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
                const subscriber_emails_errored = [];
                const subscriber_stream_names = [];
                const subscriber_stream_ids = JSON.parse(data.stream_ids);
                const error_list = [];
                let is_invitee_deactivated = false;
                arr.errors.forEach((value) => {
                    const [email, error_message, deactivated, maybe_anonymous_email] = value;
                    error_list.push(`${email}: ${error_message}`);
                    if (deactivated) {
                        is_invitee_deactivated = true;
                    } else {
                        // If they aren't deactivated, they can still be subscribed.
                        subscriber_emails_errored.push(maybe_anonymous_email);
                    }
                    invitee_emails_errored.push(email);
                });
                subscriber_stream_ids.forEach((stream_id) => {
                    subscriber_stream_names.push({name: stream_data.get_sub_by_id(stream_id).name});
                });
                const error_response = render_invitation_failed_error({
                    error_message: arr.msg,
                    error_list,
                    is_admin: page_params.is_admin,
                    is_invitee_deactivated,
                    show_subscription:
                        arr.show_subscription && subscriber_emails_errored.length > 0,
                    subscriber_emails_errored,
                    subscriber_stream_names,
                });
                ui_report.message(error_response, invite_status, "alert-warning");
                invitee_emails_group.addClass("warning");

                if (arr.sent_invitations) {
                    invitee_emails.val(invitee_emails_errored.join("\n"));
                }

                $("#subscribe_existing_accounts").on("click", () => {
                    subscribe_existing_accounts(subscriber_stream_names, subscriber_emails_errored);
                });
            }
        },
        complete() {
            $("#submit-invitation").button("reset");
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
            $("#submit-invitation").button("reset");
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
    autosize($("#invitee_emails").trigger("focus"));

    overlays.open_overlay({
        name: "invite",
        overlay: $("#invite-user"),
        on_close() {
            hashchange.exit_overlay();
        },
    });
};

exports.initialize = function () {
    $(document).on("click", ".invite_check_all_button", (e) => {
        $("#streams_to_add :checkbox").prop("checked", true);
        e.preventDefault();
    });

    $(document).on("click", ".invite_uncheck_all_button", (e) => {
        $("#streams_to_add :checkbox").prop("checked", false);
        e.preventDefault();
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
