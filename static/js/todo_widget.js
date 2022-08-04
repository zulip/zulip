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

    constructor({
        message_sender_id,
        current_user_id,
        is_my_task_list,
        task_list_title,
        tasks,
        report_error_function,
    }) {
        this.message_sender_id = message_sender_id;
        this.me = current_user_id;
        this.is_my_task_list = is_my_task_list;
        // input_mode indicates if the task list title is being input currently
        this.input_mode = is_my_task_list; // for now
        this.report_error_function = report_error_function;

        if (task_list_title) {
            this.set_task_list_title(task_list_title);
        } else {
            this.set_task_list_title($t({defaultMessage: "Task list"}));
        }

        for (const [i, data] of tasks.entries()) {
            this.handle.new_task.inbound("canned", {
                // due to legacy reasons, key / idx for a task list
                // starts at 2 and increments by 2 for each task
                key: (i + 1) * 2,
                task: data.task,
                desc: data.desc,
            });
        }

        this.my_idx = 2 * tasks.length + 1;
    }

    set_task_list_title(new_title) {
        this.input_mode = false;
        this.task_list_title = new_title;
    }

    get_task_list_title() {
        return this.task_list_title;
    }

    set_input_mode() {
        this.input_mode = true;
    }

    clear_input_mode() {
        this.input_mode = false;
    }

    get_input_mode() {
        return this.input_mode;
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
        new_task_list_title: {
            outbound: (title) => {
                const event = {
                    type: "new_task_list_title",
                    title,
                };
                if (this.is_my_task_list) {
                    return event;
                }
                return undefined;
            },

            inbound: (sender_id, data) => {
                // Only the message author can edit questions.
                if (sender_id !== this.message_sender_id) {
                    this.report_error_function(
                        `user ${sender_id} is not allowed to edit the task list title`,
                    );
                    return;
                }

                if (typeof data.title !== "string") {
                    this.report_error_function("todo widget: bad type for inbound task list title");
                    return;
                }

                this.set_task_list_title(data.title);
            },
        },

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
            outbound(old_idx, new_idx) {
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

export function activate({
    $elem,
    callback,
    extra_data: {task_list_title = "", tasks = []} = {},
    message,
}) {
    const is_my_task_list = people.is_my_user_id(message.sender_id);
    const task_data = new TaskData({
        message_sender_id: message.sender_id,
        current_user_id: people.my_current_user_id(),
        is_my_task_list,
        task_list_title,
        tasks,
        report_error_function: blueslip.warn,
    });

    function update_edit_controls() {
        const has_title = $elem.find("input.todo-task-list-title").val().trim() !== "";
        $elem.find("button.todo-task-list-title-check").toggle(has_title);
    }

    function render_task_list_title() {
        const task_list_title = task_data.get_task_list_title();
        const input_mode = task_data.get_input_mode();
        const can_edit = is_my_task_list && !input_mode;

        $elem.find(".todo-task-list-title-header").toggle(!input_mode);
        $elem.find(".todo-task-list-title-header").text(task_list_title);
        $elem.find(".todo-edit-task-list-title").toggle(can_edit);
        update_edit_controls();

        $elem.find(".todo-task-list-title-bar").toggle(input_mode);
    }

    function start_editing() {
        task_data.set_input_mode();

        const task_list_title = task_data.get_task_list_title();
        $elem.find("input.todo-task-list-title").val(task_list_title);
        render_task_list_title();
        $elem.find("input.todo-task-list-title").trigger("focus");
    }

    function abort_edit() {
        task_data.clear_input_mode();
        render_task_list_title();
    }

    function submit_task_list_title() {
        const $task_list_title_input = $elem.find("input.todo-task-list-title");
        let new_task_list_title = $task_list_title_input.val().trim();
        const old_task_list_title = task_data.get_task_list_title();

        // We should disable the button for blank task list title,
        // so this is just defensive code.
        if (new_task_list_title.trim() === "") {
            new_task_list_title = old_task_list_title;
        }

        // Optimistically set the task list title locally.
        task_data.set_task_list_title(new_task_list_title);
        render_task_list_title();

        // If there were no actual edits, we can exit now.
        if (new_task_list_title === old_task_list_title) {
            return;
        }

        // Broadcast the new task list title to our peers.
        const data = task_data.handle.new_task_list_title.outbound(new_task_list_title);
        callback(data);
    }

    function build_widget() {
        const html = render_widgets_todo_widget();
        $elem.html(html);

        $elem.find("input.todo-task-list-title").on("keyup", (e) => {
            e.stopPropagation();
            update_edit_controls();
        });

        $elem.find("input.todo-task-list-title").on("keydown", (e) => {
            e.stopPropagation();

            if (e.key === "Enter") {
                submit_task_list_title();
                return;
            }

            if (e.key === "Escape") {
                abort_edit();
                return;
            }
        });

        $elem.find(".todo-edit-task-list-title").on("click", (e) => {
            e.stopPropagation();
            start_editing();
        });

        $elem.find("button.todo-task-list-title-check").on("click", (e) => {
            e.stopPropagation();
            submit_task_list_title();
        });

        $elem.find("button.todo-task-list-title-remove").on("click", (e) => {
            e.stopPropagation();
            abort_edit();
        });

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

        render_task_list_title();
        render_results();
    };

    build_widget();
    render_task_list_title();
    render_results();
}
