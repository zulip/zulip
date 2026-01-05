import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_todo_modal_task from "./todo_modal_task.ts";

export default function render_add_todo_list_modal() {
    const out = html`<form id="add-todo-form" class="new-style">
        <label class="todo-label">${$t({defaultMessage: "To-do list title"})}</label>
        <div class="todo-title-input-container">
            <input
                type="text"
                id="todo-title-input"
                autocomplete="off"
                value="${$t({defaultMessage: "Task list"})}"
                class="modal_text_input"
            />
        </div>
        <label class="todo-label">${$t({defaultMessage: "Tasks"})}</label>
        <p>${$t({defaultMessage: "Anyone can add more tasks after the to-do list is posted."})}</p>
        <ul class="todo-options-list" data-simplebar data-simplebar-tab-index="-1">
            ${{__html: render_todo_modal_task()}} ${{__html: render_todo_modal_task()}}
            ${{__html: render_todo_modal_task()}}
        </ul>
    </form> `;
    return to_html(out);
}
