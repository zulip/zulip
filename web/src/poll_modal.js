import $ from "jquery";
import {Sortable} from "sortablejs";

import render_poll_modal_option from "../templates/poll_modal_option.hbs";

function create_option_row($last_option_row_input) {
    const row = render_poll_modal_option();
    const $row_container = $last_option_row_input.closest(".simplebar-content");
    $row_container.append(row);
}

function add_option_row(e) {
    // if the option triggering the input event e is not the last,
    // that is, its next sibling has the class `option-row`, we
    // do not add a new option row and return from this function
    // This handles a case when the next empty input row is already
    // added and user is updating the above row(s).
    if ($(e.target).closest(".option-row").next().hasClass("option-row")) {
        return;
    }
    create_option_row($(e.target));
}

function delete_option_row(e) {
    const $row = $(e.target).closest(".option-row");
    $row.remove();
}

export function poll_options_setup() {
    const $poll_options_list = $("#add-poll-form .poll-options-list");
    const $submit_button = $("#add-poll-modal .dialog_submit_button");
    const $question_input = $("#add-poll-form #poll-question-input");

    // Disable the submit button if the question is empty.
    $submit_button.prop("disabled", true);
    $question_input.on("input", () => {
        if ($question_input.val().trim() !== "") {
            $submit_button.prop("disabled", false);
        } else {
            $submit_button.prop("disabled", true);
        }
    });

    $poll_options_list.on("input", "input.poll-option-input", add_option_row);
    $poll_options_list.on("click", "button.delete-option", delete_option_row);

    // setTimeout is needed to here to give time for simplebar to initialise
    setTimeout(() => {
        Sortable.create($("#add-poll-form .poll-options-list .simplebar-content")[0], {
            onUpdate() {},
            // We don't want the last (empty) row to be draggable, as a new row
            // is added on input event of the last row.
            filter: "input, .option-row:last-child",
            preventOnFilter: false,
        });
    }, 0);
}

export function frame_poll_message_content() {
    const question = $("#poll-question-input").val().trim();
    const options = $(".poll-option-input")
        .map(function () {
            return $(this).val().trim();
        })
        .toArray()
        .filter(Boolean);
    return "/poll " + question + "\n" + options.join("\n");
}
