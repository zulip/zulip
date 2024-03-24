import $ from "jquery";
import assert from "minimalistic-assert";
import {z} from "zod";

import type {InboundData} from "../shared/src/poll_data";
import render_widgets_todo_widget from "../templates/widgets/todo_widget.hbs";
import render_widgets_todo_widget_tasks from "../templates/widgets/todo_widget_tasks.hbs";

import * as blueslip from "./blueslip";
import {$t} from "./i18n";
import type {Message} from "./message_store";
import {page_params} from "./page_params";
import * as people from "./people";

// Any single user should send add a finite number of tasks
// to a todo list. We arbitrarily pick this value.
const MAX_IDX = 1000;

type Task = {
    completed: boolean;
    task: string;
    desc: string;
    idx: number;
    key: string;
};

export type NewTaskOutboundData = {
    type: string;
    task: string;
    desc: string;
    key: number;
    completed: boolean;
};
export type StrikeOutboundData = {
    type: string;
    key: string;
};
export type TodoHandle = {
    [key: string]: {
        outbound: (...args: string[]) => InboundData | undefined;
        inbound: (sender_id: number, data: InboundData) => void;
    };
    new_task: {
        outbound: (task: string, desc: string) => NewTaskOutboundData | undefined;
        inbound: (sender_id: number, data: InboundData) => void;
    };
    strike: {
        outbound: (key: string) => StrikeOutboundData;
        inbound: (sender_id: number, data: InboundData) => void;
    };
};

const inbount_new_task_schema = z.object({
    key: z.number(),
    task: z.string(),
    desc: z.string(),
    completed: z.boolean(),
    type: z.literal("new_task"),
});

const inbound_strike_schema = z.object({
    key: z.string(),
    type: z.literal("strike"),
});

export class TaskData {
    task_map = new Map<string, Task>();
    my_idx = 1;
    me: number;

    constructor({current_user_id}: {current_user_id: number}) {
        this.me = current_user_id;
    }

    get_widget_data(): {all_tasks: Task[]} {
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

    // eslint-disable-next-line @typescript-eslint/member-ordering
    handle: TodoHandle = {
        new_task: {
            outbound: (task: string, desc: string) => {
                this.my_idx += 1;
                const event: NewTaskOutboundData = {
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

            inbound: (sender_id: number, data: InboundData): void => {
                const safe_data = inbount_new_task_schema.parse(data);
                // All messages readers may add tasks.
                // for legacy reasons, the inbound idx is
                // called key in the event
                const idx = safe_data.key;
                const task = safe_data.task;
                const desc = safe_data.desc;

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
                const completed = safe_data.completed;

                const task_data = {
                    task,
                    desc,
                    idx,
                    key,
                    completed: Boolean(completed),
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
            outbound(key: string) {
                const event: StrikeOutboundData = {
                    type: "strike",
                    key,
                };

                return event;
            },

            inbound: (_sender_id: number, data: InboundData): void => {
                const safe_data = inbound_strike_schema.parse(data);
                const key = safe_data.key;
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
    };

    handle_event(sender_id: number, data: InboundData): void {
        const type = data.type;
        if (this.handle[type]?.inbound !== undefined) {
            this.handle[type].inbound(sender_id, data);
        } else {
            blueslip.warn(`todo widget: unknown inbound type: ${type}`);
        }
    }
}

export function activate(opts: {
    $elem: JQuery;
    callback: (data: NewTaskOutboundData | StrikeOutboundData | undefined) => void;
    message: Message;
}): void {
    const $elem: JQuery = opts.$elem;
    const callback = opts.callback;

    const task_data = new TaskData({
        current_user_id: people.my_current_user_id(),
    });

    function render(): void {
        const html = render_widgets_todo_widget();
        $elem.html(html);

        $elem.find("button.add-task").on("click", (e) => {
            e.stopPropagation();
            $elem.find(".widget-error").text("");
            const taskValue = $elem?.find<HTMLInputElement>("input.add-task")?.val();
            assert(taskValue !== undefined, "taskValue is undefined");
            const task = taskValue.trim();
            const descValue = $elem?.find<HTMLInputElement>("input.add-desc")?.val();
            assert(descValue !== undefined, "descValue is undefined");
            const desc = descValue.trim();

            if (task === "") {
                return;
            }

            $elem.find("input.add-task").val("").trigger("focus");
            $elem.find("input.add-desc").val("");

            const task_exists = task_data.name_in_use(task);
            if (task_exists) {
                $elem.find(".widget-error").text($t({defaultMessage: "Task already exists"}));
                return;
            }

            const data = task_data.handle.new_task.outbound(task, desc);
            if (data) {
                callback(data);
            }
        });
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
            const data = task_data.handle.strike.outbound(key ?? "");
            callback(data);
        });
    }

    $elem.handle_events = function (events): void {
        for (const event of events) {
            task_data.handle_event(event.sender_id, event.data);
        }

        render_results();
    };

    render();
    render_results();
}
