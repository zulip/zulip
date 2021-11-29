import $ from "jquery";

import render_widgets_todo_widget from "../templates/widgets/todo_widget.hbs";
import render_widgets_todo_widget_tasks from "../templates/widgets/todo_widget_tasks.hbs";

import * as blueslip from "./blueslip";
import {$t} from "./i18n";

// Any single user should send add a finite number of tasks
// to a todo list. We arbitrarily pick this value.
const MAX_IDX = 1000;

export class TaskData {
    task_map = new Map();
    my_idx = 1;

    constructor(task_list_name) {
        this.task_list_name = task_list_name;
        if (task_list_name) {
            this.set_task_list_name(task_list_name);
        }
    }

    get_widget_data() {
        const all_tasks = Array.from(this.task_map.values());

        const pending_tasks = [];
        const completed_tasks = [];

        for (const item of all_tasks) {
            if (item.completed) {
                completed_tasks.push(item);
            } else {
                pending_tasks.push(item);
            }
        }

        const widget_data = {
            pending_tasks,
            completed_tasks,
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

    set_task_list_name(task_list_name) {
        this.task_list_name = task_list_name;
    }

    get_task_list_name() {
        return this.task_list_name || "Task list";
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
            outbound: (key) => {
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

        change_pos: {
            outbound: (key_start, key_end) => {
                const event = {
                    type: "change_pos",
                    key_start,
                    key_end,
                };
                return event;
            },

            inbound: (sender_id, data) => {
                const key_start = data.key_start;
                const key_end = data.key_end;

                if (typeof key_start !== "string") {
                    blueslip.warn("todo widget: bad type for inbound task key");
                    return;
                }

                if (typeof key_end !== "string") {
                    blueslip.warn("todo widget: bad type for inbound task key");
                    return;
                }

                const task_start = this.task_map.get(key_start);
                const idx_start = task_start.idx;
                const task_end = this.task_map.get(key_end);

                task_start.idx = task_end.idx;
                task_start.key = task_end.key;
                task_end.idx = idx_start;
                task_end.key = key_start;

                this.task_map.set(task_start.key, task_start);
                this.task_map.set(task_end.key, task_end);
            },
        },

        task_list_name: {
            outbound: (task_list_name) => {
                const event = {
                    type: "task_list_name",
                    task_list_name,
                };
                return event;
            },

            inbound: (sender_id, data) => {
                const task_list_name = data.task_list_name;

                if (typeof task_list_name !== "string") {
                    blueslip.warn("todo widget: bad type for inbound task_list_name");
                    return;
                }

                this.set_task_list_name(task_list_name);
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
    const elem = opts.elem;
    const callback = opts.callback;

    const task_data = new TaskData(opts.extra_data ? opts.extra_data.name : "");

    function update_edit_controls() {
        const has_name = elem.find("input.todo-name").val().trim() !== "";
        elem.find("button.todo-name-check").toggle(has_name);
    }

    function render_task_list_name(start_editing = false) {
        const task_list_name = task_data.get_task_list_name();
        elem.find(".todo-name-header").text(task_list_name);
        elem.find(".todo-name-bar").toggle(start_editing);
        elem.find(".todo-name-header").toggle(!start_editing);
        elem.find("input.todo-name").val(task_list_name);
        update_edit_controls();
    }

    function start_editing() {
        render_task_list_name(true);
        elem.find("input.todo-name").trigger("focus");
    }

    function abort_edit() {
        render_task_list_name();
    }

    function submit_task_list_name() {
        let new_task_list_name = elem.find("input.todo-name").val().trim();
        const old_task_list_name = task_data.get_task_list_name();

        if (new_task_list_name === "") {
            new_task_list_name = old_task_list_name;
        }

        task_data.set_task_list_name(new_task_list_name);
        render_task_list_name();

        if (new_task_list_name === old_task_list_name) {
            return;
        }

        const data = task_data.handle.task_list_name.outbound(new_task_list_name);
        callback(data);
    }

    function render() {
        const html = render_widgets_todo_widget();
        elem.html(html);

        elem.find("button.add-task").on("click", (e) => {
            e.stopPropagation();
            elem.find(".widget-error").text("");
            const task = elem.find("input.add-task").val().trim();
            const desc = elem.find("input.add-desc").val().trim();

            if (task === "") {
                return;
            }

            elem.find(".add-task").val("").trigger("focus");
            elem.find(".add-desc").val("").trigger("focus");

            const task_exists = task_data.name_in_use(task);
            if (task_exists) {
                elem.find(".widget-error").text($t({defaultMessage: "Task already exists"}));
                return;
            }

            const data = task_data.handle.new_task.outbound(task, desc);
            callback(data);
        });

        elem.find("input.todo-name").on("keyup", (e) => {
            e.stopPropagation();
            update_edit_controls();
        });

        elem.find("input.todo-name").on("keydown", (e) => {
            e.stopPropagation();

            if (e.key === "Enter") {
                submit_task_list_name();
                return;
            }

            if (e.key === "Escape") {
                abort_edit();
                return;
            }
        });

        elem.find(".todo-edit-name").on("click", (e) => {
            e.stopPropagation();
            start_editing();
        });

        elem.find("button.todo-name-check").on("click", (e) => {
            e.stopPropagation();
            submit_task_list_name();
        });

        elem.find("button.todo-name-remove").on("click", (e) => {
            e.stopPropagation();
            abort_edit();
        });
    }

    function render_results() {
        const widget_data = task_data.get_widget_data();
        const html = render_widgets_todo_widget_tasks(widget_data);
        let dragged;
        elem.find("ul.todo-widget").html(html);
        elem.find(".widget-error").text("");

        elem.find("input.task").on("click", (e) => {
            e.stopPropagation();
            const key = $(e.target).attr("data-key");

            const data = task_data.handle.strike.outbound(key);
            callback(data);
        });

        elem.find(".task-item").on("dragstart", (e) => {
            dragged = $(e.target).attr("data-key");
            e.target.style.opacity = 0.5;
        });

        elem.find(".task-item").on("dragend", (e) => {
            e.target.style.opacity = "";
        });

        elem.find(".dropzone").on("dragover", (e) => {
            e.preventDefault();
        });

        elem.find(".dropzone").on("dragenter", (e) => {
            e.target.style.background = "hsl(0, 0%, 64%, 0.65)";
        });

        elem.find(".dropzone").on("dragleave", (e) => {
            e.target.style.background = "";
        });

        elem.find(".dropzone").on("drop", (e) => {
            e.target.style.background = "";
            const data = task_data.handle.change_pos.outbound(
                dragged,
                $(e.target).attr("data-key"),
            );
            callback(data);
        });
    }

    elem.handle_events = function (events) {
        for (const event of events) {
            task_data.handle_event(event.sender_id, event.data);
        }

        render_task_list_name();
        render_results();
    };

    render();
    render_task_list_name();
    render_results();
}
