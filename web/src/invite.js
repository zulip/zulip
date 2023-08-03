import autosize from "autosize";
import ClipboardJS from "clipboard";
import {add} from "date-fns";
import $ from "jquery";

import copy_invite_link from "../templates/copy_invite_link.hbs";
import render_invitation_failed_error from "../templates/invitation_failed_error.hbs";
import render_invite_user_modal from "../templates/invite_user_modal.hbs";
import render_settings_dev_env_email_access from "../templates/settings/dev_env_email_access.hbs";

import * as channel from "./channel";
import * as common from "./common";
import {csrf_token} from "./csrf";
import * as dialog_widget from "./dialog_widget";
import * as gear_menu from "./gear_menu";
import {$t, $t_html} from "./i18n";
import {page_params} from "./page_params";
import * as scroll_util from "./scroll_util";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as stream_data from "./stream_data";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";
import * as util from "./util";

let custom_expiration_time_input = 10;
let custom_expiration_time_unit = "days";

function reset_error_messages() {
    $("#dialog_error").hide().text("").removeClass(common.status_classes);

    if (page_params.development_environment) {
        $("#dev_env_msg").hide().text("").removeClass(common.status_classes);
    }
}

function get_common_invitation_data() {
    const invite_as = Number.parseInt($("#invite_as").val(), 10);
    let expires_in = $("#expires_in").val();
    // See settings_config.expires_in_values for why we do this conversion.
    if (expires_in === "null") {
        expires_in = JSON.stringify(null);
    } else if (expires_in === "custom") {
        expires_in = Number.parseFloat(get_expiration_time_in_minutes());
    } else {
        expires_in = Number.parseFloat($("#expires_in").val());
    }

    let stream_ids = [];
    const default_stream_ids = stream_data.get_default_stream_ids();
    if (default_stream_ids.length !== 0 && $("#invite_select_default_streams").prop("checked")) {
        stream_ids = default_stream_ids;
    } else {
        $("#invite-stream-checkboxes input:checked").each(function () {
            const stream_id = Number.parseInt($(this).val(), 10);
            stream_ids.push(stream_id);
        });
    }

    const data = {
        csrfmiddlewaretoken: csrf_token,
        invite_as,
        stream_ids: JSON.stringify(stream_ids),
        invite_expires_in_minutes: expires_in,
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
    const loading_text = $("#invite-user-modal .dialog_submit_button").data("loading-text");
    $("#invite-user-modal .dialog_submit_button").text(loading_text);
    $("#invite-user-modal .dialog_submit_button").prop("disabled", true);
    return true;
}

function submit_invitation_form() {
    const $invite_status = $("#dialog_error");
    const $invitee_emails = $("#invitee_emails");
    const data = get_common_invitation_data();
    data.invitee_emails = $("#invitee_emails").val();

    channel.post({
        url: "/json/invites",
        data,
        beforeSend,
        success() {
            ui_report.success(
                $t_html({defaultMessage: "User(s) invited successfully."}),
                $invite_status,
            );
            $invitee_emails.val("");

            if (page_params.development_environment) {
                const rendered_email_msg = render_settings_dev_env_email_access();
                $("#dev_env_msg").html(rendered_email_msg).addClass("alert-info").show();
            }

            if ($("#expires_in").val() === "custom") {
                // Hide the custom inputs if the custom input is set
                // to one of the dropdown's standard options.
                const time_in_minutes = get_expiration_time_in_minutes();
                for (const option of Object.values(settings_config.expires_in_values)) {
                    if (option.value === time_in_minutes) {
                        $("#custom-invite-expiration-time").hide();
                        $("#expires_in").val(time_in_minutes);
                        return;
                    }
                }
            }
        },
        error(xhr) {
            if (xhr.responseJSON?.errors === undefined) {
                // There was a fatal error, no partial processing occurred.
                ui_report.error("", xhr, $invite_status);
            } else {
                // Some users were not invited.
                const response_body = xhr.responseJSON;
                const invitee_emails_errored = [];
                const error_list = [];
                let is_invitee_deactivated = false;
                for (const value of response_body.errors) {
                    const [email, error_message, deactivated] = value;
                    error_list.push(`${email}: ${error_message}`);
                    if (deactivated) {
                        is_invitee_deactivated = true;
                    }
                    invitee_emails_errored.push(email);
                }

                const error_response = render_invitation_failed_error({
                    error_message: response_body.msg,
                    error_list,
                    is_admin: page_params.is_admin,
                    is_invitee_deactivated,
                    license_limit_reached: response_body.license_limit_reached,
                    has_billing_access: page_params.is_owner || page_params.is_billing_admin,
                    daily_limit_reached: response_body.daily_limit_reached,
                });
                ui_report.message(error_response, $invite_status, "alert-warning");

                if (response_body.sent_invitations) {
                    $invitee_emails.val(invitee_emails_errored.join("\n"));
                }
            }
        },
        complete() {
            $("#invite-user-modal .dialog_submit_button").text($t({defaultMessage: "Invite"}));
            $("#invite-user-modal .dialog_submit_button").prop("disabled", false);
            $("#invite-user-modal .dialog_exit_button").prop("disabled", false);
            $("#invitee_emails").trigger("focus");
            scroll_util.get_scroll_element($("#invite-user-modal"))[0].scrollTop = 0;
        },
    });
}

function generate_multiuse_invite() {
    const $invite_status = $("#dialog_error");
    const data = get_common_invitation_data();
    channel.post({
        url: "/json/invites/multiuse",
        data,
        beforeSend,
        success(data) {
            const copy_link_html = copy_invite_link(data);
            ui_report.success(copy_link_html, $invite_status);
            new ClipboardJS("#copy_generated_invite_link");
        },
        error(xhr) {
            ui_report.error("", xhr, $invite_status);
        },
        complete() {
            $("#invite-user-modal .dialog_submit_button").text(
                $t({defaultMessage: "Generate invite link"}),
            );
            $("#invite-user-modal .dialog_submit_button").prop("disabled", false);
            $("#invite-user-modal .dialog_exit_button").prop("disabled", false);
            scroll_util.get_scroll_element($("#invite-user-modal"))[0].scrollTop = 0;
        },
    });
}

export function get_invite_streams() {
    const streams = stream_data.get_invite_stream_data();
    streams.sort((a, b) => util.strcmp(a.name, b.name));
    return streams;
}

function valid_to(expires_in) {
    const time_valid = Number.parseFloat(expires_in);
    if (!time_valid) {
        return $t({defaultMessage: "Never expires"});
    }

    // The below is a duplicate of timerender.get_full_datetime, with a different base string.
    const valid_to = add(new Date(), {minutes: time_valid});
    const date = timerender.get_localized_date_or_time_for_format(valid_to, "dayofyear_year");
    const time = timerender.get_localized_date_or_time_for_format(valid_to, "time");

    return $t({defaultMessage: "Expires on {date} at {time}"}, {date, time});
}

function get_expiration_time_in_minutes() {
    switch (custom_expiration_time_unit) {
        case "hours":
            return custom_expiration_time_input * 60;
        case "days":
            return custom_expiration_time_input * 24 * 60;
        case "weeks":
            return custom_expiration_time_input * 7 * 24 * 60;
        default:
            return custom_expiration_time_input;
    }
}

function set_expires_on_text() {
    if ($("#expires_in").val() === "custom") {
        $("#expires_on").hide();
        $("#custom_expires_on").text(valid_to(get_expiration_time_in_minutes()));
    } else {
        $("#expires_on").show();
        $("#expires_on").text(valid_to($("#expires_in").val()));
    }
}

function set_custom_time_inputs_visibility() {
    if ($("#expires_in").val() === "custom") {
        $("#custom-expiration-time-input").val(custom_expiration_time_input);
        $("#custom-expiration-time-unit").val(custom_expiration_time_unit);
        $("#custom-invite-expiration-time").show();
    } else {
        $("#custom-invite-expiration-time").hide();
    }
}

function set_streams_to_join_list_visibility() {
    const default_streams_selected = $("#invite_select_default_streams").prop("checked");
    if (default_streams_selected) {
        $("#streams_to_add .invite-stream-controls").hide();
        $("#invite-stream-checkboxes").hide();
    } else {
        $("#streams_to_add .invite-stream-controls").show();
        $("#invite-stream-checkboxes").show();
    }
}

function open_invite_user_modal(e) {
    e.stopPropagation();
    e.preventDefault();

    gear_menu.close();

    const time_unit_choices = ["minutes", "hours", "days", "weeks"];
    const html_body = render_invite_user_modal({
        is_admin: page_params.is_admin,
        is_owner: page_params.is_owner,
        development_environment: page_params.development_environment,
        invite_as_options: settings_config.user_role_values,
        expires_in_options: settings_config.expires_in_values,
        time_choices: time_unit_choices,
        streams: get_invite_streams(),
        notifications_stream: stream_data.get_notifications_stream(),
        show_select_default_streams_option: stream_data.get_default_stream_ids().length !== 0,
        user_has_email_set: !settings_data.user_email_not_configured(),
    });

    function invite_user_modal_post_render() {
        $("#invite-user-modal .dialog_submit_button").prop("disabled", true);
        $("#email_invite_radio").prop("checked", true);

        if (!settings_data.user_can_create_multiuse_invite()) {
            $("#generate_multiuse_invite_radio").prop("disabled", true);
            $("#generate_multiuse_invite_radio_container").addClass("control-label-disabled");
            $("#generate_multiuse_invite_radio_container").addClass("disabled_setting_tooltip");
        }

        const user_has_email_set = !settings_data.user_email_not_configured();

        autosize($("#invitee_emails").trigger("focus"));

        set_custom_time_inputs_visibility();
        set_expires_on_text();
        set_streams_to_join_list_visibility();

        function toggle_invite_submit_button() {
            $("#invite-user-modal .dialog_submit_button").prop(
                "disabled",
                $("#invitee_emails").val().trim() === "" &&
                    !$("#generate_multiuse_invite_radio").is(":checked"),
            );
        }

        $("#invite-user-modal").on("input", "input, textarea, select", () => {
            toggle_invite_submit_button();
        });

        $("#invite-user-modal").on("change", "#email_invite_radio", () => {
            $("#invitee_emails_container").show();
            $("#invite-user-modal .dialog_submit_button").text($t({defaultMessage: "Invite"}));
            $("#invite-user-modal .dialog_submit_button").data(
                "loading-text",
                $t({defaultMessage: "Inviting..."}),
            );
            toggle_invite_submit_button();
            reset_error_messages();
        });

        $("#invite-user-modal").on("change", "#generate_multiuse_invite_radio", () => {
            $("#invitee_emails_container").hide();
            $("#invite-user-modal .dialog_submit_button").text(
                $t({defaultMessage: "Generate invite link"}),
            );
            $("#invite-user-modal .dialog_submit_button").data(
                "loading-text",
                $t({defaultMessage: "Generating link..."}),
            );
            $("#invite-user-modal .dialog_submit_button").prop("disabled", false);
            reset_error_messages();
        });

        $("#expires_in").on("change", () => {
            set_custom_time_inputs_visibility();
            set_expires_on_text();
        });

        $("#expires_on").text(valid_to($("#expires_in").val()));

        $("#custom-expiration-time-input").on("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                return;
            }
        });

        $(".custom-expiration-time").on("change", () => {
            custom_expiration_time_input = $("#custom-expiration-time-input").val();
            custom_expiration_time_unit = $("#custom-expiration-time-unit").val();
            $("#custom_expires_on").text(valid_to(get_expiration_time_in_minutes()));
        });

        $("#invite_check_all_button").on("click", () => {
            $("#invite-stream-checkboxes input[type=checkbox]").prop("checked", true);
            toggle_invite_submit_button();
        });

        $("#invite_uncheck_all_button").on("click", () => {
            $("#invite-stream-checkboxes input[type=checkbox]").prop("checked", false);
        });

        $("#invite_select_default_streams").on("change", () => {
            set_streams_to_join_list_visibility();
        });

        if (!user_has_email_set) {
            $("#invite-user-form :input").prop("disabled", !user_has_email_set);
        }

        if (!settings_data.user_can_invite_users_by_email()) {
            $("#email_invite_radio").prop("disabled", true);
            $("#email_invite_radio_container").addClass(
                "control-label-disabled disabled_setting_tooltip",
            );

            $("#generate_multiuse_invite_radio").prop("checked", true);
            $("#generate_multiuse_invite_radio").trigger("change");
        }
    }

    function invite_users() {
        const is_generate_invite_link = $("#generate_multiuse_invite_radio").prop("checked");
        if (is_generate_invite_link) {
            generate_multiuse_invite();
        } else {
            submit_invitation_form();
        }
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Invite users to Zulip"}),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Invite"}),
        id: "invite-user-modal",
        loading_spinner: true,
        on_click: invite_users,
        post_render: invite_user_modal_post_render,
    });
}

export function initialize() {
    $(document).on("click", ".invite-user-link", open_invite_user_modal);
}
