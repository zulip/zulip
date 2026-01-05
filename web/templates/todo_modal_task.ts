import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_icon_button from "./components/icon_button.ts";

export default function render_todo_modal_task() {
    const out = html`<li class="option-row">
        <i class="zulip-icon zulip-icon-grip-vertical drag-icon"></i>
        <input
            type="text"
            class="todo-input modal_text_input"
            placeholder="${$t({defaultMessage: "New task"})}"
        />
        <div class="todo-description-container">
            <input
                type="text"
                class="todo-description-input modal_text_input"
                disabled="true"
                placeholder="${$t({defaultMessage: "Task description (optional)"})}"
            />
        </div>
        ${{
            __html: render_icon_button({
                ["aria-label"]: $t({defaultMessage: "Delete"}),
                icon: "trash",
                custom_classes: "delete-option",
                intent: "danger",
            }),
        }}
    </li> `;
    return to_html(out);
}
