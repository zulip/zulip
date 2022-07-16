import $ from "jquery";
import {Sortable} from "sortablejs";

import render_poll_modal_option from "../templates/poll_modal_option.hbs";

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

export function poll_options_setup() {
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

export function frame_poll_message_content() {
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
