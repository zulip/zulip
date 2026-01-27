import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import {$t} from "./i18n.ts";

// Any single user should send add a finite number of tasks
// to a todo list. We arbitrarily pick this value.
const MAX_IDX = 1000;

export const todo_widget_extra_data_schema = z.object({
    task_list_title: z.optional(z.string()),
    tasks: z.optional(z.array(z.object({task: z.string(), desc: z.string()}))),
});

export type TodoWidgetExtraData = z.infer<typeof todo_widget_extra_data_schema>;

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
