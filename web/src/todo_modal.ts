import $ from "jquery";
import SortableJS from "sortablejs";

import render_todo_modal_option from "../templates/todo_modal_option.hbs";

function create_option_row($last_option_row_input: JQuery): void {
    const row_html = render_todo_modal_option();
    const $row_container = $last_option_row_input.closest(".simplebar-content");
    $row_container.append($(row_html));
}

function add_option_row(this: HTMLElement): void {
    // if the option triggering the input event e is not the last,
    // that is, its next sibling has the class `option-row`, we
    // do not add a new option row and return from this function
    // This handles a case when the next empty input row is already
    // added and user is updating the above row(s).
    if ($(this).closest(".option-row").next().hasClass("option-row")) {
        return;
    }
    create_option_row($(this));
}

function delete_option_row(this: HTMLElement): void {
    const $row = $(this).closest(".option-row");
    $row.remove();
}

export function todo_options_setup(): void {
    const $todo_options_list = $("#add-todo-form .todo-options-list");

    $todo_options_list.on("input", "input.todo-option-input", add_option_row);
    $todo_options_list.on("input", "input.todo-option-description", add_option_row);
    $todo_options_list.on("click", "button.delete-option", delete_option_row);

    // setTimeout is needed to here to give time for simplebar to initialise
    setTimeout(() => {
        SortableJS.create($("#add-todo-form .todo-options-list .simplebar-content")[0], {
            onUpdate() {
                // Do nothing on drag; the order is only processed on submission.
            },
            // We don't want the last (empty) row to be draggable, as a new row
            // is added on input event of the last row.
            filter: "input, .option-row:last-child",
            preventOnFilter: false,
        });
    }, 0);
}

export function frame_todo_message_content(): string {
    const title = $<HTMLInputElement>("input#todo-title-input").val()!.trim();

    const options = $<HTMLInputElement>("input.todo-option-input")
        .map(function () {
            return $(this).val()!.trim();
        })
        .toArray();

    const descriptions = $<HTMLInputElement>("input.todo-option-description")
        .map(function () {
            return $(this).val()!.trim();
        })
        .toArray();

    const task = options
        .map((option, index) => {
            const description = ": " + descriptions[index];
            if (option.trim() !== "") {
                return `${option}${description}`;
            }
            return "";
        })
        .filter(Boolean);

    return "/todo " + title + "\n" + task.join("\n");
}
