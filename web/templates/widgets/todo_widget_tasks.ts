import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";

export default function render_todo_widget_tasks(context) {
    const out = to_array(context.all_tasks).map(
        (task) => html`
            <li>
                <label class="checkbox">
                    <span class="todo-checkbox">
                        <input
                            type="checkbox"
                            class="task"
                            data-key="${task.key}"
                            ${to_bool(task.completed) ? "checked" : ""}
                        />
                        <span class="custom-checkbox"></span>
                    </span>
                    <span class="todo-task">
                        ${to_bool(task.completed)
                            ? html`
                                  <s
                                      ><strong>${task.task}</strong>${to_bool(task.desc)
                                          ? html`: ${task.desc}`
                                          : ""}</s
                                  >
                              `
                            : html`
                                  <strong>${task.task}</strong>${to_bool(task.desc)
                                      ? html`: ${task.desc}`
                                      : ""}
                              `}
                    </span>
                </label>
            </li>
        `,
    );
    return to_html(out);
}
