import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_todo_widget() {
    const out = html`<div class="todo-widget">
        <div class="todo-widget-header-area">
            <h4 class="todo-task-list-title-header">${$t({defaultMessage: "Task list"})}</h4>
            <i class="fa fa-pencil todo-edit-task-list-title"></i>
            <div class="todo-task-list-title-bar">
                <input
                    type="text"
                    class="todo-task-list-title"
                    placeholder="${$t({defaultMessage: "Add todo task list title"})}"
                />
                <button class="todo-task-list-title-remove"><i class="fa fa-remove"></i></button>
                <button class="todo-task-list-title-check"><i class="fa fa-check"></i></button>
            </div>
        </div>
        <ul class="todo-widget"></ul>
        <div class="add-task-bar">
            <input type="text" class="add-task" placeholder="${$t({defaultMessage: "New task"})}" />
            <input
                type="text"
                class="add-desc"
                placeholder="${$t({defaultMessage: "Description"})}"
            />
            <button class="add-task">${$t({defaultMessage: "Add task"})}</button>
            <div class="widget-error"></div>
        </div>
    </div> `;
    return to_html(out);
}
