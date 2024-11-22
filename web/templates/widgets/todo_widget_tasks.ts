import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";

export default function render_todo_widget_tasks(context) {
    const out = to_array(context.all_tasks).map(
        (task) => html`
            <li>
                <label class="checkbox">
                    <div class="todo-checkbox">
                        <input
                            type="checkbox"
                            class="task"
                            data-key="${task.key}"
                            ${to_bool(task.completed) ? "checked" : ""}
                        />
                        <span class="custom-checkbox"></span>
                    </div>
                    <div class="todo-task">
                        ${to_bool(task.completed)
                            ? html`
                                  <strike
                                      ><strong>${task.task}</strong>${to_bool(task.desc)
                                          ? html`: ${task.desc}`
                                          : ""}</strike
                                  >
                              `
                            : html`
                                  <strong>${task.task}</strong>${to_bool(task.desc)
                                      ? html`: ${task.desc}`
                                      : ""}
                              `}
                    </div>
                </label>
            </li>
        `,
    );
    return to_html(out);
}
