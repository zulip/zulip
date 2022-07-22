import $ from "jquery";
import {Sortable} from "sortablejs";

import render_widgets_todo_widget from "../templates/widgets/todo_widget.hbs";
import render_widgets_todo_widget_tasks from "../templates/widgets/todo_widget_tasks.hbs";

import * as blueslip from "./blueslip";
import {$t} from "./i18n";
import {page_params} from "./page_params";
import * as people from "./people";

// Any single user should send add a finite number of tasks
// to a todo list. We arbitrarily pick this value.
const MAX_IDX = 1000;

export class TaskData {
    task_map = new Map();
    my_idx = 1;

    constructor({current_user_id}) {
        this.me = current_user_id;
    }

    get_widget_data() {
        const all_tasks = Array.from(this.task_map.values());
        // idx indicates the (current and changeable) order of the todos
        all_tasks.sort((a, b) => a.idx - b.idx);

        const widget_data = {
            all_tasks,
        };

        return widget_data;
    }

    name_in_use(name) {
        for (const item of this.task_map.values()) {
            if (item.task === name) {
                return true;
            }
        }

        return false;
    }

    handle = {
        new_task: {
            outbound: (task, desc) => {
                this.my_idx += 1;
                const event = {
                    type: "new_task",
                    key: this.my_idx,
                    task,
                    desc,
                    completed: false,
                };

                if (!this.name_in_use(task)) {
                    return event;
                }
                return undefined;
            },

            inbound: (sender_id, data) => {
                // All messages readers may add tasks.
                // for legacy reasons, the inbound idx is
                // called key in the event
                const idx = data.key;
                const task = data.task;
                const desc = data.desc;

                if (!Number.isInteger(idx) || idx < 0 || idx > MAX_IDX) {
                    blueslip.warn("todo widget: bad type for inbound task idx");
                    return;
                }

                if (typeof task !== "string") {
                    blueslip.warn("todo widget: bad type for inbound task title");
                    return;
                }

                if (typeof desc !== "string") {
                    blueslip.warn("todo widget: bad type for inbound task desc");
                    return;
                }

                const key = idx + "," + sender_id;
                const completed = data.completed;

                const task_data = {
                    task,
                    desc,
                    idx,
                    key,
                    completed,
                };

                if (!this.name_in_use(task)) {
                    this.task_map.set(key, task_data);
                }

                // I may have added a task from another device.
                if (sender_id === this.me && this.my_idx <= idx) {
                    this.my_idx = idx + 1;
                }
            },
        },

        strike: {
            outbound(key) {
                const event = {
                    type: "strike",
                    key,
                };

                return event;
            },

            inbound: (sender_id, data) => {
                // All message readers may strike/unstrike todo tasks.
                const key = data.key;
                if (typeof key !== "string") {
                    blueslip.warn("todo widget: bad type for inbound strike key");
                    return;
                }

                const item = this.task_map.get(key);

                if (item === undefined) {
                    blueslip.warn("Do we have legacy data? unknown key for tasks: " + key);
                    return;
                }

                item.completed = !item.completed;
            },
        },

        change_order: {
            outbound: (old_idx, new_idx) => {
                const event = {
                    type: "change_order",
                    old_idx,
                    new_idx,
                };

                return event;
            },

            inbound: (sender_id, data) => {
                // All message readers may change order of todo tasks.
                const old_idx = data.old_idx;
                const new_idx = data.new_idx;

                if (!Number.isInteger(new_idx) || new_idx < 0 || new_idx > MAX_IDX) {
                    blueslip.warn("todo widget: bad type for inbound task idx");
                    return;
                }

                if (!Number.isInteger(old_idx) || old_idx < 0 || old_idx > MAX_IDX) {
                    blueslip.warn("todo widget: bad type for inbound task idx");
                    return;
                }

                const {all_tasks} = this.get_widget_data();
                all_tasks[old_idx / 2 - 1].idx = new_idx;
                if (old_idx < new_idx) {
                    // if a todo was moved down, shift up all todos between old and new position
                    for (let idx = old_idx + 2; idx <= new_idx; idx += 2) {
                        all_tasks[idx / 2 - 1].idx = idx - 2;
                    }
                } else {
                    // if a todo was moved up, shift down all todos between old and new position
                    for (let idx = new_idx; idx < old_idx; idx += 2) {
                        all_tasks[idx / 2 - 1].idx = idx + 2;
                    }
                }
            },
        },
    };

    handle_event(sender_id, data) {
        const type = data.type;
        if (this.handle[type] && this.handle[type].inbound) {
            this.handle[type].inbound(sender_id, data);
        } else {
            blueslip.warn(`todo widget: unknown inbound type: ${type}`);
        }
    }
}

export function activate(opts) {
    const $elem = opts.$elem;
    const callback = opts.callback;

    const task_data = new TaskData({
        current_user_id: people.my_current_user_id(),
    });

    function render() {
        const html = render_widgets_todo_widget();
        $elem.html(html);

        $elem.find("button.add-task").on("click", (e) => {
            e.stopPropagation();
            $elem.find(".widget-error").text("");
            const task = $elem.find("input.add-task").val().trim();
            const desc = $elem.find("input.add-desc").val().trim();

            if (task === "") {
                return;
            }

            $elem.find(".add-task").val("").trigger("focus");
            $elem.find(".add-desc").val("").trigger("focus");

            const task_exists = task_data.name_in_use(task);
            if (task_exists) {
                $elem.find(".widget-error").text($t({defaultMessage: "Task already exists"}));
                return;
            }

            const data = task_data.handle.new_task.outbound(task, desc);
            callback(data);
        });
    }

    function render_results() {
        const widget_data = task_data.get_widget_data();
        const html = render_widgets_todo_widget_tasks(widget_data);
        $elem.find("ul.todo-widget").html(html);
        Sortable.create($elem.find("ul.todo-widget")[0], {
            onUpdate(e) {
                const old_pos = e.oldDraggableIndex;
                const new_pos = e.newDraggableIndex;
                // The way `idx` is assigned initially is such that it starts
                // at 2 for a task list and increments by 2 for each task.
                // For example, for a list with 3 tasks, the `idx` values would
                // be 2, 4, and 6, while the actual indices in the tasks array
                // would, of course, be 0, 1 and 2. Hence the addition by 1
                // and doubling to convert from array index (`pos`) to `idx`
                const old_idx = (old_pos + 1) * 2;
                const new_idx = (new_pos + 1) * 2;
                const data = task_data.handle.change_order.outbound(old_idx, new_idx);
                callback(data);
            },
        });
        $elem.find(".widget-error").text("");

        $elem.find("input.task").on("click", (e) => {
            e.stopPropagation();

            if (page_params.is_spectator) {
                // Logically, spectators should not be able to toggle
                // TODO checkboxes. However, the browser changes the
                // checkbox's state before calling handlers like this,
                // so we need to just toggle the checkbox back to its
                // previous state.
                $(e.target).prop("checked", !$(e.target).is(":checked"));
                $(e.target).trigger("blur");
                return;
            }
            const key = $(e.target).attr("data-key");

            const data = task_data.handle.strike.outbound(key);
            callback(data);
        });
    }

    $elem.handle_events = function (events) {
        for (const event of events) {
            task_data.handle_event(event.sender_id, event.data);
        }

        render_results();
    };

    render();
    render_results();
}
