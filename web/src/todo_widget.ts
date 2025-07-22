import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_widgets_todo_widget from "../templates/widgets/todo_widget.hbs";
import render_widgets_todo_widget_tasks from "../templates/widgets/todo_widget_tasks.hbs";

import * as blueslip from "./blueslip.ts";
import {$t} from "./i18n.ts";
import type {Message} from "./message_store.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import type {Event} from "./poll_widget.ts";

// Any single user should send add a finite number of tasks
// to a todo list. We arbitrarily pick this value.
const MAX_IDX = 1000;

export const todo_widget_extra_data_schema = z.nullable(
    z.object({
        task_list_title: z.optional(z.string()),
        tasks: z.optional(z.array(z.object({task: z.string(), desc: z.string()}))),
    }),
);

const todo_widget_inbound_data = z.intersection(
    z.object({
        type: z.enum(["new_task", "new_task_list_title", "strike"]),
    }),
    z.record(z.string(), z.unknown()),
);

// TODO: This schema is being used to parse two completely
// different types of things (inbound and outbound data),
// which should be refactored so that the code here is
// clearer and less confusing.
const new_task_inbound_data_schema = z.object({
    type: z.optional(z.literal("new_task")),
    key: z.int().check(z.nonnegative(), z.lte(MAX_IDX)),
    task: z.string(),
    desc: z.string(),
    completed: z.boolean(),
});

type NewTaskOutboundData = z.output<typeof new_task_inbound_data_schema>;

type NewTaskTitleOutboundData = {
    type: "new_task_list_title";
    title: string;
};

type TaskStrikeOutboundData = {
    type: "strike";
    key: string;
};

type TodoTask = {
    task: string;
    desc: string;
};

type Task = {
    task: string;
    desc: string;
    idx: number;
    key: string;
    completed: boolean;
};

export type TodoWidgetOutboundData =
    | NewTaskTitleOutboundData
    | NewTaskOutboundData
    | TaskStrikeOutboundData;

export class TaskData {
    message_sender_id: number;
    me: number;
    is_my_task_list: boolean;
    input_mode: boolean;
    report_error_function: (msg: string, more_info?: Record<string, unknown>) => void;
    task_list_title: string;
    task_map = new Map<string, Task>();
    my_idx = 1;

    handle = {
        new_task_list_title: {
            outbound: (title: string): NewTaskTitleOutboundData | undefined => {
                const event = {
                    type: "new_task_list_title" as const,
                    title,
                };
                if (this.is_my_task_list) {
                    return event;
                }
                return undefined;
            },

            inbound: (sender_id: number, raw_data: unknown): void => {
                // Only the message author can edit questions.
                const new_task_title_inbound_data = z.object({
                    type: z.literal("new_task_list_title"),
                    title: z.string(),
                });
                const parsed = new_task_title_inbound_data.safeParse(raw_data);

                if (!parsed.success) {
                    this.report_error_function(
                        "todo widget: bad type for inbound task list title",
                        {error: parsed.error},
                    );
                    return;
                }
                const data = parsed.data;
                if (sender_id !== this.message_sender_id) {
                    this.report_error_function(
                        `user ${sender_id} is not allowed to edit the task list title`,
                    );
                    return;
                }

                this.set_task_list_title(data.title);
            },
        },

        new_task: {
            outbound: (task: string, desc: string): NewTaskOutboundData | undefined => {
                this.my_idx += 1;
                const event = {
                    type: "new_task" as const,
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

            inbound: (sender_id: number | string, raw_data: unknown): void => {
                // All readers may add tasks. For legacy reasons, the
                // inbound idx is called key in the event.

                const parsed = new_task_inbound_data_schema.safeParse(raw_data);
                if (!parsed.success) {
                    blueslip.warn("todo widget: bad type for inbound task data", {
                        error: parsed.error,
                    });
                    return;
                }

                const data = parsed.data;
                const idx = data.key;
                const task = data.task;
                const desc = data.desc;

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
            outbound(key: string): TaskStrikeOutboundData {
                const event = {
                    type: "strike" as const,
                    key,
                };

                return event;
            },

            inbound: (_sender_id: number, raw_data: unknown): void => {
                const task_strike_inbound_data_schema = z.object({
                    type: z.literal("strike"),
                    key: z.string(),
                });
                const parsed = task_strike_inbound_data_schema.safeParse(raw_data);
                if (!parsed.success) {
                    blueslip.warn("todo widget: bad type for inbound strike key", {
                        error: parsed.error,
                    });
                    return;
                }
                // All message readers may strike/unstrike todo tasks.
                const data = parsed.data;
                const key = data.key;
                const item = this.task_map.get(key);

                if (item === undefined) {
                    blueslip.warn("Do we have legacy data? unknown key for tasks: " + key);
                    return;
                }

                item.completed = !item.completed;
            },
        },
    };

    constructor({
        message_sender_id,
        current_user_id,
        is_my_task_list,
        task_list_title,
        tasks,
        report_error_function,
    }: {
        message_sender_id: number;
        current_user_id: number;
        is_my_task_list: boolean;
        task_list_title: string;
        tasks: TodoTask[];
        report_error_function: (msg: string, more_info?: Record<string, unknown>) => void;
    }) {
        this.message_sender_id = message_sender_id;
        this.me = current_user_id;
        this.is_my_task_list = is_my_task_list;
        // input_mode indicates if the task list title is being input currently
        this.input_mode = is_my_task_list; // for now
        this.report_error_function = report_error_function;
        this.task_list_title = "";
        if (task_list_title) {
            this.set_task_list_title(task_list_title);
        } else {
            this.set_task_list_title($t({defaultMessage: "Task list"}));
        }

        for (const [i, data] of tasks.entries()) {
            this.handle.new_task.inbound("canned", {
                key: i,
                task: data.task,
                desc: data.desc,
                completed: false,
            });
        }
    }

    set_task_list_title(new_title: string): void {
        this.input_mode = false;
        this.task_list_title = new_title;
    }

    get_task_list_title(): string {
        return this.task_list_title;
    }

    set_input_mode(): void {
        this.input_mode = true;
    }

    clear_input_mode(): void {
        this.input_mode = false;
    }

    get_input_mode(): boolean {
        return this.input_mode;
    }

    get_widget_data(): {
        all_tasks: Task[];
    } {
        const all_tasks = [...this.task_map.values()];

        const widget_data = {
            all_tasks,
        };

        return widget_data;
    }

    name_in_use(name: string): boolean {
        for (const item of this.task_map.values()) {
            if (item.task === name) {
                return true;
            }
        }

        return false;
    }

    handle_event(sender_id: number, raw_data: unknown): void {
        const parsed = todo_widget_inbound_data.safeParse(raw_data);
        if (!parsed.success) {
            return;
        }

        const {data} = parsed;
        const type = data.type;
        if (this.handle[type]) {
            this.handle[type].inbound(sender_id, data);
        } else {
            blueslip.warn(`todo widget: unknown inbound type: ${type}`);
        }
    }
}

export function activate({
    $elem,
    callback,
    extra_data,
    message,
}: {
    $elem: JQuery;
    callback: (data: TodoWidgetOutboundData | undefined) => void;
    extra_data: unknown;
    message: Message;
}): (events: Event[]) => void {
    const parse_result = todo_widget_extra_data_schema.safeParse(extra_data);
    if (!parse_result.success) {
        blueslip.warn("invalid todo extra data", {issues: parse_result.error.issues});
        return () => {
            /* we send a dummy function when extra data is invalid */
        };
    }
    const {data} = parse_result;
    const {task_list_title = "", tasks = []} = data ?? {};
    const is_my_task_list = people.is_my_user_id(message.sender_id);
    const task_data = new TaskData({
        message_sender_id: message.sender_id,
        current_user_id: people.my_current_user_id(),
        is_my_task_list,
        task_list_title,
        tasks,
        report_error_function: blueslip.warn,
    });

    function update_edit_controls(): void {
        const has_title =
            $elem.find<HTMLInputElement>("input.todo-task-list-title").val()?.trim() !== "";
        $elem.find("button.todo-task-list-title-check").toggle(has_title);
    }

    function render_task_list_title(): void {
        const task_list_title = task_data.get_task_list_title();
        const input_mode = task_data.get_input_mode();
        const can_edit = is_my_task_list && !input_mode;

        $elem.find(".todo-task-list-title-header").toggle(!input_mode);
        $elem.find(".todo-task-list-title-header").text(task_list_title);
        $elem.find(".todo-edit-task-list-title").toggle(can_edit);
        update_edit_controls();

        $elem.find(".todo-task-list-title-bar").toggle(input_mode);
    }

    function start_editing(): void {
        task_data.set_input_mode();

        const task_list_title = task_data.get_task_list_title();
        $elem.find("input.todo-task-list-title").val(task_list_title);
        render_task_list_title();
        $elem.find("input.todo-task-list-title").trigger("focus");
    }

    function abort_edit(): void {
        task_data.clear_input_mode();
        render_task_list_title();
    }

    function submit_task_list_title(): void {
        const $task_list_title_input = $elem.find<HTMLInputElement>("input.todo-task-list-title");
        let new_task_list_title = $task_list_title_input.val()?.trim() ?? "";
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

    function build_widget(): void {
        const html = render_widgets_todo_widget();
        $elem.html(html);

        // This throttling ensures that the function runs only after the user stops typing.
        const throttled_update_add_task_button = _.throttle(update_add_task_button, 300);
        $elem.find("input.add-task").on("keyup", (e) => {
            e.stopPropagation();
            throttled_update_add_task_button();
        });

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
            const task = $elem.find<HTMLInputElement>("input.add-task").val()?.trim() ?? "";
            const desc = $elem.find<HTMLInputElement>("input.add-desc").val()?.trim() ?? "";

            $elem.find("input.add-task").val("").trigger("focus");
            $elem.find("input.add-desc").val("");

            // This case should not generally occur.
            const task_exists = task_data.name_in_use(task);
            if (task_exists) {
                $elem.find(".widget-error").text($t({defaultMessage: "Task already exists"}));
                return;
            }

            const data = task_data.handle.new_task.outbound(task, desc);
            callback(data);
        });
    }

    function update_add_task_button(): void {
        const task = $elem.find<HTMLInputElement>("input.add-task").val()?.trim() ?? "";
        const task_exists = task_data.name_in_use(task);
        const $add_task_wrapper = $elem.find(".add-task-wrapper");
        const $add_task_button = $elem.find("button.add-task");

        if (task === "") {
            $add_task_wrapper.attr(
                "data-tippy-content",
                $t({defaultMessage: "Name the task before adding."}),
            );
            $add_task_button.prop("disabled", true);
        } else if (task_exists) {
            $add_task_wrapper.attr(
                "data-tippy-content",
                $t({defaultMessage: "Cannot add duplicate task."}),
            );
            $add_task_button.prop("disabled", true);
        } else {
            $add_task_wrapper.removeAttr("data-tippy-content");
            $add_task_button.prop("disabled", false);
        }
    }

    function render_results(): void {
        const widget_data = task_data.get_widget_data();
        const html = render_widgets_todo_widget_tasks(widget_data);
        $elem.find("ul.todo-widget").html(html);
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
            assert(key !== undefined);

            const data = task_data.handle.strike.outbound(key);
            callback(data);
        });

        update_add_task_button();
    }

    const handle_events = function (events: Event[]): void {
        for (const event of events) {
            task_data.handle_event(event.sender_id, event.data);
        }

        render_task_list_title();
        render_results();
    };

    build_widget();
    render_task_list_title();
    render_results();

    return handle_events;
}
