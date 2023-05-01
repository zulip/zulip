/* Compose box module responsible for the message's recipient */

import $ from "jquery";
import _ from "lodash";

import * as compose_banner from "./compose_banner";
import * as compose_fade from "./compose_fade";
import * as compose_pm_pill from "./compose_pm_pill";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as compose_validate from "./compose_validate";
import {DropdownListWidget} from "./dropdown_list_widget";
import {$t} from "./i18n";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
import * as stream_bar from "./stream_bar";
import * as stream_data from "./stream_data";
import * as ui_util from "./ui_util";
import * as util from "./util";

export let compose_recipient_widget;

const DIRECT_MESSAGE = "direct";

function composing_to_current_topic_narrow() {
    return (
        util.lower_same(compose_state.stream_name(), narrow_state.stream() || "") &&
        util.lower_same(compose_state.topic(), narrow_state.topic() || "")
    );
}

function composing_to_current_private_message_narrow() {
    const compose_state_recipient = compose_state.private_message_recipient();
    const narrow_state_recipient = narrow_state.pm_emails_string();
    return (
        compose_state_recipient &&
        narrow_state_recipient &&
        _.isEqual(
            compose_state_recipient
                .split(",")
                .map((s) => s.trim())
                .sort(),
            narrow_state_recipient
                .split(",")
                .map((s) => s.trim())
                .sort(),
        )
    );
}

export function update_narrow_to_recipient_visibility() {
    const message_type = compose_state.get_message_type();
    if (message_type === "stream") {
        const stream_name = compose_state.stream_name();
        const stream_exists = Boolean(stream_data.get_stream_id(stream_name));

        if (
            stream_exists &&
            !composing_to_current_topic_narrow() &&
            compose_state.has_full_recipient()
        ) {
            $(".narrow_to_compose_recipients").toggleClass("invisible", false);
            return;
        }
    } else if (message_type === "private") {
        const recipients = compose_state.private_message_recipient();
        if (
            recipients &&
            !composing_to_current_private_message_narrow() &&
            compose_state.has_full_recipient()
        ) {
            $(".narrow_to_compose_recipients").toggleClass("invisible", false);
            return;
        }
    }
    $(".narrow_to_compose_recipients").toggleClass("invisible", true);
}

function update_fade() {
    if (!compose_state.composing()) {
        return;
    }

    const msg_type = compose_state.get_message_type();

    // It's possible that the new topic is not a resolved topic
    // so we clear the older warning.
    compose_validate.clear_topic_resolved_warning();

    compose_validate.warn_if_topic_resolved();
    compose_fade.set_focused_recipient(msg_type);
    compose_fade.update_all();
}

export function update_on_recipient_change() {
    update_fade();
    update_narrow_to_recipient_visibility();
}

export function open_compose_stream_dropup() {
    if ($("#id_compose_select_recipient").hasClass("open")) {
        return;
    }
    // We trigger a click rather than directly toggling the element;
    // this is important to ensure the filter text gets cleared when
    // reopening the widget after previous use.
    $("#id_compose_select_recipient > .dropdown-toggle").trigger("click");
}

export function check_stream_posting_policy_for_compose_box(stream_name) {
    const stream = stream_data.get_sub_by_name(stream_name);
    if (!stream) {
        return;
    }
    const can_post_messages_in_stream = stream_data.can_post_messages_in_stream(stream);
    if (!can_post_messages_in_stream) {
        $(".compose_right_float_container").addClass("disabled-compose-send-button-container");
        compose_banner.show_error_message(
            $t({
                defaultMessage: "You do not have permission to post in this stream.",
            }),
            compose_banner.CLASSNAMES.no_post_permissions,
        );
    } else {
        $(".compose_right_float_container").removeClass("disabled-compose-send-button-container");
        compose_banner.clear_errors();
    }
}

function switch_message_type(message_type) {
    $("#compose-content .alert").hide();

    compose_state.set_message_type(message_type);

    const opts = {
        message_type,
        stream: compose_state.stream_name(),
        topic: compose_state.topic(),
        private_message_recipient: compose_state.private_message_recipient(),
    };
    update_compose_for_message_type(message_type, opts);
    update_placeholder_text();
    compose_ui.set_focus(message_type, opts);
}

export function update_compose_for_message_type(message_type) {
    if (message_type === "stream") {
        $("#compose-direct-recipient").hide();
        $("#stream_message_recipient_topic").show();
        $("#stream_toggle").addClass("active");
        $("#private_message_toggle").removeClass("active");
        $("#compose-recipient").removeClass("compose-recipient-direct-selected");
    } else {
        $("#compose-direct-recipient").show();
        $("#stream_message_recipient_topic").hide();
        $("#stream_toggle").removeClass("active");
        $("#private_message_toggle").addClass("active");
        $("#compose-recipient").addClass("compose-recipient-direct-selected");
        // TODO: When "Direct message" is selected, we show "DM" on the dropdown
        // button. It would be nice if the dropdown supported a way to attach
        // the "DM" button display string so we wouldn't have to manually change
        // it here.
        const direct_message_label = $t({defaultMessage: "DM"});
        $("#compose_select_recipient_name").html(
            `<i class="zulip-icon zulip-icon-users stream-privacy-type-icon"></i> ${direct_message_label}`,
        );
    }
    compose_banner.clear_errors();
    compose_banner.clear_warnings();
}

export function on_compose_select_recipient_update(new_value) {
    const message_type = compose_state.get_message_type();
    if (new_value === DIRECT_MESSAGE) {
        // TODO: In theory, we could do something more lightweight in
        // the case it's already that value, but doing nothing would
        // display the wrong and fail to update focus properly.
        switch_message_type("private");

        if (compose_state.private_message_recipient().length === 0) {
            $("#private_message_recipient").trigger("focus").trigger("select");
        }
    } else {
        const $stream_header_colorblock = $(
            "#compose_recipient_selection_dropdown .stream_header_colorblock",
        );
        stream_bar.decorate(new_value, $stream_header_colorblock);
        if (message_type === "private") {
            switch_message_type("stream");
        }
        // Always move focus to the topic input even if it's not empty,
        // since it's likely the user will want to update the topic
        // after updating the stream.
        ui_util.place_caret_at_end($("#stream_message_recipient_topic")[0]);
        check_stream_posting_policy_for_compose_box(new_value);
    }
    update_on_recipient_change();
}

export function update_stream_dropdown_options() {
    compose_recipient_widget.replace_data(get_options_for_recipient_widget());
}

export function possibly_update_dropdown_selection(old_stream_name, new_stream_name) {
    const selected_stream = compose_state.stream_name();
    if (selected_stream === old_stream_name) {
        compose_state.set_stream_name(new_stream_name);
    }
}

function get_options_for_recipient_widget() {
    const options = stream_data
        .subscribed_subs()
        .map((stream) => ({
            name: stream.name,
            value: stream.name,
            stream,
        }))
        .sort((a, b) => {
            if (a.name.toLowerCase() < b.name.toLowerCase()) {
                return -1;
            }
            if (a.name.toLowerCase() > b.name.toLowerCase()) {
                return 1;
            }
            return 0;
        });

    const direct_messages_option = {
        name: $t({defaultMessage: "Direct message"}),
        value: DIRECT_MESSAGE,
        is_direct_message: true,
    };
    if (
        page_params.realm_private_message_policy ===
        settings_config.private_message_policy_values.by_anyone.code
    ) {
        options.unshift(direct_messages_option);
    } else {
        options.push(direct_messages_option);
    }
    return options;
}

export function initialize() {
    const opts = {
        widget_name: "compose_select_recipient",
        data: get_options_for_recipient_widget(),
        default_text: $t({defaultMessage: "Select a stream"}),
        value: null,
        on_update: on_compose_select_recipient_update,
    };
    compose_recipient_widget = new DropdownListWidget(opts);
    compose_recipient_widget.setup();

    $("#compose_select_recipient_widget").on("select", (e) => {
        // We often focus on input fields to bring the user to fill it out.
        // In this situation, a focus on the dropdown div opens the dropdown
        // menu so that the user can select an option.
        open_compose_stream_dropup();
        e.stopPropagation();
    });

    // `keyup` isn't relevant for streams since it registers as a change only
    // when an item in the dropdown is selected.
    $("#stream_message_recipient_topic,#private_message_recipient").on(
        "keyup",
        update_on_recipient_change,
    );
    // changes for the stream dropdown are handled in on_compose_select_recipient_update
    $("#stream_message_recipient_topic,#private_message_recipient").on("change", () => {
        update_on_recipient_change();
        compose_state.set_recipient_edited_manually(true);
    });
}

export function update_placeholder_text() {
    // Change compose placeholder text only if compose box is open.
    if (!$("#compose-textarea").is(":visible")) {
        return;
    }

    const opts = {
        message_type: compose_state.get_message_type(),
        stream: compose_state.stream_name(),
        topic: compose_state.topic(),
        // TODO: to remove a circular import, PM recipient needs
        // to be calculated in compose_state instead of compose_pm_pill.
        private_message_recipient: compose_pm_pill.get_emails(),
    };

    $("#compose-textarea").attr("placeholder", compose_ui.compute_placeholder_text(opts));
}
