import $ from "jquery";

import render_announce_stream_docs from "../templates/announce_stream_docs.hbs";
import render_subscription_invites_warning_modal from "../templates/confirm_dialog/confirm_subscription_invites_warning.hbs";

import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import {$t, $t_html} from "./i18n";
import * as loading from "./loading";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_data from "./settings_data";
import * as stream_create_subscribers from "./stream_create_subscribers";
import * as stream_data from "./stream_data";
import * as stream_settings_ui from "./stream_settings_ui";
import * as ui_report from "./ui_report";

let created_stream;

export function reset_created_stream() {
    created_stream = undefined;
}

export function set_name(stream) {
    created_stream = stream;
}

export function get_name() {
    return created_stream;
}

class StreamSubscriptionError {
    report_no_subs_to_stream() {
        $("#stream_subscription_error").text(
            $t({defaultMessage: "You cannot create a stream with no subscribers!"}),
        );
        $("#stream_subscription_error").show();
    }

    cant_create_stream_without_susbscribing() {
        $("#stream_subscription_error").text(
            $t({
                defaultMessage:
                    "You must be an organization administrator to create a stream without subscribing.",
            }),
        );
        $("#stream_subscription_error").show();
    }

    clear_errors() {
        $("#stream_subscription_error").hide();
    }
}
const stream_subscription_error = new StreamSubscriptionError();

class StreamNameError {
    report_already_exists() {
        $("#stream_name_error").text(
            $t({defaultMessage: "A stream with this name already exists"}),
        );
        $("#stream_name_error").show();
    }

    clear_errors() {
        $("#stream_name_error").hide();
    }

    report_empty_stream() {
        $("#stream_name_error").text($t({defaultMessage: "A stream needs to have a name"}));
        $("#stream_name_error").show();
    }

    select() {
        $("#create_stream_name").trigger("focus").trigger("select");
    }

    pre_validate(stream_name) {
        // Don't worry about empty strings...we just want to call this
        // to warn users early before they start doing too much work
        // after they make the effort to type in a stream name.  (The
        // use case here is that I go to create a stream, only to find
        // out it already exists, and I was just too lazy to look at
        // the public streams that I'm not subscribed to yet.  Once I
        // realize the stream already exists, I may want to cancel.)
        if (stream_name && stream_data.get_sub(stream_name)) {
            this.report_already_exists();
            return;
        }

        this.clear_errors();
    }

    validate_for_submit(stream_name) {
        if (!stream_name) {
            this.report_empty_stream();
            this.select();
            return false;
        }

        if (stream_data.get_sub(stream_name)) {
            this.report_already_exists();
            this.select();
            return false;
        }

        // If we got this far, then we think we have a new unique stream
        // name, so we'll submit to the server.  (It's still plausible,
        // however, that there's some invite-only stream that we don't
        // know about locally that will cause a name collision.)
        return true;
    }
}
const stream_name_error = new StreamNameError();

// Stores the previous state of the stream creation checkbox.
let stream_announce_previous_value =
    settings_data.user_can_create_public_streams() ||
    settings_data.user_can_create_web_public_streams();

// Within the new stream modal...
function update_announce_stream_state() {
    // If there is no notifications_stream, we simply hide the widget.
    if (!stream_data.realm_has_notifications_stream()) {
        $("#announce-new-stream").hide();
        return;
    }

    // If the stream is invite only, disable the "Announce stream" option.
    // Otherwise enable it.
    const $announce_stream_checkbox = $("#announce-new-stream input");
    const $announce_stream_label = $("#announce-new-stream");
    let disable_it = false;
    const privacy_type = $("input:radio[name=privacy]:checked").val();
    const is_invite_only =
        privacy_type === "invite-only" || privacy_type === "invite-only-public-history";
    $announce_stream_label.removeClass("control-label-disabled");

    // Here, we arrange to save the state of the announce checkbox
    // when switching to creating a private stream; we will restore it
    // when switching back to a public stream. This input-disabled
    // check prevents overwriting stream_announce_previous_value with
    // the false when switching between private stream types.
    if (!$announce_stream_checkbox.prop("disabled")) {
        stream_announce_previous_value = $announce_stream_checkbox.prop("checked");
    }

    if (is_invite_only) {
        disable_it = true;
        $announce_stream_checkbox.prop("checked", false);
        $announce_stream_label.addClass("control-label-disabled");
    } else {
        // If the stream was already public, this will be a noop.
        $announce_stream_checkbox.prop("checked", stream_announce_previous_value);
    }

    $announce_stream_checkbox.prop("disabled", disable_it);
    $("#announce-new-stream").show();
}

function create_stream() {
    const data = {};
    const stream_name = $("#create_stream_name").val().trim();
    const description = $("#create_stream_description").val().trim();
    created_stream = stream_name;

    // Even though we already check to make sure that while typing the user cannot enter
    // newline characters (by pressing the Enter key) it would still be possible to copy
    // and paste over a description with newline characters in it. Prevent that.
    if (description.includes("\n")) {
        ui_report.client_error(
            $t_html({defaultMessage: "The stream description cannot contain newline characters."}),
            $(".stream_create_info"),
        );
        return undefined;
    }
    data.subscriptions = JSON.stringify([{name: stream_name, description}]);

    let invite_only;
    let history_public_to_subscribers;
    let is_web_public;
    const privacy_setting = $("#stream_creation_form input[name=privacy]:checked").val();

    switch (privacy_setting) {
        case "invite-only": {
            invite_only = true;
            history_public_to_subscribers = false;
            is_web_public = false;

            break;
        }
        case "invite-only-public-history": {
            invite_only = true;
            history_public_to_subscribers = true;
            is_web_public = false;

            break;
        }
        case "web-public": {
            invite_only = false;
            history_public_to_subscribers = true;
            is_web_public = true;

            break;
        }
        default: {
            invite_only = false;
            history_public_to_subscribers = true;
            is_web_public = false;
        }
    }

    data.is_web_public = JSON.stringify(is_web_public);
    data.invite_only = JSON.stringify(invite_only);
    data.history_public_to_subscribers = JSON.stringify(history_public_to_subscribers);

    const stream_post_policy = Number.parseInt(
        $("#stream_creation_form select[name=stream-post-policy]").val(),
        10,
    );

    data.stream_post_policy = JSON.stringify(stream_post_policy);

    let message_retention_selection = $(
        "#stream_creation_form select[name=stream_message_retention_setting]",
    ).val();
    if (message_retention_selection === "retain_for_period") {
        message_retention_selection = Number.parseInt(
            $("#stream_creation_form input[name=stream-message-retention-days]").val(),
            10,
        );
    }

    data.message_retention_days = JSON.stringify(message_retention_selection);

    const announce =
        stream_data.realm_has_notifications_stream() &&
        $("#announce-new-stream input").prop("checked");
    data.announce = JSON.stringify(announce);

    // TODO: We can eliminate the user_ids -> principals conversion
    //       once we upgrade the backend to accept user_ids.
    const user_ids = stream_create_subscribers.get_principals();
    data.principals = JSON.stringify(user_ids);

    loading.make_indicator($("#stream_creating_indicator"), {
        text: $t({defaultMessage: "Creating stream..."}),
    });

    // Subscribe yourself and possible other people to a new stream.
    return channel.post({
        url: "/json/users/me/subscriptions",
        data,
        success() {
            $("#create_stream_name").val("");
            $("#create_stream_description").val("");
            ui_report.success(
                $t_html({defaultMessage: "Stream successfully created!"}),
                $(".stream_create_info"),
            );
            loading.destroy_indicator($("#stream_creating_indicator"));
            // The rest of the work is done via the subscribe event we will get
        },
        error(xhr) {
            const msg = JSON.parse(xhr.responseText).msg;
            if (msg.includes("access")) {
                // If we can't access the stream, we can safely assume it's
                // a duplicate stream that we are not invited to.
                //
                // BUG: This check should be using error codes, not
                // parsing the error string, so it works correctly
                // with i18n.  And likely we should be reporting the
                // error text directly rather than turning it into
                // "Error creating stream"?
                stream_name_error.report_already_exists(stream_name);
                stream_name_error.trigger("select");
            }

            ui_report.error(
                $t_html({defaultMessage: "Error creating stream"}),
                xhr,
                $(".stream_create_info"),
            );
            loading.destroy_indicator($("#stream_creating_indicator"));
        },
    });
}

export function new_stream_clicked(stream_name) {
    // this changes the tab switcher (settings/preview) which isn't necessary
    // to a add new stream title.
    stream_settings_ui.show_subs_pane.create_stream();
    $(".stream-row.active").removeClass("active");

    if (stream_name !== "") {
        $("#create_stream_name").val(stream_name);
    }
    show_new_stream_modal();
    $("#create_stream_name").trigger("focus");
}

function clear_error_display() {
    stream_name_error.clear_errors();
    $(".stream_create_info").hide();
    stream_subscription_error.clear_errors();
}

export function show_new_stream_modal() {
    $("#stream-creation").removeClass("hide");
    $(".right .settings").hide();
    stream_settings_ui.hide_or_disable_stream_privacy_options_if_required($("#stream-creation"));

    stream_create_subscribers.build_widgets();

    // Select the first visible and enabled choice for stream privacy.
    $("#make-invite-only input:visible:not([disabled])").first().prop("checked", true);
    // Make the options default to the same each time:
    // "announce stream" on.
    $("#stream_creation_form .stream-message-retention-days-input").hide();
    $("#stream_creation_form select[name=stream_message_retention_setting]").val("realm_default");

    // Add listener to .show stream-message-retention-days-input that we've hidden above
    $("#stream_creation_form .stream_message_retention_setting").on("change", (e) => {
        if (e.target.value === "retain_for_period") {
            $("#stream_creation_form .stream-message-retention-days-input").show();
        } else {
            $("#stream_creation_form .stream-message-retention-days-input").hide();
        }
    });

    update_announce_stream_state();
    clear_error_display();
}

export function set_up_handlers() {
    const $people_to_add_holder = $("#people_to_add").expectOne();
    stream_create_subscribers.create_handlers($people_to_add_holder);

    const $container = $("#stream-creation").expectOne();

    $container.on("change", ".stream-privacy-values input", update_announce_stream_state);

    $container.on("click", ".finalize_create_stream", (e) => {
        e.preventDefault();
        clear_error_display();

        const stream_name = $("#create_stream_name").val().trim();
        const name_ok = stream_name_error.validate_for_submit(stream_name);

        if (!name_ok) {
            return;
        }

        const principals = stream_create_subscribers.get_principals();
        if (principals.length === 0) {
            stream_subscription_error.report_no_subs_to_stream();
            return;
        }
        if (!principals.includes(people.my_current_user_id()) && !page_params.is_admin) {
            stream_subscription_error.cant_create_stream_without_susbscribing();
            return;
        }

        if (principals.length >= 50) {
            const html_body = render_subscription_invites_warning_modal({
                stream_name,
                count: principals.length,
            });

            confirm_dialog.launch({
                html_heading: $t_html({defaultMessage: "Large number of subscribers"}),
                html_body,
                on_click: () => {
                    create_stream();
                },
            });
        } else {
            create_stream();
        }
    });

    $container.on("input", "#create_stream_name", () => {
        const stream_name = $("#create_stream_name").val().trim();

        // This is an inexpensive check.
        stream_name_error.pre_validate(stream_name);
    });

    $container.on("mouseover", "#announce-stream-docs", (e) => {
        const $announce_stream_docs = $("#announce-stream-docs");
        $announce_stream_docs.popover({
            placement: "right",
            content: render_announce_stream_docs({
                notifications_stream: stream_data.get_notifications_stream(),
            }),
            html: true,
            trigger: "manual",
        });
        $announce_stream_docs.popover("show");
        $announce_stream_docs.data("popover").tip().css("z-index", 2000);
        $announce_stream_docs
            .data("popover")
            .tip()
            .find(".popover-content")
            .css("margin", "9px 14px");
        e.stopPropagation();
    });
    $container.on("mouseout", "#announce-stream-docs", (e) => {
        $("#announce-stream-docs").popover("hide");
        e.stopPropagation();
    });

    // Do not allow the user to enter newline characters while typing out the
    // stream's description during it's creation.
    $container.on("keydown", "#create_stream_description", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
        }
    });
}
