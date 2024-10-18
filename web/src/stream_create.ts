import $ from "jquery";
import assert from "minimalistic-assert";
import {z} from "zod";

import render_subscription_invites_warning_modal from "../templates/confirm_dialog/confirm_subscription_invites_warning.hbs";

import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as loading from "./loading";
import * as onboarding_steps from "./onboarding_steps";
import * as people from "./people";
import * as settings_data from "./settings_data";
import {current_user, realm} from "./state_data";
import * as stream_create_subscribers from "./stream_create_subscribers";
import * as stream_data from "./stream_data";
import * as stream_settings_components from "./stream_settings_components";
import * as stream_ui_updates from "./stream_ui_updates";
import type {HTMLSelectOneElement} from "./types";
import * as ui_report from "./ui_report";
import * as util from "./util";

let created_stream: string | undefined;
// Default is true since the current user is added to
// the subscribers list initially.
let current_user_subscribed_to_created_stream = true;

export function reset_created_stream(): void {
    created_stream = undefined;
}

export function set_name(stream: string): void {
    created_stream = stream;
}

export function get_name(): string | undefined {
    return created_stream;
}

export function reset_current_user_subscribed_to_created_stream(): void {
    current_user_subscribed_to_created_stream = true;
}

export function set_current_user_subscribed_to_created_stream(is_subscribed: boolean): void {
    current_user_subscribed_to_created_stream = is_subscribed;
}

export function get_current_user_subscribed_to_created_stream(): boolean {
    return current_user_subscribed_to_created_stream;
}

export function set_first_stream_created_modal_shown(): void {
    onboarding_steps.post_onboarding_step_as_read("first_stream_created_banner");
}

export function should_show_first_stream_created_modal(): boolean {
    return onboarding_steps.ONE_TIME_NOTICES_TO_DISPLAY.has("first_stream_created_banner");
}

class StreamSubscriptionError {
    report_no_subs_to_stream(): void {
        $("#stream_subscription_error").text(
            $t({defaultMessage: "You cannot create a channel with no subscribers."}),
        );
        $("#stream_subscription_error").show();
    }

    cant_create_stream_without_subscribing(): void {
        $("#stream_subscription_error").text(
            $t({
                defaultMessage:
                    "You must be an organization administrator to create a channel without subscribing.",
            }),
        );
        $("#stream_subscription_error").show();
    }

    clear_errors(): void {
        $("#stream_subscription_error").hide();
    }
}
const stream_subscription_error = new StreamSubscriptionError();

class StreamNameError {
    report_already_exists(): void {
        $("#stream_name_error").text(
            $t({defaultMessage: "A channel with this name already exists."}),
        );
        $("#stream_name_error").show();
    }

    clear_errors(): void {
        $("#stream_name_error").hide();
    }

    report_empty_stream(): void {
        $("#stream_name_error").text($t({defaultMessage: "Choose a name for the new channel."}));
        $("#stream_name_error").show();
    }

    select(): void {
        $("#create_stream_name").trigger("focus").trigger("select");
    }

    pre_validate(stream_name: string): void {
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

    validate_for_submit(stream_name: string): boolean {
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

function toggle_advanced_configurations(): void {
    const $advanced_configurations_view = $(".advanced-configurations-collapase-view");
    const $toggle_button = $(".toggle-advanced-configurations-icon");

    if ($advanced_configurations_view.is(":visible")) {
        // Toggle into the condensed state
        $advanced_configurations_view.addClass("hide");
        $toggle_button.addClass("fa-caret-right");
        $toggle_button.removeClass("fa-caret-down");
    } else {
        // Toggle into the expanded state
        $advanced_configurations_view.removeClass("hide");
        $toggle_button.addClass("fa-caret-down");
        $toggle_button.removeClass("fa-caret-right");
    }
}

$("body").on("click", ".settings-sticky-footer #stream_creation_go_to_subscribers", (e) => {
    e.preventDefault();
    e.stopPropagation();

    const stream_name = $<HTMLInputElement>("input#create_stream_name").val()!.trim();
    const is_stream_name_valid = stream_name_error.validate_for_submit(stream_name);
    const privacy_type = $("#stream_creation_form input[type=radio][name=privacy]:checked").val();
    let invite_only = false;
    let is_web_public = false;

    if (is_stream_name_valid) {
        if (privacy_type === "invite-only" || privacy_type === "invite-only-public-history") {
            invite_only = true;
        } else if (privacy_type === "web-public") {
            is_web_public = true;
        }

        const sub = {
            name: stream_name,
            invite_only,
            is_web_public,
        };
        stream_settings_components.show_subs_pane.create_stream("subscribers_container", sub);
    }
});

$("body").on(
    "click",
    ".settings-sticky-footer #stream_creation_go_to_configure_channel_settings",
    (e) => {
        e.preventDefault();
        e.stopPropagation();
        stream_settings_components.show_subs_pane.create_stream("configure_channel_settings");
    },
);

$("body").on("click", ".advanced-configurations-container .advance-config-title-container", (e) => {
    e.stopPropagation();
    toggle_advanced_configurations();
});

// Stores the previous state of the stream creation checkbox.
let stream_announce_previous_value: boolean;

// Within the new stream modal...
function update_announce_stream_state(): void {
    // If there is no new_stream_announcements_stream, we simply hide the widget.
    if (stream_data.get_new_stream_announcements_stream() === "") {
        $("#announce-new-stream").hide();
        return;
    }

    // If the stream is invite only, disable the "Announce stream" option.
    // Otherwise enable it.
    const $announce_stream_checkbox = $<HTMLInputElement>("#announce-new-stream input");
    const $announce_stream_label = $("#announce-new-stream");
    let disable_it = false;
    const privacy_type = $("#stream_creation_form input[type=radio][name=privacy]:checked").val();
    const is_invite_only =
        privacy_type === "invite-only" || privacy_type === "invite-only-public-history";
    $announce_stream_label.removeClass("control-label-disabled");

    // Here, we arrange to save the state of the announce checkbox
    // when switching to creating a private stream; we will restore it
    // when switching back to a public stream. This input-disabled
    // check prevents overwriting stream_announce_previous_value with
    // the false when switching between private stream types.
    if (!$announce_stream_checkbox.prop("disabled")) {
        stream_announce_previous_value = util.the($announce_stream_checkbox).checked;
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

function create_stream(): void {
    const stream_name = $<HTMLInputElement>("input#create_stream_name").val()!.trim();
    const description = $<HTMLInputElement>("input#create_stream_description").val()!.trim();
    created_stream = stream_name;

    // Even though we already check to make sure that while typing the user cannot enter
    // newline characters (by pressing the Enter key) it would still be possible to copy
    // and paste over a description with newline characters in it. Prevent that.
    if (description.includes("\n")) {
        ui_report.client_error(
            $t_html({defaultMessage: "The channel description cannot contain newline characters."}),
            $(".stream_create_info"),
        );
        return;
    }
    const subscriptions = JSON.stringify([{name: stream_name, description}]);

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

    const default_stream = util.the(
        $<HTMLInputElement>("#stream_creation_form input.is_default_stream"),
    ).checked;

    const stream_post_policy = Number.parseInt(
        $<HTMLSelectOneElement>(
            "#stream_creation_form select:not([multiple])[name=stream-post-policy]",
        ).val()!,
        10,
    );

    let message_retention_selection = $(
        "#stream_creation_form select[name=stream_message_retention_setting]",
    ).val();
    if (message_retention_selection === "custom_period") {
        message_retention_selection = Number.parseInt(
            $<HTMLInputElement>(
                "#stream_creation_form input[name=stream-message-retention-days]",
            ).val()!,
            10,
        );
    }

    let announce =
        stream_data.get_new_stream_announcements_stream() !== "" &&
        util.the($<HTMLInputElement>("#announce-new-stream input")).checked;

    if (
        stream_data.get_new_stream_announcements_stream() === "" &&
        stream_data.realm_has_new_stream_announcements_stream() &&
        !invite_only
    ) {
        announce = true;
    }

    // TODO: We can eliminate the user_ids -> principals conversion
    //       once we upgrade the backend to accept user_ids.
    const user_ids = stream_create_subscribers.get_principals();
    const principals = JSON.stringify(user_ids);
    set_current_user_subscribed_to_created_stream(user_ids.includes(current_user.user_id));

    assert(stream_settings_components.new_stream_can_remove_subscribers_group_widget !== null);
    const widget_value =
        stream_settings_components.new_stream_can_remove_subscribers_group_widget.value();
    assert(typeof widget_value === "number");
    const can_remove_subscribers_group_id = widget_value;

    loading.make_indicator($("#stream_creating_indicator"), {
        text: $t({defaultMessage: "Creating channel..."}),
    });

    const data = {
        subscriptions,
        is_web_public: JSON.stringify(is_web_public),
        invite_only: JSON.stringify(invite_only),
        history_public_to_subscribers: JSON.stringify(history_public_to_subscribers),
        is_default_stream: JSON.stringify(default_stream),
        stream_post_policy: JSON.stringify(stream_post_policy),
        message_retention_days: JSON.stringify(message_retention_selection),
        announce: JSON.stringify(announce),
        principals,
        can_remove_subscribers_group: can_remove_subscribers_group_id,
    };

    // Subscribe yourself and possible other people to a new stream.
    void channel.post({
        url: "/json/users/me/subscriptions",
        data,
        success(): void {
            $("#create_stream_name").val("");
            $("#create_stream_description").val("");
            loading.destroy_indicator($("#stream_creating_indicator"));
            // The rest of the work is done via the subscribe event we will get
        },
        error(xhr): void {
            const error_message = z.object({msg: z.string().optional()}).parse(xhr.responseJSON);
            if (error_message?.msg?.includes("access")) {
                // If we can't access the stream, we can safely
                // assume it's a duplicate stream that we are not invited to.
                //
                // BUG: This check should be using error codes, not
                // parsing the error string, so it works correctly
                // with i18n.  And likely we should be reporting the
                // error text directly rather than turning it into
                // "Error creating channel"?
                stream_name_error.report_already_exists();
                stream_name_error.select();
            }

            ui_report.error(
                $t_html({defaultMessage: "Error creating channel"}),
                xhr,
                $(".stream_create_info"),
            );
            loading.destroy_indicator($("#stream_creating_indicator"));
        },
    });
}

export function new_stream_clicked(stream_name: string): void {
    // this changes the tab switcher (settings/preview) which isn't necessary
    // to a add new stream title.
    stream_settings_components.show_subs_pane.create_stream();
    $(".stream-row.active").removeClass("active");

    if (stream_name !== "") {
        $("#create_stream_name").val(stream_name);
    }
    show_new_stream_modal();
    $("#create_stream_name").trigger("focus");
}

function clear_error_display(): void {
    stream_name_error.clear_errors();
    $(".stream_create_info").hide();
    stream_subscription_error.clear_errors();
}

export function show_new_stream_modal(): void {
    $("#stream-creation").removeClass("hide");
    $(".right .settings").hide();
    stream_settings_components.hide_or_disable_stream_privacy_options_if_required(
        $("#stream-creation"),
    );

    stream_create_subscribers.build_widgets();

    // Select the first visible and enabled choice for stream privacy.
    $("#make-invite-only input:visible:not([disabled])").first().prop("checked", true);
    // Make the options default to the same each time

    // The message retention setting is visible to owners only. The below block
    // sets the default state of setting if it is visible.
    if (current_user.is_owner) {
        $("#stream_creation_form .stream-message-retention-days-input").hide();
        $("#stream_creation_form select[name=stream_message_retention_setting]").val(
            "realm_default",
        );

        // The user is not allowed to set the setting to amy value other than
        // "realm_default" for realms on limited plans, so we disable the setting.
        $("#stream_creation_form select[name=stream_message_retention_setting]").prop(
            "disabled",
            !realm.zulip_plan_is_not_limited,
        );

        // This listener is only needed if the dropdown setting is enabled.
        if (realm.zulip_plan_is_not_limited) {
            // Add listener to .show stream-message-retention-days-input that we've hidden above
            $<HTMLSelectOneElement>("#stream_creation_form .stream_message_retention_setting").on(
                "change",
                (e) => {
                    if (e.target.value === "custom_period") {
                        $("#stream_creation_form .stream-message-retention-days-input").show();
                    } else {
                        $("#stream_creation_form .stream-message-retention-days-input").hide();
                    }
                },
            );
        }
    }
    const $add_subscribers_container = $(
        "#stream_creation_form .subscriber_list_settings",
    ).expectOne();

    stream_ui_updates.enable_or_disable_add_subscribers_elements(
        $add_subscribers_container,
        settings_data.user_can_subscribe_other_users(),
        true,
    );

    // set default state for "announce stream" and "default stream" option.
    $("#stream_creation_form .default-stream input").prop("checked", false);
    update_announce_stream_state();
    stream_ui_updates.update_default_stream_and_stream_privacy_state($("#stream-creation"));
    clear_error_display();
}

export function set_up_handlers(): void {
    stream_announce_previous_value =
        settings_data.user_can_create_public_streams() ||
        settings_data.user_can_create_web_public_streams();

    const $subscribers_container = $(".subscribers_container").expectOne();
    stream_create_subscribers.create_handlers($subscribers_container);

    const $container = $("#stream-creation").expectOne();

    $container.on("change", ".stream-privacy-values input", () => {
        update_announce_stream_state();
        stream_ui_updates.update_default_stream_and_stream_privacy_state($container);
    });

    $container.on("change", ".default-stream input", () => {
        stream_ui_updates.update_default_stream_and_stream_privacy_state($container);
    });

    $container.on("click", ".finalize_create_stream", (e) => {
        e.preventDefault();
        clear_error_display();

        const stream_name = $<HTMLInputElement>("input#create_stream_name").val()!.trim();
        const name_ok = stream_name_error.validate_for_submit(stream_name);

        if (!name_ok) {
            stream_settings_components.show_subs_pane.create_stream("configure_channel_settings");
            return;
        }

        const principals = stream_create_subscribers.get_principals();
        if (principals.length === 0) {
            stream_subscription_error.report_no_subs_to_stream();
            return;
        }
        if (!principals.includes(people.my_current_user_id()) && !current_user.is_admin) {
            stream_subscription_error.cant_create_stream_without_subscribing();
            return;
        }

        if (principals.length >= 50) {
            const html_body = render_subscription_invites_warning_modal({
                channel_name: stream_name,
                count: principals.length,
            });

            confirm_dialog.launch({
                html_heading: $t_html({defaultMessage: "Large number of subscribers"}),
                html_body,
                on_click() {
                    create_stream();
                },
            });
        } else {
            create_stream();
        }
    });

    $container.on("input", "#create_stream_name", () => {
        const stream_name = $<HTMLInputElement>("input#create_stream_name").val()!.trim();

        // This is an inexpensive check.
        stream_name_error.pre_validate(stream_name);
    });

    // Do not allow the user to enter newline characters while typing out the
    // stream's description during it's creation.
    $container.on("keydown", "#create_stream_description", (e) => {
        if (keydown_util.is_enter_event(e)) {
            e.preventDefault();
        }
    });

    assert(stream_settings_components.new_stream_can_remove_subscribers_group_widget !== null);
    stream_settings_components.new_stream_can_remove_subscribers_group_widget.setup();
}
