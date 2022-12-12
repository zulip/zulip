import $ from "jquery";
import {Sortable} from "sortablejs";

import render_poll_modal_option from "../templates/poll_modal_option.hbs";

import * as composebox_typeahead from "./composebox_typeahead";
import {DirectMessageRecipientPill} from "./direct_message_recipient_pill";
import {DropdownListWidget} from "./dropdown_list_widget";
import {$t} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as message_edit from "./message_edit";
import * as stream_bar from "./stream_bar";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";

let recipient_type;
let poll_pm_pill;

function create_option_row(container) {
    const row = render_poll_modal_option();
    $(container).append(row);
}

function add_option_row(e) {
    // if the option triggering the input event e is not the last,
    // that is, its next sibling has the class `option-row`, we
    // do not add a new option row and return from this function
    // This handles a case when the next empty input row is already
    // added and user is updating the above row(s).
    if ($(e.target).parent().next().hasClass("option-row")) {
        return;
    }
    const $options_div = $(e.target).parent().parent();
    create_option_row($options_div);
}

function delete_option_row(e) {
    const $row = $(e.currentTarget).parent();
    $row.remove();
}

function poll_options_setup() {
    const $poll_options_list = $("#add-poll-form .poll-options-list");

    $poll_options_list.on("input", ".option-row input", add_option_row);
    $poll_options_list.on("click", "button.delete-option", delete_option_row);

    // setTimeout is needed to here to give time for simplebar to initialise
    setTimeout(() => {
        Sortable.create($("#add-poll-form .poll-options-list .simplebar-content")[0], {
            onUpdate() {},
            filter: "input",
            preventOnFilter: false,
        });
    }, 0);
}

function stream_recipient_setup() {
    const $topic_input = $("#add-poll-form .inline_topic_edit");
    const $stream_id = $("#add-poll-form .stream_id");
    const $stream_header_colorblock = $("#dialog_widget_modal .topic_stream_edit_header").find(
        ".stream_header_colorblock",
    );

    const stream_id = Number($stream_id.val(), 10);
    const stream_name = sub_store.get(stream_id)?.name;
    stream_bar.decorate(stream_name, $stream_header_colorblock, false);
    const streams_list = message_edit.get_available_streams_for_moving_messages(stream_id);
    let stream_widget;
    const opts = {
        widget_name: "select_stream",
        data: streams_list,
        default_text: $t({defaultMessage: "Select a stream"}),
        include_current_item: false,
        value: stream_id,
        on_update() {
            const new_stream_id = Number(stream_widget.value(), 10);
            $stream_id.val(new_stream_id);
            const new_stream_name = sub_store.get(new_stream_id).name;
            $topic_input.data("typeahead").unlisten();
            composebox_typeahead.initialize_topic_edit_typeahead(
                $topic_input,
                new_stream_name,
                false,
            );
        },
    };
    stream_widget = new DropdownListWidget(opts);
    composebox_typeahead.initialize_topic_edit_typeahead($topic_input, stream_name, false);
    stream_widget.setup();

    $("#add-poll-form").on("click keypress", ".stream-dropdown .list_item", (e) => {
        // We want the dropdown to collapse once any of the list item is pressed
        // and thus don't want to kill the natural bubbling of event.
        e.preventDefault();
        if (e.type === "keypress" && !keydown_util.is_enter_event(e)) {
            return;
        }
        const stream_name = stream_data.maybe_get_stream_name(
            Number.parseInt(stream_widget.value(), 10),
        );
        stream_bar.decorate(stream_name, $stream_header_colorblock, false);
    });
}

function private_recipient_setup() {
    poll_pm_pill = new DirectMessageRecipientPill($("#private_message_recipient_poll").parent());
    composebox_typeahead.initialize_poll_private_recipient_typeahead(poll_pm_pill);
    const initial_pm_recipient = $("#add-poll-form .initial_pm_recipient").val();
    poll_pm_pill.set_from_emails(initial_pm_recipient);
}

export function setup() {
    poll_options_setup();
    recipient_type = $("#add-poll-form .message_type").val();
    if (recipient_type === "stream") {
        stream_recipient_setup();
    } else if (recipient_type === "private") {
        private_recipient_setup();
    }
}

function frame_poll_message_content() {
    // if the question field is left empty we use the placeholder instead as
    // the question is anyway editable by the poll creator in the widget
    const question =
        $("#poll-question-textarea").val().trim() ||
        $("#poll-question-textarea").attr("placeholder");
    const options = $(".poll-option-input")
        .map(function () {
            return $(this).val().trim();
        })
        .toArray()
        .filter(Boolean);
    return "/poll " + question + "\n" + options.join("\n");
}

function get_stream_name() {
    const stream_id = Number($("#add-poll-form .stream_id").val(), 10);
    return sub_store.get(stream_id).name;
}

function get_topic() {
    return $("#add-poll-form .inline_topic_edit").val().trim();
}

function get_pm_recipient() {
    return poll_pm_pill.get_emails();
}

export function get_poll_message_data() {
    const message_content = frame_poll_message_content();
    if (recipient_type === "stream") {
        const stream_name = get_stream_name();
        const topic = get_topic();
        return {message_content, stream_name, topic};
    } else if (recipient_type === "private") {
        const private_message_recipient = get_pm_recipient();
        return {message_content, private_message_recipient};
    }
    return {message_content};
}
